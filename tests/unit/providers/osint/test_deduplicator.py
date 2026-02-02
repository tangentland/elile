"""Tests for OSINT deduplicator."""

from uuid import uuid7

import pytest

from elile.providers.osint.deduplicator import (
    DeduplicationResult,
    OSINTDeduplicator,
    create_deduplicator,
)
from elile.providers.osint.types import (
    NewsMention,
    OSINTSource,
    ProfessionalInfo,
    PublicRecord,
    SocialMediaProfile,
)


class TestOSINTDeduplicator:
    """Tests for OSINTDeduplicator class."""

    @pytest.fixture
    def deduplicator(self) -> OSINTDeduplicator:
        """Create a deduplicator instance."""
        return OSINTDeduplicator(similarity_threshold=0.85)

    def test_deduplicate_profiles_empty(self, deduplicator: OSINTDeduplicator) -> None:
        """Test deduplicating empty list."""
        result = deduplicator.deduplicate_profiles([])
        assert result.total_input == 0
        assert result.total_output == 0
        assert result.duplicates_removed == 0

    def test_deduplicate_profiles_no_duplicates(self, deduplicator: OSINTDeduplicator) -> None:
        """Test deduplicating profiles with no duplicates."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                username="john_smith",
                display_name="John Smith",
            ),
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.TWITTER,
                username="jane_doe",
                display_name="Jane Doe",
            ),
        ]
        result = deduplicator.deduplicate_profiles(profiles)
        assert result.total_input == 2
        assert result.total_output == 2
        assert result.duplicates_removed == 0

    def test_deduplicate_profiles_same_source_username(
        self, deduplicator: OSINTDeduplicator
    ) -> None:
        """Test deduplicating profiles with same source and username."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                username="john_smith",
                display_name="John Smith",
                match_confidence=0.9,
            ),
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                username="john_smith",
                display_name="John Smith",
                match_confidence=0.8,
            ),
        ]
        result = deduplicator.deduplicate_profiles(profiles)
        assert result.total_input == 2
        assert result.total_output == 1
        assert result.duplicates_removed == 1
        assert len(result.duplicate_groups) == 1

    def test_deduplicate_profiles_similar_names(self, deduplicator: OSINTDeduplicator) -> None:
        """Test deduplicating profiles with similar names."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                username="jsmith",
                display_name="John Smith",
                location="New York, NY",
            ),
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.TWITTER,
                username="john_smith",
                display_name="John Smith",
                location="New York, NY",
            ),
        ]
        result = deduplicator.deduplicate_profiles(profiles)
        # Same name + same location should merge
        assert result.total_output == 1

    def test_deduplicate_news_empty(self, deduplicator: OSINTDeduplicator) -> None:
        """Test deduplicating empty news list."""
        result = deduplicator.deduplicate_news([])
        assert result.total_input == 0
        assert result.total_output == 0

    def test_deduplicate_news_same_url(self, deduplicator: OSINTDeduplicator) -> None:
        """Test deduplicating news with same URL."""
        mentions = [
            NewsMention(
                mention_id=uuid7(),
                source=OSINTSource.NEWS_WIRE,
                headline="Breaking News",
                url="https://example.com/article/123",
            ),
            NewsMention(
                mention_id=uuid7(),
                source=OSINTSource.BUSINESS_NEWS,
                headline="Breaking News Story",
                url="https://example.com/article/123",
            ),
        ]
        result = deduplicator.deduplicate_news(mentions)
        assert result.total_input == 2
        assert result.total_output == 1

    def test_deduplicate_news_similar_headlines(self, deduplicator: OSINTDeduplicator) -> None:
        """Test deduplicating news with similar headlines."""
        from datetime import datetime

        mentions = [
            NewsMention(
                mention_id=uuid7(),
                headline="TechCorp announces new product launch",
                published_at=datetime(2024, 1, 15),
            ),
            NewsMention(
                mention_id=uuid7(),
                headline="TechCorp announces new product launch today",
                published_at=datetime(2024, 1, 15),
            ),
        ]
        result = deduplicator.deduplicate_news(mentions)
        assert result.total_output == 1

    def test_deduplicate_news_different_headlines(self, deduplicator: OSINTDeduplicator) -> None:
        """Test news with different headlines are kept separate."""
        mentions = [
            NewsMention(
                mention_id=uuid7(),
                headline="TechCorp announces product launch",
            ),
            NewsMention(
                mention_id=uuid7(),
                headline="Completely different news story",
            ),
        ]
        result = deduplicator.deduplicate_news(mentions)
        assert result.total_output == 2

    def test_deduplicate_records_empty(self, deduplicator: OSINTDeduplicator) -> None:
        """Test deduplicating empty records list."""
        result = deduplicator.deduplicate_records([])
        assert result.total_input == 0

    def test_deduplicate_records_same_case_number(self, deduplicator: OSINTDeduplicator) -> None:
        """Test deduplicating records with same case number."""
        records = [
            PublicRecord(
                record_id=uuid7(),
                case_number="CA-2023-12345",
                jurisdiction="California",
                title="Case Title",
            ),
            PublicRecord(
                record_id=uuid7(),
                case_number="CA-2023-12345",
                jurisdiction="California",
                title="Case Title - Updated",
            ),
        ]
        result = deduplicator.deduplicate_records(records)
        assert result.total_input == 2
        assert result.total_output == 1

    def test_deduplicate_records_same_url(self, deduplicator: OSINTDeduplicator) -> None:
        """Test deduplicating records with same URL."""
        records = [
            PublicRecord(
                record_id=uuid7(),
                url="https://court.gov/case/12345",
                title="Case One",
            ),
            PublicRecord(
                record_id=uuid7(),
                url="https://court.gov/case/12345",
                title="Case One Updated",
            ),
        ]
        result = deduplicator.deduplicate_records(records)
        assert result.total_output == 1

    def test_deduplicate_professional_empty(self, deduplicator: OSINTDeduplicator) -> None:
        """Test deduplicating empty professional list."""
        result = deduplicator.deduplicate_professional([])
        assert result.total_input == 0

    def test_deduplicate_professional_same_company_title(
        self, deduplicator: OSINTDeduplicator
    ) -> None:
        """Test deduplicating professional info with same company and title."""
        infos = [
            ProfessionalInfo(
                info_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                current_company="TechCorp",
                current_title="Software Engineer",
                skills=["Python"],
            ),
            ProfessionalInfo(
                info_id=uuid7(),
                source=OSINTSource.CRUNCHBASE,
                current_company="TechCorp",
                current_title="Software Engineer",
                skills=["Java"],
            ),
        ]
        result = deduplicator.deduplicate_professional(infos)
        assert result.total_input == 2
        assert result.total_output == 1
        # Skills should be merged
        merged = result.items[0]
        assert "Python" in merged.skills
        assert "Java" in merged.skills

    def test_merge_profiles_keeps_best_data(self, deduplicator: OSINTDeduplicator) -> None:
        """Test merging profiles keeps best data."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                username="jsmith",
                display_name="John Smith",
                match_confidence=0.9,
                follower_count=1000,
            ),
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                username="jsmith",
                display_name="John Smith",
                match_confidence=0.7,
                bio="Professional bio here",
                location="New York",
            ),
        ]
        result = deduplicator.deduplicate_profiles(profiles)
        merged = result.items[0]
        # Should keep higher confidence profile but merge in missing data
        assert merged.match_confidence == 0.9
        assert merged.bio == "Professional bio here"
        assert merged.location == "New York"


