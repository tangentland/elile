# Task 1.4: Multi-Tenancy Infrastructure

## Overview

Implement row-level security for multi-tenant data isolation using tenant_id filtering at ORM level. Prevent cross-tenant data leakage through automatic query filtering and tenant validation middleware.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema (tenant table)
- Task 1.3: Request Context (tenant_id propagation)

## Implementation Checklist

- [ ] Create Tenant model with configuration
- [ ] Add tenant_id to all tenant-scoped tables
- [ ] Implement SQLAlchemy query filter for tenant isolation
- [ ] Create tenant validation middleware
- [ ] Build tenant configuration loader
- [ ] Write tests for cross-tenant isolation
- [ ] Security audit for tenant leakage

## Key Models/Interfaces

```python
# src/elile/models/tenant.py
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin

class Tenant(Base, TimestampMixin):
    """Multi-tenant organization."""
    __tablename__ = "tenants"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), default="US")
    active: Mapped[bool] = mapped_column(default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)

# src/elile/core/multi_tenancy.py
from sqlalchemy import event
from sqlalchemy.orm import Session

def add_tenant_filter(session: Session, ctx: RequestContext):
    """Add tenant filter to all queries in session."""
    @event.listens_for(session, "do_orm_execute")
    def receive_do_orm_execute(orm_execute_state):
        if orm_execute_state.is_select:
            # Add tenant_id filter to SELECT queries
            orm_execute_state.statement = orm_execute_state.statement.filter_by(
                tenant_id=ctx.tenant_id
            )

# src/elile/api/middleware.py
from fastapi import Request, HTTPException

async def tenant_validation_middleware(request: Request, call_next):
    """Validate tenant exists and is active."""
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    # Verify tenant exists and is active
    tenant = await get_tenant(UUID(tenant_id))
    if not tenant or not tenant.active:
        raise HTTPException(status_code=403, detail="Invalid tenant")

    request.state.tenant = tenant
    return await call_next(request)
```

## Testing Requirements

### Unit Tests
- Tenant model CRUD operations
- Query filter adds tenant_id automatically
- Cross-tenant query returns empty result

### Integration Tests
- User from tenant A cannot access tenant B data
- Bulk operations respect tenant boundaries
- Audit logs include correct tenant_id

### Security Tests
- SQL injection attempts blocked
- Manually bypassing tenant_id filter fails
- Admin operations across tenants controlled

**Coverage Target**: 95%+ (security critical)

## Acceptance Criteria

- [ ] Tenant table created with config JSON field
- [ ] All tenant-scoped tables have tenant_id FK
- [ ] SQLAlchemy automatically filters queries by tenant_id
- [ ] Missing X-Tenant-ID header returns 400
- [ ] Invalid/inactive tenant returns 403
- [ ] Cross-tenant data access impossible in tests
- [ ] Tenant config accessible via context

## Deliverables

- `src/elile/models/tenant.py`
- `src/elile/core/multi_tenancy.py`
- `src/elile/api/middleware.py` (tenant validation)
- `migrations/versions/003_add_tenants.py`
- `tests/unit/test_multi_tenancy.py`
- `tests/security/test_tenant_isolation.py`

## References

- Architecture: [02-core-system.md](../architecture/02-core-system.md) - Multi-tenancy design
- Dependencies: Task 1.3 (context), Task 1.1 (database)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
