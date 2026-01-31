"""Canonical entity management.

This module provides the EntityManager class for high-level
entity operations including creation, resolution, and relationship management.
"""

from uuid import UUID, uuid7

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from elile.core.audit import AuditLogger
from elile.core.context import get_current_context
from elile.core.logging import get_logger
from elile.db.models.audit import AuditEventType
from elile.db.models.entity import Entity, EntityType

from .deduplication import EntityDeduplicator
from .graph import RelationshipEdge, RelationshipGraph, RelationshipPath
from .identifiers import IdentifierManager
from .matcher import EntityMatcher
from .types import (
    IdentifierRecord,
    IdentifierType,
    MatchResult,
    RelationType,
    SubjectIdentifiers,
)

logger = get_logger(__name__)


class EntityCreateResult(BaseModel):
    """Result of entity creation attempt."""

    entity_id: UUID
    created: bool = True  # False if existing entity returned
    match_result: MatchResult | None = None


class EntityManager:
    """High-level entity management operations.

    Provides a unified interface for entity creation, resolution,
    identifier management, and relationship operations.
    """

    def __init__(
        self,
        session: AsyncSession,
        audit_logger: AuditLogger | None = None,
    ):
        """Initialize the entity manager.

        Args:
            session: Database session for operations
            audit_logger: Optional audit logger for tracking changes
        """
        self._session = session
        self._audit = audit_logger
        self._matcher = EntityMatcher(session)
        self._dedup = EntityDeduplicator(session, audit_logger)
        self._identifiers = IdentifierManager(session)
        self._graph = RelationshipGraph(session)

    async def create_entity(
        self,
        entity_type: EntityType,
        identifiers: SubjectIdentifiers,
        allow_duplicate: bool = False,
    ) -> EntityCreateResult:
        """Create a new entity with deduplication check.

        First checks for existing entities with matching identifiers.
        If found, returns the existing entity. Otherwise creates new.

        Args:
            entity_type: Type of entity (INDIVIDUAL, ORGANIZATION, ADDRESS)
            identifiers: Subject identifiers for the entity
            allow_duplicate: If True, skip dedup check and always create

        Returns:
            EntityCreateResult with entity_id and creation status
        """
        # Check for duplicates unless explicitly skipped
        if not allow_duplicate:
            dedup_result = await self._dedup.check_duplicate(identifiers, entity_type)
            if dedup_result.is_duplicate:
                logger.info(
                    "entity_dedup_match",
                    existing_entity_id=str(dedup_result.existing_entity_id),
                )
                from .types import MatchType, ResolutionDecision

                return EntityCreateResult(
                    entity_id=dedup_result.existing_entity_id,
                    created=False,
                    match_result=MatchResult(
                        entity_id=dedup_result.existing_entity_id,
                        match_type=MatchType.EXACT,
                        confidence=dedup_result.match_confidence,
                        decision=ResolutionDecision.MATCH_EXISTING,
                        matched_identifiers=dedup_result.matching_identifiers,
                    ) if dedup_result.existing_entity_id else None,
                )

        # Create new entity
        entity_id = uuid7()
        canonical_identifiers = self._build_canonical_identifiers(identifiers)

        entity = Entity(
            entity_id=entity_id,
            entity_type=entity_type.value,
            canonical_identifiers=canonical_identifiers,
        )
        self._session.add(entity)
        await self._session.flush()

        # Audit log
        if self._audit:
            await self._audit.log_event(
                event_type=AuditEventType.ENTITY_CREATED,
                entity_id=entity_id,
                event_data={
                    "entity_type": entity_type.value,
                    "identifier_types": list(canonical_identifiers.keys()),
                },
            )

        logger.info(
            "entity_created",
            entity_id=str(entity_id),
            entity_type=entity_type.value,
        )

        return EntityCreateResult(
            entity_id=entity_id,
            created=True,
        )

    async def get_entity(self, entity_id: UUID) -> Entity | None:
        """Get an entity by ID.

        Args:
            entity_id: Entity ID to retrieve

        Returns:
            Entity or None if not found
        """
        stmt = select(Entity).where(Entity.entity_id == entity_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve(
        self,
        identifiers: SubjectIdentifiers,
        entity_type: EntityType = EntityType.INDIVIDUAL,
    ) -> MatchResult:
        """Resolve identifiers to an existing entity.

        Uses the EntityMatcher to find matching entities.

        Args:
            identifiers: Subject identifiers to resolve
            entity_type: Expected entity type

        Returns:
            MatchResult with resolution decision
        """
        return await self._matcher.resolve(identifiers, entity_type)

    # -------------------------------------------------------------------------
    # Identifier Management
    # -------------------------------------------------------------------------

    async def add_identifier(
        self,
        entity_id: UUID,
        identifier_type: IdentifierType,
        value: str,
        confidence: float = 1.0,
        source: str = "unknown",
        **kwargs,
    ) -> bool:
        """Add an identifier to an entity.

        May trigger a merge if the identifier matches another entity.

        Args:
            entity_id: Entity to add identifier to
            identifier_type: Type of identifier
            value: Identifier value
            confidence: Confidence score 0.0-1.0
            source: Where identifier was discovered
            **kwargs: Additional args (country, state)

        Returns:
            True if identifier was added
        """
        # Add the identifier
        success = await self._identifiers.add_identifier(
            entity_id=entity_id,
            identifier_type=identifier_type,
            value=value,
            confidence=confidence,
            source=source,
            **kwargs,
        )

        if not success:
            return False

        # Check for merge trigger
        merge_result = await self._dedup.on_identifier_added(
            entity_id, identifier_type, value
        )

        if merge_result:
            logger.info(
                "identifier_triggered_merge",
                entity_id=str(entity_id),
                canonical_id=str(merge_result.canonical_entity_id),
            )

        return True

    async def get_identifiers(
        self,
        entity_id: UUID,
    ) -> dict[IdentifierType, IdentifierRecord]:
        """Get all identifiers for an entity.

        Args:
            entity_id: Entity to get identifiers for

        Returns:
            Dictionary of identifier type to record
        """
        return await self._identifiers.get_identifiers(entity_id)

    async def get_identifier(
        self,
        entity_id: UUID,
        identifier_type: IdentifierType,
    ) -> IdentifierRecord | None:
        """Get a specific identifier for an entity.

        Args:
            entity_id: Entity to get identifier from
            identifier_type: Type of identifier

        Returns:
            IdentifierRecord or None
        """
        return await self._identifiers.get_identifier(entity_id, identifier_type)

    # -------------------------------------------------------------------------
    # Relationship Management
    # -------------------------------------------------------------------------

    async def add_relation(
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
        edge = await self._graph.add_edge(
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relation_type=relation_type,
            confidence=confidence,
            metadata=metadata,
        )

        # Audit log
        if self._audit:
            await self._audit.log_event(
                event_type=AuditEventType.RELATION_ADDED,
                entity_id=from_entity_id,
                event_data={
                    "to_entity_id": str(to_entity_id),
                    "relation_type": relation_type.value,
                },
            )

        return edge

    async def get_relations(
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
        return await self._graph.get_edges(
            entity_id=entity_id,
            direction=direction,
            relation_type=relation_type,
        )

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
            depth: Maximum relationship depth
            relation_types: Optional filter by types
            min_confidence: Minimum confidence threshold

        Returns:
            Dictionary of entity_id to distance
        """
        return await self._graph.get_neighbors(
            entity_id=entity_id,
            depth=depth,
            relation_types=relation_types,
            min_confidence=min_confidence,
        )

    async def find_path(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        max_depth: int = 5,
    ) -> RelationshipPath:
        """Find the shortest path between two entities.

        Args:
            from_entity_id: Starting entity
            to_entity_id: Target entity
            max_depth: Maximum search depth

        Returns:
            RelationshipPath (check .exists for success)
        """
        return await self._graph.get_path(
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            max_depth=max_depth,
        )

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _build_canonical_identifiers(
        self,
        identifiers: SubjectIdentifiers,
    ) -> dict:
        """Build canonical_identifiers dict from SubjectIdentifiers.

        Args:
            identifiers: Subject identifiers to convert

        Returns:
            Dictionary suitable for Entity.canonical_identifiers
        """
        from datetime import datetime

        result: dict = {}
        now = datetime.utcnow().isoformat()

        # Name
        if identifiers.full_name:
            result["full_name"] = {
                "value": identifiers.full_name,
                "confidence": 1.0,
                "discovered_at": now,
                "source": "initial_creation",
            }

        # Name variants
        if identifiers.name_variants:
            result["name_variants"] = [
                {"value": v, "confidence": 1.0, "discovered_at": now}
                for v in identifiers.name_variants
            ]

        # Date of birth
        if identifiers.date_of_birth:
            result["date_of_birth"] = {
                "value": str(identifiers.date_of_birth),
                "confidence": 1.0,
                "discovered_at": now,
                "source": "initial_creation",
            }

        # Address
        if identifiers.street_address:
            addr_parts = [
                identifiers.street_address,
                identifiers.city,
                identifiers.state,
                identifiers.postal_code,
            ]
            result["address"] = {
                "value": " ".join(filter(None, addr_parts)),
                "confidence": 1.0,
                "discovered_at": now,
                "source": "initial_creation",
            }

        # Canonical identifiers
        if identifiers.ssn:
            result["ssn"] = {
                "value": identifiers.ssn,
                "confidence": 1.0,
                "discovered_at": now,
                "source": "initial_creation",
            }

        if identifiers.ein:
            result["ein"] = {
                "value": identifiers.ein,
                "confidence": 1.0,
                "discovered_at": now,
                "source": "initial_creation",
            }

        if identifiers.passport:
            result["passport"] = {
                "value": identifiers.passport,
                "country": identifiers.passport_country,
                "confidence": 1.0,
                "discovered_at": now,
                "source": "initial_creation",
            }

        if identifiers.drivers_license:
            result["drivers_license"] = {
                "value": identifiers.drivers_license,
                "state": identifiers.drivers_license_state,
                "confidence": 1.0,
                "discovered_at": now,
                "source": "initial_creation",
            }

        if identifiers.email:
            result["email"] = {
                "value": identifiers.email,
                "confidence": 1.0,
                "discovered_at": now,
                "source": "initial_creation",
            }

        if identifiers.phone:
            result["phone"] = {
                "value": identifiers.phone,
                "confidence": 1.0,
                "discovered_at": now,
                "source": "initial_creation",
            }

        return result
