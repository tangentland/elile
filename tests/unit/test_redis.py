"""Unit tests for Redis cache and utilities."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid7

import pytest

from elile.core.redis import (
    RateLimiter,
    RedisCache,
    SessionStore,
    cached,
)


class TestRedisCache:
    """Tests for RedisCache."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Redis client.

        Note: pipeline() is a sync method that returns a pipeline object,
        while most other methods are async.
        """
        client = MagicMock()
        # Async methods
        client.get = AsyncMock()
        client.set = AsyncMock()
        client.delete = AsyncMock()
        client.exists = AsyncMock()
        client.scan_iter = MagicMock()
        return client

    @pytest.fixture
    def cache(self, mock_client):
        """Create cache with mock client."""
        return RedisCache(client=mock_client, prefix="test", default_ttl=300)

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache, mock_client):
        """Test getting existing value from cache."""
        # Setup mock - pipeline() is sync, returns object with async execute()
        pipe = MagicMock()
        pipe.get = MagicMock(return_value=pipe)
        pipe.ttl = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=['{"name": "test"}', 250])
        mock_client.pipeline.return_value = pipe

        result = await cache.get("my_key")

        assert result.hit is True
        assert result.value == {"name": "test"}
        assert result.ttl_remaining == 250

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache, mock_client):
        """Test getting non-existent value from cache."""
        pipe = MagicMock()
        pipe.get = MagicMock(return_value=pipe)
        pipe.ttl = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[None, -2])
        mock_client.pipeline.return_value = pipe

        result = await cache.get("missing_key")

        assert result.hit is False
        assert result.value is None

    @pytest.mark.asyncio
    async def test_set_value(self, cache, mock_client):
        """Test setting value in cache."""
        mock_client.set = AsyncMock(return_value=True)

        result = await cache.set("my_key", {"data": "value"})

        assert result is True
        mock_client.set.assert_called_once()
        call_args = mock_client.set.call_args
        assert call_args[0][0] == "test:my_key"
        assert json.loads(call_args[0][1]) == {"data": "value"}
        assert call_args[1]["ex"] == 300

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self, cache, mock_client):
        """Test setting value with custom TTL."""
        mock_client.set = AsyncMock(return_value=True)

        await cache.set("my_key", "value", ttl=60)

        call_args = mock_client.set.call_args
        assert call_args[1]["ex"] == 60

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, cache, mock_client):
        """Test deleting existing key."""
        mock_client.delete = AsyncMock(return_value=1)

        result = await cache.delete("my_key")

        assert result is True
        mock_client.delete.assert_called_once_with("test:my_key")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, cache, mock_client):
        """Test deleting non-existent key."""
        mock_client.delete = AsyncMock(return_value=0)

        result = await cache.delete("missing_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, cache, mock_client):
        """Test checking existing key."""
        mock_client.exists = AsyncMock(return_value=1)

        result = await cache.exists("my_key")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, cache, mock_client):
        """Test checking non-existent key."""
        mock_client.exists = AsyncMock(return_value=0)

        result = await cache.exists("missing_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_or_set_cache_hit(self, cache, mock_client):
        """Test get_or_set with cache hit."""
        pipe = MagicMock()
        pipe.get = MagicMock(return_value=pipe)
        pipe.ttl = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=['"cached_value"', 100])
        mock_client.pipeline.return_value = pipe

        factory = AsyncMock(return_value="computed_value")
        result = await cache.get_or_set("my_key", factory)

        assert result == "cached_value"
        factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss(self, cache, mock_client):
        """Test get_or_set with cache miss."""
        pipe = MagicMock()
        pipe.get = MagicMock(return_value=pipe)
        pipe.ttl = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[None, -2])
        mock_client.pipeline.return_value = pipe
        mock_client.set = AsyncMock(return_value=True)

        factory = AsyncMock(return_value="computed_value")
        result = await cache.get_or_set("my_key", factory)

        assert result == "computed_value"
        factory.assert_called_once()
        mock_client.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_tenant_isolated_key(self, cache, mock_client):
        """Test tenant isolation in cache keys."""
        mock_client.exists = AsyncMock(return_value=0)

        # Mock context
        mock_ctx = MagicMock()
        mock_ctx.tenant_id = uuid7()

        with patch("elile.core.redis.get_current_context_or_none", return_value=mock_ctx):
            await cache.exists("my_key", tenant_isolated=True)

        call_args = mock_client.exists.call_args[0][0]
        assert f"tenant:{mock_ctx.tenant_id}" in call_args

    @pytest.mark.asyncio
    async def test_clear_pattern(self, cache, mock_client):
        """Test clearing keys by pattern."""
        # scan_iter returns an async iterator
        mock_client.scan_iter = MagicMock(return_value=AsyncIterator(["test:key1", "test:key2"]))
        mock_client.delete = AsyncMock(return_value=1)

        deleted = await cache.clear_pattern("key*")

        assert deleted == 2


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Redis client."""
        client = MagicMock()
        client.delete = AsyncMock()
        client.zrem = AsyncMock()
        client.zrange = AsyncMock()
        return client

    @pytest.fixture
    def limiter(self, mock_client):
        """Create rate limiter with mock client."""
        return RateLimiter(client=mock_client, prefix="test")

    @pytest.mark.asyncio
    async def test_check_allowed(self, limiter, mock_client):
        """Test rate limit check when allowed."""
        pipe = MagicMock()
        pipe.zremrangebyscore = MagicMock(return_value=pipe)
        pipe.zcard = MagicMock(return_value=pipe)
        pipe.zadd = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[None, 5, None, True])
        mock_client.pipeline.return_value = pipe

        result = await limiter.check("user123", "api", limit=10, window_seconds=60)

        assert result.allowed is True
        assert result.remaining == 4

    @pytest.mark.asyncio
    async def test_check_denied(self, limiter, mock_client):
        """Test rate limit check when denied."""
        pipe = MagicMock()
        pipe.zremrangebyscore = MagicMock(return_value=pipe)
        pipe.zcard = MagicMock(return_value=pipe)
        pipe.zadd = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[None, 10, None, True])
        mock_client.pipeline.return_value = pipe
        mock_client.zrem = AsyncMock()
        mock_client.zrange = AsyncMock(return_value=[(b"1706745600", 1706745600.0)])

        result = await limiter.check("user123", "api", limit=10, window_seconds=60)

        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after is not None

    @pytest.mark.asyncio
    async def test_reset(self, limiter, mock_client):
        """Test resetting rate limit."""
        mock_client.delete = AsyncMock(return_value=1)

        result = await limiter.reset("user123", "api")

        assert result is True
        mock_client.delete.assert_called_once()


