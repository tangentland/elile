"""Profile repository for managing entity profile records."""

from uuid import UUID

from sqlalchemy import select

from elile.db.models.profile import EntityProfile, ProfileTrigger
from elile.db.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[EntityProfile, UUID]):
    """Repository for EntityProfile model operations.

    Provides profile-specific queries in addition to base CRUD operations.
    """

    model = EntityProfile

    async def get_by_entity(
        self,
        entity_id: UUID,
        *,
        limit: int = 50,
    ) -> list[EntityProfile]:
        """Get profiles for an entity.

        Args:
            entity_id: Entity to get profiles for
            limit: Maximum profiles to return

        Returns:
            List of profiles ordered by version (newest first)
        """
        stmt = select(EntityProfile).where(EntityProfile.entity_id == entity_id)
        stmt = stmt.order_by(EntityProfile.version.desc()).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest(self, entity_id: UUID) -> EntityProfile | None:
        """Get the latest profile for an entity.

        Args:
            entity_id: Entity to get latest profile for

        Returns:
            Latest profile or None if no profiles exist
        """
        stmt = (
            select(EntityProfile)
            .where(EntityProfile.entity_id == entity_id)
            .order_by(EntityProfile.version.desc())
            .limit(1)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_version(self, entity_id: UUID, version: int) -> EntityProfile | None:
        """Get a specific profile version for an entity.

        Args:
            entity_id: Entity ID
            version: Version number to retrieve

        Returns:
            Profile with specified version or None
        """
        stmt = (
            select(EntityProfile)
            .where(EntityProfile.entity_id == entity_id)
            .where(EntityProfile.version == version)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_trigger(
        self,
        trigger_type: ProfileTrigger,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityProfile]:
        """Get profiles by trigger type.

        Args:
            trigger_type: Profile trigger to filter by
            limit: Maximum profiles to return
            offset: Number to skip

        Returns:
            List of profiles with the given trigger type
        """
        stmt = select(EntityProfile).where(EntityProfile.trigger_type == trigger_type.value)

        stmt = stmt.order_by(EntityProfile.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_screening_profiles(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityProfile]:
        """Get profiles created from screening.

        Args:
            limit: Maximum profiles to return
            offset: Number to skip

        Returns:
            List of screening profiles
        """
        return await self.get_by_trigger(
            ProfileTrigger.SCREENING,
            limit=limit,
            offset=offset,
        )

    async def get_monitoring_profiles(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityProfile]:
        """Get profiles created from monitoring.

        Args:
            limit: Maximum profiles to return
            offset: Number to skip

        Returns:
            List of monitoring profiles
        """
        return await self.get_by_trigger(
            ProfileTrigger.MONITORING,
            limit=limit,
            offset=offset,
        )

    async def get_next_version(self, entity_id: UUID) -> int:
        """Get the next version number for an entity's profile.

        Args:
            entity_id: Entity ID

        Returns:
            Next version number (1 if no profiles exist)
        """
        from sqlalchemy import func

        stmt = select(func.max(EntityProfile.version)).where(EntityProfile.entity_id == entity_id)
        result = await self.db.execute(stmt)
        max_version = result.scalar()

        return (max_version or 0) + 1

    async def get_by_trigger_id(
        self,
        trigger_id: UUID,
    ) -> list[EntityProfile]:
        """Get profiles by trigger ID.

        Args:
            trigger_id: The screening or monitoring run ID

        Returns:
            List of profiles created by this trigger
        """
        stmt = (
            select(EntityProfile)
            .where(EntityProfile.trigger_id == trigger_id)
            .order_by(EntityProfile.created_at.desc())
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())
