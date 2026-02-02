"""Unit tests for Sanctions Provider type definitions.

Tests the enums, models, and exceptions for sanctions screening.
"""

from datetime import date, datetime
from uuid import UUID, uuid7

import pytest
from pydantic import ValidationError

from elile.providers.sanctions import (
    EntityType,
    FuzzyMatchConfig,
    MatchType,
    SanctionedEntity,
    SanctionsAddress,
    SanctionsAlias,
    SanctionsIdentifier,
    SanctionsList,
    SanctionsListUnavailableError,
    SanctionsMatch,
    SanctionsProviderError,
    SanctionsScreeningError,
    SanctionsScreeningResult,
)

# =============================================================================
# Enum Tests
# =============================================================================


class TestSanctionsList:
    """Tests for SanctionsList enum."""

    def test_ofac_sdn_value(self):
        """Test OFAC SDN list value."""
        assert SanctionsList.OFAC_SDN.value == "ofac_sdn"

    def test_ofac_consolidated_value(self):
        """Test OFAC Consolidated list value."""
        assert SanctionsList.OFAC_CONSOLIDATED.value == "ofac_consolidated"

    def test_un_consolidated_value(self):
        """Test UN Consolidated list value."""
        assert SanctionsList.UN_CONSOLIDATED.value == "un_consolidated"

    def test_eu_consolidated_value(self):
        """Test EU Consolidated list value."""
        assert SanctionsList.EU_CONSOLIDATED.value == "eu_consolidated"

    def test_interpol_red_value(self):
        """Test Interpol Red Notices value."""
        assert SanctionsList.INTERPOL_RED.value == "interpol_red"

    def test_interpol_yellow_value(self):
        """Test Interpol Yellow Notices value."""
        assert SanctionsList.INTERPOL_YELLOW.value == "interpol_yellow"

    def test_world_pep_value(self):
        """Test World PEP database value."""
        assert SanctionsList.WORLD_PEP.value == "world_pep"

    def test_world_rca_value(self):
        """Test World RCA database value."""
        assert SanctionsList.WORLD_RCA.value == "world_rca"

    def test_fbi_most_wanted_value(self):
        """Test FBI Most Wanted value."""
        assert SanctionsList.FBI_MOST_WANTED.value == "fbi_most_wanted"

    def test_bis_denied_value(self):
        """Test BIS Denied Persons value."""
        assert SanctionsList.BIS_DENIED.value == "bis_denied"

    def test_bis_entity_value(self):
        """Test BIS Entity List value."""
        assert SanctionsList.BIS_ENTITY.value == "bis_entity"

    def test_adverse_media_value(self):
        """Test Adverse Media value."""
        assert SanctionsList.ADVERSE_MEDIA.value == "adverse_media"

    def test_all_lists_have_unique_values(self):
        """Test all lists have unique values."""
        values = [lst.value for lst in SanctionsList]
        assert len(values) == len(set(values))


class TestMatchType:
    """Tests for MatchType enum."""

    def test_exact_value(self):
        """Test EXACT match value."""
        assert MatchType.EXACT.value == "exact"

    def test_strong_value(self):
        """Test STRONG match value."""
        assert MatchType.STRONG.value == "strong"

    def test_medium_value(self):
        """Test MEDIUM match value."""
        assert MatchType.MEDIUM.value == "medium"

    def test_weak_value(self):
        """Test WEAK match value."""
        assert MatchType.WEAK.value == "weak"

    def test_potential_value(self):
        """Test POTENTIAL match value."""
        assert MatchType.POTENTIAL.value == "potential"

    def test_no_match_value(self):
        """Test NO_MATCH value."""
        assert MatchType.NO_MATCH.value == "no_match"


class TestEntityType:
    """Tests for EntityType enum."""

    def test_individual_value(self):
        """Test INDIVIDUAL entity type."""
        assert EntityType.INDIVIDUAL.value == "individual"

    def test_organization_value(self):
        """Test ORGANIZATION entity type."""
        assert EntityType.ORGANIZATION.value == "organization"

    def test_vessel_value(self):
        """Test VESSEL entity type."""
        assert EntityType.VESSEL.value == "vessel"

    def test_aircraft_value(self):
        """Test AIRCRAFT entity type."""
        assert EntityType.AIRCRAFT.value == "aircraft"

    def test_unknown_value(self):
        """Test UNKNOWN entity type."""
        assert EntityType.UNKNOWN.value == "unknown"


