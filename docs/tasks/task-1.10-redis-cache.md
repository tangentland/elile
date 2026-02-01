# Task 1.10: Redis Cache Layer

**Priority**: P1
**Phase**: 1 - Foundation
**Estimated Effort**: 2 days
**Dependencies**: Task 1.2 (Data Models), Task 1.9 (Repository Pattern)

## Context

Implement Redis caching layer to improve performance for frequently accessed data and reduce database load. Critical for screening state management, rate limiting, and session storage.

**Architecture Reference**: [02-core-system.md](../docs/architecture/02-core-system.md) - Cache Layer
**Related**: [10-platform.md](../docs/architecture/10-platform.md) - Scaling Strategy

## Objectives

1. Set up Redis connection pool and configuration
2. Implement cache decorator for automatic caching
3. Create cache strategies for different data types
4. Add cache invalidation patterns
5. Support distributed locking for critical operations

## Technical Approach

### Redis Configuration

```python
# src/elile/config/cache.py
from pydantic_settings import BaseSettings

class CacheSettings(BaseSettings):
    """Redis cache configuration."""

    redis_url: str = "redis://localhost:6379/0"
    redis_password: Optional[str] = None
    redis_max_connections: int = 50
    redis_socket_timeout: int = 5
    redis_socket_connect_timeout: int = 5

    # Cache TTLs (seconds)
    cache_ttl_screening: int = 300  # 5 minutes
    cache_ttl_subject: int = 600  # 10 minutes
    cache_ttl_org: int = 3600  # 1 hour
    cache_ttl_compliance: int = 86400  # 24 hours

    # Key prefixes
    cache_prefix_screening: str = "screening:"
    cache_prefix_subject: str = "subject:"
    cache_prefix_org: str = "org:"
    cache_prefix_lock: str = "lock:"

    class Config:
        env_file = ".env"
        env_prefix = "ELILE_"

cache_settings = CacheSettings()
```

### Redis Client

```python
# src/elile/cache/redis_client.py
import json
from typing import Optional, Any
from redis import Redis, ConnectionPool
from elile.config.cache import cache_settings

class RedisClient:
    """Redis client wrapper."""

    def __init__(self):
        self.pool = ConnectionPool.from_url(
            cache_settings.redis_url,
            password=cache_settings.redis_password,
            max_connections=cache_settings.redis_max_connections,
            socket_timeout=cache_settings.redis_socket_timeout,
            socket_connect_timeout=cache_settings.redis_socket_connect_timeout,
            decode_responses=True
        )
        self.client = Redis(connection_pool=self.pool)

    def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        return self.client.get(key)

    def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value with optional TTL."""
        if ttl:
            return self.client.setex(key, ttl, value)
        return self.client.set(key, value)

    def delete(self, key: str) -> int:
        """Delete key."""
        return self.client.delete(key)

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        keys = self.client.keys(pattern)
        if keys:
            return self.client.delete(*keys)
        return 0

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        return self.client.exists(key) > 0

    def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter."""
        return self.client.incr(key, amount)

    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL on existing key."""
        return self.client.expire(key, ttl)

# Global Redis client instance
redis_client = RedisClient()
```

### Cache Service

```python
# src/elile/cache/cache_service.py
import json
import hashlib
from typing import Optional, Any, Callable, TypeVar
from functools import wraps
from elile.cache.redis_client import redis_client
from elile.utils.serialization import to_json, from_json

T = TypeVar("T")

class CacheService:
    """High-level cache service."""

    def __init__(self, prefix: str, default_ttl: int):
        self.prefix = prefix
        self.default_ttl = default_ttl

    def _make_key(self, key: str) -> str:
        """Create prefixed cache key."""
        return f"{self.prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        cache_key = self._make_key(key)
        value = redis_client.get(cache_key)

        if value is None:
            return None

        return from_json(value)

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set cached value."""
        cache_key = self._make_key(key)
        ttl = ttl or self.default_ttl
        serialized = to_json(value)
        return redis_client.set(cache_key, serialized, ttl)

    def delete(self, key: str) -> int:
        """Delete cached value."""
        cache_key = self._make_key(key)
        return redis_client.delete(cache_key)

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        cache_pattern = self._make_key(pattern)
        return redis_client.delete_pattern(cache_pattern)

    def cached(
        self,
        key_fn: Optional[Callable[..., str]] = None,
        ttl: Optional[int] = None
    ):
        """Decorator for automatic caching."""
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            def wrapper(*args, **kwargs) -> T:
                # Generate cache key
                if key_fn:
                    cache_key = key_fn(*args, **kwargs)
                else:
                    # Default: hash function name and arguments
                    key_parts = [func.__name__]
                    key_parts.extend(str(arg) for arg in args)
                    key_parts.extend(f"{k}={v}" for k, v in kwargs.items())
                    key_str = ":".join(key_parts)
                    cache_key = hashlib.sha256(key_str.encode()).hexdigest()[:16]

                # Try cache first
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                # Execute function and cache result
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                return result

            return wrapper
        return decorator

# Cache service instances
screening_cache = CacheService(
    prefix="screening:",
    default_ttl=300
)

subject_cache = CacheService(
    prefix="subject:",
    default_ttl=600
)

org_cache = CacheService(
    prefix="org:",
    default_ttl=3600
)
```

### Distributed Lock

