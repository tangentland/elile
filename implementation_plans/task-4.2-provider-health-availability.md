# Task 4.2: Provider Health & Availability

## Overview
Implement provider health monitoring and circuit breaker pattern to ensure reliable data acquisition with graceful degradation when providers become unavailable.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-31
**Dependencies**: Task 4.1 (Provider Interface)

## Requirements

### Circuit Breaker Pattern
1. **States**: CLOSED (normal) → OPEN (failing fast) → HALF_OPEN (testing recovery)
2. **Failure Detection**: Track consecutive failures
3. **Recovery Testing**: Limited requests in half-open state
4. **Configuration**: Customizable thresholds

### Health Monitoring
1. **Periodic Checks**: Background health verification
2. **Status Tracking**: HEALTHY, DEGRADED, UNHEALTHY, MAINTENANCE
3. **Latency Monitoring**: Detect slow providers
4. **Metrics Collection**: Success rate, latency, error counts

### Registry Integration
1. **Circuit Breaker Registry**: Central breaker management
2. **Metrics Registry**: Centralized metrics tracking
3. **Health Updates**: Automatic registry synchronization

## Deliverables

### Circuit Breaker (`src/elile/providers/health.py`)
- CircuitState enum (CLOSED, OPEN, HALF_OPEN)
- CircuitBreakerConfig model
- CircuitBreaker class
- CircuitOpenError exception

### Health Monitor (`src/elile/providers/health.py`)
- HealthMonitorConfig model
- HealthMonitor class (background monitoring)
- ProviderMetrics model

### Circuit Breaker Registry
- CircuitBreakerRegistry class
- Centralized breaker/metrics management
- Success/failure recording

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/elile/providers/health.py` | Health monitoring module |
| `src/elile/providers/__init__.py` | Updated exports |
| `tests/unit/test_provider_health.py` | Unit tests (37 tests) |

## Circuit Breaker States

```
     ┌──────────────────────────────────────────────────────┐
     │                                                      │
     │   CLOSED ──[failures >= threshold]──► OPEN          │
     │      │                                   │           │
     │      │ [success resets                   │           │
     │      │  failure count]           [timeout elapsed]  │
     │      │                                   │           │
     │      ▼                                   ▼           │
     │   CLOSED ◄──[successes >= threshold]── HALF_OPEN   │
     │                                          │           │
     │                               [any failure]          │
     │                                          │           │
     │                                          ▼           │
     │                                        OPEN         │
     │                                                      │
     └──────────────────────────────────────────────────────┘
```

## Key Patterns

### Circuit Breaker Usage
```python
breaker_registry = CircuitBreakerRegistry()

# Before request
if breaker_registry.can_execute(provider_id):
    try:
        result = await provider.execute_check(...)
        breaker_registry.record_success(provider_id, latency_ms)
    except Exception as e:
        breaker_registry.record_failure(provider_id, str(e))
        raise
else:
    raise CircuitOpenError(provider_id)
```

### Health Monitor
```python
monitor = HealthMonitor(registry)

# Start background monitoring
await monitor.start()

# Manual health check
health = await monitor.check_provider("provider_id")

# Stop monitoring
await monitor.stop()
```

### Metrics Tracking
```python
metrics = breaker_registry.get_metrics(provider_id)
print(f"Success rate: {metrics.success_rate}")
print(f"Average latency: {metrics.average_latency_ms}ms")
```

## Configuration Defaults

### Circuit Breaker
- failure_threshold: 5 (failures before opening)
- success_threshold: 3 (successes in half-open to close)
- timeout_seconds: 60.0 (time before trying half-open)
- half_open_max_calls: 3 (test calls in half-open)

### Health Monitor
- check_interval_seconds: 60.0
- unhealthy_threshold: 3 (failed checks before unhealthy)
- healthy_threshold: 2 (successful checks before healthy)
- degraded_latency_ms: 5000 (latency threshold for degraded)

## Test Results
- 37 unit tests passing
- Tests circuit state transitions
- Tests threshold behavior
- Tests timeout recovery
- Tests health monitoring
- Tests metrics collection
