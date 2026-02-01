"""API schemas for screening endpoints.

This module defines the request and response schemas for the screening API,
separate from the internal domain models to allow API versioning.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from elile.agent.state import SearchDegree, ServiceTier, VigilanceLevel
from elile.compliance.types import Locale, RoleCategory
from elile.screening.types import ReportType, ScreeningPriority, ScreeningStatus

# =============================================================================
# Request Schemas
# =============================================================================


class AddressInput(BaseModel):
    """Address input for subject."""

    street_address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str = "US"


class SubjectInput(BaseModel):
    """Subject information for screening request.

    Maps to SubjectIdentifiers domain model.
    """

    full_name: str = Field(..., min_length=2, max_length=200, description="Subject's full name")
    first_name: str | None = Field(default=None, max_length=100, description="Subject's first name")
    last_name: str | None = Field(default=None, max_length=100, description="Subject's last name")
    middle_name: str | None = Field(
        default=None, max_length=100, description="Subject's middle name"
    )
    date_of_birth: str | None = Field(default=None, description="Date of birth (YYYY-MM-DD format)")

    # Identifiers
    ssn: str | None = Field(
        default=None, description="Social Security Number (full or last 4 digits)"
    )
    email: str | None = Field(default=None, description="Email address")
    phone: str | None = Field(default=None, description="Phone number")

    # Address
    current_address: AddressInput | None = Field(default=None, description="Current address")

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: str | None) -> str | None:
        """Validate date of birth format."""
        if v is None:
            return v
        try:
            from datetime import datetime

            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("date_of_birth must be in YYYY-MM-DD format") from None


class ScreeningCreateRequest(BaseModel):
    """Request body for initiating a new screening.

    Example:
        {
            "subject": {
                "full_name": "John Smith",
                "date_of_birth": "1985-03-15",
                "ssn": "6789"
            },
            "locale": "US",
            "service_tier": "standard",
            "consent_token": "consent-abc123"
        }
    """

    subject: SubjectInput = Field(..., description="Subject information")
    locale: Locale = Field(default=Locale.US, description="Geographic jurisdiction")
    service_tier: ServiceTier = Field(
        default=ServiceTier.STANDARD, description="Service tier (standard or enhanced)"
    )
    search_degree: SearchDegree = Field(
        default=SearchDegree.D1,
        description="Search depth (D1=subject, D2=connections, D3=extended)",
    )
    vigilance_level: VigilanceLevel = Field(
        default=VigilanceLevel.V0, description="Ongoing monitoring level"
    )
    role_category: RoleCategory = Field(
        default=RoleCategory.STANDARD, description="Job role category for relevance weighting"
    )
    consent_token: str = Field(..., min_length=1, description="Consent verification token")
    report_types: list[ReportType] = Field(
        default_factory=lambda: [ReportType.SUMMARY],
        description="Reports to generate upon completion",
    )
    priority: ScreeningPriority = Field(
        default=ScreeningPriority.NORMAL, description="Processing priority"
    )
    callback_url: str | None = Field(default=None, description="Webhook URL for status updates")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata")

    @field_validator("search_degree")
    @classmethod
    def validate_degree_tier(cls, v: SearchDegree, info: Any) -> SearchDegree:
        """Validate that D3 requires Enhanced tier."""
        # Access other fields through info.data
        tier = info.data.get("service_tier", ServiceTier.STANDARD)
        if v == SearchDegree.D3 and tier != ServiceTier.ENHANCED:
            raise ValueError("D3 search degree requires Enhanced service tier")
        return v


# =============================================================================
# Response Schemas
# =============================================================================


class PhaseResultResponse(BaseModel):
    """Response for a single screening phase."""

    phase_name: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    duration_seconds: float | None
    error_message: str | None = None


class CostSummaryResponse(BaseModel):
    """Cost breakdown response."""

    total_cost: str
    data_provider_cost: str
    ai_model_cost: str
    currency: str = "USD"
    cache_savings: str


class ReportResponse(BaseModel):
    """Generated report response (metadata only, no content)."""

    report_id: UUID
    report_type: ReportType
    format: str
    generated_at: datetime
    size_bytes: int


class ScreeningResponse(BaseModel):
    """Response for a screening request.

    This is the standard response returned by GET and POST screening endpoints.
    """

    screening_id: UUID = Field(..., description="Unique screening identifier")
    status: ScreeningStatus = Field(..., description="Current status")
    created_at: datetime = Field(..., description="When the screening was initiated")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Progress
    progress_percent: int = Field(default=0, ge=0, le=100, description="Completion percentage")
    current_phase: str | None = Field(default=None, description="Current execution phase")

    # Results (when complete)
    risk_score: int | None = Field(default=None, ge=0, le=100, description="Risk score (0-100)")
    risk_level: str | None = Field(
        default=None, description="Risk level (low/moderate/high/critical)"
    )
    recommendation: str | None = Field(
        default=None, description="Recommendation (proceed/review_required/do_not_proceed)"
    )

    # Findings summary
    findings_count: int = Field(default=0, description="Total number of findings")
    critical_findings: int = Field(default=0, description="Number of critical findings")
    high_findings: int = Field(default=0, description="Number of high severity findings")

    # Reports
    reports: list[ReportResponse] = Field(default_factory=list, description="Generated reports")

    # Phases
    phases: list[PhaseResultResponse] = Field(
        default_factory=list, description="Phase execution details"
    )

    # Cost
    cost_summary: CostSummaryResponse | None = Field(default=None, description="Cost breakdown")

    # Error info (when failed)
    error_code: str | None = Field(default=None, description="Error code if failed")
    error_message: str | None = Field(default=None, description="Error message if failed")

    # Links
    report_url: str | None = Field(default=None, description="URL to download report")

    model_config = {
        "json_schema_extra": {
            "example": {
                "screening_id": "019478f2-1234-7000-8000-abcdef123456",
                "status": "complete",
                "created_at": "2026-01-30T12:00:00Z",
                "updated_at": "2026-01-30T12:05:00Z",
                "progress_percent": 100,
                "current_phase": "complete",
                "risk_score": 35,
                "risk_level": "moderate",
                "recommendation": "proceed_with_caution",
                "findings_count": 3,
                "critical_findings": 0,
                "high_findings": 1,
                "reports": [],
                "phases": [],
                "error_code": None,
                "error_message": None,
            }
        }
    }


class ScreeningListResponse(BaseModel):
    """Response for listing screenings."""

    items: list[ScreeningResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class ScreeningCancelResponse(BaseModel):
    """Response for screening cancellation."""

    screening_id: UUID
    status: ScreeningStatus = ScreeningStatus.CANCELLED
    cancelled_at: datetime
    message: str = "Screening cancelled successfully"


# =============================================================================
# Factory Functions
# =============================================================================


def screening_response_from_result(
    result: Any,  # ScreeningResult
    request_time: datetime | None = None,
) -> ScreeningResponse:
    """Convert internal ScreeningResult to API response.

    Args:
        result: ScreeningResult from domain layer.
        request_time: When the request was made (for created_at).

    Returns:
        ScreeningResponse for API.
    """
    # Map phases
    phases = []
    for phase in result.phases:
        phases.append(
            PhaseResultResponse(
                phase_name=phase.phase_name,
                started_at=phase.started_at,
                completed_at=phase.completed_at,
                status=phase.status,
                duration_seconds=phase.duration_seconds,
                error_message=phase.error_message,
            )
        )

    # Map reports
    reports = []
    for report in result.reports:
        reports.append(
            ReportResponse(
                report_id=report.report_id,
                report_type=report.report_type,
                format=report.format,
                generated_at=report.generated_at,
                size_bytes=report.size_bytes,
            )
        )

    # Map cost summary
    cost_summary = None
    if result.cost_summary:
        cost_summary = CostSummaryResponse(
            total_cost=str(result.cost_summary.total_cost),
            data_provider_cost=str(result.cost_summary.data_provider_cost),
            ai_model_cost=str(result.cost_summary.ai_model_cost),
            currency=result.cost_summary.currency,
            cache_savings=str(result.cost_summary.cache_savings),
        )

    # Determine progress percent from status
    progress_map = {
        ScreeningStatus.PENDING: 0,
        ScreeningStatus.VALIDATING: 10,
        ScreeningStatus.IN_PROGRESS: 50,
        ScreeningStatus.ANALYZING: 80,
        ScreeningStatus.GENERATING_REPORT: 90,
        ScreeningStatus.COMPLETE: 100,
        ScreeningStatus.FAILED: 0,
        ScreeningStatus.CANCELLED: 0,
        ScreeningStatus.COMPLIANCE_BLOCKED: 0,
    }

    # Determine current phase
    current_phase = None
    if result.phases:
        current_phase = result.phases[-1].phase_name

    # Convert uuid_utils.UUID to standard uuid.UUID for Pydantic serialization
    screening_id = UUID(str(result.screening_id)) if result.screening_id else None

    return ScreeningResponse(
        screening_id=screening_id,
        status=result.status,
        created_at=result.started_at or request_time or datetime.now(),
        updated_at=result.completed_at or datetime.now(),
        progress_percent=progress_map.get(result.status, 0),
        current_phase=current_phase,
        risk_score=result.risk_score if result.status == ScreeningStatus.COMPLETE else None,
        risk_level=result.risk_level if result.status == ScreeningStatus.COMPLETE else None,
        recommendation=result.recommendation if result.status == ScreeningStatus.COMPLETE else None,
        findings_count=result.findings_count,
        critical_findings=result.critical_findings,
        high_findings=result.high_findings,
        reports=reports,
        phases=phases,
        cost_summary=cost_summary,
        error_code=result.error_code,
        error_message=result.error_message,
    )
