"""Tests for OSINT provider type definitions."""

from datetime import datetime
from uuid import uuid7

from elile.providers.osint.types import (
    DuplicateGroup,
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    NewsMention,
    OSINTProviderConfig,
    OSINTProviderError,
    OSINTRateLimitError,
    OSINTSearchError,
    OSINTSearchResult,
    OSINTSource,
    OSINTSourceUnavailableError,
    ProfessionalInfo,
    PublicRecord,
    RelationshipType,
    RelevanceScore,
    SentimentType,
    SocialMediaProfile,
    SourceReliability,
)


class TestOSINTSource:
    """Tests for OSINTSource enum."""

    def test_social_media_sources(self) -> None:
        """Test social media source types."""
        assert OSINTSource.LINKEDIN == "linkedin"
        assert OSINTSource.TWITTER == "twitter"
        assert OSINTSource.FACEBOOK == "facebook"
        assert OSINTSource.GITHUB == "github"

    def test_news_sources(self) -> None:
        """Test news source types."""
        assert OSINTSource.NEWS_WIRE == "news_wire"
        assert OSINTSource.LOCAL_NEWS == "local_news"
        assert OSINTSource.BUSINESS_NEWS == "business_news"
        assert OSINTSource.TECH_NEWS == "tech_news"

    def test_public_record_sources(self) -> None:
        """Test public record source types."""
        assert OSINTSource.COURT_RECORDS == "court_records"
        assert OSINTSource.PROPERTY_RECORDS == "property_records"
        assert OSINTSource.BUSINESS_FILINGS == "business_filings"

    def test_government_sources(self) -> None:
        """Test government source types."""
        assert OSINTSource.SEC_FILINGS == "sec_filings"
        assert OSINTSource.POLITICAL_CONTRIBUTIONS == "political_contributions"


class TestSourceReliability:
    """Tests for SourceReliability enum."""

    def test_reliability_levels(self) -> None:
        """Test all reliability levels exist."""
        assert SourceReliability.AUTHORITATIVE == "authoritative"
        assert SourceReliability.HIGHLY_RELIABLE == "highly_reliable"
        assert SourceReliability.GENERALLY_RELIABLE == "generally_reliable"
        assert SourceReliability.SOMEWHAT_RELIABLE == "somewhat_reliable"
        assert SourceReliability.LOW_RELIABILITY == "low_reliability"


class TestSentimentType:
    """Tests for SentimentType enum."""

    def test_sentiment_types(self) -> None:
        """Test all sentiment types exist."""
        assert SentimentType.POSITIVE == "positive"
        assert SentimentType.NEUTRAL == "neutral"
        assert SentimentType.NEGATIVE == "negative"
        assert SentimentType.MIXED == "mixed"


class TestEntityType:
    """Tests for EntityType enum."""

    def test_entity_types(self) -> None:
        """Test all entity types exist."""
        assert EntityType.PERSON == "person"
        assert EntityType.ORGANIZATION == "organization"
        assert EntityType.LOCATION == "location"
        assert EntityType.EMAIL == "email"
        assert EntityType.PHONE == "phone"
        assert EntityType.URL == "url"


class TestRelationshipType:
    """Tests for RelationshipType enum."""

    def test_relationship_types(self) -> None:
        """Test all relationship types exist."""
        assert RelationshipType.WORKS_FOR == "works_for"
        assert RelationshipType.WORKED_FOR == "worked_for"
        assert RelationshipType.FOUNDED == "founded"
        assert RelationshipType.BOARD_MEMBER == "board_member"
        assert RelationshipType.EDUCATED_AT == "educated_at"


class TestSocialMediaProfile:
    """Tests for SocialMediaProfile model."""

    def test_profile_creation(self) -> None:
        """Test basic profile creation."""
        profile = SocialMediaProfile(
            profile_id=uuid7(),
            source=OSINTSource.LINKEDIN,
            username="jsmith",
            display_name="John Smith",
        )
        assert profile.username == "jsmith"
        assert profile.source == OSINTSource.LINKEDIN
        assert profile.verified is False
        assert profile.match_confidence == 0.0

    def test_profile_full(self) -> None:
        """Test profile with all fields."""
        profile = SocialMediaProfile(
            profile_id=uuid7(),
            source=OSINTSource.TWITTER,
            username="johnsmith",
            display_name="John Smith",
            profile_url="https://twitter.com/johnsmith",
            bio="Tech enthusiast",
            follower_count=5000,
            following_count=500,
            post_count=1000,
            verified=True,
            location="San Francisco, CA",
            is_likely_match=True,
            match_confidence=0.85,
        )
        assert profile.follower_count == 5000
        assert profile.verified is True
        assert profile.is_likely_match is True
        assert profile.match_confidence == 0.85


