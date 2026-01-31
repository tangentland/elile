# Task 3.5: Multi-Tenant Entity Isolation

## Overview
Ensure proper tenant isolation for entity data, preventing cross-tenant data leakage while allowing shared cache for paid external sources.

**Priority**: P0
**Status**: Planned
**Dependencies**: Task 1.4 (Multi-Tenancy), Task 3.1

## Requirements

### Isolation Rules

1. **Customer-Provided Data**: Strictly tenant-scoped
   - HRIS records
   - Customer-uploaded documents
   - Internal notes

2. **Paid External Data**: Shared across tenants
   - Sanctions lists
   - Credit bureau data
   - Public records

3. **Entity Resolution**: Tenant-aware
   - Exact match only within tenant scope for customer data
   - Shared scope for external data deduplication

### Data Origin Tracking

Use DataOrigin enum from cache model:
- `PAID_EXTERNAL`: Shared scope
- `CUSTOMER_PROVIDED`: Tenant-isolated scope

## Deliverables

### TenantAwareEntityService

Wraps EntityManager with tenant enforcement:
- `create_entity(entity_type, identifiers)`: Auto-add tenant_id
- `get_entity(entity_id)`: Verify tenant access
- `search_entities(query)`: Filter by tenant
- `share_external_entity(entity_id)`: Mark as shared

### EntityAccessControl

Access verification:
- `can_access(entity_id, tenant_id)`: Check access rights
- `get_accessible_entities(tenant_id)`: List accessible
- `verify_isolation(entity_id)`: Audit isolation

### TenantScopedQuery

Query builder with automatic tenant filtering:
- `with_tenant(tenant_id)`: Set tenant scope
- `with_shared()`: Include shared entities
- `exclude_other_tenants()`: Strict isolation

## Files to Create

| File | Purpose |
|------|---------|
| `src/elile/entity/tenant.py` | TenantAwareEntityService |
| `src/elile/entity/access.py` | EntityAccessControl |
| `tests/unit/test_tenant_isolation.py` | Unit tests |
| `tests/integration/test_entity_isolation.py` | Integration tests |

## Isolation Implementation

### Query Filter
```python
def build_tenant_query(
    base_query: Select,
    tenant_id: UUID,
    include_shared: bool = True,
) -> Select:
    """Add tenant isolation to query."""
    if include_shared:
        # Include tenant's own + shared external data
        return base_query.where(
            or_(
                Entity.tenant_id == tenant_id,
                Entity.data_origin == DataOrigin.PAID_EXTERNAL,
            )
        )
    else:
        # Strict tenant isolation
        return base_query.where(Entity.tenant_id == tenant_id)
```

### Access Verification
```python
async def verify_access(
    self,
    entity_id: UUID,
    tenant_id: UUID,
) -> bool:
    """Verify tenant can access entity."""
    entity = await self._repo.get(entity_id)
    if entity is None:
        return False

    # Own tenant's data
    if entity.tenant_id == tenant_id:
        return True

    # Shared external data
    if entity.data_origin == DataOrigin.PAID_EXTERNAL:
        return True

    return False
```

## Schema Changes

Add to Entity model:
```python
class Entity(Base):
    # ... existing fields ...
    tenant_id: Mapped[UUID | None] = mapped_column(
        PortableUUID(),
        ForeignKey("tenants.tenant_id"),
        nullable=True,  # None for shared external
        index=True,
    )
    data_origin: Mapped[DataOrigin] = mapped_column(
        default=DataOrigin.CUSTOMER_PROVIDED,
    )
```

## Integration Points

- RequestContext for current tenant
- EntityManager for entity operations
- CacheRepository for cached data isolation
- AuditLogger for access logging

## Test Cases

1. Tenant A cannot access Tenant B's entities
2. Tenant A can access shared external entities
3. Customer data always has tenant_id
4. External data has tenant_id = None
5. Entity search respects tenant scope
6. Cross-tenant access attempt logged
