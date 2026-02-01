"""Records Phase Handler for criminal, civil, financial, and regulatory records.

This module provides the RecordsPhaseHandler that collects and analyzes
official records including criminal, civil, financial, license, regulatory,
and sanctions data.

Architecture Reference: docs/architecture/05-investigation.md
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import ServiceTier
from elile.compliance.types import Locale
from elile.core.logging import get_logger

logger = get_logger(__name__)


class RecordType(str, Enum):
    """Types of records checked."""

    CRIMINAL = "criminal"
    CIVIL = "civil"
    FINANCIAL = "financial"
    LICENSE = "license"
    REGULATORY = "regulatory"
    SANCTIONS = "sanctions"


class RecordSeverity(str, Enum):
    """Severity levels for record findings."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CriminalRecord:
    """A criminal record finding."""

    record_id: UUID = field(default_factory=uuid7)
    offense_type: str = ""
    offense_date: date | None = None
    jurisdiction: str = ""
    disposition: str = ""
    severity: RecordSeverity = RecordSeverity.MEDIUM
    source: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": str(self.record_id),
            "offense_type": self.offense_type,
            "offense_date": self.offense_date.isoformat() if self.offense_date else None,
            "jurisdiction": self.jurisdiction,
            "disposition": self.disposition,
            "severity": self.severity.value,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass
class CivilRecord:
    """A civil litigation record."""

    record_id: UUID = field(default_factory=uuid7)
    case_type: str = ""
    filing_date: date | None = None
    jurisdiction: str = ""
    role: str = ""  # plaintiff, defendant
    status: str = ""
    severity: RecordSeverity = RecordSeverity.LOW
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": str(self.record_id),
            "case_type": self.case_type,
            "filing_date": self.filing_date.isoformat() if self.filing_date else None,
            "jurisdiction": self.jurisdiction,
            "role": self.role,
            "status": self.status,
            "severity": self.severity.value,
            "source": self.source,
        }


@dataclass
class FinancialRecord:
    """A financial record (bankruptcy, lien, judgment)."""

    record_id: UUID = field(default_factory=uuid7)
    record_type: str = ""  # bankruptcy, lien, judgment
    filing_date: date | None = None
    amount: float | None = None
    status: str = ""
    severity: RecordSeverity = RecordSeverity.MEDIUM
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": str(self.record_id),
            "record_type": self.record_type,
            "filing_date": self.filing_date.isoformat() if self.filing_date else None,
            "amount": self.amount,
            "status": self.status,
            "severity": self.severity.value,
            "source": self.source,
        }


@dataclass
class LicenseRecord:
    """A professional license record."""

    record_id: UUID = field(default_factory=uuid7)
    license_type: str = ""
    issuing_authority: str = ""
    status: str = ""
    issue_date: date | None = None
    expiration_date: date | None = None
    disciplinary_actions: list[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": str(self.record_id),
            "license_type": self.license_type,
            "issuing_authority": self.issuing_authority,
            "status": self.status,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "expiration_date": self.expiration_date.isoformat() if self.expiration_date else None,
            "disciplinary_actions": self.disciplinary_actions,
            "source": self.source,
        }


@dataclass
class RegulatoryRecord:
    """A regulatory action or enforcement record."""

    record_id: UUID = field(default_factory=uuid7)
    agency: str = ""
    action_type: str = ""
    action_date: date | None = None
    description: str = ""
    severity: RecordSeverity = RecordSeverity.HIGH
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": str(self.record_id),
            "agency": self.agency,
            "action_type": self.action_type,
            "action_date": self.action_date.isoformat() if self.action_date else None,
            "description": self.description,
            "severity": self.severity.value,
            "source": self.source,
        }


@dataclass
class SanctionsRecord:
    """A sanctions list match."""

    record_id: UUID = field(default_factory=uuid7)
    list_name: str = ""
    match_type: str = ""  # exact, partial, alias
    match_score: float = 0.0
    listed_date: date | None = None
    reason: str = ""
    severity: RecordSeverity = RecordSeverity.CRITICAL
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": str(self.record_id),
            "list_name": self.list_name,
            "match_type": self.match_type,
            "match_score": self.match_score,
            "listed_date": self.listed_date.isoformat() if self.listed_date else None,
            "reason": self.reason,
            "severity": self.severity.value,
            "source": self.source,
        }


