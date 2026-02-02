"""Tests for OSINT entity and relationship extraction."""

from uuid import uuid7

import pytest

from elile.providers.osint.entity_extractor import (
    EntityExtractor,
    RelationshipExtractor,
    create_entity_extractor,
    create_relationship_extractor,
)
from elile.providers.osint.types import (
    EntityType,
    NewsMention,
    OSINTSource,
    ProfessionalInfo,
    PublicRecord,
    RelationshipType,
    SocialMediaProfile,
)


class TestEntityExtractor:
    """Tests for EntityExtractor class."""

    @pytest.fixture
    def extractor(self) -> EntityExtractor:
        """Create an entity extractor instance."""
        return EntityExtractor()

    def test_extract_from_profiles_person(self, extractor: EntityExtractor) -> None:
        """Test extracting person entity from profile."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                display_name="John Smith",
                username="jsmith",
            )
        ]
        entities = extractor.extract_from_profiles(profiles)
        person_entities = [e for e in entities if e.entity_type == EntityType.PERSON]
        assert len(person_entities) >= 1
        assert any(e.name == "John Smith" for e in person_entities)

    def test_extract_from_profiles_location(self, extractor: EntityExtractor) -> None:
        """Test extracting location entity from profile."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                display_name="John Smith",
                location="San Francisco, CA",
            )
        ]
        entities = extractor.extract_from_profiles(profiles)
        location_entities = [e for e in entities if e.entity_type == EntityType.LOCATION]
        assert len(location_entities) >= 1
        assert any("San Francisco" in e.name for e in location_entities)

    def test_extract_from_profiles_bio_entities(self, extractor: EntityExtractor) -> None:
        """Test extracting entities from bio."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.TWITTER,
                display_name="Jane Doe",
                bio="Contact me at jane@example.com or follow @janedoe",
            )
        ]
        entities = extractor.extract_from_profiles(profiles)
        email_entities = [e for e in entities if e.entity_type == EntityType.EMAIL]
        handle_entities = [e for e in entities if e.entity_type == EntityType.SOCIAL_HANDLE]
        assert len(email_entities) >= 1
        assert len(handle_entities) >= 1

    def test_extract_from_news_entities(self, extractor: EntityExtractor) -> None:
        """Test extracting entities from news mentions."""
        mentions = [
            NewsMention(
                mention_id=uuid7(),
                source=OSINTSource.NEWS_WIRE,
                headline="TechCorp CEO announces $5M funding",
                snippet="John Smith, CEO of TechCorp, announced...",
                entities_mentioned=["John Smith", "TechCorp"],
                author="Jane Reporter",
                publication="Tech News",
            )
        ]
        entities = extractor.extract_from_news(mentions)

        # Should find mentioned entities
        names = [e.name for e in entities]
        assert "John Smith" in names
        assert "TechCorp" in names

        # Should find money
        money_entities = [e for e in entities if e.entity_type == EntityType.MONEY]
        assert len(money_entities) >= 1

    def test_extract_from_records_parties(self, extractor: EntityExtractor) -> None:
        """Test extracting parties from public records."""
        records = [
            PublicRecord(
                record_id=uuid7(),
                source=OSINTSource.COURT_RECORDS,
                title="Smith vs TechCorp Inc.",
                parties=["John Smith", "TechCorp Inc."],
                jurisdiction="California",
                amount=50000.00,
            )
        ]
        entities = extractor.extract_from_records(records)

        # Should find parties
        party_names = [
            e.name
            for e in entities
            if e.entity_type in (EntityType.PERSON, EntityType.ORGANIZATION)
        ]
        assert "John Smith" in party_names
        assert "TechCorp Inc." in party_names

        # Should find jurisdiction as location
        locations = [e for e in entities if e.entity_type == EntityType.LOCATION]
        assert any("California" in e.name for e in locations)

        # Should find amount as money
        money = [e for e in entities if e.entity_type == EntityType.MONEY]
        assert len(money) >= 1

    def test_extract_from_professional_companies(self, extractor: EntityExtractor) -> None:
        """Test extracting companies from professional info."""
        infos = [
            ProfessionalInfo(
                info_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                current_title="Software Engineer",
                current_company="TechCorp",
                employment_history=[
                    {"company": "PreviousCorp", "title": "Junior Engineer"},
                ],
                education=[
                    {"school": "MIT", "degree": "BS Computer Science"},
                ],
                board_positions=["NonProfit Foundation"],
            )
        ]
        entities = extractor.extract_from_professional(infos)

        org_names = [e.name for e in entities if e.entity_type == EntityType.ORGANIZATION]
        assert "TechCorp" in org_names
        assert "PreviousCorp" in org_names
        assert "MIT" in org_names
        assert "NonProfit Foundation" in org_names

    def test_extract_emails(self, extractor: EntityExtractor) -> None:
        """Test email extraction pattern."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                display_name="Test",
                bio="Email: test@example.com, support@company.org",
            )
        ]
        entities = extractor.extract_from_profiles(profiles)
        emails = [e for e in entities if e.entity_type == EntityType.EMAIL]
        assert len(emails) == 2

    def test_extract_phones(self, extractor: EntityExtractor) -> None:
        """Test phone extraction pattern."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                display_name="Test",
                bio="Call me at 415-555-1234 or (650) 555-9876",
            )
        ]
        entities = extractor.extract_from_profiles(profiles)
        phones = [e for e in entities if e.entity_type == EntityType.PHONE]
        assert len(phones) == 2

    def test_extract_urls(self, extractor: EntityExtractor) -> None:
        """Test URL extraction pattern."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                display_name="Test",
                bio="Visit https://mysite.com or http://blog.example.org",
            )
        ]
        entities = extractor.extract_from_profiles(profiles)
        urls = [e for e in entities if e.entity_type == EntityType.URL]
        assert len(urls) == 2

    def test_extract_social_handles(self, extractor: EntityExtractor) -> None:
        """Test social handle extraction."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.TWITTER,
                display_name="Test",
                bio="Follow me @testuser and @otheruser",
            )
        ]
        entities = extractor.extract_from_profiles(profiles)
        handles = [e for e in entities if e.entity_type == EntityType.SOCIAL_HANDLE]
        assert len(handles) == 2

    def test_entity_deduplication(self, extractor: EntityExtractor) -> None:
        """Test that duplicate entities are deduplicated."""
        profiles = [
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
        ]
        entities = extractor.extract_from_profiles(profiles)
        john_entities = [e for e in entities if e.name == "John Smith"]
        # Should be deduplicated to one entity with multiple sources
        assert len(john_entities) == 1
        assert john_entities[0].source_count >= 1

    def test_clear_cache(self, extractor: EntityExtractor) -> None:
        """Test clearing entity cache."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                display_name="John Smith",
            )
        ]
        extractor.extract_from_profiles(profiles)
        assert len(extractor._entity_cache) > 0

        extractor.clear_cache()
        assert len(extractor._entity_cache) == 0


