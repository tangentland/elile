# Task 12.1: Performance Profiling - Implementation Plan

## Overview

Implemented comprehensive observability infrastructure for the Elile platform, including:
- OpenTelemetry distributed tracing with OTLP export
- Prometheus metrics for all critical operations
- HTTP request middleware for automatic metrics collection
- Custom span decorators for screening, SAR loop, and provider operations

## Files Created

### Source Files

| File | Purpose |
|------|---------|
| `src/elile/observability/__init__.py` | Module exports and public API |
| `src/elile/observability/tracing.py` | OpenTelemetry tracing instrumentation |
| `src/elile/observability/metrics.py` | Prometheus metrics definitions and helpers |
| `src/elile/api/middleware/observability.py` | HTTP request metrics middleware |

### Test Files

| File | Tests |
|------|-------|
| `tests/unit/test_observability_tracing.py` | 40 tests for tracing module |
| `tests/unit/test_observability_metrics.py` | 37 tests for metrics module |
| `tests/integration/test_observability_middleware.py` | 12 tests for middleware |

## Files Modified

| File | Changes |
|------|---------|
| `pyproject.toml` | Added OpenTelemetry and Prometheus dependencies |
| `src/elile/api/app.py` | Integrated observability initialization in lifespan |
| `src/elile/api/routers/health.py` | Added `/metrics` endpoint |
| `src/elile/api/middleware/__init__.py` | Exported ObservabilityMiddleware |
| `CODEBASE_INDEX.md` | Added observability module documentation |
| `IMPLEMENTATION_STATUS.md` | Updated Phase 12 progress |
| `docs/plans/phase-12-production-readiness.md` | Updated task status |
| `docs/plans/P0-TASKS-SUMMARY.md` | Updated task status |

## Key Patterns Used

### Tracing Decorators
```python
@traced_async("screening.execute")
async def execute_screening():
    add_span_attributes(screening_id=str(screening.id))
    ...

@trace_screening(screening_id=screening_id, tier="standard", degree="d1")
async def screening_operation():
    ...
```

### Metrics Context Managers
```python
with observe_screening_duration(tier="standard", degree="d1") as ctx:
    result = await execute_screening()
    ctx["status"] = "success"
```

### Key Metrics Defined
| Metric | Type | Purpose |
|--------|------|---------|
| `elile_screening_duration_seconds` | Histogram | Screening execution time |
| `elile_screenings_total` | Counter | Total screenings by tier/degree/status |
| `elile_provider_query_duration_seconds` | Histogram | Provider query latency |
| `elile_sar_confidence_score` | Histogram | SAR loop confidence scores |
| `elile_risk_score` | Histogram | Risk score distribution |
| `elile_http_request_duration_seconds` | Histogram | HTTP request latency |

## Test Results

```
======================== 89 passed, 2 warnings in 0.27s ========================
```

All 89 tests pass:
- 40 tracing unit tests
- 37 metrics unit tests
- 12 middleware integration tests

## Dependencies Added

```toml
# OpenTelemetry for distributed tracing
"opentelemetry-api>=1.20.0",
"opentelemetry-sdk>=1.20.0",
"opentelemetry-instrumentation-fastapi>=0.43b0",
"opentelemetry-instrumentation-sqlalchemy>=0.43b0",
"opentelemetry-instrumentation-httpx>=0.43b0",
"opentelemetry-exporter-otlp>=1.20.0",
# Prometheus metrics
"prometheus-client>=0.19.0",
"starlette-prometheus>=0.9.0",
```

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OTEL_SERVICE_NAME` | "elile" | Service name in traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | None | OTLP collector endpoint |
| `OTEL_TRACING_ENABLED` | "true" | Enable/disable tracing |
| `OTEL_SAMPLE_RATE` | "1.0" | Trace sampling rate |
| `METRICS_ENABLED` | "true" | Enable/disable metrics |
| `METRICS_PREFIX` | "elile" | Metric name prefix |

## Architecture Integration

The observability module integrates with the existing architecture:

1. **Middleware Stack**: `ObservabilityMiddleware` is the outermost middleware, capturing all HTTP requests
2. **Lifespan Management**: Tracing is initialized at startup and shutdown cleanly
3. **FastAPI Instrumentation**: Automatic span creation for all API endpoints
4. **SQLAlchemy Instrumentation**: Database query tracing (when enabled)
5. **HTTPX Instrumentation**: Outbound HTTP request tracing

## Usage Examples

### Initialize Tracing
```python
from elile.observability import TracingManager, TracingConfig

config = TracingConfig(
    service_name="elile",
    otlp_endpoint="http://localhost:4317",
)
manager = TracingManager(config)
manager.initialize()
manager.instrument_fastapi(app)
```

### Record Custom Metrics
```python
from elile.observability import (
    record_provider_query,
    observe_risk_score,
)

record_provider_query(
    provider_id="sterling",
    check_type="criminal_national",
    status="success",
    duration_seconds=1.5,
)

observe_risk_score(
    score=45.0,
    role_category="financial",
    level="moderate",
    recommendation="review_required",
)
```

## Notes

- The `/metrics` endpoint is excluded from authentication for Prometheus scraping
- Health endpoints are excluded from metrics to avoid noise
- UUIDs and numeric IDs in paths are normalized to `{id}` for low-cardinality metrics
- Tracing can be disabled via environment variable for performance-sensitive deployments
