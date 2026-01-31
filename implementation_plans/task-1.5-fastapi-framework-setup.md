# Task 1.5: FastAPI Framework Setup

## Overview

Establish the FastAPI framework foundation for the Elile employee risk assessment platform. This task creates the application factory pattern with middleware for authentication, tenant validation, request context management, and error handling.

**Dependencies**: Task 1.3 (RequestContext), Task 1.4 (Multi-Tenancy)

## Existing Infrastructure (No Changes Needed)

- `src/elile/db/dependencies.py` - Tenant validation dependencies
- `src/elile/core/context.py` - RequestContext with ContextVars
- `src/elile/core/audit.py` - AuditLogger service
- `src/elile/core/exceptions.py` - Exception hierarchy
- `src/elile/core/tenant.py` - TenantService
- `src/elile/config/settings.py` - Settings with API_SECRET_KEY

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/api/__init__.py` | Package init exporting create_app |
| `src/elile/api/app.py` | Application factory with lifespan management |
| `src/elile/api/dependencies.py` | API-level FastAPI dependencies |
| `src/elile/api/middleware/__init__.py` | Middleware package exports |
| `src/elile/api/middleware/context.py` | RequestContext middleware with UUIDv7 |
| `src/elile/api/middleware/auth.py` | Bearer token authentication |
| `src/elile/api/middleware/tenant.py` | X-Tenant-ID validation |
| `src/elile/api/middleware/errors.py` | Exception-to-HTTP mapping |
| `src/elile/api/middleware/logging.py` | Request audit logging |
| `src/elile/api/schemas/__init__.py` | Schema package exports |
| `src/elile/api/schemas/errors.py` | APIError and ErrorCode enum |
| `src/elile/api/schemas/health.py` | Health check response schemas |
| `src/elile/api/routers/__init__.py` | Router package exports |
| `src/elile/api/routers/health.py` | /health, /health/db, /health/ready endpoints |
| `tests/unit/test_api_middleware.py` | 31 middleware unit tests |
| `tests/unit/test_api_schemas.py` | 14 schema unit tests |
| `tests/integration/test_api_health.py` | 16 health endpoint tests |
| `tests/integration/test_api_middleware.py` | 17 middleware integration tests |

## Files Modified

| File | Changes |
|------|---------|
| `src/elile/config/settings.py` | Added API_HOST, API_PORT, CORS_ORIGINS |
| `src/elile/db/config.py` | Added init_db(), close_db(), get_async_session() |
| `src/elile/db/models/audit.py` | Added API_REQUEST, API_ERROR event types |
| `src/elile/core/exceptions.py` | Added AuthenticationError |
| `tests/conftest.py` | Added test_app, test_client, authenticated_client fixtures |

## Component Design

### 1. Application Factory (`src/elile/api/app.py`)

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure FastAPI application."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Elile API",
        description="Employee risk assessment platform API",
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=_lifespan,
    )

    app.state.settings = settings
    _configure_middleware(app, settings)
    _configure_routers(app)
    return app
```

### 2. Middleware Stack (outer to inner)

```
Request
  -> RequestLoggingMiddleware (audit all requests)
    -> ErrorHandlingMiddleware (exception -> HTTP response)
      -> CORSMiddleware (if configured)
        -> AuthenticationMiddleware (validate Bearer token)
          -> TenantValidationMiddleware (validate X-Tenant-ID)
            -> RequestContextMiddleware (set ContextVar)
              -> Route Handler
```

### 3. Error Response Format

```python
class APIError(BaseModel):
    error_code: str      # e.g., "not_found", "unauthorized"
    message: str         # Human-readable message
    details: dict | None # Additional context
    request_id: str      # UUIDv7 for tracing
    timestamp: datetime  # When error occurred
```

### 4. Exception to HTTP Mapping

| Exception | HTTP Status | Error Code |
|-----------|-------------|------------|
| AuthenticationError | 401 | unauthorized |
| TenantNotFoundError | 404 | tenant_not_found |
| TenantInactiveError | 403 | tenant_inactive |
| TenantAccessDeniedError | 403 | tenant_access_denied |
| ComplianceError | 403 | compliance_blocked |
| BudgetExceededError | 402 | budget_exceeded |
| ConsentExpiredError | 403 | consent_expired |
| ConsentScopeError | 403 | consent_scope_error |
| ValidationError | 422 | validation_error |
| ContextNotSetError | 500 | internal_error |

### 5. Health Endpoints

```
GET /health        # Basic liveness (no auth required)
GET /health/db     # Database connectivity check
GET /health/ready  # Full readiness check (database + redis)
```

## Key Implementation Details

### Request ID Flow
- RequestContextMiddleware generates UUIDv7 request_id
- ID is stored in request.state.request_id
- Added to X-Request-ID response header
- Included in all error responses for tracing

### Authentication Flow
- Bearer token extracted from Authorization header
- Validated against settings.API_SECRET_KEY
- In DEBUG mode with no key: accepts any non-empty token
- Sets request.state.actor_id and request.state.actor_type

### Tenant Validation Flow
- X-Tenant-ID header extracted and parsed as UUID
- Tenant validated via TenantService (exists and active)
- Sets request.state.tenant_id for downstream use

### Settings Injection
- Middleware uses app.state.settings for testability
- Falls back to get_settings() for production compatibility

## Test Summary

- **Unit Tests**: 45 tests covering schemas and middleware
- **Integration Tests**: 33 tests covering endpoints and middleware stack
- **Total**: 78 new tests, all passing

## Verification Commands

```bash
# Run all tests
.venv/bin/pytest -v

# Run only API tests
.venv/bin/pytest tests/unit/test_api*.py tests/integration/test_api*.py -v

# Start server
uvicorn elile.api.app:create_app --factory

# Test health endpoint
curl http://localhost:8000/health

# Test with auth
curl -H "Authorization: Bearer <key>" -H "X-Tenant-ID: <uuid>" http://localhost:8000/v1/...
```

## Notes

- Health endpoints bypass auth and tenant validation
- UUIDv7 used for all request_id values (time-ordered)
- API key validation uses app.state.settings for test isolation
- CORS middleware only added if CORS_ORIGINS is configured
- Database init/close handled in application lifespan
