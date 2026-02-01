# Task 1.3: Request Context Framework

## Overview

Build immutable request context propagation system that carries tenant_id, user_id, correlation_id, locale, and audit metadata through all layers of the application. Essential for multi-tenant isolation and audit trail completeness.

**Priority**: P0 | **Effort**: 1-2 days | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema (tenant model)
- Task 1.2: Audit Logging (context used in audit events)

## Implementation Checklist

- [ ] Create frozen `RequestContext` dataclass with required fields
- [ ] Implement context factory from FastAPI request
- [ ] Add context to SQLAlchemy session (tenant isolation)
- [ ] Create async context propagation using `contextvars`
- [ ] Build context injection middleware for FastAPI
- [ ] Write unit tests for immutability and propagation
- [ ] Integration tests with audit logging

## Key Models/Interfaces

```python
# src/elile/core/context.py
from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime

@dataclass(frozen=True)
class RequestContext:
    """Immutable request context for tenant isolation and audit."""
    correlation_id: UUID = field(default_factory=uuid4)
    tenant_id: UUID
    user_id: UUID | None = None
    locale: str = "US"

    # Audit metadata
    ip_address: str | None = None
    user_agent: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Database session (not serialized)
    db: Any = field(default=None, repr=False)

# src/elile/api/dependencies.py
from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

async def get_request_context(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> RequestContext:
    """Extract request context from FastAPI request."""
    tenant_id = request.headers.get("X-Tenant-ID")
    user_id = request.state.user_id  # From auth middleware

    return RequestContext(
        tenant_id=UUID(tenant_id),
        user_id=UUID(user_id) if user_id else None,
        locale=request.headers.get("X-Locale", "US"),
        ip_address=request.client.host,
        user_agent=request.headers.get("User-Agent"),
        db=db
    )
```

## Testing Requirements

### Unit Tests
- Context immutability (frozen dataclass)
- Context factory from HTTP headers
- Missing tenant_id raises error
- Default locale and correlation_id generation

### Integration Tests
- Context propagates through async calls
- Audit events capture context correctly
- Multi-tenant queries filter by context.tenant_id

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] RequestContext is immutable (frozen)
- [ ] Context includes correlation_id, tenant_id, user_id, locale
- [ ] Context propagates through async function calls
- [ ] FastAPI dependency injects context from request headers
- [ ] Missing X-Tenant-ID header returns 400 error
- [ ] All audit log entries reference request context
- [ ] Integration with Task 1.4 (multi-tenancy) verified

## Deliverables

- `src/elile/core/context.py`
- `src/elile/api/dependencies.py`
- `src/elile/api/middleware.py` (context injection)
- `tests/unit/test_context.py`
- `tests/integration/test_context_propagation.py`

## References

- Architecture: [02-core-system.md](../architecture/02-core-system.md) - Request context design
- Dependencies: Task 1.2 (audit), Task 1.4 (multi-tenancy)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
