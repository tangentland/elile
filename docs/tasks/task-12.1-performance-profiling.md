# Task 12.1: Performance Profiling

## Overview

Implement performance profiling and monitoring instrumentation using OpenTelemetry for distributed tracing, metrics collection, and performance bottleneck identification.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 7.1: Screening Orchestrator
- Task 5.9: SAR Loop Orchestrator

## Implementation

```python
# src/elile/observability/tracing.py
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Initialize tracer
tracer = trace.get_tracer(__name__)

# Instrument FastAPI
FastAPIInstrumentor.instrument_app(app)

# Add custom spans
@tracer.start_as_current_span("sar_loop_execution")
async def execute_sar_with_tracing(...):
    span = trace.get_current_span()
    span.set_attribute("info_type", str(info_type))
    span.set_attribute("iteration", iteration_number)

    result = await execute_sar_loop(...)

    span.set_attribute("confidence_score", result.confidence_score)
    return result

# Performance metrics
from prometheus_client import Counter, Histogram

screening_duration = Histogram(
    "screening_duration_seconds",
    "Time to complete screening",
    ["tier", "degree"]
)

query_count = Counter(
    "provider_queries_total",
    "Total provider queries",
    ["provider", "status"]
)
```

## Acceptance Criteria

- [ ] OpenTelemetry tracing instrumented
- [ ] Custom spans for key operations
- [ ] Prometheus metrics exported
- [ ] Performance baseline established
- [ ] Bottleneck identification dashboard

## Deliverables

- `src/elile/observability/tracing.py`
- `src/elile/observability/metrics.py`
- Performance baseline report

## References

- Architecture: [10-platform.md](../../docs/architecture/10-platform.md)

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