class TestSessionStore:
    """Tests for SessionStore."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def store(self, mock_client):
        """Create session store with mock client."""
        return SessionStore(client=mock_client, prefix="session", ttl=3600)

    @pytest.mark.asyncio
    async def test_create_session(self, store, mock_client):
        """Test creating new session."""
        mock_client.set = AsyncMock(return_value=True)
        session_id = uuid7()

        result = await store.create(session_id, {"user_id": "123"})

        assert result is True
        call_args = mock_client.set.call_args
        assert f"session:{session_id}" == call_args[0][0]
        data = json.loads(call_args[0][1])
        assert data["user_id"] == "123"
        assert "_created_at" in data

    @pytest.mark.asyncio
    async def test_create_session_already_exists(self, store, mock_client):
        """Test creating session when one already exists."""
        mock_client.set = AsyncMock(return_value=None)  # nx=True returns None if exists
        session_id = uuid7()

        result = await store.create(session_id, {"user_id": "123"})

        assert result is False

    @pytest.mark.asyncio
    async def test_get_session(self, store, mock_client):
        """Test getting session data."""
        session_data = {
            "user_id": "123",
            "_created_at": datetime.now(UTC).isoformat(),
            "_updated_at": datetime.now(UTC).isoformat(),
        }
        mock_client.get = AsyncMock(return_value=json.dumps(session_data))
        session_id = uuid7()

        result = await store.get(session_id)

        assert result["user_id"] == "123"
        assert "_created_at" in result

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, store, mock_client):
        """Test getting non-existent session."""
        mock_client.get = AsyncMock(return_value=None)
        session_id = uuid7()

        result = await store.get(session_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_session(self, store, mock_client):
        """Test updating session data."""
        existing_data = {"user_id": "123", "_created_at": "2024-01-01T00:00:00+00:00"}
        mock_client.get = AsyncMock(return_value=json.dumps(existing_data))
        mock_client.set = AsyncMock()
        session_id = uuid7()

        result = await store.update(session_id, {"role": "admin"})

        assert result is True
        call_args = mock_client.set.call_args
        updated_data = json.loads(call_args[0][1])
        assert updated_data["user_id"] == "123"
        assert updated_data["role"] == "admin"

    @pytest.mark.asyncio
    async def test_update_nonexistent_session(self, store, mock_client):
        """Test updating non-existent session."""
        mock_client.get = AsyncMock(return_value=None)
        session_id = uuid7()

        result = await store.update(session_id, {"role": "admin"})

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_session(self, store, mock_client):
        """Test deleting session."""
        mock_client.delete = AsyncMock(return_value=1)
        session_id = uuid7()

        result = await store.delete(session_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_session(self, store, mock_client):
        """Test checking session existence."""
        mock_client.exists = AsyncMock(return_value=1)
        session_id = uuid7()

        result = await store.exists(session_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_touch_session(self, store, mock_client):
        """Test extending session TTL."""
        mock_client.expire = AsyncMock(return_value=True)
        session_id = uuid7()

        result = await store.touch(session_id)

        assert result is True
        mock_client.expire.assert_called_once()


class TestCachedDecorator:
    """Tests for @cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_decorator_miss(self):
        """Test cached decorator with cache miss."""
        # Create mock client with proper structure
        mock_client = MagicMock()
        mock_client.set = AsyncMock(return_value=True)

        pipe = MagicMock()
        pipe.get = MagicMock(return_value=pipe)
        pipe.ttl = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[None, -2])
        mock_client.pipeline.return_value = pipe

        async def mock_get_client():
            return mock_client

        with patch("elile.core.redis.get_redis_client", mock_get_client):
            call_count = 0

            @cached("user:{user_id}", ttl=60)
            async def get_user(user_id: str) -> dict:
                nonlocal call_count
                call_count += 1
                return {"id": user_id, "name": "Test"}

            result = await get_user("123")

            assert result == {"id": "123", "name": "Test"}
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_cached_decorator_hit(self):
        """Test cached decorator with cache hit."""
        mock_client = MagicMock()

        pipe = MagicMock()
        pipe.get = MagicMock(return_value=pipe)
        pipe.ttl = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=['{"id": "123", "name": "Cached"}', 60])
        mock_client.pipeline.return_value = pipe

        async def mock_get_client():
            return mock_client

        with patch("elile.core.redis.get_redis_client", mock_get_client):
            call_count = 0

            @cached("user:{user_id}", ttl=60)
            async def get_user(user_id: str) -> dict:
                nonlocal call_count
                call_count += 1
                return {"id": user_id, "name": "Test"}

            result = await get_user("123")

            assert result == {"id": "123", "name": "Cached"}
            assert call_count == 0


# Helper for async iteration
class AsyncIterator:
    """Helper to create async iterator from list."""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item
