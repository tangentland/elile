# Task 12.3: Security Hardening

## Overview

Implement security hardening measures including input sanitization, SQL injection prevention, XSS protection, CSRF tokens, and security headers.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 10.1: API Gateway
- Task 10.2: Authentication Middleware

## Implementation

```python
# src/elile/security/hardening.py
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# HTTPS redirect
app.add_middleware(HTTPSRedirectMiddleware)

# Trusted hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["api.elile.com", "*.elile.com"]
)

# Input sanitization
def sanitize_input(value: str) -> str:
    """Sanitize user input."""
    import bleach
    return bleach.clean(value, tags=[], strip=True)

# SQL injection prevention (already handled by SQLAlchemy ORM)
# But enforce parameterized queries
async def safe_query(session, entity_id: UUID):
    # Good - parameterized
    return await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )

    # Bad - never do this
    # await session.execute(f"SELECT * FROM entities WHERE id = '{entity_id}'")
```

## Acceptance Criteria

- [ ] Security headers configured
- [ ] HTTPS enforced in production
- [ ] Input sanitization on all user inputs
- [ ] SQL injection prevention verified
- [ ] Rate limiting enforced
- [ ] CORS properly configured
- [ ] Security audit passing

## Deliverables

- `src/elile/security/hardening.py`
- Security audit report
- Penetration test results (if available)

## References

- Architecture: [07-compliance.md](../../docs/architecture/07-compliance.md) - Security

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
