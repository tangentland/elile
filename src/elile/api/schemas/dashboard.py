"""API schemas for HR Dashboard endpoints.

This module defines the request and response schemas for the HR Dashboard API,
providing portfolio metrics, screening lists, alerts, and risk distribution.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from elile.monitoring.types import AlertSeverity
from elile.risk.risk_scorer import RiskLevel
from elile.screening.types import ScreeningStatus

# =============================================================================
# Response Schemas
# =============================================================================


class RiskDistributionItem(BaseModel):
    """Risk distribution by level."""

    level: str = Field(..., description="Risk level (low/moderate/high/critical)")
    count: int = Field(..., ge=0, description="Number of screenings at this level")
    percentage: float = Field(..., ge=0, le=100, description="Percentage of total")


class RiskDistribution(BaseModel):
    """Complete risk distribution across all levels."""

    low: int = Field(default=0, ge=0, description="Count of low risk screenings")
    moderate: int = Field(default=0, ge=0, description="Count of moderate risk screenings")
    high: int = Field(default=0, ge=0, description="Count of high risk screenings")
    critical: int = Field(default=0, ge=0, description="Count of critical risk screenings")
    unknown: int = Field(default=0, ge=0, description="Count of screenings without risk level")
    total: int = Field(default=0, ge=0, description="Total completed screenings")

    @classmethod
    def from_counts(
        cls,
        low: int = 0,
        moderate: int = 0,
        high: int = 0,
        critical: int = 0,
        unknown: int = 0,
    ) -> "RiskDistribution":
        """Create from individual counts."""
        return cls(
            low=low,
            moderate=moderate,
            high=high,
            critical=critical,
            unknown=unknown,
            total=low + moderate + high + critical + unknown,
        )

    def to_items(self) -> list[RiskDistributionItem]:
        """Convert to list of items with percentages."""
        items = []
        for level in [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL]:
            count = getattr(self, level.value, 0)
            pct = (count / self.total * 100) if self.total > 0 else 0.0
            items.append(
                RiskDistributionItem(
                    level=level.value,
                    count=count,
                    percentage=round(pct, 1),
                )
            )
        return items


class AlertSummary(BaseModel):
    """Alert summary for dashboard."""

    alert_id: UUID = Field(..., description="Alert identifier")
    severity: AlertSeverity = Field(..., description="Alert severity")
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Alert description")
    created_at: datetime = Field(..., description="When alert was created")
    acknowledged: bool = Field(default=False, description="Whether alert is acknowledged")
    entity_name: str | None = Field(default=None, description="Related entity name")
    screening_id: UUID | None = Field(default=None, description="Related screening ID")

    model_config = {
        "json_schema_extra": {
            "example": {
                "alert_id": "019478f2-1234-7000-8000-abcdef123456",
                "severity": "high",
                "title": "New Criminal Record Detected",
                "description": "Criminal record found during monitoring",
                "created_at": "2026-01-30T12:00:00Z",
                "acknowledged": False,
                "entity_name": "John Smith",
                "screening_id": None,
            }
        }
    }


class ScreeningSummary(BaseModel):
    """Screening summary for dashboard list."""

    screening_id: UUID = Field(..., description="Screening identifier")
    status: ScreeningStatus = Field(..., description="Current screening status")
    subject_name: str = Field(..., description="Subject's name")
    created_at: datetime = Field(..., description="When screening was initiated")
    completed_at: datetime | None = Field(default=None, description="When screening completed")
    risk_score: int | None = Field(default=None, ge=0, le=100, description="Risk score (0-100)")
    risk_level: str | None = Field(default=None, description="Risk level")
    recommendation: str | None = Field(default=None, description="Hiring recommendation")
    findings_count: int = Field(default=0, ge=0, description="Total findings count")
    critical_findings: int = Field(default=0, ge=0, description="Critical findings count")

    model_config = {
        "json_schema_extra": {
            "example": {
                "screening_id": "019478f2-1234-7000-8000-abcdef123456",
                "status": "complete",
                "subject_name": "John Smith",
                "created_at": "2026-01-30T12:00:00Z",
                "completed_at": "2026-01-30T12:05:00Z",
                "risk_score": 35,
                "risk_level": "moderate",
                "recommendation": "proceed_with_caution",
                "findings_count": 3,
                "critical_findings": 0,
            }
        }
    }


class PortfolioMetrics(BaseModel):
    """HR portfolio overview metrics."""

    total_screenings: int = Field(default=0, ge=0, description="Total screenings")
    active_screenings: int = Field(default=0, ge=0, description="Screenings in progress")
    completed_screenings: int = Field(default=0, ge=0, description="Completed screenings")
    pending_reviews: int = Field(default=0, ge=0, description="Screenings requiring review")
    pending_decisions: int = Field(default=0, ge=0, description="Screenings awaiting decision")
    this_month: int = Field(default=0, ge=0, description="Screenings initiated this month")
    average_risk_score: float = Field(default=0.0, ge=0, le=100, description="Average risk score")
    risk_distribution: RiskDistribution = Field(
        default_factory=RiskDistribution, description="Risk level distribution"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_screenings": 150,
                "active_screenings": 12,
                "completed_screenings": 138,
                "pending_reviews": 5,
                "pending_decisions": 3,
                "this_month": 28,
                "average_risk_score": 32.5,
                "risk_distribution": {
                    "low": 85,
                    "moderate": 35,
                    "high": 15,
                    "critical": 3,
                    "unknown": 0,
                    "total": 138,
                },
            }
        }
    }


class HRPortfolioResponse(BaseModel):
    """Response for HR portfolio overview."""

    metrics: PortfolioMetrics = Field(..., description="Portfolio metrics")
    recent_alerts: list[AlertSummary] = Field(
        default_factory=list, description="Recent alerts (up to 10)"
    )
    updated_at: datetime = Field(..., description="When data was last updated")

    model_config = {
        "json_schema_extra": {
            "example": {
                "metrics": {
                    "total_screenings": 150,
                    "active_screenings": 12,
                    "completed_screenings": 138,
                    "pending_reviews": 5,
                    "pending_decisions": 3,
                    "this_month": 28,
                    "average_risk_score": 32.5,
                    "risk_distribution": {
                        "low": 85,
                        "moderate": 35,
                        "high": 15,
                        "critical": 3,
                        "unknown": 0,
                        "total": 138,
                    },
                },
                "recent_alerts": [],
                "updated_at": "2026-01-30T12:00:00Z",
            }
        }
    }


class HRScreeningsListResponse(BaseModel):
    """Paginated response for HR screenings list."""

    items: list[ScreeningSummary] = Field(..., description="Screening summaries")
    total: int = Field(..., ge=0, description="Total matching screenings")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    has_more: bool = Field(..., description="Whether more pages exist")
    filters_applied: dict[str, Any] = Field(
        default_factory=dict, description="Applied filters"
    )


class HRAlertsListResponse(BaseModel):
    """Paginated response for HR alerts list."""

    items: list[AlertSummary] = Field(..., description="Alert summaries")
    total: int = Field(..., ge=0, description="Total alerts")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    has_more: bool = Field(..., description="Whether more pages exist")
    unacknowledged_count: int = Field(
        default=0, ge=0, description="Count of unacknowledged alerts"
    )


class RiskDistributionResponse(BaseModel):
    """Response for risk distribution data."""

    distribution: RiskDistribution = Field(..., description="Risk distribution by level")
    items: list[RiskDistributionItem] = Field(..., description="Distribution as list with %")
    period: str = Field(default="all_time", description="Time period for distribution")
    updated_at: datetime = Field(..., description="When data was last updated")
