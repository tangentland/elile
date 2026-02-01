"""Core types and models for the screening service.

This module defines the data models for screening requests, results, and status
tracking used throughout the screening workflow.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from uuid_utils import uuid7

from elile.agent.state import SearchDegree, ServiceTier, VigilanceLevel
from elile.compliance.types import Locale, RoleCategory
from elile.entity.types import SubjectIdentifiers


# =============================================================================
# Enums
# =============================================================================


class ScreeningStatus(str, Enum):
    """Status of a screening request."""

    PENDING = "pending"  # Request received, not yet started
    VALIDATING = "validating"  # Validating request and compliance
    IN_PROGRESS = "in_progress"  # Investigation running
    ANALYZING = "analyzing"  # Risk analysis in progress
    GENERATING_REPORT = "generating_report"  # Report generation
    COMPLETE = "complete"  # Successfully completed
    FAILED = "failed"  # Failed due to error
    CANCELLED = "cancelled"  # Cancelled by user or system
    COMPLIANCE_BLOCKED = "compliance_blocked"  # Blocked by compliance rules


class ReportType(str, Enum):
    """Types of reports that can be generated."""

    SUMMARY = "summary"  # HR Manager - risk level and recommendation
    AUDIT = "audit"  # Compliance - data sources and consent trail
    INVESTIGATION = "investigation"  # Security - detailed findings
    CASE_FILE = "case_file"  # Investigator - complete raw data
    DISCLOSURE = "disclosure"  # Subject - FCRA compliant summary
    PORTFOLIO = "portfolio"  # Executive - aggregate metrics


class ScreeningPriority(str, Enum):
    """Priority level for screening processing."""

    LOW = "low"  # Normal queue processing
    NORMAL = "normal"  # Standard priority
    HIGH = "high"  # Expedited processing
    URGENT = "urgent"  # Immediate processing


# =============================================================================
# Request Models
# =============================================================================


class ScreeningRequest(BaseModel):
    """Request to initiate a screening investigation.

    Contains all information needed to execute a complete background screening.

    Attributes:
        screening_id: Unique identifier for this screening.
        tenant_id: Tenant requesting the screening.
        subject: Subject identifiers (name, DOB, SSN, etc.).
        locale: Geographic jurisdiction for compliance rules.
        service_tier: Standard or Enhanced tier.
        search_degree: D1 (subject only), D2 (connections), D3 (extended network).
        vigilance_level: Ongoing monitoring frequency.
        role_category: Job role category for relevance weighting.
        consent_token: Token proving subject consent was obtained.
        report_types: Reports to generate upon completion.
        priority: Processing priority.
        requested_by: Actor who initiated the screening.
        metadata: Additional request metadata.
        requested_at: When the request was submitted.
    """

    screening_id: UUID = Field(default_factory=uuid7)
    tenant_id: UUID
    subject: SubjectIdentifiers
    locale: Locale
    service_tier: ServiceTier = ServiceTier.STANDARD
    search_degree: SearchDegree = SearchDegree.D1
    vigilance_level: VigilanceLevel = VigilanceLevel.V0
    role_category: RoleCategory = RoleCategory.STANDARD
    consent_token: str
    report_types: list[ReportType] = Field(default_factory=lambda: [ReportType.SUMMARY])
    priority: ScreeningPriority = ScreeningPriority.NORMAL
    requested_by: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def model_post_init(self, __context: Any) -> None:
        """Validate request constraints after initialization."""
        # D3 requires Enhanced tier
        if self.search_degree == SearchDegree.D3 and self.service_tier != ServiceTier.ENHANCED:
            raise ValueError("D3 search degree requires Enhanced service tier")


class ScreeningRequestCreate(BaseModel):
    """Input model for creating a new screening request.

    This is a simpler version without auto-generated fields.
    """

    tenant_id: UUID
    subject: SubjectIdentifiers
    locale: Locale
    service_tier: ServiceTier = ServiceTier.STANDARD
    search_degree: SearchDegree = SearchDegree.D1
    vigilance_level: VigilanceLevel = VigilanceLevel.V0
    role_category: RoleCategory = RoleCategory.STANDARD
    consent_token: str
    report_types: list[ReportType] = Field(default_factory=lambda: [ReportType.SUMMARY])
    priority: ScreeningPriority = ScreeningPriority.NORMAL
    requested_by: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_screening_request(self) -> ScreeningRequest:
        """Convert to full ScreeningRequest with generated fields."""
        return ScreeningRequest(
            tenant_id=self.tenant_id,
            subject=self.subject,
            locale=self.locale,
            service_tier=self.service_tier,
            search_degree=self.search_degree,
            vigilance_level=self.vigilance_level,
            role_category=self.role_category,
            consent_token=self.consent_token,
            report_types=self.report_types,
            priority=self.priority,
            requested_by=self.requested_by,
            metadata=self.metadata,
        )


# =============================================================================
# Result Models
# =============================================================================


@dataclass
class ScreeningPhaseResult:
    """Result from a single phase of the screening process.

    Tracks timing and outcome for each phase (validation, investigation, analysis, etc.).
    """

    phase_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: str = "pending"
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def complete(self, status: str = "complete", error: str | None = None) -> None:
        """Mark phase as complete."""
        self.completed_at = datetime.now(UTC)
        self.status = status
        self.error_message = error

    @property
    def duration_seconds(self) -> float | None:
        """Get phase duration in seconds."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "phase_name": self.phase_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "details": self.details,
        }


