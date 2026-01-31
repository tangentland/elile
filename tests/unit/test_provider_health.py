"""Unit tests for Provider Health & Circuit Breaker.

Tests the CircuitBreaker, HealthMonitor, and related classes.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from elile.providers import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitOpenError,
    CircuitState,
    HealthMonitor,
    HealthMonitorConfig,
    ProviderHealth,
    ProviderMetrics,
    ProviderStatus,
)


# =============================================================================
# CircuitBreaker Tests
# =============================================================================


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig model."""

    def test_defaults(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.timeout_seconds == 60.0
        assert config.half_open_max_calls == 3

    def test_custom_values(self):
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=30.0,
        )
        assert config.failure_threshold == 3
        assert config.success_threshold == 2


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.fixture
    def breaker(self):
        """Create a circuit breaker with test config."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=1.0,
        )
        return CircuitBreaker("test_provider", config)

    def test_initial_state_closed(self, breaker):
        """Test initial state is closed."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed is True
        assert breaker.can_execute() is True

    def test_record_success_in_closed(self, breaker):
        """Test recording success in closed state."""
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_failure_opens_circuit(self, breaker):
        """Test circuit opens after threshold failures."""
        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open is True
        assert breaker.can_execute() is False

    def test_success_resets_failure_count(self, breaker):
        """Test success resets failure count."""
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()  # Should reset

        # Now need 3 more failures to open
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

    def test_timeout_transitions_to_half_open(self, breaker):
        """Test timeout transitions from open to half-open."""
        # Open the circuit
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Set last failure time in the past
        breaker._last_failure_time = datetime.utcnow() - timedelta(seconds=2)

        # Checking state should trigger transition
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.is_half_open is True

    def test_half_open_allows_limited_calls(self, breaker):
        """Test half-open state allows limited test calls."""
        breaker._state = CircuitState.HALF_OPEN
        breaker._half_open_calls = 0

        # Should allow 3 calls (half_open_max_calls = 3)
        assert breaker.can_execute() is True
        breaker._half_open_calls = 1
        assert breaker.can_execute() is True
        breaker._half_open_calls = 2
        assert breaker.can_execute() is True
        breaker._half_open_calls = 3
        assert breaker.can_execute() is False

    def test_success_in_half_open_closes_circuit(self, breaker):
        """Test successful requests in half-open close the circuit."""
        breaker._state = CircuitState.HALF_OPEN

        breaker.record_success()
        assert breaker.state == CircuitState.HALF_OPEN

        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_failure_in_half_open_reopens(self, breaker):
        """Test failure in half-open reopens circuit."""
        breaker._state = CircuitState.HALF_OPEN

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_reset(self, breaker):
        """Test reset returns to closed state."""
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0

    def test_force_open(self, breaker):
        """Test force open transitions to open state."""
        assert breaker.state == CircuitState.CLOSED
        breaker.force_open()
        assert breaker.state == CircuitState.OPEN

    def test_get_status(self, breaker):
        """Test get_status returns correct info."""
        breaker.record_failure()
        status = breaker.get_status()

        assert status["provider_id"] == "test_provider"
        assert status["state"] == CircuitState.CLOSED.value
        assert status["failure_count"] == 1


class TestCircuitOpenError:
    """Tests for CircuitOpenError exception."""

    def test_error_message(self):
        """Test error message format."""
        error = CircuitOpenError("test_provider")
        assert "test_provider" in str(error)
        assert error.provider_id == "test_provider"


# =============================================================================
# ProviderMetrics Tests
# =============================================================================


class TestProviderMetrics:
    """Tests for ProviderMetrics model."""

    @pytest.fixture
    def metrics(self):
        """Create empty metrics."""
        return ProviderMetrics(provider_id="test")

    def test_initial_values(self, metrics):
        """Test initial metric values."""
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.success_rate == 1.0  # No requests = assume healthy
        assert metrics.average_latency_ms == 0.0

    def test_record_success(self, metrics):
        """Test recording successful request."""
        metrics.record_success(100)
        metrics.record_success(200)

        assert metrics.total_requests == 2
        assert metrics.successful_requests == 2
        assert metrics.failed_requests == 0
        assert metrics.total_latency_ms == 300
        assert metrics.average_latency_ms == 150.0
        assert metrics.success_rate == 1.0

    def test_record_failure(self, metrics):
        """Test recording failed request."""
        metrics.record_failure("Connection timeout")

        assert metrics.total_requests == 1
        assert metrics.failed_requests == 1
        assert metrics.last_error == "Connection timeout"
        assert metrics.success_rate == 0.0

    def test_mixed_requests(self, metrics):
        """Test mixed success and failure."""
        metrics.record_success(100)
        metrics.record_success(100)
        metrics.record_failure()

        assert metrics.total_requests == 3
        assert metrics.successful_requests == 2
        assert metrics.failed_requests == 1
        assert metrics.success_rate == pytest.approx(0.666, rel=0.01)


