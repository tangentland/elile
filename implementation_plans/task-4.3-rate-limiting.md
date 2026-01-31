# Task 4.3: Rate Limiting

## Overview
Implement per-provider rate limiting with token bucket algorithm to enforce API rate limits and prevent provider overload or billing surprises.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-31
**Dependencies**: Task 4.1 (Provider Interface)

## Requirements

### Token Bucket Algorithm
1. **Smooth Rate Limiting**: Allow bursts while enforcing sustained throughput limits
2. **Configurable Per-Provider**: Different providers may have different rate limits
3. **Time-Based Refill**: Tokens accumulate over time up to maximum
4. **Async-Safe**: Thread-safe for concurrent requests

### Rate Limit Configuration
1. **tokens_per_second**: Sustained throughput rate
2. **max_tokens**: Burst capacity (bucket size)
3. **initial_tokens**: Starting tokens (optional, defaults to max)

### Registry Pattern
1. **Global Registry**: Centralized rate limiter management
2. **Provider-Specific Config**: Configure limits per provider
3. **Statistics Tracking**: Track allowed/denied requests

## Deliverables

### Rate Limit Module (`src/elile/providers/rate_limit.py`)
- RateLimitStrategy enum (TOKEN_BUCKET, SLIDING_WINDOW)
- RateLimitConfig model
- RateLimitStatus dataclass
- RateLimitResult dataclass
- RateLimitExceededError exception
- TokenBucket class
- ProviderRateLimitRegistry class
- get_rate_limit_registry() singleton accessor

### Exports Updated (`src/elile/providers/__init__.py`)
- All rate limiting classes exported

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/elile/providers/rate_limit.py` | Rate limiting module (new) |
| `src/elile/providers/__init__.py` | Updated exports |
| `tests/unit/test_provider_rate_limit.py` | Unit tests (35 tests) |

## Token Bucket Algorithm

```
     Token Bucket State
     ┌─────────────────────────┐
     │  Max: 100 tokens        │
     │  ┌───────────────────┐  │
     │  │████████████░░░░░░░│  │ Current: 60 tokens
     │  └───────────────────┘  │
     │  Refill: 10 tokens/sec  │
     └─────────────────────────┘

     Request arrives:
     - If tokens >= 1: Consume 1 token, allow request
     - If tokens < 1: Deny request, return retry_after

     Time passes:
     - Add (elapsed_seconds * tokens_per_second) tokens
     - Cap at max_tokens
```

## Key Patterns

### Configure Provider Rate Limits
```python
from elile.providers import RateLimitConfig, get_rate_limit_registry

registry = get_rate_limit_registry()

# Configure Sterling with conservative limits
registry.configure_provider("sterling", RateLimitConfig(
    tokens_per_second=10.0,
    max_tokens=50.0,
))

# Configure Checkr with higher limits
registry.configure_provider("checkr", RateLimitConfig(
    tokens_per_second=50.0,
    max_tokens=200.0,
))
```

### Acquire Tokens Before Request
```python
from elile.providers import get_rate_limit_registry, RateLimitExceededError

registry = get_rate_limit_registry()

try:
    await registry.acquire_or_raise("sterling")
    result = await provider.execute_check(...)
except RateLimitExceededError as e:
    logger.warning(
        "rate_limited",
        provider_id="sterling",
        retry_after=e.retry_after_seconds,
    )
    # Handle: queue, use fallback, or return error
```

### Check Without Consuming
```python
# Useful for pre-flight checks
result = await registry.check("sterling")
if not result.allowed:
    # Route to different provider
    provider = get_fallback_provider()
```

### Wait for Tokens
```python
# Block until tokens available (use with caution)
result = await registry.acquire("sterling", wait=True)
# Request will proceed after waiting
```

## Configuration Defaults

```python
RateLimitConfig(
    tokens_per_second=10.0,  # 10 requests per second sustained
    max_tokens=100.0,        # Up to 100 requests burst
    initial_tokens=100.0,    # Start at full capacity
    strategy=RateLimitStrategy.TOKEN_BUCKET,
)
```

## Test Results
- 35 unit tests passing
- Tests token acquisition and denial
- Tests refill over time
- Tests concurrent access safety
- Tests configuration per provider
- Tests registry management
- Tests error handling

## Integration Notes

### With Circuit Breaker
```python
# Rate limiting before circuit breaker
if rate_limits.can_execute(provider_id):
    result = await rate_limits.acquire_or_raise(provider_id)

    if breaker_registry.can_execute(provider_id):
        try:
            response = await provider.execute_check(...)
            breaker_registry.record_success(provider_id, latency)
        except Exception:
            breaker_registry.record_failure(provider_id)
            raise
```

### Recommended Provider Limits
| Provider | tokens_per_second | max_tokens | Rationale |
|----------|-------------------|------------|-----------|
| Sterling | 10.0 | 50.0 | Conservative for paid API |
| Checkr | 50.0 | 200.0 | Higher limits documented |
| Court Records | 5.0 | 20.0 | Public API, be respectful |
| Free APIs | 1.0 | 10.0 | Very conservative |
