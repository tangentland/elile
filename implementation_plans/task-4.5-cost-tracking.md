# Task 4.5: Cost Tracking

## Overview
Implement cost tracking for provider queries to enable billing attribution, budget management, and cost optimization analytics.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-31
**Dependencies**: Task 4.1 (Provider Interface), Task 4.4 (Response Caching)

## Requirements

### Cost Recording
1. **Per-query cost capture**: Record cost for each provider query
2. **Tenant attribution**: Associate costs with tenant for billing
3. **Screening attribution**: Link costs to screening sessions
4. **Cache savings tracking**: Calculate savings from cache hits

### Cost Aggregation
1. **By tenant**: Total costs per customer
2. **By provider**: Costs per data provider
3. **By check type**: Costs per check type category
4. **By time period**: Daily, weekly, monthly aggregations

### Budget Management
1. **Budget limits**: Set spending limits per tenant
2. **Threshold alerts**: Warning when approaching limits
3. **Hard limits**: Block requests when budget exceeded

## Existing Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| `ProviderQueryCost` | `providers/types.py` | Cost tracking model |
| `CachedDataSource.cost_incurred` | `db/models/cache.py` | Cost stored with cached data |
| `ProviderResult.cost_incurred` | `providers/types.py` | Cost on provider results |

## Deliverables

### Cost Service (`src/elile/providers/cost.py`)
- CostRecord dataclass
- CostSummary dataclass
- BudgetConfig model
- BudgetStatus dataclass
- ProviderCostService class
- BudgetExceededError exception

### Methods
```python
class ProviderCostService:
    async def record_cost(query_id, provider_id, check_type, cost, tenant_id) -> CostRecord
    async def record_cache_savings(query_id, provider_id, saved_amount, tenant_id) -> None
    async def get_tenant_costs(tenant_id, start_date, end_date) -> CostSummary
    async def get_provider_costs(provider_id, start_date, end_date) -> CostSummary
    async def check_budget(tenant_id, estimated_cost) -> BudgetStatus
    async def set_budget(tenant_id, config) -> None
```

## Files to Create/Modify

| File | Purpose |
|------|---------|
| `src/elile/providers/cost.py` | Cost tracking service (new) |
| `src/elile/providers/__init__.py` | Updated exports |
| `tests/unit/test_provider_cost.py` | Unit tests |

## Cost Record Structure

```python
@dataclass
class CostRecord:
    record_id: UUID
    query_id: UUID
    provider_id: str
    check_type: str
    tenant_id: UUID
    screening_id: UUID | None

    # Cost details
    cost_amount: Decimal
    cost_currency: str

    # Cache impact
    cache_hit: bool
    cache_savings: Decimal | None

    # Timestamps
    incurred_at: datetime
```

## Budget Configuration

```python
class BudgetConfig(BaseModel):
    tenant_id: UUID
    monthly_limit: Decimal | None
    daily_limit: Decimal | None
    warning_threshold: float = 0.8  # Warn at 80%
    hard_limit: bool = True  # Block when exceeded
```

## Key Patterns

### Recording Query Cost
```python
cost_service = ProviderCostService()

# After provider query
record = await cost_service.record_cost(
    query_id=query.query_id,
    provider_id="sterling",
    check_type=CheckType.CRIMINAL_NATIONAL,
    cost=result.cost_incurred,
    tenant_id=tenant_id,
    screening_id=screening_id,
)
```

### Recording Cache Savings
```python
# When cache hit saves a query
await cost_service.record_cache_savings(
    query_id=query_id,
    provider_id="sterling",
    saved_amount=Decimal("5.00"),
    tenant_id=tenant_id,
)
```

### Budget Checking
```python
# Before making expensive query
status = await cost_service.check_budget(
    tenant_id=tenant_id,
    estimated_cost=Decimal("10.00"),
)

if status.would_exceed:
    if status.hard_limit:
        raise BudgetExceededError(tenant_id, status)
    else:
        logger.warning("Budget warning", remaining=status.remaining)
```

### Cost Analytics
```python
# Get tenant's monthly costs
summary = await cost_service.get_tenant_costs(
    tenant_id=tenant_id,
    start_date=month_start,
    end_date=month_end,
)

print(f"Total: ${summary.total_cost}")
print(f"Saved by cache: ${summary.cache_savings}")
print(f"By provider: {summary.by_provider}")
```

## Verification

1. Run unit tests: `.venv/bin/pytest tests/unit/test_provider_cost.py -v`
2. Run full test suite: `.venv/bin/pytest -v`
3. Verify cost recording for provider queries
4. Verify budget limit enforcement
5. Verify cache savings tracking

## Notes

- Costs stored in-memory for this implementation (database persistence in future)
- Budget limits are per-tenant configurable
- Cache savings tracked separately from actual costs
- All amounts in USD by default
