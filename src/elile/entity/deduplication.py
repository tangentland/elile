"""Entity deduplication pipeline.

This module provides the EntityDeduplicator class for detecting and merging
duplicate entities across the platform.
"""

from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from elile.core.audit import AuditLogger
from elile.core.context import get_current_context
from elile.core.logging import get_logger
from elile.db.models.audit import AuditEventType
from elile.db.models.entity import Entity, EntityRelation, EntityType
from elile.db.models.profile import EntityProfile

from .matcher import EntityMatcher
from .types import IdentifierType, MatchResult, MatchType, SubjectIdentifiers

logger = get_logger(__name__)


class MergeResult(BaseModel):
    """Result of merging two entities.

    Contains information about the merge operation including
    the canonical (surviving) entity and statistics.
    """

    canonical_entity_id: UUID
    merged_entity_id: UUID
    relationships_updated: int = 0
    profiles_migrated: int = 0
    identifiers_merged: list[str] = Field(default_factory=list)
    reason: str = "duplicate_detected"


class DuplicateCandidate(BaseModel):
    """A potential duplicate entity.

    Represents an entity that might be a duplicate of another,
    with confidence scoring and matching details.
    """

    entity_id: UUID
    match_confidence: float = Field(ge=0.0, le=1.0)
    match_type: MatchType
    matching_identifiers: list[IdentifierType] = Field(default_factory=list)


class DeduplicationResult(BaseModel):
    """Result of a deduplication check.

    Indicates whether a duplicate was found and provides
    the existing entity ID if so.
    """

    is_duplicate: bool = False
    existing_entity_id: UUID | None = None
    match_confidence: float = 0.0
    matching_identifiers: list[IdentifierType] = Field(default_factory=list)


