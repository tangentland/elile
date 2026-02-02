"""Education verification provider implementation.

This module provides the EducationProvider class for verifying education
credentials through the National Student Clearinghouse and other sources.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid7

from elile.agent.state import SearchDegree, ServiceTier
from elile.compliance.types import CheckType, Locale
from elile.core.logging import get_logger
from elile.entity.types import SubjectIdentifiers
from elile.providers.protocol import BaseDataProvider
from elile.providers.types import (
    CostTier,
    DataSourceCategory,
    ProviderCapability,
    ProviderHealth,
    ProviderInfo,
    ProviderResult,
    ProviderStatus,
)

from .diploma_mill import DiplomaMilDetector, create_diploma_mill_detector
from .matcher import InstitutionMatcher, create_institution_matcher
from .types import (
    AccreditationType,
    ClaimedEducation,
    DegreeType,
    EducationDiscrepancy,
    EducationProviderConfig,
    EducationVerificationResult,
    Institution,
    InstitutionType,
    MatchConfidence,
    VerificationStatus,
    VerifiedEducation,
)

logger = get_logger(__name__)


class EducationProvider(BaseDataProvider):
    """Education verification provider.

    Verifies education credentials through:
    - National Student Clearinghouse (US)
    - Direct registrar queries
    - International verification services

    Includes diploma mill detection and accreditation verification.

    Usage:
        provider = EducationProvider()

        # Execute education verification check
        result = await provider.execute_check(
            check_type=CheckType.EDUCATION_VERIFICATION,
            subject=SubjectIdentifiers(full_name="John Smith"),
            locale=Locale.US,
        )

        if result.success:
            verification = result.normalized_data["verification"]
            if verification["status"] == "verified":
                print("Education verified!")
    """

    def __init__(self, config: EducationProviderConfig | None = None) -> None:
        """Initialize the education provider.

        Args:
            config: Optional provider configuration.
        """
        self._config = config or EducationProviderConfig()
        self._matcher = create_institution_matcher()
        self._diploma_mill_detector = create_diploma_mill_detector()

        # In-memory institution database (simulated)
        # In production, this would be populated from actual data sources
        self._institutions_db: dict[str, Institution] = {}
        self._load_sample_institutions()

        # Provider info
        provider_info = ProviderInfo(
            provider_id="education_provider",
            name="Education Verification Provider",
            description="Education credential verification (NSC, registrars, international)",
            category=DataSourceCategory.CORE,
            capabilities=[
                ProviderCapability(
                    check_type=CheckType.EDUCATION_VERIFICATION,
                    supported_locales=list(Locale),
                    cost_tier=CostTier.MEDIUM,
                    average_latency_ms=2000,
                    reliability_score=0.95,
                ),
                ProviderCapability(
                    check_type=CheckType.EDUCATION_DEGREE,
                    supported_locales=list(Locale),
                    cost_tier=CostTier.MEDIUM,
                    average_latency_ms=2000,
                    reliability_score=0.95,
                ),
            ],
            base_url="https://api.studentclearinghouse.org/v1",
            rate_limit_per_minute=100,
            rate_limit_per_day=10000,
            requires_api_key=True,
            supports_batch=True,
        )

        super().__init__(provider_info)

        logger.info(
            "education_provider_initialized",
            diploma_mill_detection=self._config.enable_diploma_mill_detection,
            international_support=self._config.enable_international,
        )

    @property
    def config(self) -> EducationProviderConfig:
        """Get the provider configuration."""
        return self._config

    @property
    def matcher(self) -> InstitutionMatcher:
        """Get the institution matcher."""
        return self._matcher

    @property
    def diploma_mill_detector(self) -> DiplomaMilDetector:
        """Get the diploma mill detector."""
        return self._diploma_mill_detector

    async def execute_check(
        self,
        check_type: CheckType,
        subject: SubjectIdentifiers,
        locale: Locale,
        *,
        degree: SearchDegree = SearchDegree.D1,  # noqa: ARG002
        service_tier: ServiceTier = ServiceTier.STANDARD,  # noqa: ARG002
        timeout_ms: int = 30000,  # noqa: ARG002
        claimed_education: ClaimedEducation | None = None,
    ) -> ProviderResult:
        """Execute an education verification check.

        Args:
            check_type: Type of check (EDUCATION_VERIFICATION or EDUCATION_DEGREE).
            subject: Subject identifiers to verify.
            locale: Locale for compliance context.
            degree: Search degree (reserved for future use).
            service_tier: Service tier (reserved for future use).
            timeout_ms: Request timeout (reserved for future use).
            claimed_education: Optional claimed education to verify against.

        Returns:
            ProviderResult with verification results.
        """
        start_time = datetime.now(UTC)
        query_id = uuid7()

        try:
            # Build subject name
            subject_name = self._build_subject_name(subject)
            if not subject_name:
                return ProviderResult(
                    provider_id=self.provider_id,
                    check_type=check_type,
                    locale=locale,
                    success=False,
                    error_code="INVALID_SUBJECT",
                    error_message="No name provided for education verification",
                    query_id=query_id,
                )

            # If no claimed education provided, create a minimal one
            if claimed_education is None:
                claimed_education = ClaimedEducation(
                    institution_name="Unknown",
                    degree_type=DegreeType.UNKNOWN,
                )

            # Execute verification
            verification_result = await self._verify_education(
                subject_name=subject_name,
                subject_dob=subject.date_of_birth,
                claimed=claimed_education,
                query_id=query_id,
            )

            # Calculate latency
            latency_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            verification_result.verification_time_ms = latency_ms

            # Build normalized data
            normalized_data = self._normalize_verification_result(verification_result)

            logger.info(
                "education_check_complete",
                query_id=str(query_id),
                check_type=check_type.value,
                subject_name=subject_name,
                institution=claimed_education.institution_name,
                status=verification_result.status.value,
                latency_ms=latency_ms,
                locale=locale.value,
            )

            return ProviderResult(
                provider_id=self.provider_id,
                check_type=check_type,
                locale=locale,
                success=True,
                normalized_data=normalized_data,
                query_id=query_id,
                latency_ms=latency_ms,
                cost_incurred=self._calculate_cost(verification_result),
            )

        except Exception as e:
            latency_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            logger.error(
                "education_check_failed",
                query_id=str(query_id),
                check_type=check_type.value,
                error=str(e),
            )
            return ProviderResult(
                provider_id=self.provider_id,
                check_type=check_type,
                locale=locale,
                success=False,
                error_code="VERIFICATION_ERROR",
                error_message=str(e),
                retryable=True,
                query_id=query_id,
                latency_ms=latency_ms,
            )

    async def health_check(self) -> ProviderHealth:
        """Check provider health.

        Returns:
            ProviderHealth with current status.
        """
        # In production, would check actual NSC API connectivity
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.HEALTHY,
            last_check=datetime.now(UTC),
            latency_ms=100,
            success_rate_24h=0.95,
        )

    async def verify_education(
        self,
        subject_name: str,
        claimed_education: ClaimedEducation,
        *,
        subject_dob: date | None = None,
    ) -> EducationVerificationResult:
        """Verify education credentials.

        Public method for direct verification without the provider interface.

        Args:
            subject_name: Name of the subject.
            claimed_education: Claimed education to verify.
            subject_dob: Optional date of birth.

        Returns:
            EducationVerificationResult with verification details.
        """
        return await self._verify_education(
            subject_name=subject_name,
            subject_dob=subject_dob,
            claimed=claimed_education,
            query_id=uuid7(),
        )

    async def check_institution(self, institution_name: str) -> dict[str, Any]:
        """Check if an institution is legitimate.

        Args:
            institution_name: Name of the institution.

        Returns:
            Dictionary with institution info and any flags.
        """
        # Check diploma mill
        diploma_mill_flags = self._diploma_mill_detector.check_institution(institution_name)

        # Try to find in database
        institutions_list = list(self._institutions_db.values())
        match_result = self._matcher.match_single(institution_name, institutions_list)

        return {
            "institution_name": institution_name,
            "is_diploma_mill": len(diploma_mill_flags) > 0,
            "diploma_mill_flags": diploma_mill_flags,
            "found_in_database": match_result is not None,
            "matched_institution": match_result.institution.name if match_result else None,
            "match_confidence": match_result.confidence.value if match_result else None,
            "match_score": match_result.score if match_result else None,
        }

    async def get_institution_database_stats(self) -> dict[str, Any]:
        """Get statistics about the institution database.

        Returns:
            Dictionary with database statistics.
        """
        return {
            "total_institutions": len(self._institutions_db),
            "by_type": self._count_by_type(),
            "by_country": self._count_by_country(),
            "accredited": sum(
                1
                for i in self._institutions_db.values()
                if i.accreditation
                not in (AccreditationType.UNACCREDITED, AccreditationType.UNKNOWN)
            ),
        }

    async def _verify_education(
        self,
        subject_name: str,
        subject_dob: date | None,
        claimed: ClaimedEducation,
        query_id: UUID,
    ) -> EducationVerificationResult:
        """Internal method to verify education.

        Args:
            subject_name: Name of the subject.
            subject_dob: Date of birth.
            claimed: Claimed education credentials.
            query_id: Query identifier.

        Returns:
            EducationVerificationResult with verification details.
        """
        result = EducationVerificationResult(
            verification_id=query_id,
            subject_name=subject_name,
            claimed=claimed,
        )

        # Step 1: Check for diploma mill
        if self._config.enable_diploma_mill_detection:
            diploma_mill_flags = self._diploma_mill_detector.check_institution(
                claimed.institution_name
            )
            if diploma_mill_flags:
                result.status = VerificationStatus.DIPLOMA_MILL
                result.diploma_mill_flags = diploma_mill_flags
                result.verification_notes.append("Institution flagged as potential diploma mill")
                return result

        # Step 2: Find the institution in our database
        institutions_list = list(self._institutions_db.values())
        match_result = self._matcher.match_single(claimed.institution_name, institutions_list)

        if match_result is None:
            result.status = VerificationStatus.NO_RECORD
            result.institution_match = MatchConfidence.NO_MATCH
            result.verification_notes.append(
                f"Institution '{claimed.institution_name}' not found in database"
            )
            return result

        result.institution_match = match_result.confidence

        # Step 3: Check matched institution for diploma mill flags
        if self._config.enable_diploma_mill_detection:
            institution_flags = self._diploma_mill_detector.check_institution_full(
                match_result.institution
            )
            if institution_flags:
                result.status = VerificationStatus.DIPLOMA_MILL
                result.diploma_mill_flags = institution_flags
                return result

        # Step 4: Simulate NSC verification (in production, would call actual API)
        verified_record = await self._simulate_nsc_verification(
            subject_name=subject_name,
            subject_dob=subject_dob,
            institution=match_result.institution,
            claimed=claimed,
        )

        if verified_record is None:
            result.status = VerificationStatus.NO_RECORD
            result.verification_notes.append(
                f"No enrollment record found for {subject_name} at {match_result.institution.name}"
            )
            return result

        result.verified = verified_record

        # Step 5: Compare claimed vs verified
        discrepancies = self._compare_education(claimed, verified_record)
        result.discrepancies = discrepancies

        # Step 6: Determine final status
        if not discrepancies:
            result.status = VerificationStatus.VERIFIED
        elif any(d.severity == "high" for d in discrepancies):
            result.status = VerificationStatus.DISCREPANCY
        else:
            result.status = VerificationStatus.PARTIAL_MATCH

        return result

    async def _simulate_nsc_verification(
        self,
        subject_name: str,
        subject_dob: date | None,  # noqa: ARG002
        institution: Institution,
        claimed: ClaimedEducation,
    ) -> VerifiedEducation | None:
        """Simulate NSC verification (mock for testing).

        In production, this would call the actual NSC API.

        Args:
            subject_name: Name of the subject.
            subject_dob: Date of birth.
            institution: Matched institution.
            claimed: Claimed education.

        Returns:
            VerifiedEducation if found, None otherwise.
        """
        # Simulate ~80% success rate for finding records
        # Use subject name hash to make it deterministic for testing
        name_hash = sum(ord(c) for c in subject_name.lower())

        if name_hash % 10 < 8:  # 80% chance of finding record
            # Simulate minor variations from claimed data
            graduation_date = claimed.graduation_date
            if graduation_date and name_hash % 5 == 0:
                # Simulate graduation date off by a semester
                graduation_date = date(
                    graduation_date.year,
                    (
                        graduation_date.month + 6
                        if graduation_date.month <= 6
                        else graduation_date.month - 6
                    ),
                    1,
                )

            return VerifiedEducation(
                institution=institution,
                degree_type=claimed.degree_type,
                degree_title=claimed.degree_title,
                major=claimed.major,
                minor=claimed.minor,
                graduation_date=graduation_date,
                enrollment_start=claimed.enrollment_start,
                enrollment_end=claimed.enrollment_end,
                degree_conferred=True,
                verification_source="NSC",
            )

        return None

    def _compare_education(
        self,
        claimed: ClaimedEducation,
        verified: VerifiedEducation,
    ) -> list[EducationDiscrepancy]:
        """Compare claimed education against verified record.

        Args:
            claimed: Claimed education credentials.
            verified: Verified education record.

        Returns:
            List of discrepancies found.
        """
        discrepancies: list[EducationDiscrepancy] = []

        # Compare degree type
        if (
            claimed.degree_type != DegreeType.UNKNOWN
            and claimed.degree_type != verified.degree_type
        ):
            discrepancies.append(
                EducationDiscrepancy(
                    field="degree_type",
                    claimed_value=claimed.degree_type.value,
                    verified_value=verified.degree_type.value,
                    severity="high",
                    explanation="Degree type does not match verified record",
                )
            )

        # Compare major
        if claimed.major and verified.major:
            claimed_major = claimed.major.lower().strip()
            verified_major = verified.major.lower().strip()
            if claimed_major != verified_major:
                discrepancies.append(
                    EducationDiscrepancy(
                        field="major",
                        claimed_value=claimed.major,
                        verified_value=verified.major,
                        severity="medium",
                        explanation="Major field of study does not match",
                    )
                )

        # Compare graduation date
        if claimed.graduation_date and verified.graduation_date:
            date_diff = abs((claimed.graduation_date - verified.graduation_date).days)
            if date_diff > 180:  # More than 6 months difference
                discrepancies.append(
                    EducationDiscrepancy(
                        field="graduation_date",
                        claimed_value=claimed.graduation_date.isoformat(),
                        verified_value=verified.graduation_date.isoformat(),
                        severity="medium",
                        explanation=f"Graduation date differs by {date_diff} days",
                    )
                )

        # Check if degree was actually conferred
        if not verified.degree_conferred:
            discrepancies.append(
                EducationDiscrepancy(
                    field="degree_conferred",
                    claimed_value="yes",
                    verified_value="no",
                    severity="high",
                    explanation="Degree was not conferred (attended but did not graduate)",
                )
            )

        return discrepancies

    def _normalize_verification_result(
        self,
        result: EducationVerificationResult,
    ) -> dict[str, Any]:
        """Normalize verification result to standard format."""
        return {
            "verification": {
                "verification_id": str(result.verification_id),
                "subject_name": result.subject_name,
                "status": result.status.value,
                "institution_match": result.institution_match.value,
                "is_diploma_mill": result.is_diploma_mill(),
                "has_discrepancies": result.has_discrepancies(),
                "verified_at": result.verified_at.isoformat(),
                "verification_time_ms": result.verification_time_ms,
            },
            "claimed": {
                "institution_name": result.claimed.institution_name,
                "degree_type": result.claimed.degree_type.value,
                "degree_title": result.claimed.degree_title,
                "major": result.claimed.major,
                "graduation_date": (
                    result.claimed.graduation_date.isoformat()
                    if result.claimed.graduation_date
                    else None
                ),
            },
            "verified": (
                {
                    "institution_name": result.verified.institution.name,
                    "institution_type": result.verified.institution.type.value,
                    "accreditation": result.verified.institution.accreditation.value,
                    "degree_type": result.verified.degree_type.value,
                    "degree_title": result.verified.degree_title,
                    "major": result.verified.major,
                    "graduation_date": (
                        result.verified.graduation_date.isoformat()
                        if result.verified.graduation_date
                        else None
                    ),
                    "degree_conferred": result.verified.degree_conferred,
                    "verification_source": result.verified.verification_source,
                }
                if result.verified
                else None
            ),
            "discrepancies": [
                {
                    "field": d.field,
                    "claimed": d.claimed_value,
                    "verified": d.verified_value,
                    "severity": d.severity,
                    "explanation": d.explanation,
                }
                for d in result.discrepancies
            ],
            "diploma_mill_flags": result.diploma_mill_flags,
            "notes": result.verification_notes,
        }

    def _calculate_cost(self, result: EducationVerificationResult) -> Decimal:
        """Calculate cost based on verification performed."""
        # Base cost for verification
        base_cost = Decimal("5.00")

        # International verification costs more
        if result.verified and result.verified.institution.country != "US":
            base_cost += Decimal("10.00")

        return base_cost

    def _build_subject_name(self, subject: SubjectIdentifiers) -> str:
        """Build subject name from identifiers."""
        if subject.full_name:
            return subject.full_name

        parts = []
        if subject.first_name:
            parts.append(subject.first_name)
        if subject.middle_name:
            parts.append(subject.middle_name)
        if subject.last_name:
            parts.append(subject.last_name)

        return " ".join(parts)

    def _count_by_type(self) -> dict[str, int]:
        """Count institutions by type."""
        counts: dict[str, int] = {}
        for inst in self._institutions_db.values():
            type_val = inst.type.value
            counts[type_val] = counts.get(type_val, 0) + 1
        return counts

    def _count_by_country(self) -> dict[str, int]:
        """Count institutions by country."""
        counts: dict[str, int] = {}
        for inst in self._institutions_db.values():
            country = inst.country
            counts[country] = counts.get(country, 0) + 1
        return counts

    def _load_sample_institutions(self) -> None:
        """Load sample institution data for testing.

        In production, this would load from actual data sources.
        """
        sample_institutions = [
            Institution(
                institution_id="MIT001",
                name="Massachusetts Institute of Technology",
                aliases=["MIT", "Mass Tech"],
                type=InstitutionType.UNIVERSITY,
                city="Cambridge",
                state_province="MA",
                country="US",
                accreditation=AccreditationType.REGIONAL_NECHE,
                accreditor_name="New England Commission of Higher Education",
                ope_id="00215300",
                ipeds_id="166683",
                nsc_code="002178",
                founded_year=1861,
                website="https://www.mit.edu",
            ),
            Institution(
                institution_id="HARV001",
                name="Harvard University",
                aliases=["Harvard", "Harvard College"],
                type=InstitutionType.UNIVERSITY,
                city="Cambridge",
                state_province="MA",
                country="US",
                accreditation=AccreditationType.REGIONAL_NECHE,
                accreditor_name="New England Commission of Higher Education",
                ope_id="00215600",
                ipeds_id="166027",
                nsc_code="002155",
                founded_year=1636,
                website="https://www.harvard.edu",
            ),
            Institution(
                institution_id="STAN001",
                name="Stanford University",
                aliases=["Stanford", "Leland Stanford Junior University"],
                type=InstitutionType.UNIVERSITY,
                city="Stanford",
                state_province="CA",
                country="US",
                accreditation=AccreditationType.REGIONAL_WASC,
                accreditor_name="WASC Senior College and University Commission",
                ope_id="00130500",
                ipeds_id="243744",
                nsc_code="001305",
                founded_year=1885,
                website="https://www.stanford.edu",
            ),
            Institution(
                institution_id="UCLA001",
                name="University of California, Los Angeles",
                aliases=["UCLA", "UC Los Angeles"],
                type=InstitutionType.UNIVERSITY,
                city="Los Angeles",
                state_province="CA",
                country="US",
                accreditation=AccreditationType.REGIONAL_WASC,
                accreditor_name="WASC Senior College and University Commission",
                ope_id="00131000",
                ipeds_id="110662",
                nsc_code="001315",
                founded_year=1919,
                website="https://www.ucla.edu",
            ),
            Institution(
                institution_id="NYU001",
                name="New York University",
                aliases=["NYU"],
                type=InstitutionType.UNIVERSITY,
                city="New York",
                state_province="NY",
                country="US",
                accreditation=AccreditationType.REGIONAL_MSCHE,
                accreditor_name="Middle States Commission on Higher Education",
                ope_id="00278500",
                ipeds_id="193900",
                nsc_code="002785",
                founded_year=1831,
                website="https://www.nyu.edu",
            ),
            Institution(
                institution_id="UCB001",
                name="University of California, Berkeley",
                aliases=["UC Berkeley", "Cal", "Berkeley"],
                type=InstitutionType.UNIVERSITY,
                city="Berkeley",
                state_province="CA",
                country="US",
                accreditation=AccreditationType.REGIONAL_WASC,
                accreditor_name="WASC Senior College and University Commission",
                ope_id="00131200",
                ipeds_id="110635",
                nsc_code="001312",
                founded_year=1868,
                website="https://www.berkeley.edu",
            ),
            Institution(
                institution_id="UMICH001",
                name="University of Michigan",
                aliases=["UMich", "Michigan", "U of M"],
                type=InstitutionType.UNIVERSITY,
                city="Ann Arbor",
                state_province="MI",
                country="US",
                accreditation=AccreditationType.REGIONAL_HLC,
                accreditor_name="Higher Learning Commission",
                ope_id="00222000",
                ipeds_id="170976",
                nsc_code="002325",
                founded_year=1817,
                website="https://www.umich.edu",
            ),
            Institution(
                institution_id="OXFD001",
                name="University of Oxford",
                aliases=["Oxford", "Oxford University"],
                type=InstitutionType.UNIVERSITY,
                city="Oxford",
                state_province="Oxfordshire",
                country="GB",
                accreditation=AccreditationType.INTERNATIONAL,
                accreditor_name="UK Quality Assurance Agency",
                founded_year=1096,
                website="https://www.ox.ac.uk",
            ),
            Institution(
                institution_id="CAMB001",
                name="University of Cambridge",
                aliases=["Cambridge", "Cambridge University"],
                type=InstitutionType.UNIVERSITY,
                city="Cambridge",
                state_province="Cambridgeshire",
                country="GB",
                accreditation=AccreditationType.INTERNATIONAL,
                accreditor_name="UK Quality Assurance Agency",
                founded_year=1209,
                website="https://www.cam.ac.uk",
            ),
            Institution(
                institution_id="COMM001",
                name="Santa Monica Community College",
                aliases=["SMC", "Santa Monica College"],
                type=InstitutionType.COMMUNITY_COLLEGE,
                city="Santa Monica",
                state_province="CA",
                country="US",
                accreditation=AccreditationType.REGIONAL_WASC,
                accreditor_name="WASC Senior College and University Commission",
                founded_year=1929,
                website="https://www.smc.edu",
            ),
        ]

        for inst in sample_institutions:
            self._institutions_db[inst.institution_id] = inst

        logger.info(
            "sample_institution_data_loaded",
            total_institutions=len(self._institutions_db),
        )


# =============================================================================
# Factory functions
# =============================================================================

_provider_instance: EducationProvider | None = None


def get_education_provider(
    config: EducationProviderConfig | None = None,
) -> EducationProvider:
    """Get the singleton education provider instance.

    Args:
        config: Optional configuration for first initialization.

    Returns:
        The EducationProvider singleton.
    """
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = EducationProvider(config)
    return _provider_instance


def create_education_provider(
    config: EducationProviderConfig | None = None,
) -> EducationProvider:
    """Create a new education provider instance.

    Use this for testing or when you need a fresh provider.

    Args:
        config: Optional configuration.

    Returns:
        A new EducationProvider instance.
    """
    return EducationProvider(config)
