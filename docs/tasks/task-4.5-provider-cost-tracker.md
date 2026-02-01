# Task 4.5: Provider Cost Tracker

## Overview

Track costs for all provider API calls to enable budget monitoring and cost optimization. Records per-query costs and aggregates by provider, tenant, and time period. See [06-data-sources.md](../architecture/06-data-sources.md#cost-tracking) for cost tracking requirements.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 4.1: Provider Gateway
- Task 1.1: Database Schema

## Implementation Checklist

- [ ] Create provider_costs table schema
- [ ] Build CostTracker service
- [ ] Implement cost recording per query
- [ ] Add cost aggregation queries
- [ ] Create budget alert system
- [ ] Build cost reporting queries
- [ ] Write cost tracker tests

## Key Implementation

```python
# src/elile/providers/cost_tracker.py
from decimal import Decimal
from datetime import datetime, date

class ProviderCostRecord(BaseModel):
    """Record of provider API cost."""
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    provider_id: str
    check_type: str
    entity_id: UUID
    screening_id: UUID | None
    cost_usd: Decimal
    query_timestamp: datetime
    billed_records: int = 0
    metadata: dict = {}

class CostAggregation(BaseModel):
    """Aggregated cost metrics."""
    period_start: date
    period_end: date
    total_cost: Decimal
    query_count: int
    by_provider: dict[str, Decimal]
    by_check_type: dict[str, Decimal]

class BudgetAlert(BaseModel):
    """Budget threshold alert."""
    tenant_id: UUID
    alert_type: str  # "daily", "monthly", "per_screening"
    threshold_usd: Decimal
    current_spend: Decimal
    alert_timestamp: datetime

class ProviderCostTracker:
    """Track and report provider API costs."""

    def __init__(self, db: Database):
        self.db = db

    async def record_cost(self, cost_record: ProviderCostRecord) -> None:
        """Record a provider API cost."""
        await self.db.execute(
            """
            INSERT INTO provider_costs (
                id, tenant_id, provider_id, check_type,
                entity_id, screening_id, cost_usd,
                query_timestamp, billed_records, metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
            )
            """,
            cost_record.id,
            cost_record.tenant_id,
            cost_record.provider_id,
            cost_record.check_type,
            cost_record.entity_id,
            cost_record.screening_id,
            cost_record.cost_usd,
            cost_record.query_timestamp,
            cost_record.billed_records,
            cost_record.metadata,
        )

        # Check budget alerts
        await self._check_budget_alerts(cost_record.tenant_id)

    async def get_daily_costs(
        self,
        tenant_id: UUID,
        date: date
    ) -> CostAggregation:
        """Get costs for a specific day."""
        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())

        return await self._aggregate_costs(tenant_id, start, end)

    async def get_monthly_costs(
        self,
        tenant_id: UUID,
        year: int,
        month: int
    ) -> CostAggregation:
        """Get costs for a specific month."""
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)

        return await self._aggregate_costs(tenant_id, start, end)

    async def get_screening_cost(
        self,
        screening_id: UUID
    ) -> Decimal:
        """Get total cost for a screening."""
        result = await self.db.fetchrow(
            """
            SELECT SUM(cost_usd) as total
            FROM provider_costs
            WHERE screening_id = $1
            """,
            screening_id,
        )

        return result["total"] or Decimal("0.00")

    async def _aggregate_costs(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime
    ) -> CostAggregation:
        """Aggregate costs for time period."""
        # Total cost
        total_result = await self.db.fetchrow(
            """
            SELECT
                SUM(cost_usd) as total_cost,
                COUNT(*) as query_count
            FROM provider_costs
            WHERE tenant_id = $1
              AND query_timestamp >= $2
              AND query_timestamp < $3
            """,
            tenant_id, start, end,
        )

        # By provider
        provider_results = await self.db.fetch(
            """
            SELECT provider_id, SUM(cost_usd) as cost
            FROM provider_costs
            WHERE tenant_id = $1
              AND query_timestamp >= $2
              AND query_timestamp < $3
            GROUP BY provider_id
            """,
            tenant_id, start, end,
        )

        # By check type
        check_results = await self.db.fetch(
            """
            SELECT check_type, SUM(cost_usd) as cost
            FROM provider_costs
            WHERE tenant_id = $1
              AND query_timestamp >= $2
              AND query_timestamp < $3
            GROUP BY check_type
            """,
            tenant_id, start, end,
        )

        return CostAggregation(
            period_start=start.date(),
            period_end=end.date(),
            total_cost=total_result["total_cost"] or Decimal("0.00"),
            query_count=total_result["query_count"],
            by_provider={r["provider_id"]: r["cost"] for r in provider_results},
            by_check_type={r["check_type"]: r["cost"] for r in check_results},
        )

    async def _check_budget_alerts(self, tenant_id: UUID) -> None:
        """Check if budget thresholds exceeded."""
        # Get budget configuration
        budget_config = await self._get_budget_config(tenant_id)
        if not budget_config:
            return

        # Check daily budget
        if budget_config.get("daily_limit"):
            today_costs = await self.get_daily_costs(tenant_id, date.today())
            if today_costs.total_cost >= budget_config["daily_limit"]:
                await self._raise_budget_alert(
                    tenant_id,
                    "daily",
                    budget_config["daily_limit"],
                    today_costs.total_cost,
                )

    async def _get_budget_config(self, tenant_id: UUID) -> dict:
        """Get budget configuration for tenant."""
        result = await self.db.fetchrow(
            "SELECT budget_config FROM tenants WHERE id = $1",
            tenant_id,
        )
        return result["budget_config"] if result else {}

    async def _raise_budget_alert(
        self,
        tenant_id: UUID,
        alert_type: str,
        threshold: Decimal,
        current: Decimal,
    ):
        """Raise budget alert."""
        alert = BudgetAlert(
            tenant_id=tenant_id,
            alert_type=alert_type,
            threshold_usd=threshold,
            current_spend=current,
            alert_timestamp=datetime.utcnow(),
        )

        # Log alert
        logger.warning(
            f"Budget alert: {alert_type} threshold ${threshold} exceeded",
            extra={"tenant_id": tenant_id, "current": current},
        )

        # TODO: Send notification (webhook, email, etc.)
```

## Testing Requirements

### Unit Tests
- Cost recording
- Daily/monthly aggregation
- Screening cost calculation
- Budget alert triggers

### Integration Tests
- Multi-tenant cost tracking
- Time-based aggregations
- Budget threshold enforcement

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] provider_costs table created
- [ ] record_cost() saves costs correctly
- [ ] Aggregation queries work for daily/monthly periods
- [ ] Screening cost calculation accurate
- [ ] Budget alerts trigger at thresholds
- [ ] Unit tests pass with 85%+ coverage

## Deliverables

- `src/elile/providers/cost_tracker.py`
- `tests/unit/test_cost_tracker.py`
- Database migration for provider_costs table

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md#cost-tracking)
- Dependencies: Task 4.1 (provider gateway), Task 1.1 (database)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
