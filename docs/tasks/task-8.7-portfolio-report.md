# Task 8.7: Portfolio Report Generator

**Priority**: P1
**Phase**: 8 - Reporting Engine
**Estimated Effort**: 3 days
**Dependencies**: Task 8.1 (Report Generation)

## Context

Generate executive portfolio reports showing aggregate risk metrics, trends, and organizational risk posture across all subjects.

## Objectives

1. Aggregate org-wide metrics
2. Risk distribution analysis
3. Trend visualization
4. Compliance status summary
5. Executive-level insights

## Technical Approach

```python
# src/elile/reporting/generators/portfolio.py
class PortfolioReportGenerator:
    def generate(self, org_id: str, period: DateRange) -> PortfolioReport:
        return PortfolioReport(
            total_screenings=count,
            risk_distribution=dist,
            trends=trends,
            compliance_summary=compliance,
            recommendations=recommendations
        )
```

## Implementation Checklist

- [ ] Aggregate metrics
- [ ] Generate visualizations
- [ ] Test accuracy

## Success Criteria

- [ ] Accurate aggregation
- [ ] Meaningful insights
