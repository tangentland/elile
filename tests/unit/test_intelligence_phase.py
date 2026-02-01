"""Tests for the IntelligencePhaseHandler module.

Tests cover:
- Media mention analysis
- Social profile tracking
- Professional presence detection
- Risk indicator identification
- Intelligence profile aggregation
- Phase execution and results
"""

import pytest
from datetime import date

from elile.agent.state import ServiceTier
from elile.compliance.types import Locale
from elile.investigation.phases.intelligence import (
    IntelligenceConfig,
    IntelligencePhaseHandler,
    IntelligencePhaseResult,
    IntelligenceProfile,
    MediaCategory,
    MediaMention,
    MediaSentiment,
    ProfessionalPresence,
    RiskIndicator,
    SocialPlatform,
    SocialProfile,
    create_intelligence_phase_handler,
)


class TestMediaCategory:
    """Tests for MediaCategory enum."""

    def test_all_categories_exist(self) -> None:
        """Test all expected categories exist."""
        assert MediaCategory.NEWS.value == "news"
        assert MediaCategory.LEGAL.value == "legal"
        assert MediaCategory.REGULATORY.value == "regulatory"
        assert MediaCategory.FINANCIAL.value == "financial"
        assert MediaCategory.POLITICAL.value == "political"
        assert MediaCategory.SOCIAL.value == "social"
        assert MediaCategory.OTHER.value == "other"


class TestMediaSentiment:
    """Tests for MediaSentiment enum."""

    def test_all_sentiments_exist(self) -> None:
        """Test all expected sentiments exist."""
        assert MediaSentiment.POSITIVE.value == "positive"
        assert MediaSentiment.NEUTRAL.value == "neutral"
        assert MediaSentiment.NEGATIVE.value == "negative"
        assert MediaSentiment.MIXED.value == "mixed"


class TestSocialPlatform:
    """Tests for SocialPlatform enum."""

    def test_all_platforms_exist(self) -> None:
        """Test all expected platforms exist."""
        assert SocialPlatform.LINKEDIN.value == "linkedin"
        assert SocialPlatform.TWITTER.value == "twitter"
        assert SocialPlatform.FACEBOOK.value == "facebook"
        assert SocialPlatform.INSTAGRAM.value == "instagram"
        assert SocialPlatform.OTHER.value == "other"


class TestMediaMention:
    """Tests for MediaMention dataclass."""

    def test_media_mention_defaults(self) -> None:
        """Test default media mention values."""
        mention = MediaMention()
        assert mention.source_name == ""
        assert mention.category == MediaCategory.OTHER
        assert mention.sentiment == MediaSentiment.NEUTRAL
        assert mention.is_adverse is False

    def test_media_mention_adverse(self) -> None:
        """Test adverse media mention."""
        mention = MediaMention(
            source_name="News Outlet",
            title="Executive Faces Fraud Charges",
            snippet="The executive was charged with...",
            published_date=date(2023, 5, 10),
            category=MediaCategory.LEGAL,
            sentiment=MediaSentiment.NEGATIVE,
            relevance_score=0.95,
            is_adverse=True,
        )
        assert mention.is_adverse is True
        assert mention.category == MediaCategory.LEGAL

    def test_media_mention_to_dict(self) -> None:
        """Test media mention serialization."""
        mention = MediaMention(
            source_name="Financial Times",
            title="Industry Analysis",
            sentiment=MediaSentiment.POSITIVE,
        )
        d = mention.to_dict()
        assert d["source_name"] == "Financial Times"
        assert d["sentiment"] == "positive"
        assert "mention_id" in d


class TestSocialProfile:
    """Tests for SocialProfile dataclass."""

    def test_social_profile_defaults(self) -> None:
        """Test default social profile values."""
        profile = SocialProfile()
        assert profile.platform == SocialPlatform.OTHER
        assert profile.username == ""
        assert profile.risk_indicators == []

    def test_social_profile_linkedin(self) -> None:
        """Test LinkedIn profile."""
        profile = SocialProfile(
            platform=SocialPlatform.LINKEDIN,
            username="john-smith",
            profile_url="https://linkedin.com/in/john-smith",
            is_verified=True,
            follower_count=500,
            confidence=0.9,
        )
        assert profile.platform == SocialPlatform.LINKEDIN
        assert profile.is_verified is True

    def test_social_profile_with_risks(self) -> None:
        """Test profile with risk indicators."""
        profile = SocialProfile(
            platform=SocialPlatform.TWITTER,
            username="suspicious_user",
            risk_indicators=["extremist_content", "hate_speech"],
        )
        assert len(profile.risk_indicators) == 2

    def test_social_profile_to_dict(self) -> None:
        """Test social profile serialization."""
        profile = SocialProfile(
            platform=SocialPlatform.FACEBOOK,
            follower_count=1000,
        )
        d = profile.to_dict()
        assert d["platform"] == "facebook"
        assert d["follower_count"] == 1000


