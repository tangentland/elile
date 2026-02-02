"""Unit tests for cross-screening index type definitions."""

from datetime import datetime, UTC
from uuid import uuid7

import pytest

from elile.screening.index.types import (
    ConnectionStrength,
    ConnectionType,
    CrossScreeningIndexError,
    CrossScreeningResult,
    EntityReference,
    IndexingError,
    NetworkEdge,
    NetworkGraph,
    NetworkNode,
    ScreeningEntity,
    ScreeningNotIndexedError,
    SubjectConnection,
    SubjectNotFoundError,
)
from elile.entity.types import RelationType


class TestConnectionType:
    """Tests for ConnectionType enum."""

    def test_connection_type_values(self):
        """Test all connection type values exist."""
        assert ConnectionType.EMPLOYER.value == "employer"
        assert ConnectionType.COLLEAGUE.value == "colleague"
        assert ConnectionType.BUSINESS_PARTNER.value == "business_partner"
        assert ConnectionType.DIRECTOR.value == "director"
        assert ConnectionType.ADDRESS.value == "address"
        assert ConnectionType.FAMILY.value == "family"
        assert ConnectionType.ASSOCIATE.value == "associate"
        assert ConnectionType.SHARED_FINDING.value == "shared_finding"
        assert ConnectionType.SHARED_SOURCE.value == "shared_source"
        assert ConnectionType.NETWORK_NEIGHBOR.value == "network_neighbor"

    def test_connection_type_is_string_enum(self):
        """Test that ConnectionType is a string enum."""
        assert isinstance(ConnectionType.EMPLOYER, str)
        assert ConnectionType.EMPLOYER == "employer"


class TestConnectionStrength:
    """Tests for ConnectionStrength enum."""

    def test_strength_values(self):
        """Test all strength values exist."""
        assert ConnectionStrength.WEAK.value == "weak"
        assert ConnectionStrength.MODERATE.value == "moderate"
        assert ConnectionStrength.STRONG.value == "strong"
        assert ConnectionStrength.VERIFIED.value == "verified"


class TestSubjectConnection:
    """Tests for SubjectConnection model."""

    def test_create_basic_connection(self):
        """Test creating a basic connection."""
        source_id = uuid7()
        target_id = uuid7()
        now = datetime.now(UTC)

        connection = SubjectConnection(
            connection_id=uuid7(),
            source_subject_id=source_id,
            target_subject_id=target_id,
            connection_type=ConnectionType.COLLEAGUE,
            discovered_at=now,
            last_seen_at=now,
        )

        assert connection.source_subject_id == source_id
        assert connection.target_subject_id == target_id
        assert connection.connection_type == ConnectionType.COLLEAGUE
        assert connection.strength == ConnectionStrength.MODERATE
        assert connection.confidence_score == 0.5
        assert connection.degree == 1

    def test_connection_with_all_fields(self):
        """Test connection with all fields populated."""
        screening_id = uuid7()
        now = datetime.now(UTC)

        connection = SubjectConnection(
            connection_id=uuid7(),
            source_subject_id=uuid7(),
            target_subject_id=uuid7(),
            connection_type=ConnectionType.EMPLOYER,
            strength=ConnectionStrength.VERIFIED,
            confidence_score=0.95,
            degree=1,
            discovered_at=now,
            last_seen_at=now,
            screening_ids=[screening_id],
            evidence=["Employment records", "Payroll data"],
            metadata={"position": "Manager"},
        )

        assert connection.strength == ConnectionStrength.VERIFIED
        assert connection.confidence_score == 0.95
        assert len(connection.screening_ids) == 1
        assert len(connection.evidence) == 2
        assert connection.metadata["position"] == "Manager"

    def test_is_direct_property(self):
        """Test is_direct property."""
        now = datetime.now(UTC)

        direct = SubjectConnection(
            connection_id=uuid7(),
            source_subject_id=uuid7(),
            target_subject_id=uuid7(),
            connection_type=ConnectionType.COLLEAGUE,
            degree=1,
            discovered_at=now,
            last_seen_at=now,
        )
        assert direct.is_direct is True

        indirect = SubjectConnection(
            connection_id=uuid7(),
            source_subject_id=uuid7(),
            target_subject_id=uuid7(),
            connection_type=ConnectionType.NETWORK_NEIGHBOR,
            degree=2,
            discovered_at=now,
            last_seen_at=now,
        )
        assert indirect.is_direct is False

    def test_to_relation_type(self):
        """Test conversion to RelationType."""
        now = datetime.now(UTC)

        connection = SubjectConnection(
            connection_id=uuid7(),
            source_subject_id=uuid7(),
            target_subject_id=uuid7(),
            connection_type=ConnectionType.EMPLOYER,
            discovered_at=now,
            last_seen_at=now,
        )
        assert connection.to_relation_type() == RelationType.EMPLOYER

        # Shared finding has no RelationType equivalent
        connection2 = SubjectConnection(
            connection_id=uuid7(),
            source_subject_id=uuid7(),
            target_subject_id=uuid7(),
            connection_type=ConnectionType.SHARED_FINDING,
            discovered_at=now,
            last_seen_at=now,
        )
        assert connection2.to_relation_type() is None