# =============================================================================
# Model Tests
# =============================================================================


class TestSanctionsAlias:
    """Tests for SanctionsAlias model."""

    def test_create_alias_with_defaults(self):
        """Test creating alias with defaults."""
        alias = SanctionsAlias(alias_name="John Doe")
        assert alias.alias_name == "John Doe"
        assert alias.alias_type == "aka"
        assert alias.quality == "good"

    def test_create_alias_with_all_fields(self):
        """Test creating alias with all fields."""
        alias = SanctionsAlias(
            alias_name="Johnny D",
            alias_type="fka",
            quality="low",
        )
        assert alias.alias_name == "Johnny D"
        assert alias.alias_type == "fka"
        assert alias.quality == "low"


class TestSanctionsAddress:
    """Tests for SanctionsAddress model."""

    def test_create_address_with_defaults(self):
        """Test creating address with defaults."""
        addr = SanctionsAddress()
        assert addr.street is None
        assert addr.city is None
        assert addr.address_type == "primary"

    def test_create_full_address(self):
        """Test creating address with all fields."""
        addr = SanctionsAddress(
            street="123 Main St",
            city="New York",
            state_province="NY",
            postal_code="10001",
            country="US",
            address_type="mailing",
        )
        assert addr.street == "123 Main St"
        assert addr.city == "New York"
        assert addr.state_province == "NY"
        assert addr.postal_code == "10001"
        assert addr.country == "US"
        assert addr.address_type == "mailing"


class TestSanctionsIdentifier:
    """Tests for SanctionsIdentifier model."""

    def test_create_identifier(self):
        """Test creating identifier."""
        ident = SanctionsIdentifier(
            id_type="passport",
            id_number="AB123456",
            country="US",
            notes="Expired 2020",
        )
        assert ident.id_type == "passport"
        assert ident.id_number == "AB123456"
        assert ident.country == "US"
        assert ident.notes == "Expired 2020"

    def test_identifier_without_optional_fields(self):
        """Test identifier without optional fields."""
        ident = SanctionsIdentifier(
            id_type="national_id",
            id_number="123-456-789",
        )
        assert ident.country is None
        assert ident.notes is None


class TestSanctionedEntity:
    """Tests for SanctionedEntity model."""

    def test_create_minimal_entity(self):
        """Test creating entity with minimal fields."""
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="John Doe",
        )
        assert entity.entity_id == "TEST-001"
        assert entity.list_source == SanctionsList.OFAC_SDN
        assert entity.entity_type == EntityType.INDIVIDUAL
        assert entity.name == "John Doe"
        assert entity.aliases == []
        assert entity.nationality == []

    def test_create_full_entity(self):
        """Test creating entity with all fields."""
        now = datetime.now()
        entity = SanctionedEntity(
            entity_id="TEST-002",
            list_source=SanctionsList.UN_CONSOLIDATED,
            entity_type=EntityType.ORGANIZATION,
            name="Evil Corp",
            aliases=[SanctionsAlias(alias_name="E-Corp")],
            date_of_birth=date(1990, 1, 1),
            place_of_birth="Unknown",
            nationality=["RU", "BY"],
            addresses=[SanctionsAddress(city="Moscow")],
            identifiers=[SanctionsIdentifier(id_type="ein", id_number="12-3456789")],
            programs=["RUSSIA", "CYBER"],
            remarks="Known cyber threat actor",
            listed_date=date(2022, 3, 1),
            last_updated=now,
            raw_data={"source": "test"},
        )
        assert entity.name == "Evil Corp"
        assert len(entity.aliases) == 1
        assert entity.aliases[0].alias_name == "E-Corp"
        assert entity.date_of_birth == date(1990, 1, 1)
        assert len(entity.nationality) == 2
        assert len(entity.programs) == 2
        assert entity.remarks == "Known cyber threat actor"


