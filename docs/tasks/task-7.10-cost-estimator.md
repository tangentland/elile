# Task 7.10: Screening Cost Estimator

**Priority**: P1
**Phase**: 7 - Screening Workflows
**Estimated Effort**: 2 days
**Dependencies**: Task 7.1 (Screening Orchestration)

## Context

Implement cost estimation for screening operations before execution, helping organizations budget and make informed tier selection decisions.

## Objectives

1. Estimate screening costs pre-execution
2. Account for data provider fees
3. Calculate tier-based pricing
4. Support bulk pricing estimates
5. Track actual vs estimated costs

## Technical Approach

```python
# src/elile/screening/cost_estimator.py
class CostEstimator:
    def estimate_screening_cost(
        self,
        tier: ServiceTier,
        degree: Degree,
        checks: Set[CheckType],
        locale: str
    ) -> CostEstimate:
        base_cost = self._get_tier_base_cost(tier)
        provider_costs = self._calculate_provider_costs(checks)
        return CostEstimate(
            total=base_cost + provider_costs,
            breakdown=self._get_cost_breakdown()
        )
```

## Implementation Checklist

- [ ] Implement cost calculation
- [ ] Add provider pricing
- [ ] Test accuracy

## Success Criteria

- [ ] Estimates within 10% of actual
- [ ] All cost factors included
