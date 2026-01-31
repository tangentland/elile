"""Entity matching and resolution engine.

This module provides the EntityMatcher class for resolving subjects
to existing entities or determining that new entities should be created.
"""

import re
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from elile.agent.state import ServiceTier
from elile.core.logging import get_logger
from elile.db.models.entity import Entity, EntityType

from .types import (
    IdentifierType,
    MatchedField,
    MatchResult,
    MatchType,
    ResolutionDecision,
    SubjectIdentifiers,
)

logger = get_logger(__name__)


# Matching thresholds
EXACT_MATCH_CONFIDENCE = 1.0
FUZZY_MATCH_THRESHOLD_STANDARD = 0.85  # Auto-match in Standard tier
FUZZY_MATCH_THRESHOLD_REVIEW = 0.70  # Minimum for Enhanced tier review
FUZZY_MATCH_THRESHOLD_REJECT = 0.70  # Below this, create new entity


class EntityMatcher:
    """Entity matching engine for resolution.

    Provides exact and fuzzy matching of subject identifiers
    against existing entities in the database.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the entity matcher.

        Args:
            session: Database session for queries
        """
        self._session = session

    async def resolve(
        self,
        identifiers: SubjectIdentifiers,
        entity_type: EntityType = EntityType.INDIVIDUAL,
        tier: ServiceTier = ServiceTier.STANDARD,
    ) -> MatchResult:
        """Resolve subject identifiers to an entity.

        Attempts exact match first, then fuzzy match if no exact match found.
        Resolution decision depends on confidence and service tier.

        Args:
            identifiers: Subject identifiers to match
            entity_type: Expected entity type
            tier: Service tier (affects review requirements)

        Returns:
            MatchResult with entity_id (if matched) and decision
        """
        # Try exact match first
        exact_result = await self.match_exact(identifiers, entity_type)
        if exact_result.entity_id is not None:
            logger.debug(
                "entity_exact_match",
                entity_id=str(exact_result.entity_id),
                matched_identifiers=[i.value for i in exact_result.matched_identifiers],
            )
            return exact_result

        # Try fuzzy match
        fuzzy_result = await self.match_fuzzy(identifiers, entity_type, tier)
        logger.debug(
            "entity_fuzzy_match",
            entity_id=str(fuzzy_result.entity_id) if fuzzy_result.entity_id else None,
            confidence=fuzzy_result.confidence,
            decision=fuzzy_result.decision.value,
        )
        return fuzzy_result

    async def match_exact(
        self,
        identifiers: SubjectIdentifiers,
        entity_type: EntityType = EntityType.INDIVIDUAL,
    ) -> MatchResult:
        """Attempt exact match on canonical identifiers.

        Args:
            identifiers: Subject identifiers to match
            entity_type: Expected entity type

        Returns:
            MatchResult with entity_id if exact match found
        """
        canonical = identifiers.get_canonical_identifiers()
        if not canonical:
            return MatchResult(
                match_type=MatchType.NEW,
                confidence=0.0,
                decision=ResolutionDecision.CREATE_NEW,
                resolution_notes="No canonical identifiers provided",
            )

        # Try each canonical identifier
        for id_type, value in canonical.items():
            # Skip soft identifiers for exact match
            if id_type in (IdentifierType.EMAIL, IdentifierType.PHONE):
                continue

            entity = await self._find_by_identifier(id_type, value, entity_type)
            if entity:
                return MatchResult(
                    entity_id=entity.entity_id,
                    match_type=MatchType.EXACT,
                    confidence=EXACT_MATCH_CONFIDENCE,
                    decision=ResolutionDecision.MATCH_EXISTING,
                    matched_identifiers=[id_type],
                    resolution_notes=f"Exact match on {id_type.value}",
                )

        # No exact match found
        return MatchResult(
            match_type=MatchType.NEW,
            confidence=0.0,
            decision=ResolutionDecision.CREATE_NEW,
            resolution_notes="No exact match on canonical identifiers",
        )

    async def match_fuzzy(
        self,
        identifiers: SubjectIdentifiers,
        entity_type: EntityType = EntityType.INDIVIDUAL,
        tier: ServiceTier = ServiceTier.STANDARD,
    ) -> MatchResult:
        """Attempt fuzzy match on name, DOB, and address.

        Args:
            identifiers: Subject identifiers to match
            entity_type: Expected entity type
            tier: Service tier (affects review threshold)

        Returns:
            MatchResult with entity_id if fuzzy match found
        """
        # Need at least a name to fuzzy match
        if not identifiers.full_name:
            return MatchResult(
                match_type=MatchType.NEW,
                confidence=0.0,
                decision=ResolutionDecision.CREATE_NEW,
                resolution_notes="No name provided for fuzzy matching",
            )

        # Find candidate entities to compare
        candidates = await self._find_candidates(identifiers, entity_type)
        if not candidates:
            return MatchResult(
                match_type=MatchType.NEW,
                confidence=0.0,
                decision=ResolutionDecision.CREATE_NEW,
                resolution_notes="No candidate entities found",
            )

        # Calculate similarity for each candidate
        best_match: Entity | None = None
        best_confidence = 0.0
        best_fields: list[MatchedField] = []

        for candidate in candidates:
            confidence, matched_fields = self._calculate_similarity(identifiers, candidate)
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = candidate
                best_fields = matched_fields

        # Determine decision based on confidence and tier
        if best_confidence >= FUZZY_MATCH_THRESHOLD_STANDARD:
            # High confidence match
            return MatchResult(
                entity_id=best_match.entity_id if best_match else None,
                match_type=MatchType.FUZZY,
                confidence=best_confidence,
                decision=ResolutionDecision.MATCH_EXISTING,
                matched_fields=best_fields,
                resolution_notes=f"High confidence fuzzy match ({best_confidence:.2f})",
            )
        elif best_confidence >= FUZZY_MATCH_THRESHOLD_REVIEW:
            # Medium confidence - tier determines behavior
            if tier == ServiceTier.ENHANCED:
                return MatchResult(
                    entity_id=best_match.entity_id if best_match else None,
                    match_type=MatchType.FUZZY,
                    confidence=best_confidence,
                    decision=ResolutionDecision.PENDING_REVIEW,
                    requires_review=True,
                    matched_fields=best_fields,
                    resolution_notes=f"Medium confidence ({best_confidence:.2f}) - queued for review",
                )
            else:
                # Standard tier - create new entity
                return MatchResult(
                    match_type=MatchType.NEW,
                    confidence=best_confidence,
                    decision=ResolutionDecision.CREATE_NEW,
                    matched_fields=best_fields,
                    resolution_notes=f"Medium confidence ({best_confidence:.2f}) - creating new entity",
                )
        else:
            # Low confidence - create new entity
            return MatchResult(
                match_type=MatchType.NEW,
                confidence=best_confidence,
                decision=ResolutionDecision.CREATE_NEW,
                matched_fields=best_fields if best_fields else [],
                resolution_notes=f"Low confidence ({best_confidence:.2f}) - creating new entity",
            )

    async def _find_by_identifier(
        self,
        id_type: IdentifierType,
        value: str,
        entity_type: EntityType,
    ) -> Entity | None:
        """Find entity by canonical identifier.

        Args:
            id_type: Type of identifier
            value: Identifier value
            entity_type: Expected entity type

        Returns:
            Entity if found, None otherwise
        """
        # Normalize the value
        normalized = self._normalize_identifier(id_type, value)

        # Query entities with matching identifier
        # Note: This uses JSON containment which may need optimization
        stmt = select(Entity).where(
            Entity.entity_type == entity_type.value,
        )
        result = await self._session.execute(stmt)
        entities = result.scalars().all()

        # Check each entity's canonical_identifiers
        for entity in entities:
            stored = entity.canonical_identifiers.get(id_type.value, {})
            if isinstance(stored, dict):
                stored_value = stored.get("value", "")
            else:
                stored_value = str(stored)

            if self._normalize_identifier(id_type, stored_value) == normalized:
                return entity

        return None

    async def _find_candidates(
        self,
        identifiers: SubjectIdentifiers,
        entity_type: EntityType,
        limit: int = 100,
    ) -> Sequence[Entity]:
        """Find candidate entities for fuzzy matching.

        Args:
            identifiers: Subject identifiers
            entity_type: Expected entity type
            limit: Maximum candidates to return

        Returns:
            List of candidate entities
        """
        # Get entities of the right type
        # In production, this would use more sophisticated filtering
        stmt = select(Entity).where(
            Entity.entity_type == entity_type.value,
        ).limit(limit)

        result = await self._session.execute(stmt)
        return result.scalars().all()

    def _calculate_similarity(
        self,
        identifiers: SubjectIdentifiers,
        entity: Entity,
    ) -> tuple[float, list[MatchedField]]:
        """Calculate similarity score between subject and entity.

        Uses weighted combination of:
        - Name similarity (40%)
        - DOB match (35%)
        - Address similarity (25%)

        Args:
            identifiers: Subject identifiers
            entity: Entity to compare

        Returns:
            Tuple of (confidence score, list of matched fields)
        """
        scores: list[tuple[float, float]] = []  # (score, weight)
        matched_fields: list[MatchedField] = []

        # Extract entity identifiers
        entity_name = self._get_entity_name(entity)
        entity_dob = self._get_entity_dob(entity)
        entity_address = self._get_entity_address(entity)

        # Name similarity (weight: 0.4)
        if identifiers.full_name and entity_name:
            name_sim = self._string_similarity(identifiers.full_name, entity_name)
            scores.append((name_sim, 0.4))
            if name_sim > 0.5:
                matched_fields.append(MatchedField(
                    field_name="full_name",
                    source_value=identifiers.full_name,
                    matched_value=entity_name,
                    similarity=name_sim,
                ))

        # DOB match (weight: 0.35)
        if identifiers.date_of_birth and entity_dob:
            # Compare as strings (entity stores DOB as ISO string)
            source_dob_str = str(identifiers.date_of_birth)
            dob_match = 1.0 if source_dob_str == entity_dob else 0.0
            scores.append((dob_match, 0.35))
            if dob_match == 1.0:
                matched_fields.append(MatchedField(
                    field_name="date_of_birth",
                    source_value=str(identifiers.date_of_birth),
                    matched_value=str(entity_dob),
                    similarity=1.0,
                ))

        # Address similarity (weight: 0.25)
        if identifiers.street_address and entity_address:
            addr_sim = self._address_similarity(identifiers, entity_address)
            scores.append((addr_sim, 0.25))
            if addr_sim > 0.5:
                matched_fields.append(MatchedField(
                    field_name="address",
                    source_value=identifiers.street_address,
                    matched_value=entity_address,
                    similarity=addr_sim,
                ))

        # Calculate weighted average
        if not scores:
            return 0.0, []

        total_weight = sum(w for _, w in scores)
        if total_weight == 0:
            return 0.0, matched_fields

        weighted_sum = sum(s * w for s, w in scores)
        confidence = weighted_sum / total_weight

        return confidence, matched_fields

    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity using Jaro-Winkler algorithm.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Similarity score 0.0 - 1.0
        """
        # Normalize strings
        s1 = s1.lower().strip()
        s2 = s2.lower().strip()

        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        # Use Jaro similarity as base
        jaro = self._jaro_similarity(s1, s2)

        # Jaro-Winkler prefix bonus
        prefix_len = 0
        for i in range(min(4, len(s1), len(s2))):
            if s1[i] == s2[i]:
                prefix_len += 1
            else:
                break

        # Winkler modification
        return jaro + (prefix_len * 0.1 * (1 - jaro))

    def _jaro_similarity(self, s1: str, s2: str) -> float:
        """Calculate Jaro similarity.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Jaro similarity 0.0 - 1.0
        """
        len1, len2 = len(s1), len(s2)
        if len1 == 0 and len2 == 0:
            return 1.0

        match_distance = max(len1, len2) // 2 - 1
        if match_distance < 0:
            match_distance = 0

        s1_matches = [False] * len1
        s2_matches = [False] * len2

        matches = 0
        transpositions = 0

        # Find matches
        for i in range(len1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len2)

            for j in range(start, end):
                if s2_matches[j] or s1[i] != s2[j]:
                    continue
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

        if matches == 0:
            return 0.0

        # Count transpositions
        k = 0
        for i in range(len1):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

        return (
            matches / len1 + matches / len2 + (matches - transpositions / 2) / matches
        ) / 3

    def _address_similarity(
        self,
        identifiers: SubjectIdentifiers,
        entity_address: str,
    ) -> float:
        """Calculate address similarity.

        Args:
            identifiers: Subject identifiers with address
            entity_address: Entity's address string

        Returns:
            Similarity score 0.0 - 1.0
        """
        # Combine subject address components
        subject_addr = " ".join(filter(None, [
            identifiers.street_address,
            identifiers.city,
            identifiers.state,
            identifiers.postal_code,
        ]))

        return self._string_similarity(subject_addr, entity_address)

    def _normalize_identifier(self, id_type: IdentifierType, value: str) -> str:
        """Normalize identifier for comparison.

        Args:
            id_type: Type of identifier
            value: Raw identifier value

        Returns:
            Normalized identifier value
        """
        if not value:
            return ""

        # Remove all non-alphanumeric characters
        normalized = re.sub(r"[^a-zA-Z0-9]", "", value)

        # Type-specific normalization
        if id_type == IdentifierType.SSN:
            # SSN: just digits
            normalized = re.sub(r"\D", "", value)
        elif id_type == IdentifierType.EIN:
            # EIN: just digits
            normalized = re.sub(r"\D", "", value)
        elif id_type == IdentifierType.PHONE:
            # Phone: digits only, remove country code prefix
            normalized = re.sub(r"\D", "", value)
            if normalized.startswith("1") and len(normalized) == 11:
                normalized = normalized[1:]
        elif id_type == IdentifierType.EMAIL:
            # Email: lowercase
            normalized = value.lower().strip()

        return normalized

    def _get_entity_name(self, entity: Entity) -> str | None:
        """Extract name from entity canonical identifiers."""
        identifiers = entity.canonical_identifiers
        if "full_name" in identifiers:
            name = identifiers["full_name"]
            return name.get("value") if isinstance(name, dict) else str(name)
        if "name_variants" in identifiers:
            variants = identifiers["name_variants"]
            if isinstance(variants, list) and variants:
                first = variants[0]
                return first.get("value") if isinstance(first, dict) else str(first)
        return None

    def _get_entity_dob(self, entity: Entity) -> str | None:
        """Extract date of birth from entity canonical identifiers."""
        identifiers = entity.canonical_identifiers
        if "date_of_birth" in identifiers:
            dob = identifiers["date_of_birth"]
            return dob.get("value") if isinstance(dob, dict) else str(dob)
        return None

    def _get_entity_address(self, entity: Entity) -> str | None:
        """Extract address from entity canonical identifiers."""
        identifiers = entity.canonical_identifiers
        if "address" in identifiers:
            addr = identifiers["address"]
            return addr.get("value") if isinstance(addr, dict) else str(addr)
        return None
