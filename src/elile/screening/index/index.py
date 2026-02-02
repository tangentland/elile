"""Cross-screening entity index for network analysis.

This module provides the CrossScreeningIndex class for indexing and querying
entity connections across screening operations.
"""

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.core.logging import get_logger

from .types import (
    ConnectionStrength,
    ConnectionType,
    CrossScreeningResult,
    IndexingError,
    NetworkEdge,
    NetworkGraph,
    NetworkNode,
    ScreeningEntity,
    SubjectConnection,
    SubjectNotFoundError,
)

logger = get_logger(__name__)


class IndexConfig(BaseModel):
    """Configuration for the cross-screening index.

    Attributes:
        max_degree: Maximum connection degree to track (default 3).
        min_confidence: Minimum confidence score to include connections (default 0.3).
        decay_factor: Factor to reduce confidence for indirect connections (default 0.7).
        max_connections_per_subject: Limit on connections per subject (default 1000).
        enable_temporal_tracking: Whether to track temporal changes (default True).
    """

    max_degree: int = 3
    min_confidence: float = Field(ge=0.0, le=1.0, default=0.3)
    decay_factor: float = Field(ge=0.0, le=1.0, default=0.7)
    max_connections_per_subject: int = 1000
    enable_temporal_tracking: bool = True


class IndexStatistics(BaseModel):
    """Statistics about the cross-screening index.

    Attributes:
        total_subjects: Number of unique subjects indexed.
        total_connections: Total connections in the index.
        total_screenings: Number of screenings indexed.
        avg_connections_per_subject: Average connections per subject.
        last_updated: When the index was last updated.
    """

    total_subjects: int = 0
    total_connections: int = 0
    total_screenings: int = 0
    avg_connections_per_subject: float = 0.0
    last_updated: datetime | None = None


