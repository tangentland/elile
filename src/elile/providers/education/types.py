"""Type definitions for education verification.

This module defines the core types for education verification including
degree types, institution types, and verification results.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DegreeType(str, Enum):
    """Types of academic degrees."""

    # Undergraduate
    ASSOCIATE = "associate"  # Associate degree (AA, AS, AAS)
    BACHELOR = "bachelor"  # Bachelor's degree (BA, BS, BFA)

    # Graduate
    MASTER = "master"  # Master's degree (MA, MS, MBA, MFA)
    DOCTORATE = "doctorate"  # Doctoral degree (PhD, EdD, MD, JD)

    # Professional
    PROFESSIONAL = "professional"  # Professional degree (MD, JD, DDS)

    # Certifications
    CERTIFICATE = "certificate"  # Certificate programs
    DIPLOMA = "diploma"  # Diploma programs

    # Other
    NON_DEGREE = "non_degree"  # Attended but no degree
    UNKNOWN = "unknown"  # Type unknown


class InstitutionType(str, Enum):
    """Types of educational institutions."""

    UNIVERSITY = "university"
    COLLEGE = "college"
    COMMUNITY_COLLEGE = "community_college"
    TECHNICAL_SCHOOL = "technical_school"
    TRADE_SCHOOL = "trade_school"
    GRADUATE_SCHOOL = "graduate_school"
    PROFESSIONAL_SCHOOL = "professional_school"
    ONLINE_UNIVERSITY = "online_university"
    FOREIGN_INSTITUTION = "foreign_institution"
    UNKNOWN = "unknown"


class AccreditationType(str, Enum):
    """Types of accreditation."""

    # Regional (US)
    REGIONAL_HLC = "regional_hlc"  # Higher Learning Commission
    REGIONAL_MSCHE = "regional_msche"  # Middle States Commission
    REGIONAL_NECHE = "regional_neche"  # New England Commission
    REGIONAL_NWCCU = "regional_nwccu"  # Northwest Commission
    REGIONAL_SACSCOC = "regional_sacscoc"  # Southern Association
    REGIONAL_WASC = "regional_wasc"  # Western Association

    # National (US)
    NATIONAL = "national"  # National accreditation
    PROGRAMMATIC = "programmatic"  # Program-specific

    # International
    INTERNATIONAL = "international"  # Foreign accreditation

    # Status
    UNACCREDITED = "unaccredited"  # Not accredited
    REVOKED = "revoked"  # Accreditation revoked
    PENDING = "pending"  # Accreditation pending
    UNKNOWN = "unknown"  # Status unknown


class VerificationStatus(str, Enum):
    """Status of education verification."""

    VERIFIED = "verified"  # Education verified as claimed
    PARTIAL_MATCH = "partial_match"  # Some details match, some differ
    NOT_VERIFIED = "not_verified"  # Could not verify
    DISCREPANCY = "discrepancy"  # Information doesn't match
    NO_RECORD = "no_record"  # No record found
    DIPLOMA_MILL = "diploma_mill"  # Institution is a diploma mill
    PENDING = "pending"  # Verification in progress
    UNABLE_TO_VERIFY = "unable_to_verify"  # Institution unresponsive


class MatchConfidence(str, Enum):
    """Confidence level of institution/degree match."""

    EXACT = "exact"  # Exact match
    HIGH = "high"  # High confidence match
    MEDIUM = "medium"  # Medium confidence
    LOW = "low"  # Low confidence
    NO_MATCH = "no_match"  # No match found


class Institution(BaseModel):
    """An educational institution.

    Attributes:
        institution_id: Unique identifier for the institution.
        name: Official institution name.
        aliases: Alternative names and abbreviations.
        type: Type of institution.
        city: City location.
        state_province: State or province.
        country: Country code (ISO 3166-1 alpha-2).
        accreditation: Primary accreditation type.
        accreditor_name: Name of accrediting body.
        ope_id: US Office of Postsecondary Education ID.
        ipeds_id: US Integrated Postsecondary Education Data System ID.
        nsc_code: National Student Clearinghouse code.
        is_active: Whether institution is currently operating.
        is_diploma_mill: Whether flagged as diploma mill.
        founded_year: Year institution was founded.
        website: Official website URL.
    """

    institution_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    type: InstitutionType = InstitutionType.UNKNOWN
    city: str | None = None
    state_province: str | None = None
    country: str = "US"
    accreditation: AccreditationType = AccreditationType.UNKNOWN
    accreditor_name: str | None = None
    ope_id: str | None = None
    ipeds_id: str | None = None
    nsc_code: str | None = None
    is_active: bool = True
    is_diploma_mill: bool = False
    founded_year: int | None = None
    website: str | None = None


class ClaimedEducation(BaseModel):
    """Education credentials claimed by a subject.

    Attributes:
        institution_name: Name of claimed institution.
        degree_type: Type of degree claimed.
        degree_title: Specific degree title (e.g., "Bachelor of Science").
        major: Major/field of study.
        minor: Minor field of study.
        graduation_date: Claimed graduation date.
        enrollment_start: Claimed enrollment start.
        enrollment_end: Claimed enrollment end.
        gpa: Claimed GPA (optional).
        honors: Any honors claimed.
    """

    institution_name: str
    degree_type: DegreeType = DegreeType.UNKNOWN
    degree_title: str | None = None
    major: str | None = None
    minor: str | None = None
    graduation_date: date | None = None
    enrollment_start: date | None = None
    enrollment_end: date | None = None
    gpa: float | None = Field(default=None, ge=0.0, le=4.0)
    honors: list[str] = Field(default_factory=list)


class VerifiedEducation(BaseModel):
    """Education record as verified from official sources.

    Attributes:
        institution: Verified institution details.
        degree_type: Verified degree type.
        degree_title: Official degree title.
        major: Verified major.
        minor: Verified minor.
        graduation_date: Official graduation date.
        enrollment_start: Official enrollment start.
        enrollment_end: Official enrollment end.
        degree_conferred: Whether degree was actually conferred.
        verification_source: Source of verification (NSC, registrar, etc.).
        verified_at: When verification was performed.
    """

    institution: Institution
    degree_type: DegreeType
    degree_title: str | None = None
    major: str | None = None
    minor: str | None = None
    graduation_date: date | None = None
    enrollment_start: date | None = None
    enrollment_end: date | None = None
    degree_conferred: bool = False
    verification_source: str = "NSC"
    verified_at: datetime = Field(default_factory=lambda: datetime.now())


class EducationDiscrepancy(BaseModel):
    """A discrepancy found between claimed and verified education.

    Attributes:
        field: Name of the discrepant field.
        claimed_value: Value claimed by subject.
        verified_value: Value from verification source.
        severity: How serious the discrepancy is (low/medium/high).
        explanation: Human-readable explanation.
    """

    field: str
    claimed_value: str | None
    verified_value: str | None
    severity: str = "medium"  # low, medium, high
    explanation: str


class EducationVerificationResult(BaseModel):
    """Complete result of an education verification.

    Attributes:
        verification_id: Unique identifier for this verification.
        subject_name: Name of the subject being verified.
        claimed: The claimed education credentials.
        verified: The verified education record (if found).
        status: Overall verification status.
        institution_match: How well the institution matched.
        discrepancies: List of discrepancies found.
        diploma_mill_flags: Reasons if flagged as diploma mill.
        verification_notes: Additional notes from verification.
        verified_at: When verification completed.
        verification_time_ms: How long verification took.
        cached: Whether result was from cache.
    """

    verification_id: UUID
    subject_name: str
    claimed: ClaimedEducation
    verified: VerifiedEducation | None = None
    status: VerificationStatus = VerificationStatus.PENDING
    institution_match: MatchConfidence = MatchConfidence.NO_MATCH
    discrepancies: list[EducationDiscrepancy] = Field(default_factory=list)
    diploma_mill_flags: list[str] = Field(default_factory=list)
    verification_notes: list[str] = Field(default_factory=list)
    verified_at: datetime = Field(default_factory=lambda: datetime.now())
    verification_time_ms: float = 0.0
    cached: bool = False

    def has_discrepancies(self) -> bool:
        """Check if any discrepancies were found."""
        return len(self.discrepancies) > 0

    def get_high_severity_discrepancies(self) -> list[EducationDiscrepancy]:
        """Get only high severity discrepancies."""
        return [d for d in self.discrepancies if d.severity == "high"]

    def is_diploma_mill(self) -> bool:
        """Check if institution was flagged as diploma mill."""
        return self.status == VerificationStatus.DIPLOMA_MILL or len(self.diploma_mill_flags) > 0


class InstitutionMatchResult(BaseModel):
    """Result of matching an institution name.

    Attributes:
        institution: The matched institution.
        confidence: Match confidence level.
        score: Numeric match score (0.0-1.0).
        match_reasons: Why this institution matched.
    """

    institution: Institution
    confidence: MatchConfidence
    score: float = Field(ge=0.0, le=1.0)
    match_reasons: list[str] = Field(default_factory=list)


class EducationProviderConfig(BaseModel):
    """Configuration for the education verification provider.

    Attributes:
        nsc_api_key: National Student Clearinghouse API key.
        nsc_api_url: NSC API endpoint.
        enable_diploma_mill_detection: Whether to check diploma mill database.
        enable_international: Whether to verify international degrees.
        cache_ttl_seconds: How long to cache results.
        timeout_ms: Request timeout in milliseconds.
        min_match_score: Minimum score to consider a match.
    """

    nsc_api_key: str | None = None
    nsc_api_url: str = "https://api.studentclearinghouse.org/v1"
    enable_diploma_mill_detection: bool = True
    enable_international: bool = True
    cache_ttl_seconds: int = 86400  # 24 hours
    timeout_ms: int = 30000
    min_match_score: float = Field(ge=0.0, le=1.0, default=0.70)


# =============================================================================
# Exceptions
# =============================================================================


class EducationProviderError(Exception):
    """Base exception for education provider errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InstitutionNotFoundError(EducationProviderError):
    """Raised when an institution cannot be found."""

    def __init__(self, institution_name: str) -> None:
        super().__init__(
            f"Institution not found: {institution_name}",
            details={"institution_name": institution_name},
        )
        self.institution_name = institution_name


class VerificationFailedError(EducationProviderError):
    """Raised when verification fails."""

    def __init__(self, verification_id: UUID, reason: str) -> None:
        super().__init__(
            f"Education verification {verification_id} failed: {reason}",
            details={"verification_id": str(verification_id), "reason": reason},
        )
        self.verification_id = verification_id
        self.reason = reason


class DiplomaMilDetectedError(EducationProviderError):
    """Raised when a diploma mill is detected."""

    def __init__(self, institution_name: str, flags: list[str]) -> None:
        super().__init__(
            f"Diploma mill detected: {institution_name}",
            details={"institution_name": institution_name, "flags": flags},
        )
        self.institution_name = institution_name
        self.flags = flags
