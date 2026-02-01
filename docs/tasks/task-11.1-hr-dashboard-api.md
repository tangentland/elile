# Task 11.1: HR Dashboard API

## Overview

Implement HR Dashboard API endpoints providing screening summaries, portfolio metrics, and risk distribution for HR managers.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 10.1: API Gateway
- Task 8.2: HR Summary Report

## Implementation

```python
# src/elile/api/v1/dashboard.py
@router.get("/dashboard/hr/portfolio")
async def get_hr_portfolio(
    ctx: RequestContext = Depends(authenticate_request)
):
    """Get HR portfolio overview."""
    return {
        "total_screenings": await screening_service.count_screenings(ctx),
        "pending_reviews": await screening_service.count_pending_reviews(ctx),
        "risk_distribution": await risk_service.get_risk_distribution(ctx),
        "recent_alerts": await alert_service.get_recent_alerts(ctx, limit=10)
    }

@router.get("/dashboard/hr/screenings")
async def list_screenings(
    status: ScreeningStatus | None = None,
    risk_level: RiskLevel | None = None,
    limit: int = 50,
    ctx: RequestContext = Depends(authenticate_request)
):
    """List screenings with filters."""
    return await screening_service.list_screenings(
        ctx, status=status, risk_level=risk_level, limit=limit
    )
```

## Acceptance Criteria

- [ ] GET /dashboard/hr/portfolio - overview metrics
- [ ] GET /dashboard/hr/screenings - list with filters
- [ ] GET /dashboard/hr/alerts - recent alerts
- [ ] Risk distribution data
- [ ] Pagination support

## Deliverables

- `src/elile/api/v1/dashboard.py`
- `tests/integration/test_hr_dashboard_api.py`

## References

- Architecture: [11-interfaces.md](../../docs/architecture/11-interfaces.md) - HR Dashboard

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
