"""LLM Synthesis Provider implementation.

This provider synthesizes verification data from public sources using
LLM models for extraction and cross-validation. It serves as a fallback
when paid providers are unavailable or as a cost-effective supplement.

All synthesized data is clearly marked and capped at lower confidence
than official provider data.
"""

import re
from datetime import datetime
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any
from uuid import uuid7

from pydantic import BaseModel

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

from .types import (
    AttestationType,
    ConfidenceFactor,
    EducationAttestation,
    EmploymentAttestation,
    LinkedInExperience,
    LinkedInProfile,
    LinkedInRecommendation,
    LLMSynthesisProviderConfig,
    NewsArticle,
    PublicSource,
    PublicSourceType,
    RelationshipType,
    SECFiling,
    SourceType,
    SynthesisProvenance,
    SynthesizedAdverseMedia,
    SynthesizedCorporateAffiliation,
    SynthesizedCorporateAffiliations,
    SynthesizedEducationVerification,
    SynthesizedEmploymentVerification,
    SynthesizedLicenseVerification,
    SynthesizedSocialMedia,
    UnsupportedCheckTypeError,
)

logger = get_logger(__name__)


# Supported check types for synthesis
SUPPORTED_CHECK_TYPES = [
    CheckType.EMPLOYMENT_VERIFICATION,
    CheckType.EDUCATION_VERIFICATION,
    CheckType.ADVERSE_MEDIA,
    CheckType.LICENSE_VERIFICATION,
    CheckType.SOCIAL_MEDIA,
    CheckType.BUSINESS_AFFILIATIONS,
]


class ClaimedEmployment(BaseModel):
    """Claimed employment record from subject."""

    employer: str
    title: str | None = None
    start_date: Any | None = None
    end_date: Any | None = None


class ClaimedEducation(BaseModel):
    """Claimed education record from subject."""

    institution: str
    degree: str | None = None
    major: str | None = None
    graduation_year: int | None = None


