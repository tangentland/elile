"""Provider health monitoring and circuit breaker.

This module provides health monitoring, circuit breaker pattern implementation,
and availability management for data providers.
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable

from pydantic import BaseModel, Field

from elile.core.logging import get_logger

from .types import ProviderHealth, ProviderStatus

logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Circuit tripped, requests fail fast
    HALF_OPEN = "half_open"  # Testing if provider recovered


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = Field(default=5, description="Failures before opening circuit")
    success_threshold: int = Field(default=3, description="Successes in half-open to close")
    timeout_seconds: float = Field(default=60.0, description="Time before trying half-open")
    half_open_max_calls: int = Field(default=3, description="Max test calls in half-open state")


class CircuitBreaker:
    """Circuit breaker for provider protection.

    Implements the circuit breaker pattern to prevent cascading failures
    and provide fail-fast behavior when a provider is unhealthy.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Provider is unhealthy, requests fail immediately
    - HALF_OPEN: Testing if provider recovered, limited requests allowed

    Usage:
        breaker = CircuitBreaker("provider_id")

        if breaker.can_execute():
            try:
                result = await provider.execute_check(...)
                breaker.record_success()
            except Exception as e:
                breaker.record_failure()
                raise
        else:
            raise CircuitOpenError("Provider circuit is open")
    """

    def __init__(
        self,
        provider_id: str,
        config: CircuitBreakerConfig | None = None,
    ):
        """Initialize circuit breaker.

        Args:
            provider_id: ID of the provider this breaker protects.
            config: Circuit breaker configuration.
        """
        self.provider_id = provider_id
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        self._check_timeout()
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN

    def can_execute(self) -> bool:
        """Check if a request can be executed.

        Returns:
            True if request should proceed, False if circuit is open.
        """
        state = self.state

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            return False

        # HALF_OPEN: allow limited test calls
        if self._half_open_calls < self.config.half_open_max_calls:
            return True

        return False

    def record_success(self) -> None:
        """Record a successful request.

        In HALF_OPEN state, enough successes will close the circuit.
        """
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            self._half_open_calls += 1

            if self._success_count >= self.config.success_threshold:
                self._close()
                logger.info(
                    "circuit_closed",
                    provider_id=self.provider_id,
                    success_count=self._success_count,
                )
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            if self._failure_count > 0:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request.

        Enough failures will open the circuit.
        """
        self._failure_count += 1
        self._last_failure_time = datetime.utcnow()

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open reopens circuit
            self._open()
            logger.warning(
                "circuit_reopened",
                provider_id=self.provider_id,
                failure_count=self._failure_count,
            )
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                self._open()
                logger.warning(
                    "circuit_opened",
                    provider_id=self.provider_id,
                    failure_count=self._failure_count,
                )

    def reset(self) -> None:
        """Reset circuit to closed state."""
        self._close()
        self._failure_count = 0
        logger.info("circuit_reset", provider_id=self.provider_id)

    def force_open(self) -> None:
        """Force circuit to open state (for maintenance, etc.)."""
        self._open()
        logger.info("circuit_force_opened", provider_id=self.provider_id)

    def _check_timeout(self) -> None:
        """Check if timeout has elapsed and transition to half-open."""
        if self._state != CircuitState.OPEN:
            return

        if self._last_failure_time is None:
            return

        elapsed = datetime.utcnow() - self._last_failure_time
        if elapsed.total_seconds() >= self.config.timeout_seconds:
            self._half_open()
            logger.info(
                "circuit_half_open",
                provider_id=self.provider_id,
                elapsed_seconds=elapsed.total_seconds(),
            )

    def _open(self) -> None:
        """Transition to open state."""
        self._state = CircuitState.OPEN
        self._success_count = 0
        self._half_open_calls = 0

    def _half_open(self) -> None:
        """Transition to half-open state."""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._half_open_calls = 0

    def _close(self) -> None:
        """Transition to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = None

    def get_status(self) -> dict:
        """Get circuit breaker status.

        Returns:
            Dict with current state and metrics.
        """
        return {
            "provider_id": self.provider_id,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": (
                self._last_failure_time.isoformat() if self._last_failure_time else None
            ),
        }


class CircuitOpenError(Exception):
    """Raised when a request is made with an open circuit."""

    def __init__(self, provider_id: str):
        super().__init__(f"Circuit is open for provider: {provider_id}")
        self.provider_id = provider_id


class ProviderMetrics(BaseModel):
    """Metrics for a provider's performance and reliability."""

    provider_id: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: int = 0
    last_request_time: datetime | None = None
    last_success_time: datetime | None = None
    last_failure_time: datetime | None = None
    last_error: str | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 1.0  # No requests yet, assume healthy
        return self.successful_requests / self.total_requests

    @property
    def average_latency_ms(self) -> float:
        """Calculate average latency in milliseconds."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    def record_success(self, latency_ms: int) -> None:
        """Record a successful request.

        Args:
            latency_ms: Request latency in milliseconds.
        """
        now = datetime.utcnow()
        self.total_requests += 1
        self.successful_requests += 1
        self.total_latency_ms += latency_ms
        self.last_request_time = now
        self.last_success_time = now

    def record_failure(self, error: str | None = None) -> None:
        """Record a failed request.

        Args:
            error: Error message for the failure.
        """
        now = datetime.utcnow()
        self.total_requests += 1
        self.failed_requests += 1
        self.last_request_time = now
        self.last_failure_time = now
        self.last_error = error


class HealthMonitorConfig(BaseModel):
    """Configuration for health monitor behavior."""

    check_interval_seconds: float = Field(default=60.0, description="Interval between checks")
    unhealthy_threshold: int = Field(default=3, description="Failed checks before unhealthy")
    healthy_threshold: int = Field(default=2, description="Successful checks before healthy")
    degraded_latency_ms: int = Field(default=5000, description="Latency threshold for degraded")


class HealthMonitor:
    """Monitor provider health and update status.

    Performs periodic health checks and maintains provider health status.
    Integrates with ProviderRegistry to update health cache.

    Usage:
        monitor = HealthMonitor(registry)

        # Start monitoring (runs in background)
        await monitor.start()

        # Manual health check
        health = await monitor.check_provider("provider_id")

        # Stop monitoring
        await monitor.stop()
    """

    def __init__(
        self,
        registry: "ProviderRegistry",  # type: ignore[name-defined]
        config: HealthMonitorConfig | None = None,
    ):
        """Initialize health monitor.

        Args:
            registry: Provider registry to monitor.
            config: Health monitor configuration.
        """
        from .registry import ProviderRegistry

        self._registry: ProviderRegistry = registry
        self.config = config or HealthMonitorConfig()

        self._running = False
        self._task: asyncio.Task | None = None
        self._consecutive_failures: dict[str, int] = {}
        self._consecutive_successes: dict[str, int] = {}

    @property
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running

    async def start(self) -> None:
        """Start the health monitor background task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("health_monitor_started", interval=self.config.check_interval_seconds)

    async def stop(self) -> None:
        """Stop the health monitor background task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("health_monitor_stopped")

    async def check_provider(self, provider_id: str) -> ProviderHealth:
        """Check health of a specific provider.

        Args:
            provider_id: ID of provider to check.

        Returns:
            Updated health status.
        """
        provider = self._registry.get_provider(provider_id)

        start_time = datetime.utcnow()
        try:
            health = await provider.health_check()
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Update health with latency
            health.latency_ms = latency_ms

            # Track consecutive successes
            self._consecutive_failures[provider_id] = 0
            self._consecutive_successes[provider_id] = (
                self._consecutive_successes.get(provider_id, 0) + 1
            )

            # Check for degraded status based on latency
            if (
                health.status == ProviderStatus.HEALTHY
                and latency_ms > self.config.degraded_latency_ms
            ):
                health.status = ProviderStatus.DEGRADED

            # Update success rate
            health.success_rate_24h = self._calculate_success_rate(provider_id)

            logger.debug(
                "health_check_success",
                provider_id=provider_id,
                latency_ms=latency_ms,
                status=health.status.value,
            )

        except Exception as e:
            # Track consecutive failures
            self._consecutive_successes[provider_id] = 0
            failures = self._consecutive_failures.get(provider_id, 0) + 1
            self._consecutive_failures[provider_id] = failures

            # Determine status based on failure count
            if failures >= self.config.unhealthy_threshold:
                status = ProviderStatus.UNHEALTHY
            else:
                status = ProviderStatus.DEGRADED

            health = ProviderHealth(
                provider_id=provider_id,
                status=status,
                last_check=datetime.utcnow(),
                error_message=str(e),
                consecutive_failures=failures,
                success_rate_24h=self._calculate_success_rate(provider_id),
            )

            logger.warning(
                "health_check_failed",
                provider_id=provider_id,
                error=str(e),
                consecutive_failures=failures,
            )

        # Update registry health cache
        self._registry.update_provider_health(health)

        return health

    async def check_all(self) -> dict[str, ProviderHealth]:
        """Check health of all registered providers.

        Returns:
            Dict mapping provider_id to health status.
        """
        providers = self._registry.list_providers()
        results = {}

        # Run health checks concurrently
        tasks = [self.check_provider(p.provider_id) for p in providers]
        if tasks:
            health_results = await asyncio.gather(*tasks, return_exceptions=True)

            for provider, result in zip(providers, health_results):
                if isinstance(result, Exception):
                    results[provider.provider_id] = ProviderHealth(
                        provider_id=provider.provider_id,
                        status=ProviderStatus.UNHEALTHY,
                        last_check=datetime.utcnow(),
                        error_message=str(result),
                    )
                else:
                    results[provider.provider_id] = result

        return results

    async def _monitor_loop(self) -> None:
        """Background loop for periodic health checks."""
        while self._running:
            try:
                await self.check_all()
            except Exception as e:
                logger.error("health_monitor_error", error=str(e))

            await asyncio.sleep(self.config.check_interval_seconds)

    def _calculate_success_rate(self, provider_id: str) -> float:
        """Calculate success rate for a provider.

        Args:
            provider_id: Provider to calculate rate for.

        Returns:
            Success rate (0.0 to 1.0).
        """
        failures = self._consecutive_failures.get(provider_id, 0)
        successes = self._consecutive_successes.get(provider_id, 0)
        total = failures + successes

        if total == 0:
            return 1.0

        return successes / total


class CircuitBreakerRegistry:
    """Registry for managing circuit breakers across providers.

    Provides centralized access to circuit breakers and ensures
    one breaker per provider.
    """

    def __init__(self, default_config: CircuitBreakerConfig | None = None):
        """Initialize circuit breaker registry.

        Args:
            default_config: Default configuration for new breakers.
        """
        self._breakers: dict[str, CircuitBreaker] = {}
        self._default_config = default_config or CircuitBreakerConfig()
        self._metrics: dict[str, ProviderMetrics] = {}

    def get_breaker(
        self,
        provider_id: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """Get or create circuit breaker for a provider.

        Args:
            provider_id: Provider ID.
            config: Optional custom config (uses default if not provided).

        Returns:
            CircuitBreaker for the provider.
        """
        if provider_id not in self._breakers:
            self._breakers[provider_id] = CircuitBreaker(
                provider_id,
                config or self._default_config,
            )
            self._metrics[provider_id] = ProviderMetrics(provider_id=provider_id)

        return self._breakers[provider_id]

    def get_metrics(self, provider_id: str) -> ProviderMetrics:
        """Get metrics for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            ProviderMetrics for the provider.
        """
        if provider_id not in self._metrics:
            self._metrics[provider_id] = ProviderMetrics(provider_id=provider_id)
        return self._metrics[provider_id]

    def record_success(self, provider_id: str, latency_ms: int) -> None:
        """Record successful request for a provider.

        Args:
            provider_id: Provider ID.
            latency_ms: Request latency.
        """
        breaker = self.get_breaker(provider_id)
        breaker.record_success()

        metrics = self.get_metrics(provider_id)
        metrics.record_success(latency_ms)

    def record_failure(self, provider_id: str, error: str | None = None) -> None:
        """Record failed request for a provider.

        Args:
            provider_id: Provider ID.
            error: Error message.
        """
        breaker = self.get_breaker(provider_id)
        breaker.record_failure()

        metrics = self.get_metrics(provider_id)
        metrics.record_failure(error)

    def can_execute(self, provider_id: str) -> bool:
        """Check if requests can be made to a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            True if circuit is closed or half-open with capacity.
        """
        breaker = self.get_breaker(provider_id)
        return breaker.can_execute()

    def get_status(self, provider_id: str) -> dict:
        """Get combined status for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            Dict with circuit breaker and metrics status.
        """
        breaker = self.get_breaker(provider_id)
        metrics = self.get_metrics(provider_id)

        return {
            "circuit_breaker": breaker.get_status(),
            "metrics": {
                "success_rate": metrics.success_rate,
                "average_latency_ms": metrics.average_latency_ms,
                "total_requests": metrics.total_requests,
                "failed_requests": metrics.failed_requests,
            },
        }

    def get_all_status(self) -> dict[str, dict]:
        """Get status for all tracked providers.

        Returns:
            Dict mapping provider_id to status.
        """
        return {pid: self.get_status(pid) for pid in self._breakers.keys()}

    def reset(self, provider_id: str) -> None:
        """Reset circuit breaker and metrics for a provider.

        Args:
            provider_id: Provider ID.
        """
        if provider_id in self._breakers:
            self._breakers[provider_id].reset()
        if provider_id in self._metrics:
            self._metrics[provider_id] = ProviderMetrics(provider_id=provider_id)

    def reset_all(self) -> None:
        """Reset all circuit breakers and metrics."""
        for provider_id in list(self._breakers.keys()):
            self.reset(provider_id)
