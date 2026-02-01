# Task 1.7: Error Handling Framework

## Overview

Build structured exception hierarchy and error handling framework that automatically logs errors to audit system, returns consistent API error responses, and supports error categorization (validation, permission, provider, system).

**Priority**: P0 | **Effort**: 1-2 days | **Status**: Not Started

## Dependencies

- Task 1.2: Audit Logging (errors logged as audit events)

## Implementation Checklist

- [ ] Create exception hierarchy with base ElileException
- [ ] Add error codes and categories
- [ ] Implement FastAPI exception handlers
- [ ] Auto-log exceptions to audit system
- [ ] Build error response formatter
- [ ] Add context preservation in exceptions
- [ ] Write exception handling tests

## Key Implementation

```python
# src/elile/core/errors.py
from enum import Enum

class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    PERMISSION = "permission"
    PROVIDER = "provider"
    COMPLIANCE = "compliance"
    SYSTEM = "system"

class ElileException(Exception):
    """Base exception for all Elile errors."""
    def __init__(
        self,
        message: str,
        error_code: str,
        category: ErrorCategory,
        status_code: int = 500,
        details: dict | None = None,
        ctx: RequestContext | None = None
    ):
        self.message = message
        self.error_code = error_code
        self.category = category
        self.status_code = status_code
        self.details = details or {}
        self.ctx = ctx
        super().__init__(message)

class ValidationError(ElileException):
    """Input validation failed."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            category=ErrorCategory.VALIDATION,
            status_code=400,
            details=details
        )

class PermissionDeniedError(ElileException):
    """User lacks required permission."""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            category=ErrorCategory.PERMISSION,
            status_code=403
        )

class ProviderError(ElileException):
    """Data provider failure."""
    def __init__(self, provider_id: str, message: str):
        super().__init__(
            message=f"Provider {provider_id} error: {message}",
            error_code="PROVIDER_ERROR",
            category=ErrorCategory.PROVIDER,
            status_code=502,
            details={"provider_id": provider_id}
        )

class ComplianceViolationError(ElileException):
    """Operation violates compliance rules."""
    def __init__(self, rule_id: str, message: str):
        super().__init__(
            message=message,
            error_code="COMPLIANCE_VIOLATION",
            category=ErrorCategory.COMPLIANCE,
            status_code=403,
            details={"rule_id": rule_id}
        )

# src/elile/api/exception_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse

async def elile_exception_handler(request: Request, exc: ElileException):
    """Handle ElileException and log to audit."""
    if exc.ctx:
        audit_logger = AuditLogger(exc.ctx.db)
        await audit_logger.log_event(
            event_type=AuditEventType.ERROR_OCCURRED,
            ctx=exc.ctx,
            event_data={
                "error_code": exc.error_code,
                "category": exc.category,
                "message": exc.message,
                "details": exc.details
            },
            severity=AuditSeverity.ERROR
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "category": exc.category,
            "message": exc.message,
            "details": exc.details
        }
    )

# In app.py
app.add_exception_handler(ElileException, elile_exception_handler)
```

## Testing Requirements

### Unit Tests
- Exception hierarchy structure
- Error codes unique
- Status codes correct per exception type
- Context preserved in exceptions

### Integration Tests
- API returns structured error JSON
- Errors logged to audit_events table
- Correlation IDs in error responses
- Exception handlers for all custom exceptions

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] Exception hierarchy with 5+ specific exception types
- [ ] All exceptions include error_code and category
- [ ] FastAPI handlers return JSON with error structure
- [ ] Exceptions automatically logged to audit system
- [ ] RequestContext preserved in exceptions
- [ ] Error responses include correlation_id
- [ ] Tests verify error handling end-to-end

## Deliverables

- `src/elile/core/errors.py`
- `src/elile/api/exception_handlers.py`
- `tests/unit/test_errors.py`
- `tests/integration/test_error_handling.py`

## References

- Architecture: [02-core-system.md](../architecture/02-core-system.md) - Error handling
- Dependencies: Task 1.2 (audit logging)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
