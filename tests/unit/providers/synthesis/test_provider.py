"""Tests for LLM Synthesis Provider."""

from decimal import Decimal

import pytest

from elile.compliance.types import CheckType, Locale
from elile.entity.types import SubjectIdentifiers
from elile.providers.synthesis.provider import (
    SUPPORTED_CHECK_TYPES,
    AttestationScorer,
    ClaimedEducation,
    ClaimedEmployment,
    EducationAttestationAggregator,
    EmploymentAttestationAggregator,
    LLMSynthesisProvider,
    create_synthesis_provider,
    get_synthesis_provider,
)
from elile.providers.synthesis.types import (
    AttestationType,
    ConfidenceFactor,
    EmploymentAttestation,
    LinkedInExperience,
    LinkedInProfile,
    LinkedInRecommendation,
    LLMSynthesisProviderConfig,
    NewsArticle,
    RelationshipType,
    SECFiling,
    SourceType,
    SynthesisLLMModel,
    UnsupportedCheckTypeError,
)
from elile.providers.types import DataSourceCategory, ProviderStatus


class TestLLMSynthesisProviderInit:
    """Tests for LLMSynthesisProvider initialization."""

    def test_default_initialization(self) -> None:
        """Test provider initializes with default config."""
        provider = LLMSynthesisProvider()
        assert provider.provider_id == "llm_synthesis"
        assert provider.config.primary_model == SynthesisLLMModel.CLAUDE_SONNET
        assert provider.config.require_consensus is True

    def test_custom_config_initialization(self) -> None:
        """Test provider initializes with custom config."""
        config = LLMSynthesisProviderConfig(
            primary_model=SynthesisLLMModel.GPT4,
            require_consensus=False,
        )
        provider = LLMSynthesisProvider(config)
        assert provider.config.primary_model == SynthesisLLMModel.GPT4
        assert provider.config.require_consensus is False

    def test_provider_info(self) -> None:
        """Test provider info is correctly set."""
        provider = LLMSynthesisProvider()
        info = provider.provider_info

        assert info.provider_id == "llm_synthesis"
        assert info.name == "LLM Synthesis Provider"
        assert info.category == DataSourceCategory.CORE
        assert len(info.capabilities) == len(SUPPORTED_CHECK_TYPES)

    def test_supported_checks(self) -> None:
        """Test supported check types."""
        provider = LLMSynthesisProvider()
        checks = provider.supported_checks

        assert CheckType.EMPLOYMENT_VERIFICATION in checks
        assert CheckType.EDUCATION_VERIFICATION in checks
        assert CheckType.ADVERSE_MEDIA in checks
        assert CheckType.LICENSE_VERIFICATION in checks
        assert CheckType.SOCIAL_MEDIA in checks
        assert CheckType.BUSINESS_AFFILIATIONS in checks

        # NOT supported
        assert CheckType.CREDIT_REPORT not in checks
        assert CheckType.CRIMINAL_NATIONAL not in checks


