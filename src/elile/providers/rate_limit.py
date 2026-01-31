"""Provider rate limiting for Elile.

This module provides rate limiting functionality for data providers,
implementing the token bucket algorithm for smooth rate limiting
with configurable per-provider limits.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from elile.core.logging import get_logger

logger = get_logger(__name__)


class RateLimitStrategy(str, Enum):
    """Rate limiting strategy."""

    TOKEN_BUCKET = "token_bucket"  # Smooth rate limiting with burst allowance
    SLIDING_WINDOW = "sliding_window"  # Strict windowed rate limiting


class RateLimitConfig(BaseModel):
    """Configuration for provider rate limiting.

    Defines the rate limit parameters using token bucket algorithm:
    - tokens_per_second: Refill rate (sustained throughput)
    - max_tokens: Bucket capacity (burst allowance)
    - initial_tokens: Starting tokens (optional, defaults to max_tokens)
    """

    tokens_per_second: float = Field(
        default=10.0,
        gt=0,
        description="Token refill rate per second",
    )
    max_tokens: float = Field(
        default=100.0,
        gt=0,
        description="Maximum tokens (burst capacity)",
    )
    initial_tokens: float | None = Field(
        default=None,
        description="Initial tokens (defaults to max_tokens)",
    )
    strategy: RateLimitStrategy = Field(
        default=RateLimitStrategy.TOKEN_BUCKET,
        description="Rate limiting strategy",
    )

    def model_post_init(self, __context: Any) -> None:
        """Set initial_tokens to max_tokens if not specified."""
        if self.initial_tokens is None:
            object.__setattr__(self, "initial_tokens", self.max_tokens)


@dataclass
class RateLimitStatus:
    """Current rate limit status for a provider."""

    provider_id: str
    available_tokens: float
    max_tokens: float
    tokens_per_second: float
    last_refill: datetime
    requests_allowed: int = 0
    requests_denied: int = 0

    @property
    def utilization(self) -> float:
        """Calculate bucket utilization (0.0 = empty, 1.0 = full)."""
        return self.available_tokens / self.max_tokens if self.max_tokens > 0 else 0.0

    @property
    def is_limited(self) -> bool:
        """Check if provider is currently rate limited."""
        return self.available_tokens < 1.0


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    tokens_remaining: float
    retry_after_seconds: float | None = None
    wait_time_seconds: float = 0.0

    @property
    def retry_after_ms(self) -> int | None:
        """Get retry-after in milliseconds."""
        if self.retry_after_seconds is None:
            return None
        return int(self.retry_after_seconds * 1000)


class RateLimitExceededError(Exception):
    """Raised when a rate limit is exceeded."""

    def __init__(
        self,
        provider_id: str,
        retry_after_seconds: float | None = None,
    ):
        self.provider_id = provider_id
        self.retry_after_seconds = retry_after_seconds

        message = f"Rate limit exceeded for provider: {provider_id}"
        if retry_after_seconds is not None:
            message += f" (retry after {retry_after_seconds:.1f}s)"

        super().__init__(message)


class TokenBucket:
    """Token bucket implementation for rate limiting.

    Uses the token bucket algorithm where:
    - Tokens are added at a constant rate (tokens_per_second)
    - Tokens accumulate up to a maximum (max_tokens)
    - Each request consumes one token
    - Requests are denied when no tokens are available

    This allows for smooth rate limiting with burst handling.
    """

    def __init__(self, provider_id: str, config: RateLimitConfig):
        """Initialize token bucket.

        Args:
            provider_id: ID of the provider this bucket limits.
            config: Rate limit configuration.
        """
        self.provider_id = provider_id
        self.config = config

        # Use explicit None check to allow initial_tokens=0.0
        self._tokens = (
            config.initial_tokens if config.initial_tokens is not None else config.max_tokens
        )
        self._last_refill = datetime.now(UTC)
        self._lock = asyncio.Lock()

        # Statistics
        self._requests_allowed = 0
        self._requests_denied = 0

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = datetime.now(UTC)
        elapsed = (now - self._last_refill).total_seconds()

        if elapsed > 0:
            tokens_to_add = elapsed * self.config.tokens_per_second
            self._tokens = min(self.config.max_tokens, self._tokens + tokens_to_add)
            self._last_refill = now

    def _tokens_needed_wait_time(self, tokens_needed: float = 1.0) -> float:
        """Calculate wait time to get required tokens.

        Args:
            tokens_needed: Number of tokens needed.

        Returns:
            Seconds to wait for tokens to become available.
        """
        if self._tokens >= tokens_needed:
            return 0.0

        tokens_deficit = tokens_needed - self._tokens
        return tokens_deficit / self.config.tokens_per_second

    async def acquire(self, tokens: float = 1.0, wait: bool = False) -> RateLimitResult:
        """Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire.
            wait: If True, wait for tokens; if False, fail immediately.

        Returns:
            RateLimitResult indicating success/failure and metadata.
        """
        async with self._lock:
            self._refill()

            wait_time = self._tokens_needed_wait_time(tokens)

            if wait_time > 0 and not wait:
                # Not enough tokens and not waiting
                self._requests_denied += 1
                logger.debug(
                    "rate_limit_denied",
                    provider_id=self.provider_id,
                    tokens_requested=tokens,
                    tokens_available=self._tokens,
                    wait_time_seconds=wait_time,
                )
                return RateLimitResult(
                    allowed=False,
                    tokens_remaining=self._tokens,
                    retry_after_seconds=wait_time,
                    wait_time_seconds=wait_time,
                )

            if wait_time > 0:
                # Release lock while waiting
                pass

        # If waiting, do so outside the lock
        if wait_time > 0 and wait:
            await asyncio.sleep(wait_time)
            async with self._lock:
                self._refill()

        async with self._lock:
            # Re-check after waiting
            if self._tokens < tokens:
                self._requests_denied += 1
                return RateLimitResult(
                    allowed=False,
                    tokens_remaining=self._tokens,
                    retry_after_seconds=self._tokens_needed_wait_time(tokens),
                )

            # Consume tokens
            self._tokens -= tokens
            self._requests_allowed += 1

            logger.debug(
                "rate_limit_allowed",
                provider_id=self.provider_id,
                tokens_consumed=tokens,
                tokens_remaining=self._tokens,
            )

            return RateLimitResult(
                allowed=True,
                tokens_remaining=self._tokens,
            )

    async def check(self, tokens: float = 1.0) -> RateLimitResult:
        """Check if tokens are available without consuming.

        Args:
            tokens: Number of tokens to check for.

        Returns:
            RateLimitResult indicating availability.
        """
        async with self._lock:
            self._refill()
            wait_time = self._tokens_needed_wait_time(tokens)

            return RateLimitResult(
                allowed=self._tokens >= tokens,
                tokens_remaining=self._tokens,
                retry_after_seconds=wait_time if wait_time > 0 else None,
                wait_time_seconds=wait_time,
            )

    def get_status(self) -> RateLimitStatus:
        """Get current bucket status.

        Returns:
            RateLimitStatus with current state.
        """
        # Note: Not thread-safe, for informational purposes
        return RateLimitStatus(
            provider_id=self.provider_id,
            available_tokens=self._tokens,
            max_tokens=self.config.max_tokens,
            tokens_per_second=self.config.tokens_per_second,
            last_refill=self._last_refill,
            requests_allowed=self._requests_allowed,
            requests_denied=self._requests_denied,
        )

    def reset(self) -> None:
        """Reset bucket to full capacity."""
        self._tokens = self.config.max_tokens
        self._last_refill = datetime.now(UTC)
        self._requests_allowed = 0
        self._requests_denied = 0


class ProviderRateLimitRegistry:
    """Registry for managing provider rate limiters.

    Provides centralized access to rate limiters and ensures
    one limiter per provider with configurable defaults.
    """

    def __init__(self, default_config: RateLimitConfig | None = None):
        """Initialize rate limit registry.

        Args:
            default_config: Default configuration for new limiters.
        """
        self._limiters: dict[str, TokenBucket] = {}
        self._configs: dict[str, RateLimitConfig] = {}
        self._default_config = default_config or RateLimitConfig()
        self._lock = asyncio.Lock()

    def configure_provider(
        self,
        provider_id: str,
        config: RateLimitConfig,
    ) -> None:
        """Configure rate limits for a specific provider.

        Args:
            provider_id: Provider ID.
            config: Rate limit configuration for this provider.
        """
        self._configs[provider_id] = config

        # Update existing limiter if present
        if provider_id in self._limiters:
            self._limiters[provider_id] = TokenBucket(provider_id, config)

        logger.info(
            "provider_rate_limit_configured",
            provider_id=provider_id,
            tokens_per_second=config.tokens_per_second,
            max_tokens=config.max_tokens,
        )

    def get_limiter(self, provider_id: str) -> TokenBucket:
        """Get or create rate limiter for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            TokenBucket for the provider.
        """
        if provider_id not in self._limiters:
            config = self._configs.get(provider_id, self._default_config)
            self._limiters[provider_id] = TokenBucket(provider_id, config)

        return self._limiters[provider_id]

    async def acquire(
        self,
        provider_id: str,
        tokens: float = 1.0,
        wait: bool = False,
    ) -> RateLimitResult:
        """Acquire tokens for a provider.

        Args:
            provider_id: Provider ID.
            tokens: Number of tokens to acquire.
            wait: If True, wait for tokens.

        Returns:
            RateLimitResult indicating success/failure.
        """
        limiter = self.get_limiter(provider_id)
        return await limiter.acquire(tokens, wait)

    async def acquire_or_raise(
        self,
        provider_id: str,
        tokens: float = 1.0,
    ) -> RateLimitResult:
        """Acquire tokens or raise RateLimitExceededError.

        Args:
            provider_id: Provider ID.
            tokens: Number of tokens to acquire.

        Returns:
            RateLimitResult if tokens acquired.

        Raises:
            RateLimitExceededError: If rate limit exceeded.
        """
        result = await self.acquire(provider_id, tokens, wait=False)

        if not result.allowed:
            raise RateLimitExceededError(
                provider_id=provider_id,
                retry_after_seconds=result.retry_after_seconds,
            )

        return result

    async def check(self, provider_id: str, tokens: float = 1.0) -> RateLimitResult:
        """Check if tokens are available without consuming.

        Args:
            provider_id: Provider ID.
            tokens: Number of tokens to check.

        Returns:
            RateLimitResult indicating availability.
        """
        limiter = self.get_limiter(provider_id)
        return await limiter.check(tokens)

    def can_execute(self, provider_id: str) -> bool:
        """Check if a request can be made to a provider.

        This is a synchronous check for quick decisions.

        Args:
            provider_id: Provider ID.

        Returns:
            True if tokens are likely available.
        """
        limiter = self.get_limiter(provider_id)
        # Refill happens during acquire, so check current state
        limiter._refill()
        return limiter._tokens >= 1.0

    def get_status(self, provider_id: str) -> RateLimitStatus:
        """Get rate limit status for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            RateLimitStatus for the provider.
        """
        limiter = self.get_limiter(provider_id)
        return limiter.get_status()

    def get_all_status(self) -> dict[str, RateLimitStatus]:
        """Get rate limit status for all tracked providers.

        Returns:
            Dict mapping provider_id to RateLimitStatus.
        """
        return {pid: self.get_status(pid) for pid in self._limiters.keys()}

    def reset(self, provider_id: str) -> None:
        """Reset rate limiter for a provider.

        Args:
            provider_id: Provider ID.
        """
        if provider_id in self._limiters:
            self._limiters[provider_id].reset()
            logger.info("provider_rate_limit_reset", provider_id=provider_id)

    def reset_all(self) -> None:
        """Reset all rate limiters."""
        for provider_id in list(self._limiters.keys()):
            self.reset(provider_id)


# Global registry instance
_rate_limit_registry: ProviderRateLimitRegistry | None = None


def get_rate_limit_registry() -> ProviderRateLimitRegistry:
    """Get the global rate limit registry.

    Returns:
        Shared ProviderRateLimitRegistry instance.
    """
    global _rate_limit_registry
    if _rate_limit_registry is None:
        _rate_limit_registry = ProviderRateLimitRegistry()
    return _rate_limit_registry


def reset_rate_limit_registry() -> None:
    """Reset the global rate limit registry.

    Primarily for testing purposes.
    """
    global _rate_limit_registry
    _rate_limit_registry = None
