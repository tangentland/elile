"""Unit tests for Provider Rate Limiting.

Tests the TokenBucket, ProviderRateLimitRegistry, and related classes.
"""

import asyncio
from datetime import UTC, datetime

import pytest

from elile.providers import (
    ProviderRateLimitRegistry,
    RateLimitConfig,
    RateLimitExceededError,
    RateLimitResult,
    RateLimitStatus,
    RateLimitStrategy,
    TokenBucket,
    get_rate_limit_registry,
    reset_rate_limit_registry,
)


# =============================================================================
# RateLimitConfig Tests
# =============================================================================


class TestRateLimitConfig:
    """Tests for RateLimitConfig model."""

    def test_defaults(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        assert config.tokens_per_second == 10.0
        assert config.max_tokens == 100.0
        assert config.initial_tokens == 100.0  # Should default to max_tokens
        assert config.strategy == RateLimitStrategy.TOKEN_BUCKET

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            tokens_per_second=5.0,
            max_tokens=50.0,
            initial_tokens=25.0,
        )
        assert config.tokens_per_second == 5.0
        assert config.max_tokens == 50.0
        assert config.initial_tokens == 25.0

    def test_initial_tokens_defaults_to_max(self):
        """Test initial_tokens defaults to max_tokens when not specified."""
        config = RateLimitConfig(max_tokens=75.0)
        assert config.initial_tokens == 75.0


# =============================================================================
# RateLimitResult Tests
# =============================================================================


class TestRateLimitResult:
    """Tests for RateLimitResult model."""

    def test_allowed_result(self):
        """Test result for allowed request."""
        result = RateLimitResult(
            allowed=True,
            tokens_remaining=5.0,
        )
        assert result.allowed is True
        assert result.tokens_remaining == 5.0
        assert result.retry_after_seconds is None
        assert result.retry_after_ms is None

    def test_denied_result(self):
        """Test result for denied request."""
        result = RateLimitResult(
            allowed=False,
            tokens_remaining=0.0,
            retry_after_seconds=2.5,
        )
        assert result.allowed is False
        assert result.tokens_remaining == 0.0
        assert result.retry_after_seconds == 2.5
        assert result.retry_after_ms == 2500


# =============================================================================
# RateLimitStatus Tests
# =============================================================================


class TestRateLimitStatus:
    """Tests for RateLimitStatus model."""

    def test_utilization(self):
        """Test utilization calculation."""
        status = RateLimitStatus(
            provider_id="test",
            available_tokens=25.0,
            max_tokens=100.0,
            tokens_per_second=10.0,
            last_refill=datetime.now(UTC),
        )
        assert status.utilization == 0.25

    def test_is_limited(self):
        """Test is_limited property."""
        # Not limited
        status = RateLimitStatus(
            provider_id="test",
            available_tokens=5.0,
            max_tokens=100.0,
            tokens_per_second=10.0,
            last_refill=datetime.now(UTC),
        )
        assert status.is_limited is False

        # Limited
        status = RateLimitStatus(
            provider_id="test",
            available_tokens=0.5,
            max_tokens=100.0,
            tokens_per_second=10.0,
            last_refill=datetime.now(UTC),
        )
        assert status.is_limited is True


# =============================================================================
# RateLimitExceededError Tests
# =============================================================================


class TestRateLimitExceededError:
    """Tests for RateLimitExceededError exception."""

    def test_error_message(self):
        """Test error message format."""
        error = RateLimitExceededError("test_provider")
        assert "test_provider" in str(error)
        assert error.provider_id == "test_provider"
        assert error.retry_after_seconds is None

    def test_error_with_retry_after(self):
        """Test error with retry_after."""
        error = RateLimitExceededError("test_provider", retry_after_seconds=5.5)
        assert "5.5s" in str(error)
        assert error.retry_after_seconds == 5.5


# =============================================================================
# TokenBucket Tests
# =============================================================================


