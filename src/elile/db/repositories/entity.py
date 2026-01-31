"""Entity repository for managing entity records."""

from uuid import UUID

from sqlalchemy import select

from elile.db.models.entity import Entity, EntityType
from elile.db.repositories.base import BaseRepository


class EntityRepository(BaseRepository[Entity, UUID]):
    """Repository for Entity model operations.

    Provides entity-specific queries in addition to base CRUD operations.
    """

    model = Entity

    async def get_by_type(
        self,
        entity_type: EntityType,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Entity]:
        """Get entities by type.

        Args:
            entity_type: Type of entity to filter by
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of entities matching the type
        """
        stmt = select(Entity).where(Entity.entity_type == entity_type.value)

        stmt = stmt.order_by(Entity.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_individuals(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Entity]:
        """Get individual (person) entities.

        Args:
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of individual entities
        """
        return await self.get_by_type(
            EntityType.INDIVIDUAL,
            limit=limit,
            offset=offset,
        )

    async def get_organizations(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Entity]:
        """Get organization entities.

        Args:
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of organization entities
        """
        return await self.get_by_type(
            EntityType.ORGANIZATION,
            limit=limit,
            offset=offset,
        )

    async def count_by_type(self, entity_type: EntityType) -> int:
        """Count entities by type.

        Args:
            entity_type: Type of entity to count

        Returns:
            Number of entities
        """
        from sqlalchemy import func

        stmt = select(func.count(Entity.entity_id)).where(Entity.entity_type == entity_type.value)
        result = await self.db.execute(stmt)
        return result.scalar() or 0
