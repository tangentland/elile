"""Observability module for Elile.

This module provides comprehensive observability capabilities:
- OpenTelemetry distributed tracing
- Prometheus metrics collection
- Performance profiling utilities

Usage:
    # Initialize tracing
    from elile.observability import TracingManager, TracingConfig

    config = TracingConfig(
        service_name="elile",
        otlp_endpoint="http://localhost:4317",
    )
    manager = TracingManager(config)
    manager.initialize()
    manager.instrument_fastapi(app)

    # Use tracing decorators
    from elile.observability import traced_async, add_span_attributes

    @traced_async("my_operation")
    async def my_function():
        add_span_attributes(custom_attr="value")
        ...

    # Record metrics
    from elile.observability import (
        observe_screening_duration,
        record_provider_query,
        observe_risk_score,
    )

    with observe_screening_duration(tier="standard", degree="d1") as ctx:
        result = await execute_screening()
        ctx["status"] = "success"

    record_provider_query(
        provider_id="sterling",
        check_type="criminal_national",
        status="success",
        duration_seconds=1.5,
        cache_hit=False,
    )
"""

from elile.observability.metrics import (
    ACTIVE_CONNECTIONS,
    ANOMALIES_DETECTED,
    CONNECTION_POOL_SIZE,
    DB_QUERY_COUNT,
    DB_QUERY_DURATION,
    FINDINGS_COUNT,
    HTTP_REQUEST_COUNT,
    HTTP_REQUEST_DURATION,
    HTTP_REQUEST_SIZE,
    HTTP_RESPONSE_SIZE,
    MEMORY_USAGE_BYTES,
    PATTERNS_RECOGNIZED,
    PROVIDER_CACHE_HITS,
    PROVIDER_CACHE_MISSES,
    PROVIDER_CIRCUIT_BREAKER_STATE,
    PROVIDER_HEALTH_STATUS,
    PROVIDER_QUERY_COUNT,
    PROVIDER_QUERY_DURATION,
    PROVIDER_RATE_LIMITED,
    QUEUE_DEPTH,
    RISK_LEVEL_COUNT,
    RISK_SCORE_DISTRIBUTION,
    SAR_CONFIDENCE_SCORE,
    SAR_FACTS_DISCOVERED,
    SAR_ITERATION_COUNT,
    SAR_PHASE_DURATION,
    SAR_QUERIES_EXECUTED,
    SCREENING_COUNT,
    SCREENING_DURATION,
    SCREENING_IN_PROGRESS,
    SCREENING_PHASE_DURATION,
    SERVICE_INFO,
    WORKER_COUNT,
    MetricsConfig,
    MetricsManager,
    create_metrics_manager,
    get_metrics,
    get_metrics_manager,
    observe_provider_query,
    observe_risk_score,
    observe_sar_iteration,
    observe_screening_duration,
    record_anomaly,
    record_db_query,
    record_finding,
    record_http_request,
    record_pattern,
    record_provider_query,
    record_provider_rate_limited,
    record_sar_iteration,
    record_sar_phase,
    record_screening_complete,
    record_screening_phase,
    set_active_connections,
    set_connection_pool_size,
    set_memory_usage,
    set_provider_circuit_breaker_state,
    set_provider_health_status,
    set_queue_depth,
    set_worker_count,
)
from elile.observability.tracing import (
    SpanKindType,
    TracingConfig,
    TracingManager,
    add_span_attributes,
    add_span_event,
    create_span,
    create_tracing_manager,
    extract_trace_context,
    get_current_span,
    get_tracer,
    get_tracing_manager,
    inject_trace_context,
    record_exception,
    trace_provider_query,
    trace_sar_loop,
    trace_screening,
    traced,
    traced_async,
)

__all__ = [
    # Tracing
    "TracingConfig",
    "TracingManager",
    "SpanKindType",
    "traced",
    "traced_async",
    "add_span_attributes",
    "add_span_event",
    "record_exception",
    "get_current_span",
    "get_tracer",
    "get_tracing_manager",
    "create_tracing_manager",
    "create_span",
    "inject_trace_context",
    "extract_trace_context",
    "trace_sar_loop",
    "trace_screening",
    "trace_provider_query",
    # Metrics Configuration
    "MetricsConfig",
    "MetricsManager",
    "get_metrics",
    "get_metrics_manager",
    "create_metrics_manager",
    # Screening Metrics
    "SCREENING_DURATION",
    "SCREENING_COUNT",
    "SCREENING_IN_PROGRESS",
    "SCREENING_PHASE_DURATION",
    "observe_screening_duration",
    "record_screening_complete",
    "record_screening_phase",
    # Provider Metrics
    "PROVIDER_QUERY_DURATION",
    "PROVIDER_QUERY_COUNT",
    "PROVIDER_CACHE_HITS",
    "PROVIDER_CACHE_MISSES",
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_CIRCUIT_BREAKER_STATE",
    "PROVIDER_HEALTH_STATUS",
    "observe_provider_query",
    "record_provider_query",
    "record_provider_rate_limited",
    "set_provider_circuit_breaker_state",
    "set_provider_health_status",
    # SAR Loop Metrics
    "SAR_ITERATION_COUNT",
    "SAR_CONFIDENCE_SCORE",
    "SAR_FACTS_DISCOVERED",
    "SAR_QUERIES_EXECUTED",
    "SAR_PHASE_DURATION",
    "observe_sar_iteration",
    "record_sar_iteration",
    "record_sar_phase",
    # Risk Analysis Metrics
    "RISK_SCORE_DISTRIBUTION",
    "RISK_LEVEL_COUNT",
    "FINDINGS_COUNT",
    "ANOMALIES_DETECTED",
    "PATTERNS_RECOGNIZED",
    "observe_risk_score",
    "record_finding",
    "record_anomaly",
    "record_pattern",
    # HTTP Metrics
    "HTTP_REQUEST_DURATION",
    "HTTP_REQUEST_COUNT",
    "HTTP_REQUEST_SIZE",
    "HTTP_RESPONSE_SIZE",
    "record_http_request",
    # Database Metrics
    "DB_QUERY_DURATION",
    "DB_QUERY_COUNT",
    "ACTIVE_CONNECTIONS",
    "CONNECTION_POOL_SIZE",
    "record_db_query",
    "set_active_connections",
    "set_connection_pool_size",
    # System Metrics
    "QUEUE_DEPTH",
    "WORKER_COUNT",
    "MEMORY_USAGE_BYTES",
    "SERVICE_INFO",
    "set_queue_depth",
    "set_worker_count",
    "set_memory_usage",
]