class TestEntityReference:
    """Tests for EntityReference model."""

    def test_create_entity_reference(self):
        """Test creating an entity reference."""
        entity_id = uuid7()
        screening_id = uuid7()
        now = datetime.now(UTC)

        ref = EntityReference(
            entity_id=entity_id,
            entity_type="person",
            name="John Smith",
            screening_id=screening_id,
            discovered_at=now,
        )

        assert ref.entity_id == entity_id
        assert ref.entity_type == "person"
        assert ref.name == "John Smith"
        assert ref.confidence_score == 1.0

    def test_entity_with_identifiers(self):
        """Test entity with identifiers."""
        ref = EntityReference(
            entity_id=uuid7(),
            entity_type="person",
            name="Jane Doe",
            screening_id=uuid7(),
            discovered_at=datetime.now(UTC),
            identifiers={"ssn": "***-**-1234", "email": "jane@example.com"},
        )

        assert len(ref.identifiers) == 2
        assert "ssn" in ref.identifiers


class TestScreeningEntity:
    """Tests for ScreeningEntity model."""

    def test_create_screening_entity(self):
        """Test creating a screening entity."""
        entity = ScreeningEntity(
            screening_id=uuid7(),
            entity_id=uuid7(),
            subject_id=uuid7(),
            entity_type="organization",
            name="Acme Corp",
            role="employer",
        )

        assert entity.entity_type == "organization"
        assert entity.name == "Acme Corp"
        assert entity.role == "employer"
        assert entity.findings_count == 0

    def test_entity_with_connections(self):
        """Test entity with connections."""
        connected_ids = [uuid7() for _ in range(3)]

        entity = ScreeningEntity(
            screening_id=uuid7(),
            entity_id=uuid7(),
            subject_id=uuid7(),
            entity_type="person",
            name="Bob Johnson",
            connections=connected_ids,
            findings_count=5,
        )

        assert len(entity.connections) == 3
        assert entity.findings_count == 5


class TestCrossScreeningResult:
    """Tests for CrossScreeningResult model."""

    def test_create_empty_result(self):
        """Test creating an empty result."""
        result = CrossScreeningResult(query_subject_id=uuid7())

        assert result.total_connections == 0
        assert result.direct_connections == 0
        assert result.max_degree == 0
        assert len(result.connections) == 0

    def test_result_with_connections(self):
        """Test result with connections."""
        now = datetime.now(UTC)
        connections = [
            SubjectConnection(
                connection_id=uuid7(),
                source_subject_id=uuid7(),
                target_subject_id=uuid7(),
                connection_type=ConnectionType.COLLEAGUE,
                degree=1,
                discovered_at=now,
                last_seen_at=now,
            ),
            SubjectConnection(
                connection_id=uuid7(),
                source_subject_id=uuid7(),
                target_subject_id=uuid7(),
                connection_type=ConnectionType.NETWORK_NEIGHBOR,
                degree=2,
                discovered_at=now,
                last_seen_at=now,
            ),
        ]

        result = CrossScreeningResult(
            query_subject_id=uuid7(),
            connections=connections,
            total_connections=2,
            direct_connections=1,
            max_degree=2,
            query_time_ms=15.5,
        )

        assert result.total_connections == 2
        assert result.direct_connections == 1
        assert result.max_degree == 2
        assert result.query_time_ms == 15.5

    def test_get_by_degree(self):
        """Test filtering by degree."""
        now = datetime.now(UTC)
        connections = [
            SubjectConnection(
                connection_id=uuid7(),
                source_subject_id=uuid7(),
                target_subject_id=uuid7(),
                connection_type=ConnectionType.COLLEAGUE,
                degree=1,
                discovered_at=now,
                last_seen_at=now,
            ),
            SubjectConnection(
                connection_id=uuid7(),
                source_subject_id=uuid7(),
                target_subject_id=uuid7(),
                connection_type=ConnectionType.COLLEAGUE,
                degree=1,
                discovered_at=now,
                last_seen_at=now,
            ),
            SubjectConnection(
                connection_id=uuid7(),
                source_subject_id=uuid7(),
                target_subject_id=uuid7(),
                connection_type=ConnectionType.NETWORK_NEIGHBOR,
                degree=2,
                discovered_at=now,
                last_seen_at=now,
            ),
        ]

        result = CrossScreeningResult(
            query_subject_id=uuid7(),
            connections=connections,
        )

        assert len(result.get_by_degree(1)) == 2
        assert len(result.get_by_degree(2)) == 1
        assert len(result.get_by_degree(3)) == 0

    def test_get_by_type(self):
        """Test filtering by type."""
        now = datetime.now(UTC)
        connections = [
            SubjectConnection(
                connection_id=uuid7(),
                source_subject_id=uuid7(),
                target_subject_id=uuid7(),
                connection_type=ConnectionType.COLLEAGUE,
                discovered_at=now,
                last_seen_at=now,
            ),
            SubjectConnection(
                connection_id=uuid7(),
                source_subject_id=uuid7(),
                target_subject_id=uuid7(),
                connection_type=ConnectionType.EMPLOYER,
                discovered_at=now,
                last_seen_at=now,
            ),
        ]

        result = CrossScreeningResult(
            query_subject_id=uuid7(),
            connections=connections,
        )

        assert len(result.get_by_type(ConnectionType.COLLEAGUE)) == 1
        assert len(result.get_by_type(ConnectionType.EMPLOYER)) == 1
        assert len(result.get_by_type(ConnectionType.FAMILY)) == 0


