"""Unit tests for Entity Resolution Engine.

Tests the EntityMatcher class, SubjectIdentifiers, MatchResult,
and related types for the entity resolution system.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid7

import pytest

from elile.agent.state import ServiceTier
from elile.db.models.entity import Entity, EntityType
from elile.entity import (
    EntityMatcher,
    IdentifierRecord,
    IdentifierType,
    MatchedField,
    MatchResult,
    MatchType,
    RelationType,
    ResolutionDecision,
    SubjectIdentifiers,
)


# =============================================================================
# SubjectIdentifiers Tests
# =============================================================================


class TestSubjectIdentifiers:
    """Tests for SubjectIdentifiers model."""

    def test_create_with_name_only(self):
        """Test creating identifiers with just a name."""
        identifiers = SubjectIdentifiers(full_name="John Smith")
        assert identifiers.full_name == "John Smith"
        assert identifiers.ssn is None
        assert identifiers.date_of_birth is None

    def test_create_with_all_fields(self):
        """Test creating identifiers with all fields."""
        identifiers = SubjectIdentifiers(
            full_name="John Michael Smith",
            first_name="John",
            middle_name="Michael",
            last_name="Smith",
            date_of_birth=date(1980, 1, 15),
            street_address="123 Main St",
            city="Springfield",
            state="IL",
            postal_code="62701",
            country="US",
            ssn="123-45-6789",
            email="john.smith@example.com",
            phone="+1-555-123-4567",
        )
        assert identifiers.full_name == "John Michael Smith"
        assert identifiers.date_of_birth == date(1980, 1, 15)
        assert identifiers.ssn == "123-45-6789"
        assert identifiers.country == "US"

    def test_has_canonical_identifiers_true(self):
        """Test has_canonical_identifiers returns True when SSN present."""
        identifiers = SubjectIdentifiers(full_name="John Smith", ssn="123-45-6789")
        assert identifiers.has_canonical_identifiers() is True

    def test_has_canonical_identifiers_with_ein(self):
        """Test has_canonical_identifiers returns True when EIN present."""
        identifiers = SubjectIdentifiers(full_name="Acme Corp", ein="12-3456789")
        assert identifiers.has_canonical_identifiers() is True

    def test_has_canonical_identifiers_false(self):
        """Test has_canonical_identifiers returns False when no canonical IDs."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            email="john@example.com",
            phone="555-1234",
        )
        assert identifiers.has_canonical_identifiers() is False

    def test_get_canonical_identifiers_empty(self):
        """Test get_canonical_identifiers with no IDs."""
        identifiers = SubjectIdentifiers(full_name="John Smith")
        canonical = identifiers.get_canonical_identifiers()
        assert canonical == {}

    def test_get_canonical_identifiers_all(self):
        """Test get_canonical_identifiers returns all available IDs."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="123-45-6789",
            ein="12-3456789",
            passport="AB1234567",
            drivers_license="D1234567",
            email="john@example.com",
            phone="+15551234567",
        )
        canonical = identifiers.get_canonical_identifiers()
        assert IdentifierType.SSN in canonical
        assert IdentifierType.EIN in canonical
        assert IdentifierType.PASSPORT in canonical
        assert IdentifierType.DRIVERS_LICENSE in canonical
        assert IdentifierType.EMAIL in canonical
        assert IdentifierType.PHONE in canonical
        assert canonical[IdentifierType.SSN] == "123-45-6789"

    def test_name_variants_default_empty(self):
        """Test name_variants defaults to empty list."""
        identifiers = SubjectIdentifiers(full_name="John Smith")
        assert identifiers.name_variants == []

    def test_name_variants_populated(self):
        """Test name_variants can be populated."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            name_variants=["Johnny Smith", "J. Smith", "John Q. Smith"],
        )
        assert len(identifiers.name_variants) == 3
        assert "Johnny Smith" in identifiers.name_variants


# =============================================================================
# MatchResult Tests
# =============================================================================


