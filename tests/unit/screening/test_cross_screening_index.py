"""Unit tests for CrossScreeningIndex."""

from datetime import datetime, UTC
from uuid import uuid7

import pytest

from elile.screening.index import (
    ConnectionStrength,
    ConnectionType,
    CrossScreeningIndex,
    CrossScreeningResult,
    IndexConfig,
    IndexingError,
    ScreeningEntity,
    SubjectConnection,
    SubjectNotFoundError,
    create_index,
    get_cross_screening_index,
)


class TestIndexConfig:
    """Tests for IndexConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = IndexConfig()
        assert config.max_degree == 3
        assert config.min_confidence == 0.3
        assert config.decay_factor == 0.7
        assert config.max_connections_per_subject == 1000
        assert config.enable_temporal_tracking is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = IndexConfig(
            max_degree=5,
            min_confidence=0.5,
            decay_factor=0.8,
            max_connections_per_subject=500,
        )
        assert config.max_degree == 5
        assert config.min_confidence == 0.5
        assert config.decay_factor == 0.8
        assert config.max_connections_per_subject == 500


class TestCrossScreeningIndex:
    """Tests for CrossScreeningIndex class."""

    def test_create_index(self):
        """Test creating an index."""
        index = CrossScreeningIndex()
        assert index.config.max_degree == 3

    def test_create_index_with_config(self):
        """Test creating an index with custom config."""
        config = IndexConfig(max_degree=5)
        index = CrossScreeningIndex(config)
        assert index.config.max_degree == 5

    @pytest.mark.asyncio
    async def test_index_screening_connections_empty(self):
        """Test indexing with no entities."""
        index = create_index()
        screening_id = uuid7()
        subject_id = uuid7()

        count = await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=[],
        )

        assert count == 0
        stats = await index.get_statistics()
        assert stats.total_screenings == 1

    @pytest.mark.asyncio
    async def test_index_screening_connections_single_entity(self):
        """Test indexing with a single entity."""
        index = create_index()
        screening_id = uuid7()
        subject_id = uuid7()
        entity_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=entity_id,
                subject_id=subject_id,
                entity_type="person",
                name="John Smith",
                role="colleague",
            )
        ]

        count = await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=entities,
        )

        # 2 connections: subject->entity and entity->subject (bidirectional)
        assert count == 2

    @pytest.mark.asyncio
    async def test_index_screening_connections_multiple_entities(self):
        """Test indexing with multiple entities."""
        index = create_index()
        screening_id = uuid7()
        subject_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Alice Johnson",
                role="colleague",
            ),
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Bob Williams",
                role="employer",
            ),
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="organization",
                name="Acme Corp",
                role="employer",
            ),
        ]

        count = await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=entities,
        )

        # 2 person entities * 2 (bidirectional) = 4 connections
        # Organization entities don't create connections to people
        assert count == 4

    @pytest.mark.asyncio
    async def test_index_with_entity_connections(self):
        """Test indexing entities that have connections to other entities."""
        index = create_index()
        screening_id = uuid7()
        subject_id = uuid7()
        entity_a = uuid7()
        entity_b = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=entity_a,
                subject_id=subject_id,
                entity_type="person",
                name="Alice",
                role="colleague",
                connections=[entity_b],
            ),
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=entity_b,
                subject_id=subject_id,
                entity_type="person",
                name="Bob",
                role="colleague",
            ),
        ]

        count = await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=entities,
        )

        # 4 bidirectional connections + 1 indirect (subject->entity_b via entity_a)
        assert count == 5


class TestFindConnectedSubjects:
    """Tests for find_connected_subjects method."""

    @pytest.mark.asyncio
    async def test_find_connected_subjects_empty(self):
        """Test finding connections when none exist."""
        index = create_index()
        subject_id = uuid7()

        # Must index subject first
        await index.index_screening_connections(
            screening_id=uuid7(),
            subject_id=subject_id,
            entities=[],
        )

        result = await index.find_connected_subjects(subject_id)

        assert result.total_connections == 0
        assert len(result.connections) == 0

    @pytest.mark.asyncio
    async def test_find_connected_subjects_not_found(self):
        """Test finding connections for unknown subject."""
        index = create_index()

        with pytest.raises(SubjectNotFoundError):
            await index.find_connected_subjects(uuid7())

    @pytest.mark.asyncio
    async def test_find_direct_connections(self):
        """Test finding direct connections."""
        index = create_index()
        screening_id = uuid7()
        subject_id = uuid7()
        entity_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=entity_id,
                subject_id=subject_id,
                entity_type="person",
                name="Connected Person",
                role="colleague",
            )
        ]

        await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=entities,
        )

        result = await index.find_connected_subjects(subject_id, max_degree=1)

        assert result.total_connections == 1
        assert result.direct_connections == 1
        assert result.max_degree == 1
        assert result.connections[0].target_subject_id == entity_id

    @pytest.mark.asyncio
    async def test_find_connections_with_type_filter(self):
        """Test filtering by connection type."""
        index = create_index()
        screening_id = uuid7()
        subject_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Colleague A",
                role="colleague",
            ),
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Boss B",
                role="employer",
            ),
        ]

        await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=entities,
        )

        # Filter for colleague only
        result = await index.find_connected_subjects(
            subject_id,
            connection_types=[ConnectionType.COLLEAGUE],
        )

        assert result.total_connections == 1
        assert result.connections[0].connection_type == ConnectionType.COLLEAGUE

    @pytest.mark.asyncio
    async def test_find_connections_with_min_confidence(self):
        """Test filtering by minimum confidence."""
        index = create_index(IndexConfig(min_confidence=0.1))
        screening_id = uuid7()
        subject_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="High Confidence",
                role="employer",
                findings_count=10,  # High findings boost confidence: 0.5 + 0.2 + 0.1 = 0.8
            ),
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Low Confidence",  # No role or findings: base 0.5
            ),
        ]

        await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=entities,
        )

        # Confidence of 0.7 should filter out the 0.5 connection but keep 0.8
        result = await index.find_connected_subjects(
            subject_id,
            min_confidence=0.7,
        )

        # Only high confidence (0.8) should pass
        assert result.total_connections == 1

    @pytest.mark.asyncio
    async def test_find_connections_max_degree_2(self):
        """Test finding connections up to degree 2."""
        index = create_index()
        screening_id = uuid7()
        subject_id = uuid7()
        entity_a = uuid7()
        entity_b = uuid7()

        # Create entity A connected to subject
        entities_1 = [
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=entity_a,
                subject_id=subject_id,
                entity_type="person",
                name="Entity A",
                role="colleague",
            )
        ]
        await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=entities_1,
        )

        # Create entity B connected to entity A (second screening)
        screening_id_2 = uuid7()
        entities_2 = [
            ScreeningEntity(
                screening_id=screening_id_2,
                entity_id=entity_b,
                subject_id=entity_a,
                entity_type="person",
                name="Entity B",
                role="colleague",
            )
        ]
        await index.index_screening_connections(
            screening_id=screening_id_2,
            subject_id=entity_a,
            entities=entities_2,
        )

        # Query from original subject with max_degree=2
        result = await index.find_connected_subjects(subject_id, max_degree=2)

        # Should find both A (degree 1) and B (degree 2)
        assert result.total_connections >= 2
        assert result.direct_connections >= 1


class TestNetworkGraph:
    """Tests for get_network_graph method."""

    @pytest.mark.asyncio
    async def test_get_empty_graph(self):
        """Test getting graph for subject with no connections."""
        index = create_index()
        subject_id = uuid7()

        await index.index_screening_connections(
            screening_id=uuid7(),
            subject_id=subject_id,
            entities=[],
        )

        graph = await index.get_network_graph(subject_id)

        assert graph.node_count == 1  # Just the subject
        assert graph.edge_count == 0
        assert graph.center_subject_id == subject_id

    @pytest.mark.asyncio
    async def test_get_graph_with_connections(self):
        """Test getting graph with connections."""
        index = create_index()
        screening_id = uuid7()
        subject_id = uuid7()
        entity_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=entity_id,
                subject_id=subject_id,
                entity_type="person",
                name="Connected Person",
                role="colleague",
            )
        ]

        await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=entities,
        )

        graph = await index.get_network_graph(subject_id, max_depth=1)

        assert graph.node_count == 2
        assert graph.edge_count == 1
        assert graph.center_subject_id == subject_id

        # Can get neighbors
        neighbors = graph.get_neighbors(subject_id)
        assert entity_id in neighbors


class TestRelationshipStrength:
    """Tests for calculate_relationship_strength method."""

    @pytest.mark.asyncio
    async def test_strength_no_connection(self):
        """Test strength when no connection exists."""
        index = create_index()
        subject_a = uuid7()
        subject_b = uuid7()

        # Index subject_a
        await index.index_screening_connections(
            screening_id=uuid7(),
            subject_id=subject_a,
            entities=[],
        )

        strength = await index.calculate_relationship_strength(subject_a, subject_b)
        assert strength == 0.0

    @pytest.mark.asyncio
    async def test_strength_direct_connection(self):
        """Test strength for direct connection."""
        index = create_index()
        screening_id = uuid7()
        subject_id = uuid7()
        entity_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=entity_id,
                subject_id=subject_id,
                entity_type="person",
                name="Connected",
                role="employer",
                findings_count=5,
            )
        ]

        await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=entities,
        )

        strength = await index.calculate_relationship_strength(subject_id, entity_id)
        assert strength > 0.0
        assert strength <= 1.0

    @pytest.mark.asyncio
    async def test_strength_multiple_screenings(self):
        """Test strength increases with multiple screenings."""
        index = create_index()
        subject_id = uuid7()
        entity_id = uuid7()

        # First screening
        await index.index_screening_connections(
            screening_id=uuid7(),
            subject_id=subject_id,
            entities=[
                ScreeningEntity(
                    screening_id=uuid7(),
                    entity_id=entity_id,
                    subject_id=subject_id,
                    entity_type="person",
                    name="Connected",
                    role="colleague",
                )
            ],
        )

        strength_1 = await index.calculate_relationship_strength(subject_id, entity_id)

        # Second screening confirms connection
        await index.index_screening_connections(
            screening_id=uuid7(),
            subject_id=subject_id,
            entities=[
                ScreeningEntity(
                    screening_id=uuid7(),
                    entity_id=entity_id,
                    subject_id=subject_id,
                    entity_type="person",
                    name="Connected",
                    role="colleague",
                )
            ],
        )

        strength_2 = await index.calculate_relationship_strength(subject_id, entity_id)

        # Strength should increase with corroboration
        assert strength_2 >= strength_1


class TestStatistics:
    """Tests for get_statistics method."""

    @pytest.mark.asyncio
    async def test_empty_statistics(self):
        """Test statistics for empty index."""
        index = create_index()
        stats = await index.get_statistics()

        assert stats.total_subjects == 0
        assert stats.total_connections == 0
        assert stats.total_screenings == 0
        assert stats.avg_connections_per_subject == 0.0

    @pytest.mark.asyncio
    async def test_statistics_after_indexing(self):
        """Test statistics after indexing."""
        index = create_index()
        screening_id = uuid7()
        subject_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Person A",
                role="colleague",
            ),
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Person B",
                role="employer",
            ),
        ]

        await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=entities,
        )

        stats = await index.get_statistics()

        assert stats.total_screenings == 1
        assert stats.total_subjects > 0
        assert stats.total_connections > 0
        assert stats.last_updated is not None


class TestRemoveScreening:
    """Tests for remove_screening method."""

    @pytest.mark.asyncio
    async def test_remove_nonexistent_screening(self):
        """Test removing a screening that doesn't exist."""
        index = create_index()
        count = await index.remove_screening(uuid7())
        assert count == 0

    @pytest.mark.asyncio
    async def test_remove_screening(self):
        """Test removing an indexed screening."""
        index = create_index()
        screening_id = uuid7()
        subject_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=screening_id,
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Person",
                role="colleague",
            )
        ]

        await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=entities,
        )

        stats_before = await index.get_statistics()
        assert stats_before.total_screenings == 1

        removed = await index.remove_screening(screening_id)
        assert removed > 0

        stats_after = await index.get_statistics()
        assert stats_after.total_screenings == 0


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_index_function(self):
        """Test create_index factory function."""
        index = create_index()
        assert isinstance(index, CrossScreeningIndex)

    def test_create_index_with_config(self):
        """Test create_index with config."""
        config = IndexConfig(max_degree=5)
        index = create_index(config)
        assert index.config.max_degree == 5

    def test_get_cross_screening_index_singleton(self):
        """Test singleton behavior."""
        # Note: This test may fail if other tests have already called
        # get_cross_screening_index(). In production, use dependency injection.
        index1 = get_cross_screening_index()
        index2 = get_cross_screening_index()
        assert index1 is index2


