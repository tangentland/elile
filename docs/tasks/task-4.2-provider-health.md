# Task 4.2: Provider Health Monitor

## Overview

Implement provider health monitoring with periodic checks, error rate tracking, circuit breaker pattern, and automatic failover to backup providers.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 4.1: Provider Gateway

## Implementation Checklist

- [ ] Create ProviderHealthMonitor service
- [ ] Implement periodic health checks
- [ ] Build error rate calculation
- [ ] Add circuit breaker pattern
- [ ] Create provider status dashboard data
- [ ] Write health monitor tests

## Key Implementation

```python
# src/elile/providers/health_monitor.py
from collections import deque
from datetime import datetime, timedelta

class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Too many failures, block requests
    HALF_OPEN = "half_open"  # Testing if provider recovered

class ProviderHealthMonitor:
    """Monitor provider health and implement circuit breaker."""

    def __init__(self, provider_registry: ProviderRegistry):
        self.registry = provider_registry
        self.health_status: dict[str, ProviderHealthStatus] = {}
        self.circuit_states: dict[str, CircuitState] = {}
        self.recent_calls: dict[str, deque] = {}  # Sliding window of recent calls

        # Circuit breaker config
        self.failure_threshold = 5  # Failures to open circuit
        self.success_threshold = 2  # Successes to close circuit
        self.timeout_seconds = 60   # How long circuit stays open

    async def check_health_all(self):
        """Run health check on all providers (periodic task)."""
        for provider_id, provider in self.registry._providers.items():
            try:
                status = await provider.health_check()
                self.health_status[provider_id] = status

                # Update circuit state based on health
                await self._update_circuit_state(provider_id, status)

            except Exception as e:
                logger.error(f"Health check failed for {provider_id}: {e}")
                self.health_status[provider_id] = ProviderHealthStatus(
                    provider_id=provider_id,
                    available=False,
                    last_check=datetime.utcnow(),
                    response_time_ms=None,
                    error_rate=1.0,
                    consecutive_failures=self.health_status.get(
                        provider_id,
                        ProviderHealthStatus(provider_id=provider_id, available=False, last_check=datetime.utcnow(), error_rate=0.0, consecutive_failures=0)
                    ).consecutive_failures + 1
                )

    async def record_call_result(
        self,
        provider_id: str,
        success: bool,
        response_time_ms: float
    ):
        """Record result of provider call for health tracking."""
        # Initialize tracking if needed
        if provider_id not in self.recent_calls:
            self.recent_calls[provider_id] = deque(maxlen=100)

        # Record call
        self.recent_calls[provider_id].append({
            "success": success,
            "timestamp": datetime.utcnow(),
            "response_time_ms": response_time_ms
        })

        # Update circuit state
        current_state = self.circuit_states.get(provider_id, CircuitState.CLOSED)

        if not success:
            consecutive_failures = self._count_consecutive_failures(provider_id)
            if consecutive_failures >= self.failure_threshold:
                self.circuit_states[provider_id] = CircuitState.OPEN
                logger.warning(f"Circuit opened for {provider_id}")
        else:
            if current_state == CircuitState.HALF_OPEN:
                consecutive_successes = self._count_consecutive_successes(provider_id)
                if consecutive_successes >= self.success_threshold:
                    self.circuit_states[provider_id] = CircuitState.CLOSED
                    logger.info(f"Circuit closed for {provider_id}")

    def is_provider_available(self, provider_id: str) -> bool:
        """Check if provider is available (circuit closed)."""
        state = self.circuit_states.get(provider_id, CircuitState.CLOSED)

        if state == CircuitState.OPEN:
            # Check if timeout expired (move to half-open)
            status = self.health_status.get(provider_id)
            if status and (datetime.utcnow() - status.last_check).seconds > self.timeout_seconds:
                self.circuit_states[provider_id] = CircuitState.HALF_OPEN
                return True  # Allow test request

            return False  # Circuit still open

        return True  # CLOSED or HALF_OPEN

    def _count_consecutive_failures(self, provider_id: str) -> int:
        """Count consecutive failures from end of call history."""
        calls = self.recent_calls.get(provider_id, deque())
        count = 0
        for call in reversed(calls):
            if call["success"]:
                break
            count += 1
        return count

    def _count_consecutive_successes(self, provider_id: str) -> int:
        """Count consecutive successes from end of call history."""
        calls = self.recent_calls.get(provider_id, deque())
        count = 0
        for call in reversed(calls):
            if not call["success"]:
                break
            count += 1
        return count

    async def _update_circuit_state(
        self,
        provider_id: str,
        status: ProviderHealthStatus
    ):
        """Update circuit breaker state based on health status."""
        if not status.available:
            self.circuit_states[provider_id] = CircuitState.OPEN
        elif status.error_rate < 0.1:  # Less than 10% errors
            self.circuit_states[provider_id] = CircuitState.CLOSED
```

## Testing Requirements

### Unit Tests
- Circuit breaker state transitions
- Consecutive failure counting
- Health check recording
- is_provider_available() logic

### Integration Tests
- Circuit opens after failures
- Circuit closes after successes
- Timeout-based half-open transition

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] Health monitor tracks provider status
- [ ] Circuit breaker opens after threshold failures
- [ ] Circuit closes after threshold successes
- [ ] Half-open state allows test requests
- [ ] is_provider_available() respects circuit state
- [ ] Periodic health checks run

## Deliverables

- `src/elile/providers/health_monitor.py`
- `tests/unit/test_provider_health.py`

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md) - Provider health
- Pattern: Circuit Breaker pattern

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
