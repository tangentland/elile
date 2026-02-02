"""HR Dashboard API endpoints.

This module provides REST API endpoints for the HR Dashboard:
- GET /dashboard/hr/portfolio - Portfolio overview and metrics
- GET /dashboard/hr/screenings - List screenings with filters
- GET /dashboard/hr/alerts - Recent alerts
- GET /dashboard/hr/risk-distribution - Risk level distribution
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query

from elile.api.dependencies import get_request_context
from elile.api.schemas.dashboard import (
    AlertSummary,
    HRAlertsListResponse,
    HRPortfolioResponse,
    HRScreeningsListResponse,
    PortfolioMetrics,
    RiskDistribution,
    RiskDistributionResponse,
    ScreeningSummary,
)
from elile.core.context import RequestContext
from elile.monitoring.alert_generator import AlertGenerator, GeneratedAlert, create_alert_generator
from elile.monitoring.types import AlertSeverity
from elile.risk.risk_scorer import RiskLevel
from elile.screening import (
    ScreeningResult,
    ScreeningStateManager,
    ScreeningStatus,
    create_state_manager,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/dashboard/hr", tags=["hr-dashboard"])


# =============================================================================
# Dependencies
# =============================================================================


def get_state_manager() -> ScreeningStateManager:
    """Get the screening state manager instance.

    In production, this would use a persistent store (Redis/database).
    """
    return _get_global_state_manager()


def get_alert_generator() -> AlertGenerator:
    """Get the alert generator instance.

    In production, this would be configured with proper channels.
    """
    return _get_global_alert_generator()


# Simple in-memory singletons for state manager and alert generator
_state_manager: ScreeningStateManager | None = None
_alert_generator: AlertGenerator | None = None


def _get_global_state_manager() -> ScreeningStateManager:
    """Get or create global state manager singleton."""
    global _state_manager
    if _state_manager is None:
        _state_manager = create_state_manager()
    return _state_manager


def _get_global_alert_generator() -> AlertGenerator:
    """Get or create global alert generator singleton."""
    global _alert_generator
    if _alert_generator is None:
        _alert_generator = create_alert_generator(include_mock_channels=True)
    return _alert_generator


# =============================================================================
# In-Memory Storage (shared with screening.py)
# =============================================================================


def _get_screening_storage() -> dict[str, ScreeningResult]:
    """Get the shared screening storage (lazy import to avoid circular dependency)."""
    from elile.api.routers.v1.screening import _stored_results
    return _stored_results


def _get_tenant_screening_results(tenant_id: UUID) -> list[ScreeningResult]:
    """Get tenant screenings from shared storage."""
    from elile.api.routers.v1.screening import _get_tenant_results
    return _get_tenant_results(tenant_id)


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/portfolio",
    response_model=HRPortfolioResponse,
    summary="Get HR portfolio overview",
    description="""
    Get comprehensive portfolio overview for HR managers including:
    - Total, active, and completed screening counts
    - Pending reviews and decisions
    - Risk distribution across all completed screenings
    - Recent alerts requiring attention

    This endpoint provides a high-level dashboard view of the
    organization's screening portfolio.
    """,
    responses={
        200: {"description": "Portfolio overview"},
    },
)
async def get_hr_portfolio(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    alert_generator: Annotated[AlertGenerator, Depends(get_alert_generator)],
) -> HRPortfolioResponse:
    """Get HR portfolio overview metrics.

    Args:
        ctx: Request context with tenant info.
        alert_generator: Alert generator for recent alerts.

    Returns:
        HRPortfolioResponse with portfolio metrics and recent alerts.
    """
    logger.debug(
        "Getting HR portfolio",
        tenant_id=str(ctx.tenant_id),
    )

    # Get all screenings for tenant
    tenant_screenings = _get_tenant_screening_results(ctx.tenant_id)

    # Calculate metrics
    metrics = _calculate_portfolio_metrics(tenant_screenings)

    # Get recent alerts (up to 10)
    recent_alerts = _get_recent_alerts(alert_generator, limit=10)

    return HRPortfolioResponse(
        metrics=metrics,
        recent_alerts=recent_alerts,
        updated_at=datetime.now(UTC),
    )


@router.get(
    "/screenings",
    response_model=HRScreeningsListResponse,
    summary="List screenings with filters",
    description="""
    List screenings for the HR dashboard with filtering and pagination.

    **Filters:**
    - status: Filter by screening status
    - risk_level: Filter by risk level (low/moderate/high/critical)
    - has_critical_findings: Filter by presence of critical findings
    - date_from/date_to: Filter by date range

    Results are sorted by creation date (newest first).
    """,
    responses={
        200: {"description": "List of screenings"},
    },
)
async def list_hr_screenings(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    status: Annotated[
        ScreeningStatus | None,
        Query(description="Filter by screening status"),
    ] = None,
    risk_level: Annotated[
        str | None,
        Query(description="Filter by risk level (low/moderate/high/critical)"),
    ] = None,
    has_critical_findings: Annotated[
        bool | None,
        Query(description="Filter by presence of critical findings"),
    ] = None,
    date_from: Annotated[
        datetime | None,
        Query(description="Filter by start date (ISO 8601)"),
    ] = None,
    date_to: Annotated[
        datetime | None,
        Query(description="Filter by end date (ISO 8601)"),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 50,
) -> HRScreeningsListResponse:
    """List screenings with filters for HR dashboard.

    Args:
        ctx: Request context with tenant info.
        status: Optional status filter.
        risk_level: Optional risk level filter.
        has_critical_findings: Optional critical findings filter.
        date_from: Optional start date filter.
        date_to: Optional end date filter.
        page: Page number (1-indexed).
        page_size: Number of items per page.

    Returns:
        HRScreeningsListResponse with paginated screenings.
    """
    logger.debug(
        "Listing HR screenings",
        tenant_id=str(ctx.tenant_id),
        status=status.value if status else None,
        risk_level=risk_level,
        page=page,
        page_size=page_size,
    )

    # Get all screenings for tenant
    tenant_screenings = _get_tenant_screening_results(ctx.tenant_id)

    # Apply filters
    filtered = tenant_screenings
    filters_applied: dict[str, str | bool] = {}

    if status:
        filtered = [s for s in filtered if s.status == status]
        filters_applied["status"] = status.value

    if risk_level:
        filtered = [s for s in filtered if s.risk_level == risk_level]
        filters_applied["risk_level"] = risk_level

    if has_critical_findings is not None:
        if has_critical_findings:
            filtered = [s for s in filtered if s.critical_findings > 0]
        else:
            filtered = [s for s in filtered if s.critical_findings == 0]
        filters_applied["has_critical_findings"] = has_critical_findings

    if date_from:
        filtered = [s for s in filtered if s.started_at and s.started_at >= date_from]
        filters_applied["date_from"] = date_from.isoformat()

    if date_to:
        filtered = [s for s in filtered if s.started_at and s.started_at <= date_to]
        filters_applied["date_to"] = date_to.isoformat()

    # Sort by started_at descending (newest first)
    filtered.sort(key=lambda s: s.started_at or datetime.min, reverse=True)

    # Paginate
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_results = filtered[start:end]

    # Convert to summaries
    items = [_screening_to_summary(s) for s in page_results]

    return HRScreeningsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
        filters_applied=filters_applied,
    )


@router.get(
    "/alerts",
    response_model=HRAlertsListResponse,
    summary="Get recent alerts",
    description="""
    Get alerts for the HR dashboard with filtering and pagination.

    **Filters:**
    - severity: Filter by alert severity
    - acknowledged: Filter by acknowledgment status

    Results are sorted by creation date (newest first).
    """,
    responses={
        200: {"description": "List of alerts"},
    },
)
async def list_hr_alerts(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    alert_generator: Annotated[AlertGenerator, Depends(get_alert_generator)],
    severity: Annotated[
        AlertSeverity | None,
        Query(description="Filter by severity"),
    ] = None,
    acknowledged: Annotated[
        bool | None,
        Query(description="Filter by acknowledgment status"),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> HRAlertsListResponse:
    """List alerts for HR dashboard.

    Args:
        ctx: Request context with tenant info.
        alert_generator: Alert generator for alert history.
        severity: Optional severity filter.
        acknowledged: Optional acknowledgment filter.
        page: Page number (1-indexed).
        page_size: Number of items per page.

    Returns:
        HRAlertsListResponse with paginated alerts.
    """
    logger.debug(
        "Listing HR alerts",
        tenant_id=str(ctx.tenant_id),
        severity=severity.value if severity else None,
        acknowledged=acknowledged,
        page=page,
        page_size=page_size,
    )

    # Get alerts from generator
    all_alerts = alert_generator.get_alert_history(limit=1000)

    # Apply filters
    filtered = all_alerts

    if severity:
        filtered = [a for a in filtered if a.severity == severity]

    if acknowledged is not None:
        filtered = [a for a in filtered if a.alert.acknowledged == acknowledged]

    # Count unacknowledged
    unacknowledged_count = sum(1 for a in all_alerts if not a.alert.acknowledged)

    # Sort by created_at descending
    filtered.sort(key=lambda a: a.created_at, reverse=True)

    # Paginate
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_results = filtered[start:end]

    # Convert to summaries
    items = [_alert_to_summary(a) for a in page_results]

    return HRAlertsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
        unacknowledged_count=unacknowledged_count,
    )


@router.get(
    "/risk-distribution",
    response_model=RiskDistributionResponse,
    summary="Get risk distribution",
    description="""
    Get the risk level distribution across all completed screenings.

    Returns counts and percentages for each risk level (low, moderate,
    high, critical) to enable visualization of portfolio risk.
    """,
    responses={
        200: {"description": "Risk distribution data"},
    },
)
async def get_risk_distribution(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    period: Annotated[
        str | None,
        Query(description="Time period (all_time, this_month, this_quarter, this_year)"),
    ] = "all_time",
) -> RiskDistributionResponse:
    """Get risk distribution data for HR dashboard.

    Args:
        ctx: Request context with tenant info.
        period: Time period filter.

    Returns:
        RiskDistributionResponse with distribution data.
    """
    logger.debug(
        "Getting risk distribution",
        tenant_id=str(ctx.tenant_id),
        period=period,
    )

    # Get all completed screenings for tenant
    tenant_screenings = _get_tenant_screening_results(ctx.tenant_id)
    completed = [s for s in tenant_screenings if s.status == ScreeningStatus.COMPLETE]

    # Apply period filter
    if period and period != "all_time":
        now = datetime.now(UTC)
        if period == "this_month":
            start_of_period = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "this_quarter":
            quarter_month = ((now.month - 1) // 3) * 3 + 1
            start_of_period = now.replace(
                month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0
            )
        elif period == "this_year":
            start_of_period = now.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            start_of_period = None

        if start_of_period:
            completed = [
                s for s in completed if s.completed_at and s.completed_at >= start_of_period
            ]

    # Calculate distribution
    distribution = _calculate_risk_distribution(completed)

    return RiskDistributionResponse(
        distribution=distribution,
        items=distribution.to_items(),
        period=period or "all_time",
        updated_at=datetime.now(UTC),
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _calculate_portfolio_metrics(screenings: list[ScreeningResult]) -> PortfolioMetrics:
    """Calculate portfolio metrics from screenings.

    Args:
        screenings: List of screening results.

    Returns:
        PortfolioMetrics with calculated values.
    """
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Count by status
    total = len(screenings)
    active_statuses = {ScreeningStatus.PENDING, ScreeningStatus.IN_PROGRESS, ScreeningStatus.VALIDATING, ScreeningStatus.ANALYZING, ScreeningStatus.GENERATING_REPORT}
    active = sum(1 for s in screenings if s.status in active_statuses)
    completed = sum(1 for s in screenings if s.status == ScreeningStatus.COMPLETE)

    # Count pending reviews (high/critical risk needing review)
    pending_reviews = sum(
        1
        for s in screenings
        if s.status == ScreeningStatus.COMPLETE
        and s.recommendation in ("review_required", "do_not_proceed")
    )

    # Count this month
    this_month = sum(1 for s in screenings if s.started_at and s.started_at >= month_start)

    # Calculate average risk score
    completed_with_score = [s for s in screenings if s.status == ScreeningStatus.COMPLETE and s.risk_score is not None]
    avg_risk = 0.0
    if completed_with_score:
        avg_risk = sum(s.risk_score for s in completed_with_score) / len(completed_with_score)

    # Calculate risk distribution
    distribution = _calculate_risk_distribution(
        [s for s in screenings if s.status == ScreeningStatus.COMPLETE]
    )

    return PortfolioMetrics(
        total_screenings=total,
        active_screenings=active,
        completed_screenings=completed,
        pending_reviews=pending_reviews,
        pending_decisions=pending_reviews,  # Same logic for now
        this_month=this_month,
        average_risk_score=round(avg_risk, 1),
        risk_distribution=distribution,
    )


def _calculate_risk_distribution(screenings: list[ScreeningResult]) -> RiskDistribution:
    """Calculate risk distribution from screenings.

    Args:
        screenings: List of completed screening results.

    Returns:
        RiskDistribution with counts per level.
    """
    low = 0
    moderate = 0
    high = 0
    critical = 0
    unknown = 0

    for s in screenings:
        if s.risk_level == RiskLevel.LOW.value:
            low += 1
        elif s.risk_level == RiskLevel.MODERATE.value:
            moderate += 1
        elif s.risk_level == RiskLevel.HIGH.value:
            high += 1
        elif s.risk_level == RiskLevel.CRITICAL.value:
            critical += 1
        else:
            unknown += 1

    return RiskDistribution.from_counts(
        low=low, moderate=moderate, high=high, critical=critical, unknown=unknown
    )


def _screening_to_summary(result: ScreeningResult) -> ScreeningSummary:
    """Convert ScreeningResult to ScreeningSummary.

    Args:
        result: Screening result.

    Returns:
        ScreeningSummary for dashboard.
    """
    # Extract subject name - ScreeningResult doesn't have metadata or subject_name
    # In production, this would be fetched from the entity or request
    subject_name = "Unknown Subject"
    if hasattr(result, "subject_name") and result.subject_name:
        subject_name = result.subject_name

    return ScreeningSummary(
        screening_id=UUID(str(result.screening_id)),
        status=result.status,
        subject_name=subject_name,
        created_at=result.started_at or datetime.now(UTC),
        completed_at=result.completed_at,
        risk_score=result.risk_score,
        risk_level=result.risk_level,
        recommendation=result.recommendation,
        findings_count=result.findings_count,
        critical_findings=result.critical_findings,
    )


def _get_recent_alerts(alert_generator: AlertGenerator, limit: int = 10) -> list[AlertSummary]:
    """Get recent alerts as summaries.

    Args:
        alert_generator: Alert generator instance.
        limit: Maximum alerts to return.

    Returns:
        List of AlertSummary.
    """
    alerts = alert_generator.get_alert_history(limit=limit)
    return [_alert_to_summary(a) for a in alerts]


def _alert_to_summary(alert: GeneratedAlert) -> AlertSummary:
    """Convert GeneratedAlert to AlertSummary.

    Args:
        alert: Generated alert.

    Returns:
        AlertSummary for dashboard.
    """
    return AlertSummary(
        alert_id=alert.alert_id,
        severity=alert.severity,
        title=alert.alert.title,
        description=alert.alert.description,
        created_at=alert.created_at,
        acknowledged=alert.alert.acknowledged,
        entity_name=None,  # Would be populated from entity lookup
        screening_id=alert.alert.monitoring_config_id,  # Using config_id as proxy
    )
