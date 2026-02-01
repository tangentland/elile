# Task 6.12: Risk Dashboard

**Priority**: P1
**Phase**: 6 - Risk Analysis
**Estimated Effort**: 3 days
**Dependencies**: Task 6.9 (Risk Trends)

## Context

Create risk dashboard for real-time risk monitoring across organization portfolio with drill-down capabilities.

## Objectives

1. Portfolio risk overview
2. Risk distribution visualization
3. Trend analysis charts
4. Alert management
5. Export and reporting

## Technical Approach

```python
# src/elile/risk/dashboard/api.py
class RiskDashboardAPI:
    async def get_portfolio_risk(self, org_id: str) -> PortfolioRisk:
        return PortfolioRisk(
            total_subjects=count,
            risk_distribution=distribution,
            trending_up=trending_subjects,
            recent_alerts=alerts
        )
```

## Implementation Checklist

- [ ] Create dashboard API
- [ ] Add visualizations
- [ ] Test performance

## Success Criteria

- [ ] Real-time updates
- [ ] Fast queries <2s
