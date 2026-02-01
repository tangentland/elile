# Task 1.5: FastAPI Framework Setup

## Overview

Initialize FastAPI application with async database support, middleware stack (CORS, logging, context injection), OpenAPI documentation, and basic endpoint structure. Foundation for all API development.

**Priority**: P0 | **Effort**: 1-2 days | **Status**: Not Started

## Dependencies

- Task 1.3: Request Context (context middleware)
- External: FastAPI 0.109+, uvicorn

## Implementation Checklist

- [ ] Create FastAPI app with lifespan management
- [ ] Configure async database connection pool
- [ ] Add middleware stack (CORS, logging, context, tenant)
- [ ] Set up OpenAPI/Swagger documentation
- [ ] Create router structure by domain
- [ ] Implement global exception handlers
- [ ] Configure uvicorn for development
- [ ] Write startup/shutdown tests

## Key Implementation

```python
# src/elile/api/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .middleware import (
    request_context_middleware,
    tenant_validation_middleware,
    correlation_id_middleware
)
from .routers import health, screenings, monitoring

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    await init_database_pool()
    await init_redis_pool()
    yield
    # Shutdown
    await close_database_pool()
    await close_redis_pool()

app = FastAPI(
    title="Elile Background Screening API",
    version="0.1.0",
    description="Employee risk assessment platform",
    lifespan=lifespan
)

# Middleware stack (order matters!)
app.add_middleware(CORSMiddleware, allow_origins=["*"])
app.add_middleware(correlation_id_middleware)
app.add_middleware(tenant_validation_middleware)
app.add_middleware(request_context_middleware)

# Routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(screenings.router, prefix="/api/v1", tags=["screenings"])

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Log all exceptions with correlation_id."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

# src/elile/config/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
)

async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db() -> AsyncSession:
    """FastAPI dependency for database session."""
    async with async_session_maker() as session:
        yield session
```

## Testing Requirements

### Unit Tests
- App instantiation succeeds
- Middleware stack configured correctly
- Exception handlers registered

### Integration Tests
- GET /api/v1/health returns 200
- Missing X-Tenant-ID returns 400
- OpenAPI schema at /docs accessible
- Database connection pool initialized

**Coverage Target**: 80%+

## Acceptance Criteria

- [ ] FastAPI app starts without errors
- [ ] Database connection pool initialized on startup
- [ ] CORS configured for development
- [ ] Middleware processes requests in order
- [ ] OpenAPI documentation at /docs
- [ ] Global exception handler logs errors
- [ ] Async database sessions work correctly
- [ ] Graceful shutdown closes connections

## Deliverables

- `src/elile/api/app.py`
- `src/elile/api/middleware.py`
- `src/elile/api/routers/health.py`
- `src/elile/config/database.py`
- `src/elile/main.py` (uvicorn entry point)
- `tests/integration/test_api.py`

## References

- Architecture: [02-core-system.md](../architecture/02-core-system.md) - API structure
- Dependencies: Task 1.3 (context middleware)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
