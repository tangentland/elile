"""Entity relationship graph management.

This module provides the RelationshipGraph class for managing
and querying entity relationships.
"""

from collections import deque
from uuid import UUID, uuid7

from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from elile.core.logging import get_logger
from elile.db.models.entity import Entity, EntityRelation

from .types import RelationType

logger = get_logger(__name__)


class RelationshipEdge(BaseModel):
    """Represents a relationship between two entities."""

    relation_id: UUID
    from_entity_id: UUID
    to_entity_id: UUID
    relation_type: RelationType
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    metadata: dict = Field(default_factory=dict)


class PathSegment(BaseModel):
    """A segment in a relationship path."""

    entity_id: UUID
    relation_type: RelationType | None = None
    direction: str = "outbound"  # "outbound" or "inbound"


class RelationshipPath(BaseModel):
    """A path between two entities through relationships."""

    start_entity_id: UUID
    end_entity_id: UUID
    segments: list[PathSegment] = Field(default_factory=list)
    length: int = 0

    @property
    def exists(self) -> bool:
        """Check if a valid path was found."""
        return self.length > 0


class RelationshipGraph:
    """Entity relationship graph manager.

    Provides operations for managing and querying entity
    relationships including neighbor discovery and path finding.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the relationship graph.

        Args:
            session: Database session for operations
        """
        self._session = session

    async def add_edge(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        relation_type: RelationType,
        confidence: float = 1.0,
        metadata: dict | None = None,
    ) -> RelationshipEdge:
        """Add a relationship between two entities.

        Args:
            from_entity_id: Source entity ID
            to_entity_id: Target entity ID
            relation_type: Type of relationship
            confidence: Confidence score 0.0-1.0
            metadata: Optional relationship metadata

        Returns:
            The created relationship edge
        """
        # Check for existing relationship
        existing = await self._find_relation(from_entity_id, to_entity_id, relation_type)
        if existing:
            # Update confidence if higher
            if confidence > existing.confidence_score:
                existing.confidence_score = confidence
                if metadata:
                    existing.metadata = metadata
                await self._session.flush()

            return RelationshipEdge(
                relation_id=existing.relation_id,
                from_entity_id=existing.from_entity_id,
                to_entity_id=existing.to_entity_id,
                relation_type=RelationType(existing.relation_type),
                confidence=existing.confidence_score,
                metadata=existing.metadata or {},
            )

        # Create new relationship
        relation = EntityRelation(
            relation_id=uuid7(),
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relation_type=relation_type.value,
            confidence_score=confidence,
            metadata=metadata or {},
        )
        self._session.add(relation)
        await self._session.flush()

        logger.info(
            "relation_added",
            from_entity_id=str(from_entity_id),
            to_entity_id=str(to_entity_id),
            relation_type=relation_type.value,
        )

        return RelationshipEdge(
            relation_id=relation.relation_id,
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relation_type=relation_type,
            confidence=confidence,
            metadata=metadata or {},
        )

    async def remove_edge(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        relation_type: RelationType | None = None,
    ) -> int:
        """Remove relationship(s) between two entities.

        Args:
            from_entity_id: Source entity ID
            to_entity_id: Target entity ID
            relation_type: Optional specific type to remove

        Returns:
            Count of removed relationships
        """
        stmt = select(EntityRelation).where(
            EntityRelation.from_entity_id == from_entity_id,
            EntityRelation.to_entity_id == to_entity_id,
        )
        if relation_type:
            stmt = stmt.where(EntityRelation.relation_type == relation_type.value)

        result = await self._session.execute(stmt)
        relations = result.scalars().all()

        count = 0
        for relation in relations:
            await self._session.delete(relation)
            count += 1

        if count > 0:
            await self._session.flush()
            logger.info(
                "relations_removed",
                from_entity_id=str(from_entity_id),
                to_entity_id=str(to_entity_id),
                count=count,
            )

        return count

    async def get_edges(
        self,
        entity_id: UUID,
        direction: str = "both",
        relation_type: RelationType | None = None,
    ) -> list[RelationshipEdge]:
        """Get relationships for an entity.

        Args:
            entity_id: Entity to get relationships for
            direction: "outbound", "inbound", or "both"
            relation_type: Optional filter by type

        Returns:
            List of relationship edges
        """
        conditions = []

        if direction in ("outbound", "both"):
            conditions.append(EntityRelation.from_entity_id == entity_id)
        if direction in ("inbound", "both"):
            conditions.append(EntityRelation.to_entity_id == entity_id)

        stmt = select(EntityRelation).where(or_(*conditions))

        if relation_type:
            stmt = stmt.where(EntityRelation.relation_type == relation_type.value)

        result = await self._session.execute(stmt)
        relations = result.scalars().all()

        return [
            RelationshipEdge(
                relation_id=r.relation_id,
                from_entity_id=r.from_entity_id,
                to_entity_id=r.to_entity_id,
                relation_type=RelationType(r.relation_type),
                confidence=r.confidence_score,
                metadata=r.metadata or {},
            )
            for r in relations
        ]

    async def get_neighbors(
        self,
        entity_id: UUID,
        depth: int = 1,
        relation_types: list[RelationType] | None = None,
        min_confidence: float = 0.0,
    ) -> dict[UUID, int]:
        """Get connected entities within a depth.

        Args:
            entity_id: Starting entity
            depth: Maximum relationship depth (1-3 recommended)
            relation_types: Optional filter by relationship types
            min_confidence: Minimum confidence threshold

        Returns:
            Dictionary of entity_id to distance from start
        """
        if depth < 1:
            return {}

        neighbors: dict[UUID, int] = {}
        visited: set[UUID] = {entity_id}
        current_level: set[UUID] = {entity_id}

        for current_depth in range(1, depth + 1):
            next_level: set[UUID] = set()

            for current_id in current_level:
                edges = await self.get_edges(current_id, direction="both")

                for edge in edges:
                    # Filter by relation type if specified
                    if relation_types and edge.relation_type not in relation_types:
                        continue

                    # Filter by confidence
                    if edge.confidence < min_confidence:
                        continue

                    # Get the connected entity
                    connected_id = (
                        edge.to_entity_id
                        if edge.from_entity_id == current_id
                        else edge.from_entity_id
                    )

                    if connected_id not in visited:
                        visited.add(connected_id)
                        neighbors[connected_id] = current_depth
                        next_level.add(connected_id)

            current_level = next_level

        return neighbors

    async def get_path(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        max_depth: int = 5,
    ) -> RelationshipPath:
        """Find the shortest path between two entities.

        Uses BFS to find the shortest relationship path.

        Args:
            from_entity_id: Starting entity
            to_entity_id: Target entity
            max_depth: Maximum search depth

        Returns:
            RelationshipPath (check .exists for success)
        """
        if from_entity_id == to_entity_id:
            return RelationshipPath(
                start_entity_id=from_entity_id,
                end_entity_id=to_entity_id,
                segments=[PathSegment(entity_id=from_entity_id)],
                length=0,
            )

        # BFS for shortest path
        queue = deque([(from_entity_id, [PathSegment(entity_id=from_entity_id)])])
        visited: set[UUID] = {from_entity_id}

        while queue:
            current_id, path = queue.popleft()

            if len(path) > max_depth:
                continue

            edges = await self.get_edges(current_id, direction="both")

            for edge in edges:
                # Determine direction and connected entity
                if edge.from_entity_id == current_id:
                    connected_id = edge.to_entity_id
                    direction = "outbound"
                else:
                    connected_id = edge.from_entity_id
                    direction = "inbound"

                if connected_id in visited:
                    continue

                new_path = path + [
                    PathSegment(
                        entity_id=connected_id,
                        relation_type=edge.relation_type,
                        direction=direction,
                    )
                ]

                if connected_id == to_entity_id:
                    return RelationshipPath(
                        start_entity_id=from_entity_id,
                        end_entity_id=to_entity_id,
                        segments=new_path,
                        length=len(new_path) - 1,
                    )

                visited.add(connected_id)
                queue.append((connected_id, new_path))

        # No path found
        return RelationshipPath(
            start_entity_id=from_entity_id,
            end_entity_id=to_entity_id,
            segments=[],
            length=0,
        )

    async def get_subgraph(
        self,
        entity_ids: list[UUID],
    ) -> list[RelationshipEdge]:
        """Get all relationships between a set of entities.

        Args:
            entity_ids: List of entity IDs to include

        Returns:
            List of edges between the entities
        """
        if not entity_ids:
            return []

        stmt = select(EntityRelation).where(
            EntityRelation.from_entity_id.in_(entity_ids),
            EntityRelation.to_entity_id.in_(entity_ids),
        )

        result = await self._session.execute(stmt)
        relations = result.scalars().all()

        return [
            RelationshipEdge(
                relation_id=r.relation_id,
                from_entity_id=r.from_entity_id,
                to_entity_id=r.to_entity_id,
                relation_type=RelationType(r.relation_type),
                confidence=r.confidence_score,
                metadata=r.metadata or {},
            )
            for r in relations
        ]

    def to_adjacency_dict(
        self,
        edges: list[RelationshipEdge],
    ) -> dict[UUID, list[tuple[UUID, RelationType, float]]]:
        """Convert edges to adjacency list representation.

        Args:
            edges: List of relationship edges

        Returns:
            Dictionary mapping entity_id to list of (neighbor, type, confidence)
        """
        adj: dict[UUID, list[tuple[UUID, RelationType, float]]] = {}

        for edge in edges:
            # Add outbound
            if edge.from_entity_id not in adj:
                adj[edge.from_entity_id] = []
            adj[edge.from_entity_id].append(
                (edge.to_entity_id, edge.relation_type, edge.confidence)
            )

            # Add inbound (undirected view)
            if edge.to_entity_id not in adj:
                adj[edge.to_entity_id] = []
            adj[edge.to_entity_id].append(
                (edge.from_entity_id, edge.relation_type, edge.confidence)
            )

        return adj

    async def _find_relation(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        relation_type: RelationType,
    ) -> EntityRelation | None:
        """Find existing relationship."""
        stmt = select(EntityRelation).where(
            EntityRelation.from_entity_id == from_entity_id,
            EntityRelation.to_entity_id == to_entity_id,
            EntityRelation.relation_type == relation_type.value,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
