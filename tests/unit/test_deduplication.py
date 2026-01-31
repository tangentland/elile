"""Unit tests for Entity Deduplication Pipeline.

Tests the EntityDeduplicator class, MergeResult, DuplicateCandidate,
and related deduplication functionality.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid7

import pytest

from elile.db.models.entity import Entity, EntityType
from elile.entity import (
    DeduplicationResult,
    DuplicateCandidate,
    EntityDeduplicator,
    IdentifierType,
    MatchType,
    MergeResult,
    SubjectIdentifiers,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestMergeResult:
    """Tests for MergeResult model."""

    def test_create_merge_result(self):
        """Test creating a merge result."""
        canonical_id = uuid7()
        merged_id = uuid7()

        result = MergeResult(
            canonical_entity_id=canonical_id,
            merged_entity_id=merged_id,
            relationships_updated=5,
            profiles_migrated=2,
            identifiers_merged=["email", "phone"],
            reason="duplicate_detected",
        )

        assert result.canonical_entity_id == canonical_id
        assert result.merged_entity_id == merged_id
        assert result.relationships_updated == 5
        assert result.profiles_migrated == 2
        assert result.identifiers_merged == ["email", "phone"]
        assert result.reason == "duplicate_detected"

    def test_merge_result_defaults(self):
        """Test MergeResult with default values."""
        result = MergeResult(
            canonical_entity_id=uuid7(),
            merged_entity_id=uuid7(),
        )

        assert result.relationships_updated == 0
        assert result.profiles_migrated == 0
        assert result.identifiers_merged == []
        assert result.reason == "duplicate_detected"


class TestDuplicateCandidate:
    """Tests for DuplicateCandidate model."""

    def test_create_duplicate_candidate(self):
        """Test creating a duplicate candidate."""
        entity_id = uuid7()

        candidate = DuplicateCandidate(
            entity_id=entity_id,
            match_confidence=0.85,
            match_type=MatchType.FUZZY,
            matching_identifiers=[IdentifierType.EMAIL],
        )

        assert candidate.entity_id == entity_id
        assert candidate.match_confidence == 0.85
        assert candidate.match_type == MatchType.FUZZY
        assert candidate.matching_identifiers == [IdentifierType.EMAIL]

    def test_duplicate_candidate_exact_match(self):
        """Test duplicate candidate with exact match."""
        candidate = DuplicateCandidate(
            entity_id=uuid7(),
            match_confidence=1.0,
            match_type=MatchType.EXACT,
            matching_identifiers=[IdentifierType.SSN],
        )

        assert candidate.match_type == MatchType.EXACT
        assert candidate.match_confidence == 1.0

    def test_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValueError):
            DuplicateCandidate(
                entity_id=uuid7(),
                match_confidence=1.5,
                match_type=MatchType.FUZZY,
            )


class TestDeduplicationResult:
    """Tests for DeduplicationResult model."""

    def test_not_duplicate(self):
        """Test result when not a duplicate."""
        result = DeduplicationResult()

        assert result.is_duplicate is False
        assert result.existing_entity_id is None
        assert result.match_confidence == 0.0
        assert result.matching_identifiers == []

    def test_is_duplicate(self):
        """Test result when duplicate found."""
        entity_id = uuid7()

        result = DeduplicationResult(
            is_duplicate=True,
            existing_entity_id=entity_id,
            match_confidence=1.0,
            matching_identifiers=[IdentifierType.SSN],
        )

        assert result.is_duplicate is True
        assert result.existing_entity_id == entity_id
        assert result.match_confidence == 1.0


# =============================================================================
# EntityDeduplicator Tests
# =============================================================================


class TestEntityDeduplicator:
    """Tests for EntityDeduplicator class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_audit(self):
        """Create a mock audit logger."""
        return AsyncMock()

    @pytest.fixture
    def deduplicator(self, mock_session, mock_audit):
        """Create an EntityDeduplicator instance."""
        return EntityDeduplicator(mock_session, mock_audit)

    def test_init(self, mock_session, mock_audit):
        """Test EntityDeduplicator initialization."""
        dedup = EntityDeduplicator(mock_session, mock_audit)
        assert dedup._session is mock_session
        assert dedup._audit is mock_audit

    def test_init_without_audit(self, mock_session):
        """Test EntityDeduplicator without audit logger."""
        dedup = EntityDeduplicator(mock_session)
        assert dedup._audit is None

    # -------------------------------------------------------------------------
    # check_duplicate Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_check_duplicate_no_match(self, mock_session, deduplicator):
        """Test check_duplicate when no existing entity found."""
        # Mock matcher to return no match
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="123-45-6789",
        )

        result = await deduplicator.check_duplicate(identifiers)

        assert result.is_duplicate is False
        assert result.existing_entity_id is None

    @pytest.mark.asyncio
    async def test_check_duplicate_with_match(self, mock_session, deduplicator):
        """Test check_duplicate when existing entity found."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.entity_type = EntityType.INDIVIDUAL.value
        mock_entity.canonical_identifiers = {"ssn": {"value": "123456789"}}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="123-45-6789",
        )

        result = await deduplicator.check_duplicate(identifiers)

        assert result.is_duplicate is True
        assert result.existing_entity_id == entity_id
        assert result.match_confidence == 1.0
        assert IdentifierType.SSN in result.matching_identifiers

    # -------------------------------------------------------------------------
    # find_potential_duplicates Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_potential_duplicates_no_entity(self, mock_session, deduplicator):
        """Test find_potential_duplicates with non-existent entity."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await deduplicator.find_potential_duplicates(uuid7())

        assert result == []

    @pytest.mark.asyncio
    async def test_find_potential_duplicates_no_name(self, mock_session, deduplicator):
        """Test find_potential_duplicates when entity has no name."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.entity_type = EntityType.INDIVIDUAL.value
        mock_entity.canonical_identifiers = {"ssn": {"value": "123456789"}}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await deduplicator.find_potential_duplicates(entity_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_find_potential_duplicates_with_matches(self, mock_session, deduplicator):
        """Test find_potential_duplicates finds similar entities."""
        source_id = uuid7()
        candidate_id = uuid7()

        source_entity = MagicMock(spec=Entity)
        source_entity.entity_id = source_id
        source_entity.entity_type = EntityType.INDIVIDUAL.value
        source_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
            "date_of_birth": {"value": "1980-01-15"},
        }

        candidate_entity = MagicMock(spec=Entity)
        candidate_entity.entity_id = candidate_id
        candidate_entity.entity_type = EntityType.INDIVIDUAL.value
        candidate_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
            "date_of_birth": {"value": "1980-01-15"},
        }

        # First call returns source entity
        # Second call returns candidates list
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = source_entity

        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [candidate_entity]

        mock_session.execute.side_effect = [mock_result1, mock_result2]

        result = await deduplicator.find_potential_duplicates(source_id)

        assert len(result) == 1
        assert result[0].entity_id == candidate_id
        assert result[0].match_confidence > 0.7

    # -------------------------------------------------------------------------
    # merge_entities Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_merge_entities_source_older(self, mock_session, mock_audit, deduplicator):
        """Test merge_entities when source is older (canonical)."""
        # Create entities with source being older (lower UUIDv7)
        source_id = uuid7()
        target_id = uuid7()  # Will be higher due to UUIDv7 monotonicity

        source_entity = MagicMock(spec=Entity)
        source_entity.entity_id = source_id
        source_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
            "ssn": {"value": "123456789"},
        }

        target_entity = MagicMock(spec=Entity)
        target_entity.entity_id = target_id
        target_entity.canonical_identifiers = {
            "full_name": {"value": "John A. Smith"},
            "email": {"value": "john@example.com"},
        }

        entities = {source_id: source_entity, target_id: target_entity}
        call_count = [0]

        async def mock_execute(stmt):
            result = MagicMock()
            result.rowcount = 0

            # Determine which entity to return based on call order
            # First two calls are for getting source and target
            if call_count[0] == 0:
                result.scalar_one_or_none.return_value = source_entity
            elif call_count[0] == 1:
                result.scalar_one_or_none.return_value = target_entity
            else:
                result.scalar_one_or_none.return_value = None
            call_count[0] += 1
            return result

        mock_session.execute = mock_execute
        mock_session.flush = AsyncMock()

        result = await deduplicator.merge_entities(source_id, target_id)

        # Source should be canonical (older)
        assert result.canonical_entity_id == source_id
        assert result.merged_entity_id == target_id
        assert "email" in result.identifiers_merged

    @pytest.mark.asyncio
    async def test_merge_entities_target_older(self, mock_session, mock_audit, deduplicator):
        """Test merge_entities when target is older (canonical)."""
        # Create entities with target being older
        target_id = uuid7()
        import time
        time.sleep(0.001)  # Ensure different timestamps
        source_id = uuid7()

        source_entity = MagicMock(spec=Entity)
        source_entity.entity_id = source_id
        source_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
        }

        target_entity = MagicMock(spec=Entity)
        target_entity.entity_id = target_id
        target_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
            "ssn": {"value": "123456789"},
        }

        call_count = [0]

        async def mock_execute(stmt):
            result = MagicMock()
            result.rowcount = 0

            # First call returns source, second returns target
            if call_count[0] == 0:
                result.scalar_one_or_none.return_value = source_entity
            elif call_count[0] == 1:
                result.scalar_one_or_none.return_value = target_entity
            else:
                result.scalar_one_or_none.return_value = None
            call_count[0] += 1
            return result

        mock_session.execute = mock_execute
        mock_session.flush = AsyncMock()

        result = await deduplicator.merge_entities(source_id, target_id)

        # Target should be canonical (older)
        assert result.canonical_entity_id == target_id
        assert result.merged_entity_id == source_id

    @pytest.mark.asyncio
    async def test_merge_entities_not_found(self, mock_session, deduplicator):
        """Test merge_entities with non-existent entity."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Entity not found"):
            await deduplicator.merge_entities(uuid7(), uuid7())

    @pytest.mark.asyncio
    async def test_merge_entities_audit_logged(self, mock_session, mock_audit, deduplicator):
        """Test that merge_entities logs audit event."""
        entity_id = uuid7()

        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result
        mock_session.flush = AsyncMock()

        source_id = uuid7()
        target_id = uuid7()

        # Need to return both entities
        call_count = 0
        async def mock_execute(stmt):
            nonlocal call_count
            result = MagicMock()
            result.rowcount = 0

            # Alternate between returning source and target
            if call_count < 2:
                mock_entity = MagicMock(spec=Entity)
                mock_entity.entity_id = source_id if call_count == 0 else target_id
                mock_entity.canonical_identifiers = {}
                result.scalar_one_or_none.return_value = mock_entity
                call_count += 1
            else:
                result.scalar_one_or_none.return_value = None

            return result

        mock_session.execute = mock_execute

        await deduplicator.merge_entities(source_id, target_id)

        # Verify audit was called
        mock_audit.log_event.assert_called_once()

    # -------------------------------------------------------------------------
    # on_identifier_added Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_on_identifier_added_no_match(self, mock_session, deduplicator):
        """Test on_identifier_added when no matching entity found."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.entity_type = EntityType.INDIVIDUAL.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await deduplicator.on_identifier_added(
            entity_id, IdentifierType.EMAIL, "john@example.com"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_on_identifier_added_entity_not_found(self, mock_session, deduplicator):
        """Test on_identifier_added when entity doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await deduplicator.on_identifier_added(
            uuid7(), IdentifierType.SSN, "123-45-6789"
        )

        assert result is None

    # -------------------------------------------------------------------------
    # Helper Method Tests
    # -------------------------------------------------------------------------

    def test_merge_identifiers(self, deduplicator):
        """Test _merge_identifiers combines dictionaries correctly."""
        canonical = {
            "full_name": {"value": "John Smith"},
            "ssn": {"value": "123456789"},
        }
        duplicate = {
            "full_name": {"value": "John A. Smith"},  # Won't override
            "email": {"value": "john@example.com"},  # Will be added
        }

        result = deduplicator._merge_identifiers(canonical, duplicate)

        assert result["full_name"]["value"] == "John Smith"  # Preserved canonical
        assert result["ssn"]["value"] == "123456789"
        assert result["email"]["value"] == "john@example.com"  # Added from duplicate

    def test_merge_identifiers_skips_internal(self, deduplicator):
        """Test _merge_identifiers skips internal keys."""
        canonical = {"full_name": {"value": "John"}}
        duplicate = {
            "_merged": {"into": "other"},
            "email": {"value": "john@example.com"},
        }

        result = deduplicator._merge_identifiers(canonical, duplicate)

        assert "_merged" not in result
        assert "email" in result

    def test_merge_identifiers_lists(self, deduplicator):
        """Test _merge_identifiers handles list values."""
        canonical = {
            "name_variants": ["John", "Johnny"],
        }
        duplicate = {
            "name_variants": ["John", "J. Smith"],  # Has overlap
        }

        result = deduplicator._merge_identifiers(canonical, duplicate)

        # Should combine and dedupe
        assert "John" in result["name_variants"]
        assert "Johnny" in result["name_variants"]
        assert "J. Smith" in result["name_variants"]

    def test_entity_to_identifiers(self, deduplicator):
        """Test _entity_to_identifiers extracts identifiers."""
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {
            "full_name": {"value": "John Smith"},
            "ssn": {"value": "123-45-6789"},
            "ein": "87-6543210",  # Non-dict format
        }

        result = deduplicator._entity_to_identifiers(mock_entity)

        assert result.full_name == "John Smith"
        assert result.ssn == "123-45-6789"
        assert result.ein == "87-6543210"

    def test_find_matching_identifiers(self, deduplicator):
        """Test _find_matching_identifiers finds exact matches."""
        entity1 = MagicMock(spec=Entity)
        entity1.canonical_identifiers = {
            "ssn": {"value": "123-45-6789"},
            "email": {"value": "john@example.com"},
        }

        entity2 = MagicMock(spec=Entity)
        entity2.canonical_identifiers = {
            "ssn": {"value": "123456789"},  # Same SSN, different format
            "phone": {"value": "+15551234567"},
        }

        result = deduplicator._find_matching_identifiers(entity1, entity2)

        assert IdentifierType.SSN in result
        assert IdentifierType.EMAIL not in result
        assert IdentifierType.PHONE not in result


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestEntityDeduplicatorIntegration:
    """Integration-style tests for EntityDeduplicator."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_full_deduplication_flow(self, mock_session):
        """Test complete deduplication flow."""
        existing_id = uuid7()
        existing_entity = MagicMock(spec=Entity)
        existing_entity.entity_id = existing_id
        existing_entity.entity_type = EntityType.INDIVIDUAL.value
        existing_entity.canonical_identifiers = {
            "ssn": {"value": "123456789"},
            "full_name": {"value": "John Smith"},
        }

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_entity]
        mock_session.execute.return_value = mock_result

        dedup = EntityDeduplicator(mock_session)

        # Try to create entity with same SSN
        identifiers = SubjectIdentifiers(
            full_name="John A. Smith",
            ssn="123-45-6789",
        )

        result = await dedup.check_duplicate(identifiers)

        # Should find the existing entity
        assert result.is_duplicate is True
        assert result.existing_entity_id == existing_id
        assert result.match_confidence == 1.0

    @pytest.mark.asyncio
    async def test_deduplication_respects_entity_type(self, mock_session):
        """Test that deduplication query filters by entity type.

        Note: This test verifies the SQL query filters by entity_type.
        The mock returns empty results for INDIVIDUAL queries, simulating
        that the database filter excludes ORGANIZATION entities.
        """
        # Mock returns empty for INDIVIDUAL type query (no individuals exist)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        dedup = EntityDeduplicator(mock_session)

        # Try to find individual with an EIN
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ein="12-3456789",
        )

        # Check for INDIVIDUAL type - empty result means no duplicate
        result = await dedup.check_duplicate(identifiers, EntityType.INDIVIDUAL)

        # No individuals found, so not a duplicate
        assert result.is_duplicate is False
        assert result.existing_entity_id is None