class TestSanctionsMatch:
    """Tests for SanctionsMatch model."""

    def test_create_match(self):
        """Test creating a match."""
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="John Doe",
        )
        match = SanctionsMatch(
            match_id=uuid7(),
            entity=entity,
            match_type=MatchType.STRONG,
            match_score=0.92,
            matched_fields=["name", "dob"],
            match_reasons=["Primary name match: John Doe"],
        )
        assert isinstance(match.match_id, UUID)
        assert match.entity.name == "John Doe"
        assert match.match_type == MatchType.STRONG
        assert match.match_score == 0.92
        assert "name" in match.matched_fields

    def test_match_score_validation_min(self):
        """Test match score minimum validation."""
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="Test",
        )
        with pytest.raises(ValidationError):
            SanctionsMatch(
                match_id=uuid7(),
                entity=entity,
                match_type=MatchType.WEAK,
                match_score=-0.1,  # Invalid: below 0.0
            )

    def test_match_score_validation_max(self):
        """Test match score maximum validation."""
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="Test",
        )
        with pytest.raises(ValidationError):
            SanctionsMatch(
                match_id=uuid7(),
                entity=entity,
                match_type=MatchType.EXACT,
                match_score=1.5,  # Invalid: above 1.0
            )


class TestSanctionsScreeningResult:
    """Tests for SanctionsScreeningResult model."""

    def test_create_no_hit_result(self):
        """Test creating result with no matches."""
        result = SanctionsScreeningResult(
            screening_id=uuid7(),
            subject_name="Clean Person",
            lists_screened=[SanctionsList.OFAC_SDN, SanctionsList.UN_CONSOLIDATED],
        )
        assert result.subject_name == "Clean Person"
        assert result.total_matches == 0
        assert result.has_hit is False
        assert result.highest_match_score == 0.0
        assert len(result.matches) == 0

    def test_create_hit_result(self):
        """Test creating result with matches."""
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="John Doe",
        )
        match = SanctionsMatch(
            match_id=uuid7(),
            entity=entity,
            match_type=MatchType.STRONG,
            match_score=0.92,
        )
        result = SanctionsScreeningResult(
            screening_id=uuid7(),
            subject_name="John Doe",
            lists_screened=[SanctionsList.OFAC_SDN],
            matches=[match],
            total_matches=1,
            highest_match_score=0.92,
            has_hit=True,
        )
        assert result.has_hit is True
        assert result.total_matches == 1
        assert result.highest_match_score == 0.92

    def test_get_strong_matches(self):
        """Test filtering for strong/exact matches."""
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="John Doe",
        )
        matches = [
            SanctionsMatch(
                match_id=uuid7(),
                entity=entity,
                match_type=MatchType.EXACT,
                match_score=0.99,
            ),
            SanctionsMatch(
                match_id=uuid7(),
                entity=entity,
                match_type=MatchType.STRONG,
                match_score=0.92,
            ),
            SanctionsMatch(
                match_id=uuid7(),
                entity=entity,
                match_type=MatchType.WEAK,
                match_score=0.72,
            ),
        ]
        result = SanctionsScreeningResult(
            screening_id=uuid7(),
            subject_name="John Doe",
            matches=matches,
            total_matches=3,
            has_hit=True,
        )
        strong_matches = result.get_strong_matches()
        assert len(strong_matches) == 2

    def test_get_matches_by_list(self):
        """Test filtering matches by list source."""
        ofac_entity = SanctionedEntity(
            entity_id="OFAC-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="Person A",
        )
        un_entity = SanctionedEntity(
            entity_id="UN-001",
            list_source=SanctionsList.UN_CONSOLIDATED,
            entity_type=EntityType.INDIVIDUAL,
            name="Person B",
        )
        matches = [
            SanctionsMatch(
                match_id=uuid7(),
                entity=ofac_entity,
                match_type=MatchType.STRONG,
                match_score=0.90,
            ),
            SanctionsMatch(
                match_id=uuid7(),
                entity=un_entity,
                match_type=MatchType.MEDIUM,
                match_score=0.85,
            ),
        ]
        result = SanctionsScreeningResult(
            screening_id=uuid7(),
            subject_name="Test",
            matches=matches,
            total_matches=2,
            has_hit=True,
        )
        ofac_matches = result.get_matches_by_list(SanctionsList.OFAC_SDN)
        assert len(ofac_matches) == 1
        assert ofac_matches[0].entity.entity_id == "OFAC-001"

        un_matches = result.get_matches_by_list(SanctionsList.UN_CONSOLIDATED)
        assert len(un_matches) == 1

        eu_matches = result.get_matches_by_list(SanctionsList.EU_CONSOLIDATED)
        assert len(eu_matches) == 0


