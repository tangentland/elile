# Task 1.9: Database Repository Pattern

## Overview
Implement the repository pattern for clean data access abstraction, providing type-safe CRUD operations for all database models.

**Priority**: P1
**Status**: Complete
**Completed**: 2026-01-31
**Tag**: `phase1/task-1.9`
**Dependencies**: Task 1.1

## Deliverables

### BaseRepository

Generic base class with:
- `get(id)`: Retrieve by primary key
- `create(data)`: Create new record
- `update(id, data)`: Update existing record
- `delete(id)`: Delete record
- `list(skip, limit)`: Paginated listing
- `count()`: Total record count
- `exists(id)`: Check existence

### EntityRepository

Entity-specific operations:
- `get_by_type(entity_type)`: Filter by EntityType
- `get_individuals()`: Get all INDIVIDUAL entities
- `get_organizations()`: Get all ORGANIZATION entities
- `count_by_type(entity_type)`: Count by type

### ProfileRepository

Profile versioning operations:
- `get_by_entity(entity_id)`: Get all profiles for entity
- `get_latest(entity_id)`: Get most recent profile
- `get_by_version(entity_id, version)`: Get specific version
- `get_by_trigger(trigger)`: Filter by ProfileTrigger
- `get_next_version(entity_id)`: Calculate next version number

### CacheRepository

Cache freshness management:
- `get_for_entity(entity_id)`: Get cached data for entity
- `get_by_check_type(check_type)`: Filter by check type
- `get_fresh_entry(entity_id, check_type)`: Get fresh cache entry
- `mark_stale(cache_id)`: Mark entry as stale
- `mark_expired(cache_id)`: Mark entry as expired
- `count_by_freshness(status)`: Count by FreshnessStatus

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/db/repositories/__init__.py` | Package exports |
| `src/elile/db/repositories/base.py` | BaseRepository |
| `src/elile/db/repositories/entity.py` | EntityRepository |
| `src/elile/db/repositories/profile.py` | ProfileRepository |
| `src/elile/db/repositories/cache.py` | CacheRepository |
| `tests/unit/test_repositories.py` | 23 unit tests |

## Usage Example

```python
from elile.db.repositories import EntityRepository

async with db_session() as session:
    repo = EntityRepository(session)
    entities = await repo.get_by_type(EntityType.INDIVIDUAL)
    entity = await repo.get(entity_id)
```

## Design Decisions

1. **Generic base**: Type parameters for model and schema
2. **Async throughout**: All operations are async
3. **Session injection**: Repository receives session, doesn't manage it
4. **collections.abc.Sequence**: Python 3.14 compatible imports