class TestRoleMapping:
    """Tests for role to connection type mapping."""

    @pytest.mark.asyncio
    async def test_employer_role(self):
        """Test employer role mapping."""
        index = create_index()
        subject_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=uuid7(),
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Boss",
                role="employer",
            )
        ]

        await index.index_screening_connections(
            screening_id=uuid7(),
            subject_id=subject_id,
            entities=entities,
        )

        result = await index.find_connected_subjects(subject_id)
        assert result.connections[0].connection_type == ConnectionType.EMPLOYER

    @pytest.mark.asyncio
    async def test_colleague_role(self):
        """Test colleague role mapping."""
        index = create_index()
        subject_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=uuid7(),
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Coworker",
                role="coworker",
            )
        ]

        await index.index_screening_connections(
            screening_id=uuid7(),
            subject_id=subject_id,
            entities=entities,
        )

        result = await index.find_connected_subjects(subject_id)
        assert result.connections[0].connection_type == ConnectionType.COLLEAGUE

    @pytest.mark.asyncio
    async def test_family_role(self):
        """Test family role mapping."""
        index = create_index()
        subject_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=uuid7(),
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Spouse",
                role="spouse",
            )
        ]

        await index.index_screening_connections(
            screening_id=uuid7(),
            subject_id=subject_id,
            entities=entities,
        )

        result = await index.find_connected_subjects(subject_id)
        assert result.connections[0].connection_type == ConnectionType.FAMILY

    @pytest.mark.asyncio
    async def test_unknown_role_defaults_to_associate(self):
        """Test unknown role defaults to associate."""
        index = create_index()
        subject_id = uuid7()

        entities = [
            ScreeningEntity(
                screening_id=uuid7(),
                entity_id=uuid7(),
                subject_id=subject_id,
                entity_type="person",
                name="Unknown",
                role="some_unknown_role",
            )
        ]

        await index.index_screening_connections(
            screening_id=uuid7(),
            subject_id=subject_id,
            entities=entities,
        )

        result = await index.find_connected_subjects(subject_id)
        assert result.connections[0].connection_type == ConnectionType.ASSOCIATE
