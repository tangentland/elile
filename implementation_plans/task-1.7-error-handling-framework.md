# Task 1.7: Error Handling Framework

## Overview

Enhance the error handling system with utilities for automatic audit event generation, error collection, and structured error handling patterns.

**Priority**: P0 (Critical)
**Dependencies**: Task 1.2 (Audit Logging), Task 1.5 (FastAPI Framework)

## Note on Task 1.5 Integration

Core HTTP error handling is already implemented in Task 1.5's ErrorHandlingMiddleware, which:
- Maps domain exceptions to HTTP status codes
- Returns standardized APIError responses
- Includes request_id for tracing

This task adds additional utilities for application-level error handling with audit logging.

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/core/error_handling.py` | Error handling utilities with audit |
| `tests/unit/test_error_handling.py` | 22 unit tests |

## Component Design

### 1. ErrorRecord Class

Captures error details for logging and audit:

```python
class ErrorRecord:
    error_code: str      # Machine-readable code
    message: str         # Human-readable message
    exception: Exception | None
    details: dict
    severity: AuditSeverity
    timestamp: datetime
```

Automatically captures:
- Exception type and message
- Stack trace for debugging
- Timestamp in UTC

### 2. ErrorHandler Context Manager

Structured error collection with automatic audit logging:

```python
async with ErrorHandler(db, ctx, resource_type="screening") as handler:
    try:
        await risky_operation()
    except SomeError as e:
        handler.record_error("operation_failed", str(e), exception=e)

    for item in items:
        try:
            await process_item(item)
        except ItemError as e:
            handler.record_error("item_failed", str(e), details={"item_id": item.id})

# All errors logged to audit on exit
```

Features:
- Collects multiple errors during an operation
- Automatically logs unhandled exceptions
- Logs to Python logging (always)
- Logs to audit system (optional, requires db session)
- Derives error codes from ElileError subclasses

### 3. handle_errors Decorator

Automatic error handling for async functions:

```python
@handle_errors(audit=True, resource_type="screening")
async def perform_screening(db: AsyncSession, subject_id: UUID):
    # ... screening logic
    pass
```

Features:
- Wraps async functions with ErrorHandler
- Extracts db session from arguments
- Uses function name as default resource_type
- Optional exception suppression (reraise=False)

### 4. error_context Helper

Simple async context manager alternative:

```python
async with error_context(db, resource_type="user") as handler:
    await risky_operation()
```

## Error Code Derivation

For ElileError subclasses, error codes are derived from class names:
- `TenantNotFoundError` → `tenant_not_found_error`
- `ComplianceError` → `compliance_error`

Non-ElileError exceptions get `internal_error`.

## Audit Integration

When db session is provided, errors are logged as `API_ERROR` audit events:

```python
await audit_logger.log_event(
    event_type=AuditEventType.API_ERROR,
    event_data=error.to_dict(),
    severity=error.severity,
    tenant_id=ctx.tenant_id,
    user_id=ctx.actor_id,
    correlation_id=ctx.correlation_id,
    resource_type=self.resource_type,
    resource_id=self.resource_id,
)
```

## Test Summary

| Test Class | Tests | Description |
|------------|-------|-------------|
| TestErrorRecord | 5 | Error record creation and serialization |
| TestErrorHandler | 9 | Error collection and logging |
| TestHandleErrorsDecorator | 5 | Decorator behavior |
| TestErrorContext | 2 | Context manager helper |
| TestErrorCodeDerivation | 2 | Error code generation |
| **Total** | **22** | |

## Usage Examples

### Basic Error Handling

```python
from elile.core.error_handling import ErrorHandler

async def process_batch(db: AsyncSession, items: list):
    async with ErrorHandler(db, resource_type="batch") as handler:
        for item in items:
            try:
                await process_item(item)
            except ProcessingError as e:
                handler.record_error(
                    "item_failed",
                    f"Failed to process item {item.id}",
                    exception=e,
                    details={"item_id": str(item.id)},
                )

        if handler.has_errors():
            # Decide how to handle partial failures
            logger.warning(f"Batch completed with {len(handler.get_errors())} errors")
```

### Decorator Usage

```python
from elile.core.error_handling import handle_errors

@handle_errors(audit=True, resource_type="screening")
async def run_screening(db: AsyncSession, subject_id: UUID):
    # Any exception will be logged and re-raised
    result = await screening_service.execute(db, subject_id)
    return result
```

## Verification

```bash
# Run tests
.venv/bin/pytest tests/unit/test_error_handling.py -v

# Check full test suite
.venv/bin/pytest -v
```

## Notes

- Audit logging is non-blocking (errors in audit don't fail main operation)
- Python logging always happens (regardless of audit setting)
- Context is automatically retrieved from ContextVar if not provided
- Exception suppression (reraise=False) should be used sparingly
