# Task 4.6: Request Routing

## Overview
Implement intelligent request routing with provider selection, retry with exponential backoff, fallback to alternate providers, and integration with circuit breaker, rate limiting, caching, and cost tracking.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-31
**Dependencies**: Task 4.1 (Provider Interface), Task 4.2 (Health/Circuit Breaker), Task 4.3 (Rate Limiting), Task 4.4 (Response Caching), Task 4.5 (Cost Tracking)

## Requirements

### Request Routing
1. **Provider selection**: Select best provider for check type/locale
2. **Tier-aware routing**: CORE for Standard, CORE+PREMIUM for Enhanced
3. **Retry with backoff**: Exponential backoff on transient failures (max 3)
4. **Fallback providers**: Try alternate providers on failure
5. **Partial completion**: Continue with other checks when one fails

### Integration Points
1. **Circuit breaker**: Check circuit state before requests, record success/failure
2. **Rate limiting**: Acquire token before requests
3. **Caching**: Check cache before provider call, store results
4. **Cost tracking**: Record costs and cache savings

### Error Handling
| Scenario | Action |
|----------|--------|
| Provider timeout | Retry with exponential backoff (max 3) |
| Provider error | Try alternate provider if available |
| Provider down (circuit open) | Route to alternates |
| Rate limited | Wait or try alternate |
| No alternate available | Mark check as incomplete |
| All providers fail | Return partial result with failure reason |

## Deliverables

### Request Router (`src/elile/providers/router.py`)
- RequestRouter class
- RoutedRequest dataclass
- RoutedResult dataclass
- RoutingConfig model
- RouteFailure dataclass

### Methods
```python
class RequestRouter:
    async def route_request(
        self,
        check_type: CheckType,
        subject: SubjectIdentifiers,
        locale: Locale,
        *,
        entity_id: UUID,
        tenant_id: UUID,
        service_tier: ServiceTier = ServiceTier.STANDARD,
        screening_id: UUID | None = None,
    ) -> RoutedResult

    async def route_batch(
        self,
        requests: list[RoutedRequest],
        *,
        parallel: bool = True,
    ) -> list[RoutedResult]
```

## Files to Create/Modify

| File | Purpose |
|------|---------|
| `src/elile/providers/router.py` | Request routing service (new) |
| `src/elile/providers/__init__.py` | Updated exports |
| `tests/unit/test_provider_router.py` | Unit tests |

## Router Configuration

```python
class RoutingConfig(BaseModel):
    max_retries: int = 3
    base_retry_delay: float = 0.5  # seconds
    max_retry_delay: float = 10.0  # seconds
    retry_jitter: float = 0.1  # ±10% jitter
    timeout: float = 30.0  # seconds per request
    parallel_batch: bool = True  # Run batch requests in parallel
```

## Routed Request/Result

```python
@dataclass
class RoutedRequest:
    request_id: UUID
    check_type: CheckType
    subject: SubjectIdentifiers
    locale: Locale
    entity_id: UUID
    tenant_id: UUID
    service_tier: ServiceTier = ServiceTier.STANDARD
    screening_id: UUID | None = None

@dataclass
class RoutedResult:
    request_id: UUID
    check_type: CheckType
    success: bool
    result: ProviderResult | None

    # Execution details
    provider_id: str | None
    attempts: int
    total_duration: timedelta

    # Cache status
    cache_hit: bool
    cache_entry_id: UUID | None

    # Cost tracking
    cost_incurred: Decimal
    cost_saved: Decimal

    # Failure info
    failure: RouteFailure | None

@dataclass
class RouteFailure:
    reason: FailureReason
    message: str
    provider_errors: list[tuple[str, str]]  # (provider_id, error_message)
```

## Routing Flow

```
1. Cache Lookup
   ├── Cache Hit (FRESH) → Return cached result
   ├── Cache Hit (STALE) → Use stale if include_stale, else continue
   └── Cache Miss → Continue to provider

2. Provider Selection
   ├── Get providers for check type/locale/tier
   ├── Filter by circuit breaker state (skip OPEN)
   ├── Sort by cost/reliability preference
   └── Select primary provider

3. Rate Limit Check
   ├── Check rate limit for primary
   ├── If limited, try next provider
   └── If all limited, fail with RATE_LIMITED

4. Execute Request
   ├── Record circuit breaker call start
   ├── Execute provider.execute_check()
   ├── Record success/failure to circuit breaker
   └── On failure, retry or fallback

5. Retry Logic (on failure)
   ├── Transient error? Retry same provider with backoff
   ├── Max retries reached? Try fallback provider
   ├── All fallbacks failed? Return incomplete result
   └── Track all provider errors for diagnostics

6. Post-Processing
   ├── Store result in cache (if successful)
   ├── Record cost to cost service
   └── Return RoutedResult
```

## Key Patterns

### Basic Routing
```python
router = RequestRouter(
    registry=get_provider_registry(),
    cache=ProviderCacheService(session),
    rate_limiter=get_rate_limit_registry(),
    circuit_registry=CircuitBreakerRegistry(),
    cost_service=get_cost_service(),
)

result = await router.route_request(
    check_type=CheckType.CRIMINAL_NATIONAL,
    subject=identifiers,
    locale=Locale.US,
    entity_id=entity_id,
    tenant_id=tenant_id,
    service_tier=ServiceTier.STANDARD,
)

if result.success:
    print(f"Provider: {result.provider_id}")
    print(f"Cost: ${result.cost_incurred}")
    print(f"Cache hit: {result.cache_hit}")
else:
    print(f"Failed: {result.failure.reason}")
    for provider_id, error in result.failure.provider_errors:
        print(f"  {provider_id}: {error}")
```

### Batch Routing
```python
requests = [
    RoutedRequest(
        request_id=uuid7(),
        check_type=CheckType.CRIMINAL_NATIONAL,
        subject=identifiers,
        locale=Locale.US,
        entity_id=entity_id,
        tenant_id=tenant_id,
    ),
    RoutedRequest(
        request_id=uuid7(),
        check_type=CheckType.CREDIT_REPORT,
        subject=identifiers,
        locale=Locale.US,
        entity_id=entity_id,
        tenant_id=tenant_id,
    ),
]

results = await router.route_batch(requests, parallel=True)

for result in results:
    if result.success:
        print(f"{result.check_type}: OK")
    else:
        print(f"{result.check_type}: {result.failure.reason}")
```

## Verification

1. Run unit tests: `.venv/bin/pytest tests/unit/test_provider_router.py -v`
2. Run full test suite: `.venv/bin/pytest -v`
3. Verify retry logic with mock failures
4. Verify fallback to alternate providers
5. Verify circuit breaker integration
6. Verify rate limiting integration
7. Verify caching integration
8. Verify cost tracking integration

## Notes

- Retries only for transient errors (timeout, connection, 5xx)
- Circuit breaker state checked before each attempt
- Rate limiting checked before each attempt
- Cache checked once at start (not on retry)
- Cost recorded only for successful provider calls
- Cache savings recorded when cache hit avoids provider call
