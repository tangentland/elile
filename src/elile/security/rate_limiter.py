"""Rate limiting middleware and utilities.

Implements sliding window rate limiting with:
- Per-client rate tracking (by IP or API key)
- Per-endpoint custom limits
- In-memory and extensible storage backends
- Rate limit headers in responses
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from elile.security.config import RateLimitConfig

if TYPE_CHECKING:
    from fastapi import Request, Response


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        limit: int = 60,
        remaining: int = 0,
        reset_time: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        self.reset_time = reset_time


@dataclass
class RateLimitResult:
    """Result of a rate limit check.

    Attributes:
        allowed: Whether the request is allowed
        limit: The rate limit for this client/endpoint
        remaining: Number of requests remaining in the window
        reset_time: Unix timestamp when the window resets
        retry_after: Seconds until the client can retry (if not allowed)
    """

    allowed: bool
    limit: int
    remaining: int
    reset_time: float
    retry_after: int = 0


@dataclass
class SlidingWindowCounter:
    """Sliding window counter for rate limiting.

    Uses a sliding window algorithm that provides smoother rate limiting
    than fixed windows. Tracks requests in the current and previous window
    to calculate a weighted count.

    Attributes:
        current_count: Requests in the current window
        previous_count: Requests in the previous window
        window_start: Start time of the current window
        window_size: Size of the window in seconds
    """

    current_count: int = 0
    previous_count: int = 0
    window_start: float = 0.0
    window_size: int = 60

    def get_weighted_count(self, now: float) -> float:
        """Get the weighted request count using sliding window.

        Args:
            now: Current timestamp

        Returns:
            Weighted count of requests
        """
        # Calculate position in current window
        time_in_window = now - self.window_start
        if time_in_window >= self.window_size:
            # Window has rolled over
            return float(self.current_count)

        # Weight previous window based on overlap
        weight = 1.0 - (time_in_window / self.window_size)
        return self.current_count + (self.previous_count * weight)

    def increment(self, now: float) -> None:
        """Increment the counter, handling window transitions.

        Args:
            now: Current timestamp
        """
        # Check if we need to roll to a new window
        if now - self.window_start >= self.window_size:
            # How many complete windows have passed?
            windows_passed = int((now - self.window_start) / self.window_size)

            if windows_passed == 1:
                # Roll to next window
                self.previous_count = self.current_count
                self.current_count = 1
                self.window_start += self.window_size
            else:
                # Multiple windows passed, reset everything
                self.previous_count = 0
                self.current_count = 1
                self.window_start = now
        else:
            self.current_count += 1


class RateLimitStore(Protocol):
    """Protocol for rate limit storage backends."""

    async def check_and_increment(self, key: str, limit: int, window_size: int) -> RateLimitResult:
        """Check rate limit and increment counter if allowed.

        Args:
            key: Unique identifier for the client/endpoint
            limit: Maximum requests allowed in the window
            window_size: Window size in seconds

        Returns:
            RateLimitResult with the check outcome
        """
        ...

    async def get_current_count(self, key: str) -> int:
        """Get the current request count for a key.

        Args:
            key: Unique identifier

        Returns:
            Current request count
        """
        ...


class InMemoryRateLimitStore(RateLimitStore):
    """In-memory rate limit storage using sliding window counters.

    Suitable for single-instance deployments. For multi-instance deployments,
    use a Redis-backed store.

    Example:
        store = InMemoryRateLimitStore()
        result = await store.check_and_increment("client:192.168.1.1", 60, 60)
        if not result.allowed:
            raise RateLimitExceeded(retry_after=result.retry_after)
    """

    def __init__(self, cleanup_interval: int = 300) -> None:
        """Initialize the store.

        Args:
            cleanup_interval: Seconds between cleanup of expired entries
        """
        self._counters: dict[str, SlidingWindowCounter] = {}
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

    async def check_and_increment(self, key: str, limit: int, window_size: int) -> RateLimitResult:
        """Check rate limit and increment counter if allowed."""
        now = time.time()

        # Periodic cleanup
        if now - self._last_cleanup > self._cleanup_interval:
            await self._cleanup(now, window_size)

        # Get or create counter
        if key not in self._counters:
            self._counters[key] = SlidingWindowCounter(
                window_start=now,
                window_size=window_size,
            )

        counter = self._counters[key]

        # Handle window rollover before checking
        if now - counter.window_start >= window_size:
            windows_passed = int((now - counter.window_start) / window_size)
            if windows_passed == 1:
                counter.previous_count = counter.current_count
                counter.current_count = 0
                counter.window_start += window_size
            else:
                counter.previous_count = 0
                counter.current_count = 0
                counter.window_start = now

        # Get weighted count
        weighted_count = counter.get_weighted_count(now)

        # Calculate reset time
        reset_time = counter.window_start + window_size

        if weighted_count >= limit:
            # Rate limit exceeded
            retry_after = max(1, int(reset_time - now))
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_time=reset_time,
                retry_after=retry_after,
            )

        # Increment counter
        counter.increment(now)

        # Calculate remaining
        remaining = max(0, int(limit - weighted_count - 1))

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=0,
        )

    async def get_current_count(self, key: str) -> int:
        """Get the current request count for a key."""
        now = time.time()
        if key not in self._counters:
            return 0
        counter = self._counters[key]
        return int(counter.get_weighted_count(now))

    async def _cleanup(self, now: float, window_size: int) -> None:
        """Clean up expired entries."""
        self._last_cleanup = now
        expired_keys = []

        for key, counter in self._counters.items():
            # Entry is expired if it's more than 2 windows old
            if now - counter.window_start > window_size * 2:
                expired_keys.append(key)

        for key in expired_keys:
            del self._counters[key]


class RateLimiter:
    """Rate limiter with configurable storage backend.

    Provides rate limiting functionality with support for:
    - Multiple storage backends (in-memory, Redis, etc.)
    - Per-endpoint custom limits
    - Client identification by IP or API key

    Example:
        store = InMemoryRateLimitStore()
        config = RateLimitConfig(requests_per_minute=60)
        limiter = RateLimiter(store, config)

        result = await limiter.check("192.168.1.1", "/v1/screenings")
        if not result.allowed:
            raise RateLimitExceeded(retry_after=result.retry_after)
    """

    def __init__(
        self,
        store: RateLimitStore,
        config: RateLimitConfig | None = None,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            store: Storage backend for rate limit counters
            config: Rate limit configuration
        """
        self.store = store
        self.config = config or RateLimitConfig()

    def _get_limit_for_endpoint(self, path: str) -> int:
        """Get the rate limit for a specific endpoint.

        Args:
            path: Request path

        Returns:
            Requests per minute limit for the endpoint
        """
        # Check for exact match first
        if path in self.config.per_endpoint_limits:
            return self.config.per_endpoint_limits[path]

        # Check for prefix match
        for endpoint_pattern, limit in self.config.per_endpoint_limits.items():
            if path.startswith(endpoint_pattern):
                return limit

        return self.config.requests_per_minute

    def _build_key(self, client_id: str, endpoint: str | None = None) -> str:
        """Build a rate limit key.

        Args:
            client_id: Client identifier (IP or API key)
            endpoint: Optional endpoint for per-endpoint limiting

        Returns:
            Rate limit key
        """
        if endpoint:
            return f"rate_limit:{client_id}:{endpoint}"
        return f"rate_limit:{client_id}"

    async def check(
        self,
        client_id: str,
        endpoint: str | None = None,
    ) -> RateLimitResult:
        """Check if a request is allowed.

        Args:
            client_id: Client identifier
            endpoint: Optional endpoint path

        Returns:
            RateLimitResult with the check outcome
        """
        if not self.config.enabled:
            return RateLimitResult(
                allowed=True,
                limit=self.config.requests_per_minute,
                remaining=self.config.requests_per_minute,
                reset_time=time.time() + 60,
            )

        limit = self._get_limit_for_endpoint(endpoint or "")
        key = self._build_key(client_id, endpoint)

        return await self.store.check_and_increment(
            key=key,
            limit=limit,
            window_size=self.config.window_size_seconds,
        )

    async def check_or_raise(
        self,
        client_id: str,
        endpoint: str | None = None,
    ) -> RateLimitResult:
        """Check rate limit and raise exception if exceeded.

        Args:
            client_id: Client identifier
            endpoint: Optional endpoint path

        Returns:
            RateLimitResult if allowed

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        result = await self.check(client_id, endpoint)
        if not result.allowed:
            raise RateLimitExceeded(
                message="Rate limit exceeded",
                retry_after=result.retry_after,
                limit=result.limit,
                remaining=result.remaining,
                reset_time=result.reset_time,
            )
        return result


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limiting on all requests.

    Adds rate limit headers to responses and returns 429 Too Many Requests
    when limits are exceeded.

    Example:
        from fastapi import FastAPI
        from elile.security.rate_limiter import (
            RateLimiterMiddleware,
            InMemoryRateLimitStore,
        )
        from elile.security.config import RateLimitConfig

        app = FastAPI()
        store = InMemoryRateLimitStore()
        config = RateLimitConfig(requests_per_minute=60)

        app.add_middleware(
            RateLimiterMiddleware,
            store=store,
            config=config,
        )
    """

    def __init__(
        self,
        app: ASGIApp,
        store: RateLimitStore | None = None,
        config: RateLimitConfig | None = None,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application
            store: Rate limit storage backend
            config: Rate limit configuration
        """
        super().__init__(app)
        self.store = store or InMemoryRateLimitStore()
        self.config = config or RateLimitConfig()
        self.limiter = RateLimiter(self.store, self.config)

    def _get_client_id(self, request: "Request") -> str:
        """Extract client identifier from request.

        Uses X-Forwarded-For if configured to trust proxies,
        otherwise uses the direct client IP.

        Args:
            request: The incoming request

        Returns:
            Client identifier string
        """
        # Check for API key in Authorization header first
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # Use a hash of the token as identifier (don't log actual tokens)
            import hashlib

            token = auth_header[7:]
            return f"token:{hashlib.sha256(token.encode()).hexdigest()[:16]}"

        # Use IP address
        if self.config.use_forwarded_for:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                # Take the first IP (client IP)
                client_ip = forwarded.split(",")[0].strip()
                # Verify it's from a trusted proxy
                if request.client and request.client.host in self.config.trusted_proxies:
                    return f"ip:{client_ip}"

        # Use direct client IP
        if request.client:
            return f"ip:{request.client.host}"

        return "ip:unknown"

    def _is_exempt(self, path: str) -> bool:
        """Check if a path is exempt from rate limiting."""
        if path in self.config.exempt_paths:
            return True
        return any(path.startswith(exempt) for exempt in self.config.exempt_paths)

    async def dispatch(
        self,
        request: "Request",
        call_next: Callable[["Request"], Awaitable["Response"]],
    ) -> "Response":
        """Process request and enforce rate limits."""
        from fastapi.responses import JSONResponse

        # Skip if not enabled
        if not self.config.enabled:
            response: "Response" = await call_next(request)
            return response

        # Skip exempt paths
        if self._is_exempt(request.url.path):
            response = await call_next(request)
            return response

        # Get client identifier
        client_id = self._get_client_id(request)

        # Check rate limit
        result = await self.limiter.check(client_id, request.url.path)

        if not result.allowed:
            # Return 429 Too Many Requests
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Rate limit exceeded. Please retry later.",
                    "retry_after": result.retry_after,
                },
                headers=self._build_rate_limit_headers(result),
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers if configured
        if self.config.include_in_headers:
            for header, value in self._build_rate_limit_headers(result).items():
                response.headers[header] = value

        return response

    def _build_rate_limit_headers(self, result: RateLimitResult) -> dict[str, str]:
        """Build rate limit response headers.

        Uses standard headers as per IETF draft:
        https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-ratelimit-headers
        """
        return {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(int(result.reset_time)),
            "Retry-After": str(result.retry_after) if result.retry_after > 0 else "",
        }