class CrossScreeningIndex:
    """Index for cross-screening entity relationships.

    Enables discovery of connections between subjects across different
    screening operations. Supports network graph queries and relationship
    strength scoring.

    Usage:
        index = CrossScreeningIndex()

        # Index a screening's connections
        await index.index_screening_connections(
            screening_id=screening_id,
            subject_id=subject_id,
            entities=discovered_entities,
        )

        # Find connected subjects
        result = await index.find_connected_subjects(
            subject_id=subject_id,
            max_degree=2,
        )
    """

    def __init__(self, config: IndexConfig | None = None) -> None:
        """Initialize the cross-screening index.

        Args:
            config: Optional index configuration.
        """
        self._config = config or IndexConfig()

        # In-memory index structures
        # subject_id -> list of connections
        self._connections: dict[UUID, list[SubjectConnection]] = defaultdict(list)
        # screening_id -> list of entity references
        self._screening_entities: dict[UUID, list[ScreeningEntity]] = {}
        # subject_id -> set of indexed screening IDs
        self._subject_screenings: dict[UUID, set[UUID]] = defaultdict(set)
        # subject_id -> NetworkNode
        self._nodes: dict[UUID, NetworkNode] = {}
        # Track indexed screenings
        self._indexed_screenings: set[UUID] = set()

        logger.info("cross_screening_index_initialized", config=self._config.model_dump())

    @property
    def config(self) -> IndexConfig:
        """Get the index configuration."""
        return self._config

    async def index_screening_connections(
        self,
        screening_id: UUID,
        subject_id: UUID,
        entities: list[ScreeningEntity],
        *,
        locale: str = "US",
    ) -> int:
        """Index all entities and connections discovered in a screening.

        Extracts entities from screening findings and creates bidirectional
        edges in the connection graph. Calculates relationship scores based
        on evidence quality.

        Args:
            screening_id: The screening operation ID.
            subject_id: The primary subject of the screening.
            entities: Entities discovered during screening.
            locale: Locale for compliance context.

        Returns:
            Number of connections indexed.

        Raises:
            IndexingError: If indexing fails.
        """
        try:
            connections_added = 0

            # Store screening entities
            self._screening_entities[screening_id] = entities
            self._indexed_screenings.add(screening_id)
            self._subject_screenings[subject_id].add(screening_id)

            # Ensure subject has a node
            if subject_id not in self._nodes:
                self._nodes[subject_id] = NetworkNode(
                    subject_id=subject_id,
                    name=f"Subject-{str(subject_id)[:8]}",
                    screenings_count=0,
                )
            self._nodes[subject_id].screenings_count += 1

            # Process each entity discovered
            for entity in entities:
                if entity.entity_type == "person" and entity.entity_id != subject_id:
                    # Create connection from subject to discovered person
                    connection = self._create_connection(
                        source_subject_id=subject_id,
                        target_subject_id=entity.entity_id,
                        entity=entity,
                        screening_id=screening_id,
                    )

                    self._add_connection(connection)
                    connections_added += 1

                    # Create bidirectional edge
                    reverse_connection = self._create_connection(
                        source_subject_id=entity.entity_id,
                        target_subject_id=subject_id,
                        entity=entity,
                        screening_id=screening_id,
                        reverse=True,
                    )
                    self._add_connection(reverse_connection)
                    connections_added += 1

                    # Index connections between discovered entities
                    for connected_id in entity.connections:
                        if connected_id != subject_id:
                            indirect = self._create_indirect_connection(
                                source_id=subject_id,
                                target_id=connected_id,
                                via_id=entity.entity_id,
                                screening_id=screening_id,
                            )
                            self._add_connection(indirect)
                            connections_added += 1

            logger.info(
                "screening_indexed",
                screening_id=str(screening_id),
                subject_id=str(subject_id),
                entities_count=len(entities),
                connections_added=connections_added,
                locale=locale,
            )

            return connections_added

        except Exception as e:
            logger.error(
                "indexing_failed",
                screening_id=str(screening_id),
                error=str(e),
            )
            raise IndexingError(screening_id, str(e)) from e

    async def find_connected_subjects(
        self,
        subject_id: UUID,
        max_degree: int = 2,
        *,
        connection_types: list[ConnectionType] | None = None,
        min_confidence: float | None = None,
        locale: str = "US",
    ) -> CrossScreeningResult:
        """Find subjects connected to a target subject.

        Performs a breadth-first search through the connection graph to find
        all subjects within the specified degree of separation.

        Args:
            subject_id: The subject to find connections for.
            max_degree: Maximum relationship depth (1-3 recommended).
            connection_types: Optional filter by connection types.
            min_confidence: Minimum confidence threshold.
            locale: Locale for audit logging.

        Returns:
            CrossScreeningResult with all discovered connections.

        Raises:
            SubjectNotFoundError: If subject is not in the index.
        """
        start_time = datetime.now(UTC)
        min_conf = min_confidence if min_confidence is not None else self._config.min_confidence

        if subject_id not in self._connections and subject_id not in self._nodes:
            raise SubjectNotFoundError(subject_id)

        # Limit max_degree to configured maximum
        effective_max_degree = min(max_degree, self._config.max_degree)

        # BFS to find connected subjects
        found_connections: list[SubjectConnection] = []
        visited: set[UUID] = {subject_id}
        current_level: set[UUID] = {subject_id}

        for current_degree in range(1, effective_max_degree + 1):
            next_level: set[UUID] = set()

            for current_id in current_level:
                for conn in self._connections.get(current_id, []):
                    # Skip if already visited
                    if conn.target_subject_id in visited:
                        continue

                    # Apply filters
                    if conn.confidence_score < min_conf:
                        continue
                    if connection_types and conn.connection_type not in connection_types:
                        continue

                    # Check connection limits
                    if len(found_connections) >= self._config.max_connections_per_subject:
                        break

                    # Adjust degree for indirect discovery
                    adjusted_conn = conn.model_copy(
                        update={"degree": current_degree}
                        if conn.degree == 1
                        else {"degree": conn.degree}
                    )
                    found_connections.append(adjusted_conn)
                    visited.add(conn.target_subject_id)
                    next_level.add(conn.target_subject_id)

            current_level = next_level

        # Calculate query time
        query_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

        result = CrossScreeningResult(
            query_subject_id=subject_id,
            connections=found_connections,
            total_connections=len(found_connections),
            direct_connections=len([c for c in found_connections if c.degree == 1]),
            max_degree=max(c.degree for c in found_connections) if found_connections else 0,
            query_time_ms=query_time,
        )

        logger.info(
            "cross_screening_query",
            subject_id=str(subject_id),
            max_degree=max_degree,
            results_count=result.total_connections,
            query_time_ms=result.query_time_ms,
            locale=locale,
        )

        return result

    async def get_network_graph(
        self,
        subject_id: UUID,
        max_depth: int = 2,
        *,
        min_weight: float = 0.0,
        locale: str = "US",
    ) -> NetworkGraph:
        """Get a network graph centered on a subject.

        Builds a subgraph of the cross-screening network for visualization
        and analysis purposes.

        Args:
            subject_id: Center subject for the graph.
            max_depth: Maximum depth from center.
            min_weight: Minimum edge weight to include.
            locale: Locale for audit logging.

        Returns:
            NetworkGraph with nodes and edges.
        """
        nodes: list[NetworkNode] = []
        edges: list[NetworkEdge] = []
        visited: set[UUID] = set()
        edge_set: set[tuple[UUID, UUID]] = set()

        # BFS to build graph
        current_level = {subject_id}

        for depth in range(max_depth + 1):
            next_level: set[UUID] = set()

            for current_id in current_level:
                if current_id in visited:
                    continue
                visited.add(current_id)

                # Add node
                if current_id in self._nodes:
                    nodes.append(self._nodes[current_id])
                else:
                    nodes.append(
                        NetworkNode(
                            subject_id=current_id,
                            name=f"Subject-{str(current_id)[:8]}",
                        )
                    )

                # Add edges to neighbors
                for conn in self._connections.get(current_id, []):
                    target_id = conn.target_subject_id
                    # Create canonical edge key (smaller UUID first)
                    if current_id < target_id:
                        edge_key = (current_id, target_id)
                    else:
                        edge_key = (target_id, current_id)

                    # Skip if edge already added or below weight threshold
                    if edge_key in edge_set:
                        continue
                    if conn.confidence_score < min_weight:
                        continue

                    edge_set.add(edge_key)
                    edges.append(
                        NetworkEdge(
                            source_id=current_id,
                            target_id=target_id,
                            connection_type=conn.connection_type,
                            weight=conn.confidence_score,
                            screenings=conn.screening_ids,
                        )
                    )

                    if depth < max_depth:
                        next_level.add(target_id)

            current_level = next_level

        graph = NetworkGraph(
            nodes=nodes,
            edges=edges,
            center_subject_id=subject_id,
            max_depth=max_depth,
        )

        logger.info(
            "network_graph_generated",
            subject_id=str(subject_id),
            max_depth=max_depth,
            nodes=graph.node_count,
            edges=graph.edge_count,
            locale=locale,
        )

        return graph

    async def calculate_relationship_strength(
        self,
        subject_id_a: UUID,
        subject_id_b: UUID,
        *,
        locale: str = "US",  # noqa: ARG002
    ) -> float:
        """Calculate the relationship strength between two subjects.

        Combines multiple factors including connection type, evidence
        quality, and corroboration across screenings.

        Args:
            subject_id_a: First subject.
            subject_id_b: Second subject.
            locale: Locale for audit context.

        Returns:
            Relationship strength score 0.0-1.0.
        """
        # Find all connections between the two subjects
        connections = [
            c
            for c in self._connections.get(subject_id_a, [])
            if c.target_subject_id == subject_id_b
        ]

        if not connections:
            return 0.0

        # Calculate aggregate strength
        # - Higher if multiple screenings confirm the connection
        # - Higher if connection is direct (degree 1)
        # - Higher for verified/strong connections

        max_confidence = max(c.confidence_score for c in connections)
        screening_count = len({sid for c in connections for sid in c.screening_ids})
        min_degree = min(c.degree for c in connections)
        strength_bonus = max(
            1.0 if c.strength == ConnectionStrength.VERIFIED else 0.0 for c in connections
        )

        # Combine factors
        base_score = max_confidence
        corroboration_factor = min(1.0 + (screening_count - 1) * 0.1, 1.3)
        degree_factor = 1.0 / min_degree  # Direct = 1.0, degree 2 = 0.5, etc.

        strength = min(1.0, base_score * corroboration_factor * degree_factor + strength_bonus * 0.1)

        return round(strength, 3)

    async def get_statistics(self) -> IndexStatistics:
        """Get statistics about the cross-screening index.

        Returns:
            IndexStatistics with current index metrics.
        """
        total_subjects = len(self._nodes)
        total_connections = sum(len(conns) for conns in self._connections.values())
        total_screenings = len(self._indexed_screenings)

        avg_connections = total_connections / total_subjects if total_subjects > 0 else 0.0

        return IndexStatistics(
            total_subjects=total_subjects,
            total_connections=total_connections,
            total_screenings=total_screenings,
            avg_connections_per_subject=round(avg_connections, 2),
            last_updated=datetime.now(UTC),
        )

    async def remove_screening(self, screening_id: UUID, *, locale: str = "US") -> int:
        """Remove a screening and its connections from the index.

        Args:
            screening_id: The screening to remove.
            locale: Locale for audit logging.

        Returns:
            Number of connections removed.
        """
        if screening_id not in self._indexed_screenings:
            return 0

        removed_count = 0

        # Remove connections associated with this screening
        for subject_id, connections in list(self._connections.items()):
            remaining = []
            for conn in connections:
                if screening_id in conn.screening_ids:
                    conn.screening_ids.remove(screening_id)
                    if not conn.screening_ids:
                        # No more screenings support this connection
                        removed_count += 1
                        continue
                remaining.append(conn)
            self._connections[subject_id] = remaining

        # Update tracking
        self._indexed_screenings.discard(screening_id)
        del self._screening_entities[screening_id]

        # Update subject screenings
        for subject_id, screenings in self._subject_screenings.items():
            screenings.discard(screening_id)
            if subject_id in self._nodes:
                self._nodes[subject_id].screenings_count = len(screenings)

        logger.info(
            "screening_removed_from_index",
            screening_id=str(screening_id),
            connections_removed=removed_count,
            locale=locale,
        )

        return removed_count

    def _create_connection(
        self,
        source_subject_id: UUID,
        target_subject_id: UUID,
        entity: ScreeningEntity,
        screening_id: UUID,
        reverse: bool = False,
    ) -> SubjectConnection:
        """Create a subject connection from a screening entity."""
        # Determine connection type from entity role
        conn_type = self._role_to_connection_type(entity.role)

        # Calculate confidence based on entity metadata
        confidence = self._calculate_entity_confidence(entity)

        # Determine strength
        strength = self._confidence_to_strength(confidence)

        # Build evidence list
        evidence = []
        if entity.role:
            evidence.append(f"Role: {entity.role}")
        if entity.findings_count > 0:
            evidence.append(f"Findings: {entity.findings_count}")

        now = datetime.now(UTC)

        return SubjectConnection(
            connection_id=uuid7(),
            source_subject_id=source_subject_id,
            target_subject_id=target_subject_id,
            connection_type=conn_type,
            strength=strength,
            confidence_score=confidence,
            degree=1,  # Direct connection
            discovered_at=now,
            last_seen_at=now,
            screening_ids=[screening_id],
            evidence=evidence,
            metadata={
                "entity_name": entity.name,
                "entity_type": entity.entity_type,
                "reverse": reverse,
            },
        )

    def _create_indirect_connection(
        self,
        source_id: UUID,
        target_id: UUID,
        via_id: UUID,
        screening_id: UUID,
    ) -> SubjectConnection:
        """Create an indirect connection through an intermediary."""
        # Decay confidence for indirect connections
        confidence = 0.5 * self._config.decay_factor

        now = datetime.now(UTC)

        return SubjectConnection(
            connection_id=uuid7(),
            source_subject_id=source_id,
            target_subject_id=target_id,
            connection_type=ConnectionType.NETWORK_NEIGHBOR,
            strength=ConnectionStrength.WEAK,
            confidence_score=confidence,
            degree=2,  # Indirect connection
            discovered_at=now,
            last_seen_at=now,
            screening_ids=[screening_id],
            evidence=[f"Connected via entity {via_id}"],
            metadata={"via_entity_id": str(via_id)},
        )

    def _add_connection(self, connection: SubjectConnection) -> None:
        """Add a connection to the index, merging with existing if present."""
        existing = self._find_existing_connection(
            connection.source_subject_id,
            connection.target_subject_id,
            connection.connection_type,
        )

        if existing:
            # Merge: update confidence, add screening IDs, update last_seen
            existing.confidence_score = max(existing.confidence_score, connection.confidence_score)
            existing.last_seen_at = datetime.now(UTC)
            for sid in connection.screening_ids:
                if sid not in existing.screening_ids:
                    existing.screening_ids.append(sid)
            existing.evidence.extend(connection.evidence)
            # Update strength if confidence increased
            existing.strength = self._confidence_to_strength(existing.confidence_score)
        else:
            # Add new connection
            self._connections[connection.source_subject_id].append(connection)

            # Ensure target has a node
            if connection.target_subject_id not in self._nodes:
                self._nodes[connection.target_subject_id] = NetworkNode(
                    subject_id=connection.target_subject_id,
                    name=connection.metadata.get("entity_name", f"Subject-{str(connection.target_subject_id)[:8]}"),
                )

            # Update connection counts
            if connection.source_subject_id in self._nodes:
                self._nodes[connection.source_subject_id].connections_count += 1

    def _find_existing_connection(
        self,
        source_id: UUID,
        target_id: UUID,
        conn_type: ConnectionType,
    ) -> SubjectConnection | None:
        """Find an existing connection between two subjects."""
        for conn in self._connections.get(source_id, []):
            if conn.target_subject_id == target_id and conn.connection_type == conn_type:
                return conn
        return None

    def _role_to_connection_type(self, role: str | None) -> ConnectionType:
        """Map an entity role to a connection type."""
        if not role:
            return ConnectionType.ASSOCIATE

        role_lower = role.lower()
        mapping = {
            "employer": ConnectionType.EMPLOYER,
            "employee": ConnectionType.EMPLOYER,
            "colleague": ConnectionType.COLLEAGUE,
            "coworker": ConnectionType.COLLEAGUE,
            "business_partner": ConnectionType.BUSINESS_PARTNER,
            "partner": ConnectionType.BUSINESS_PARTNER,
            "director": ConnectionType.DIRECTOR,
            "officer": ConnectionType.DIRECTOR,
            "family": ConnectionType.FAMILY,
            "relative": ConnectionType.FAMILY,
            "spouse": ConnectionType.FAMILY,
            "household": ConnectionType.ADDRESS,
            "address": ConnectionType.ADDRESS,
            "residence": ConnectionType.ADDRESS,
        }

        for key, value in mapping.items():
            if key in role_lower:
                return value

        return ConnectionType.ASSOCIATE

    def _calculate_entity_confidence(self, entity: ScreeningEntity) -> float:
        """Calculate confidence score for an entity."""
        # Base confidence
        confidence = 0.5

        # Boost for more findings (more evidence)
        if entity.findings_count > 0:
            confidence += min(0.2, entity.findings_count * 0.05)

        # Boost for more connections (more context)
        if entity.connections:
            confidence += min(0.1, len(entity.connections) * 0.02)

        # Boost for having a specific role
        if entity.role:
            confidence += 0.1

        return min(1.0, confidence)

    def _confidence_to_strength(self, confidence: float) -> ConnectionStrength:
        """Convert confidence score to connection strength."""
        if confidence >= 0.9:
            return ConnectionStrength.VERIFIED
        elif confidence >= 0.7:
            return ConnectionStrength.STRONG
        elif confidence >= 0.5:
            return ConnectionStrength.MODERATE
        return ConnectionStrength.WEAK


# =============================================================================
# Factory function
# =============================================================================

_index_instance: CrossScreeningIndex | None = None


def get_cross_screening_index(config: IndexConfig | None = None) -> CrossScreeningIndex:
    """Get the singleton cross-screening index instance.

    Args:
        config: Optional configuration for first initialization.

    Returns:
        The CrossScreeningIndex singleton.
    """
    global _index_instance
    if _index_instance is None:
        _index_instance = CrossScreeningIndex(config)
    return _index_instance


def create_index(config: IndexConfig | None = None) -> CrossScreeningIndex:
    """Create a new cross-screening index instance.

    Use this for testing or when you need a fresh index.

    Args:
        config: Optional configuration.

    Returns:
        A new CrossScreeningIndex instance.
    """
    return CrossScreeningIndex(config)