class TestLLMSynthesisProviderExecuteCheck:
    """Tests for LLMSynthesisProvider.execute_check method."""

    @pytest.fixture
    def provider(self) -> LLMSynthesisProvider:
        """Create a provider instance."""
        return LLMSynthesisProvider()

    @pytest.mark.asyncio
    async def test_execute_check_no_name(self, provider: LLMSynthesisProvider) -> None:
        """Test execute_check fails without full_name."""
        subject = SubjectIdentifiers()

        result = await provider.execute_check(
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is False
        assert result.error_code == "INVALID_SUBJECT"

    @pytest.mark.asyncio
    async def test_execute_check_employment(self, provider: LLMSynthesisProvider) -> None:
        """Test execute_check for employment verification."""
        subject = SubjectIdentifiers(full_name="John Smith")

        result = await provider.execute_check(
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is True
        assert result.provider_id == "llm_synthesis"
        assert result.query_id is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_check_education(self, provider: LLMSynthesisProvider) -> None:
        """Test execute_check for education verification."""
        subject = SubjectIdentifiers(full_name="Jane Doe")

        result = await provider.execute_check(
            check_type=CheckType.EDUCATION_VERIFICATION,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is True
        assert "check_type" in result.normalized_data

    @pytest.mark.asyncio
    async def test_execute_check_adverse_media(self, provider: LLMSynthesisProvider) -> None:
        """Test execute_check for adverse media."""
        subject = SubjectIdentifiers(full_name="Media Test")

        result = await provider.execute_check(
            check_type=CheckType.ADVERSE_MEDIA,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is True
        assert result.normalized_data["source_type"] == SourceType.LLM_SYNTHESIS.value

    @pytest.mark.asyncio
    async def test_execute_check_license(self, provider: LLMSynthesisProvider) -> None:
        """Test execute_check for license verification."""
        subject = SubjectIdentifiers(full_name="License Test")

        result = await provider.execute_check(
            check_type=CheckType.LICENSE_VERIFICATION,
            subject=subject,
            locale=Locale.US,
            options={"license_type": "CPA", "state": "CA"},
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_check_social_media(self, provider: LLMSynthesisProvider) -> None:
        """Test execute_check for social media."""
        subject = SubjectIdentifiers(full_name="Social Test")

        result = await provider.execute_check(
            check_type=CheckType.SOCIAL_MEDIA,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_check_corporate(self, provider: LLMSynthesisProvider) -> None:
        """Test execute_check for corporate affiliations."""
        subject = SubjectIdentifiers(full_name="Corporate Test")

        result = await provider.execute_check(
            check_type=CheckType.BUSINESS_AFFILIATIONS,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_check_unsupported(self, provider: LLMSynthesisProvider) -> None:
        """Test execute_check raises for unsupported check type."""
        subject = SubjectIdentifiers(full_name="Test")

        with pytest.raises(UnsupportedCheckTypeError):
            await provider.execute_check(
                check_type=CheckType.CREDIT_REPORT,
                subject=subject,
                locale=Locale.US,
            )

    @pytest.mark.asyncio
    async def test_execute_check_includes_compliance_flags(
        self, provider: LLMSynthesisProvider
    ) -> None:
        """Test execute_check includes compliance flags."""
        subject = SubjectIdentifiers(full_name="Compliance Test")

        result = await provider.execute_check(
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is True
        flags = result.normalized_data.get("compliance_flags", [])
        assert "SYNTHESIZED_DATA" in flags
        assert "NOT_FOR_ADVERSE_ACTION" in flags

    @pytest.mark.asyncio
    async def test_execute_check_includes_cost(self, provider: LLMSynthesisProvider) -> None:
        """Test execute_check includes cost information."""
        subject = SubjectIdentifiers(full_name="Cost Test")

        result = await provider.execute_check(
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            subject=subject,
            locale=Locale.US,
        )

        assert result.cost_incurred is not None
        assert result.cost_incurred >= Decimal("0.00")
        assert result.cost_incurred < Decimal("1.00")  # LLM synthesis is cheap


class TestLLMSynthesisProviderHealthCheck:
    """Tests for LLMSynthesisProvider.health_check method."""

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """Test health check returns healthy status."""
        provider = LLMSynthesisProvider()
        health = await provider.health_check()

        assert health.provider_id == "llm_synthesis"
        assert health.status == ProviderStatus.HEALTHY
        assert health.latency_ms >= 0


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_synthesis_provider(self) -> None:
        """Test create_synthesis_provider factory."""
        provider = create_synthesis_provider()
        assert isinstance(provider, LLMSynthesisProvider)

    def test_create_synthesis_provider_with_config(self) -> None:
        """Test create_synthesis_provider with custom config."""
        config = LLMSynthesisProviderConfig(require_consensus=False)
        provider = create_synthesis_provider(config)
        assert provider.config.require_consensus is False

    def test_get_synthesis_provider_singleton(self) -> None:
        """Test get_synthesis_provider returns singleton."""
        provider1 = get_synthesis_provider()
        provider2 = get_synthesis_provider()
        assert provider1 is provider2


class TestAttestationScorer:
    """Tests for AttestationScorer."""

    @pytest.fixture
    def scorer(self) -> AttestationScorer:
        """Create a scorer instance."""
        return AttestationScorer()

    def test_score_linkedin_recommendation_basic(self, scorer: AttestationScorer) -> None:
        """Test basic LinkedIn recommendation scoring."""
        recommendation = LinkedInRecommendation(
            author_name="Test Author",
            text="I worked with John at Acme Corp.",
        )
        attester_profile = LinkedInProfile(
            profile_url="https://linkedin.com/in/test",
            full_name="Test Author",
            experience=[LinkedInExperience(company="Acme Corporation", title="Manager")],
        )

        att = scorer.score_linkedin_recommendation(
            recommendation=recommendation,
            attester_profile=attester_profile,
            target_claimed_employer="Acme Corp",
        )

        assert att.employer == "Acme Corp"
        assert att.attestation_type == AttestationType.LINKEDIN_RECOMMENDATION
        assert att.confidence > 0.0
        assert att.confidence <= 0.70

    def test_score_linkedin_recommendation_manager_relationship(
        self, scorer: AttestationScorer
    ) -> None:
        """Test scoring with manager relationship detected."""
        recommendation = LinkedInRecommendation(
            author_name="Manager",
            text="I managed John for 2 years on my team.",
        )

        att = scorer.score_linkedin_recommendation(
            recommendation=recommendation,
            attester_profile=None,
            target_claimed_employer="Company",
        )

        assert att.relationship_type == RelationshipType.MANAGER
        assert ConfidenceFactor.RELATIONSHIP_MANAGER in att.confidence_factors

    def test_score_linkedin_recommendation_colleague_relationship(
        self, scorer: AttestationScorer
    ) -> None:
        """Test scoring with colleague relationship detected."""
        recommendation = LinkedInRecommendation(
            author_name="Peer",
            text="I worked alongside John as a colleague.",
        )

        att = scorer.score_linkedin_recommendation(
            recommendation=recommendation,
            attester_profile=None,
            target_claimed_employer="Company",
        )

        assert att.relationship_type == RelationshipType.COLLEAGUE

    def test_score_news_mention(self, scorer: AttestationScorer) -> None:
        """Test news article mention scoring."""
        article = NewsArticle(
            url="https://news.com/article",
            title="Executive Appointment",
            source="Business News",
            content="John Smith has been appointed as VP at Tech Corp.",
        )

        att = scorer.score_news_mention(
            article=article,
            subject_name="John Smith",
            target_employer="Tech Corp",
        )

        assert att is not None
        assert att.attestation_type == AttestationType.NEWS_QUOTE
        assert ConfidenceFactor.NEWS_SOURCE in att.confidence_factors

    def test_score_news_mention_no_match(self, scorer: AttestationScorer) -> None:
        """Test news article returns None when no match."""
        article = NewsArticle(
            url="https://news.com/article",
            title="Other News",
            source="News",
            content="Unrelated content about other topics.",
        )

        att = scorer.score_news_mention(
            article=article,
            subject_name="John Smith",
            target_employer="Tech Corp",
        )

        assert att is None

    def test_score_sec_filing(self, scorer: AttestationScorer) -> None:
        """Test SEC filing scoring."""
        from datetime import date

        filing = SECFiling(
            filing_type="DEF 14A",
            company_name="Tech Corp",
            filing_date=date.today(),
            url="https://sec.gov/filing/123",
            content_excerpt="JOHN SMITH, age 50, serves as Vice President.",
        )

        att = scorer.score_sec_filing(
            filing=filing,
            subject_name="John Smith",
            target_employer="Tech Corp",
        )

        assert att is not None
        assert att.attestation_type == AttestationType.SEC_FILING
        assert ConfidenceFactor.SEC_FILING_SOURCE in att.confidence_factors
        assert att.proves_dates is True

    def test_extract_relationship_unknown(self, scorer: AttestationScorer) -> None:
        """Test relationship extraction returns unknown for ambiguous text."""
        relationship = scorer._extract_relationship("Great professional skills.")
        assert relationship == RelationshipType.UNKNOWN

    def test_fuzzy_match_employer(self, scorer: AttestationScorer) -> None:
        """Test fuzzy employer matching."""
        # Exact match with normalization
        assert scorer._fuzzy_match_employer("Acme Corp", ["Acme Corporation"])

        # Case insensitive
        assert scorer._fuzzy_match_employer("ACME", ["acme inc"])

        # No match
        assert not scorer._fuzzy_match_employer("Apple", ["Microsoft", "Google"])

    def test_normalize_company_name(self, scorer: AttestationScorer) -> None:
        """Test company name normalization."""
        assert scorer._normalize_company_name("Acme Inc.") == "acme"
        assert scorer._normalize_company_name("Tech Corp") == "tech"
        assert scorer._normalize_company_name("Company LLC") == "company"


class TestEmploymentAttestationAggregator:
    """Tests for EmploymentAttestationAggregator."""

    @pytest.fixture
    def aggregator(self) -> EmploymentAttestationAggregator:
        """Create an aggregator instance."""
        return EmploymentAttestationAggregator()

    def test_aggregate_no_attestations(self, aggregator: EmploymentAttestationAggregator) -> None:
        """Test aggregation with no attestations."""
        claimed = ClaimedEmployment(employer="Test Co", title="Manager")

        result = aggregator.aggregate_attestations(
            claimed_employment=claimed,
            attestations=[],
        )

        assert result.employer == "Test Co"
        assert result.employment_confirmed is False
        assert result.confidence == 0.0
        assert "NO_ATTESTATIONS_FOUND" in result.flags

    def test_aggregate_single_attestation(
        self, aggregator: EmploymentAttestationAggregator
    ) -> None:
        """Test aggregation with single attestation."""
        claimed = ClaimedEmployment(employer="Test Co", title="Manager")
        attestation = EmploymentAttestation(
            employer="Test Co",
            attestation_type=AttestationType.LINKEDIN_RECOMMENDATION,
            attester_name="Colleague",
            attestation_text="Great work",
            confidence=0.50,
        )

        result = aggregator.aggregate_attestations(
            claimed_employment=claimed,
            attestations=[attestation],
        )

        assert result.employment_confirmed is True
        assert result.attestation_count == 1
        assert result.confidence >= 0.50

    def test_aggregate_multiple_attestations(
        self, aggregator: EmploymentAttestationAggregator
    ) -> None:
        """Test aggregation with multiple attestations boosts confidence."""
        claimed = ClaimedEmployment(employer="Test Co", title="Manager")
        attestations = [
            EmploymentAttestation(
                employer="Test Co",
                attestation_type=AttestationType.LINKEDIN_RECOMMENDATION,
                attester_name="Person A",
                attestation_text="Great",
                confidence=0.50,
            ),
            EmploymentAttestation(
                employer="Test Co",
                attestation_type=AttestationType.NEWS_QUOTE,
                attester_name="Person B",
                attestation_text="Mentioned",
                confidence=0.40,
            ),
        ]

        result = aggregator.aggregate_attestations(
            claimed_employment=claimed,
            attestations=attestations,
        )

        assert result.attestation_count == 2
        assert result.unique_attesters == 2
        # Should be boosted above single max
        assert result.confidence > 0.50

    def test_aggregate_caps_at_85(self, aggregator: EmploymentAttestationAggregator) -> None:
        """Test aggregation caps confidence at 0.85."""
        claimed = ClaimedEmployment(employer="Test Co")
        attestations = [
            EmploymentAttestation(
                employer="Test Co",
                attestation_type=AttestationType.LINKEDIN_RECOMMENDATION,
                attester_name=f"Person {i}",
                attestation_text="Great",
                confidence=0.70,
                relationship_type=RelationshipType.MANAGER,
                proves_title=True,
                mentioned_title="VP",
                proves_dates=True,
            )
            for i in range(10)
        ]

        result = aggregator.aggregate_attestations(
            claimed_employment=claimed,
            attestations=attestations,
        )

        assert result.confidence <= 0.85


class TestEducationAttestationAggregator:
    """Tests for EducationAttestationAggregator."""

    @pytest.fixture
    def aggregator(self) -> EducationAttestationAggregator:
        """Create an aggregator instance."""
        return EducationAttestationAggregator()

    def test_aggregate_no_attestations(self, aggregator: EducationAttestationAggregator) -> None:
        """Test aggregation with no attestations."""

        claimed = ClaimedEducation(institution="Test University", degree="BS")

        result = aggregator.aggregate_attestations(
            claimed_education=claimed,
            attestations=[],
        )

        assert result.attendance_confirmed is False
        assert "NO_ATTESTATIONS_FOUND" in result.flags

    def test_aggregate_caps_at_80(self, aggregator: EducationAttestationAggregator) -> None:
        """Test aggregation caps confidence at 0.80."""
        from elile.providers.synthesis.types import EducationAttestation

        claimed = ClaimedEducation(institution="Test University")
        attestations = [
            EducationAttestation(
                institution="Test University",
                attestation_type=AttestationType.ALUMNI_DIRECTORY,
                attester_name=f"Source {i}",
                attester_source=f"https://source{i}.edu",
                attestation_text="Attended",
                confidence=0.70,
                proves_degree=True,
                proves_graduation_date=True,
            )
            for i in range(5)
        ]

        result = aggregator.aggregate_attestations(
            claimed_education=claimed,
            attestations=attestations,
        )

        assert result.confidence <= 0.80


class TestDeterministicResults:
    """Tests for deterministic result generation."""

    @pytest.fixture
    def provider(self) -> LLMSynthesisProvider:
        """Create a provider instance."""
        return LLMSynthesisProvider()

    @pytest.mark.asyncio
    async def test_same_name_same_results(self, provider: LLMSynthesisProvider) -> None:
        """Test that same name produces same results."""
        subject = SubjectIdentifiers(full_name="Deterministic Test")

        result1 = await provider.execute_check(
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            subject=subject,
            locale=Locale.US,
        )
        result2 = await provider.execute_check(
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            subject=subject,
            locale=Locale.US,
        )

        # Results should be consistent
        assert result1.success == result2.success

    @pytest.mark.asyncio
    async def test_different_names_may_differ(self, provider: LLMSynthesisProvider) -> None:
        """Test that different names may produce different results."""
        subject1 = SubjectIdentifiers(full_name="Person One Unique")
        subject2 = SubjectIdentifiers(full_name="Person Two Different")

        result1 = await provider.execute_check(
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            subject=subject1,
            locale=Locale.US,
        )
        result2 = await provider.execute_check(
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            subject=subject2,
            locale=Locale.US,
        )

        # Both should succeed
        assert result1.success is True
        assert result2.success is True


class TestNormalizedOutput:
    """Tests for normalized output structure."""

    @pytest.fixture
    def provider(self) -> LLMSynthesisProvider:
        """Create a provider instance."""
        return LLMSynthesisProvider()

    @pytest.mark.asyncio
    async def test_normalized_data_structure(self, provider: LLMSynthesisProvider) -> None:
        """Test normalized data has expected structure."""
        subject = SubjectIdentifiers(full_name="Structure Test")

        result = await provider.execute_check(
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            subject=subject,
            locale=Locale.US,
        )

        data = result.normalized_data

        # Check required fields
        assert "check_type" in data
        assert "source_type" in data
        assert "provenance" in data
        assert "compliance_flags" in data

        # Check provenance structure
        prov = data["provenance"]
        assert "models_used" in prov
        assert "consensus_score" in prov

    @pytest.mark.asyncio
    async def test_compliance_flags_present(self, provider: LLMSynthesisProvider) -> None:
        """Test compliance flags are always present."""
        subject = SubjectIdentifiers(full_name="Flags Test")

        for check_type in SUPPORTED_CHECK_TYPES:
            result = await provider.execute_check(
                check_type=check_type,
                subject=subject,
                locale=Locale.US,
            )

            flags = result.normalized_data.get("compliance_flags", [])
            assert "SYNTHESIZED_DATA" in flags
            assert "NOT_FOR_ADVERSE_ACTION" in flags
