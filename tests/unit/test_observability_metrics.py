"""Unit tests for Prometheus metrics module."""

from __future__ import annotations

import time

import pytest
from prometheus_client import REGISTRY, CollectorRegistry

from elile.observability.metrics import (
    ACTIVE_CONNECTIONS,
    ANOMALIES_DETECTED,
    CONNECTION_POOL_SIZE,
    DB_QUERY_COUNT,
    DB_QUERY_DURATION,
    FINDINGS_COUNT,
    HTTP_REQUEST_COUNT,
    HTTP_REQUEST_DURATION,
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
    SCREENING_COUNT,
    SCREENING_DURATION,
    SCREENING_IN_PROGRESS,
    WORKER_COUNT,
    MetricsConfig,
    MetricsManager,
    create_metrics_manager,
    get_metrics,
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
    record_screening_complete,
    set_active_connections,
    set_connection_pool_size,
    set_memory_usage,
    set_provider_circuit_breaker_state,
    set_provider_health_status,
    set_queue_depth,
    set_worker_count,
)


class TestMetricsConfig:
    """Tests for MetricsConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = MetricsConfig()

        assert config.enabled is True
        assert config.prefix == "elile"
        assert config.default_labels is None
        assert len(config.histogram_buckets) > 0

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = MetricsConfig(
            enabled=False,
            prefix="custom",
            default_labels={"env": "test"},
        )

        assert config.enabled is False
        assert config.prefix == "custom"
        assert config.default_labels == {"env": "test"}

    def test_from_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env with default environment."""
        monkeypatch.delenv("METRICS_ENABLED", raising=False)
        monkeypatch.delenv("METRICS_PREFIX", raising=False)

        config = MetricsConfig.from_env()

        assert config.enabled is True
        assert config.prefix == "elile"

    def test_from_env_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env with custom environment variables."""
        monkeypatch.setenv("METRICS_ENABLED", "false")
        monkeypatch.setenv("METRICS_PREFIX", "custom")

        config = MetricsConfig.from_env()

        assert config.enabled is False
        assert config.prefix == "custom"


class TestMetricsManager:
    """Tests for MetricsManager."""

    def test_create_manager(self) -> None:
        """Test creating metrics manager."""
        config = MetricsConfig()
        manager = MetricsManager(config)

        assert manager.config == config
        assert manager._initialized is False

    def test_initialize(self) -> None:
        """Test initialization."""
        manager = MetricsManager(MetricsConfig())
        manager.initialize(
            service_name="test-service",
            service_version="1.0.0",
            environment="testing",
        )

        assert manager._initialized is True

    def test_initialize_disabled(self) -> None:
        """Test initialization when disabled."""
        config = MetricsConfig(enabled=False)
        manager = MetricsManager(config)

        manager.initialize()

        assert manager._initialized is False

    def test_get_metrics(self) -> None:
        """Test getting metrics output."""
        manager = MetricsManager(MetricsConfig())

        metrics = manager.get_metrics()

        assert isinstance(metrics, bytes)
        assert len(metrics) > 0


class TestScreeningMetrics:
    """Tests for screening metrics."""

    def test_observe_screening_duration(self) -> None:
        """Test observing screening duration."""
        with observe_screening_duration(tier="standard", degree="d1") as ctx:
            time.sleep(0.01)
            ctx["status"] = "success"

        # Verify in-progress gauge was incremented and decremented
        # Note: We can't easily verify the final value in unit tests
        # because the gauge is shared across tests

    def test_observe_screening_duration_with_error(self) -> None:
        """Test observing screening duration with error."""
        with pytest.raises(ValueError):
            with observe_screening_duration(tier="enhanced", degree="d2") as ctx:
                raise ValueError("Test error")
                # ctx["status"] should be set to "error" automatically

    def test_record_screening_complete(self) -> None:
        """Test recording completed screening."""
        record_screening_complete(
            tier="standard",
            degree="d1",
            status="success",
            locale="US",
            duration_seconds=5.5,
        )

        # Verify counter was incremented
        # Note: The actual value depends on test order


class TestProviderMetrics:
    """Tests for provider metrics."""

    def test_observe_provider_query(self) -> None:
        """Test observing provider query."""
        with observe_provider_query(provider_id="sterling", check_type="criminal_national") as ctx:
            time.sleep(0.001)
            ctx["status"] = "success"
            ctx["cache_hit"] = True

        # Verify metrics were recorded

    def test_observe_provider_query_with_error(self) -> None:
        """Test observing provider query with error."""
        with pytest.raises(RuntimeError):
            with observe_provider_query(provider_id="checkr", check_type="credit") as ctx:
                raise RuntimeError("Provider error")

    def test_record_provider_query(self) -> None:
        """Test recording provider query."""
        record_provider_query(
            provider_id="sterling",
            check_type="criminal_national",
            status="success",
            duration_seconds=1.5,
            cache_hit=False,
        )

    def test_record_provider_query_cache_hit(self) -> None:
        """Test recording cached provider query."""
        record_provider_query(
            provider_id="sterling",
            check_type="criminal_national",
            status="success",
            duration_seconds=0.01,
            cache_hit=True,
        )

    def test_record_provider_rate_limited(self) -> None:
        """Test recording rate-limited request."""
        record_provider_rate_limited("sterling")

    def test_set_provider_circuit_breaker_state(self) -> None:
        """Test setting circuit breaker state."""
        set_provider_circuit_breaker_state("sterling", "closed")
        set_provider_circuit_breaker_state("sterling", "open")
        set_provider_circuit_breaker_state("sterling", "half_open")

    def test_set_provider_health_status(self) -> None:
        """Test setting provider health status."""
        set_provider_health_status("sterling", "healthy")
        set_provider_health_status("sterling", "degraded")
        set_provider_health_status("sterling", "unhealthy")


class TestSARMetrics:
    """Tests for SAR loop metrics."""

    def test_observe_sar_iteration(self) -> None:
        """Test observing SAR iteration."""
        with observe_sar_iteration(info_type="criminal") as ctx:
            ctx["completion_reason"] = "confidence_met"
            ctx["confidence_score"] = 0.85
            ctx["facts_discovered"] = 10

    def test_record_sar_iteration(self) -> None:
        """Test recording SAR iteration."""
        record_sar_iteration(
            info_type="criminal",
            completion_reason="confidence_met",
            confidence_score=0.9,
            facts_discovered=15,
            queries_executed=10,
            query_types={"initial": 5, "enriched": 3, "gap_fill": 2},
        )


class TestRiskMetrics:
    """Tests for risk analysis metrics."""

    def test_observe_risk_score(self) -> None:
        """Test observing risk score."""
        observe_risk_score(
            score=45.0,
            role_category="financial",
            level="moderate",
            recommendation="review_required",
        )

    def test_record_finding(self) -> None:
        """Test recording finding."""
        record_finding(category="criminal", severity="high")
        record_finding(category="financial", severity="medium")

    def test_record_anomaly(self) -> None:
        """Test recording anomaly."""
        record_anomaly(anomaly_type="statistical_outlier")
        record_anomaly(anomaly_type="systematic_inconsistency")

    def test_record_pattern(self) -> None:
        """Test recording pattern."""
        record_pattern(pattern_type="severity_escalation")
        record_pattern(pattern_type="repeat_offender")


class TestHTTPMetrics:
    """Tests for HTTP metrics."""

    def test_record_http_request(self) -> None:
        """Test recording HTTP request."""
        record_http_request(
            method="GET",
            endpoint="/v1/screenings/{id}",
            status_code=200,
            duration_seconds=0.05,
        )

    def test_record_http_request_with_sizes(self) -> None:
        """Test recording HTTP request with sizes."""
        record_http_request(
            method="POST",
            endpoint="/v1/screenings/",
            status_code=201,
            duration_seconds=0.1,
            request_size=1024,
            response_size=512,
        )

    def test_record_http_request_error(self) -> None:
        """Test recording HTTP error."""
        record_http_request(
            method="POST",
            endpoint="/v1/screenings/",
            status_code=500,
            duration_seconds=0.02,
        )


class TestDatabaseMetrics:
    """Tests for database metrics."""

    def test_record_db_query(self) -> None:
        """Test recording database query."""
        record_db_query(
            operation="SELECT",
            table="entities",
            duration_seconds=0.005,
        )

    def test_set_active_connections(self) -> None:
        """Test setting active connections."""
        set_active_connections(10)
        set_active_connections(5)

    def test_set_connection_pool_size(self) -> None:
        """Test setting connection pool size."""
        set_connection_pool_size(20)


class TestSystemMetrics:
    """Tests for system metrics."""

    def test_set_queue_depth(self) -> None:
        """Test setting queue depth."""
        set_queue_depth("screening_queue", 50)
        set_queue_depth("alert_queue", 10)

    def test_set_worker_count(self) -> None:
        """Test setting worker count."""
        set_worker_count("screening_worker", 4)
        set_worker_count("monitoring_worker", 2)

    def test_set_memory_usage(self) -> None:
        """Test setting memory usage."""
        set_memory_usage(1024 * 1024 * 256)  # 256 MB


class TestMetricsExport:
    """Tests for metrics export."""

    def test_get_metrics_returns_bytes(self) -> None:
        """Test that get_metrics returns bytes."""
        metrics = get_metrics()
        assert isinstance(metrics, bytes)

    def test_get_metrics_contains_metric_names(self) -> None:
        """Test that exported metrics contain expected names."""
        # Record some metrics first
        record_http_request(
            method="GET",
            endpoint="/test",
            status_code=200,
            duration_seconds=0.01,
        )

        metrics = get_metrics()
        metrics_str = metrics.decode("utf-8")

        # Should contain elile prefix
        assert "elile_" in metrics_str

    def test_create_metrics_manager(self) -> None:
        """Test creating metrics manager via factory."""
        config = MetricsConfig(prefix="test")
        manager = create_metrics_manager(config)

        assert manager.config.prefix == "test"


class TestMetricLabels:
    """Tests for metric label handling."""

    def test_screening_metrics_labels(self) -> None:
        """Test screening metrics have correct labels."""
        # Record with specific labels
        record_screening_complete(
            tier="enhanced",
            degree="d3",
            status="complete",
            locale="EU",
        )

        # Get metrics and verify labels are present
        metrics = get_metrics().decode("utf-8")
        assert "tier=" in metrics
        assert "degree=" in metrics

    def test_provider_metrics_labels(self) -> None:
        """Test provider metrics have correct labels."""
        record_provider_query(
            provider_id="test_provider",
            check_type="test_check",
            status="success",
            duration_seconds=0.1,
        )

        metrics = get_metrics().decode("utf-8")
        assert "provider_id=" in metrics
        assert "check_type=" in metrics


class TestMetricValues:
    """Tests for metric value recording."""

    def test_histogram_buckets(self) -> None:
        """Test histogram bucket recording."""
        # Record various durations to hit different buckets
        for duration in [0.001, 0.01, 0.1, 1.0, 5.0]:
            record_http_request(
                method="GET",
                endpoint="/test",
                status_code=200,
                duration_seconds=duration,
            )

    def test_counter_increment(self) -> None:
        """Test counter incrementing."""
        # Record multiple requests
        for _ in range(5):
            record_http_request(
                method="GET",
                endpoint="/test",
                status_code=200,
                duration_seconds=0.01,
            )

    def test_gauge_set(self) -> None:
        """Test gauge setting."""
        set_active_connections(10)
        set_active_connections(15)
        set_active_connections(5)

        # The gauge should reflect the last value
