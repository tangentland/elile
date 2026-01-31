"""Consent management for background checks.

This module provides consent tracking and verification for background
check compliance, including:
- Consent scope management
- Verification method tracking
- FCRA disclosure compliance
- Consent validation
"""

from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.compliance.types import CheckType, Locale


class ConsentScope(str, Enum):
    """Types of consent that can be granted.

    Each scope covers a specific category of background checks.
    Multiple scopes can be granted in a single consent form.
    """

    # General background check consent
    BACKGROUND_CHECK = "background_check"

    # Specific check types
    CRIMINAL_RECORDS = "criminal_records"
    CREDIT_CHECK = "credit_check"
    EMPLOYMENT_VERIFICATION = "employment_verification"
    EDUCATION_VERIFICATION = "education_verification"
    REFERENCE_CHECK = "reference_check"
    LICENSE_VERIFICATION = "license_verification"

    # Sanctions and watchlists
    SANCTIONS_CHECK = "sanctions_check"

    # Drug testing
    DRUG_TESTING = "drug_testing"

    # Enhanced tier checks
    SOCIAL_MEDIA = "social_media"
    DIGITAL_FOOTPRINT = "digital_footprint"

    # Location/behavioral (requires explicit separate consent)
    LOCATION_DATA = "location_data"
    BEHAVIORAL_DATA = "behavioral_data"

    # Ongoing monitoring
    CONTINUOUS_MONITORING = "continuous_monitoring"


class ConsentVerificationMethod(str, Enum):
    """Methods used to verify consent was obtained."""

    E_SIGNATURE = "e_signature"  # Electronic signature
    WET_SIGNATURE = "wet_signature"  # Physical signature
    HRIS_API = "hris_api"  # Verified through HRIS integration
    SSO_ACKNOWLEDGMENT = "sso_acknowledgment"  # SSO-based acknowledgment
    RECORDED_VERBAL = "recorded_verbal"  # Recorded verbal consent
    MANUAL_ATTESTATION = "manual_attestation"  # Manual HR attestation


class FCRADisclosure(BaseModel):
    """FCRA disclosure tracking for US compliance.

    Tracks when and what disclosures were provided to the subject
    as required by FCRA.
    """

    disclosure_id: UUID = Field(default_factory=uuid7)

    # When disclosures were provided
    provided_at: datetime
    method: str  # e.g., "email", "in_person", "mail"

    # Standard FCRA disclosures
    standalone_disclosure: bool = True  # Disclosure was on separate form
    summary_of_rights: bool = True  # CFPB summary of rights provided

    # State-specific disclosures
    state_disclosures: list[str] = Field(default_factory=list)
    # e.g., ["CA_ICRAA", "NY_FAIR_CHANCE"]

    # Investigative consumer report disclosure (if applicable)
    investigative_disclosure: bool = False
    investigative_disclosure_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        """Check if all required FCRA disclosures were made."""
        return self.standalone_disclosure and self.summary_of_rights


