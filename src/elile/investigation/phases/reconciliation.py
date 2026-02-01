"""Reconciliation Phase Handler for cross-source conflict resolution.

This module provides the ReconciliationPhaseHandler that reconciles
findings across all data sources, resolves conflicts, and creates
a consolidated profile.

Architecture Reference: docs/architecture/05-investigation.md
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import InformationType
from elile.core.logging import get_logger

logger = get_logger(__name__)


class InconsistencyType(str, Enum):
    """Types of data inconsistencies."""

    DATE_MISMATCH = "date_mismatch"
    NAME_MISMATCH = "name_mismatch"
    LOCATION_MISMATCH = "location_mismatch"
    EMPLOYMENT_GAP = "employment_gap"
    CONFLICTING_RECORDS = "conflicting_records"
    MISSING_DATA = "missing_data"
    SOURCE_DISAGREEMENT = "source_disagreement"


class ResolutionStatus(str, Enum):
    """Status of conflict resolution."""

    PENDING = "pending"
    RESOLVED = "resolved"
    UNRESOLVABLE = "unresolvable"
    ESCALATED = "escalated"


class DeceptionRiskLevel(str, Enum):
    """Risk level for potential deception."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Inconsistency:
    """An inconsistency found between data sources."""

    inconsistency_id: UUID = field(default_factory=uuid7)
    inconsistency_type: InconsistencyType = InconsistencyType.SOURCE_DISAGREEMENT
    info_type: InformationType | None = None
    field_name: str = ""
    source_a: str = ""
    value_a: Any = None
    source_b: str = ""
    value_b: Any = None
    severity: str = "medium"
    description: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "inconsistency_id": str(self.inconsistency_id),
            "inconsistency_type": self.inconsistency_type.value,
            "info_type": self.info_type.value if self.info_type else None,
            "field_name": self.field_name,
            "source_a": self.source_a,
            "value_a": str(self.value_a) if self.value_a else None,
            "source_b": self.source_b,
            "value_b": str(self.value_b) if self.value_b else None,
            "severity": self.severity,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class ConflictResolution:
    """Resolution of a data conflict."""

    resolution_id: UUID = field(default_factory=uuid7)
    inconsistency_id: UUID | None = None
    status: ResolutionStatus = ResolutionStatus.PENDING
    resolved_value: Any = None
    resolution_method: str = ""
    confidence: float = 0.0
    notes: str = ""
    resolved_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution_id": str(self.resolution_id),
            "inconsistency_id": str(self.inconsistency_id) if self.inconsistency_id else None,
            "status": self.status.value,
            "resolved_value": str(self.resolved_value) if self.resolved_value else None,
            "resolution_method": self.resolution_method,
            "confidence": self.confidence,
            "notes": self.notes,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class DeceptionAnalysis:
    """Analysis of potential deception indicators."""

    analysis_id: UUID = field(default_factory=uuid7)
    risk_level: DeceptionRiskLevel = DeceptionRiskLevel.NONE
    indicators: list[str] = field(default_factory=list)
    inconsistency_count: int = 0
    unresolved_count: int = 0
    pattern_detected: bool = False
    pattern_description: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": str(self.analysis_id),
            "risk_level": self.risk_level.value,
            "indicators": self.indicators,
            "inconsistency_count": self.inconsistency_count,
            "unresolved_count": self.unresolved_count,
            "pattern_detected": self.pattern_detected,
            "pattern_description": self.pattern_description,
            "confidence": self.confidence,
        }


@dataclass
class ReconciliationProfile:
    """Consolidated profile after reconciliation."""

    profile_id: UUID = field(default_factory=uuid7)
    subject_entity_id: UUID | None = None

    # Inconsistencies
    inconsistencies: list[Inconsistency] = field(default_factory=list)
    resolutions: list[ConflictResolution] = field(default_factory=list)

    # Deception analysis
    deception_analysis: DeceptionAnalysis = field(default_factory=DeceptionAnalysis)

    # Summary
    total_inconsistencies: int = 0
    resolved_count: int = 0
    unresolved_count: int = 0
    confidence_score: float = 0.0

    # Timing
    reconciled_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def calculate_confidence(self) -> float:
        """Calculate reconciliation confidence."""
        if self.total_inconsistencies == 0:
            self.confidence_score = 1.0
        else:
            self.confidence_score = self.resolved_count / self.total_inconsistencies
        return self.confidence_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": str(self.profile_id),
            "subject_entity_id": str(self.subject_entity_id) if self.subject_entity_id else None,
            "inconsistencies": [i.to_dict() for i in self.inconsistencies],
            "resolutions": [r.to_dict() for r in self.resolutions],
            "deception_analysis": self.deception_analysis.to_dict(),
            "total_inconsistencies": self.total_inconsistencies,
            "resolved_count": self.resolved_count,
            "unresolved_count": self.unresolved_count,
            "confidence_score": self.confidence_score,
            "reconciled_at": self.reconciled_at.isoformat(),
        }


class ReconciliationConfig(BaseModel):
    """Configuration for ReconciliationPhaseHandler."""

    auto_resolve_minor: bool = Field(default=True)
    require_human_review: bool = Field(default=False)
    deception_threshold: int = Field(default=3, ge=1, le=10)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


@dataclass
class ReconciliationPhaseResult:
    """Result from ReconciliationPhaseHandler execution."""

    result_id: UUID = field(default_factory=uuid7)
    profile: ReconciliationProfile = field(default_factory=ReconciliationProfile)
    success: bool = True
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)
    requires_review: bool = False
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": str(self.result_id),
            "profile": self.profile.to_dict(),
            "success": self.success,
            "error_message": self.error_message,
            "warnings": self.warnings,
            "requires_review": self.requires_review,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


class ReconciliationPhaseHandler:
    """Handles the Reconciliation phase of investigation.

    Reconciles findings across all phases, resolves conflicts,
    and analyzes for potential deception patterns.
    """

    def __init__(self, config: ReconciliationConfig | None = None):
        self.config = config or ReconciliationConfig()

    async def execute(
        self,
        foundation_data: dict[str, Any] | None = None,
        records_data: dict[str, Any] | None = None,
        intelligence_data: dict[str, Any] | None = None,
        network_data: dict[str, Any] | None = None,
    ) -> ReconciliationPhaseResult:
        """Execute reconciliation phase."""
        start_time = datetime.now(UTC)
        result = ReconciliationPhaseResult()

        logger.info("Reconciliation phase started")

        try:
            profile = ReconciliationProfile()

            # Stub: Would analyze all input data for inconsistencies
            profile.total_inconsistencies = 0
            profile.resolved_count = 0
            profile.unresolved_count = 0
            profile.calculate_confidence()

            # Check if review required
            if self.config.require_human_review and profile.unresolved_count > 0:
                result.requires_review = True

            result.profile = profile
            result.success = True

        except Exception as e:
            logger.error("Reconciliation phase failed", error=str(e))
            result.success = False
            result.error_message = str(e)

        end_time = datetime.now(UTC)
        result.completed_at = end_time
        result.duration_ms = (end_time - start_time).total_seconds() * 1000

        return result


def create_reconciliation_phase_handler(
    config: ReconciliationConfig | None = None,
) -> ReconciliationPhaseHandler:
    """Create a reconciliation phase handler."""
    return ReconciliationPhaseHandler(config=config)