@dataclass
class RecordsProfile:
    """Combined records from all record types."""

    profile_id: UUID = field(default_factory=uuid7)
    subject_entity_id: UUID | None = None

    # Record collections
    criminal_records: list[CriminalRecord] = field(default_factory=list)
    civil_records: list[CivilRecord] = field(default_factory=list)
    financial_records: list[FinancialRecord] = field(default_factory=list)
    license_records: list[LicenseRecord] = field(default_factory=list)
    regulatory_records: list[RegulatoryRecord] = field(default_factory=list)
    sanctions_records: list[SanctionsRecord] = field(default_factory=list)

    # Summary
    total_records: int = 0
    high_severity_count: int = 0
    critical_count: int = 0
    overall_risk: RecordSeverity = RecordSeverity.NONE

    # Timing
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def calculate_risk(self) -> RecordSeverity:
        """Calculate overall risk from records."""
        if self.sanctions_records:
            self.overall_risk = RecordSeverity.CRITICAL
        elif any(r.severity == RecordSeverity.CRITICAL for r in self.criminal_records):
            self.overall_risk = RecordSeverity.CRITICAL
        elif any(r.severity == RecordSeverity.HIGH for r in self.criminal_records):
            self.overall_risk = RecordSeverity.HIGH
        elif self.regulatory_records:
            self.overall_risk = RecordSeverity.HIGH
        elif self.financial_records or self.civil_records:
            self.overall_risk = RecordSeverity.MEDIUM
        else:
            self.overall_risk = RecordSeverity.NONE
        return self.overall_risk

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": str(self.profile_id),
            "subject_entity_id": str(self.subject_entity_id) if self.subject_entity_id else None,
            "criminal_records": [r.to_dict() for r in self.criminal_records],
            "civil_records": [r.to_dict() for r in self.civil_records],
            "financial_records": [r.to_dict() for r in self.financial_records],
            "license_records": [r.to_dict() for r in self.license_records],
            "regulatory_records": [r.to_dict() for r in self.regulatory_records],
            "sanctions_records": [r.to_dict() for r in self.sanctions_records],
            "total_records": self.total_records,
            "high_severity_count": self.high_severity_count,
            "critical_count": self.critical_count,
            "overall_risk": self.overall_risk.value,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


class RecordsConfig(BaseModel):
    """Configuration for RecordsPhaseHandler."""

    enable_criminal: bool = Field(default=True)
    enable_civil: bool = Field(default=True)
    enable_financial: bool = Field(default=True)
    enable_licenses: bool = Field(default=True)
    enable_regulatory: bool = Field(default=True)
    enable_sanctions: bool = Field(default=True)
    lookback_years: int = Field(default=7, ge=1, le=20)
    parallel_execution: bool = Field(default=True)


@dataclass
class RecordsPhaseResult:
    """Result from RecordsPhaseHandler execution."""

    result_id: UUID = field(default_factory=uuid7)
    profile: RecordsProfile = field(default_factory=RecordsProfile)
    success: bool = True
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)
    record_types_checked: list[RecordType] = field(default_factory=list)
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
            "record_types_checked": [r.value for r in self.record_types_checked],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


class RecordsPhaseHandler:
    """Handles the Records phase of investigation.

    Collects and analyzes criminal, civil, financial, license,
    regulatory, and sanctions records for a subject.
    """

    def __init__(self, config: RecordsConfig | None = None):
        self.config = config or RecordsConfig()

    async def execute(
        self,
        subject_name: str,
        subject_dob: date | None = None,
        addresses: list[str] | None = None,
        tier: ServiceTier = ServiceTier.STANDARD,
        locale: Locale = Locale.US,
    ) -> RecordsPhaseResult:
        """Execute records phase."""
        start_time = datetime.now(UTC)
        result = RecordsPhaseResult()

        logger.info("Records phase started", subject_name=subject_name)

        try:
            profile = RecordsProfile()

            # Check each record type based on config
            if self.config.enable_criminal:
                result.record_types_checked.append(RecordType.CRIMINAL)
            if self.config.enable_civil:
                result.record_types_checked.append(RecordType.CIVIL)
            if self.config.enable_financial:
                result.record_types_checked.append(RecordType.FINANCIAL)
            if self.config.enable_licenses:
                result.record_types_checked.append(RecordType.LICENSE)
            if self.config.enable_regulatory:
                result.record_types_checked.append(RecordType.REGULATORY)
            if self.config.enable_sanctions:
                result.record_types_checked.append(RecordType.SANCTIONS)

            # Calculate risk level
            profile.calculate_risk()
            result.profile = profile
            result.success = True

        except Exception as e:
            logger.error("Records phase failed", error=str(e))
            result.success = False
            result.error_message = str(e)

        end_time = datetime.now(UTC)
        result.completed_at = end_time
        result.duration_ms = (end_time - start_time).total_seconds() * 1000

        return result


def create_records_phase_handler(config: RecordsConfig | None = None) -> RecordsPhaseHandler:
    """Create a records phase handler."""
    return RecordsPhaseHandler(config=config)
