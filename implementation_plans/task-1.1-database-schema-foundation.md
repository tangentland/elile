# Task 1.1: Database Schema Foundation

## Overview
Establish the core database schema and infrastructure for the Elile platform using SQLAlchemy 2.0 async with PostgreSQL.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-29
**Tag**: `phase1/task-1.1-database-schema`

## Deliverables

### SQLAlchemy Models

1. **Entity** (`src/elile/db/models/entity.py`)
   - Core entity representation (person, organization, address)
   - UUIDv7 primary keys for time-ordering
   - Encrypted `canonical_identifiers` JSON field
   - EntityType enum (INDIVIDUAL, ORGANIZATION, ADDRESS)

2. **EntityProfile** (`src/elile/db/models/profile.py`)
   - Point-in-time snapshot of entity state
   - Version tracking for delta analysis
   - ProfileTrigger enum (SCREENING, MONITORING, MANUAL)
   - Links to parent entity

3. **EntityRelation** (`src/elile/db/models/entity.py`)
   - Relationships between entities
   - Confidence scoring (0.0-1.0)
   - Relation type tracking

4. **CachedDataSource** (`src/elile/db/models/cache.py`)
   - Provider response caching
   - FreshnessStatus enum (FRESH, STALE, EXPIRED)
   - DataOrigin enum (PAID_EXTERNAL, CUSTOMER_PROVIDED)
   - TTL management

5. **Tenant** (`src/elile/db/models/tenant.py`)
   - Multi-tenant customer organizations
   - Slug-based identification
   - Active/inactive status

### Database Configuration

- Async SQLAlchemy 2.0 engine
- Connection pooling
- PortableUUID type for cross-database compatibility
- Alembic migrations infrastructure

### Pydantic Schemas

- Entity schemas for API validation
- Profile schemas with version tracking
- Tenant schemas (create, update, response)

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/db/__init__.py` | Package initialization |
| `src/elile/db/config.py` | Database configuration |
| `src/elile/db/models/__init__.py` | Model exports |
| `src/elile/db/models/base.py` | Base model, PortableUUID |
| `src/elile/db/models/entity.py` | Entity, EntityRelation |
| `src/elile/db/models/profile.py` | EntityProfile |
| `src/elile/db/models/cache.py` | CachedDataSource |
| `src/elile/db/models/tenant.py` | Tenant |
| `src/elile/db/schemas/` | Pydantic schemas |
| `migrations/` | Alembic migrations |

## Design Decisions

1. **UUIDv7**: Time-ordered UUIDs for natural chronological sorting
2. **Async throughout**: SQLAlchemy 2.0 async for non-blocking I/O
3. **Encrypted fields**: Sensitive data encrypted at rest
4. **Soft deletes**: Entities not physically deleted for audit trail
