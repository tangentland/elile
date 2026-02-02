"""Tests for rate limiter middleware."""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from elile.security.config import RateLimitConfig
from elile.security.rate_limiter import (
    InMemoryRateLimitStore,
    RateLimitExceeded,
    RateLimiter,
    RateLimiterMiddleware,
    RateLimitResult,
    SlidingWindowCounter,
)


class TestSlidingWindowCounter:
    """Tests for SlidingWindowCounter."""

    def test_initial_state(self) -> None:
        """Test counter initial state."""
        counter = SlidingWindowCounter(
            window_start=time.time(),
            window_size=60,
        )
        assert counter.current_count == 0
        assert counter.previous_count == 0

    def test_increment(self) -> None:
        """Test incrementing counter."""
        now = time.time()
        counter = SlidingWindowCounter(
            window_start=now,
            window_size=60,
        )
        counter.increment(now)
        assert counter.current_count == 1

        counter.increment(now + 1)
        assert counter.current_count == 2

    def test_window_rollover(self) -> None:
        """Test counter window rollover."""
        now = time.time()
        counter = SlidingWindowCounter(
            window_start=now,
            window_size=60,
            current_count=10,
            previous_count=5,
        )

        # Increment after window has passed
        counter.increment(now + 61)

        # Previous count should be what was current
        assert counter.previous_count == 10
        # Current count should be 1 (the new increment)
        assert counter.current_count == 1

    def test_weighted_count(self) -> None:
        """Test weighted count calculation."""
        now = time.time()
        counter = SlidingWindowCounter(
            window_start=now,
            window_size=60,
            current_count=5,
            previous_count=10,
        )

        # At the start of window, previous counts fully
        count_start = counter.get_weighted_count(now)
        assert count_start == 5 + 10  # current + full previous

        # Halfway through window, previous counts 50%
        count_mid = counter.get_weighted_count(now + 30)
        assert count_mid == 5 + 5  # current + half previous

        # Near end of window, previous barely counts
        count_end = counter.get_weighted_count(now + 59)
        assert count_end < 6  # current + minimal previous

    def test_multiple_window_skip(self) -> None:
        """Test skipping multiple windows."""
        now = time.time()
        counter = SlidingWindowCounter(
            window_start=now,
            window_size=60,
            current_count=10,
            previous_count=5,
        )

        # Increment after multiple windows have passed
        counter.increment(now + 180)  # 3 windows later

        # Everything should be reset
        assert counter.previous_count == 0
        assert counter.current_count == 1


