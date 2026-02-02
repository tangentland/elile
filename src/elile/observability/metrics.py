"""Prometheus metrics for Elile observability.

This module provides Prometheus metrics for monitoring:
- Screening operations (duration, status, tier/degree distribution)
- Provider queries (latency, success rate, cache hits)
- SAR loop iterations (confidence scores, iteration counts)
- Risk analysis (score distribution, level counts)
- System health (queue depth, active screenings)
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    Summary,
    generate_latest,
)

if TYPE_CHECKING:
    from collections.abc import Generator

__all__ = [
    "MetricsConfig",
    "MetricsManager",
    "SCREENING_DURATION",
    "SCREENING_COUNT",
    "SCREENING_IN_PROGRESS",
    "PROVIDER_QUERY_DURATION",
    "PROVIDER_QUERY_COUNT",
    "PROVIDER_CACHE_HITS",
    "SAR_ITERATION_COUNT",
    "SAR_CONFIDENCE_SCORE",
    "RISK_SCORE_DISTRIBUTION",
    "RISK_LEVEL_COUNT",
    "HTTP_REQUEST_DURATION",
    "HTTP_REQUEST_COUNT",
    "DB_QUERY_DURATION",
    "ACTIVE_CONNECTIONS",
    "observe_screening_duration",
    "observe_provider_query",
    "observe_sar_iteration",
    "observe_risk_score",
    "get_metrics",
    "create_metrics_manager",
]

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class MetricsConfig:
    """Configuration for Prometheus metrics.

    Attributes:
        enabled: Whether metrics collection is enabled.
        prefix: Prefix for all metric names.
        default_labels: Labels applied to all metrics.
        histogram_buckets: Custom histogram buckets for latency metrics.
    """

    enabled: bool = True
    prefix: str = "elile"
    default_labels: dict[str, str] | None = None
    histogram_buckets: tuple[float, ...] = (
        0.005,
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        7.5,
        10.0,
        30.0,
        60.0,
    )

    @classmethod
    def from_env(cls) -> MetricsConfig:
        """Create configuration from environment variables."""
        return cls(
            enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
            prefix=os.getenv("METRICS_PREFIX", "elile"),
        )


# Default configuration
_config = MetricsConfig()

# ============================================================================
# Screening Metrics
# ============================================================================

SCREENING_DURATION = Histogram(
    f"{_config.prefix}_screening_duration_seconds",
    "Time to complete a screening operation",
    ["tier", "degree", "status"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0),
)

SCREENING_COUNT = Counter(
    f"{_config.prefix}_screenings_total",
    "Total number of screenings processed",
    ["tier", "degree", "status", "locale"],
)

SCREENING_IN_PROGRESS = Gauge(
    f"{_config.prefix}_screenings_in_progress",
    "Number of screenings currently in progress",
    ["tier", "degree"],
)

SCREENING_PHASE_DURATION = Histogram(
    f"{_config.prefix}_screening_phase_duration_seconds",
    "Duration of each screening phase",
    ["phase", "tier"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0),
)

# ============================================================================
# Provider Metrics
# ============================================================================

PROVIDER_QUERY_DURATION = Histogram(
    f"{_config.prefix}_provider_query_duration_seconds",
    "Time for provider query execution",
    ["provider_id", "check_type", "status"],
    buckets=_config.histogram_buckets,
)

PROVIDER_QUERY_COUNT = Counter(
    f"{_config.prefix}_provider_queries_total",
    "Total number of provider queries",
    ["provider_id", "check_type", "status"],
)

PROVIDER_CACHE_HITS = Counter(
    f"{_config.prefix}_provider_cache_hits_total",
    "Number of cache hits for provider queries",
    ["provider_id", "check_type"],
)

PROVIDER_CACHE_MISSES = Counter(
    f"{_config.prefix}_provider_cache_misses_total",
    "Number of cache misses for provider queries",
    ["provider_id", "check_type"],
)

PROVIDER_RATE_LIMITED = Counter(
    f"{_config.prefix}_provider_rate_limited_total",
    "Number of rate-limited provider requests",
    ["provider_id"],
)

PROVIDER_CIRCUIT_BREAKER_STATE = Gauge(
    f"{_config.prefix}_provider_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["provider_id"],
)

PROVIDER_HEALTH_STATUS = Gauge(
    f"{_config.prefix}_provider_health_status",
    "Provider health status (0=unhealthy, 1=degraded, 2=healthy)",
    ["provider_id"],
)

# ============================================================================
# SAR Loop Metrics
# ============================================================================

SAR_ITERATION_COUNT = Counter(
    f"{_config.prefix}_sar_iterations_total",
    "Total SAR loop iterations",
    ["info_type", "completion_reason"],
)

SAR_CONFIDENCE_SCORE = Histogram(
    f"{_config.prefix}_sar_confidence_score",
    "Final confidence scores from SAR loops",
    ["info_type"],
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0),
)

SAR_FACTS_DISCOVERED = Counter(
    f"{_config.prefix}_sar_facts_discovered_total",
    "Total facts discovered during SAR loops",
    ["info_type"],
)

SAR_QUERIES_EXECUTED = Counter(
    f"{_config.prefix}_sar_queries_executed_total",
    "Total queries executed during SAR loops",
    ["info_type", "query_type"],
)

SAR_PHASE_DURATION = Histogram(
    f"{_config.prefix}_sar_phase_duration_seconds",
    "Duration of SAR phases",
    ["phase"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
)

# ============================================================================
# Risk Analysis Metrics
# ============================================================================

RISK_SCORE_DISTRIBUTION = Histogram(
    f"{_config.prefix}_risk_score",
    "Distribution of risk scores",
    ["role_category"],
    buckets=(0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100),
)

RISK_LEVEL_COUNT = Counter(
    f"{_config.prefix}_risk_levels_total",
    "Count of screenings by risk level",
    ["level", "recommendation"],
)

FINDINGS_COUNT = Counter(
    f"{_config.prefix}_findings_total",
    "Total findings discovered",
    ["category", "severity"],
)

ANOMALIES_DETECTED = Counter(
    f"{_config.prefix}_anomalies_detected_total",
    "Total anomalies detected",
    ["anomaly_type"],
)

PATTERNS_RECOGNIZED = Counter(
    f"{_config.prefix}_patterns_recognized_total",
    "Total behavioral patterns recognized",
    ["pattern_type"],
)

# ============================================================================
# HTTP/API Metrics
# ============================================================================

HTTP_REQUEST_DURATION = Histogram(
    f"{_config.prefix}_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint", "status_code"],
    buckets=_config.histogram_buckets,
)

HTTP_REQUEST_COUNT = Counter(
    f"{_config.prefix}_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_SIZE = Summary(
    f"{_config.prefix}_http_request_size_bytes",
    "HTTP request body size",
    ["method", "endpoint"],
)

HTTP_RESPONSE_SIZE = Summary(
    f"{_config.prefix}_http_response_size_bytes",
    "HTTP response body size",
    ["method", "endpoint"],
)

# ============================================================================
# Database Metrics
# ============================================================================

DB_QUERY_DURATION = Histogram(
    f"{_config.prefix}_db_query_duration_seconds",
    "Database query duration",
    ["operation", "table"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

DB_QUERY_COUNT = Counter(
    f"{_config.prefix}_db_queries_total",
    "Total database queries",
    ["operation", "table"],
)

ACTIVE_CONNECTIONS = Gauge(
    f"{_config.prefix}_db_active_connections",
    "Number of active database connections",
)

CONNECTION_POOL_SIZE = Gauge(
    f"{_config.prefix}_db_connection_pool_size",
    "Size of database connection pool",
)

# ============================================================================
# System Metrics
# ============================================================================

QUEUE_DEPTH = Gauge(
    f"{_config.prefix}_queue_depth",
    "Number of items in processing queue",
    ["queue_name"],
)

WORKER_COUNT = Gauge(
    f"{_config.prefix}_worker_count",
    "Number of active workers",
    ["worker_type"],
)

MEMORY_USAGE_BYTES = Gauge(
    f"{_config.prefix}_memory_usage_bytes",
    "Current memory usage in bytes",
)

# Service info
SERVICE_INFO = Info(
    f"{_config.prefix}_service",
    "Service information",
)


class MetricsManager:
    """Manages Prometheus metrics configuration and export.

    This class handles:
    - Metrics configuration and initialization
    - Custom registry support for testing
    - Metrics export endpoint integration
    """

    def __init__(
        self,
        config: MetricsConfig | None = None,
        registry: CollectorRegistry | None = None,
    ) -> None:
        """Initialize the metrics manager.

        Args:
            config: Metrics configuration.
            registry: Optional custom registry for testing.
        """
        self.config = config or MetricsConfig()
        self.registry = registry or REGISTRY
        self._initialized = False

    def initialize(
        self,
        service_name: str = "elile",
        service_version: str = "0.1.0",
        environment: str = "development",
    ) -> None:
        """Initialize metrics with service information.

        Args:
            service_name: Name of the service.
            service_version: Version of the service.
            environment: Deployment environment.
        """
        if self._initialized or not self.config.enabled:
            return

        SERVICE_INFO.info(
            {
                "name": service_name,
                "version": service_version,
                "environment": environment,
            }
        )

        self._initialized = True

    def get_metrics(self) -> bytes:
        """Generate metrics output in Prometheus format.

        Returns:
            Prometheus metrics as bytes.
        """
        return generate_latest(self.registry)


# Global metrics manager
_metrics_manager: MetricsManager | None = None


def get_metrics_manager() -> MetricsManager:
    """Get the global metrics manager instance."""
    global _metrics_manager
    if _metrics_manager is None:
        _metrics_manager = MetricsManager(MetricsConfig.from_env())
    return _metrics_manager


def create_metrics_manager(
    config: MetricsConfig | None = None,
    registry: CollectorRegistry | None = None,
) -> MetricsManager:
    """Create and register a new metrics manager.

    Args:
        config: Optional metrics configuration.
        registry: Optional custom registry.

    Returns:
        The configured MetricsManager instance.
    """
    global _metrics_manager
    _metrics_manager = MetricsManager(config, registry)
    return _metrics_manager


def get_metrics() -> bytes:
    """Get current metrics in Prometheus format.

    Returns:
        Prometheus metrics as bytes.
    """
    return get_metrics_manager().get_metrics()


# ============================================================================
# Convenience Functions for Recording Metrics
# ============================================================================


@contextmanager
def observe_screening_duration(
    tier: str,
    degree: str,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for observing screening duration.

    Args:
        tier: Service tier (Standard/Enhanced).
        degree: Search degree (D1/D2/D3).

    Yields:
        Context dict for setting status after completion.
    """
    SCREENING_IN_PROGRESS.labels(tier=tier, degree=degree).inc()
    context: dict[str, Any] = {"status": "success"}
    start_time = time.perf_counter()

    try:
        yield context
    except Exception:
        context["status"] = "error"
        raise
    finally:
        duration = time.perf_counter() - start_time
        status = context.get("status", "success")
        SCREENING_DURATION.labels(tier=tier, degree=degree, status=status).observe(duration)
        SCREENING_IN_PROGRESS.labels(tier=tier, degree=degree).dec()