class TestNewsMention:
    """Tests for NewsMention model."""

    def test_mention_creation(self) -> None:
        """Test basic mention creation."""
        mention = NewsMention(
            mention_id=uuid7(),
            headline="Test Article",
        )
        assert mention.headline == "Test Article"
        assert mention.sentiment == SentimentType.NEUTRAL
        assert mention.relevance == RelevanceScore.MEDIUM

    def test_mention_full(self) -> None:
        """Test mention with all fields."""
        mention = NewsMention(
            mention_id=uuid7(),
            source=OSINTSource.BUSINESS_NEWS,
            headline="CEO announces expansion",
            snippet="John Smith announced...",
            url="https://example.com/news",
            published_at=datetime(2024, 1, 15),
            author="Jane Doe",
            publication="Business Daily",
            sentiment=SentimentType.POSITIVE,
            relevance=RelevanceScore.HIGH,
            entities_mentioned=["John Smith", "TechCorp"],
            is_subject_primary=True,
            source_reliability=SourceReliability.HIGHLY_RELIABLE,
        )
        assert mention.publication == "Business Daily"
        assert mention.sentiment == SentimentType.POSITIVE
        assert mention.is_subject_primary is True
        assert len(mention.entities_mentioned) == 2


class TestPublicRecord:
    """Tests for PublicRecord model."""

    def test_record_creation(self) -> None:
        """Test basic record creation."""
        record = PublicRecord(
            record_id=uuid7(),
            record_type="Property Record",
        )
        assert record.record_type == "Property Record"
        assert record.source == OSINTSource.COURT_RECORDS

    def test_record_full(self) -> None:
        """Test record with all fields."""
        record = PublicRecord(
            record_id=uuid7(),
            source=OSINTSource.BUSINESS_FILINGS,
            record_type="Business Filing",
            title="Company Incorporation",
            filing_date=datetime(2023, 6, 1),
            jurisdiction="Delaware",
            case_number="DE-2023-12345",
            parties=["John Smith", "TechCorp LLC"],
            status="Filed",
            amount=100000.00,
            source_reliability=SourceReliability.AUTHORITATIVE,
        )
        assert record.jurisdiction == "Delaware"
        assert record.amount == 100000.00
        assert len(record.parties) == 2


class TestProfessionalInfo:
    """Tests for ProfessionalInfo model."""

    def test_info_creation(self) -> None:
        """Test basic professional info creation."""
        info = ProfessionalInfo(
            info_id=uuid7(),
            current_title="Software Engineer",
            current_company="TechCorp",
        )
        assert info.current_title == "Software Engineer"
        assert info.source == OSINTSource.LINKEDIN

    def test_info_full(self) -> None:
        """Test professional info with all fields."""
        info = ProfessionalInfo(
            info_id=uuid7(),
            source=OSINTSource.LINKEDIN,
            current_title="CEO",
            current_company="StartupCo",
            company_industry="Technology",
            company_size="50-200",
            employment_history=[
                {"company": "PreviousCorp", "title": "VP", "start_date": "2020"},
            ],
            education=[
                {"school": "MIT", "degree": "BS Computer Science"},
            ],
            skills=["Leadership", "Strategy", "Python"],
            certifications=["PMP", "AWS Certified"],
            board_positions=["TechNonProfit"],
        )
        assert info.current_title == "CEO"
        assert len(info.skills) == 3
        assert len(info.employment_history) == 1


class TestExtractedEntity:
    """Tests for ExtractedEntity model."""

    def test_entity_creation(self) -> None:
        """Test basic entity creation."""
        entity = ExtractedEntity(
            entity_id=uuid7(),
            entity_type=EntityType.PERSON,
            name="John Smith",
        )
        assert entity.name == "John Smith"
        assert entity.entity_type == EntityType.PERSON
        assert entity.confidence == 0.8

    def test_entity_with_sources(self) -> None:
        """Test entity with multiple sources."""
        entity = ExtractedEntity(
            entity_id=uuid7(),
            entity_type=EntityType.ORGANIZATION,
            name="TechCorp",
            normalized_name="techcorp",
            source_count=3,
            sources=[OSINTSource.LINKEDIN, OSINTSource.NEWS_WIRE, OSINTSource.SEC_FILINGS],
            confidence=0.95,
            context_snippets=["CEO of TechCorp", "TechCorp announced"],
        )
        assert entity.source_count == 3
        assert len(entity.sources) == 3
        assert entity.confidence == 0.95


class TestExtractedRelationship:
    """Tests for ExtractedRelationship model."""

    def test_relationship_creation(self) -> None:
        """Test basic relationship creation."""
        rel = ExtractedRelationship(
            relationship_id=uuid7(),
            relationship_type=RelationshipType.WORKS_FOR,
            source_entity="John Smith",
            source_entity_type=EntityType.PERSON,
            target_entity="TechCorp",
            target_entity_type=EntityType.ORGANIZATION,
        )
        assert rel.relationship_type == RelationshipType.WORKS_FOR
        assert rel.is_current is True
        assert rel.confidence == 0.7

    def test_relationship_full(self) -> None:
        """Test relationship with all fields."""
        rel = ExtractedRelationship(
            relationship_id=uuid7(),
            relationship_type=RelationshipType.WORKED_FOR,
            source_entity="John Smith",
            source_entity_type=EntityType.PERSON,
            target_entity="OldCorp",
            target_entity_type=EntityType.ORGANIZATION,
            start_date=datetime(2018, 1, 1),
            end_date=datetime(2022, 6, 30),
            is_current=False,
            source_count=2,
            sources=[OSINTSource.LINKEDIN, OSINTSource.NEWS_WIRE],
            confidence=0.9,
        )
        assert rel.is_current is False
        assert rel.end_date is not None


