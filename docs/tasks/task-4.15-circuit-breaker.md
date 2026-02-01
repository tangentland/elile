# Task 4.15: Provider Circuit Breaker

**Priority**: P1
**Phase**: 4 - Data Providers
**Estimated Effort**: 2 days
**Dependencies**: Task 4.1 (Provider Interface)

## Context

Implement circuit breaker pattern for data provider calls to handle failures gracefully, prevent cascade failures, and support automatic recovery.

**Architecture Reference**: [10-platform.md](../docs/architecture/10-platform.md) - Resilience

## Objectives

1. Implement circuit breaker pattern
2. Add failure threshold configuration
3. Support automatic recovery attempts
4. Create provider health tracking
5. Enable fallback strategies

## Technical Approach

```python
# src/elile/providers/resilience/circuit_breaker.py
class CircuitBreaker:
    """Circuit breaker for provider calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker."""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError()

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise
```

## Implementation Checklist

- [ ] Implement circuit breaker
- [ ] Add state management
- [ ] Create health dashboard
- [ ] Test failure scenarios

## Success Criteria

- [ ] Prevents cascade failures
- [ ] Auto-recovery works
- [ ] Health tracking accurate
