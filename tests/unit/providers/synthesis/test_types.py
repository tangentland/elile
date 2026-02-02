"""Tests for LLM Synthesis Provider types."""

from datetime import date, datetime
from uuid import UUID

from elile.providers.synthesis.types import (
    AttestationType,
    ConsensusFailedError,
    EducationAttestation,
    EmploymentAttestation,
    LinkedInEducation,
    LinkedInExperience,
    LinkedInProfile,
    LinkedInRecommendation,
    LLMExtractionError,
    LLMSynthesisProviderConfig,
    NewsArticle,
    PublicSource,
    PublicSourceType,
    RelationshipType,
    SECFiling,
    SourceFetchError,
    SourceType,
    SynthesisLLMModel,
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


class TestSourceTypeEnum:
    """Tests for SourceType enum."""

    def test_values(self) -> None:
        """Test enum has expected values."""
        assert SourceType.LLM_SYNTHESIS == "llm_synthesis"
        assert SourceType.OFFICIAL_PROVIDER == "official_provider"
        assert SourceType.PUBLIC_RECORD == "public_record"


class TestAttestationTypeEnum:
    """Tests for AttestationType enum."""

    def test_linkedin_types(self) -> None:
        """Test LinkedIn attestation types."""
        assert AttestationType.LINKEDIN_RECOMMENDATION == "linkedin_recommendation"
        assert AttestationType.LINKEDIN_SKILL_ENDORSEMENT == "linkedin_skill_endorsement"
        assert AttestationType.LINKEDIN_COWORKER_CONNECTION == "linkedin_coworker"

    def test_professional_types(self) -> None:
        """Test professional attestation types."""
        assert AttestationType.COAUTHORED_PAPER == "coauthored_paper"
        assert AttestationType.CONFERENCE_SPEAKER == "conference_speaker"
        assert AttestationType.SEC_FILING == "sec_filing"


class TestRelationshipTypeEnum:
    """Tests for RelationshipType enum."""

    def test_work_relationships(self) -> None:
        """Test work relationship types."""
        assert RelationshipType.MANAGER == "manager"
        assert RelationshipType.DIRECT_REPORT == "direct_report"
        assert RelationshipType.COLLEAGUE == "colleague"

    def test_education_relationships(self) -> None:
        """Test education relationship types."""
        assert RelationshipType.CLASSMATE == "classmate"
        assert RelationshipType.PROFESSOR == "professor"

    def test_unknown(self) -> None:
        """Test unknown relationship type."""
        assert RelationshipType.UNKNOWN == "unknown"


class TestPublicSourceTypeEnum:
    """Tests for PublicSourceType enum."""

    def test_linkedin_types(self) -> None:
        """Test LinkedIn source types."""
        assert PublicSourceType.LINKEDIN_PROFILE == "linkedin_profile"
        assert PublicSourceType.LINKEDIN_RECOMMENDATION == "linkedin_recommendation"

    def test_official_types(self) -> None:
        """Test official source types."""
        assert PublicSourceType.SEC_FILING == "sec_filing"
        assert PublicSourceType.STATE_LICENSE_BOARD == "state_license_board"


class TestSynthesisLLMModelEnum:
    """Tests for SynthesisLLMModel enum."""

    def test_model_values(self) -> None:
        """Test model enum values."""
        assert SynthesisLLMModel.CLAUDE_OPUS == "claude-3-opus"
        assert SynthesisLLMModel.CLAUDE_SONNET == "claude-3-sonnet"
        assert SynthesisLLMModel.GPT4 == "gpt-4"
        assert SynthesisLLMModel.GPT4_TURBO == "gpt-4-turbo"
        assert SynthesisLLMModel.GEMINI_PRO == "gemini-pro"


class TestPublicSource:
    """Tests for PublicSource model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        source = PublicSource(
            source_type=PublicSourceType.NEWS_ARTICLE,
            url="https://example.com/article",
            content="Article content here",
        )
        assert source.source_type == PublicSourceType.NEWS_ARTICLE
        assert source.url == "https://example.com/article"
        assert isinstance(source.source_id, UUID)

    def test_default_metadata(self) -> None:
        """Test default metadata is empty dict."""
        source = PublicSource(source_type=PublicSourceType.LINKEDIN_PROFILE)
        assert source.metadata == {}

    def test_retrieved_at_auto(self) -> None:
        """Test retrieved_at is auto-populated."""
        source = PublicSource(source_type=PublicSourceType.LINKEDIN_PROFILE)
        assert source.retrieved_at is not None
        assert isinstance(source.retrieved_at, datetime)


class TestLinkedInProfile:
    """Tests for LinkedInProfile model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        profile = LinkedInProfile(
            profile_url="https://linkedin.com/in/test",
            full_name="Test User",
            headline="Software Engineer",
            connections=500,
        )
        assert profile.full_name == "Test User"
        assert profile.connections == 500
        assert profile.verified is False

    def test_with_experience(self) -> None:
        """Test with experience entries."""
        profile = LinkedInProfile(
            profile_url="https://linkedin.com/in/test",
            full_name="Test User",
            experience=[
                LinkedInExperience(
                    company="Tech Co",
                    title="Engineer",
                    is_current=True,
                )
            ],
        )
        assert len(profile.experience) == 1
        assert profile.experience[0].is_current is True


class TestLinkedInExperience:
    """Tests for LinkedInExperience model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        exp = LinkedInExperience(
            company="Test Company",
            title="Manager",
            start_date=date(2020, 1, 1),
        )
        assert exp.company == "Test Company"
        assert exp.is_current is False

    def test_current_position(self) -> None:
        """Test current position flag."""
        exp = LinkedInExperience(
            company="Test Company",
            title="Manager",
            is_current=True,
        )
        assert exp.is_current is True
        assert exp.end_date is None


class TestLinkedInEducation:
    """Tests for LinkedInEducation model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        edu = LinkedInEducation(
            institution="Test University",
            degree="BS",
            field_of_study="Computer Science",
            end_year=2020,
        )
        assert edu.institution == "Test University"
        assert edu.end_year == 2020


class TestLinkedInRecommendation:
    """Tests for LinkedInRecommendation model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        rec = LinkedInRecommendation(
            author_name="Recommender",
            author_profile_url="https://linkedin.com/in/recommender",
            text="Great colleague to work with.",
        )
        assert rec.author_name == "Recommender"
        assert rec.text == "Great colleague to work with."


class TestNewsArticle:
    """Tests for NewsArticle model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        article = NewsArticle(
            url="https://news.com/article",
            title="Test Article",
            source="News Source",
            content="Article content.",
        )
        assert article.title == "Test Article"
        assert article.mentions_subject is True


class TestSECFiling:
    """Tests for SECFiling model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        filing = SECFiling(
            filing_type="10-K",
            company_name="Test Corp",
            filing_date=date(2024, 1, 15),
            url="https://sec.gov/filing/123",
            content_excerpt="Executive officers section...",
        )
        assert filing.filing_type == "10-K"
        assert filing.company_name == "Test Corp"


class TestEmploymentAttestation:
    """Tests for EmploymentAttestation model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        att = EmploymentAttestation(
            employer="Test Company",
            attestation_type=AttestationType.LINKEDIN_RECOMMENDATION,
            attester_name="John Doe",
            attestation_text="Great employee",
            confidence=0.65,
        )
        assert att.employer == "Test Company"
        assert att.confidence == 0.65
        assert isinstance(att.id, UUID)

    def test_confidence_bounds(self) -> None:
        """Test confidence is bounded."""
        att = EmploymentAttestation(
            employer="Test",
            attestation_type=AttestationType.LINKEDIN_RECOMMENDATION,
            attester_name="Test",
            attestation_text="Test",
            confidence=0.75,
        )
        assert 0.0 <= att.confidence <= 1.0

    def test_default_proves_fields(self) -> None:
        """Test default proves fields."""
        att = EmploymentAttestation(
            employer="Test",
            attestation_type=AttestationType.NEWS_QUOTE,
            attester_name="News",
            attestation_text="Test",
            confidence=0.5,
        )
        assert att.proves_employment is True
        assert att.proves_dates is False
        assert att.proves_title is False


class TestEducationAttestation:
    """Tests for EducationAttestation model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        att = EducationAttestation(
            institution="State University",
            attestation_type=AttestationType.ALUMNI_DIRECTORY,
            attester_name="Alumni Office",
            attestation_text="Class of 2020",
            confidence=0.60,
        )
        assert att.institution == "State University"
        assert att.proves_attendance is True


class TestSynthesisProvenance:
    """Tests for SynthesisProvenance model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        prov = SynthesisProvenance(
            public_sources=["https://linkedin.com/in/test"],
            source_types=["linkedin_profile"],
            models_used=["claude-3-opus", "gpt-4"],
            consensus_score=0.85,
        )
        assert prov.consensus_score == 0.85
        assert len(prov.models_used) == 2


class TestSynthesizedEmploymentVerification:
    """Tests for SynthesizedEmploymentVerification model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        verification = SynthesizedEmploymentVerification(
            employer="Test Company",
            claimed_title="Manager",
            employment_confirmed=True,
            confidence=0.75,
        )
        assert verification.employer == "Test Company"
        assert verification.fcra_usable is False

    def test_confidence_capped(self) -> None:
        """Test confidence is capped at 0.85."""
        verification = SynthesizedEmploymentVerification(
            employer="Test",
            confidence=0.85,
        )
        assert verification.confidence <= 0.85

    def test_default_flags(self) -> None:
        """Test default compliance flags."""
        verification = SynthesizedEmploymentVerification(employer="Test")
        assert verification.source_type == SourceType.LLM_SYNTHESIS
        assert verification.fcra_usable is False


class TestSynthesizedEducationVerification:
    """Tests for SynthesizedEducationVerification model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        verification = SynthesizedEducationVerification(
            institution="Test University",
            claimed_degree="BS",
            attendance_confirmed=True,
            confidence=0.70,
        )
        assert verification.institution == "Test University"
        assert verification.confidence <= 0.80

    def test_confidence_capped(self) -> None:
        """Test confidence is capped at 0.80."""
        verification = SynthesizedEducationVerification(
            institution="Test",
            confidence=0.80,
        )
        assert verification.confidence <= 0.80


class TestSynthesizedAdverseMedia:
    """Tests for SynthesizedAdverseMedia model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        media = SynthesizedAdverseMedia(
            subject_name="John Doe",
            total_articles_found=5,
            adverse_articles_count=1,
            confidence=0.65,
        )
        assert media.subject_name == "John Doe"
        assert "SYNTHESIZED_DATA" in media.flags

    def test_confidence_capped(self) -> None:
        """Test confidence is capped at 0.75."""
        media = SynthesizedAdverseMedia(
            subject_name="Test",
            confidence=0.75,
        )
        assert media.confidence <= 0.75


class TestSynthesizedLicenseVerification:
    """Tests for SynthesizedLicenseVerification model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        license_ver = SynthesizedLicenseVerification(
            license_type="CPA",
            claimed_state="CA",
            license_found=True,
            status="active",
            confidence=0.60,
        )
        assert license_ver.license_type == "CPA"
        assert license_ver.confidence <= 0.70


class TestSynthesizedSocialMedia:
    """Tests for SynthesizedSocialMedia model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        social = SynthesizedSocialMedia(
            subject_name="John Doe",
            profiles_found=3,
            confidence=0.70,
        )
        assert social.profiles_found == 3
        assert social.confidence <= 0.80


class TestSynthesizedCorporateAffiliation:
    """Tests for SynthesizedCorporateAffiliation model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        affiliation = SynthesizedCorporateAffiliation(
            company_name="Test Corp",
            role="Director",
            role_type="director",
            is_current=True,
            confidence=0.65,
        )
        assert affiliation.company_name == "Test Corp"
        assert affiliation.confidence <= 0.75


class TestSynthesizedCorporateAffiliations:
    """Tests for SynthesizedCorporateAffiliations model."""

    def test_creation(self) -> None:
        """Test basic creation."""
        affiliations = SynthesizedCorporateAffiliations(
            subject_name="John Doe",
            total_companies=2,
            active_affiliations=1,
            confidence=0.65,
        )
        assert affiliations.subject_name == "John Doe"


class TestLLMSynthesisProviderConfig:
    """Tests for LLMSynthesisProviderConfig model."""

    def test_defaults(self) -> None:
        """Test default configuration."""
        config = LLMSynthesisProviderConfig()
        assert config.primary_model == SynthesisLLMModel.CLAUDE_SONNET
        assert config.secondary_model == SynthesisLLMModel.GPT4
        assert config.require_consensus is True
        assert config.min_consensus_score == 0.7

    def test_max_confidence_defaults(self) -> None:
        """Test default max confidence caps."""
        config = LLMSynthesisProviderConfig()
        assert config.max_confidence["employment_verification"] == 0.85
        assert config.max_confidence["education_verification"] == 0.80
        assert config.max_confidence["adverse_media"] == 0.75

    def test_source_settings(self) -> None:
        """Test source settings defaults."""
        config = LLMSynthesisProviderConfig()
        assert config.linkedin_enabled is True
        assert config.news_search_enabled is True
        assert config.sec_filings_enabled is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = LLMSynthesisProviderConfig(
            primary_model=SynthesisLLMModel.GPT4,
            require_consensus=False,
            max_sources_per_check=5,
        )
        assert config.primary_model == SynthesisLLMModel.GPT4
        assert config.require_consensus is False
        assert config.max_sources_per_check == 5


class TestExceptions:
    """Tests for exception classes."""

    def test_unsupported_check_type_error(self) -> None:
        """Test UnsupportedCheckTypeError."""
        error = UnsupportedCheckTypeError(
            "credit_report",
            ["employment_verification", "education_verification"],
        )
        assert "credit_report" in str(error)
        assert error.check_type == "credit_report"

    def test_source_fetch_error(self) -> None:
        """Test SourceFetchError."""
        error = SourceFetchError("linkedin", "API timeout")
        assert "linkedin" in str(error)
        assert error.source_type == "linkedin"

    def test_llm_extraction_error(self) -> None:
        """Test LLMExtractionError."""
        error = LLMExtractionError("claude-3-opus", "Rate limited")
        assert "claude-3-opus" in str(error)
        assert error.model == "claude-3-opus"

    def test_consensus_failed_error(self) -> None:
        """Test ConsensusFailedError."""
        error = ConsensusFailedError(0.55, 0.70)
        assert "0.55" in str(error)
        assert error.consensus_score == 0.55
        assert error.min_required == 0.70