def record_screening_complete(
    tier: str,
    degree: str,
    status: str,
    locale: str,
    duration_seconds: float | None = None,
) -> None:
    """Record a completed screening.

    Args:
        tier: Service tier.
        degree: Search degree.
        status: Completion status.
        locale: Geographic locale.
        duration_seconds: Optional duration if not using context manager.
    """
    SCREENING_COUNT.labels(tier=tier, degree=degree, status=status, locale=locale).inc()
    if duration_seconds is not None:
        SCREENING_DURATION.labels(tier=tier, degree=degree, status=status).observe(duration_seconds)


def record_screening_phase(
    phase: str,
    tier: str,
    duration_seconds: float,
) -> None:
    """Record screening phase duration.

    Args:
        phase: Phase name.
        tier: Service tier.
        duration_seconds: Phase duration.
    """
    SCREENING_PHASE_DURATION.labels(phase=phase, tier=tier).observe(duration_seconds)


@contextmanager
def observe_provider_query(
    provider_id: str,
    check_type: str,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for observing provider query duration.

    Args:
        provider_id: Provider identifier.
        check_type: Type of check.

    Yields:
        Context dict for setting status and cache hit.
    """
    context: dict[str, Any] = {"status": "success", "cache_hit": False}
    start_time = time.perf_counter()

    try:
        yield context
    except Exception:
        context["status"] = "error"
        raise
    finally:
        duration = time.perf_counter() - start_time
        status = context.get("status", "success")
        cache_hit = context.get("cache_hit", False)

        PROVIDER_QUERY_DURATION.labels(
            provider_id=provider_id, check_type=check_type, status=status
        ).observe(duration)
        PROVIDER_QUERY_COUNT.labels(
            provider_id=provider_id, check_type=check_type, status=status
        ).inc()

        if cache_hit:
            PROVIDER_CACHE_HITS.labels(provider_id=provider_id, check_type=check_type).inc()
        else:
            PROVIDER_CACHE_MISSES.labels(provider_id=provider_id, check_type=check_type).inc()


def record_provider_query(
    provider_id: str,
    check_type: str,
    status: str,
    duration_seconds: float,
    cache_hit: bool = False,
) -> None:
    """Record a provider query.

    Args:
        provider_id: Provider identifier.
        check_type: Type of check.
        status: Query status.
        duration_seconds: Query duration.
        cache_hit: Whether result was from cache.
    """
    PROVIDER_QUERY_DURATION.labels(
        provider_id=provider_id, check_type=check_type, status=status
    ).observe(duration_seconds)
    PROVIDER_QUERY_COUNT.labels(provider_id=provider_id, check_type=check_type, status=status).inc()

    if cache_hit:
        PROVIDER_CACHE_HITS.labels(provider_id=provider_id, check_type=check_type).inc()
    else:
        PROVIDER_CACHE_MISSES.labels(provider_id=provider_id, check_type=check_type).inc()


def record_provider_rate_limited(provider_id: str) -> None:
    """Record a rate-limited provider request.

    Args:
        provider_id: Provider identifier.
    """
    PROVIDER_RATE_LIMITED.labels(provider_id=provider_id).inc()


def set_provider_circuit_breaker_state(provider_id: str, state: str) -> None:
    """Set circuit breaker state for a provider.

    Args:
        provider_id: Provider identifier.
        state: State (closed, open, half_open).
    """
    state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state.lower(), 0)
    PROVIDER_CIRCUIT_BREAKER_STATE.labels(provider_id=provider_id).set(state_value)


def set_provider_health_status(provider_id: str, status: str) -> None:
    """Set health status for a provider.

    Args:
        provider_id: Provider identifier.
        status: Status (unhealthy, degraded, healthy).
    """
    status_value = {"unhealthy": 0, "degraded": 1, "healthy": 2}.get(status.lower(), 0)
    PROVIDER_HEALTH_STATUS.labels(provider_id=provider_id).set(status_value)


@contextmanager
def observe_sar_iteration(
    info_type: str,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for observing SAR iteration.

    Args:
        info_type: Information type being processed.

    Yields:
        Context dict for setting completion reason and metrics.
    """
    context: dict[str, Any] = {
        "completion_reason": "confidence_met",
        "confidence_score": 0.0,
        "facts_discovered": 0,
    }

    try:
        yield context
    finally:
        completion_reason = context.get("completion_reason", "confidence_met")
        confidence_score = context.get("confidence_score", 0.0)
        facts_discovered = context.get("facts_discovered", 0)

        SAR_ITERATION_COUNT.labels(info_type=info_type, completion_reason=completion_reason).inc()
        SAR_CONFIDENCE_SCORE.labels(info_type=info_type).observe(confidence_score)
        SAR_FACTS_DISCOVERED.labels(info_type=info_type).inc(facts_discovered)


def record_sar_iteration(
    info_type: str,
    completion_reason: str,
    confidence_score: float,
    facts_discovered: int = 0,
    queries_executed: int = 0,  # noqa: ARG001 - reserved for future metrics
    query_types: dict[str, int] | None = None,
) -> None:
    """Record SAR iteration metrics.

    Args:
        info_type: Information type.
        completion_reason: Why iteration completed.
        confidence_score: Final confidence score.
        facts_discovered: Number of facts found.
        queries_executed: Number of queries executed (reserved for future use).
        query_types: Count by query type.
    """
    SAR_ITERATION_COUNT.labels(info_type=info_type, completion_reason=completion_reason).inc()
    SAR_CONFIDENCE_SCORE.labels(info_type=info_type).observe(confidence_score)
    SAR_FACTS_DISCOVERED.labels(info_type=info_type).inc(facts_discovered)

    if query_types:
        for query_type, count in query_types.items():
            SAR_QUERIES_EXECUTED.labels(info_type=info_type, query_type=query_type).inc(count)


def record_sar_phase(phase: str, duration_seconds: float) -> None:
    """Record SAR phase duration.

    Args:
        phase: Phase name.
        duration_seconds: Phase duration.
    """
    SAR_PHASE_DURATION.labels(phase=phase).observe(duration_seconds)


def observe_risk_score(
    score: float,
    role_category: str,
    level: str,
    recommendation: str,
) -> None:
    """Record risk score observation.

    Args:
        score: Risk score (0-100).
        role_category: Job role category.
        level: Risk level.
        recommendation: Recommended action.
    """
    RISK_SCORE_DISTRIBUTION.labels(role_category=role_category).observe(score)
    RISK_LEVEL_COUNT.labels(level=level, recommendation=recommendation).inc()


def record_finding(category: str, severity: str) -> None:
    """Record a discovered finding.

    Args:
        category: Finding category.
        severity: Finding severity.
    """
    FINDINGS_COUNT.labels(category=category, severity=severity).inc()


def record_anomaly(anomaly_type: str) -> None:
    """Record a detected anomaly.

    Args:
        anomaly_type: Type of anomaly.
    """
    ANOMALIES_DETECTED.labels(anomaly_type=anomaly_type).inc()


def record_pattern(pattern_type: str) -> None:
    """Record a recognized pattern.

    Args:
        pattern_type: Type of pattern.
    """
    PATTERNS_RECOGNIZED.labels(pattern_type=pattern_type).inc()


def record_http_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration_seconds: float,
    request_size: int | None = None,
    response_size: int | None = None,
) -> None:
    """Record HTTP request metrics.

    Args:
        method: HTTP method.
        endpoint: Request endpoint.
        status_code: Response status code.
        duration_seconds: Request duration.
        request_size: Optional request body size.
        response_size: Optional response body size.
    """
    HTTP_REQUEST_DURATION.labels(
        method=method, endpoint=endpoint, status_code=str(status_code)
    ).observe(duration_seconds)
    HTTP_REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()

    if request_size is not None:
        HTTP_REQUEST_SIZE.labels(method=method, endpoint=endpoint).observe(request_size)
    if response_size is not None:
        HTTP_RESPONSE_SIZE.labels(method=method, endpoint=endpoint).observe(response_size)