# =============================================================================
# CircuitBreakerRegistry Tests
# =============================================================================


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create circuit breaker registry."""
        return CircuitBreakerRegistry()

    def test_get_breaker_creates_new(self, registry):
        """Test getting breaker creates new one."""
        breaker = registry.get_breaker("provider1")
        assert isinstance(breaker, CircuitBreaker)
        assert breaker.provider_id == "provider1"

    def test_get_breaker_returns_same(self, registry):
        """Test getting breaker returns same instance."""
        breaker1 = registry.get_breaker("provider1")
        breaker2 = registry.get_breaker("provider1")
        assert breaker1 is breaker2

    def test_get_metrics(self, registry):
        """Test getting metrics."""
        metrics = registry.get_metrics("provider1")
        assert isinstance(metrics, ProviderMetrics)
        assert metrics.provider_id == "provider1"

    def test_record_success(self, registry):
        """Test recording success updates both breaker and metrics."""
        registry.record_success("provider1", 100)

        metrics = registry.get_metrics("provider1")
        assert metrics.successful_requests == 1
        assert metrics.total_latency_ms == 100

    def test_record_failure(self, registry):
        """Test recording failure updates both breaker and metrics."""
        registry.record_failure("provider1", "Error")

        metrics = registry.get_metrics("provider1")
        assert metrics.failed_requests == 1
        assert metrics.last_error == "Error"

    def test_can_execute(self, registry):
        """Test can_execute checks circuit state."""
        assert registry.can_execute("provider1") is True

        # Get breaker and configure it
        breaker = registry.get_breaker("provider1")
        breaker.config = CircuitBreakerConfig(failure_threshold=2)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        assert registry.can_execute("provider1") is False

    def test_get_status(self, registry):
        """Test get_status returns combined info."""
        registry.record_success("provider1", 100)
        status = registry.get_status("provider1")

        assert "circuit_breaker" in status
        assert "metrics" in status
        assert status["metrics"]["total_requests"] == 1

    def test_get_all_status(self, registry):
        """Test get_all_status returns all providers."""
        registry.record_success("provider1", 100)
        registry.record_success("provider2", 200)

        all_status = registry.get_all_status()
        assert "provider1" in all_status
        assert "provider2" in all_status

    def test_reset(self, registry):
        """Test reset clears breaker and metrics."""
        registry.record_failure("provider1", "Error")
        registry.reset("provider1")

        metrics = registry.get_metrics("provider1")
        assert metrics.failed_requests == 0

    def test_reset_all(self, registry):
        """Test reset_all clears all providers."""
        registry.record_failure("provider1", "Error")
        registry.record_failure("provider2", "Error")
        registry.reset_all()

        assert registry.get_metrics("provider1").failed_requests == 0
        assert registry.get_metrics("provider2").failed_requests == 0


# =============================================================================
# HealthMonitor Tests
# =============================================================================


class TestHealthMonitorConfig:
    """Tests for HealthMonitorConfig model."""

    def test_defaults(self):
        """Test default configuration values."""
        config = HealthMonitorConfig()
        assert config.check_interval_seconds == 60.0
        assert config.unhealthy_threshold == 3
        assert config.healthy_threshold == 2
        assert config.degraded_latency_ms == 5000


class TestHealthMonitor:
    """Tests for HealthMonitor class."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock provider registry."""
        registry = MagicMock()
        registry.list_providers.return_value = []
        return registry

    @pytest.fixture
    def monitor(self, mock_registry):
        """Create health monitor."""
        config = HealthMonitorConfig(check_interval_seconds=0.1)
        return HealthMonitor(mock_registry, config)

    def test_init(self, monitor, mock_registry):
        """Test initialization."""
        assert monitor._registry is mock_registry
        assert monitor.is_running is False

    @pytest.mark.asyncio
    async def test_start_stop(self, monitor):
        """Test start and stop."""
        await monitor.start()
        assert monitor.is_running is True

        await monitor.stop()
        assert monitor.is_running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self, monitor):
        """Test starting twice is safe."""
        await monitor.start()
        await monitor.start()  # Should be idempotent
        assert monitor.is_running is True

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_check_provider_success(self, mock_registry):
        """Test checking a healthy provider."""
        # Create mock provider
        mock_provider = MagicMock()
        mock_provider.provider_id = "test"
        mock_provider.health_check = AsyncMock(
            return_value=ProviderHealth(
                provider_id="test",
                status=ProviderStatus.HEALTHY,
                last_check=datetime.utcnow(),
            )
        )

        mock_registry.get_provider.return_value = mock_provider
        mock_registry.update_provider_health = MagicMock()

        monitor = HealthMonitor(mock_registry)
        health = await monitor.check_provider("test")

        assert health.status == ProviderStatus.HEALTHY
        assert health.latency_ms is not None
        mock_registry.update_provider_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_provider_failure(self, mock_registry):
        """Test checking a failing provider."""
        mock_provider = MagicMock()
        mock_provider.provider_id = "test"
        mock_provider.health_check = AsyncMock(side_effect=Exception("Connection failed"))

        mock_registry.get_provider.return_value = mock_provider
        mock_registry.update_provider_health = MagicMock()

        monitor = HealthMonitor(mock_registry, HealthMonitorConfig(unhealthy_threshold=2))
        health = await monitor.check_provider("test")

        assert health.status == ProviderStatus.DEGRADED
        assert "Connection failed" in health.error_message

    @pytest.mark.asyncio
    async def test_check_provider_unhealthy_after_threshold(self, mock_registry):
        """Test provider becomes unhealthy after threshold failures."""
        mock_provider = MagicMock()
        mock_provider.provider_id = "test"
        mock_provider.health_check = AsyncMock(side_effect=Exception("Failed"))

        mock_registry.get_provider.return_value = mock_provider
        mock_registry.update_provider_health = MagicMock()

        config = HealthMonitorConfig(unhealthy_threshold=2)
        monitor = HealthMonitor(mock_registry, config)

        # First failure - degraded
        health = await monitor.check_provider("test")
        assert health.status == ProviderStatus.DEGRADED

        # Second failure - unhealthy
        health = await monitor.check_provider("test")
        assert health.status == ProviderStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_provider_degraded_latency(self, mock_registry):
        """Test provider is degraded when latency is high."""
        async def slow_health_check():
            await asyncio.sleep(0.1)  # Simulate slow response
            return ProviderHealth(
                provider_id="test",
                status=ProviderStatus.HEALTHY,
                last_check=datetime.utcnow(),
            )

        mock_provider = MagicMock()
        mock_provider.provider_id = "test"
        mock_provider.health_check = slow_health_check

        mock_registry.get_provider.return_value = mock_provider
        mock_registry.update_provider_health = MagicMock()

        # Set low degraded threshold
        config = HealthMonitorConfig(degraded_latency_ms=50)
        monitor = HealthMonitor(mock_registry, config)

        health = await monitor.check_provider("test")
        assert health.status == ProviderStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_check_all(self, mock_registry):
        """Test checking all providers."""
        mock_provider1 = MagicMock()
        mock_provider1.provider_id = "p1"
        mock_provider1.health_check = AsyncMock(
            return_value=ProviderHealth(
                provider_id="p1",
                status=ProviderStatus.HEALTHY,
                last_check=datetime.utcnow(),
            )
        )

        mock_provider2 = MagicMock()
        mock_provider2.provider_id = "p2"
        mock_provider2.health_check = AsyncMock(
            return_value=ProviderHealth(
                provider_id="p2",
                status=ProviderStatus.HEALTHY,
                last_check=datetime.utcnow(),
            )
        )

        mock_registry.list_providers.return_value = [mock_provider1, mock_provider2]
        mock_registry.get_provider.side_effect = lambda pid: (
            mock_provider1 if pid == "p1" else mock_provider2
        )
        mock_registry.update_provider_health = MagicMock()

        monitor = HealthMonitor(mock_registry)
        results = await monitor.check_all()

        assert "p1" in results
        assert "p2" in results
        assert results["p1"].status == ProviderStatus.HEALTHY
        assert results["p2"].status == ProviderStatus.HEALTHY
