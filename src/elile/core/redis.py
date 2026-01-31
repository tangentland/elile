"""Redis client and cache utilities for Elile.

Provides Redis connection management, caching, session storage,
and rate limiting functionality.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import wraps
from typing import Any, ParamSpec, TypeVar
from uuid import UUID

from redis.asyncio import ConnectionPool, Redis

from elile.config.settings import get_settings
from elile.core.context import get_current_context_or_none

# Type variables for decorators
P = ParamSpec("P")
T = TypeVar("T")


# Global connection pool
_pool: ConnectionPool | None = None
_client: Redis | None = None
_lock = asyncio.Lock()


async def get_redis_pool() -> ConnectionPool:
    """Get or create the Redis connection pool.

    Returns:
        Shared connection pool for Redis connections
    """
    global _pool
    if _pool is None:
        async with _lock:
            if _pool is None:
                settings = get_settings()
                _pool = ConnectionPool.from_url(
                    settings.REDIS_URL,
                    max_connections=settings.REDIS_MAX_CONNECTIONS,
                    decode_responses=True,
                )
    return _pool


async def get_redis_client() -> Redis:
    """Get or create the Redis client.

    Returns:
        Shared Redis client with connection pool
    """
    global _client
    if _client is None:
        async with _lock:
            if _client is None:
                pool = await get_redis_pool()
                _client = Redis(connection_pool=pool)
    return _client


async def close_redis() -> None:
    """Close Redis connection pool and client.

    Should be called during application shutdown.
    """
    global _pool, _client
    async with _lock:
        if _client is not None:
            await _client.close()
            _client = None
        if _pool is not None:
            await _pool.disconnect()
            _pool = None


@dataclass
class CacheResult:
    """Result from cache operations."""

    hit: bool
    value: Any
    ttl_remaining: int | None = None


class RedisCache:
    """High-level cache interface using Redis.

    Provides type-safe caching with automatic serialization,
    TTL management, and tenant isolation support.
    """

    def __init__(
        self,
        client: Redis | None = None,
        prefix: str = "cache",
        default_ttl: int = 3600,
    ):
        """Initialize Redis cache.

        Args:
            client: Redis client (uses global if None)
            prefix: Key prefix for namespacing
            default_ttl: Default TTL in seconds
        """
        self._client = client
        self.prefix = prefix
        self.default_ttl = default_ttl

    async def _get_client(self) -> Redis:
        """Get Redis client."""
        if self._client is not None:
            return self._client
        return await get_redis_client()

    def _make_key(self, key: str, tenant_isolated: bool = False) -> str:
        """Create namespaced cache key.

        Args:
            key: Base key
            tenant_isolated: If True, include tenant_id in key

        Returns:
            Full cache key with prefix
        """
        parts = [self.prefix]

        if tenant_isolated:
            ctx = get_current_context_or_none()
            if ctx and ctx.tenant_id:
                parts.append(f"tenant:{ctx.tenant_id}")

        parts.append(key)
        return ":".join(parts)

    async def get(
        self,
        key: str,
        *,
        tenant_isolated: bool = False,
    ) -> CacheResult:
        """Get value from cache.

        Args:
            key: Cache key
            tenant_isolated: If True, scope to current tenant

        Returns:
            CacheResult with hit status and value
        """
        client = await self._get_client()
        full_key = self._make_key(key, tenant_isolated)

        pipe = client.pipeline()
        pipe.get(full_key)
        pipe.ttl(full_key)
        results = await pipe.execute()

        value_json = results[0]
        ttl = results[1] if results[1] > 0 else None

        if value_json is None:
            return CacheResult(hit=False, value=None)

        value = json.loads(value_json)
        return CacheResult(hit=True, value=value, ttl_remaining=ttl)

    async def set(
        self,
        key: str,
        value: Any,
        *,
        ttl: int | None = None,
        tenant_isolated: bool = False,
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: TTL in seconds (uses default if None)
            tenant_isolated: If True, scope to current tenant

        Returns:
            True if set successfully
        """
        client = await self._get_client()
        full_key = self._make_key(key, tenant_isolated)
        effective_ttl = ttl if ttl is not None else self.default_ttl

        value_json = json.dumps(value, default=str)
        result = await client.set(full_key, value_json, ex=effective_ttl)
        return result is True

    async def delete(
        self,
        key: str,
        *,
        tenant_isolated: bool = False,
    ) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key
            tenant_isolated: If True, scope to current tenant

        Returns:
            True if key existed and was deleted
        """
        client = await self._get_client()
        full_key = self._make_key(key, tenant_isolated)
        result = await client.delete(full_key)
        return result > 0

    async def exists(
        self,
        key: str,
        *,
        tenant_isolated: bool = False,
    ) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key
            tenant_isolated: If True, scope to current tenant

        Returns:
            True if key exists
        """
        client = await self._get_client()
        full_key = self._make_key(key, tenant_isolated)
        result = await client.exists(full_key)
        return result > 0

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        *,
        ttl: int | None = None,
        tenant_isolated: bool = False,
    ) -> Any:
        """Get value from cache, or compute and store if missing.

        Args:
            key: Cache key
            factory: Function to compute value if missing
            ttl: TTL in seconds
            tenant_isolated: If True, scope to current tenant

        Returns:
            Cached or computed value
        """
        result = await self.get(key, tenant_isolated=tenant_isolated)
        if result.hit:
            return result.value

        # Compute value
        value = factory()
        if asyncio.iscoroutine(value):
            value = await value

        await self.set(key, value, ttl=ttl, tenant_isolated=tenant_isolated)
        return value

    async def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern.

        Args:
            pattern: Redis key pattern (e.g., "cache:tenant:*")

        Returns:
            Number of keys deleted
        """
        client = await self._get_client()
        full_pattern = f"{self.prefix}:{pattern}"

        # Use SCAN to find keys (safer than KEYS for large datasets)
        deleted = 0
        async for key in client.scan_iter(match=full_pattern):
            await client.delete(key)
            deleted += 1

        return deleted


@dataclass
class RateLimitResult:
    """Result from rate limit check."""

    allowed: bool
    remaining: int
    reset_at: datetime
    retry_after: int | None = None


class RateLimiter:
    """Token bucket rate limiter using Redis.

    Provides distributed rate limiting across multiple
    application instances.
    """

    def __init__(
        self,
        client: Redis | None = None,
        prefix: str = "ratelimit",
    ):
        """Initialize rate limiter.

        Args:
            client: Redis client (uses global if None)
            prefix: Key prefix for namespacing
        """
        self._client = client
        self.prefix = prefix

    async def _get_client(self) -> Redis:
        """Get Redis client."""
        if self._client is not None:
            return self._client
        return await get_redis_client()

    def _make_key(self, identifier: str, resource: str) -> str:
        """Create rate limit key."""
        return f"{self.prefix}:{resource}:{identifier}"

    async def check(
        self,
        identifier: str,
        resource: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check if request is allowed under rate limit.

        Uses sliding window algorithm for smooth rate limiting.

        Args:
            identifier: Who is making the request (e.g., tenant_id, IP)
            resource: What resource is being accessed
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            RateLimitResult with allowed status and metadata
        """
        client = await self._get_client()
        key = self._make_key(identifier, resource)
        now = datetime.now(UTC)
        now_ts = now.timestamp()

        # Sliding window using sorted set
        pipe = client.pipeline()

        # Remove old entries outside window
        window_start = now_ts - window_seconds
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current entries
        pipe.zcard(key)

        # Add current request (we'll remove if over limit)
        request_id = f"{now_ts}"
        pipe.zadd(key, {request_id: now_ts})

        # Set expiry on key
        pipe.expire(key, window_seconds)

        results = await pipe.execute()
        current_count = results[1]

        reset_at = datetime.fromtimestamp(now_ts + window_seconds, tz=UTC)

        if current_count >= limit:
            # Over limit - remove the request we just added
            await client.zrem(key, request_id)

            # Calculate retry after
            oldest_entry = await client.zrange(key, 0, 0, withscores=True)
            if oldest_entry:
                oldest_ts = oldest_entry[0][1]
                retry_after = int(oldest_ts + window_seconds - now_ts) + 1
            else:
                retry_after = window_seconds

            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=reset_at,
                retry_after=retry_after,
            )

        remaining = limit - current_count - 1
        return RateLimitResult(
            allowed=True,
            remaining=max(0, remaining),
            reset_at=reset_at,
        )

    async def reset(self, identifier: str, resource: str) -> bool:
        """Reset rate limit for identifier.

        Args:
            identifier: Who to reset
            resource: Which resource

        Returns:
            True if key existed and was deleted
        """
        client = await self._get_client()
        key = self._make_key(identifier, resource)
        result = await client.delete(key)
        return result > 0


