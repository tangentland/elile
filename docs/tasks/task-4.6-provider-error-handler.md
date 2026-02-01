# Task 4.6: Provider Error Handler

## Overview

Implement robust error handling for provider API failures with retry logic, circuit breakers, and fallback strategies. See [06-data-sources.md](../architecture/06-data-sources.md#error-handling) for error handling requirements.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 4.1: Provider Gateway
- Task 4.3: Rate Limiter

## Implementation Checklist

- [ ] Define provider error taxonomy
- [ ] Implement exponential backoff retry
- [ ] Build circuit breaker pattern
- [ ] Add provider fallback logic
- [ ] Create error logging and metrics
- [ ] Implement partial failure handling
- [ ] Write error handler tests

## Key Implementation

```python
# src/elile/providers/errors.py
from enum import Enum

class ErrorSeverity(str, Enum):
    """Error severity levels."""
    TRANSIENT = "transient"  # Retry immediately
    TEMPORARY = "temporary"  # Retry with backoff
    PERMANENT = "permanent"  # Do not retry
    FATAL = "fatal"  # Stop entire operation

class ProviderError(Exception):
    """Base provider error."""
    severity: ErrorSeverity = ErrorSeverity.TEMPORARY

    def __init__(self, provider_id: str, message: str, severity: ErrorSeverity = None):
        self.provider_id = provider_id
        self.severity = severity or self.severity
        super().__init__(f"[{provider_id}] {message}")

class RateLimitError(ProviderError):
    """Rate limit exceeded."""
    severity = ErrorSeverity.TEMPORARY

    def __init__(self, provider_id: str, retry_after: int):
        self.retry_after = retry_after
        super().__init__(provider_id, f"Rate limited, retry after {retry_after}s")

class AuthenticationError(ProviderError):
    """Authentication failed."""
    severity = ErrorSeverity.FATAL

class TimeoutError(ProviderError):
    """Request timeout."""
    severity = ErrorSeverity.TRANSIENT

class ServiceUnavailableError(ProviderError):
    """Provider service unavailable."""
    severity = ErrorSeverity.TEMPORARY

class InvalidRequestError(ProviderError):
    """Invalid request parameters."""
    severity = ErrorSeverity.PERMANENT

class ProviderDataError(ProviderError):
    """Invalid data from provider."""
    severity = ErrorSeverity.TEMPORARY

# src/elile/providers/retry.py
import asyncio
from typing import TypeVar, Callable

T = TypeVar("T")

class RetryConfig(BaseModel):
    """Retry configuration."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

class RetryHandler:
    """Handles retry logic with exponential backoff."""

    def __init__(self, config: RetryConfig = RetryConfig()):
        self.config = config

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute function with retry logic."""
        attempt = 0
        last_error = None

        while attempt < self.config.max_attempts:
            try:
                return await func(*args, **kwargs)

            except ProviderError as e:
                last_error = e
                attempt += 1

                # Don't retry permanent or fatal errors
                if e.severity in (ErrorSeverity.PERMANENT, ErrorSeverity.FATAL):
                    raise

                # Calculate backoff delay
                if e.severity == ErrorSeverity.TRANSIENT:
                    delay = 0.1  # Quick retry
                elif isinstance(e, RateLimitError):
                    delay = e.retry_after
                else:
                    delay = self._calculate_backoff(attempt)

                logger.info(
                    f"Retry attempt {attempt}/{self.config.max_attempts} after {delay}s",
                    extra={"error": str(e), "provider_id": e.provider_id}
                )

                await asyncio.sleep(delay)

        # All retries exhausted
        raise last_error

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = self.config.initial_delay * (self.config.exponential_base ** (attempt - 1))
        delay = min(delay, self.config.max_delay)

        # Add jitter to prevent thundering herd
        if self.config.jitter:
            import random
            delay *= (0.5 + random.random())

        return delay

# src/elile/providers/circuit_breaker.py
from datetime import datetime, timedelta

class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    half_open_max_calls: int = 3

class CircuitBreaker:
    """Circuit breaker for provider calls."""

    def __init__(self, provider_id: str, config: CircuitBreakerConfig):
        self.provider_id = provider_id
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.half_open_calls = 0

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function through circuit breaker."""
        # Check if circuit should transition
        self._check_state_transition()

        # Reject if circuit is open
        if self.state == CircuitState.OPEN:
            raise ServiceUnavailableError(
                self.provider_id,
                "Circuit breaker OPEN"
            )

        # Limit calls in half-open state
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                raise ServiceUnavailableError(
                    self.provider_id,
                    "Circuit breaker HALF_OPEN, max test calls reached"
                )
            self.half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result

        except ProviderError as e:
            self._on_failure()
            raise

    def _check_state_transition(self):
        """Check if circuit state should transition."""
        if self.state == CircuitState.OPEN:
            if self.last_failure_time:
                elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if elapsed >= self.config.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0

    def _on_success(self):
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            # Recovery successful
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.half_open_calls = 0

        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            # Failed recovery, reopen circuit
            self.state = CircuitState.OPEN

        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN

class ProviderErrorHandler:
    """Centralized error handling for providers."""

    def __init__(self):
        self.retry_handler = RetryHandler()
        self.circuit_breakers: dict[str, CircuitBreaker] = {}

    def get_circuit_breaker(self, provider_id: str) -> CircuitBreaker:
        """Get or create circuit breaker for provider."""
        if provider_id not in self.circuit_breakers:
            self.circuit_breakers[provider_id] = CircuitBreaker(
                provider_id,
                CircuitBreakerConfig()
            )
        return self.circuit_breakers[provider_id]

    async def execute(
        self,
        provider_id: str,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute provider call with error handling."""
        circuit_breaker = self.get_circuit_breaker(provider_id)

        return await self.retry_handler.execute(
            circuit_breaker.call,
            func,
            *args,
            **kwargs
        )

# Global error handler
error_handler = ProviderErrorHandler()
```

## Testing Requirements

### Unit Tests
- Error severity classification
- Exponential backoff calculation
- Circuit breaker state transitions
- Retry count limits
- Jitter randomization

### Integration Tests
- Retry on transient failures
- Circuit breaker opening on repeated failures
- Circuit breaker recovery
- Rate limit retry handling

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] Error taxonomy defined
- [ ] Retry handler with exponential backoff works
- [ ] Circuit breaker prevents cascading failures
- [ ] Error severity routing correct
- [ ] Jitter added to backoff delays
- [ ] Unit tests pass with 90%+ coverage

## Deliverables

- `src/elile/providers/errors.py`
- `src/elile/providers/retry.py`
- `src/elile/providers/circuit_breaker.py`
- `tests/unit/test_error_handler.py`

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md#error-handling)
- Dependencies: Task 4.1 (provider gateway), Task 4.3 (rate limiter)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