class TestFuzzyMatchConfig:
    """Tests for FuzzyMatchConfig model."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        config = FuzzyMatchConfig()
        assert config.exact_threshold == 0.99
        assert config.strong_threshold == 0.90
        assert config.medium_threshold == 0.80
        assert config.weak_threshold == 0.70
        assert config.min_threshold == 0.60

    def test_default_options(self):
        """Test default option values."""
        config = FuzzyMatchConfig()
        assert config.use_phonetic is True
        assert config.use_aliases is True
        assert config.weight_dob == 0.2
        assert config.weight_country == 0.1

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        config = FuzzyMatchConfig(
            exact_threshold=0.98,
            strong_threshold=0.85,
            medium_threshold=0.75,
        )
        assert config.exact_threshold == 0.98
        assert config.strong_threshold == 0.85
        assert config.medium_threshold == 0.75

    def test_score_to_match_type_exact(self):
        """Test score to match type conversion - exact."""
        config = FuzzyMatchConfig()
        assert config.score_to_match_type(1.0) == MatchType.EXACT
        assert config.score_to_match_type(0.99) == MatchType.EXACT

    def test_score_to_match_type_strong(self):
        """Test score to match type conversion - strong."""
        config = FuzzyMatchConfig()
        assert config.score_to_match_type(0.95) == MatchType.STRONG
        assert config.score_to_match_type(0.90) == MatchType.STRONG

    def test_score_to_match_type_medium(self):
        """Test score to match type conversion - medium."""
        config = FuzzyMatchConfig()
        assert config.score_to_match_type(0.85) == MatchType.MEDIUM
        assert config.score_to_match_type(0.80) == MatchType.MEDIUM

    def test_score_to_match_type_weak(self):
        """Test score to match type conversion - weak."""
        config = FuzzyMatchConfig()
        assert config.score_to_match_type(0.75) == MatchType.WEAK
        assert config.score_to_match_type(0.70) == MatchType.WEAK

    def test_score_to_match_type_potential(self):
        """Test score to match type conversion - potential."""
        config = FuzzyMatchConfig()
        assert config.score_to_match_type(0.65) == MatchType.POTENTIAL
        assert config.score_to_match_type(0.60) == MatchType.POTENTIAL

    def test_score_to_match_type_no_match(self):
        """Test score to match type conversion - no match."""
        config = FuzzyMatchConfig()
        assert config.score_to_match_type(0.59) == MatchType.NO_MATCH
        assert config.score_to_match_type(0.0) == MatchType.NO_MATCH

    def test_threshold_validation_bounds(self):
        """Test threshold validation bounds."""
        with pytest.raises(ValidationError):
            FuzzyMatchConfig(exact_threshold=1.5)

        with pytest.raises(ValidationError):
            FuzzyMatchConfig(min_threshold=-0.1)


# =============================================================================
# Exception Tests
# =============================================================================


class TestSanctionsProviderError:
    """Tests for SanctionsProviderError exception."""

    def test_create_error(self):
        """Test creating provider error."""
        error = SanctionsProviderError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {}

    def test_create_error_with_details(self):
        """Test creating error with details."""
        error = SanctionsProviderError(
            "Test error",
            details={"code": "TEST_001", "context": "unit test"},
        )
        assert error.message == "Test error"
        assert error.details["code"] == "TEST_001"
        assert error.details["context"] == "unit test"


class TestSanctionsListUnavailableError:
    """Tests for SanctionsListUnavailableError exception."""

    def test_create_unavailable_error(self):
        """Test creating list unavailable error."""
        error = SanctionsListUnavailableError(
            SanctionsList.OFAC_SDN,
            "Connection timeout",
        )
        assert error.list_source == SanctionsList.OFAC_SDN
        assert error.reason == "Connection timeout"
        assert "ofac_sdn" in str(error)
        assert "Connection timeout" in str(error)
        assert error.details["list_source"] == "ofac_sdn"


class TestSanctionsScreeningError:
    """Tests for SanctionsScreeningError exception."""

    def test_create_screening_error(self):
        """Test creating screening error."""
        screening_id = uuid7()
        error = SanctionsScreeningError(
            screening_id,
            "Invalid subject name",
        )
        assert error.screening_id == screening_id
        assert error.reason == "Invalid subject name"
        assert str(screening_id) in str(error)
        assert "Invalid subject name" in str(error)