class Consent(BaseModel):
    """Consent record for background check authorization.

    Tracks the consent granted by a subject for specific types
    of background checks.
    """

    consent_id: UUID = Field(default_factory=uuid7)
    subject_id: UUID  # The person granting consent

    # What was consented to
    scopes: list[ConsentScope] = Field(default_factory=list)

    # When consent was obtained
    granted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None  # None = no expiration

    # How consent was verified
    verification_method: ConsentVerificationMethod
    verification_reference: str | None = None  # e.g., signature ID, HRIS transaction

    # Locale for compliance
    locale: Locale = Locale.US

    # FCRA disclosures (US only)
    fcra_disclosure: FCRADisclosure | None = None

    # Purpose limitation
    purpose: str | None = None  # e.g., "pre-employment screening"

    # Revocation
    revoked_at: datetime | None = None
    revocation_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Check if consent is currently valid (not expired or revoked)."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and datetime.now(UTC) > self.expires_at:
            return False
        return True

    @property
    def is_revoked(self) -> bool:
        """Check if consent was revoked."""
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        """Check if consent has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def covers_scope(self, scope: ConsentScope) -> bool:
        """Check if consent covers a specific scope.

        Args:
            scope: The scope to check

        Returns:
            True if the scope is covered by this consent
        """
        if not self.is_valid:
            return False

        # Background check consent covers most basic checks
        if ConsentScope.BACKGROUND_CHECK in self.scopes:
            if scope in {
                ConsentScope.BACKGROUND_CHECK,
                ConsentScope.CRIMINAL_RECORDS,
                ConsentScope.EMPLOYMENT_VERIFICATION,
                ConsentScope.EDUCATION_VERIFICATION,
                ConsentScope.LICENSE_VERIFICATION,
                ConsentScope.SANCTIONS_CHECK,
            }:
                return True

        return scope in self.scopes

    def covers_check_type(self, check_type: CheckType) -> bool:
        """Check if consent covers a specific check type.

        Args:
            check_type: The check type to verify

        Returns:
            True if the check type is covered
        """
        if not self.is_valid:
            return False

        scope = _check_type_to_scope(check_type)
        if scope is None:
            return False

        return self.covers_scope(scope)


class ConsentResult(BaseModel):
    """Result of consent verification."""

    valid: bool
    consent: Consent | None = None
    missing_scopes: list[ConsentScope] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ConsentManager:
    """Manager for consent verification and tracking.

    Provides methods to verify consent for specific check types
    and identify missing consent scopes.
    """

    def __init__(self):
        """Initialize the consent manager."""
        self._consents: dict[UUID, list[Consent]] = {}  # subject_id -> consents

    def register_consent(self, consent: Consent) -> None:
        """Register a consent record.

        Args:
            consent: The consent to register
        """
        if consent.subject_id not in self._consents:
            self._consents[consent.subject_id] = []
        self._consents[consent.subject_id].append(consent)

    def get_consents(self, subject_id: UUID) -> list[Consent]:
        """Get all consents for a subject.

        Args:
            subject_id: The subject's ID

        Returns:
            List of consent records
        """
        return self._consents.get(subject_id, [])

    def get_valid_consents(self, subject_id: UUID) -> list[Consent]:
        """Get all valid (not expired/revoked) consents for a subject.

        Args:
            subject_id: The subject's ID

        Returns:
            List of valid consent records
        """
        return [c for c in self.get_consents(subject_id) if c.is_valid]

    def verify_consent(
        self,
        subject_id: UUID,
        required_scopes: list[ConsentScope],
    ) -> ConsentResult:
        """Verify consent for required scopes.

        Args:
            subject_id: The subject's ID
            required_scopes: Scopes that need consent

        Returns:
            ConsentResult with verification status
        """
        valid_consents = self.get_valid_consents(subject_id)

        if not valid_consents:
            return ConsentResult(
                valid=False,
                missing_scopes=required_scopes,
                errors=["No valid consent found for subject"],
            )

        # Check which scopes are covered
        covered_scopes: set[ConsentScope] = set()
        covering_consent: Consent | None = None

        for consent in valid_consents:
            for scope in required_scopes:
                if consent.covers_scope(scope):
                    covered_scopes.add(scope)
                    covering_consent = consent

        missing = [s for s in required_scopes if s not in covered_scopes]

        if missing:
            return ConsentResult(
                valid=False,
                consent=covering_consent,
                missing_scopes=missing,
                errors=[f"Missing consent for: {', '.join(s.value for s in missing)}"],
            )

        return ConsentResult(
            valid=True,
            consent=covering_consent,
        )

    def verify_check_types(
        self,
        subject_id: UUID,
        check_types: list[CheckType],
    ) -> ConsentResult:
        """Verify consent for specific check types.

        Args:
            subject_id: The subject's ID
            check_types: Check types to verify

        Returns:
            ConsentResult with verification status
        """
        # Convert check types to required scopes
        required_scopes: set[ConsentScope] = set()
        for check_type in check_types:
            scope = _check_type_to_scope(check_type)
            if scope:
                required_scopes.add(scope)

        return self.verify_consent(subject_id, list(required_scopes))

    def verify_fcra_disclosure(
        self,
        consent: Consent,
        locale: Locale,
    ) -> tuple[bool, list[str]]:
        """Verify FCRA disclosure requirements.

        Args:
            consent: The consent to verify
            locale: The locale for compliance

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors: list[str] = []

        # FCRA only applies to US
        if not locale.value.startswith("US"):
            return True, []

        if consent.fcra_disclosure is None:
            return False, ["No FCRA disclosure record"]

        disclosure = consent.fcra_disclosure

        if not disclosure.standalone_disclosure:
            errors.append("Disclosure was not on standalone form")

        if not disclosure.summary_of_rights:
            errors.append("Summary of rights not provided")

        # Check state-specific requirements
        if locale == Locale.US_CA and "CA_ICRAA" not in disclosure.state_disclosures:
            errors.append("California ICRAA disclosure not provided")

        if locale == Locale.US_NY and "NY_FAIR_CHANCE" not in disclosure.state_disclosures:
            errors.append("New York Fair Chance disclosure not provided")

        return len(errors) == 0, errors

    def revoke_consent(
        self,
        consent_id: UUID,
        reason: str | None = None,
    ) -> bool:
        """Revoke a consent record.

        Args:
            consent_id: The consent ID to revoke
            reason: Optional reason for revocation

        Returns:
            True if consent was found and revoked
        """
        for consents in self._consents.values():
            for consent in consents:
                if consent.consent_id == consent_id:
                    consent.revoked_at = datetime.now(UTC)
                    consent.revocation_reason = reason
                    return True
        return False


