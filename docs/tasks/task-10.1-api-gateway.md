# Task 10.1: API Gateway

## Overview

Implement FastAPI gateway with rate limiting, request validation, error handling, and OpenAPI documentation for all screening and monitoring endpoints.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 1.5: FastAPI Setup
- Task 7.7: Screening API Endpoints

## Implementation

```python
# src/elile/api/gateway.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter

app = FastAPI(
    title="Elile API",
    version="1.0.0",
    description="Employee Risk Assessment Platform"
)

# Rate limiting
limiter = Limiter(key_func=lambda r: r.client.host)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include routers
app.include_router(screening_router)
app.include_router(monitoring_router)
app.include_router(reports_router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global error handler."""
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "request_id": request.state.request_id}
    )
```

## Acceptance Criteria

- [ ] FastAPI application with routers
- [ ] Rate limiting (1000/min standard, 100/min screening)
- [ ] Global error handling
- [ ] OpenAPI documentation
- [ ] CORS middleware

## Deliverables

- `src/elile/api/gateway.py`
- `tests/integration/test_api_gateway.py`

## References

- Architecture: [09-integration.md](../../docs/architecture/09-integration.md)

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
