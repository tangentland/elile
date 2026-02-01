# Task 10.2: Authentication Middleware

## Overview

Implement authentication middleware supporting API keys and OAuth 2.0 for machine-to-machine access with tenant isolation and role-based access control.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 1.4: Multi-Tenancy
- Task 10.1: API Gateway

## Implementation

```python
# src/elile/api/auth.py
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, OAuth2PasswordBearer

security = HTTPBearer()

async def authenticate_request(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> RequestContext:
    """Authenticate API request."""

    token = credentials.credentials

    # Validate API key or JWT
    if token.startswith("sk_"):
        return await authenticate_api_key(token)
    else:
        return await authenticate_jwt(token)

async def authenticate_api_key(api_key: str) -> RequestContext:
    """Authenticate via API key."""
    # Lookup key in database
    key_record = await db.get_api_key(api_key)
    if not key_record or not key_record.is_active:
        raise HTTPException(401, "Invalid API key")

    return RequestContext(
        tenant_id=key_record.tenant_id,
        user_id=key_record.created_by,
        roles=key_record.roles
    )
```

## Acceptance Criteria

- [ ] API key authentication
- [ ] JWT/OAuth2 support
- [ ] Tenant isolation enforced
- [ ] Role-based access control
- [ ] Token validation and expiry

## Deliverables

- `src/elile/api/auth.py`
- `tests/unit/test_authentication.py`

## References

- Architecture: [09-integration.md](../../docs/architecture/09-integration.md) - Authentication

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
