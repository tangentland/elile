# Task 1.4: Multi-Tenancy Infrastructure

## Status: IMPLEMENTED

**Branch:** `feature/task-1.3-request-context`
**Date:** 2026-01-30

## Overview

Implement tenant isolation at the application layer using the existing `Tenant` model and `RequestContext` framework.

**Key Architecture Decision:** Entity/EntityRelation/EntityProfile do NOT have tenant_id because entities are shared across tenants (same person investigated by multiple orgs resolves to same canonical entity). Isolation is enforced at:
- Application layer via `RequestContext.tenant_id`
- Cache layer via `CachedDataSource.customer_id` for customer-provided data
- Audit layer via `AuditEvent.tenant_id`

## Components Implemented

### 1. TenantService (`src/elile/core/tenant.py`)

CRUD operations for tenant management:
- `create_tenant(name, slug, correlation_id)` - Create new tenant
- `get_tenant(tenant_id)` - Get by ID (returns None if not found)
- `get_tenant_or_raise(tenant_id)` - Get or raise TenantNotFoundError
- `get_tenant_by_slug(slug)` - Get by unique slug
- `list_tenants(active_only, limit, offset)` - Paginated listing
- `update_tenant(tenant_id, name, slug, correlation_id)` - Update properties
- `deactivate_tenant(tenant_id, correlation_id)` - Soft delete
- `validate_tenant_active(tenant_id)` - Validate exists and active

All operations audit-logged via AuditLogger.

### 2. Custom Exceptions (`src/elile/core/exceptions.py`)

Added:
- `TenantNotFoundError(tenant_id)` - Tenant doesn't exist
- `TenantInactiveError(tenant_id)` - Tenant is deactivated
- `TenantAccessDeniedError(tenant_id, resource)` - Access denied

### 3. Pydantic Schemas (`src/elile/db/schemas/tenant.py`)

- `TenantCreate` - name, slug (validated: lowercase alphanumeric with hyphens)
- `TenantUpdate` - optional name, slug
- `TenantResponse` - full tenant with timestamps, `from_attributes=True`

### 4. Tenant Query Helpers (`src/elile/db/queries/tenant.py`)

```python
def filter_cache_by_tenant(query, tenant_id, cache_scope) -> Select:
    """Add tenant filtering to CachedDataSource query.

    SHARED scope: paid_external (all) + customer_provided (this tenant)
    TENANT_ISOLATED scope: customer_provided (this tenant) only
    """

def filter_cache_by_context(query) -> Select:
    """Use current RequestContext for filtering."""

async def get_tenant_cache_entry(db, entity_id, check_type, tenant_id, cache_scope):
    """Get cache entry respecting tenant isolation."""
```

### 5. FastAPI Dependencies (`src/elile/db/dependencies.py`)

- `get_tenant_id_from_header()` - Extract from X-Tenant-ID header
- `get_required_tenant_id_from_header()` - Required X-Tenant-ID header
- `get_validated_tenant_id()` - Validate tenant exists and is active
- `get_tenant_db()` - Return `TenantDatabaseSession(session, tenant_id)`

### 6. Model Exports (`src/elile/db/models/__init__.py`)

Added `Tenant` to exports.

### 7. Alembic Migration (`migrations/versions/003_add_tenant_infrastructure.py`)

- Create `tenants` table with indexes
- Add FK: `cached_data_sources.customer_id` -> `tenants.tenant_id` (CASCADE)
- Add FK: `audit_events.tenant_id` -> `tenants.tenant_id` (SET NULL)

### 8. Audit Event Types (`src/elile/db/models/audit.py`)

Added to `AuditEventType` enum:
- `TENANT_CREATED = "tenant.created"`
- `TENANT_UPDATED = "tenant.updated"`
- `TENANT_DEACTIVATED = "tenant.deactivated"`

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/core/tenant.py` | TenantService |
| `src/elile/db/schemas/tenant.py` | Pydantic schemas |
| `src/elile/db/dependencies.py` | FastAPI dependencies |
| `src/elile/db/queries/__init__.py` | Package init |
| `src/elile/db/queries/tenant.py` | Query helpers |
| `migrations/versions/003_add_tenant_infrastructure.py` | Migration |
| `tests/unit/test_tenant_service.py` | Unit tests |
| `tests/integration/test_tenant_isolation.py` | Integration tests |

## Files Modified

| File | Changes |
|------|---------|
| `src/elile/core/exceptions.py` | Added 3 tenant exceptions |
| `src/elile/core/__init__.py` | Export TenantService, exceptions |
| `src/elile/db/models/__init__.py` | Export Tenant |
| `src/elile/db/models/audit.py` | Added tenant event types |
| `src/elile/db/schemas/__init__.py` | Export tenant schemas |

## Implementation Notes

### UUIDv7 Standard

All identifiers use Python 3.14 native `uuid.uuid7()` for time-ordered UUIDs:
- Natural chronological sorting without additional timestamp-based ordering
- More efficient indexing in databases
- **DO NOT use uuid4** - it is not time-ordered

### Tenant Isolation Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    TENANT ISOLATION LAYERS                       │
│                                                                  │
│  Layer 1: AUTHENTICATION                                        │
│    - API keys scoped to customer org                           │
│    - JWT tokens carry tenant_id claim                          │
│                                                                  │
│  Layer 2: DATA ISOLATION (cache)                               │
│    - Shared cache: Paid external provider data                 │
│    - Isolated cache: Customer-provided HRIS data               │
│    - Query patterns enforce tenant_id filters                  │
│                                                                  │
│  Layer 3: CONFIGURATION                                         │
│    - Per-tenant compliance overrides                           │
│    - Custom freshness policies                                 │
│    - Locale-specific data retention rules                      │
│                                                                  │
│  Layer 4: AUDIT TRAIL                                          │
│    - All logs tagged with tenant_id                            │
│    - Cross-tenant queries blocked at ORM level                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Cache Scope Logic

| Cache Scope | Data Visible |
|-------------|--------------|
| `SHARED` | All `paid_external` + this tenant's `customer_provided` |
| `TENANT_ISOLATED` | Only this tenant's `customer_provided` |

### Slug Validation

Tenant slugs are validated to be:
- Lowercase alphanumeric with hyphens
- Cannot start or end with hyphen
- Cannot contain consecutive hyphens
- 1-100 characters

## Verification Checklist

- [x] Tenant CRUD operations work
- [x] Cache isolation: tenant A cannot see tenant B's customer_provided data
- [x] Shared data: both tenants can see paid_external data
- [x] Audit logging for tenant operations
- [x] Migration applies cleanly
- [x] Unit tests pass
- [x] Integration tests pass

## Dependencies

- Task 1.2: Audit Logging System (completed)
- Task 1.3: Request Context Framework (completed)

## Next Steps

- Task 1.5: Compliance Engine (depends on this task)