class TestNetworkGraph:
    """Tests for NetworkGraph model."""

    def test_create_empty_graph(self):
        """Test creating an empty graph."""
        graph = NetworkGraph()

        assert graph.node_count == 0
        assert graph.edge_count == 0
        assert graph.center_subject_id is None

    def test_graph_with_nodes_and_edges(self):
        """Test graph with nodes and edges."""
        subject_a = uuid7()
        subject_b = uuid7()
        subject_c = uuid7()

        nodes = [
            NetworkNode(subject_id=subject_a, name="Subject A"),
            NetworkNode(subject_id=subject_b, name="Subject B"),
            NetworkNode(subject_id=subject_c, name="Subject C"),
        ]
        edges = [
            NetworkEdge(
                source_id=subject_a,
                target_id=subject_b,
                connection_type=ConnectionType.COLLEAGUE,
            ),
            NetworkEdge(
                source_id=subject_b,
                target_id=subject_c,
                connection_type=ConnectionType.EMPLOYER,
            ),
        ]

        graph = NetworkGraph(
            nodes=nodes,
            edges=edges,
            center_subject_id=subject_a,
            max_depth=2,
        )

        assert graph.node_count == 3
        assert graph.edge_count == 2
        assert graph.center_subject_id == subject_a
        assert graph.max_depth == 2

    def test_get_node(self):
        """Test getting a node by ID."""
        subject_id = uuid7()
        nodes = [NetworkNode(subject_id=subject_id, name="Test Subject")]

        graph = NetworkGraph(nodes=nodes)

        found = graph.get_node(subject_id)
        assert found is not None
        assert found.name == "Test Subject"

        not_found = graph.get_node(uuid7())
        assert not_found is None

    def test_get_neighbors(self):
        """Test getting neighbors."""
        subject_a = uuid7()
        subject_b = uuid7()
        subject_c = uuid7()

        edges = [
            NetworkEdge(
                source_id=subject_a,
                target_id=subject_b,
                connection_type=ConnectionType.COLLEAGUE,
            ),
            NetworkEdge(
                source_id=subject_a,
                target_id=subject_c,
                connection_type=ConnectionType.EMPLOYER,
            ),
        ]

        graph = NetworkGraph(edges=edges)

        neighbors = graph.get_neighbors(subject_a)
        assert len(neighbors) == 2
        assert subject_b in neighbors
        assert subject_c in neighbors

        # B is connected to A
        b_neighbors = graph.get_neighbors(subject_b)
        assert subject_a in b_neighbors


class TestExceptions:
    """Tests for cross-screening index exceptions."""

    def test_cross_screening_index_error(self):
        """Test CrossScreeningIndexError creation."""
        exc = CrossScreeningIndexError("Test error", details={"key": "value"})
        assert exc.message == "Test error"
        assert exc.details["key"] == "value"
        assert "Test error" in str(exc)

    def test_subject_not_found_error(self):
        """Test SubjectNotFoundError creation."""
        subject_id = uuid7()
        exc = SubjectNotFoundError(subject_id)

        assert exc.subject_id == subject_id
        assert str(subject_id) in str(exc)
        assert "not found" in str(exc).lower()

    def test_screening_not_indexed_error(self):
        """Test ScreeningNotIndexedError creation."""
        screening_id = uuid7()
        exc = ScreeningNotIndexedError(screening_id)

        assert exc.screening_id == screening_id
        assert str(screening_id) in str(exc)
        assert "not been indexed" in str(exc).lower()

    def test_indexing_error(self):
        """Test IndexingError creation."""
        screening_id = uuid7()
        reason = "Database connection failed"
        exc = IndexingError(screening_id, reason)

        assert exc.screening_id == screening_id
        assert exc.reason == reason
        assert str(screening_id) in str(exc)
        assert reason in str(exc)
