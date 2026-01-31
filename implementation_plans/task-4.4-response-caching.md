# Task 4.4: Response Caching Service

## Overview
Implement provider response caching to minimize API calls, reduce costs, and improve latency. Uses the existing CachedDataSource model with cache-aside pattern.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-31
**Tag**: `phase4/task-4.4`
**Dependencies**: Task 4.1 (Provider Interface)

## Requirements

### Cache-Aside Pattern
1. **Check cache first**: Before calling provider, check for cached response
2. **Store on miss**: After successful provider call, store in cache
3. **Freshness management**: Track fresh/stale/expired status
4. **Tenant isolation**: Customer-provided data scoped to tenant

### Freshness Configuration
1. **Per-check-type configs**: Different freshness periods by check category
2. **Criminal checks**: 7 days fresh, 14 days stale
3. **Credit checks**: 30 days fresh, 30 days stale (FCRA)
4. **Employment/Education**: 30-90 days fresh

### Data Sharing Model
1. **PAID_EXTERNAL**: Shared across all tenants (purchased data)
2. **CUSTOMER_PROVIDED**: Scoped to originating tenant only

### Statistics Tracking
1. **Hit rates**: Fresh hits, stale hits, misses
2. **Store count**: Number of cache stores
3. **Invalidations**: Manual invalidations

## Existing Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| `CachedDataSource` | `db/models/cache.py` | SQLAlchemy model for cached responses |
| `DataOrigin` | `db/models/cache.py` | PAID_EXTERNAL vs CUSTOMER_PROVIDED |
| `FreshnessStatus` | `db/models/cache.py` | FRESH, STALE, EXPIRED |
| `CacheRepository` | `db/repositories/cache.py` | Database operations for cache |
| `Encryptor` | `core/encryption.py` | Encrypt raw response data |

## Deliverables

### Cache Service (`src/elile/providers/cache.py`)
- CacheFreshnessConfig model
- CacheEntry dataclass
- CacheLookupResult dataclass
- CacheStats dataclass
- ProviderCacheService class
- DEFAULT_FRESHNESS_CONFIGS dictionary

### Methods
```python
class ProviderCacheService:
    async def get(entity_id, provider_id, check_type, tenant_id) -> CacheLookupResult
    async def store(entity_id, result, tenant_id, data_origin) -> CacheEntry
    async def invalidate(entity_id, provider_id, check_type) -> int
    async def get_or_fetch(entity_id, provider_id, check_type, fetch_fn) -> (ProviderResult, bool)
    async def update_freshness() -> (stale_count, expired_count)
    async def cleanup_expired(older_than) -> int
```

## Files to Create/Modify

| File | Purpose |
|------|---------|
| `src/elile/providers/cache.py` | Cache service (new) |
| `src/elile/providers/__init__.py` | Updated exports |
| `tests/unit/test_provider_cache.py` | Unit tests |

## Default Freshness Configs

| Category | Fresh Duration | Stale Duration | Rationale |
|----------|---------------|----------------|-----------|
| Criminal | 7 days | 14 days | Legal importance, frequent updates |
| Credit | 30 days | 30 days | FCRA monthly reporting |
| Employment | 30 days | 60 days | Moderately stable |
| Education | 90 days | 180 days | Very stable |
| Identity | 30 days | 60 days | Moderately stable |
| Default | 7 days | 30 days | Conservative fallback |

## Key Patterns

### Cache-Aside with get_or_fetch
```python
cache = ProviderCacheService(session)

# Automatic cache-aside
result, was_cached = await cache.get_or_fetch(
    entity_id=entity_id,
    provider_id="sterling",
    check_type=CheckType.CRIMINAL_NATIONAL,
    fetch_fn=lambda: provider.execute_check(...),
)

if was_cached:
    logger.info("Cache hit - saved API call")
```

### Manual Cache Check
```python
# Check cache first
lookup = await cache.get(entity_id, provider_id, check_type)

if lookup.hit:
    if lookup.is_fresh_hit:
        return lookup.entry.normalized_data
    elif lookup.is_stale_hit:
        logger.warning("Using stale data", age_days=lookup.entry.age.days)
        return lookup.entry.normalized_data

# Cache miss - fetch from provider
```

### Tenant Isolation
```python
# Customer-provided data is tenant-scoped
await cache.store(
    entity_id=entity_id,
    result=result,
    tenant_id=tenant_id,
    data_origin=DataOrigin.CUSTOMER_PROVIDED,  # Only this tenant can see it
)

# Paid external data is shared
await cache.store(
    entity_id=entity_id,
    result=result,
    data_origin=DataOrigin.PAID_EXTERNAL,  # All tenants can use it
)
```

## Verification

1. Run unit tests: `.venv/bin/pytest tests/unit/test_provider_cache.py -v`
2. Run full test suite: `.venv/bin/pytest -v`
3. Verify cache hit/miss statistics tracking
4. Verify tenant isolation for customer-provided data
5. Verify shared access for paid external data

## Notes

- Uses existing CacheRepository for database operations
- Raw response encrypted using core Encryptor
- Freshness computed on read (not stored status, but fresh_until/stale_until)
- CacheEntry created on-demand from CachedDataSource model
