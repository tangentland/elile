# Task 1.11: Structured Logging

## Overview
Implement structured JSON logging with correlation ID tracking and context propagation using structlog.

**Priority**: P1
**Status**: Complete
**Completed**: 2026-01-31
**Tag**: `phase1/task-1.11`
**Dependencies**: Task 1.2

## Deliverables

### setup_logging Function

Configure structlog with:
- JSON format for production, console for development
- Configurable log level
- Timestamp inclusion
- Request context propagation

### Structlog Processors

Custom processors:
- `add_request_context`: Inject correlation_id, tenant_id, actor_id
- `add_environment_info`: Add environment name
- `drop_color_message_key`: Remove uvicorn color codes

### get_logger Function

Get configured logger:
- Returns structlog BoundLogger
- Optional name parameter
- Consistent configuration

### LogContext Class

Context manager for temporary bindings:
- Bind values for duration of block
- Automatic cleanup on exit
- Supports arbitrary key-value pairs

### Context Variable Functions

- `bind_contextvars(**kwargs)`: Bind to context
- `unbind_contextvars(*keys)`: Unbind from context
- `clear_contextvars()`: Clear all context

### Helper Functions

Standardized log patterns:
- `log_request_start(logger, method, path)`: HTTP request start
- `log_request_end(logger, method, path, status, duration)`: Request complete
- `log_exception(logger, exc)`: Exception with context
- `log_database_query(logger, query_type, table, duration)`: DB operations
- `log_external_call(logger, service, operation, duration, success)`: External APIs

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/core/logging.py` | All logging utilities |
| `tests/unit/test_logging.py` | 21 unit tests |

## Usage Example

```python
from elile.core.logging import setup_logging, get_logger, LogContext

setup_logging(log_level="INFO", json_format=True)
logger = get_logger(__name__)

with LogContext(operation="process_order", order_id=123):
    logger.info("Processing started")
    # All logs include operation and order_id
```

## Log Output Format (JSON)

```json
{
  "timestamp": "2026-01-31T10:30:00Z",
  "level": "info",
  "logger": "elile.api.middleware",
  "event": "request_completed",
  "correlation_id": "01234567-89ab-cdef-0123-456789abcdef",
  "tenant_id": "...",
  "actor_id": "...",
  "environment": "production",
  "http_method": "GET",
  "http_path": "/api/v1/users",
  "http_status": 200,
  "duration_ms": 45.23
}
```

## Design Decisions

1. **structlog**: Industry standard for structured logging
2. **JSON in production**: Machine-parseable for log aggregation
3. **Console in dev**: Human-readable with colors
4. **Context propagation**: Automatic from RequestContext