class TestEntityTypeInference:
    """Tests for entity type inference."""

    @pytest.fixture
    def extractor(self) -> EntityExtractor:
        """Create an entity extractor instance."""
        return EntityExtractor()

    def test_infer_organization(self, extractor: EntityExtractor) -> None:
        """Test inferring organization type."""
        assert extractor._infer_entity_type("Apple Inc") == EntityType.ORGANIZATION
        assert extractor._infer_entity_type("TechCorp LLC") == EntityType.ORGANIZATION
        assert extractor._infer_entity_type("Global Corp") == EntityType.ORGANIZATION

    def test_infer_title(self, extractor: EntityExtractor) -> None:
        """Test inferring title type."""
        assert extractor._infer_entity_type("CEO") == EntityType.TITLE
        assert extractor._infer_entity_type("Vice President") == EntityType.TITLE
        assert extractor._infer_entity_type("Director of Engineering") == EntityType.TITLE

    def test_infer_email(self, extractor: EntityExtractor) -> None:
        """Test inferring email type."""
        assert extractor._infer_entity_type("test@example.com") == EntityType.EMAIL

    def test_infer_social_handle(self, extractor: EntityExtractor) -> None:
        """Test inferring social handle type."""
        assert extractor._infer_entity_type("@username") == EntityType.SOCIAL_HANDLE

    def test_infer_person_default(self, extractor: EntityExtractor) -> None:
        """Test default inference is person."""
        assert extractor._infer_entity_type("John Smith") == EntityType.PERSON