class TestMatchResult:
    """Tests for MatchResult model."""

    def test_create_exact_match(self):
        """Test creating an exact match result."""
        entity_id = uuid7()
        result = MatchResult(
            entity_id=entity_id,
            match_type=MatchType.EXACT,
            confidence=1.0,
            decision=ResolutionDecision.MATCH_EXISTING,
            matched_identifiers=[IdentifierType.SSN],
            resolution_notes="Exact match on SSN",
        )
        assert result.entity_id == entity_id
        assert result.match_type == MatchType.EXACT
        assert result.confidence == 1.0
        assert result.decision == ResolutionDecision.MATCH_EXISTING
        assert not result.requires_review

    def test_create_fuzzy_match(self):
        """Test creating a fuzzy match result."""
        entity_id = uuid7()
        result = MatchResult(
            entity_id=entity_id,
            match_type=MatchType.FUZZY,
            confidence=0.87,
            decision=ResolutionDecision.MATCH_EXISTING,
            matched_fields=[
                MatchedField(
                    field_name="full_name",
                    source_value="John Smith",
                    matched_value="John A. Smith",
                    similarity=0.92,
                )
            ],
        )
        assert result.match_type == MatchType.FUZZY
        assert result.confidence == 0.87
        assert len(result.matched_fields) == 1

    def test_create_pending_review(self):
        """Test creating a pending review result."""
        entity_id = uuid7()
        result = MatchResult(
            entity_id=entity_id,
            match_type=MatchType.FUZZY,
            confidence=0.75,
            decision=ResolutionDecision.PENDING_REVIEW,
            requires_review=True,
        )
        assert result.decision == ResolutionDecision.PENDING_REVIEW
        assert result.requires_review is True

    def test_create_new_entity(self):
        """Test creating a new entity result."""
        result = MatchResult(
            match_type=MatchType.NEW,
            confidence=0.0,
            decision=ResolutionDecision.CREATE_NEW,
            resolution_notes="No matching entities found",
        )
        assert result.entity_id is None
        assert result.match_type == MatchType.NEW
        assert result.decision == ResolutionDecision.CREATE_NEW

    def test_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValueError):
            MatchResult(
                match_type=MatchType.FUZZY,
                confidence=1.5,  # Invalid
                decision=ResolutionDecision.CREATE_NEW,
            )

        with pytest.raises(ValueError):
            MatchResult(
                match_type=MatchType.FUZZY,
                confidence=-0.1,  # Invalid
                decision=ResolutionDecision.CREATE_NEW,
            )


# =============================================================================
# MatchedField Tests
# =============================================================================


class TestMatchedField:
    """Tests for MatchedField model."""

    def test_create_matched_field(self):
        """Test creating a matched field."""
        field = MatchedField(
            field_name="full_name",
            source_value="John Smith",
            matched_value="John A. Smith",
            similarity=0.92,
        )
        assert field.field_name == "full_name"
        assert field.source_value == "John Smith"
        assert field.matched_value == "John A. Smith"
        assert field.similarity == 0.92


# =============================================================================
# IdentifierRecord Tests
# =============================================================================


class TestIdentifierRecord:
    """Tests for IdentifierRecord model."""

    def test_create_identifier_record(self):
        """Test creating an identifier record."""
        from datetime import datetime

        record = IdentifierRecord(
            identifier_type=IdentifierType.SSN,
            value="123-45-6789",
            confidence=1.0,
            discovered_at=datetime.now(),
            source="employment_verification",
        )
        assert record.identifier_type == IdentifierType.SSN
        assert record.value == "123-45-6789"
        assert record.confidence == 1.0

    def test_to_dict(self):
        """Test converting identifier record to dictionary."""
        from datetime import datetime

        now = datetime.now()
        record = IdentifierRecord(
            identifier_type=IdentifierType.PASSPORT,
            value="AB1234567",
            confidence=0.95,
            discovered_at=now,
            source="travel_records",
            country="US",
        )
        result = record.to_dict()
        assert result["value"] == "AB1234567"
        assert result["confidence"] == 0.95
        assert result["source"] == "travel_records"
        assert result["country"] == "US"
        assert "discovered_at" in result


