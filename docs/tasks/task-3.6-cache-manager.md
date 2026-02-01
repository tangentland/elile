# Task 3.6: Cache Manager (Core)

## Overview

Implement provider response caching system using CachedDataSource model. Stores provider responses with timestamps for freshness evaluation (Task 3.7). Reduces costs and API calls.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema (CachedDataSource model)
- Task 1.10: Redis (optional distributed cache)

## Implementation Checklist

- [ ] Create CacheManager service
- [ ] Implement cache storage (database + Redis)
- [ ] Build cache retrieval by entity + check_type
- [ ] Add cache invalidation logic
- [ ] Create cache statistics tracking
- [ ] Write cache manager tests

## Key Implementation

```python
# src/elile/services/cache_manager.py
from datetime import datetime, timedelta

class CacheManager:
    """Manages cached provider responses."""

    def __init__(self, db: AsyncSession, redis: Redis | None = None):
        self.db = db
        self.redis = redis

    async def get_cached_response(
        self,
        entity_id: UUID,
        check_type: str,
        provider_id: str
    ) -> CachedDataSource | None:
        """Retrieve cached response if exists."""
        from sqlalchemy import select

        # Try Redis first (fast)
        if self.redis:
            cache_key = f"cache:{entity_id}:{check_type}:{provider_id}"
            cached = await self.redis.get(cache_key)
            if cached:
                return CachedDataSource.parse_raw(cached)

        # Fall back to database
        query = select(CachedDataSource).where(
            CachedDataSource.entity_id == entity_id,
            CachedDataSource.check_type == check_type,
            CachedDataSource.provider_id == provider_id
        ).order_by(CachedDataSource.cached_at.desc()).limit(1)

        result = await self.db.execute(query)
        cached = result.scalars().first()

        # Populate Redis for next time
        if cached and self.redis:
            cache_key = f"cache:{entity_id}:{check_type}:{provider_id}"
            await self.redis.setex(
                cache_key,
                timedelta(days=1),
                cached.json()
            )

        return cached

    async def store_cached_response(
        self,
        entity_id: UUID,
        check_type: str,
        provider_id: str,
        response_data: dict,
        ctx: RequestContext
    ) -> CachedDataSource:
        """Store provider response in cache."""
        cached = CachedDataSource(
            entity_id=entity_id,
            check_type=check_type,
            provider_id=provider_id,
            cached_at=datetime.utcnow(),
            response_data=response_data,
            tenant_id=ctx.tenant_id
        )

        self.db.add(cached)
        await self.db.flush()

        # Store in Redis
        if self.redis:
            cache_key = f"cache:{entity_id}:{check_type}:{provider_id}"
            await self.redis.setex(
                cache_key,
                timedelta(days=1),
                cached.json()
            )

        return cached

    async def invalidate_cache(
        self,
        entity_id: UUID,
        check_type: str | None = None,
        provider_id: str | None = None
    ):
        """Invalidate cached responses."""
        from sqlalchemy import delete

        # Build delete query
        query = delete(CachedDataSource).where(
            CachedDataSource.entity_id == entity_id
        )
        if check_type:
            query = query.where(CachedDataSource.check_type == check_type)
        if provider_id:
            query = query.where(CachedDataSource.provider_id == provider_id)

        await self.db.execute(query)

        # Clear Redis
        if self.redis:
            pattern = f"cache:{entity_id}:*"
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)

    async def get_cache_stats(self, entity_id: UUID) -> dict:
        """Get cache statistics for entity."""
        from sqlalchemy import select, func

        query = select(
            CachedDataSource.check_type,
            func.count(CachedDataSource.cache_id).label("count"),
            func.max(CachedDataSource.cached_at).label("latest")
        ).where(
            CachedDataSource.entity_id == entity_id
        ).group_by(CachedDataSource.check_type)

        result = await self.db.execute(query)
        rows = result.all()

        return {
            row.check_type: {
                "count": row.count,
                "latest": row.latest.isoformat() if row.latest else None
            }
            for row in rows
        }
```

## Testing Requirements

### Unit Tests
- Cache storage and retrieval
- Cache invalidation
- Redis integration (if available)
- Multi-tenant isolation

### Integration Tests
- Cache hit/miss scenarios
- Cache expiration
- Concurrent cache access

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] Cache stores provider responses
- [ ] get_cached_response() retrieves by entity + check_type
- [ ] Redis integration works (optional)
- [ ] Cache invalidation clears entries
- [ ] Multi-tenant isolation enforced
- [ ] Cache statistics available

## Deliverables

- `src/elile/services/cache_manager.py`
- `tests/unit/test_cache_manager.py`
- `tests/integration/test_cache_redis.py`

## References

- Architecture: [02-core-system.md](../architecture/02-core-system.md) - Caching
- Dependencies: Task 1.1 (CachedDataSource), Task 1.10 (Redis)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