class TestProfessionalPresence:
    """Tests for ProfessionalPresence dataclass."""

    def test_professional_presence_defaults(self) -> None:
        """Test default professional presence values."""
        presence = ProfessionalPresence()
        assert presence.platform == ""
        assert presence.verified is False

    def test_professional_presence_with_data(self) -> None:
        """Test professional presence with full data."""
        presence = ProfessionalPresence(
            platform="LinkedIn",
            profile_url="https://linkedin.com/in/jane-doe",
            headline="Senior Software Engineer",
            current_position="Software Engineer",
            company="Tech Corp",
            connections=500,
            endorsements=50,
            verified=True,
        )
        assert presence.platform == "LinkedIn"
        assert presence.endorsements == 50

    def test_professional_presence_to_dict(self) -> None:
        """Test professional presence serialization."""
        presence = ProfessionalPresence(
            platform="AngelList",
            headline="Startup Founder",
        )
        d = presence.to_dict()
        assert d["platform"] == "AngelList"
        assert d["headline"] == "Startup Founder"


class TestRiskIndicator:
    """Tests for RiskIndicator dataclass."""

    def test_risk_indicator_defaults(self) -> None:
        """Test default risk indicator values."""
        indicator = RiskIndicator()
        assert indicator.indicator_type == ""
        assert indicator.severity == "medium"

    def test_risk_indicator_with_data(self) -> None:
        """Test risk indicator with full data."""
        indicator = RiskIndicator(
            indicator_type="adverse_media",
            description="Subject mentioned in fraud investigation",
            source="news_outlet",
            severity="high",
            confidence=0.85,
        )
        assert indicator.severity == "high"
        assert indicator.confidence == 0.85

    def test_risk_indicator_to_dict(self) -> None:
        """Test risk indicator serialization."""
        indicator = RiskIndicator(
            indicator_type="pep_connection",
            severity="critical",
        )
        d = indicator.to_dict()
        assert d["indicator_type"] == "pep_connection"
        assert d["severity"] == "critical"


class TestIntelligenceProfile:
    """Tests for IntelligenceProfile dataclass."""

    def test_intelligence_profile_defaults(self) -> None:
        """Test default profile values."""
        profile = IntelligenceProfile()
        assert profile.adverse_media_count == 0
        assert profile.media_sentiment_summary == MediaSentiment.NEUTRAL
        assert profile.overall_risk_score == 0.0

    def test_calculate_risk_score_no_risks(self) -> None:
        """Test risk calculation with no adverse indicators."""
        profile = IntelligenceProfile()
        score = profile.calculate_risk_score()
        assert score == 0.0

    def test_calculate_risk_score_adverse_media(self) -> None:
        """Test risk calculation with adverse media."""
        profile = IntelligenceProfile(adverse_media_count=3)
        score = profile.calculate_risk_score()
        assert score == pytest.approx(0.3)

    def test_calculate_risk_score_capped(self) -> None:
        """Test risk score is capped at 1.0."""
        profile = IntelligenceProfile(
            adverse_media_count=10,
            risk_indicators=[
                RiskIndicator(severity="high"),
                RiskIndicator(severity="high"),
                RiskIndicator(severity="high"),
            ],
        )
        score = profile.calculate_risk_score()
        assert score == 1.0

    def test_calculate_risk_score_high_indicators(self) -> None:
        """Test risk calculation with high severity indicators."""
        profile = IntelligenceProfile(
            risk_indicators=[RiskIndicator(severity="high")]
        )
        score = profile.calculate_risk_score()
        assert score == pytest.approx(0.2)

    def test_calculate_risk_score_medium_indicators(self) -> None:
        """Test risk calculation with medium severity indicators."""
        profile = IntelligenceProfile(
            risk_indicators=[RiskIndicator(severity="medium")]
        )
        score = profile.calculate_risk_score()
        assert score == pytest.approx(0.1)

    def test_intelligence_profile_to_dict(self) -> None:
        """Test profile serialization."""
        profile = IntelligenceProfile(
            media_mentions=[MediaMention(source_name="Test")],
            adverse_media_count=1,
        )
        d = profile.to_dict()
        assert d["adverse_media_count"] == 1
        assert len(d["media_mentions"]) == 1


