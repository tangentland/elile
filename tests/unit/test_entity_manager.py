"""Unit tests for Canonical Entity Management.

Tests the EntityManager, IdentifierManager, and RelationshipGraph classes.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid7

import pytest

from elile.db.models.entity import Entity, EntityRelation, EntityType
from elile.entity import (
    EntityCreateResult,
    EntityManager,
    IdentifierManager,
    IdentifierRecord,
    IdentifierType,
    IdentifierUpdate,
    PathSegment,
    RelationshipEdge,
    RelationshipGraph,
    RelationshipPath,
    RelationType,
    SubjectIdentifiers,
)


# =============================================================================
# IdentifierManager Tests
# =============================================================================


class TestIdentifierManager:
    """Tests for IdentifierManager class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def identifier_manager(self, mock_session):
        """Create an IdentifierManager instance."""
        return IdentifierManager(mock_session)

    def test_init(self, mock_session):
        """Test IdentifierManager initialization."""
        manager = IdentifierManager(mock_session)
        assert manager._session is mock_session

    @pytest.mark.asyncio
    async def test_add_identifier_entity_not_found(self, mock_session, identifier_manager):
        """Test add_identifier when entity doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await identifier_manager.add_identifier(
            entity_id=uuid7(),
            identifier_type=IdentifierType.SSN,
            value="123-45-6789",
            source="test",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_add_identifier_new(self, mock_session, identifier_manager):
        """Test adding a new identifier."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await identifier_manager.add_identifier(
            entity_id=entity_id,
            identifier_type=IdentifierType.SSN,
            value="123-45-6789",
            confidence=0.95,
            source="credit_bureau",
        )

        assert result is True
        assert "ssn" in mock_entity.canonical_identifiers
        assert mock_entity.canonical_identifiers["ssn"]["value"] == "123-45-6789"
        assert mock_entity.canonical_identifiers["ssn"]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_add_identifier_higher_confidence(self, mock_session, identifier_manager):
        """Test updating identifier with higher confidence."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {
            "ssn": {
                "value": "123-45-6789",
                "confidence": 0.8,
                "discovered_at": datetime.utcnow().isoformat(),
                "source": "old_source",
            }
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await identifier_manager.add_identifier(
            entity_id=entity_id,
            identifier_type=IdentifierType.SSN,
            value="123-45-6789",
            confidence=0.95,  # Higher confidence
            source="better_source",
        )

        assert result is True
        assert mock_entity.canonical_identifiers["ssn"]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_get_identifiers(self, mock_session, identifier_manager):
        """Test getting all identifiers for an entity."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {
            "ssn": {
                "value": "123-45-6789",
                "confidence": 1.0,
                "discovered_at": datetime.utcnow().isoformat(),
                "source": "test",
            },
            "email": {
                "value": "john@example.com",
                "confidence": 0.9,
                "discovered_at": datetime.utcnow().isoformat(),
                "source": "test",
            },
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await identifier_manager.get_identifiers(entity_id)

        assert len(result) == 2
        assert IdentifierType.SSN in result
        assert IdentifierType.EMAIL in result
        assert result[IdentifierType.SSN].value == "123-45-6789"

    @pytest.mark.asyncio
    async def test_get_identifier(self, mock_session, identifier_manager):
        """Test getting a specific identifier."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {
            "ssn": {
                "value": "123-45-6789",
                "confidence": 1.0,
                "discovered_at": datetime.utcnow().isoformat(),
                "source": "test",
            },
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await identifier_manager.get_identifier(entity_id, IdentifierType.SSN)

        assert result is not None
        assert result.value == "123-45-6789"
        assert result.identifier_type == IdentifierType.SSN

    @pytest.mark.asyncio
    async def test_has_identifier(self, mock_session, identifier_manager):
        """Test checking if entity has an identifier."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.canonical_identifiers = {"ssn": {"value": "123"}}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        assert await identifier_manager.has_identifier(entity_id, IdentifierType.SSN) is True
        assert await identifier_manager.has_identifier(entity_id, IdentifierType.EIN) is False


# =============================================================================
# RelationshipGraph Tests
# =============================================================================