class TestCreateDeduplicator:
    """Tests for create_deduplicator factory function."""

    def test_create_default(self) -> None:
        """Test creating deduplicator with defaults."""
        dedup = create_deduplicator()
        assert isinstance(dedup, OSINTDeduplicator)
        assert dedup.similarity_threshold == 0.85

    def test_create_custom_threshold(self) -> None:
        """Test creating deduplicator with custom threshold."""
        dedup = create_deduplicator(similarity_threshold=0.95)
        assert dedup.similarity_threshold == 0.95


class TestDeduplicationResult:
    """Tests for DeduplicationResult model."""

    def test_result_defaults(self) -> None:
        """Test result defaults."""
        result = DeduplicationResult()
        assert result.total_input == 0
        assert result.total_output == 0
        assert result.duplicates_removed == 0
        assert result.duplicate_groups == []
        assert result.items == []


class TestStringSimilarity:
    """Tests for string similarity calculation."""

    @pytest.fixture
    def deduplicator(self) -> OSINTDeduplicator:
        """Create a deduplicator instance."""
        return OSINTDeduplicator()

    def test_identical_strings(self, deduplicator: OSINTDeduplicator) -> None:
        """Test identical strings have similarity of 1.0."""
        sim = deduplicator._string_similarity("hello", "hello")
        assert sim == 1.0

    def test_similar_strings(self, deduplicator: OSINTDeduplicator) -> None:
        """Test similar strings have high similarity."""
        sim = deduplicator._string_similarity("John Smith", "John Smyth")
        assert sim >= 0.8

    def test_different_strings(self, deduplicator: OSINTDeduplicator) -> None:
        """Test different strings have low similarity."""
        sim = deduplicator._string_similarity("Apple", "Orange")
        assert sim < 0.5

    def test_empty_string(self, deduplicator: OSINTDeduplicator) -> None:
        """Test empty string returns 0."""
        sim = deduplicator._string_similarity("hello", "")
        assert sim == 0.0

    def test_none_string(self, deduplicator: OSINTDeduplicator) -> None:
        """Test None string returns 0."""
        sim = deduplicator._string_similarity("hello", None)
        assert sim == 0.0

    def test_case_insensitive(self, deduplicator: OSINTDeduplicator) -> None:
        """Test similarity is case insensitive."""
        sim = deduplicator._string_similarity("HELLO", "hello")
        assert sim == 1.0