class SessionStore:
    """Session storage using Redis.

    Provides secure session management with automatic
    expiration and optional tenant isolation.
    """

    def __init__(
        self,
        client: Redis | None = None,
        prefix: str = "session",
        ttl: int = 86400,  # 24 hours default
    ):
        """Initialize session store.

        Args:
            client: Redis client (uses global if None)
            prefix: Key prefix for namespacing
            ttl: Session TTL in seconds
        """
        self._client = client
        self.prefix = prefix
        self.ttl = ttl

    async def _get_client(self) -> Redis:
        """Get Redis client."""
        if self._client is not None:
            return self._client
        return await get_redis_client()

    def _make_key(self, session_id: str | UUID) -> str:
        """Create session key."""
        return f"{self.prefix}:{session_id}"

    async def create(
        self,
        session_id: str | UUID,
        data: dict[str, Any],
        *,
        ttl: int | None = None,
    ) -> bool:
        """Create new session.

        Args:
            session_id: Unique session identifier
            data: Session data
            ttl: Override default TTL

        Returns:
            True if created successfully
        """
        client = await self._get_client()
        key = self._make_key(session_id)
        effective_ttl = ttl if ttl is not None else self.ttl

        # Add metadata
        session_data = {
            **data,
            "_created_at": datetime.now(UTC).isoformat(),
            "_updated_at": datetime.now(UTC).isoformat(),
        }

        value = json.dumps(session_data, default=str)
        result = await client.set(key, value, ex=effective_ttl, nx=True)
        return result is True

    async def get(self, session_id: str | UUID) -> dict[str, Any] | None:
        """Get session data.

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if not found
        """
        client = await self._get_client()
        key = self._make_key(session_id)

        value = await client.get(key)
        if value is None:
            return None

        return json.loads(value)

    async def update(
        self,
        session_id: str | UUID,
        data: dict[str, Any],
        *,
        extend_ttl: bool = True,
    ) -> bool:
        """Update session data.

        Args:
            session_id: Session identifier
            data: Data to merge into session
            extend_ttl: If True, reset TTL

        Returns:
            True if session exists and was updated
        """
        client = await self._get_client()
        key = self._make_key(session_id)

        # Get existing session
        existing = await client.get(key)
        if existing is None:
            return False

        session_data = json.loads(existing)
        session_data.update(data)
        session_data["_updated_at"] = datetime.now(UTC).isoformat()

        value = json.dumps(session_data, default=str)

        if extend_ttl:
            await client.set(key, value, ex=self.ttl)
        else:
            await client.set(key, value, keepttl=True)

        return True

    async def delete(self, session_id: str | UUID) -> bool:
        """Delete session.

        Args:
            session_id: Session identifier

        Returns:
            True if session existed and was deleted
        """
        client = await self._get_client()
        key = self._make_key(session_id)
        result = await client.delete(key)
        return result > 0

    async def exists(self, session_id: str | UUID) -> bool:
        """Check if session exists.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists
        """
        client = await self._get_client()
        key = self._make_key(session_id)
        result = await client.exists(key)
        return result > 0

    async def touch(self, session_id: str | UUID) -> bool:
        """Extend session TTL without modifying data.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists and TTL was extended
        """
        client = await self._get_client()
        key = self._make_key(session_id)
        result = await client.expire(key, self.ttl)
        return result


def cached(
    key_template: str,
    ttl: int = 3600,
    tenant_isolated: bool = False,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for caching function results in Redis.

    Args:
        key_template: Cache key template with {arg} placeholders
        ttl: Cache TTL in seconds
        tenant_isolated: If True, scope cache to tenant

    Returns:
        Decorated function

    Example:
        @cached("user:{user_id}", ttl=300)
        async def get_user(user_id: str) -> User:
            ...
    """
    cache = RedisCache(prefix="fn")

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Build cache key from template
            # Get function argument names
            import inspect

            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            key = key_template.format(**bound.arguments)

            # Try cache
            result = await cache.get(key, tenant_isolated=tenant_isolated)
            if result.hit:
                return result.value

            # Call function
            value = await func(*args, **kwargs)

            # Cache result
            await cache.set(key, value, ttl=ttl, tenant_isolated=tenant_isolated)
            return value

        return wrapper

    return decorator