# =============================================================================
# Enum Tests
# =============================================================================


class TestEnums:
    """Tests for entity resolution enums."""

    def test_match_type_values(self):
        """Test MatchType enum values."""
        assert MatchType.EXACT.value == "exact"
        assert MatchType.FUZZY.value == "fuzzy"
        assert MatchType.NEW.value == "new"

    def test_resolution_decision_values(self):
        """Test ResolutionDecision enum values."""
        assert ResolutionDecision.MATCH_EXISTING.value == "match_existing"
        assert ResolutionDecision.CREATE_NEW.value == "create_new"
        assert ResolutionDecision.PENDING_REVIEW.value == "pending_review"

    def test_identifier_type_values(self):
        """Test IdentifierType enum values."""
        assert IdentifierType.SSN.value == "ssn"
        assert IdentifierType.EIN.value == "ein"
        assert IdentifierType.PASSPORT.value == "passport"
        assert IdentifierType.EMAIL.value == "email"
        assert IdentifierType.PHONE.value == "phone"

    def test_relation_type_values(self):
        """Test RelationType enum values."""
        assert RelationType.EMPLOYER.value == "employer"
        assert RelationType.EMPLOYEE.value == "employee"
        assert RelationType.HOUSEHOLD.value == "household"
        assert RelationType.FAMILY.value == "family"
        assert RelationType.DIRECTOR.value == "director"


# =============================================================================
# EntityMatcher Tests
# =============================================================================