class TestOSINTSearchResult:
    """Tests for OSINTSearchResult model."""

    def test_result_creation(self) -> None:
        """Test basic result creation."""
        result = OSINTSearchResult(
            search_id=uuid7(),
            subject_name="John Smith",
        )
        assert result.subject_name == "John Smith"
        assert result.has_results() is False

    def test_result_with_findings(self) -> None:
        """Test result with findings."""
        result = OSINTSearchResult(
            search_id=uuid7(),
            subject_name="John Smith",
            social_profiles=[
                SocialMediaProfile(
                    profile_id=uuid7(),
                    source=OSINTSource.LINKEDIN,
                    display_name="John Smith",
                    match_confidence=0.9,
                ),
            ],
            news_mentions=[
                NewsMention(
                    mention_id=uuid7(),
                    headline="Test",
                    relevance=RelevanceScore.HIGH,
                ),
            ],
            total_items_found=2,
            unique_items_after_dedup=2,
        )
        assert result.has_results() is True
        assert result.get_high_relevance_count() == 2

    def test_get_source_breakdown(self) -> None:
        """Test source breakdown calculation."""
        result = OSINTSearchResult(
            search_id=uuid7(),
            subject_name="John Smith",
            social_profiles=[
                SocialMediaProfile(
                    profile_id=uuid7(),
                    source=OSINTSource.LINKEDIN,
                    display_name="John Smith",
                ),
                SocialMediaProfile(
                    profile_id=uuid7(),
                    source=OSINTSource.TWITTER,
                    display_name="John Smith",
                ),
            ],
            news_mentions=[
                NewsMention(mention_id=uuid7(), source=OSINTSource.NEWS_WIRE),
                NewsMention(mention_id=uuid7(), source=OSINTSource.NEWS_WIRE),
            ],
        )
        breakdown = result.get_source_breakdown()
        assert breakdown["linkedin"] == 1
        assert breakdown["twitter"] == 1
        assert breakdown["news_wire"] == 2


class TestDuplicateGroup:
    """Tests for DuplicateGroup model."""

    def test_group_creation(self) -> None:
        """Test duplicate group creation."""
        canonical_id = uuid7()
        dup_id = uuid7()
        group = DuplicateGroup(
            group_id=uuid7(),
            item_type="social_profile",
            canonical_item_id=canonical_id,
            duplicate_item_ids=[dup_id],
            similarity_scores={str(dup_id): 0.92},
        )
        assert group.item_type == "social_profile"
        assert len(group.duplicate_item_ids) == 1


class TestOSINTProviderConfig:
    """Tests for OSINTProviderConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = OSINTProviderConfig()
        assert config.api_key is None
        assert config.enable_social_media is True
        assert config.enable_news_search is True
        assert config.enable_public_records is True
        assert config.enable_professional is True
        assert config.enable_entity_extraction is True
        assert config.enable_relationship_extraction is True
        assert config.enable_deduplication is True
        assert config.dedup_similarity_threshold == 0.85
        assert config.news_lookback_days == 365

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = OSINTProviderConfig(
            api_key="test-key",
            enable_public_records=False,
            news_lookback_days=180,
            dedup_similarity_threshold=0.90,
            sources_to_exclude=[OSINTSource.TIKTOK],
        )
        assert config.api_key == "test-key"
        assert config.enable_public_records is False
        assert config.news_lookback_days == 180
        assert config.dedup_similarity_threshold == 0.90


class TestExceptions:
    """Tests for OSINT provider exceptions."""

    def test_osint_provider_error(self) -> None:
        """Test base exception."""
        error = OSINTProviderError("Test error", {"key": "value"})
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {"key": "value"}

    def test_osint_search_error(self) -> None:
        """Test search error exception."""
        search_id = uuid7()
        error = OSINTSearchError(
            search_id,
            "Timeout",
            failed_sources=["linkedin", "twitter"],
        )
        assert str(search_id) in str(error)
        assert error.search_id == search_id
        assert error.reason == "Timeout"
        assert "linkedin" in error.failed_sources

    def test_osint_rate_limit_error(self) -> None:
        """Test rate limit exception."""
        error = OSINTRateLimitError(OSINTSource.LINKEDIN, retry_after_seconds=60)
        assert "linkedin" in str(error).lower()
        assert error.source == OSINTSource.LINKEDIN
        assert error.retry_after_seconds == 60

    def test_osint_source_unavailable_error(self) -> None:
        """Test source unavailable exception."""
        error = OSINTSourceUnavailableError(OSINTSource.TWITTER, "API down")
        assert "twitter" in str(error).lower()
        assert error.source == OSINTSource.TWITTER
        assert error.reason == "API down"