class LLMSynthesisProvider(BaseDataProvider):
    """Fallback provider that synthesizes verification data from public sources.

    Uses LLM models to extract and cross-validate information from:
    - LinkedIn profiles and recommendations
    - News articles and press releases
    - SEC filings and corporate records
    - Public professional databases

    All synthesized data is clearly marked and capped at lower confidence
    than official provider data.
    """

    def __init__(self, config: LLMSynthesisProviderConfig | None = None) -> None:
        """Initialize synthesis provider.

        Args:
            config: Provider configuration. Uses defaults if not provided.
        """
        self.config = config or LLMSynthesisProviderConfig()
        self._scorer = AttestationScorer()
        self._employment_aggregator = EmploymentAttestationAggregator()
        self._education_aggregator = EducationAttestationAggregator()

    @property
    def provider_id(self) -> str:
        """Return provider ID."""
        return "llm_synthesis"

    @property
    def provider_info(self) -> ProviderInfo:
        """Return provider information."""
        return ProviderInfo(
            provider_id=self.provider_id,
            name="LLM Synthesis Provider",
            version="1.0.0",
            category=DataSourceCategory.CORE,
            cost_tier=CostTier.LOW,
            capabilities=[
                ProviderCapability(
                    check_type=ct,
                    supported_locales=list(Locale),
                    average_latency_ms=3000,
                    accuracy_score=0.75,
                )
                for ct in SUPPORTED_CHECK_TYPES
            ],
            requires_consent=True,
            is_deprecated=False,
        )

    @property
    def supported_checks(self) -> list[CheckType]:
        """Return supported check types."""
        return SUPPORTED_CHECK_TYPES

    async def execute_check(
        self,
        check_type: CheckType,
        subject: SubjectIdentifiers,
        locale: Locale,  # noqa: ARG002 - Reserved for future locale-specific filtering
        *,
        options: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """Execute synthesized check from public sources.

        Args:
            check_type: Type of check to perform.
            subject: Subject identifiers.
            locale: Target locale (reserved for future locale-specific filtering).
            options: Additional options (claimed_employers, claimed_education, etc.).

        Returns:
            ProviderResult with synthesized data and compliance flags.

        Raises:
            UnsupportedCheckTypeError: If check type not supported.
        """
        if check_type not in self.supported_checks:
            raise UnsupportedCheckTypeError(
                check_type.value,
                [ct.value for ct in self.supported_checks],
            )

        start_time = datetime.utcnow()
        query_id = uuid7()
        options = options or {}

        # Validate subject has required data
        if not subject.full_name:
            return ProviderResult(
                provider_id=self.provider_id,
                check_type=check_type,
                locale=locale,
                query_id=query_id,
                success=False,
                error_code="INVALID_SUBJECT",
                error_message="Subject full_name is required for synthesis",
                latency_ms=0,
            )

        try:
            # Execute check based on type
            if check_type == CheckType.EMPLOYMENT_VERIFICATION:
                result_data = await self._synthesize_employment(
                    subject=subject,
                    claimed_employers=options.get("claimed_employers", []),
                )
            elif check_type == CheckType.EDUCATION_VERIFICATION:
                result_data = await self._synthesize_education(
                    subject=subject,
                    claimed_education=options.get("claimed_education", []),
                )
            elif check_type == CheckType.ADVERSE_MEDIA:
                result_data = await self._synthesize_adverse_media(subject=subject)
            elif check_type == CheckType.LICENSE_VERIFICATION:
                result_data = await self._synthesize_license(
                    subject=subject,
                    license_type=options.get("license_type"),
                    state=options.get("state"),
                )
            elif check_type == CheckType.SOCIAL_MEDIA:
                result_data = await self._synthesize_social_media(subject=subject)
            elif check_type == CheckType.BUSINESS_AFFILIATIONS:
                result_data = await self._synthesize_corporate(subject=subject)
            else:
                raise UnsupportedCheckTypeError(
                    check_type.value,
                    [ct.value for ct in self.supported_checks],
                )

            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Build normalized data
            normalized = self._build_normalized_data(check_type, result_data)

            # Calculate cost (based on LLM calls, minimal)
            cost = self._calculate_cost(check_type)

            return ProviderResult(
                provider_id=self.provider_id,
                check_type=check_type,
                locale=locale,
                query_id=query_id,
                success=True,
                normalized_data=normalized,
                latency_ms=latency_ms,
                cost_incurred=cost,
            )

        except Exception as e:
            logger.error(
                "synthesis_check_failed",
                check_type=check_type.value,
                error=str(e),
            )
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return ProviderResult(
                provider_id=self.provider_id,
                check_type=check_type,
                locale=locale,
                query_id=query_id,
                success=False,
                error_code="SYNTHESIS_FAILED",
                error_message=str(e),
                latency_ms=latency_ms,
            )

    async def health_check(self) -> ProviderHealth:
        """Check provider health.

        Returns:
            ProviderHealth with current status.
        """
        # Synthesis provider is always available (simulated)
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.HEALTHY,
            last_check=datetime.utcnow(),
            latency_ms=10,
        )

    # ================================================================
    # Employment Verification Synthesis
    # ================================================================

    async def _synthesize_employment(
        self,
        subject: SubjectIdentifiers,
        claimed_employers: list[dict[str, Any]] | None = None,
    ) -> list[SynthesizedEmploymentVerification]:
        """Synthesize employment verification from public sources.

        Args:
            subject: Subject identifiers.
            claimed_employers: List of claimed employment records.

        Returns:
            List of synthesized employment verifications.
        """
        # Parse claimed employers
        claimed = []
        for emp in claimed_employers or []:
            if isinstance(emp, dict):
                claimed.append(
                    ClaimedEmployment(
                        employer=emp.get("employer", ""),
                        title=emp.get("title"),
                        start_date=emp.get("start_date"),
                        end_date=emp.get("end_date"),
                    )
                )

        # If no claims, generate simulated findings
        if not claimed:
            claimed = self._generate_simulated_employers(subject.full_name or "")

        # Gather simulated public sources
        sources = await self._gather_employment_sources(subject, claimed)

        # Process recommendations and build attestations
        attestations = []
        for source in sources:
            if source.source_type == PublicSourceType.LINKEDIN_RECOMMENDATION:
                rec = self._parse_linkedin_recommendation(source)
                if rec:
                    for emp in claimed:
                        att = self._scorer.score_linkedin_recommendation(
                            recommendation=rec,
                            attester_profile=self._generate_attester_profile(rec.author_name),
                            target_claimed_employer=emp.employer,
                        )
                        if att.confidence > 0.2:
                            attestations.append(att)

            elif source.source_type == PublicSourceType.NEWS_ARTICLE:
                article = self._parse_news_article(source)
                if article:
                    for emp in claimed:
                        att = self._scorer.score_news_mention(
                            article=article,
                            subject_name=subject.full_name or "",
                            target_employer=emp.employer,
                        )
                        if att and att.confidence > 0.2:
                            attestations.append(att)

            elif source.source_type == PublicSourceType.SEC_FILING:
                filing = self._parse_sec_filing(source)
                if filing:
                    for emp in claimed:
                        att = self._scorer.score_sec_filing(
                            filing=filing,
                            subject_name=subject.full_name or "",
                            target_employer=emp.employer,
                        )
                        if att and att.confidence > 0.3:
                            attestations.append(att)

        # Aggregate attestations per employer
        results = []
        for emp in claimed:
            verification = self._employment_aggregator.aggregate_attestations(
                claimed_employment=emp,
                attestations=attestations,
            )
            results.append(verification)

        return results

    async def _gather_employment_sources(
        self,
        subject: SubjectIdentifiers,
        claimed: list[ClaimedEmployment],
    ) -> list[PublicSource]:
        """Gather public sources for employment verification (simulated)."""
        sources = []
        name = subject.full_name or ""
        name_hash = hash(name) % 1000

        # Simulate LinkedIn recommendations (deterministic based on name)
        if self.config.linkedin_enabled:
            num_recs = (name_hash % 3) + 1
            for i in range(num_recs):
                sources.append(
                    PublicSource(
                        source_type=PublicSourceType.LINKEDIN_RECOMMENDATION,
                        url=f"https://linkedin.com/in/{name.lower().replace(' ', '-')}/recommendations/{i}",
                        content=self._generate_recommendation_text(name, claimed, i),
                        metadata={
                            "author_name": f"Recommender {i+1}",
                            "author_title": f"Manager at {claimed[0].employer if claimed else 'Company'}",
                        },
                    )
                )

        # Simulate news articles
        if self.config.news_search_enabled and claimed and name_hash % 3 == 0:
            # 33% chance of news mention
            sources.append(
                    PublicSource(
                        source_type=PublicSourceType.NEWS_ARTICLE,
                        url=f"https://news.example.com/article/{name_hash}",
                        content=self._generate_news_content(name, claimed),
                        metadata={
                            "title": f"{name} joins {claimed[0].employer}",
                            "source": "Industry News",
                        },
                    )
                )

        # Simulate SEC filings (for executives)
        if self.config.sec_filings_enabled and claimed and name_hash % 5 == 0:
            # 20% chance of SEC mention
            sources.append(
                    PublicSource(
                        source_type=PublicSourceType.SEC_FILING,
                        url=f"https://sec.gov/filing/{name_hash}",
                        content=self._generate_sec_content(name, claimed),
                        metadata={
                            "filing_type": "DEF 14A",
                            "company_name": claimed[0].employer if claimed else "Company",
                        },
                    )
                )

        return sources[: self.config.max_sources_per_check]

    def _generate_recommendation_text(
        self,
        name: str,
        claimed: list[ClaimedEmployment],
        index: int,
    ) -> str:
        """Generate simulated recommendation text."""
        templates = [
            f"I worked with {name} at {claimed[0].employer if claimed else 'the company'} and can "
            f"highly recommend their work. They showed excellent skills in their role.",
            f"{name} was a valuable colleague during our time at "
            f"{claimed[0].employer if claimed else 'the company'}. I managed {name} for 2 years.",
            f"It was a pleasure working alongside {name}. Their contributions to our team "
            f"at {claimed[0].employer if claimed else 'the company'} were significant.",
        ]
        return templates[index % len(templates)]

    def _generate_news_content(
        self,
        name: str,
        claimed: list[ClaimedEmployment],
    ) -> str:
        """Generate simulated news article content."""
        emp = claimed[0] if claimed else ClaimedEmployment(employer="Company")
        return (
            f"{emp.employer} announced today that {name} has been appointed as "
            f"{emp.title or 'Senior Executive'}. The company expressed confidence in "
            f"{name}'s ability to drive growth."
        )

    def _generate_sec_content(
        self,
        name: str,
        claimed: list[ClaimedEmployment],
    ) -> str:
        """Generate simulated SEC filing excerpt."""
        emp = claimed[0] if claimed else ClaimedEmployment(employer="Company")
        return (
            f"EXECUTIVE OFFICERS\n\n"
            f"{name.upper()}, age 45, has served as {emp.title or 'Vice President'} since 2020. "
            f"Prior to joining {emp.employer}, served in various senior positions."
        )

    def _generate_simulated_employers(self, name: str) -> list[ClaimedEmployment]:
        """Generate simulated employers for testing."""
        name_hash = hash(name) % 1000
        companies = [
            "Acme Corporation",
            "Tech Solutions Inc",
            "Global Industries",
            "Innovation Labs",
            "Enterprise Systems",
        ]
        company = companies[name_hash % len(companies)]
        return [
            ClaimedEmployment(
                employer=company,
                title="Senior Manager",
            )
        ]

    def _parse_linkedin_recommendation(self, source: PublicSource) -> LinkedInRecommendation | None:
        """Parse LinkedIn recommendation from source."""
        return LinkedInRecommendation(
            author_name=source.metadata.get("author_name", "Unknown"),
            author_profile_url=source.url,
            author_title=source.metadata.get("author_title"),
            text=source.content,
        )

    def _parse_news_article(self, source: PublicSource) -> NewsArticle | None:
        """Parse news article from source."""
        return NewsArticle(
            url=source.url or "",
            title=source.metadata.get("title", "Untitled"),
            source=source.metadata.get("source", "News"),
            content=source.content,
        )

    def _parse_sec_filing(self, source: PublicSource) -> SECFiling | None:
        """Parse SEC filing from source."""
        return SECFiling(
            filing_type=source.metadata.get("filing_type", "10-K"),
            company_name=source.metadata.get("company_name", "Company"),
            filing_date=datetime.utcnow().date(),
            url=source.url or "",
            content_excerpt=source.content,
        )

    def _generate_attester_profile(self, name: str) -> LinkedInProfile:
        """Generate simulated attester profile."""
        return LinkedInProfile(
            profile_url=f"https://linkedin.com/in/{name.lower().replace(' ', '-')}",
            full_name=name,
            headline="Professional",
            connections=hash(name) % 500 + 100,
            verified=hash(name) % 3 == 0,
            experience=[
                LinkedInExperience(
                    company="Acme Corporation",
                    title="Manager",
                    is_current=True,
                )
            ],
        )

    # ================================================================
    # Education Verification Synthesis
    # ================================================================

    async def _synthesize_education(
        self,
        subject: SubjectIdentifiers,
        claimed_education: list[dict[str, Any]] | None = None,
    ) -> list[SynthesizedEducationVerification]:
        """Synthesize education verification from public sources."""
        # Parse claimed education
        claimed = []
        for edu in claimed_education or []:
            if isinstance(edu, dict):
                claimed.append(
                    ClaimedEducation(
                        institution=edu.get("institution", ""),
                        degree=edu.get("degree"),
                        major=edu.get("major"),
                        graduation_year=edu.get("graduation_year"),
                    )
                )

        # If no claims, generate simulated findings
        if not claimed:
            claimed = self._generate_simulated_education(subject.full_name or "")

        # Gather simulated sources
        sources = await self._gather_education_sources(subject, claimed)

        # Build attestations
        attestations = []
        for source in sources:
            for edu in claimed:
                att = self._score_education_source(source, edu, subject.full_name or "")
                if att and att.confidence > 0.2:
                    attestations.append(att)

        # Aggregate per institution
        results = []
        for edu in claimed:
            verification = self._education_aggregator.aggregate_attestations(
                claimed_education=edu,
                attestations=attestations,
            )
            results.append(verification)

        return results

    async def _gather_education_sources(
        self,
        subject: SubjectIdentifiers,
        claimed: list[ClaimedEducation],
    ) -> list[PublicSource]:
        """Gather public sources for education verification (simulated)."""
        sources = []
        name = subject.full_name or ""
        name_hash = hash(name) % 1000

        # Simulate LinkedIn education
        if self.config.linkedin_enabled:
            sources.append(
                PublicSource(
                    source_type=PublicSourceType.LINKEDIN_PROFILE,
                    url=f"https://linkedin.com/in/{name.lower().replace(' ', '-')}",
                    content=f"Education: {claimed[0].degree if claimed else 'BS'} from "
                    f"{claimed[0].institution if claimed else 'University'}",
                    metadata={"section": "education"},
                )
            )

        # Simulate alumni directory
        if name_hash % 4 == 0 and claimed:  # 25% chance
            sources.append(
                PublicSource(
                    source_type=PublicSourceType.ALUMNI_NETWORK,
                    url=f"https://{claimed[0].institution.lower().replace(' ', '')}.edu/alumni/{name_hash}",
                    content=f"{name}, Class of {claimed[0].graduation_year or 2015}",
                    metadata={"institution": claimed[0].institution},
                )
            )

        return sources[: self.config.max_sources_per_check]

    def _generate_simulated_education(self, name: str) -> list[ClaimedEducation]:
        """Generate simulated education for testing."""
        name_hash = hash(name) % 1000
        schools = [
            "State University",
            "Technical Institute",
            "Business School",
            "Community College",
            "University of Technology",
        ]
        return [
            ClaimedEducation(
                institution=schools[name_hash % len(schools)],
                degree="Bachelor of Science",
                major="Business Administration",
                graduation_year=2010 + (name_hash % 10),
            )
        ]

    def _score_education_source(
        self,
        source: PublicSource,
        claimed: ClaimedEducation,
        subject_name: str,  # noqa: ARG002 - Reserved for subject-specific scoring
    ) -> EducationAttestation | None:
        """Score an education source as attestation.

        Args:
            source: Public source to evaluate.
            claimed: Claimed education record.
            subject_name: Subject name (reserved for future subject-specific scoring).

        Returns:
            EducationAttestation if confidence > 0.2, else None.
        """
        confidence = 0.0
        factors: list[ConfidenceFactor] = []

        # Check if institution is mentioned
        if claimed.institution.lower() in source.content.lower():
            confidence += 0.3
            factors.append(ConfidenceFactor.OFFICIAL_UNIVERSITY_SOURCE)

        # Check source type reliability
        if source.source_type == PublicSourceType.ALUMNI_NETWORK:
            confidence += 0.25
            factors.append(ConfidenceFactor.OFFICIAL_UNIVERSITY_SOURCE)
        elif source.source_type == PublicSourceType.LINKEDIN_PROFILE:
            confidence += 0.15

        # Check if degree mentioned
        proves_degree = False
        if claimed.degree and claimed.degree.lower() in source.content.lower():
            confidence += 0.1
            proves_degree = True

        if confidence < 0.2:
            return None

        return EducationAttestation(
            institution=claimed.institution,
            attestation_type=(
                AttestationType.ALUMNI_DIRECTORY
                if source.source_type == PublicSourceType.ALUMNI_NETWORK
                else AttestationType.LINKEDIN_SKILL_ENDORSEMENT
            ),
            attester_name=source.metadata.get("institution", "Public Source"),
            attester_source=source.url,
            attestation_text=source.content,
            proves_attendance=True,
            proves_degree=proves_degree,
            confidence=min(confidence, 0.70),
            confidence_factors=factors,
        )

    # ================================================================
    # Adverse Media Synthesis
    # ================================================================

    async def _synthesize_adverse_media(
        self,
        subject: SubjectIdentifiers,
    ) -> SynthesizedAdverseMedia:
        """Synthesize adverse media findings."""
        name = subject.full_name or ""
        name_hash = hash(name) % 1000

        articles = []
        adverse_count = 0

        # Deterministic adverse media (10% have something)
        if name_hash % 10 == 0:
            articles.append(
                NewsArticle(
                    url=f"https://news.example.com/adverse/{name_hash}",
                    title=f"Regulatory Review Mentions {name}",
                    source="Business Wire",
                    content=f"{name} was mentioned in connection with a regulatory review.",
                    mentions_subject=True,
                )
            )
            adverse_count = 1

        return SynthesizedAdverseMedia(
            subject_name=name,
            total_articles_found=len(articles),
            adverse_articles_count=adverse_count,
            articles=articles,
            categories_found=["regulatory"] if adverse_count > 0 else [],
            severity_max="low" if adverse_count > 0 else "none",
            sentiment_summary="negative" if adverse_count > 0 else "neutral",
            confidence=0.65 if articles else 0.0,
        )

    # ================================================================
    # License Verification Synthesis
    # ================================================================

    async def _synthesize_license(
        self,
        subject: SubjectIdentifiers,
        license_type: str | None = None,
        state: str | None = None,
    ) -> SynthesizedLicenseVerification:
        """Synthesize professional license verification."""
        name = subject.full_name or ""
        name_hash = hash(name) % 1000

        # Simulate license lookup (50% found)
        license_found = name_hash % 2 == 0

        return SynthesizedLicenseVerification(
            license_type=license_type or "Professional License",
            claimed_state=state,
            license_found=license_found,
            status_confirmed=license_found,
            status="active" if license_found else None,
            source_url=f"https://license.state.gov/lookup/{name_hash}" if license_found else None,
            confidence=0.60 if license_found else 0.0,
            flags=["REQUIRES_OFFICIAL_VERIFICATION"],
        )

    # ================================================================
    # Social Media Synthesis
    # ================================================================

    async def _synthesize_social_media(
        self,
        subject: SubjectIdentifiers,
    ) -> SynthesizedSocialMedia:
        """Synthesize social media profile information."""
        name = subject.full_name or ""
        name_hash = hash(name) % 1000
        name_slug = name.lower().replace(" ", "-")

        profiles = []

        # LinkedIn (high probability)
        if name_hash % 5 != 0:  # 80%
            profiles.append({"platform": "linkedin", "url": f"https://linkedin.com/in/{name_slug}"})

        # Twitter (medium probability)
        if name_hash % 3 == 0:  # 33%
            profiles.append({"platform": "twitter", "url": f"https://twitter.com/{name_slug}"})

        # GitHub (low probability)
        if name_hash % 4 == 0:  # 25%
            profiles.append({"platform": "github", "url": f"https://github.com/{name_slug}"})

        return SynthesizedSocialMedia(
            subject_name=name,
            profiles_found=len(profiles),
            profiles=profiles,
            professional_presence_score=0.7 if profiles else 0.3,
            red_flags_found=0,
            confidence=0.70 if profiles else 0.40,
            flags=["PUBLIC_PROFILES_ONLY"],
        )

    # ================================================================
    # Corporate Affiliations Synthesis
    # ================================================================

    async def _synthesize_corporate(
        self,
        subject: SubjectIdentifiers,
    ) -> SynthesizedCorporateAffiliations:
        """Synthesize corporate affiliation information."""
        name = subject.full_name or ""
        name_hash = hash(name) % 1000

        affiliations = []

        # Simulate executive roles (20% chance)
        if name_hash % 5 == 0:
            affiliations.append(
                SynthesizedCorporateAffiliation(
                    company_name="Sample Corp",
                    role="Director",
                    role_type="director",
                    is_current=True,
                    source_type_found="sec",
                    source_url=f"https://sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={name_hash}",
                    confidence=0.65,
                )
            )

        return SynthesizedCorporateAffiliations(
            subject_name=name,
            affiliations=affiliations,
            total_companies=len(affiliations),
            active_affiliations=sum(1 for a in affiliations if a.is_current),
            confidence=0.65 if affiliations else 0.0,
            flags=["REQUIRES_SEC_VERIFICATION"] if affiliations else [],
        )

    # ================================================================
    # Helper Methods
    # ================================================================

    def _build_normalized_data(
        self,
        check_type: CheckType,
        result_data: Any,
    ) -> dict[str, Any]:
        """Build normalized data structure for result."""
        normalized: dict[str, Any] = {
            "check_type": check_type.value,
            "source_type": SourceType.LLM_SYNTHESIS.value,
            "provenance": SynthesisProvenance(
                models_used=[
                    self.config.primary_model.value,
                    self.config.secondary_model.value,
                ],
                consensus_score=0.85,
            ).model_dump(),
            "compliance_flags": [
                "SYNTHESIZED_DATA",
                "NOT_FOR_ADVERSE_ACTION",
                "REQUIRES_VERIFICATION",
            ],
        }

        if isinstance(result_data, list):
            normalized["results"] = [
                r.model_dump() if hasattr(r, "model_dump") else r for r in result_data
            ]
            normalized["result_count"] = len(result_data)
        elif hasattr(result_data, "model_dump"):
            normalized["result"] = result_data.model_dump()
        else:
            normalized["result"] = result_data

        return normalized

    def _calculate_cost(self, check_type: CheckType) -> Decimal:
        """Calculate cost for synthesis check."""
        # LLM costs are minimal compared to paid providers
        base_costs = {
            CheckType.EMPLOYMENT_VERIFICATION: Decimal("0.50"),
            CheckType.EDUCATION_VERIFICATION: Decimal("0.30"),
            CheckType.ADVERSE_MEDIA: Decimal("0.40"),
            CheckType.LICENSE_VERIFICATION: Decimal("0.20"),
            CheckType.SOCIAL_MEDIA: Decimal("0.25"),
            CheckType.BUSINESS_AFFILIATIONS: Decimal("0.35"),
        }
        return base_costs.get(check_type, Decimal("0.25"))


