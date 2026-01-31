"""Identifier management for canonical entities.

This module provides the IdentifierManager class for managing
entity identifiers with confidence tracking and history.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from elile.core.logging import get_logger
from elile.db.models.entity import Entity

from .types import IdentifierRecord, IdentifierType

logger = get_logger(__name__)


class IdentifierUpdate(BaseModel):
    """Represents an identifier update operation."""

    identifier_type: IdentifierType
    value: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    source: str
    country: str | None = None  # For passport, national ID
    state: str | None = None  # For driver's license


class IdentifierManager:
    """Manager for entity identifiers.

    Handles adding, updating, and retrieving identifiers
    for canonical entities with confidence tracking.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the identifier manager.

        Args:
            session: Database session for operations
        """
        self._session = session

    async def add_identifier(
        self,
        entity_id: UUID,
        identifier_type: IdentifierType,
        value: str,
        confidence: float = 1.0,
        source: str = "unknown",
        country: str | None = None,
        state: str | None = None,
    ) -> bool:
        """Add or update an identifier for an entity.

        If identifier already exists, updates confidence if higher.
        Identifiers are never deleted (append-only).

        Args:
            entity_id: Entity to add identifier to
            identifier_type: Type of identifier
            value: Identifier value
            confidence: Confidence score 0.0-1.0
            source: Where identifier was discovered
            country: Country for passport/national ID
            state: State for driver's license

        Returns:
            True if identifier was added/updated, False if entity not found
        """
        entity = await self._get_entity(entity_id)
        if entity is None:
            logger.warning("entity_not_found", entity_id=str(entity_id))
            return False

        # Get current identifiers
        identifiers = entity.canonical_identifiers.copy()

        # Create identifier record
        record = IdentifierRecord(
            identifier_type=identifier_type,
            value=value,
            confidence=confidence,
            discovered_at=datetime.utcnow(),
            source=source,
            country=country,
            state=state,
        )

        key = identifier_type.value

        # Handle name variants specially (they're a list)
        if identifier_type == IdentifierType.PHONE or key == "name_variants":
            # For name variants, maintain a list
            if key not in identifiers:
                identifiers[key] = []

            # Check if value already exists
            existing = identifiers[key]
            if isinstance(existing, list):
                found = False
                for i, item in enumerate(existing):
                    item_value = item.get("value") if isinstance(item, dict) else str(item)
                    if item_value == value:
                        # Update confidence if higher
                        if isinstance(item, dict) and confidence > item.get("confidence", 0):
                            existing[i] = record.to_dict()
                        found = True
                        break

                if not found:
                    existing.append(record.to_dict())
        else:
            # Single value identifiers
            if key in identifiers:
                existing = identifiers[key]
                existing_conf = existing.get("confidence", 0) if isinstance(existing, dict) else 0

                if confidence > existing_conf:
                    # Update with higher confidence value
                    identifiers[key] = record.to_dict()
                    logger.debug(
                        "identifier_confidence_updated",
                        entity_id=str(entity_id),
                        identifier_type=key,
                        old_confidence=existing_conf,
                        new_confidence=confidence,
                    )
            else:
                # Add new identifier
                identifiers[key] = record.to_dict()

        # Update entity
        entity.canonical_identifiers = identifiers
        await self._session.flush()

        logger.info(
            "identifier_added",
            entity_id=str(entity_id),
            identifier_type=key,
            source=source,
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
        entity = await self._get_entity(entity_id)
        if entity is None:
            return {}

        result: dict[IdentifierType, IdentifierRecord] = {}
        identifiers = entity.canonical_identifiers

        for key, value in identifiers.items():
            if key.startswith("_"):
                continue  # Skip internal keys

            try:
                id_type = IdentifierType(key)
            except ValueError:
                continue  # Skip unknown types

            if isinstance(value, dict):
                result[id_type] = IdentifierRecord(
                    identifier_type=id_type,
                    value=value.get("value", ""),
                    confidence=value.get("confidence", 1.0),
                    discovered_at=datetime.fromisoformat(
                        value.get("discovered_at", datetime.utcnow().isoformat())
                    ),
                    source=value.get("source", "unknown"),
                    country=value.get("country"),
                    state=value.get("state"),
                )
            elif isinstance(value, list) and value:
                # For list types, return the first/primary value
                first = value[0]
                if isinstance(first, dict):
                    result[id_type] = IdentifierRecord(
                        identifier_type=id_type,
                        value=first.get("value", ""),
                        confidence=first.get("confidence", 1.0),
                        discovered_at=datetime.fromisoformat(
                            first.get("discovered_at", datetime.utcnow().isoformat())
                        ),
                        source=first.get("source", "unknown"),
                    )

        return result

    async def get_identifier(
        self,
        entity_id: UUID,
        identifier_type: IdentifierType,
    ) -> IdentifierRecord | None:
        """Get a specific identifier for an entity.

        Args:
            entity_id: Entity to get identifier from
            identifier_type: Type of identifier to get

        Returns:
            IdentifierRecord or None if not found
        """
        identifiers = await self.get_identifiers(entity_id)
        return identifiers.get(identifier_type)

    async def has_identifier(
        self,
        entity_id: UUID,
        identifier_type: IdentifierType,
    ) -> bool:
        """Check if entity has a specific identifier type.

        Args:
            entity_id: Entity to check
            identifier_type: Type of identifier

        Returns:
            True if identifier exists
        """
        entity = await self._get_entity(entity_id)
        if entity is None:
            return False

        return identifier_type.value in entity.canonical_identifiers

    async def get_identifier_history(
        self,
        entity_id: UUID,
        identifier_type: IdentifierType,
    ) -> list[IdentifierRecord]:
        """Get history of an identifier (for list types like name variants).

        Args:
            entity_id: Entity to get history for
            identifier_type: Type of identifier

        Returns:
            List of identifier records
        """
        entity = await self._get_entity(entity_id)
        if entity is None:
            return []

        key = identifier_type.value
        if key not in entity.canonical_identifiers:
            return []

        value = entity.canonical_identifiers[key]

        # Handle list vs single value
        if isinstance(value, list):
            records = []
            for item in value:
                if isinstance(item, dict):
                    records.append(
                        IdentifierRecord(
                            identifier_type=identifier_type,
                            value=item.get("value", ""),
                            confidence=item.get("confidence", 1.0),
                            discovered_at=datetime.fromisoformat(
                                item.get("discovered_at", datetime.utcnow().isoformat())
                            ),
                            source=item.get("source", "unknown"),
                        )
                    )
            return records
        elif isinstance(value, dict):
            return [
                IdentifierRecord(
                    identifier_type=identifier_type,
                    value=value.get("value", ""),
                    confidence=value.get("confidence", 1.0),
                    discovered_at=datetime.fromisoformat(
                        value.get("discovered_at", datetime.utcnow().isoformat())
                    ),
                    source=value.get("source", "unknown"),
                )
            ]

        return []

    async def _get_entity(self, entity_id: UUID) -> Entity | None:
        """Get entity by ID."""
        stmt = select(Entity).where(Entity.entity_id == entity_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