class TestRelationshipGraph:
    """Tests for RelationshipGraph class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def graph(self, mock_session):
        """Create a RelationshipGraph instance."""
        return RelationshipGraph(mock_session)

    def test_init(self, mock_session):
        """Test RelationshipGraph initialization."""
        graph = RelationshipGraph(mock_session)
        assert graph._session is mock_session

    @pytest.mark.asyncio
    async def test_add_edge_new(self, mock_session, graph):
        """Test adding a new relationship edge."""
        from_id = uuid7()
        to_id = uuid7()

        # Mock no existing relation
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        edge = await graph.add_edge(
            from_entity_id=from_id,
            to_entity_id=to_id,
            relation_type=RelationType.EMPLOYER,
            confidence=0.95,
        )

        assert edge.from_entity_id == from_id
        assert edge.to_entity_id == to_id
        assert edge.relation_type == RelationType.EMPLOYER
        assert edge.confidence == 0.95
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_edge_existing_higher_confidence(self, mock_session, graph):
        """Test updating existing edge with higher confidence."""
        from_id = uuid7()
        to_id = uuid7()
        relation_id = uuid7()

        mock_relation = MagicMock(spec=EntityRelation)
        mock_relation.relation_id = relation_id
        mock_relation.from_entity_id = from_id
        mock_relation.to_entity_id = to_id
        mock_relation.relation_type = RelationType.EMPLOYER.value
        mock_relation.confidence_score = 0.8
        mock_relation.metadata = {}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_relation
        mock_session.execute.return_value = mock_result

        edge = await graph.add_edge(
            from_entity_id=from_id,
            to_entity_id=to_id,
            relation_type=RelationType.EMPLOYER,
            confidence=0.95,  # Higher
        )

        assert edge.relation_id == relation_id
        assert mock_relation.confidence_score == 0.95  # Updated

    @pytest.mark.asyncio
    async def test_get_edges_outbound(self, mock_session, graph):
        """Test getting outbound edges."""
        entity_id = uuid7()
        target_id = uuid7()

        mock_relation = MagicMock(spec=EntityRelation)
        mock_relation.relation_id = uuid7()
        mock_relation.from_entity_id = entity_id
        mock_relation.to_entity_id = target_id
        mock_relation.relation_type = RelationType.EMPLOYER.value
        mock_relation.confidence_score = 0.9
        mock_relation.metadata = {}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_relation]
        mock_session.execute.return_value = mock_result

        edges = await graph.get_edges(entity_id, direction="outbound")

        assert len(edges) == 1
        assert edges[0].from_entity_id == entity_id
        assert edges[0].relation_type == RelationType.EMPLOYER

    @pytest.mark.asyncio
    async def test_get_neighbors_depth_1(self, mock_session, graph):
        """Test getting neighbors at depth 1."""
        entity_id = uuid7()
        neighbor_id = uuid7()

        mock_relation = MagicMock(spec=EntityRelation)
        mock_relation.relation_id = uuid7()
        mock_relation.from_entity_id = entity_id
        mock_relation.to_entity_id = neighbor_id
        mock_relation.relation_type = RelationType.COLLEAGUE.value
        mock_relation.confidence_score = 0.9
        mock_relation.metadata = {}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_relation]
        mock_session.execute.return_value = mock_result

        neighbors = await graph.get_neighbors(entity_id, depth=1)

        assert neighbor_id in neighbors
        assert neighbors[neighbor_id] == 1  # Distance 1

    @pytest.mark.asyncio
    async def test_get_path_same_entity(self, mock_session, graph):
        """Test path finding when start == end."""
        entity_id = uuid7()

        path = await graph.get_path(entity_id, entity_id)

        assert path.exists is False  # Length 0 means no traversal needed
        assert path.start_entity_id == entity_id
        assert path.end_entity_id == entity_id
        assert path.length == 0

    @pytest.mark.asyncio
    async def test_get_path_direct_connection(self, mock_session, graph):
        """Test path finding with direct connection."""
        from_id = uuid7()
        to_id = uuid7()

        mock_relation = MagicMock(spec=EntityRelation)
        mock_relation.relation_id = uuid7()
        mock_relation.from_entity_id = from_id
        mock_relation.to_entity_id = to_id
        mock_relation.relation_type = RelationType.EMPLOYER.value
        mock_relation.confidence_score = 0.9
        mock_relation.metadata = {}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_relation]
        mock_session.execute.return_value = mock_result

        path = await graph.get_path(from_id, to_id)

        assert path.exists is True
        assert path.length == 1
        assert path.start_entity_id == from_id
        assert path.end_entity_id == to_id

    @pytest.mark.asyncio
    async def test_get_path_no_connection(self, mock_session, graph):
        """Test path finding with no connection."""
        from_id = uuid7()
        to_id = uuid7()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        path = await graph.get_path(from_id, to_id)

        assert path.exists is False
        assert path.length == 0

    def test_to_adjacency_dict(self, graph):
        """Test converting edges to adjacency dictionary."""
        id1 = uuid7()
        id2 = uuid7()
        id3 = uuid7()

        edges = [
            RelationshipEdge(
                relation_id=uuid7(),
                from_entity_id=id1,
                to_entity_id=id2,
                relation_type=RelationType.EMPLOYER,
                confidence=0.9,
            ),
            RelationshipEdge(
                relation_id=uuid7(),
                from_entity_id=id2,
                to_entity_id=id3,
                relation_type=RelationType.COLLEAGUE,
                confidence=0.8,
            ),
        ]

        adj = graph.to_adjacency_dict(edges)

        assert id1 in adj
        assert id2 in adj
        assert id3 in adj
        assert len(adj[id1]) == 1  # Only one edge from id1
        assert len(adj[id2]) == 2  # Two edges touch id2


# =============================================================================
# RelationshipEdge and Path Tests
# =============================================================================


class TestRelationshipModels:
    """Tests for relationship models."""

    def test_relationship_edge_creation(self):
        """Test creating a relationship edge."""
        edge = RelationshipEdge(
            relation_id=uuid7(),
            from_entity_id=uuid7(),
            to_entity_id=uuid7(),
            relation_type=RelationType.EMPLOYER,
            confidence=0.95,
            metadata={"source": "hr_records"},
        )

        assert edge.relation_type == RelationType.EMPLOYER
        assert edge.confidence == 0.95
        assert edge.metadata["source"] == "hr_records"

    def test_path_segment_creation(self):
        """Test creating a path segment."""
        segment = PathSegment(
            entity_id=uuid7(),
            relation_type=RelationType.COLLEAGUE,
            direction="outbound",
        )

        assert segment.relation_type == RelationType.COLLEAGUE
        assert segment.direction == "outbound"

    def test_relationship_path_exists(self):
        """Test relationship path existence check."""
        path_exists = RelationshipPath(
            start_entity_id=uuid7(),
            end_entity_id=uuid7(),
            segments=[PathSegment(entity_id=uuid7())],
            length=1,
        )
        assert path_exists.exists is True

        path_not_exists = RelationshipPath(
            start_entity_id=uuid7(),
            end_entity_id=uuid7(),
            segments=[],
            length=0,
        )
        assert path_not_exists.exists is False


# =============================================================================
# EntityManager Tests
# =============================================================================


class TestEntityManager:
    """Tests for EntityManager class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_audit(self):
        """Create a mock audit logger."""
        return AsyncMock()

    @pytest.fixture
    def manager(self, mock_session, mock_audit):
        """Create an EntityManager instance."""
        return EntityManager(mock_session, mock_audit)

    def test_init(self, mock_session, mock_audit):
        """Test EntityManager initialization."""
        manager = EntityManager(mock_session, mock_audit)
        assert manager._session is mock_session
        assert manager._audit is mock_audit
        assert manager._matcher is not None
        assert manager._dedup is not None
        assert manager._identifiers is not None
        assert manager._graph is not None

    @pytest.mark.asyncio
    async def test_create_entity_new(self, mock_session, mock_audit, manager):
        """Test creating a new entity."""
        # Mock dedup check returns no duplicate
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="123-45-6789",
        )

        result = await manager.create_entity(EntityType.INDIVIDUAL, identifiers)

        assert result.created is True
        assert result.entity_id is not None
        mock_session.add.assert_called_once()
        mock_audit.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_entity_existing_duplicate(self, mock_session, mock_audit, manager):
        """Test create_entity returns existing when duplicate found."""
        existing_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = existing_id
        mock_entity.entity_type = EntityType.INDIVIDUAL.value
        mock_entity.canonical_identifiers = {"ssn": {"value": "123456789"}}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="123-45-6789",
        )

        result = await manager.create_entity(EntityType.INDIVIDUAL, identifiers)

        assert result.created is False
        assert result.entity_id == existing_id

    @pytest.mark.asyncio
    async def test_create_entity_allow_duplicate(self, mock_session, mock_audit, manager):
        """Test create_entity with allow_duplicate=True."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        identifiers = SubjectIdentifiers(
            full_name="John Smith",
        )

        result = await manager.create_entity(
            EntityType.INDIVIDUAL, identifiers, allow_duplicate=True
        )

        assert result.created is True

    @pytest.mark.asyncio
    async def test_get_entity(self, mock_session, manager):
        """Test getting an entity by ID."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await manager.get_entity(entity_id)

        assert result is mock_entity

    @pytest.mark.asyncio
    async def test_add_identifier_via_manager(self, mock_session, manager):
        """Test adding identifier through manager."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.canonical_identifiers = {}
        mock_entity.entity_type = EntityType.INDIVIDUAL.value

        # First call for identifier manager, rest for dedup
        call_count = [0]

        async def mock_execute(stmt):
            result = MagicMock()
            if call_count[0] == 0:
                result.scalar_one_or_none.return_value = mock_entity
            else:
                result.scalar_one_or_none.return_value = mock_entity
                result.scalars.return_value.all.return_value = []
            call_count[0] += 1
            return result

        mock_session.execute = mock_execute

        result = await manager.add_identifier(
            entity_id=entity_id,
            identifier_type=IdentifierType.EMAIL,
            value="john@example.com",
            source="user_input",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_add_relation_via_manager(self, mock_session, mock_audit, manager):
        """Test adding relation through manager."""
        from_id = uuid7()
        to_id = uuid7()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        edge = await manager.add_relation(
            from_entity_id=from_id,
            to_entity_id=to_id,
            relation_type=RelationType.EMPLOYER,
        )

        assert edge.from_entity_id == from_id
        assert edge.to_entity_id == to_id
        mock_audit.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_neighbors_via_manager(self, mock_session, manager):
        """Test getting neighbors through manager."""
        entity_id = uuid7()
        neighbor_id = uuid7()

        mock_relation = MagicMock(spec=EntityRelation)
        mock_relation.relation_id = uuid7()
        mock_relation.from_entity_id = entity_id
        mock_relation.to_entity_id = neighbor_id
        mock_relation.relation_type = RelationType.COLLEAGUE.value
        mock_relation.confidence_score = 0.9
        mock_relation.metadata = {}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_relation]
        mock_session.execute.return_value = mock_result

        neighbors = await manager.get_neighbors(entity_id, depth=1)

        assert neighbor_id in neighbors

    def test_build_canonical_identifiers(self, manager):
        """Test building canonical identifiers from SubjectIdentifiers."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date(1980, 1, 15),
            ssn="123-45-6789",
            email="john@example.com",
            street_address="123 Main St",
            city="Springfield",
            state="IL",
            postal_code="62701",
        )

        result = manager._build_canonical_identifiers(identifiers)

        assert "full_name" in result
        assert result["full_name"]["value"] == "John Smith"
        assert "date_of_birth" in result
        assert result["date_of_birth"]["value"] == "1980-01-15"
        assert "ssn" in result
        assert "email" in result
        assert "address" in result
        assert "123 Main St" in result["address"]["value"]


# =============================================================================
# EntityCreateResult Tests
# =============================================================================


class TestEntityCreateResult:
    """Tests for EntityCreateResult model."""

    def test_create_result_new_entity(self):
        """Test result for newly created entity."""
        result = EntityCreateResult(
            entity_id=uuid7(),
            created=True,
        )
        assert result.created is True
        assert result.match_result is None

    def test_create_result_existing_entity(self):
        """Test result for existing entity match."""
        result = EntityCreateResult(
            entity_id=uuid7(),
            created=False,
        )
        assert result.created is False