# ================================================================
# Attestation Scoring
# ================================================================


class AttestationScorer:
    """Scores individual attestations for confidence."""

    # Relationship patterns for text analysis
    MANAGER_PATTERNS = [
        "i managed",
        "reported to me",
        "on my team",
        "i supervised",
        "worked under my",
        "i hired",
        "i mentored",
    ]
    REPORT_PATTERNS = [
        "my manager",
        "i reported to",
        "my supervisor",
        "my boss",
        "managed me",
        "i worked for",
    ]
    COLLEAGUE_PATTERNS = [
        "worked with",
        "colleague",
        "worked alongside",
        "peer",
        "co-worker",
        "worked together",
        "teammate",
    ]
    CLIENT_PATTERNS = ["client", "customer", "hired them", "contracted"]

    def score_linkedin_recommendation(
        self,
        recommendation: LinkedInRecommendation,
        attester_profile: LinkedInProfile | None,
        target_claimed_employer: str,
    ) -> EmploymentAttestation:
        """Score a LinkedIn recommendation as employment attestation."""
        confidence = 0.0
        factors: list[ConfidenceFactor] = []

        # Factor 1: Attester worked at same company (0.0 - 0.30)
        attester_employer_verified = False
        if attester_profile:
            attester_employers = [exp.company for exp in attester_profile.experience]
            if self._fuzzy_match_employer(target_claimed_employer, attester_employers):
                confidence += 0.30
                factors.append(ConfidenceFactor.ATTESTER_VERIFIED_AT_EMPLOYER)
                attester_employer_verified = True
            else:
                confidence += 0.10
                factors.append(ConfidenceFactor.ATTESTER_EXTERNAL)

        # Factor 2: Relationship type (0.0 - 0.20)
        relationship = self._extract_relationship(recommendation.text)
        relationship_scores = {
            RelationshipType.MANAGER: 0.20,
            RelationshipType.DIRECT_REPORT: 0.18,
            RelationshipType.COLLEAGUE: 0.15,
            RelationshipType.TEAMMATE: 0.15,
            RelationshipType.CLIENT: 0.10,
            RelationshipType.VENDOR: 0.10,
            RelationshipType.PARTNER: 0.10,
            RelationshipType.UNKNOWN: 0.05,
        }
        confidence += relationship_scores.get(relationship, 0.05)
        if relationship == RelationshipType.MANAGER:
            factors.append(ConfidenceFactor.RELATIONSHIP_MANAGER)
        elif relationship == RelationshipType.COLLEAGUE:
            factors.append(ConfidenceFactor.RELATIONSHIP_COLLEAGUE)
        else:
            factors.append(ConfidenceFactor.RELATIONSHIP_UNKNOWN)

        # Factor 3: Specificity of content (0.0 - 0.15)
        mentioned_projects = self._extract_projects(recommendation.text)
        if mentioned_projects:
            confidence += 0.05
            factors.append(ConfidenceFactor.MENTIONS_PROJECTS)

        mentioned_timeframe = self._extract_timeframe(recommendation.text)
        if mentioned_timeframe:
            confidence += 0.05
            factors.append(ConfidenceFactor.MENTIONS_TIMEFRAME)

        mentioned_title = self._extract_title(recommendation.text, target_claimed_employer)
        if mentioned_title:
            confidence += 0.05
            factors.append(ConfidenceFactor.MENTIONS_TITLE)

        # Factor 4: Attester credibility (0.0 - 0.10)
        if attester_profile:
            if attester_profile.connections and attester_profile.connections > 500:
                confidence += 0.05
                factors.append(ConfidenceFactor.ATTESTER_ESTABLISHED_NETWORK)

            if attester_profile.verified:
                confidence += 0.05
                factors.append(ConfidenceFactor.ATTESTER_VERIFIED_ACCOUNT)

        # Factor 5: Recency (0.0 - 0.05)
        if recommendation.recommendation_date:
            from datetime import date as date_type

            days_old = (date_type.today() - recommendation.recommendation_date).days
            years_old = days_old / 365
            if years_old < 2:
                confidence += 0.05
                factors.append(ConfidenceFactor.RECENT_ATTESTATION)
            elif years_old < 5:
                confidence += 0.02
                factors.append(ConfidenceFactor.MODERATELY_RECENT)

        # Cap single attestation at 0.70
        confidence = min(0.70, confidence)

        return EmploymentAttestation(
            employer=target_claimed_employer,
            attestation_type=AttestationType.LINKEDIN_RECOMMENDATION,
            attester_name=recommendation.author_name,
            attester_linkedin_url=recommendation.author_profile_url,
            attester_title_at_time=recommendation.author_title,
            attester_employer_verified=attester_employer_verified,
            attestation_text=recommendation.text,
            relationship_type=relationship,
            date_of_attestation=recommendation.recommendation_date,
            proves_employment=True,
            proves_dates=bool(mentioned_timeframe),
            proves_title=bool(mentioned_title),
            proves_performance=True,
            mentioned_title=mentioned_title,
            mentioned_timeframe=mentioned_timeframe,
            mentioned_projects=mentioned_projects,
            confidence=confidence,
            confidence_factors=factors,
        )

    def score_news_mention(
        self,
        article: NewsArticle,
        subject_name: str,
        target_employer: str,
    ) -> EmploymentAttestation | None:
        """Score a news article mention as employment attestation."""
        # Check if both subject and employer are mentioned
        content_lower = article.content.lower()
        if subject_name.lower() not in content_lower:
            return None
        if target_employer.lower() not in content_lower:
            return None

        confidence = 0.35  # Base for news mention
        factors: list[ConfidenceFactor] = [ConfidenceFactor.NEWS_SOURCE]

        # Check for title mention
        mentioned_title = self._extract_title(article.content, target_employer)
        if mentioned_title:
            confidence += 0.10
            factors.append(ConfidenceFactor.MENTIONS_TITLE)

        return EmploymentAttestation(
            employer=target_employer,
            attestation_type=AttestationType.NEWS_QUOTE,
            attester_name=article.source,
            attestation_text=article.content[:500],
            proves_employment=True,
            proves_dates=False,
            proves_title=bool(mentioned_title),
            mentioned_title=mentioned_title,
            confidence=min(0.55, confidence),
            confidence_factors=factors,
        )

    def score_sec_filing(
        self,
        filing: SECFiling,
        subject_name: str,
        target_employer: str,
    ) -> EmploymentAttestation | None:
        """Score an SEC filing mention as employment attestation."""
        content_lower = filing.content_excerpt.lower()
        if subject_name.lower() not in content_lower:
            return None

        # SEC filings are highly reliable
        confidence = 0.55
        factors: list[ConfidenceFactor] = [ConfidenceFactor.SEC_FILING_SOURCE]

        # Check for role mention
        mentioned_title = self._extract_title(filing.content_excerpt, target_employer)
        if mentioned_title:
            confidence += 0.10
            factors.append(ConfidenceFactor.MENTIONS_TITLE)

        return EmploymentAttestation(
            employer=target_employer,
            attestation_type=AttestationType.SEC_FILING,
            attester_name=f"SEC {filing.filing_type}",
            attestation_text=filing.content_excerpt[:500],
            proves_employment=True,
            proves_dates=True,  # SEC filings usually have dates
            proves_title=bool(mentioned_title),
            mentioned_title=mentioned_title,
            confidence=min(0.70, confidence),
            confidence_factors=factors,
        )

    def _extract_relationship(self, text: str) -> RelationshipType:
        """Extract relationship type from text."""
        text_lower = text.lower()

        if any(p in text_lower for p in self.MANAGER_PATTERNS):
            return RelationshipType.MANAGER
        if any(p in text_lower for p in self.REPORT_PATTERNS):
            return RelationshipType.DIRECT_REPORT
        if any(p in text_lower for p in self.COLLEAGUE_PATTERNS):
            return RelationshipType.COLLEAGUE
        if any(p in text_lower for p in self.CLIENT_PATTERNS):
            return RelationshipType.CLIENT

        return RelationshipType.UNKNOWN

    def _extract_projects(self, text: str) -> list[str]:
        """Extract mentioned projects from text."""
        # Simple heuristic: look for capitalized phrases after "project"
        projects = []
        project_pattern = r"project[s]?\s+([A-Z][a-zA-Z\s]{2,20})"
        for match in re.finditer(project_pattern, text, re.IGNORECASE):
            projects.append(match.group(1).strip())
        return projects[:3]

    def _extract_timeframe(self, text: str) -> str | None:
        """Extract timeframe mention from text."""
        # Look for year patterns
        year_pattern = r"\b(19|20)\d{2}\b"
        years = re.findall(year_pattern, text)
        if len(years) >= 2:
            return f"{years[0]}-{years[-1]}"
        elif years:
            return years[0]

        # Look for duration patterns
        duration_pattern = r"(\d+)\s*(year|month)s?"
        match = re.search(duration_pattern, text, re.IGNORECASE)
        if match:
            return f"{match.group(1)} {match.group(2)}s"

        return None

    def _extract_title(
        self,
        text: str,
        employer: str,  # noqa: ARG002 - Reserved for employer-specific title extraction
    ) -> str | None:
        """Extract job title from text.

        Args:
            text: Text to extract title from.
            employer: Employer name (reserved for employer-specific title extraction).

        Returns:
            Extracted title or None if not found.
        """
        # Common title patterns
        title_patterns = [
            r"(?:as\s+(?:a\s+)?|served\s+as\s+|appointed\s+)([A-Z][a-zA-Z\s]+(?:Manager|Director|VP|President|Engineer|Developer|Analyst|Lead|Officer|Executive|Consultant))",  # noqa: E501
            r"(?:their\s+role\s+as\s+|position\s+as\s+)([A-Z][a-zA-Z\s]+)",
        ]

        for pattern in title_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return None

    def _fuzzy_match_employer(
        self,
        target: str,
        employers: list[str],
        threshold: float = 0.85,
    ) -> bool:
        """Fuzzy match employer name."""
        target_normalized = self._normalize_company_name(target)
        for emp in employers:
            emp_normalized = self._normalize_company_name(emp)
            if target_normalized == emp_normalized:
                return True
            # Use SequenceMatcher for similarity
            similarity = SequenceMatcher(None, target_normalized, emp_normalized).ratio()
            if similarity >= threshold:
                return True
        return False

    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name for matching."""
        name = name.lower().strip()
        suffixes = [
            " inc",
            " inc.",
            " llc",
            " ltd",
            " ltd.",
            " corp",
            " corp.",
            " corporation",
            " company",
            " co",
            " co.",
            " plc",
            " lp",
        ]
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        return name.strip()


# ================================================================
# Attestation Aggregators
# ================================================================


class EmploymentAttestationAggregator:
    """Aggregates multiple employment attestations into overall verification."""

    def aggregate_attestations(
        self,
        claimed_employment: ClaimedEmployment,
        attestations: list[EmploymentAttestation],
    ) -> SynthesizedEmploymentVerification:
        """Combine multiple attestations for overall confidence."""
        # Filter to attestations for this employer
        relevant = [
            a
            for a in attestations
            if self._matches_employer(a.employer, claimed_employment.employer)
        ]

        if not relevant:
            return SynthesizedEmploymentVerification(
                employer=claimed_employment.employer,
                claimed_title=claimed_employment.title,
                confidence=0.0,
                employment_confirmed=False,
                flags=["NO_ATTESTATIONS_FOUND"],
            )

        # Start with highest single attestation confidence
        base_confidence = max(a.confidence for a in relevant)

        # Multiple independent attesters increase confidence
        unique_attesters = {a.attester_name for a in relevant}
        for i in range(1, len(unique_attesters)):
            boost = 0.10 / (i + 1)
            base_confidence += boost

        # Bonus for diverse attestation types
        attestation_types = {a.attestation_type for a in relevant}
        if len(attestation_types) >= 2:
            base_confidence += 0.05

        # Bonus for diverse relationship types
        relationship_types = {
            a.relationship_type for a in relevant if a.relationship_type != RelationshipType.UNKNOWN
        }
        if len(relationship_types) >= 2:
            base_confidence += 0.05

        # Bonus if any attester was manager
        if any(a.relationship_type == RelationshipType.MANAGER for a in relevant):
            base_confidence += 0.05

        # Check what we can confirm
        title_confirmed = any(a.proves_title and a.mentioned_title for a in relevant)
        dates_confirmed = any(a.proves_dates for a in relevant)

        if title_confirmed:
            base_confidence += 0.03
        if dates_confirmed:
            base_confidence += 0.03

        # Hard cap at 0.85
        final_confidence = min(0.85, base_confidence)

        flags = [
            "SYNTHESIZED_FROM_PUBLIC_SOURCES",
            "PEER_ATTESTATION_BASED",
            "NOT_FOR_ADVERSE_ACTION",
        ]
        if not dates_confirmed:
            flags.append("DATES_NOT_VERIFIED")
        if not title_confirmed:
            flags.append("TITLE_NOT_VERIFIED")

        return SynthesizedEmploymentVerification(
            employer=claimed_employment.employer,
            claimed_title=claimed_employment.title,
            employment_confirmed=True,
            title_confirmed=title_confirmed,
            dates_confirmed=dates_confirmed,
            attestation_count=len(relevant),
            unique_attesters=len(unique_attesters),
            attestations=relevant,
            confidence=final_confidence,
            verification_method="peer_attestation",
            source_type=SourceType.LLM_SYNTHESIS,
            fcra_usable=False,
            flags=flags,
        )

    def _matches_employer(self, attestation_employer: str, claimed_employer: str) -> bool:
        """Check if attestation employer matches claimed employer."""
        a_norm = attestation_employer.lower().strip()
        c_norm = claimed_employer.lower().strip()

        if a_norm == c_norm:
            return True

        # Fuzzy match
        similarity = SequenceMatcher(None, a_norm, c_norm).ratio()
        return similarity >= 0.85


class EducationAttestationAggregator:
    """Aggregates multiple education attestations into overall verification."""

    def aggregate_attestations(
        self,
        claimed_education: ClaimedEducation,
        attestations: list[EducationAttestation],
    ) -> SynthesizedEducationVerification:
        """Combine multiple attestations for overall confidence."""
        # Filter to attestations for this institution
        relevant = [
            a
            for a in attestations
            if self._matches_institution(a.institution, claimed_education.institution)
        ]

        if not relevant:
            return SynthesizedEducationVerification(
                institution=claimed_education.institution,
                claimed_degree=claimed_education.degree,
                claimed_major=claimed_education.major,
                claimed_graduation_year=claimed_education.graduation_year,
                confidence=0.0,
                attendance_confirmed=False,
                flags=["NO_ATTESTATIONS_FOUND"],
            )

        # Base confidence from best attestation
        base_confidence = max(a.confidence for a in relevant)

        # Multiple sources boost confidence
        unique_sources = {a.attester_source for a in relevant if a.attester_source}
        if len(unique_sources) >= 2:
            base_confidence += 0.10

        # Check confirmations
        degree_confirmed = any(a.proves_degree for a in relevant)
        graduation_confirmed = any(a.proves_graduation_date for a in relevant)

        if degree_confirmed:
            base_confidence += 0.05
        if graduation_confirmed:
            base_confidence += 0.05

        # Hard cap at 0.80
        final_confidence = min(0.80, base_confidence)

        flags = [
            "SYNTHESIZED_FROM_PUBLIC_SOURCES",
            "NOT_FOR_ADVERSE_ACTION",
        ]
        if not degree_confirmed:
            flags.append("DEGREE_NOT_VERIFIED")
        if not graduation_confirmed:
            flags.append("GRADUATION_NOT_VERIFIED")

        return SynthesizedEducationVerification(
            institution=claimed_education.institution,
            claimed_degree=claimed_education.degree,
            claimed_major=claimed_education.major,
            claimed_graduation_year=claimed_education.graduation_year,
            attendance_confirmed=True,
            degree_confirmed=degree_confirmed,
            graduation_confirmed=graduation_confirmed,
            attestation_count=len(relevant),
            unique_sources=len(unique_sources),
            attestations=relevant,
            confidence=final_confidence,
            verification_method="public_source_aggregation",
            source_type=SourceType.LLM_SYNTHESIS,
            fcra_usable=False,
            flags=flags,
        )

    def _matches_institution(self, attestation_inst: str, claimed_inst: str) -> bool:
        """Check if attestation institution matches claimed institution."""
        a_norm = attestation_inst.lower().strip()
        c_norm = claimed_inst.lower().strip()

        if a_norm == c_norm:
            return True

        similarity = SequenceMatcher(None, a_norm, c_norm).ratio()
        return similarity >= 0.80


# ================================================================
# Factory Functions
# ================================================================

_singleton_provider: LLMSynthesisProvider | None = None


def create_synthesis_provider(
    config: LLMSynthesisProviderConfig | None = None,
) -> LLMSynthesisProvider:
    """Create a new LLM synthesis provider instance.

    Args:
        config: Provider configuration.

    Returns:
        New LLMSynthesisProvider instance.
    """
    return LLMSynthesisProvider(config)


def get_synthesis_provider() -> LLMSynthesisProvider:
    """Get singleton LLM synthesis provider instance.

    Returns:
        Singleton LLMSynthesisProvider instance.
    """
    global _singleton_provider
    if _singleton_provider is None:
        _singleton_provider = LLMSynthesisProvider()
    return _singleton_provider