class TestIntelligenceConfig:
    """Tests for IntelligenceConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = IntelligenceConfig()
        assert config.enable_media_search is True
        assert config.enable_social_search is True
        assert config.max_media_results == 50
        assert config.media_lookback_years == 5

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = IntelligenceConfig(
            enable_social_search=False,
            max_media_results=100,
            adverse_only=True,
        )
        assert config.enable_social_search is False
        assert config.max_media_results == 100
        assert config.adverse_only is True


class TestIntelligencePhaseResult:
    """Tests for IntelligencePhaseResult."""

    def test_result_defaults(self) -> None:
        """Test default result values."""
        result = IntelligencePhaseResult()
        assert result.success is True
        assert result.sources_searched == []

    def test_result_to_dict(self) -> None:
        """Test result serialization."""
        result = IntelligencePhaseResult(
            success=True,
            sources_searched=["media", "social"],
        )
        d = result.to_dict()
        assert d["success"] is True
        assert "media" in d["sources_searched"]


class TestIntelligencePhaseHandler:
    """Tests for IntelligencePhaseHandler."""

    @pytest.fixture
    def handler(self) -> IntelligencePhaseHandler:
        """Create a handler with default config."""
        return IntelligencePhaseHandler()

    @pytest.mark.asyncio
    async def test_execute_with_full_data(self, handler: IntelligencePhaseHandler) -> None:
        """Test execution with full subject data."""
        result = await handler.execute(
            subject_name="John Smith",
            aliases=["Johnny S", "J. Smith"],
            tier=ServiceTier.ENHANCED,
            locale=Locale.US,
        )

        assert result.success is True
        assert "media" in result.sources_searched
        assert "social" in result.sources_searched
        assert "professional" in result.sources_searched

    @pytest.mark.asyncio
    async def test_execute_with_minimal_data(self, handler: IntelligencePhaseHandler) -> None:
        """Test execution with minimal subject data."""
        result = await handler.execute(
            subject_name="Jane Doe",
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_respects_config(self) -> None:
        """Test that execution respects config settings."""
        config = IntelligenceConfig(
            enable_media_search=True,
            enable_social_search=False,
            enable_professional_search=False,
        )
        handler = IntelligencePhaseHandler(config=config)
        result = await handler.execute(subject_name="Test Subject")

        assert "media" in result.sources_searched
        assert "social" not in result.sources_searched
        assert "professional" not in result.sources_searched

    @pytest.mark.asyncio
    async def test_execute_calculates_risk(self, handler: IntelligencePhaseHandler) -> None:
        """Test that execution calculates risk score."""
        result = await handler.execute(subject_name="John Smith")

        # Stub returns empty profile, so risk should be 0
        assert result.profile.overall_risk_score == 0.0

    @pytest.mark.asyncio
    async def test_execute_records_timing(self, handler: IntelligencePhaseHandler) -> None:
        """Test that execution records timing."""
        result = await handler.execute(subject_name="John Smith")

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration_ms >= 0

    def test_custom_config(self) -> None:
        """Test handler with custom configuration."""
        config = IntelligenceConfig(
            max_media_results=100,
            media_lookback_years=10,
        )
        handler = IntelligencePhaseHandler(config=config)

        assert handler.config.max_media_results == 100
        assert handler.config.media_lookback_years == 10


class TestCreateIntelligencePhaseHandler:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating handler with defaults."""
        handler = create_intelligence_phase_handler()
        assert isinstance(handler, IntelligencePhaseHandler)

    def test_create_with_config(self) -> None:
        """Test creating handler with custom config."""
        config = IntelligenceConfig(adverse_only=True)
        handler = create_intelligence_phase_handler(config=config)
        assert handler.config.adverse_only is True
