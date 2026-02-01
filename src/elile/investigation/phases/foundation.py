"""Foundation Phase Handler for baseline data collection.

This module provides the FoundationPhaseHandler that establishes the
baseline identity, employment, and education profile for a subject.
This is the first phase of investigation, collecting verified data
that subsequent phases build upon.

The Foundation phase:
1. Verifies identity (name, DOB, SSN, addresses)
2. Verifies employment history
3. Verifies education credentials
4. Creates a baseline profile for downstream phases

Architecture Reference: docs/architecture/05-investigation.md
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import InformationType, ServiceTier
from elile.compliance.types import Locale
from elile.core.logging import get_logger

logger = get_logger(__name__)


class VerificationStatus(str, Enum):
    """Status of verification for a data element."""

    VERIFIED = "verified"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    CONFLICTING = "conflicting"
    NOT_FOUND = "not_found"
    PENDING = "pending"


@dataclass
class IdentityBaseline:
    """Baseline identity verification data.

    Contains verified identity information including name variants,
    date of birth, SSN verification, and address history.
    """

    baseline_id: UUID = field(default_factory=uuid7)

    # Name verification
    legal_name: str = ""
    name_variants: list[str] = field(default_factory=list)
    name_status: VerificationStatus = VerificationStatus.PENDING

    # DOB verification
    date_of_birth: date | None = None
    dob_status: VerificationStatus = VerificationStatus.PENDING

    # SSN verification (last 4 only for privacy)
    ssn_last4: str | None = None
    ssn_status: VerificationStatus = VerificationStatus.PENDING

    # Address history
    current_address: str | None = None
    address_history: list[str] = field(default_factory=list)
    address_status: VerificationStatus = VerificationStatus.PENDING

    # Contact information
    phone_numbers: list[str] = field(default_factory=list)
    email_addresses: list[str] = field(default_factory=list)

    # Verification metadata
    sources_checked: list[str] = field(default_factory=list)
    confidence: float = 0.0
    verified_at: datetime | None = None

    @property
    def is_verified(self) -> bool:
        """Check if identity is sufficiently verified."""
        required_verified = [self.name_status, self.dob_status]
        return all(s == VerificationStatus.VERIFIED for s in required_verified)

    @property
    def overall_status(self) -> VerificationStatus:
        """Get overall identity verification status."""
        statuses = [self.name_status, self.dob_status, self.ssn_status, self.address_status]

        if all(s == VerificationStatus.VERIFIED for s in statuses):
            return VerificationStatus.VERIFIED
        elif VerificationStatus.CONFLICTING in statuses:
            return VerificationStatus.CONFLICTING
        elif any(s == VerificationStatus.VERIFIED for s in statuses):
            return VerificationStatus.PARTIAL
        elif all(s == VerificationStatus.NOT_FOUND for s in statuses):
            return VerificationStatus.NOT_FOUND
        else:
            return VerificationStatus.UNVERIFIED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "baseline_id": str(self.baseline_id),
            "legal_name": self.legal_name,
            "name_variants": self.name_variants,
            "name_status": self.name_status.value,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "dob_status": self.dob_status.value,
            "ssn_last4": self.ssn_last4,
            "ssn_status": self.ssn_status.value,
            "current_address": self.current_address,
            "address_history": self.address_history,
            "address_status": self.address_status.value,
            "phone_numbers": self.phone_numbers,
            "email_addresses": self.email_addresses,
            "sources_checked": self.sources_checked,
            "confidence": self.confidence,
            "overall_status": self.overall_status.value,
            "is_verified": self.is_verified,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }


@dataclass
class EmploymentBaseline:
    """Baseline employment verification data.

    Contains verified employment history including employers,
    positions, dates, and verification status.
    """

    baseline_id: UUID = field(default_factory=uuid7)

    # Employment records
    employers: list[dict[str, Any]] = field(default_factory=list)
    current_employer: str | None = None
    current_title: str | None = None

    # Employment gaps
    gaps_identified: list[dict[str, Any]] = field(default_factory=list)
    total_years_verified: float = 0.0

    # Verification status
    status: VerificationStatus = VerificationStatus.PENDING
    sources_checked: list[str] = field(default_factory=list)
    confidence: float = 0.0
    verified_at: datetime | None = None

    def add_employer(
        self,
        employer_name: str,
        title: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        verified: bool = False,
        source: str = "",
    ) -> None:
        """Add an employer to the history."""
        self.employers.append(
            {
                "employer_name": employer_name,
                "title": title,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "verified": verified,
                "source": source,
            }
        )

    @property
    def employer_count(self) -> int:
        """Number of employers in history."""
        return len(self.employers)

    @property
    def verified_employer_count(self) -> int:
        """Number of verified employers."""
        return sum(1 for e in self.employers if e.get("verified", False))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "baseline_id": str(self.baseline_id),
            "employers": self.employers,
            "current_employer": self.current_employer,
            "current_title": self.current_title,
            "gaps_identified": self.gaps_identified,
            "total_years_verified": self.total_years_verified,
            "status": self.status.value,
            "employer_count": self.employer_count,
            "verified_employer_count": self.verified_employer_count,
            "sources_checked": self.sources_checked,
            "confidence": self.confidence,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }


@dataclass
class EducationBaseline:
    """Baseline education verification data.

    Contains verified education credentials including institutions,
    degrees, dates, and verification status.
    """

    baseline_id: UUID = field(default_factory=uuid7)

    # Education records
    credentials: list[dict[str, Any]] = field(default_factory=list)
    highest_degree: str | None = None
    highest_degree_institution: str | None = None

    # Verification status
    status: VerificationStatus = VerificationStatus.PENDING
    sources_checked: list[str] = field(default_factory=list)
    confidence: float = 0.0
    verified_at: datetime | None = None

    def add_credential(
        self,
        institution: str,
        degree: str | None = None,
        field_of_study: str | None = None,
        graduation_date: date | None = None,
        verified: bool = False,
        source: str = "",
    ) -> None:
        """Add an education credential."""
        self.credentials.append(
            {
                "institution": institution,
                "degree": degree,
                "field_of_study": field_of_study,
                "graduation_date": graduation_date.isoformat() if graduation_date else None,
                "verified": verified,
                "source": source,
            }
        )

    @property
    def credential_count(self) -> int:
        """Number of credentials."""
        return len(self.credentials)

    @property
    def verified_credential_count(self) -> int:
        """Number of verified credentials."""
        return sum(1 for c in self.credentials if c.get("verified", False))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "baseline_id": str(self.baseline_id),
            "credentials": self.credentials,
            "highest_degree": self.highest_degree,
            "highest_degree_institution": self.highest_degree_institution,
            "status": self.status.value,
            "credential_count": self.credential_count,
            "verified_credential_count": self.verified_credential_count,
            "sources_checked": self.sources_checked,
            "confidence": self.confidence,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }


@dataclass
class BaselineProfile:
    """Combined baseline profile from Foundation phase.

    Contains identity, employment, and education baselines with
    aggregate verification status and confidence.
    """

    profile_id: UUID = field(default_factory=uuid7)
    subject_entity_id: UUID | None = None

    # Component baselines
    identity: IdentityBaseline = field(default_factory=IdentityBaseline)
    employment: EmploymentBaseline = field(default_factory=EmploymentBaseline)
    education: EducationBaseline = field(default_factory=EducationBaseline)

    # Aggregate status
    overall_confidence: float = 0.0
    types_verified: list[InformationType] = field(default_factory=list)
    types_pending: list[InformationType] = field(default_factory=list)

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def calculate_confidence(self) -> float:
        """Calculate aggregate confidence from components."""
        confidences = [self.identity.confidence, self.employment.confidence, self.education.confidence]
        non_zero = [c for c in confidences if c > 0]
        if non_zero:
            self.overall_confidence = sum(non_zero) / len(non_zero)
        return self.overall_confidence

    @property
    def is_complete(self) -> bool:
        """Check if all foundation types are verified."""
        return (
            self.identity.is_verified
            and self.employment.status == VerificationStatus.VERIFIED
            and self.education.status == VerificationStatus.VERIFIED
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "profile_id": str(self.profile_id),
            "subject_entity_id": str(self.subject_entity_id) if self.subject_entity_id else None,
            "identity": self.identity.to_dict(),
            "employment": self.employment.to_dict(),
            "education": self.education.to_dict(),
            "overall_confidence": self.overall_confidence,
            "types_verified": [t.value for t in self.types_verified],
            "types_pending": [t.value for t in self.types_pending],
            "is_complete": self.is_complete,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class FoundationConfig(BaseModel):
    """Configuration for FoundationPhaseHandler."""

    # Verification requirements
    require_identity_verification: bool = Field(default=True)
    require_employment_verification: bool = Field(default=True)
    require_education_verification: bool = Field(default=True)

    # Lookback periods
    employment_lookback_years: int = Field(default=7, ge=1, le=20)
    education_lookback_years: int = Field(default=10, ge=1, le=30)

    # Confidence thresholds
    min_identity_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    min_employment_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    min_education_confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    # Data source settings
    max_sources_per_type: int = Field(default=3, ge=1, le=10)
    include_secondary_sources: bool = Field(default=True)


@dataclass
class FoundationPhaseResult:
    """Result from FoundationPhaseHandler execution."""

    result_id: UUID = field(default_factory=uuid7)
    profile: BaselineProfile = field(default_factory=BaselineProfile)

    # Execution metadata
    success: bool = True
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)

    # Statistics
    queries_executed: int = 0
    sources_checked: int = 0
    facts_extracted: int = 0

    # Type completion
    identity_complete: bool = False
    employment_complete: bool = False
    education_complete: bool = False

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: float = 0.0

    @property
    def all_complete(self) -> bool:
        """Check if all foundation types are complete."""
        return self.identity_complete and self.employment_complete and self.education_complete

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "profile": self.profile.to_dict(),
            "success": self.success,
            "error_message": self.error_message,
            "warnings": self.warnings,
            "queries_executed": self.queries_executed,
            "sources_checked": self.sources_checked,
            "facts_extracted": self.facts_extracted,
            "identity_complete": self.identity_complete,
            "employment_complete": self.employment_complete,
            "education_complete": self.education_complete,
            "all_complete": self.all_complete,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


class FoundationPhaseHandler:
    """Handles the Foundation phase of investigation.

    The Foundation phase establishes the baseline identity, employment,
    and education profile for a subject. This data is used by all
    subsequent phases to enhance search accuracy and verify findings.

    The phase executes sequentially:
    1. Identity verification (name, DOB, SSN, addresses)
    2. Employment verification (employers, titles, dates)
    3. Education verification (degrees, institutions, dates)

    Example:
        ```python
        handler = FoundationPhaseHandler()
        result = await handler.execute(
            subject_name="John Smith",
            subject_dob=date(1985, 3, 15),
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )
        print(f"Identity verified: {result.identity_complete}")
        print(f"Overall confidence: {result.profile.overall_confidence}")
        ```
    """

    def __init__(self, config: FoundationConfig | None = None):
        """Initialize the foundation phase handler.

        Args:
            config: Handler configuration.
        """
        self.config = config or FoundationConfig()

    async def execute(
        self,
        subject_name: str,
        subject_dob: date | None = None,
        subject_ssn_last4: str | None = None,
        tier: ServiceTier = ServiceTier.STANDARD,
        locale: Locale = Locale.US,
    ) -> FoundationPhaseResult:
        """Execute the Foundation phase.

        Args:
            subject_name: Subject's legal name.
            subject_dob: Subject's date of birth.
            subject_ssn_last4: Last 4 digits of SSN (US only).
            tier: Service tier for provider selection.
            locale: Subject locale for compliance.

        Returns:
            FoundationPhaseResult with baseline profile.
        """
        start_time = datetime.now(UTC)
        result = FoundationPhaseResult()

        logger.info(
            "Foundation phase started",
            subject_name=subject_name,
            tier=tier.value,
            locale=locale.value,
        )

        try:
            # Step 1: Identity verification
            identity = await self._verify_identity(
                subject_name=subject_name,
                subject_dob=subject_dob,
                subject_ssn_last4=subject_ssn_last4,
                locale=locale,
            )
            result.profile.identity = identity
            result.identity_complete = identity.is_verified

            # Step 2: Employment verification
            if self.config.require_employment_verification:
                employment = await self._verify_employment(
                    subject_name=subject_name,
                    identity=identity,
                    locale=locale,
                )
                result.profile.employment = employment
                result.employment_complete = employment.status == VerificationStatus.VERIFIED
            else:
                result.employment_complete = True

            # Step 3: Education verification
            if self.config.require_education_verification:
                education = await self._verify_education(
                    subject_name=subject_name,
                    identity=identity,
                    locale=locale,
                )
                result.profile.education = education
                result.education_complete = education.status == VerificationStatus.VERIFIED
            else:
                result.education_complete = True

            # Calculate aggregate confidence
            result.profile.calculate_confidence()

            # Update type tracking
            if result.identity_complete:
                result.profile.types_verified.append(InformationType.IDENTITY)
            else:
                result.profile.types_pending.append(InformationType.IDENTITY)

            if result.employment_complete:
                result.profile.types_verified.append(InformationType.EMPLOYMENT)
            else:
                result.profile.types_pending.append(InformationType.EMPLOYMENT)

            if result.education_complete:
                result.profile.types_verified.append(InformationType.EDUCATION)
            else:
                result.profile.types_pending.append(InformationType.EDUCATION)

            result.success = True

        except Exception as e:
            logger.error("Foundation phase failed", error=str(e))
            result.success = False
            result.error_message = str(e)

        end_time = datetime.now(UTC)
        result.completed_at = end_time
        result.duration_ms = (end_time - start_time).total_seconds() * 1000
        result.profile.completed_at = end_time

        logger.info(
            "Foundation phase completed",
            success=result.success,
            identity_complete=result.identity_complete,
            employment_complete=result.employment_complete,
            education_complete=result.education_complete,
            confidence=result.profile.overall_confidence,
        )

        return result

    async def _verify_identity(
        self,
        subject_name: str,
        subject_dob: date | None,
        subject_ssn_last4: str | None,
        locale: Locale,
    ) -> IdentityBaseline:
        """Verify subject identity.

        Args:
            subject_name: Subject's legal name.
            subject_dob: Date of birth.
            subject_ssn_last4: Last 4 SSN digits.
            locale: Subject locale.

        Returns:
            IdentityBaseline with verification results.
        """
        identity = IdentityBaseline()
        identity.legal_name = subject_name

        # Set provided data
        if subject_dob:
            identity.date_of_birth = subject_dob
            identity.dob_status = VerificationStatus.VERIFIED
        else:
            identity.dob_status = VerificationStatus.PENDING

        if subject_ssn_last4:
            identity.ssn_last4 = subject_ssn_last4
            identity.ssn_status = VerificationStatus.VERIFIED
        else:
            identity.ssn_status = VerificationStatus.PENDING

        # Name is provided, mark as verified
        identity.name_status = VerificationStatus.VERIFIED

        # Address status pending (would be filled by actual queries)
        identity.address_status = VerificationStatus.PENDING

        # Calculate confidence based on what's verified
        verified_count = sum(
            1
            for s in [identity.name_status, identity.dob_status, identity.ssn_status]
            if s == VerificationStatus.VERIFIED
        )
        identity.confidence = verified_count / 3.0

        identity.verified_at = datetime.now(UTC)
        identity.sources_checked = ["input_data"]

        return identity

    async def _verify_employment(
        self,
        subject_name: str,
        identity: IdentityBaseline,
        locale: Locale,
    ) -> EmploymentBaseline:
        """Verify employment history.

        Args:
            subject_name: Subject's name.
            identity: Verified identity baseline.
            locale: Subject locale.

        Returns:
            EmploymentBaseline with verification results.
        """
        employment = EmploymentBaseline()

        # Stub implementation - would execute actual queries
        # For now, mark as pending
        employment.status = VerificationStatus.PENDING
        employment.confidence = 0.0
        employment.sources_checked = []

        return employment

    async def _verify_education(
        self,
        subject_name: str,
        identity: IdentityBaseline,
        locale: Locale,
    ) -> EducationBaseline:
        """Verify education credentials.

        Args:
            subject_name: Subject's name.
            identity: Verified identity baseline.
            locale: Subject locale.

        Returns:
            EducationBaseline with verification results.
        """
        education = EducationBaseline()

        # Stub implementation - would execute actual queries
        # For now, mark as pending
        education.status = VerificationStatus.PENDING
        education.confidence = 0.0
        education.sources_checked = []

        return education


def create_foundation_phase_handler(
    config: FoundationConfig | None = None,
) -> FoundationPhaseHandler:
    """Create a foundation phase handler.

    Args:
        config: Optional handler configuration.

    Returns:
        Configured FoundationPhaseHandler.
    """
    return FoundationPhaseHandler(config=config)
