# Task 1.3: Request Context Framework

## Overview
Implement ContextVar-based request context propagation for tracking tenant, actor, and correlation IDs through async call chains.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-30
**Tag**: `phase1/task-1.3-request-context`
**Dependencies**: Task 1.1, Task 1.2

## Deliverables

### RequestContext Model

Pydantic model with:
- `tenant_id`: Customer organization identifier
- `actor_id`: User or service performing operation
- `correlation_id`: Request tracing ID (UUIDv7)
- `locale`: Geographic jurisdiction for compliance
- `actor_type`: HUMAN, SERVICE, or SYSTEM
- `cache_scope`: SHARED or TENANT_ISOLATED
- `permitted_checks`: List of allowed check types

### ContextVar Integration

- `_request_context`: ContextVar for async propagation
- Automatic propagation through async call chains
- Thread-safe context isolation

### Context Managers and Functions

- `request_context()`: Context manager for setting context
- `create_context()`: Factory with UUIDv7 generation
- `get_current_context()`: Get context or raise
- `get_current_context_or_none()`: Get context or None
- `require_context()`: Decorator enforcing context

### Enums

- `ActorType`: HUMAN, SERVICE, SYSTEM
- `CacheScope`: SHARED, TENANT_ISOLATED

### Exceptions

- `ContextNotSetError`: Context not available
- `ComplianceError`: Compliance violation
- `BudgetExceededError`: Budget limit reached
- `ConsentExpiredError`: Consent no longer valid

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/core/context.py` | RequestContext, ContextVars |
| `src/elile/core/exceptions.py` | Exception classes |
| `tests/unit/test_request_context.py` | Unit tests |
| `tests/integration/test_context_propagation.py` | Integration tests |

## Usage Example

```python
from elile.core import create_context, request_context, get_current_context

ctx = create_context(tenant_id=tenant_id, actor_id=user_id, locale="US")
with request_context(ctx):
    current = get_current_context()
    # Context available throughout async call chain
```

## Design Decisions

1. **ContextVar**: Python's built-in async context propagation
2. **Pydantic model**: Validation and serialization
3. **UUIDv7 correlation_id**: Time-ordered for log analysis
4. **Immutable context**: Context frozen after creation
