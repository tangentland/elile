"""Secret caching layer for reducing backend calls.

This module provides in-memory caching of secrets to reduce
load on the secrets backend and improve performance.
"""

import asyncio
import contextlib
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from elile.secrets.protocol import SecretValue
from elile.secrets.types import SecretMetadata, SecretType

logger = logging.getLogger(__name__)


@dataclass
class SecretCacheConfig:
    """Configuration for the secrets cache.

    Attributes:
        enabled: Whether caching is enabled
        default_ttl_seconds: Default TTL for cached entries
        max_entries: Maximum number of entries in the cache
        refresh_before_expiry_seconds: Refresh secrets this long before expiry
        cleanup_interval_seconds: How often to run cleanup
    """

    enabled: bool = True
    default_ttl_seconds: int = 300
    max_entries: int = 1000
    refresh_before_expiry_seconds: int = 60
    cleanup_interval_seconds: int = 60


@dataclass
class CachedSecret:
    """A cached secret entry.

    Attributes:
        value: The cached SecretValue
        cached_at: When the entry was cached
        expires_at: When the entry expires
        access_count: Number of times accessed from cache
        last_accessed: Last access time
    """

    value: SecretValue
    cached_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CacheStats:
    """Statistics about cache performance.

    Attributes:
        hits: Number of cache hits
        misses: Number of cache misses
        evictions: Number of entries evicted
        expirations: Number of entries expired
        entries: Current number of entries
        hit_rate: Cache hit rate (0.0 to 1.0)
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    entries: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


class SecretCache:
    """In-memory cache for secrets.

    Provides thread-safe caching with TTL expiration and LRU eviction
    when the cache is full.

    Example:
        cache = SecretCache(config)

        # Check cache first
        cached = cache.get(path)
        if cached is not None:
            return cached

        # Fetch from backend
        value = await backend.get_secret(path)

        # Store in cache
        cache.set(path, value)
    """

    def __init__(self, config: SecretCacheConfig | None = None):
        """Initialize the cache.

        Args:
            config: Cache configuration
        """
        self.config = config or SecretCacheConfig()
        self._cache: OrderedDict[str, CachedSecret] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = CacheStats()
        self._cleanup_task: asyncio.Task[None] | None = None

    @property
    def stats(self) -> CacheStats:
        """Get current cache statistics."""
        self._stats.entries = len(self._cache)
        return self._stats

    async def start(self) -> None:
        """Start the cache cleanup task."""
        if self.config.enabled and self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.debug("Secret cache cleanup task started")

    async def stop(self) -> None:
        """Stop the cache cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None
            logger.debug("Secret cache cleanup task stopped")

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of expired entries."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval_seconds)
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Cache cleanup error: {e}")

    def get(self, path: str) -> SecretValue | None:
        """Get a cached secret.

        Args:
            path: Path to the secret

        Returns:
            SecretValue if found and not expired, None otherwise
        """
        if not self.config.enabled:
            return None

        cached = self._cache.get(path)
        if cached is None:
            self._stats.misses += 1
            return None

        # Check expiration
        now = datetime.utcnow()
        if cached.expires_at <= now:
            # Expired - remove and return miss
            self._cache.pop(path, None)
            self._stats.misses += 1
            self._stats.expirations += 1
            return None

        # Cache hit - update stats and move to end (LRU)
        self._stats.hits += 1
        cached.access_count += 1
        cached.last_accessed = now
        self._cache.move_to_end(path)

        # Return a copy marked as cached
        return SecretValue(
            path=cached.value.path,
            data=cached.value.data,
            metadata=cached.value.metadata,
            cached=True,
            retrieved_at=cached.value.retrieved_at,
        )

    def set(
        self,
        path: str,
        value: SecretValue,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store a secret in the cache.

        Args:
            path: Path to the secret
            value: SecretValue to cache
            ttl_seconds: TTL override (uses default if not specified)
        """
        if not self.config.enabled:
            return

        ttl = ttl_seconds or self.config.default_ttl_seconds
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=ttl)

        # Evict if at capacity
        while len(self._cache) >= self.config.max_entries:
            # Remove oldest entry (first item in OrderedDict)
            oldest_key = next(iter(self._cache))
            self._cache.pop(oldest_key)
            self._stats.evictions += 1
            logger.debug(f"Evicted cache entry: {oldest_key}")

        # Add to cache
        self._cache[path] = CachedSecret(
            value=value,
            cached_at=now,
            expires_at=expires_at,
        )

    def invalidate(self, path: str) -> bool:
        """Invalidate a cached entry.

        Args:
            path: Path to invalidate

        Returns:
            True if entry was removed, False if not found
        """
        if path in self._cache:
            del self._cache[path]
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all entries matching a prefix.

        Args:
            prefix: Path prefix to match

        Returns:
            Number of entries invalidated
        """
        to_remove = [key for key in self._cache if key.startswith(prefix)]
        for key in to_remove:
            del self._cache[key]
        return len(to_remove)

    def clear(self) -> int:
        """Clear all cached entries.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache)
        self._cache.clear()
        return count

    async def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        async with self._lock:
            now = datetime.utcnow()
            expired = [path for path, cached in self._cache.items() if cached.expires_at <= now]
            for path in expired:
                del self._cache[path]
            self._stats.expirations += len(expired)
            return len(expired)

    def needs_refresh(self, path: str) -> bool:
        """Check if a cached entry needs refreshing.

        Returns True if the entry is within refresh_before_expiry_seconds
        of expiring, allowing proactive refresh.

        Args:
            path: Path to check

        Returns:
            True if entry should be refreshed
        """
        cached = self._cache.get(path)
        if cached is None:
            return True

        now = datetime.utcnow()
        refresh_at = cached.expires_at - timedelta(
            seconds=self.config.refresh_before_expiry_seconds
        )
        return now >= refresh_at

    def get_or_none(self, path: str) -> tuple[SecretValue | None, bool]:
        """Get a cached secret and whether it needs refresh.

        Useful for implementing stale-while-revalidate pattern.

        Args:
            path: Path to the secret

        Returns:
            Tuple of (value or None, needs_refresh)
        """
        value = self.get(path)
        if value is None:
            return None, True

        needs_refresh = self.needs_refresh(path)
        return value, needs_refresh


def create_secret_from_data(
    path: str,
    data: dict[str, Any],
    secret_type: SecretType = SecretType.GENERIC,
    version: int = 1,
) -> SecretValue:
    """Helper to create a SecretValue from raw data.

    Args:
        path: Secret path
        data: Secret data
        secret_type: Type of secret
        version: Version number

    Returns:
        SecretValue instance
    """
    now = datetime.utcnow()
    metadata = SecretMetadata(
        secret_type=secret_type,
        created_at=now,
        updated_at=now,
        version=version,
    )
    return SecretValue(
        path=path,
        data=data,
        metadata=metadata,
        cached=False,
        retrieved_at=now,
    )