@dataclass
class ScreeningCostSummary:
    """Cost breakdown for a screening."""

    total_cost: Decimal = Decimal("0.00")
    data_provider_cost: Decimal = Decimal("0.00")
    ai_model_cost: Decimal = Decimal("0.00")
    storage_cost: Decimal = Decimal("0.00")
    currency: str = "USD"
    cost_by_provider: dict[str, Decimal] = field(default_factory=dict)
    cost_by_check_type: dict[str, Decimal] = field(default_factory=dict)
    cache_savings: Decimal = Decimal("0.00")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_cost": str(self.total_cost),
            "data_provider_cost": str(self.data_provider_cost),
            "ai_model_cost": str(self.ai_model_cost),
            "storage_cost": str(self.storage_cost),
            "currency": self.currency,
            "cost_by_provider": {k: str(v) for k, v in self.cost_by_provider.items()},
            "cost_by_check_type": {k: str(v) for k, v in self.cost_by_check_type.items()},
            "cache_savings": str(self.cache_savings),
        }


@dataclass
class GeneratedReport:
    """A generated report for the screening."""

    report_id: UUID = field(default_factory=uuid7)
    report_type: ReportType = ReportType.SUMMARY
    format: str = "pdf"  # pdf, html, json
    content: bytes = field(default_factory=bytes)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    size_bytes: int = 0
    checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (without content bytes)."""
        return {
            "report_id": str(self.report_id),
            "report_type": self.report_type.value,
            "format": self.format,
            "generated_at": self.generated_at.isoformat(),
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
        }


@dataclass
class ScreeningResult:
    """Complete result of a screening investigation.

    Contains all outputs from the screening process including risk assessment,
    generated reports, cost tracking, and detailed phase results.
    """

    result_id: UUID = field(default_factory=uuid7)
    screening_id: UUID = field(default_factory=uuid7)
    tenant_id: UUID | None = None
    entity_id: UUID | None = None

    # Status
    status: ScreeningStatus = ScreeningStatus.PENDING
    error_message: str | None = None
    error_code: str | None = None

    # Risk assessment ID (references ComprehensiveRiskAssessment)
    risk_assessment_id: UUID | None = None
    risk_score: int = 0
    risk_level: str = "low"
    recommendation: str = "proceed"

    # Reports
    reports: list[GeneratedReport] = field(default_factory=list)

    # Phase tracking
    phases: list[ScreeningPhaseResult] = field(default_factory=list)

    # Cost tracking
    cost_summary: ScreeningCostSummary = field(default_factory=ScreeningCostSummary)

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Statistics
    findings_count: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    data_sources_queried: int = 0
    queries_executed: int = 0

    def add_phase(self, phase_name: str) -> ScreeningPhaseResult:
        """Add a new phase and return it for tracking."""
        phase = ScreeningPhaseResult(phase_name=phase_name)
        self.phases.append(phase)
        return phase

    def get_phase(self, phase_name: str) -> ScreeningPhaseResult | None:
        """Get a phase by name."""
        for phase in self.phases:
            if phase.phase_name == phase_name:
                return phase
        return None

    @property
    def duration_seconds(self) -> float | None:
        """Get total screening duration in seconds."""
        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "screening_id": str(self.screening_id),
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "status": self.status.value,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "risk_assessment_id": str(self.risk_assessment_id) if self.risk_assessment_id else None,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "recommendation": self.recommendation,
            "reports": [r.to_dict() for r in self.reports],
            "phases": [p.to_dict() for p in self.phases],
            "cost_summary": self.cost_summary.to_dict(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "findings_count": self.findings_count,
            "critical_findings": self.critical_findings,
            "high_findings": self.high_findings,
            "data_sources_queried": self.data_sources_queried,
            "queries_executed": self.queries_executed,
        }


# =============================================================================
# Error Models
# =============================================================================


class ScreeningError(Exception):
    """Base exception for screening errors."""

    def __init__(
        self,
        message: str,
        code: str = "SCREENING_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class ScreeningValidationError(ScreeningError):
    """Error during request validation."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class ScreeningComplianceError(ScreeningError):
    """Error due to compliance rule violation."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="COMPLIANCE_ERROR", details=details)


class ScreeningExecutionError(ScreeningError):
    """Error during screening execution."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="EXECUTION_ERROR", details=details)