```python
# src/elile/cache/lock.py
import time
import uuid
from contextlib import contextmanager
from typing import Optional
from elile.cache.redis_client import redis_client

class DistributedLock:
    """Redis-based distributed lock."""

    def __init__(
        self,
        key: str,
        timeout: int = 30,
        retry_interval: float = 0.1
    ):
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.lock_value = str(uuid.uuid4())

    def acquire(self, blocking: bool = True, timeout: Optional[int] = None) -> bool:
        """Acquire lock."""
        deadline = time.time() + (timeout or self.timeout) if blocking else 0

        while True:
            # Try to set lock with NX (only if not exists)
            acquired = redis_client.client.set(
                self.key,
                self.lock_value,
                ex=self.timeout,
                nx=True
            )

            if acquired:
                return True

            if not blocking:
                return False

            if time.time() >= deadline:
                return False

            time.sleep(self.retry_interval)

    def release(self) -> bool:
        """Release lock."""
        # Use Lua script to ensure atomic check-and-delete
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = redis_client.client.eval(
            lua_script,
            1,
            self.key,
            self.lock_value
        )
        return result == 1

    def __enter__(self):
        """Context manager entry."""
        if not self.acquire():
            raise TimeoutError(f"Failed to acquire lock: {self.key}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()

@contextmanager
def distributed_lock(key: str, timeout: int = 30):
    """Context manager for distributed locking."""
    lock = DistributedLock(key, timeout)
    try:
        if not lock.acquire():
            raise TimeoutError(f"Failed to acquire lock: {key}")
        yield lock
    finally:
        lock.release()
```

### Cache Invalidation

```python
# src/elile/cache/invalidation.py
from typing import List
from elile.cache.cache_service import (
    screening_cache,
    subject_cache,
    org_cache
)

class CacheInvalidator:
    """Handles cache invalidation patterns."""

    @staticmethod
    def invalidate_screening(screening_id: str) -> None:
        """Invalidate screening cache."""
        screening_cache.delete(screening_id)
        screening_cache.invalidate_pattern(f"{screening_id}:*")

    @staticmethod
    def invalidate_subject(subject_id: str) -> None:
        """Invalidate subject and related screenings."""
        subject_cache.delete(subject_id)
        screening_cache.invalidate_pattern(f"*:subject:{subject_id}")

    @staticmethod
    def invalidate_org(org_id: str) -> None:
        """Invalidate organization cache."""
        org_cache.delete(org_id)
        org_cache.invalidate_pattern(f"{org_id}:*")

    @staticmethod
    def invalidate_batch(
        screening_ids: List[str] = None,
        subject_ids: List[str] = None
    ) -> None:
        """Batch invalidation."""
        if screening_ids:
            for screening_id in screening_ids:
                CacheInvalidator.invalidate_screening(screening_id)

        if subject_ids:
            for subject_id in subject_ids:
                CacheInvalidator.invalidate_subject(subject_id)
```

## Implementation Checklist

### Core Infrastructure
- [ ] Configure Redis connection pool
- [ ] Create RedisClient wrapper
- [ ] Implement CacheService class
- [ ] Add serialization/deserialization
- [ ] Create cache decorator

### Cache Strategies
- [ ] Implement screening cache
- [ ] Implement subject cache
- [ ] Implement organization cache
- [ ] Add compliance rules cache
- [ ] Create session cache

### Advanced Features
- [ ] Implement distributed locking
- [ ] Add cache invalidation patterns
- [ ] Create batch operations
- [ ] Add cache warming strategies
- [ ] Implement cache statistics

### Testing
- [ ] Test cache hit/miss scenarios
- [ ] Test TTL expiration
- [ ] Test distributed lock contention
- [ ] Test invalidation patterns
- [ ] Add performance benchmarks

## Testing Strategy

```python
# tests/cache/test_cache_service.py
import pytest
import time
from elile.cache.cache_service import CacheService
from elile.cache.lock import distributed_lock

def test_cache_get_set():
    """Test basic cache operations."""
    cache = CacheService("test:", 60)

    cache.set("key1", {"data": "value"})
    result = cache.get("key1")

    assert result == {"data": "value"}

def test_cache_ttl():
    """Test TTL expiration."""
    cache = CacheService("test:", 1)

    cache.set("key2", "value", ttl=1)
    assert cache.get("key2") == "value"

    time.sleep(2)
    assert cache.get("key2") is None

def test_distributed_lock():
    """Test distributed locking."""
    with distributed_lock("test_resource", timeout=5):
        # Lock acquired
        with pytest.raises(TimeoutError):
            with distributed_lock("test_resource", timeout=1):
                pass  # Should timeout

def test_cache_decorator():
    """Test cache decorator."""
    cache = CacheService("test:", 60)
    call_count = 0

    @cache.cached(ttl=60)
    def expensive_function(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 2

    # First call executes function
    result1 = expensive_function(5)
    assert result1 == 10
    assert call_count == 1

    # Second call uses cache
    result2 = expensive_function(5)
    assert result2 == 10
    assert call_count == 1
```

## Success Criteria

- [ ] Redis connection pool configured correctly
- [ ] Cache hit rate >70% for frequently accessed data
- [ ] Cache operations complete in <5ms
- [ ] Distributed locks prevent race conditions
- [ ] Cache invalidation works correctly
- [ ] Cache tests achieve >90% coverage

## Documentation

- Document cache key naming conventions
- Create cache invalidation guide
- Add distributed locking examples
- Document TTL strategies by data type

## Future Enhancements

- Add cache analytics and monitoring
- Implement cache compression
- Support multiple Redis clusters
- Add automatic cache warming
- Implement cache circuit breaker