class EntityDeduplicator:
    """Entity deduplication engine.

    Provides duplicate detection before entity creation and
    merge operations for identified duplicates.
    """

    def __init__(self, session: AsyncSession, audit_logger: AuditLogger | None = None):
        """Initialize the deduplicator.

        Args:
            session: Database session for operations
            audit_logger: Optional audit logger for merge events
        """
        self._session = session
        self._audit = audit_logger
        self._matcher = EntityMatcher(session)

    async def check_duplicate(
        self,
        identifiers: SubjectIdentifiers,
        entity_type: EntityType = EntityType.INDIVIDUAL,
        tenant_id: UUID | None = None,
    ) -> DeduplicationResult:
        """Check if identifiers match an existing entity.

        Should be called before creating a new entity to prevent duplicates.

        Args:
            identifiers: Subject identifiers to check
            entity_type: Expected entity type
            tenant_id: Optional tenant scope (None = current context)

        Returns:
            DeduplicationResult indicating if duplicate found
        """
        # Get tenant from context if not provided
        if tenant_id is None:
            try:
                ctx = get_current_context()
                tenant_id = ctx.tenant_id
            except Exception:
                pass  # No context available, proceed without tenant scope

        # Use matcher for exact match on canonical identifiers
        result = await self._matcher.match_exact(identifiers, entity_type)

        if result.entity_id is not None:
            logger.info(
                "duplicate_detected",
                existing_entity_id=str(result.entity_id),
                match_type=result.match_type.value,
                identifiers=result.matched_identifiers,
            )
            return DeduplicationResult(
                is_duplicate=True,
                existing_entity_id=result.entity_id,
                match_confidence=result.confidence,
                matching_identifiers=result.matched_identifiers,
            )

        return DeduplicationResult(is_duplicate=False)

    async def find_potential_duplicates(
        self,
        entity_id: UUID,
        min_confidence: float = 0.70,
    ) -> list[DuplicateCandidate]:
        """Find potential duplicates of an existing entity.

        Scans the database for entities that might be duplicates
        based on fuzzy matching.

        Args:
            entity_id: Entity to find duplicates for
            min_confidence: Minimum confidence threshold

        Returns:
            List of potential duplicate candidates
        """
        # Get the source entity
        stmt = select(Entity).where(Entity.entity_id == entity_id)
        result = await self._session.execute(stmt)
        source = result.scalar_one_or_none()

        if source is None:
            logger.warning("entity_not_found", entity_id=str(entity_id))
            return []

        # Build identifiers from source entity
        identifiers = self._entity_to_identifiers(source)
        if not identifiers.full_name:
            # Can't fuzzy match without a name
            return []

        # Get candidates of the same type
        stmt = select(Entity).where(
            Entity.entity_type == source.entity_type,
            Entity.entity_id != entity_id,
        )
        result = await self._session.execute(stmt)
        candidates = result.scalars().all()

        duplicates: list[DuplicateCandidate] = []

        for candidate in candidates:
            confidence, matched_fields = self._matcher._calculate_similarity(
                identifiers, candidate
            )

            if confidence >= min_confidence:
                # Determine matched identifiers from exact matches
                matched_ids = self._find_matching_identifiers(source, candidate)

                duplicates.append(
                    DuplicateCandidate(
                        entity_id=candidate.entity_id,
                        match_confidence=confidence,
                        match_type=MatchType.EXACT if matched_ids else MatchType.FUZZY,
                        matching_identifiers=matched_ids,
                    )
                )

        # Sort by confidence descending
        duplicates.sort(key=lambda x: x.match_confidence, reverse=True)
        return duplicates

    async def merge_entities(
        self,
        source_id: UUID,
        target_id: UUID,
        reason: str = "duplicate_detected",
    ) -> MergeResult:
        """Merge two entities into one.

        The older entity (by UUIDv7 timestamp) becomes the canonical entity.
        The newer entity is marked as merged and all its data is migrated.

        Args:
            source_id: First entity ID
            target_id: Second entity ID
            reason: Reason for the merge

        Returns:
            MergeResult with merge statistics
        """
        # Load both entities
        source = await self._get_entity(source_id)
        target = await self._get_entity(target_id)

        if source is None or target is None:
            raise ValueError(f"Entity not found: {source_id if source is None else target_id}")

        # Determine canonical (older by UUIDv7 has lower value)
        if source_id < target_id:
            canonical = source
            duplicate = target
        else:
            canonical = target
            duplicate = source

        logger.info(
            "entity_merge_started",
            canonical_id=str(canonical.entity_id),
            duplicate_id=str(duplicate.entity_id),
            reason=reason,
        )

        # 1. Merge canonical identifiers
        merged_identifiers = self._merge_identifiers(
            canonical.canonical_identifiers,
            duplicate.canonical_identifiers,
        )
        new_identifier_keys = [
            k for k in duplicate.canonical_identifiers.keys()
            if k not in canonical.canonical_identifiers
        ]

        canonical.canonical_identifiers = merged_identifiers

        # 2. Update relationships
        rel_count = await self._update_relationships(
            duplicate.entity_id, canonical.entity_id
        )

        # 3. Migrate profiles
        profile_count = await self._migrate_profiles(
            duplicate.entity_id, canonical.entity_id
        )

        # 4. Mark duplicate as merged
        await self._mark_merged(duplicate.entity_id, canonical.entity_id)

        # 5. Commit changes
        await self._session.flush()

        # 6. Audit log
        if self._audit:
            await self._audit.log_event(
                event_type=AuditEventType.ENTITY_MERGED,
                entity_id=canonical.entity_id,
                event_data={
                    "merged_from": str(duplicate.entity_id),
                    "reason": reason,
                    "relationships_updated": rel_count,
                    "profiles_migrated": profile_count,
                    "identifiers_merged": new_identifier_keys,
                },
            )

        logger.info(
            "entity_merge_completed",
            canonical_id=str(canonical.entity_id),
            merged_id=str(duplicate.entity_id),
            relationships_updated=rel_count,
            profiles_migrated=profile_count,
        )

        return MergeResult(
            canonical_entity_id=canonical.entity_id,
            merged_entity_id=duplicate.entity_id,
            relationships_updated=rel_count,
            profiles_migrated=profile_count,
            identifiers_merged=new_identifier_keys,
            reason=reason,
        )

    async def on_identifier_added(
        self,
        entity_id: UUID,
        identifier_type: IdentifierType,
        identifier_value: str,
    ) -> MergeResult | None:
        """Handle when a new identifier is added to an entity.

        Checks if the new identifier matches another entity,
        triggering a merge if so.

        Args:
            entity_id: Entity that received the new identifier
            identifier_type: Type of identifier added
            identifier_value: Value of the identifier

        Returns:
            MergeResult if merge was triggered, None otherwise
        """
        # Get the current entity
        entity = await self._get_entity(entity_id)
        if entity is None:
            return None

        # Check for exact match on this identifier
        identifiers = SubjectIdentifiers()

        # Set the appropriate identifier field
        if identifier_type == IdentifierType.SSN:
            identifiers.ssn = identifier_value
        elif identifier_type == IdentifierType.EIN:
            identifiers.ein = identifier_value
        elif identifier_type == IdentifierType.PASSPORT:
            identifiers.passport = identifier_value
        elif identifier_type == IdentifierType.DRIVERS_LICENSE:
            identifiers.drivers_license = identifier_value
        elif identifier_type == IdentifierType.EMAIL:
            identifiers.email = identifier_value
        elif identifier_type == IdentifierType.PHONE:
            identifiers.phone = identifier_value
        else:
            return None  # Unknown identifier type

        # Find matching entity (excluding self)
        entity_type = EntityType(entity.entity_type)
        match_result = await self._matcher.match_exact(identifiers, entity_type)

        if match_result.entity_id is not None and match_result.entity_id != entity_id:
            # Found a matching entity - trigger merge
            logger.info(
                "identifier_match_triggered_merge",
                entity_id=str(entity_id),
                matched_entity_id=str(match_result.entity_id),
                identifier_type=identifier_type.value,
            )
            return await self.merge_entities(
                entity_id,
                match_result.entity_id,
                reason=f"identifier_enrichment_{identifier_type.value}",
            )

        return None

    async def _get_entity(self, entity_id: UUID) -> Entity | None:
        """Get entity by ID."""
        stmt = select(Entity).where(Entity.entity_id == entity_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _update_relationships(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
    ) -> int:
        """Update all relationships pointing to/from merged entity.

        Args:
            from_entity_id: Merged (duplicate) entity ID
            to_entity_id: Canonical entity ID

        Returns:
            Count of updated relationships
        """
        count = 0

        # Update from_entity_id references
        stmt = (
            update(EntityRelation)
            .where(EntityRelation.from_entity_id == from_entity_id)
            .values(from_entity_id=to_entity_id)
        )
        result = await self._session.execute(stmt)
        count += result.rowcount

        # Update to_entity_id references
        stmt = (
            update(EntityRelation)
            .where(EntityRelation.to_entity_id == from_entity_id)
            .values(to_entity_id=to_entity_id)
        )
        result = await self._session.execute(stmt)
        count += result.rowcount

        return count

    async def _migrate_profiles(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
    ) -> int:
        """Migrate all profiles from merged entity to canonical.

        Args:
            from_entity_id: Merged (duplicate) entity ID
            to_entity_id: Canonical entity ID

        Returns:
            Count of migrated profiles
        """
        stmt = (
            update(EntityProfile)
            .where(EntityProfile.entity_id == from_entity_id)
            .values(entity_id=to_entity_id)
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def _mark_merged(
        self,
        merged_entity_id: UUID,
        canonical_entity_id: UUID,
    ) -> None:
        """Mark an entity as merged into another.

        Args:
            merged_entity_id: Entity that was merged (duplicate)
            canonical_entity_id: Entity it was merged into
        """
        entity = await self._get_entity(merged_entity_id)
        if entity:
            # Store merge info in canonical_identifiers
            entity.canonical_identifiers["_merged"] = {
                "into": str(canonical_entity_id),
                "merged_at": "auto",  # Would use datetime in production
            }

    def _merge_identifiers(
        self,
        canonical_ids: dict,
        duplicate_ids: dict,
    ) -> dict:
        """Merge identifier dictionaries.

        Preserves canonical values, adds new values from duplicate.

        Args:
            canonical_ids: Identifiers from canonical entity
            duplicate_ids: Identifiers from duplicate entity

        Returns:
            Merged identifier dictionary
        """
        merged = dict(canonical_ids)

        for key, value in duplicate_ids.items():
            if key.startswith("_"):
                continue  # Skip internal keys

            if key not in merged:
                merged[key] = value
            elif isinstance(value, list) and isinstance(merged[key], list):
                # Merge lists (e.g., name_variants)
                merged[key] = list(set(merged[key] + value))

        return merged

    def _entity_to_identifiers(self, entity: Entity) -> SubjectIdentifiers:
        """Convert entity to SubjectIdentifiers for matching.

        Args:
            entity: Entity to convert

        Returns:
            SubjectIdentifiers populated from entity
        """
        ids = entity.canonical_identifiers

        # Extract name
        full_name = None
        if "full_name" in ids:
            name = ids["full_name"]
            full_name = name.get("value") if isinstance(name, dict) else str(name)

        # Extract SSN
        ssn = None
        if "ssn" in ids:
            ssn_data = ids["ssn"]
            ssn = ssn_data.get("value") if isinstance(ssn_data, dict) else str(ssn_data)

        # Extract EIN
        ein = None
        if "ein" in ids:
            ein_data = ids["ein"]
            ein = ein_data.get("value") if isinstance(ein_data, dict) else str(ein_data)

        # Extract DOB
        dob = None
        if "date_of_birth" in ids:
            dob_data = ids["date_of_birth"]
            dob_str = dob_data.get("value") if isinstance(dob_data, dict) else str(dob_data)
            # Would parse to date in production

        return SubjectIdentifiers(
            full_name=full_name,
            ssn=ssn,
            ein=ein,
        )

    def _find_matching_identifiers(
        self,
        entity1: Entity,
        entity2: Entity,
    ) -> list[IdentifierType]:
        """Find which canonical identifiers match between two entities.

        Args:
            entity1: First entity
            entity2: Second entity

        Returns:
            List of matching identifier types
        """
        matches: list[IdentifierType] = []
        ids1 = entity1.canonical_identifiers
        ids2 = entity2.canonical_identifiers

        # Check each canonical identifier type
        for id_type in IdentifierType:
            key = id_type.value

            if key in ids1 and key in ids2:
                val1 = ids1[key]
                val2 = ids2[key]

                # Extract values from dict format
                if isinstance(val1, dict):
                    val1 = val1.get("value", "")
                if isinstance(val2, dict):
                    val2 = val2.get("value", "")

                # Normalize and compare
                norm1 = self._matcher._normalize_identifier(id_type, str(val1))
                norm2 = self._matcher._normalize_identifier(id_type, str(val2))

                if norm1 and norm2 and norm1 == norm2:
                    matches.append(id_type)

        return matches