def record_db_query(operation: str, table: str, duration_seconds: float) -> None:
    """Record database query metrics.

    Args:
        operation: Query operation type.
        table: Target table.
        duration_seconds: Query duration.
    """
    DB_QUERY_DURATION.labels(operation=operation, table=table).observe(duration_seconds)
    DB_QUERY_COUNT.labels(operation=operation, table=table).inc()


def set_active_connections(count: int) -> None:
    """Set active database connection count.

    Args:
        count: Number of active connections.
    """
    ACTIVE_CONNECTIONS.set(count)


def set_connection_pool_size(size: int) -> None:
    """Set connection pool size.

    Args:
        size: Pool size.
    """
    CONNECTION_POOL_SIZE.set(size)


def set_queue_depth(queue_name: str, depth: int) -> None:
    """Set queue depth.

    Args:
        queue_name: Name of the queue.
        depth: Current queue depth.
    """
    QUEUE_DEPTH.labels(queue_name=queue_name).set(depth)


def set_worker_count(worker_type: str, count: int) -> None:
    """Set worker count.

    Args:
        worker_type: Type of worker.
        count: Number of workers.
    """
    WORKER_COUNT.labels(worker_type=worker_type).set(count)


def set_memory_usage(bytes_used: int) -> None:
    """Set memory usage.

    Args:
        bytes_used: Memory usage in bytes.
    """
    MEMORY_USAGE_BYTES.set(bytes_used)