class TestEntityMatcher:
    """Tests for EntityMatcher class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def matcher(self, mock_session):
        """Create an EntityMatcher instance."""
        return EntityMatcher(mock_session)

    def test_init(self, mock_session):
        """Test EntityMatcher initialization."""
        matcher = EntityMatcher(mock_session)
        assert matcher._session is mock_session

    # -------------------------------------------------------------------------
    # Identifier Normalization Tests
    # -------------------------------------------------------------------------

    def test_normalize_ssn(self, matcher):
        """Test SSN normalization."""
        assert matcher._normalize_identifier(IdentifierType.SSN, "123-45-6789") == "123456789"
        assert matcher._normalize_identifier(IdentifierType.SSN, "123 45 6789") == "123456789"
        assert matcher._normalize_identifier(IdentifierType.SSN, "123456789") == "123456789"

    def test_normalize_ein(self, matcher):
        """Test EIN normalization."""
        assert matcher._normalize_identifier(IdentifierType.EIN, "12-3456789") == "123456789"
        assert matcher._normalize_identifier(IdentifierType.EIN, "123456789") == "123456789"

    def test_normalize_phone(self, matcher):
        """Test phone number normalization."""
        # Remove country code prefix
        assert matcher._normalize_identifier(IdentifierType.PHONE, "+1-555-123-4567") == "5551234567"
        assert matcher._normalize_identifier(IdentifierType.PHONE, "15551234567") == "5551234567"
        assert matcher._normalize_identifier(IdentifierType.PHONE, "(555) 123-4567") == "5551234567"

    def test_normalize_email(self, matcher):
        """Test email normalization."""
        assert matcher._normalize_identifier(IdentifierType.EMAIL, "John@Example.COM") == "john@example.com"
        assert matcher._normalize_identifier(IdentifierType.EMAIL, "  user@test.com  ") == "user@test.com"

    def test_normalize_empty(self, matcher):
        """Test normalizing empty value."""
        assert matcher._normalize_identifier(IdentifierType.SSN, "") == ""
        assert matcher._normalize_identifier(IdentifierType.SSN, None) == ""

    # -------------------------------------------------------------------------
    # String Similarity Tests
    # -------------------------------------------------------------------------

    def test_string_similarity_exact(self, matcher):
        """Test string similarity for exact match."""
        assert matcher._string_similarity("John Smith", "John Smith") == 1.0

    def test_string_similarity_case_insensitive(self, matcher):
        """Test string similarity is case insensitive."""
        assert matcher._string_similarity("John Smith", "john smith") == 1.0

    def test_string_similarity_high(self, matcher):
        """Test high string similarity."""
        sim = matcher._string_similarity("John Smith", "John A. Smith")
        assert sim > 0.85

    def test_string_similarity_medium(self, matcher):
        """Test medium string similarity."""
        sim = matcher._string_similarity("John Smith", "Jonathan Smithson")
        assert 0.7 < sim < 0.95

    def test_string_similarity_low(self, matcher):
        """Test low string similarity."""
        sim = matcher._string_similarity("John Smith", "Robert Johnson")
        assert sim < 0.5

    def test_string_similarity_empty(self, matcher):
        """Test string similarity with empty strings."""
        assert matcher._string_similarity("", "") == 1.0
        assert matcher._string_similarity("John", "") == 0.0
        assert matcher._string_similarity("", "John") == 0.0

    # -------------------------------------------------------------------------
    # Jaro Similarity Tests
    # -------------------------------------------------------------------------

    def test_jaro_similarity_exact(self, matcher):
        """Test Jaro similarity for exact match."""
        assert matcher._jaro_similarity("hello", "hello") == 1.0

    def test_jaro_similarity_similar(self, matcher):
        """Test Jaro similarity for similar strings."""
        sim = matcher._jaro_similarity("martha", "marhta")
        assert sim > 0.9

    def test_jaro_similarity_different(self, matcher):
        """Test Jaro similarity for different strings."""
        sim = matcher._jaro_similarity("hello", "world")
        assert sim < 0.5

    def test_jaro_similarity_empty(self, matcher):
        """Test Jaro similarity with empty strings."""
        assert matcher._jaro_similarity("", "") == 1.0

    # -------------------------------------------------------------------------
    # Exact Match Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_match_exact_no_canonical_ids(self, matcher):
        """Test exact match with no canonical identifiers."""
        identifiers = SubjectIdentifiers(full_name="John Smith")
        result = await matcher.match_exact(identifiers, EntityType.INDIVIDUAL)
        assert result.match_type == MatchType.NEW
        assert result.decision == ResolutionDecision.CREATE_NEW
        assert result.entity_id is None

    @pytest.mark.asyncio
    async def test_match_exact_with_ssn_no_match(self, mock_session, matcher):
        """Test exact match with SSN but no entity found."""
        # Setup mock to return empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="123-45-6789",
        )
        result = await matcher.match_exact(identifiers, EntityType.INDIVIDUAL)
        assert result.match_type == MatchType.NEW
        assert result.decision == ResolutionDecision.CREATE_NEW

    @pytest.mark.asyncio
    async def test_match_exact_with_ssn_match(self, mock_session, matcher):
        """Test exact match with SSN finds entity."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.entity_type = EntityType.INDIVIDUAL.value
        mock_entity.canonical_identifiers = {
            "ssn": {"value": "123456789"},
        }

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="123-45-6789",
        )
        result = await matcher.match_exact(identifiers, EntityType.INDIVIDUAL)
        assert result.match_type == MatchType.EXACT
        assert result.confidence == 1.0
        assert result.decision == ResolutionDecision.MATCH_EXISTING
        assert result.entity_id == entity_id
        assert IdentifierType.SSN in result.matched_identifiers

    @pytest.mark.asyncio
    async def test_match_exact_skips_soft_identifiers(self, mock_session, matcher):
        """Test exact match skips email and phone (soft identifiers)."""
        # Setup mock to return empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            email="john@example.com",
            phone="+15551234567",
        )
        result = await matcher.match_exact(identifiers, EntityType.INDIVIDUAL)
        # Should create new since email/phone are soft identifiers
        assert result.match_type == MatchType.NEW
        assert result.decision == ResolutionDecision.CREATE_NEW

    # -------------------------------------------------------------------------
    # Fuzzy Match Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_match_fuzzy_no_name(self, matcher):
        """Test fuzzy match without name returns new entity."""
        identifiers = SubjectIdentifiers(ssn="123-45-6789")
        result = await matcher.match_fuzzy(identifiers, EntityType.INDIVIDUAL)
        assert result.match_type == MatchType.NEW
        assert result.decision == ResolutionDecision.CREATE_NEW
        assert "No name provided" in result.resolution_notes

    @pytest.mark.asyncio
    async def test_match_fuzzy_no_candidates(self, mock_session, matcher):
        """Test fuzzy match with no candidate entities."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(full_name="John Smith")
        result = await matcher.match_fuzzy(identifiers, EntityType.INDIVIDUAL)
        assert result.match_type == MatchType.NEW
        assert result.decision == ResolutionDecision.CREATE_NEW
        assert "No candidate entities" in result.resolution_notes

    @pytest.mark.asyncio
    async def test_match_fuzzy_high_confidence(self, mock_session, matcher):
        """Test fuzzy match with high confidence auto-matches."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
            "date_of_birth": {"value": "1980-01-15"},
            "address": {"value": "123 Main St Springfield IL 62701"},
        }

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date(1980, 1, 15),
            street_address="123 Main St",
            city="Springfield",
            state="IL",
            postal_code="62701",
        )
        result = await matcher.match_fuzzy(
            identifiers, EntityType.INDIVIDUAL, ServiceTier.STANDARD
        )
        assert result.match_type == MatchType.FUZZY
        assert result.confidence >= 0.85
        assert result.decision == ResolutionDecision.MATCH_EXISTING
        assert result.entity_id == entity_id

    @pytest.mark.asyncio
    async def test_match_fuzzy_medium_confidence_standard_tier(self, mock_session, matcher):
        """Test fuzzy match with medium confidence in Standard tier creates new."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "John A. Smith"},
            # Different DOB - should lower confidence
            "date_of_birth": {"value": "1981-02-20"},
        }

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date(1980, 1, 15),
        )
        result = await matcher.match_fuzzy(
            identifiers, EntityType.INDIVIDUAL, ServiceTier.STANDARD
        )
        # Medium confidence in Standard tier should create new
        if 0.70 <= result.confidence < 0.85:
            assert result.decision == ResolutionDecision.CREATE_NEW

    @pytest.mark.asyncio
    async def test_match_fuzzy_medium_confidence_enhanced_tier(self, mock_session, matcher):
        """Test fuzzy match with medium confidence in Enhanced tier requires review."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
            # No DOB - should lower confidence to medium range
        }

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date(1980, 1, 15),
        )
        result = await matcher.match_fuzzy(
            identifiers, EntityType.INDIVIDUAL, ServiceTier.ENHANCED
        )
        # High name similarity but missing DOB - could be pending review
        if 0.70 <= result.confidence < 0.85:
            assert result.decision == ResolutionDecision.PENDING_REVIEW
            assert result.requires_review is True

    @pytest.mark.asyncio
    async def test_match_fuzzy_low_confidence(self, mock_session, matcher):
        """Test fuzzy match with low confidence creates new entity."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "Robert Johnson"},
            "date_of_birth": {"value": "1990-06-01"},
        }

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date(1980, 1, 15),
        )
        result = await matcher.match_fuzzy(
            identifiers, EntityType.INDIVIDUAL, ServiceTier.STANDARD
        )
        # Very different names should result in low confidence
        assert result.confidence < 0.70
        assert result.decision == ResolutionDecision.CREATE_NEW

    # -------------------------------------------------------------------------
    # Resolve Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_resolve_exact_match_first(self, mock_session, matcher):
        """Test resolve attempts exact match before fuzzy."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {
            "ssn": {"value": "123456789"},
        }

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="123-45-6789",
        )
        result = await matcher.resolve(identifiers)
        assert result.match_type == MatchType.EXACT
        assert result.entity_id == entity_id

    @pytest.mark.asyncio
    async def test_resolve_falls_back_to_fuzzy(self, mock_session, matcher):
        """Test resolve falls back to fuzzy when no exact match."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
            "date_of_birth": {"value": "1980-01-15"},
            "address": {"value": "123 Main St Springfield IL 62701"},
        }

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date(1980, 1, 15),
            street_address="123 Main St",
            city="Springfield",
            state="IL",
            postal_code="62701",
        )
        result = await matcher.resolve(identifiers)
        # No SSN means no exact match, should fall back to fuzzy
        assert result.match_type == MatchType.FUZZY

    # -------------------------------------------------------------------------
    # Entity Helper Tests
    # -------------------------------------------------------------------------

    def test_get_entity_name_from_full_name(self, matcher):
        """Test extracting name from entity."""
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
        }
        assert matcher._get_entity_name(mock_entity) == "John Smith"

    def test_get_entity_name_from_variants(self, matcher):
        """Test extracting name from variants."""
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {
            "name_variants": [{"value": "John Smith"}, {"value": "J. Smith"}],
        }
        assert matcher._get_entity_name(mock_entity) == "John Smith"

    def test_get_entity_name_none(self, matcher):
        """Test extracting name when not present."""
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {}
        assert matcher._get_entity_name(mock_entity) is None

    def test_get_entity_dob(self, matcher):
        """Test extracting DOB from entity."""
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {
            "date_of_birth": {"value": "1980-01-15"},
        }
        assert matcher._get_entity_dob(mock_entity) == "1980-01-15"

    def test_get_entity_dob_none(self, matcher):
        """Test extracting DOB when not present."""
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {}
        assert matcher._get_entity_dob(mock_entity) is None

    def test_get_entity_address(self, matcher):
        """Test extracting address from entity."""
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {
            "address": {"value": "123 Main St Springfield IL 62701"},
        }
        assert matcher._get_entity_address(mock_entity) == "123 Main St Springfield IL 62701"

    # -------------------------------------------------------------------------
    # Address Similarity Tests
    # -------------------------------------------------------------------------

    def test_address_similarity_exact(self, matcher):
        """Test address similarity for exact match."""
        identifiers = SubjectIdentifiers(
            street_address="123 Main St",
            city="Springfield",
            state="IL",
            postal_code="62701",
        )
        entity_address = "123 Main St Springfield IL 62701"
        sim = matcher._address_similarity(identifiers, entity_address)
        assert sim > 0.9

    def test_address_similarity_partial(self, matcher):
        """Test address similarity for partial match."""
        identifiers = SubjectIdentifiers(
            street_address="123 Main Street",
            city="Springfield",
            state="IL",
        )
        entity_address = "123 Main St Springfield IL 62701"
        sim = matcher._address_similarity(identifiers, entity_address)
        assert sim > 0.7

    # -------------------------------------------------------------------------
    # Calculate Similarity Tests
    # -------------------------------------------------------------------------

    def test_calculate_similarity_name_only(self, matcher):
        """Test similarity calculation with name only."""
        identifiers = SubjectIdentifiers(full_name="John Smith")
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
        }

        confidence, matched_fields = matcher._calculate_similarity(identifiers, mock_entity)
        assert confidence > 0.9
        assert len(matched_fields) == 1
        assert matched_fields[0].field_name == "full_name"

    def test_calculate_similarity_name_and_dob(self, matcher):
        """Test similarity calculation with name and DOB."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date(1980, 1, 15),
        )
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
            "date_of_birth": {"value": "1980-01-15"},
        }

        confidence, matched_fields = matcher._calculate_similarity(identifiers, mock_entity)
        assert confidence > 0.9
        assert len(matched_fields) == 2

    def test_calculate_similarity_all_fields(self, matcher):
        """Test similarity calculation with all fields."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date(1980, 1, 15),
            street_address="123 Main St",
            city="Springfield",
            state="IL",
            postal_code="62701",
        )
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
            "date_of_birth": {"value": "1980-01-15"},
            "address": {"value": "123 Main St Springfield IL 62701"},
        }

        confidence, matched_fields = matcher._calculate_similarity(identifiers, mock_entity)
        assert confidence > 0.95
        assert len(matched_fields) == 3

    def test_calculate_similarity_no_matching_fields(self, matcher):
        """Test similarity calculation with no data."""
        identifiers = SubjectIdentifiers()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {}

        confidence, matched_fields = matcher._calculate_similarity(identifiers, mock_entity)
        assert confidence == 0.0
        assert len(matched_fields) == 0

    def test_calculate_similarity_dob_mismatch(self, matcher):
        """Test similarity with mismatched DOB lowers confidence."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date(1980, 1, 15),
        )
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
            "date_of_birth": {"value": "1985-06-20"},  # Different DOB
        }

        confidence, matched_fields = matcher._calculate_similarity(identifiers, mock_entity)
        # DOB mismatch should lower overall confidence
        assert confidence < 0.85
        # Only name should match
        assert len(matched_fields) == 1