class TestRelationshipExtractor:
    """Tests for RelationshipExtractor class."""

    @pytest.fixture
    def extractor(self) -> RelationshipExtractor:
        """Create a relationship extractor instance."""
        return RelationshipExtractor()

    def test_extract_current_employment(self, extractor: RelationshipExtractor) -> None:
        """Test extracting current employment relationship."""
        infos = [
            ProfessionalInfo(
                info_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                current_title="Software Engineer",
                current_company="TechCorp",
            )
        ]
        rels = extractor.extract_from_professional(infos, "John Smith")

        works_for = [r for r in rels if r.relationship_type == RelationshipType.WORKS_FOR]
        assert len(works_for) >= 1
        assert works_for[0].source_entity == "John Smith"
        assert works_for[0].target_entity == "TechCorp"
        assert works_for[0].is_current is True

    def test_extract_past_employment(self, extractor: RelationshipExtractor) -> None:
        """Test extracting past employment relationship."""
        infos = [
            ProfessionalInfo(
                info_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                current_title="Manager",
                current_company="NewCorp",
                employment_history=[
                    {
                        "company": "OldCorp",
                        "title": "Engineer",
                        "start_date": "2018",
                        "end_date": "2022",
                    },
                ],
            )
        ]
        rels = extractor.extract_from_professional(infos, "John Smith")

        worked_for = [r for r in rels if r.relationship_type == RelationshipType.WORKED_FOR]
        assert len(worked_for) >= 1
        assert worked_for[0].target_entity == "OldCorp"
        assert worked_for[0].is_current is False

    def test_extract_education(self, extractor: RelationshipExtractor) -> None:
        """Test extracting education relationship."""
        infos = [
            ProfessionalInfo(
                info_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                current_title="Engineer",
                current_company="Corp",
                education=[
                    {"school": "MIT", "degree": "BS Computer Science"},
                ],
            )
        ]
        rels = extractor.extract_from_professional(infos, "John Smith")

        educated_at = [r for r in rels if r.relationship_type == RelationshipType.EDUCATED_AT]
        assert len(educated_at) >= 1
        assert educated_at[0].target_entity == "MIT"

    def test_extract_board_positions(self, extractor: RelationshipExtractor) -> None:
        """Test extracting board member relationship."""
        infos = [
            ProfessionalInfo(
                info_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                current_title="CEO",
                current_company="Corp",
                board_positions=["NonProfit Foundation"],
            )
        ]
        rels = extractor.extract_from_professional(infos, "John Smith")

        board = [r for r in rels if r.relationship_type == RelationshipType.BOARD_MEMBER]
        assert len(board) >= 1
        assert board[0].target_entity == "NonProfit Foundation"

    def test_extract_from_news_mentions(self, extractor: RelationshipExtractor) -> None:
        """Test extracting relationships from news mentions."""
        mentions = [
            NewsMention(
                mention_id=uuid7(),
                source=OSINTSource.NEWS_WIRE,
                headline="Partnership Announcement",
                entities_mentioned=["John Smith", "Jane Doe", "TechCorp"],
            )
        ]
        rels = extractor.extract_from_news(mentions, "John Smith")

        mentioned_with = [r for r in rels if r.relationship_type == RelationshipType.MENTIONED_WITH]
        # Should have relationships with Jane Doe and TechCorp
        assert len(mentioned_with) >= 2

    def test_extract_location_from_profiles(self, extractor: RelationshipExtractor) -> None:
        """Test extracting location relationship from profiles."""
        profiles = [
            SocialMediaProfile(
                profile_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                display_name="John Smith",
                location="San Francisco, CA",
            )
        ]
        rels = extractor.extract_from_profiles(profiles, "John Smith")

        located_in = [r for r in rels if r.relationship_type == RelationshipType.LOCATED_IN]
        assert len(located_in) >= 1
        assert "San Francisco" in located_in[0].target_entity

    def test_relationship_deduplication(self, extractor: RelationshipExtractor) -> None:
        """Test that duplicate relationships are deduplicated."""
        infos = [
            ProfessionalInfo(
                info_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                current_company="TechCorp",
                current_title="Engineer",
            ),
            ProfessionalInfo(
                info_id=uuid7(),
                source=OSINTSource.CRUNCHBASE,
                current_company="TechCorp",
                current_title="Engineer",
            ),
        ]
        rels = extractor.extract_from_professional(infos, "John Smith")

        works_for = [r for r in rels if r.relationship_type == RelationshipType.WORKS_FOR]
        # Should be deduplicated to one relationship with multiple sources
        techcorp_rels = [r for r in works_for if r.target_entity == "TechCorp"]
        assert len(techcorp_rels) == 1
        assert techcorp_rels[0].source_count >= 1

    def test_clear_cache(self, extractor: RelationshipExtractor) -> None:
        """Test clearing relationship cache."""
        infos = [
            ProfessionalInfo(
                info_id=uuid7(),
                source=OSINTSource.LINKEDIN,
                current_company="TechCorp",
                current_title="Engineer",
            )
        ]
        extractor.extract_from_professional(infos, "John Smith")
        assert len(extractor._relationship_cache) > 0

        extractor.clear_cache()
        assert len(extractor._relationship_cache) == 0


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_entity_extractor(self) -> None:
        """Test create_entity_extractor factory."""
        extractor = create_entity_extractor()
        assert isinstance(extractor, EntityExtractor)

    def test_create_relationship_extractor(self) -> None:
        """Test create_relationship_extractor factory."""
        extractor = create_relationship_extractor()
        assert isinstance(extractor, RelationshipExtractor)