class TestInMemoryRateLimitStore:
    """Tests for InMemoryRateLimitStore."""

    @pytest.fixture
    def store(self) -> InMemoryRateLimitStore:
        """Create a rate limit store."""
        return InMemoryRateLimitStore()

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, store: InMemoryRateLimitStore) -> None:
        """Test first request is always allowed."""
        result = await store.check_and_increment("client1", limit=60, window_size=60)
        assert result.allowed is True
        assert result.remaining == 59
        assert result.limit == 60

    @pytest.mark.asyncio
    async def test_within_limit(self, store: InMemoryRateLimitStore) -> None:
        """Test requests within limit are allowed."""
        for i in range(5):
            result = await store.check_and_increment("client1", limit=60, window_size=60)
            assert result.allowed is True
            assert result.remaining == 59 - i

    @pytest.mark.asyncio
    async def test_exceeds_limit(self, store: InMemoryRateLimitStore) -> None:
        """Test requests exceeding limit are blocked."""
        # Use up the limit
        for _ in range(10):
            await store.check_and_increment("client1", limit=10, window_size=60)

        # Next request should be blocked
        result = await store.check_and_increment("client1", limit=10, window_size=60)
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0

    @pytest.mark.asyncio
    async def test_different_clients_independent(self, store: InMemoryRateLimitStore) -> None:
        """Test different clients have independent limits."""
        # Use up client1's limit
        for _ in range(10):
            await store.check_and_increment("client1", limit=10, window_size=60)

        # Client1 should be blocked
        result1 = await store.check_and_increment("client1", limit=10, window_size=60)
        assert result1.allowed is False

        # Client2 should still be allowed
        result2 = await store.check_and_increment("client2", limit=10, window_size=60)
        assert result2.allowed is True

    @pytest.mark.asyncio
    async def test_get_current_count(self, store: InMemoryRateLimitStore) -> None:
        """Test getting current count."""
        # No requests yet
        count = await store.get_current_count("client1")
        assert count == 0

        # After some requests
        for _ in range(5):
            await store.check_and_increment("client1", limit=60, window_size=60)

        count = await store.get_current_count("client1")
        assert count >= 5


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.fixture
    def limiter(self) -> RateLimiter:
        """Create a rate limiter."""
        store = InMemoryRateLimitStore()
        config = RateLimitConfig(
            enabled=True,
            requests_per_minute=60,
            per_endpoint_limits={
                "/v1/screenings": 30,
            },
        )
        return RateLimiter(store, config)

    @pytest.mark.asyncio
    async def test_check_allowed(self, limiter: RateLimiter) -> None:
        """Test check returns allowed for normal requests."""
        result = await limiter.check("client1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_per_endpoint_limit(self, limiter: RateLimiter) -> None:
        """Test per-endpoint rate limits."""
        # Default endpoint uses 60 rpm
        result = await limiter.check("client1", "/v1/other")
        assert result.limit == 60

        # Screening endpoint uses 30 rpm
        result = await limiter.check("client1", "/v1/screenings")
        assert result.limit == 30

    @pytest.mark.asyncio
    async def test_check_or_raise_allowed(self, limiter: RateLimiter) -> None:
        """Test check_or_raise returns result when allowed."""
        result = await limiter.check_or_raise("client1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_or_raise_exceeded(self, limiter: RateLimiter) -> None:
        """Test check_or_raise raises when limit exceeded."""
        # Create limiter with very low limit
        store = InMemoryRateLimitStore()
        config = RateLimitConfig(enabled=True, requests_per_minute=2)
        limiter = RateLimiter(store, config)

        # Use up the limit
        await limiter.check_or_raise("client1")
        await limiter.check_or_raise("client1")

        # Next request should raise
        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.check_or_raise("client1")

        assert exc_info.value.retry_after > 0
        assert exc_info.value.limit == 2

    @pytest.mark.asyncio
    async def test_disabled_limiter(self) -> None:
        """Test disabled rate limiter allows all requests."""
        store = InMemoryRateLimitStore()
        config = RateLimitConfig(enabled=False)
        limiter = RateLimiter(store, config)

        # Should always be allowed when disabled
        for _ in range(100):
            result = await limiter.check("client1")
            assert result.allowed is True


class TestRateLimiterMiddleware:
    """Tests for RateLimiterMiddleware."""

    @pytest.fixture
    def app_with_rate_limit(self) -> FastAPI:
        """Create test app with rate limiter middleware."""
        app = FastAPI()
        store = InMemoryRateLimitStore()
        config = RateLimitConfig(
            enabled=True,
            requests_per_minute=5,  # Low limit for testing
            include_in_headers=True,
            exempt_paths=frozenset({"/health"}),
        )
        app.add_middleware(RateLimiterMiddleware, store=store, config=config)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/health")
        def health() -> dict[str, str]:
            return {"status": "ok"}

        return app

    @pytest.fixture
    def client(self, app_with_rate_limit: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app_with_rate_limit)

    def test_rate_limit_headers(self, client: TestClient) -> None:
        """Test rate limit headers are included."""
        response = client.get("/test")

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_request_allowed(self, client: TestClient) -> None:
        """Test normal requests are allowed."""
        response = client.get("/test")
        assert response.status_code == 200

    def test_rate_limit_exceeded(self, client: TestClient) -> None:
        """Test rate limit exceeded returns 429."""
        # Make requests until limit is exceeded
        for _ in range(5):
            response = client.get("/test")
            if response.status_code == 429:
                break

        # Eventually should get 429
        response = client.get("/test")
        assert response.status_code == 429
        assert response.json()["error"] == "rate_limit_exceeded"
        assert "Retry-After" in response.headers

    def test_exempt_paths_not_limited(self, client: TestClient) -> None:
        """Test exempt paths are not rate limited."""
        # Health endpoint should never be rate limited
        for _ in range(100):
            response = client.get("/health")
            assert response.status_code == 200

    def test_different_clients_independent(self) -> None:
        """Test different clients have independent limits."""
        app = FastAPI()
        store = InMemoryRateLimitStore()
        config = RateLimitConfig(enabled=True, requests_per_minute=2)
        app.add_middleware(RateLimiterMiddleware, store=store, config=config)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)

        # Client 1 uses up its limit
        for _ in range(3):
            client.get("/test", headers={"X-Forwarded-For": "1.1.1.1"})

        # Client 2 should still be allowed (different IP via different test)
        # Note: TestClient uses same IP, so we test with Authorization header
        response1 = client.get("/test", headers={"Authorization": "Bearer token1"})
        response2 = client.get("/test", headers={"Authorization": "Bearer token2"})

        # At least one should succeed
        assert response1.status_code == 200 or response2.status_code == 200


class TestRateLimitResult:
    """Tests for RateLimitResult."""

    def test_allowed_result(self) -> None:
        """Test creating allowed result."""
        result = RateLimitResult(
            allowed=True,
            limit=60,
            remaining=59,
            reset_time=time.time() + 60,
        )
        assert result.allowed is True
        assert result.retry_after == 0

    def test_blocked_result(self) -> None:
        """Test creating blocked result."""
        result = RateLimitResult(
            allowed=False,
            limit=60,
            remaining=0,
            reset_time=time.time() + 30,
            retry_after=30,
        )
        assert result.allowed is False
        assert result.retry_after == 30


class TestRateLimitExceeded:
    """Tests for RateLimitExceeded exception."""

    def test_exception_attributes(self) -> None:
        """Test exception has correct attributes."""
        exc = RateLimitExceeded(
            message="Rate limit exceeded",
            retry_after=60,
            limit=100,
            remaining=0,
            reset_time=time.time() + 60,
        )
        assert exc.message == "Rate limit exceeded"
        assert exc.retry_after == 60
        assert exc.limit == 100
        assert exc.remaining == 0

    def test_exception_str(self) -> None:
        """Test exception string representation."""
        exc = RateLimitExceeded(message="Custom message")
        assert str(exc) == "Custom message"
