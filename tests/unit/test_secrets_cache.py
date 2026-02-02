"""Tests for secrets cache."""

import asyncio
from datetime import datetime, timedelta

import pytest

from elile.secrets.cache import (
    CachedSecret,
    CacheStats,
    SecretCache,
    SecretCacheConfig,
    create_secret_from_data,
)
from elile.secrets.protocol import SecretValue
from elile.secrets.types import SecretMetadata, SecretType


@pytest.fixture
def cache_config() -> SecretCacheConfig:
    """Create test cache config."""
    return SecretCacheConfig(
        enabled=True,
        default_ttl_seconds=300,
        max_entries=10,
        refresh_before_expiry_seconds=60,
        cleanup_interval_seconds=1,
    )


@pytest.fixture
def cache(cache_config: SecretCacheConfig) -> SecretCache:
    """Create test cache."""
    return SecretCache(cache_config)


@pytest.fixture
def sample_secret() -> SecretValue:
    """Create a sample secret value."""
    return create_secret_from_data(
        "elile/test/secret",
        {"key": "value"},
        SecretType.GENERIC,
    )


class TestSecretCacheConfig:
    """Tests for SecretCacheConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = SecretCacheConfig()

        assert config.enabled is True
        assert config.default_ttl_seconds == 300
        assert config.max_entries == 1000
        assert config.refresh_before_expiry_seconds == 60

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = SecretCacheConfig(
            enabled=False,
            default_ttl_seconds=600,
            max_entries=500,
        )

        assert config.enabled is False
        assert config.default_ttl_seconds == 600
        assert config.max_entries == 500


class TestCacheStats:
    """Tests for CacheStats."""

    def test_initial_stats(self) -> None:
        """Test initial stats are zero."""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.expirations == 0
        assert stats.entries == 0

    def test_hit_rate_zero(self) -> None:
        """Test hit rate when no requests."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self) -> None:
        """Test hit rate calculation."""
        stats = CacheStats(hits=80, misses=20)
        assert stats.hit_rate == 0.8

    def test_hit_rate_all_hits(self) -> None:
        """Test 100% hit rate."""
        stats = CacheStats(hits=100, misses=0)
        assert stats.hit_rate == 1.0


class TestCachedSecret:
    """Tests for CachedSecret."""

    def test_create_cached_secret(
        self,
        sample_secret: SecretValue,
    ) -> None:
        """Test creating a cached secret entry."""
        now = datetime.utcnow()
        expires = now + timedelta(seconds=300)

        cached = CachedSecret(
            value=sample_secret,
            cached_at=now,
            expires_at=expires,
        )

        assert cached.value == sample_secret
        assert cached.cached_at == now
        assert cached.expires_at == expires
        assert cached.access_count == 0