class TestTokenBucket:
    """Tests for TokenBucket class."""

    @pytest.fixture
    def bucket(self):
        """Create a token bucket with test config."""
        config = RateLimitConfig(
            tokens_per_second=10.0,
            max_tokens=10.0,
            initial_tokens=10.0,
        )
        return TokenBucket("test_provider", config)

    @pytest.mark.asyncio
    async def test_initial_state(self, bucket):
        """Test initial bucket state."""
        status = bucket.get_status()
        assert status.provider_id == "test_provider"
        assert status.available_tokens == 10.0
        assert status.max_tokens == 10.0

    @pytest.mark.asyncio
    async def test_acquire_success(self, bucket):
        """Test successful token acquisition."""
        result = await bucket.acquire()
        assert result.allowed is True
        assert result.tokens_remaining == 9.0

    @pytest.mark.asyncio
    async def test_acquire_multiple(self, bucket):
        """Test multiple token acquisitions."""
        for i in range(10):
            result = await bucket.acquire()
            assert result.allowed is True
            # Use approximate comparison due to time-based refill
            expected = 9.0 - i
            assert result.tokens_remaining >= expected - 0.1
            assert result.tokens_remaining <= expected + 0.1

    @pytest.mark.asyncio
    async def test_acquire_denied(self, bucket):
        """Test token acquisition denied when empty."""
        # Drain the bucket
        for _ in range(10):
            await bucket.acquire()

        # Should be denied
        result = await bucket.acquire()
        assert result.allowed is False
        assert result.retry_after_seconds is not None
        assert result.retry_after_seconds > 0

    @pytest.mark.asyncio
    async def test_acquire_with_wait(self):
        """Test token acquisition with wait."""
        config = RateLimitConfig(
            tokens_per_second=20.0,  # 1 token per 50ms
            max_tokens=1.0,
            initial_tokens=0.0,  # Start empty
        )
        bucket = TokenBucket("test", config)

        # Should wait and succeed
        start = datetime.now(UTC)
        result = await bucket.acquire(wait=True)
        elapsed = (datetime.now(UTC) - start).total_seconds()

        assert result.allowed is True
        # At 20 tokens/second, need 50ms for 1 token
        # Allow some tolerance for timing variations
        assert elapsed >= 0.03  # Should have waited at least 30ms

    @pytest.mark.asyncio
    async def test_check_without_consuming(self, bucket):
        """Test checking tokens without consuming."""
        result = await bucket.check()
        assert result.allowed is True
        assert result.tokens_remaining == 10.0

        # Should still have all tokens
        status = bucket.get_status()
        assert status.available_tokens == 10.0

    @pytest.mark.asyncio
    async def test_refill_over_time(self):
        """Test token refill over time."""
        config = RateLimitConfig(
            tokens_per_second=100.0,  # Fast refill
            max_tokens=10.0,
            initial_tokens=0.0,
        )
        bucket = TokenBucket("test", config)

        # Wait for some refill
        await asyncio.sleep(0.05)  # 50ms = 5 tokens at 100/s

        result = await bucket.check()
        assert result.allowed is True
        assert result.tokens_remaining >= 4.0  # At least 4 tokens

    @pytest.mark.asyncio
    async def test_refill_capped_at_max(self):
        """Test that refill doesn't exceed max tokens."""
        config = RateLimitConfig(
            tokens_per_second=1000.0,  # Very fast
            max_tokens=10.0,
            initial_tokens=10.0,
        )
        bucket = TokenBucket("test", config)

        # Wait and check
        await asyncio.sleep(0.1)

        status = bucket.get_status()
        assert status.available_tokens <= 10.0  # Should not exceed max

    @pytest.mark.asyncio
    async def test_reset(self, bucket):
        """Test bucket reset."""
        # Drain the bucket
        for _ in range(10):
            await bucket.acquire()

        # Reset
        bucket.reset()

        status = bucket.get_status()
        assert status.available_tokens == 10.0
        assert status.requests_allowed == 0
        assert status.requests_denied == 0

    @pytest.mark.asyncio
    async def test_statistics(self, bucket):
        """Test request statistics tracking."""
        # Some allowed requests
        for _ in range(5):
            await bucket.acquire()

        # Drain remaining and get denied
        for _ in range(10):
            await bucket.acquire()

        status = bucket.get_status()
        assert status.requests_allowed == 10
        assert status.requests_denied == 5


# =============================================================================
# ProviderRateLimitRegistry Tests
# =============================================================================