def _check_type_to_scope(check_type: CheckType) -> ConsentScope | None:
    """Map a check type to its required consent scope.

    Args:
        check_type: The check type

    Returns:
        The required consent scope, or None if not mapped
    """
    mapping: dict[CheckType, ConsentScope] = {
        # Criminal records
        CheckType.CRIMINAL_NATIONAL: ConsentScope.CRIMINAL_RECORDS,
        CheckType.CRIMINAL_STATE: ConsentScope.CRIMINAL_RECORDS,
        CheckType.CRIMINAL_COUNTY: ConsentScope.CRIMINAL_RECORDS,
        CheckType.CRIMINAL_FEDERAL: ConsentScope.CRIMINAL_RECORDS,
        CheckType.CRIMINAL_INTERNATIONAL: ConsentScope.CRIMINAL_RECORDS,
        CheckType.SEX_OFFENDER: ConsentScope.CRIMINAL_RECORDS,
        # Credit
        CheckType.CREDIT_REPORT: ConsentScope.CREDIT_CHECK,
        CheckType.CREDIT_SCORE: ConsentScope.CREDIT_CHECK,
        # Employment
        CheckType.EMPLOYMENT_VERIFICATION: ConsentScope.EMPLOYMENT_VERIFICATION,
        CheckType.EMPLOYMENT_REFERENCE: ConsentScope.REFERENCE_CHECK,
        # Education
        CheckType.EDUCATION_VERIFICATION: ConsentScope.EDUCATION_VERIFICATION,
        CheckType.EDUCATION_DEGREE: ConsentScope.EDUCATION_VERIFICATION,
        # Licenses
        CheckType.LICENSE_VERIFICATION: ConsentScope.LICENSE_VERIFICATION,
        CheckType.PROFESSIONAL_SANCTIONS: ConsentScope.LICENSE_VERIFICATION,
        CheckType.REGULATORY_ENFORCEMENT: ConsentScope.LICENSE_VERIFICATION,
        # Sanctions
        CheckType.SANCTIONS_OFAC: ConsentScope.SANCTIONS_CHECK,
        CheckType.SANCTIONS_UN: ConsentScope.SANCTIONS_CHECK,
        CheckType.SANCTIONS_EU: ConsentScope.SANCTIONS_CHECK,
        CheckType.SANCTIONS_PEP: ConsentScope.SANCTIONS_CHECK,
        CheckType.WATCHLIST_INTERPOL: ConsentScope.SANCTIONS_CHECK,
        CheckType.WATCHLIST_FBI: ConsentScope.SANCTIONS_CHECK,
        # Drug testing
        CheckType.DRUG_TEST: ConsentScope.DRUG_TESTING,
        # Social media / digital
        CheckType.SOCIAL_MEDIA: ConsentScope.SOCIAL_MEDIA,
        CheckType.DIGITAL_FOOTPRINT: ConsentScope.DIGITAL_FOOTPRINT,
        # Location / behavioral
        CheckType.LOCATION_HISTORY: ConsentScope.LOCATION_DATA,
        CheckType.BEHAVIORAL_DATA: ConsentScope.BEHAVIORAL_DATA,
    }

    return mapping.get(check_type)


def create_consent(
    subject_id: UUID,
    scopes: list[ConsentScope],
    verification_method: ConsentVerificationMethod = ConsentVerificationMethod.E_SIGNATURE,
    locale: Locale = Locale.US,
    expires_in_days: int | None = 365,
    purpose: str | None = "pre-employment screening",
) -> Consent:
    """Create a new consent record.

    Args:
        subject_id: The subject granting consent
        scopes: Consent scopes being granted
        verification_method: How consent was verified
        locale: The applicable locale
        expires_in_days: Days until consent expires (None = no expiration)
        purpose: Purpose of the consent

    Returns:
        New Consent record
    """
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=expires_in_days) if expires_in_days else None

    return Consent(
        subject_id=subject_id,
        scopes=scopes,
        granted_at=now,
        expires_at=expires_at,
        verification_method=verification_method,
        locale=locale,
        purpose=purpose,
    )


def create_fcra_disclosure(
    state_disclosures: list[str] | None = None,
    investigative: bool = False,
) -> FCRADisclosure:
    """Create an FCRA disclosure record.

    Args:
        state_disclosures: List of state-specific disclosures provided
        investigative: Whether investigative consumer report disclosure was made

    Returns:
        New FCRADisclosure record
    """
    now = datetime.now(UTC)
    return FCRADisclosure(
        provided_at=now,
        method="e_signature",
        standalone_disclosure=True,
        summary_of_rights=True,
        state_disclosures=state_disclosures or [],
        investigative_disclosure=investigative,
        investigative_disclosure_at=now if investigative else None,
    )