class TestSecretCache:
    """Tests for SecretCache."""

    def test_cache_disabled(self, sample_secret: SecretValue) -> None:
        """Test cache when disabled."""
        config = SecretCacheConfig(enabled=False)
        cache = SecretCache(config)

        cache.set("test", sample_secret)
        result = cache.get("test")

        assert result is None

    def test_cache_get_miss(self, cache: SecretCache) -> None:
        """Test cache miss."""
        result = cache.get("nonexistent")

        assert result is None
        assert cache.stats.misses == 1

    def test_cache_set_and_get(
        self,
        cache: SecretCache,
        sample_secret: SecretValue,
    ) -> None:
        """Test setting and getting a cached value."""
        cache.set("test", sample_secret)
        result = cache.get("test")

        assert result is not None
        assert result.data == sample_secret.data
        assert result.cached is True
        assert cache.stats.hits == 1

    def test_cache_expiration(
        self,
        sample_secret: SecretValue,
    ) -> None:
        """Test that expired entries return miss."""
        config = SecretCacheConfig(
            enabled=True,
            default_ttl_seconds=1,  # 1 second TTL
        )
        cache = SecretCache(config)

        cache.set("test", sample_secret)

        # Should hit initially
        assert cache.get("test") is not None

        # Wait for expiration
        import time

        time.sleep(1.1)

        # Should miss after expiration
        result = cache.get("test")
        assert result is None
        assert cache.stats.expirations == 1

    def test_cache_lru_eviction(
        self,
        cache: SecretCache,
    ) -> None:
        """Test LRU eviction when at capacity."""
        # Fill cache to capacity (max_entries=10)
        for i in range(10):
            secret = create_secret_from_data(
                f"elile/test/{i}",
                {"value": i},
            )
            cache.set(f"path_{i}", secret)

        # Access first entry to make it recent
        cache.get("path_0")

        # Add one more to trigger eviction
        new_secret = create_secret_from_data("elile/test/new", {"value": "new"})
        cache.set("path_new", new_secret)

        # path_1 should be evicted (oldest unused)
        assert cache.get("path_1") is None
        # path_0 should still exist (was accessed)
        assert cache.get("path_0") is not None
        # new entry should exist
        assert cache.get("path_new") is not None
        assert cache.stats.evictions >= 1

    def test_cache_invalidate(
        self,
        cache: SecretCache,
        sample_secret: SecretValue,
    ) -> None:
        """Test invalidating a cache entry."""
        cache.set("test", sample_secret)
        assert cache.get("test") is not None

        result = cache.invalidate("test")
        assert result is True
        assert cache.get("test") is None

    def test_cache_invalidate_nonexistent(
        self,
        cache: SecretCache,
    ) -> None:
        """Test invalidating nonexistent entry."""
        result = cache.invalidate("nonexistent")
        assert result is False

    def test_cache_invalidate_prefix(
        self,
        cache: SecretCache,
    ) -> None:
        """Test invalidating by prefix."""
        for i in range(5):
            secret = create_secret_from_data(f"elile/database/{i}", {"value": i})
            cache.set(f"elile/database/{i}", secret)

        for i in range(3):
            secret = create_secret_from_data(f"elile/ai/{i}", {"value": i})
            cache.set(f"elile/ai/{i}", secret)

        count = cache.invalidate_prefix("elile/database")
        assert count == 5

        # Database entries gone
        assert cache.get("elile/database/0") is None
        # AI entries still there
        assert cache.get("elile/ai/0") is not None

    def test_cache_clear(
        self,
        cache: SecretCache,
    ) -> None:
        """Test clearing all entries."""
        for i in range(5):
            secret = create_secret_from_data(f"elile/test/{i}", {"value": i})
            cache.set(f"path_{i}", secret)

        count = cache.clear()
        assert count == 5
        assert cache.stats.entries == 0

    def test_needs_refresh(
        self,
        sample_secret: SecretValue,
    ) -> None:
        """Test checking if entry needs refresh."""
        config = SecretCacheConfig(
            enabled=True,
            default_ttl_seconds=300,
            refresh_before_expiry_seconds=60,
        )
        cache = SecretCache(config)

        cache.set("test", sample_secret)

        # Should not need refresh initially
        assert cache.needs_refresh("test") is False

        # Nonexistent should need refresh
        assert cache.needs_refresh("nonexistent") is True

    def test_get_or_none(
        self,
        cache: SecretCache,
        sample_secret: SecretValue,
    ) -> None:
        """Test get_or_none method."""
        # Miss case
        value, needs_refresh = cache.get_or_none("nonexistent")
        assert value is None
        assert needs_refresh is True

        # Hit case
        cache.set("test", sample_secret)
        value, needs_refresh = cache.get_or_none("test")
        assert value is not None
        assert needs_refresh is False

    def test_custom_ttl(
        self,
        cache: SecretCache,
        sample_secret: SecretValue,
    ) -> None:
        """Test setting entry with custom TTL."""
        cache.set("test", sample_secret, ttl_seconds=600)

        # Entry should exist
        assert cache.get("test") is not None


class TestCreateSecretFromData:
    """Tests for create_secret_from_data helper."""

    def test_create_basic_secret(self) -> None:
        """Test creating a basic secret."""
        secret = create_secret_from_data(
            "elile/test/path",
            {"key": "value"},
        )

        assert secret.path == "elile/test/path"
        assert secret.data == {"key": "value"}
        assert secret.metadata.secret_type == SecretType.GENERIC
        assert secret.cached is False

    def test_create_secret_with_type(self) -> None:
        """Test creating secret with specific type."""
        secret = create_secret_from_data(
            "elile/database/postgres",
            {"host": "localhost"},
            SecretType.DATABASE,
            version=2,
        )

        assert secret.metadata.secret_type == SecretType.DATABASE
        assert secret.metadata.version == 2


@pytest.mark.asyncio
class TestSecretCacheAsync:
    """Async tests for SecretCache."""

    async def test_cleanup_expired(self) -> None:
        """Test cleanup of expired entries."""
        config = SecretCacheConfig(
            enabled=True,
            default_ttl_seconds=1,
        )
        cache = SecretCache(config)

        # Add entries
        for i in range(5):
            secret = create_secret_from_data(f"elile/test/{i}", {"value": i})
            cache.set(f"path_{i}", secret)

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Cleanup
        count = await cache.cleanup_expired()
        assert count == 5
        assert cache.stats.expirations == 5

    async def test_start_stop(self) -> None:
        """Test starting and stopping cache."""
        config = SecretCacheConfig(
            enabled=True,
            cleanup_interval_seconds=1,
        )
        cache = SecretCache(config)

        await cache.start()
        assert cache._cleanup_task is not None

        await cache.stop()
        assert cache._cleanup_task is None