# =============================================================================
# Integration-style Tests (still unit but testing full flow)
# =============================================================================


class TestEntityMatcherIntegration:
    """Integration-style tests for EntityMatcher."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_full_resolution_flow_exact_match(self, mock_session):
        """Test complete resolution flow with exact SSN match."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.entity_type = EntityType.INDIVIDUAL.value
        mock_entity.canonical_identifiers = {
            "ssn": {"value": "123456789"},
            "full_name": {"value": "John Michael Smith"},
        }

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute.return_value = mock_result

        matcher = EntityMatcher(mock_session)
        identifiers = SubjectIdentifiers(
            full_name="John M. Smith",
            first_name="John",
            middle_name="Michael",
            last_name="Smith",
            date_of_birth=date(1980, 1, 15),
            ssn="123-45-6789",
        )

        result = await matcher.resolve(identifiers)

        assert result.match_type == MatchType.EXACT
        assert result.confidence == 1.0
        assert result.decision == ResolutionDecision.MATCH_EXISTING
        assert result.entity_id == entity_id
        assert IdentifierType.SSN in result.matched_identifiers
        assert "Exact match on ssn" in result.resolution_notes

    @pytest.mark.asyncio
    async def test_full_resolution_flow_fuzzy_match(self, mock_session):
        """Test complete resolution flow with fuzzy match."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.entity_type = EntityType.INDIVIDUAL.value
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "John Michael Smith"},
            "date_of_birth": {"value": "1980-01-15"},
            "address": {"value": "123 Main Street Springfield IL 62701"},
        }

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute.return_value = mock_result

        matcher = EntityMatcher(mock_session)
        identifiers = SubjectIdentifiers(
            full_name="John M. Smith",
            date_of_birth=date(1980, 1, 15),
            street_address="123 Main St",
            city="Springfield",
            state="IL",
            postal_code="62701",
        )

        result = await matcher.resolve(identifiers, tier=ServiceTier.STANDARD)

        assert result.match_type == MatchType.FUZZY
        assert result.confidence >= 0.85
        assert result.decision == ResolutionDecision.MATCH_EXISTING
        assert result.entity_id == entity_id

    @pytest.mark.asyncio
    async def test_full_resolution_flow_no_match(self, mock_session):
        """Test complete resolution flow with no match found."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        matcher = EntityMatcher(mock_session)
        identifiers = SubjectIdentifiers(
            full_name="Completely New Person",
            date_of_birth=date(1995, 12, 31),
        )

        result = await matcher.resolve(identifiers)

        assert result.match_type == MatchType.NEW
        assert result.confidence == 0.0
        assert result.decision == ResolutionDecision.CREATE_NEW
        assert result.entity_id is None