class TestProviderRateLimitRegistry:
    """Tests for ProviderRateLimitRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create rate limit registry."""
        return ProviderRateLimitRegistry()

    def test_get_limiter_creates_new(self, registry):
        """Test getting limiter creates new one."""
        limiter = registry.get_limiter("provider1")
        assert isinstance(limiter, TokenBucket)
        assert limiter.provider_id == "provider1"

    def test_get_limiter_returns_same(self, registry):
        """Test getting limiter returns same instance."""
        limiter1 = registry.get_limiter("provider1")
        limiter2 = registry.get_limiter("provider1")
        assert limiter1 is limiter2

    def test_configure_provider(self, registry):
        """Test configuring provider-specific limits."""
        config = RateLimitConfig(
            tokens_per_second=5.0,
            max_tokens=50.0,
        )
        registry.configure_provider("provider1", config)

        limiter = registry.get_limiter("provider1")
        assert limiter.config.tokens_per_second == 5.0
        assert limiter.config.max_tokens == 50.0

    @pytest.mark.asyncio
    async def test_acquire(self, registry):
        """Test acquiring tokens through registry."""
        result = await registry.acquire("provider1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_acquire_or_raise_success(self, registry):
        """Test acquire_or_raise success."""
        result = await registry.acquire_or_raise("provider1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_acquire_or_raise_failure(self, registry):
        """Test acquire_or_raise raises when limited."""
        config = RateLimitConfig(
            tokens_per_second=1.0,
            max_tokens=1.0,
            initial_tokens=0.0,
        )
        registry.configure_provider("provider1", config)

        with pytest.raises(RateLimitExceededError) as exc_info:
            await registry.acquire_or_raise("provider1")

        assert exc_info.value.provider_id == "provider1"
        assert exc_info.value.retry_after_seconds is not None

    @pytest.mark.asyncio
    async def test_check(self, registry):
        """Test checking without consuming."""
        result = await registry.check("provider1")
        assert result.allowed is True

    def test_can_execute(self, registry):
        """Test synchronous can_execute check."""
        assert registry.can_execute("provider1") is True

    def test_get_status(self, registry):
        """Test getting status."""
        status = registry.get_status("provider1")
        assert isinstance(status, RateLimitStatus)
        assert status.provider_id == "provider1"

    @pytest.mark.asyncio
    async def test_get_all_status(self, registry):
        """Test getting all statuses."""
        await registry.acquire("provider1")
        await registry.acquire("provider2")

        all_status = registry.get_all_status()
        assert "provider1" in all_status
        assert "provider2" in all_status

    @pytest.mark.asyncio
    async def test_reset(self, registry):
        """Test resetting a provider."""
        config = RateLimitConfig(
            tokens_per_second=1.0,
            max_tokens=5.0,
            initial_tokens=5.0,
        )
        registry.configure_provider("provider1", config)

        # Consume some tokens
        for _ in range(3):
            await registry.acquire("provider1")

        # Reset
        registry.reset("provider1")

        status = registry.get_status("provider1")
        assert status.available_tokens == 5.0

    @pytest.mark.asyncio
    async def test_reset_all(self, registry):
        """Test resetting all providers."""
        await registry.acquire("provider1")
        await registry.acquire("provider2")

        registry.reset_all()

        # Both should be at full capacity
        status1 = registry.get_status("provider1")
        status2 = registry.get_status("provider2")
        assert status1.available_tokens == status1.max_tokens
        assert status2.available_tokens == status2.max_tokens


# =============================================================================
# Global Registry Tests
# =============================================================================


class TestGlobalRateLimitRegistry:
    """Tests for global registry functions."""

    def test_get_rate_limit_registry(self):
        """Test getting global registry."""
        reset_rate_limit_registry()
        registry1 = get_rate_limit_registry()
        registry2 = get_rate_limit_registry()
        assert registry1 is registry2

    def test_reset_rate_limit_registry(self):
        """Test resetting global registry."""
        registry1 = get_rate_limit_registry()
        reset_rate_limit_registry()
        registry2 = get_rate_limit_registry()
        assert registry1 is not registry2


# =============================================================================
# Concurrency Tests
# =============================================================================


class TestConcurrency:
    """Tests for concurrent rate limiting behavior."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self):
        """Test concurrent token acquisition is safe."""
        config = RateLimitConfig(
            tokens_per_second=0.1,  # Slow refill
            max_tokens=10.0,
            initial_tokens=10.0,
        )
        bucket = TokenBucket("test", config)

        # Launch many concurrent acquires
        tasks = [bucket.acquire() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        allowed = sum(1 for r in results if r.allowed)
        denied = sum(1 for r in results if not r.allowed)

        # Should have exactly 10 allowed (initial tokens)
        assert allowed == 10
        assert denied == 10

    @pytest.mark.asyncio
    async def test_concurrent_registry_access(self):
        """Test concurrent registry access is safe."""
        registry = ProviderRateLimitRegistry()

        async def acquire_many(provider_id: str):
            for _ in range(10):
                await registry.acquire(provider_id)

        # Concurrent access to multiple providers
        await asyncio.gather(
            acquire_many("provider1"),
            acquire_many("provider2"),
            acquire_many("provider3"),
        )

        # All providers should have used tokens
        status1 = registry.get_status("provider1")
        status2 = registry.get_status("provider2")
        status3 = registry.get_status("provider3")

        assert status1.requests_allowed == 10
        assert status2.requests_allowed == 10
        assert status3.requests_allowed == 10
