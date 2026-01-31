"""Cache repository for managing cached data source records."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select, update

from elile.db.models.cache import CachedDataSource, FreshnessStatus
from elile.db.repositories.base import BaseRepository


class CacheRepository(BaseRepository[CachedDataSource, UUID]):
    """Repository for CachedDataSource model operations.

    Provides cache-specific queries including freshness management
    and tenant-isolated access.
    """

    model = CachedDataSource

    async def get_by_provider(
        self,
        provider_id: str,
        *,
        tenant_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CachedDataSource]:
        """Get cached entries by provider.

        Args:
            provider_id: Data provider identifier
            tenant_id: Optional tenant filter
            limit: Maximum entries to return
            offset: Number to skip

        Returns:
            List of cached entries from the provider
        """
        stmt = select(CachedDataSource).where(CachedDataSource.provider_id == provider_id)

        if tenant_id is not None:
            stmt = stmt.where(CachedDataSource.customer_id == tenant_id)

        stmt = stmt.order_by(CachedDataSource.acquired_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_for_entity(
        self,
        entity_id: UUID,
        *,
        provider_id: str | None = None,
        fresh_only: bool = False,
    ) -> list[CachedDataSource]:
        """Get cached entries for an entity.

        Args:
            entity_id: Entity to get cached data for
            provider_id: Optional provider filter
            fresh_only: Only return fresh entries

        Returns:
            List of cached entries
        """
        stmt = select(CachedDataSource).where(CachedDataSource.entity_id == entity_id)

        if provider_id is not None:
            stmt = stmt.where(CachedDataSource.provider_id == provider_id)

        if fresh_only:
            stmt = stmt.where(CachedDataSource.freshness_status == FreshnessStatus.FRESH.value)

        stmt = stmt.order_by(CachedDataSource.acquired_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_check_type(
        self,
        entity_id: UUID,
        check_type: str,
        *,
        tenant_id: UUID | None = None,
    ) -> CachedDataSource | None:
        """Get cached entry by entity and check type.

        Args:
            entity_id: Entity to get cached data for
            check_type: Type of background check
            tenant_id: Optional tenant filter

        Returns:
            Cached entry or None if not found
        """
        stmt = select(CachedDataSource).where(
            CachedDataSource.entity_id == entity_id,
            CachedDataSource.check_type == check_type,
        )

        if tenant_id is not None:
            stmt = stmt.where(CachedDataSource.customer_id == tenant_id)

        stmt = stmt.order_by(CachedDataSource.acquired_at.desc()).limit(1)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_fresh_entry(
        self,
        entity_id: UUID,
        provider_id: str,
        check_type: str,
    ) -> CachedDataSource | None:
        """Get a fresh cached entry if available.

        Args:
            entity_id: Entity the data is for
            provider_id: Data provider
            check_type: Type of background check

        Returns:
            Fresh cached entry or None
        """
        now = datetime.now(UTC)
        stmt = (
            select(CachedDataSource)
            .where(CachedDataSource.entity_id == entity_id)
            .where(CachedDataSource.provider_id == provider_id)
            .where(CachedDataSource.check_type == check_type)
            .where(CachedDataSource.freshness_status == FreshnessStatus.FRESH.value)
            .where(CachedDataSource.fresh_until > now)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_stale(
        self,
        cache_id: UUID,
        *,
        commit: bool = True,
    ) -> bool:
        """Mark a cached entry as stale.

        Args:
            cache_id: Cache entry ID
            commit: Whether to commit

        Returns:
            True if updated, False if not found
        """
        stmt = (
            update(CachedDataSource)
            .where(CachedDataSource.cache_id == cache_id)
            .values(freshness_status=FreshnessStatus.STALE.value)
        )

        result = await self.db.execute(stmt)

        if commit:
            await self.db.commit()

        return result.rowcount > 0

    async def mark_expired(
        self,
        cache_id: UUID,
        *,
        commit: bool = True,
    ) -> bool:
        """Mark a cached entry as expired.

        Args:
            cache_id: Cache entry ID
            commit: Whether to commit

        Returns:
            True if updated, False if not found
        """
        stmt = (
            update(CachedDataSource)
            .where(CachedDataSource.cache_id == cache_id)
            .values(freshness_status=FreshnessStatus.EXPIRED.value)
        )

        result = await self.db.execute(stmt)

        if commit:
            await self.db.commit()

        return result.rowcount > 0

    async def update_freshness_batch(
        self,
        *,
        commit: bool = True,
    ) -> tuple[int, int]:
        """Update freshness for all entries based on their configured timestamps.

        Uses the fresh_until and stale_until timestamps configured on each entry
        to determine when they become stale or expired.

        Args:
            commit: Whether to commit

        Returns:
            Tuple of (stale_count, expired_count)
        """
        now = datetime.now(UTC)

        # Mark expired (past stale_until)
        expired_stmt = (
            update(CachedDataSource)
            .where(CachedDataSource.stale_until < now)
            .where(CachedDataSource.freshness_status != FreshnessStatus.EXPIRED.value)
            .values(freshness_status=FreshnessStatus.EXPIRED.value)
        )
        expired_result = await self.db.execute(expired_stmt)

        # Mark stale (past fresh_until but not yet past stale_until)
        stale_stmt = (
            update(CachedDataSource)
            .where(CachedDataSource.fresh_until < now)
            .where(CachedDataSource.stale_until >= now)
            .where(CachedDataSource.freshness_status == FreshnessStatus.FRESH.value)
            .values(freshness_status=FreshnessStatus.STALE.value)
        )
        stale_result = await self.db.execute(stale_stmt)

        if commit:
            await self.db.commit()

        return stale_result.rowcount, expired_result.rowcount

    async def delete_expired(
        self,
        older_than: timedelta | None = None,
        *,
        commit: bool = True,
    ) -> int:
        """Delete expired cache entries.

        Args:
            older_than: Only delete entries older than this duration
            commit: Whether to commit

        Returns:
            Number of entries deleted
        """
        stmt = delete(CachedDataSource).where(
            CachedDataSource.freshness_status == FreshnessStatus.EXPIRED.value
        )

        if older_than is not None:
            cutoff = datetime.now(UTC) - older_than
            stmt = stmt.where(CachedDataSource.acquired_at < cutoff)

        result = await self.db.execute(stmt)

        if commit:
            await self.db.commit()

        return result.rowcount

    async def delete_for_entity(
        self,
        entity_id: UUID,
        *,
        commit: bool = True,
    ) -> int:
        """Delete all cached entries for an entity.

        Args:
            entity_id: Entity to delete cache for
            commit: Whether to commit

        Returns:
            Number of entries deleted
        """
        stmt = delete(CachedDataSource).where(CachedDataSource.entity_id == entity_id)

        result = await self.db.execute(stmt)

        if commit:
            await self.db.commit()

        return result.rowcount

    async def get_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CachedDataSource]:
        """Get cached entries for a tenant.

        Args:
            tenant_id: Tenant ID
            limit: Maximum entries to return
            offset: Number to skip

        Returns:
            List of cached entries
        """
        stmt = (
            select(CachedDataSource)
            .where(CachedDataSource.customer_id == tenant_id)
            .order_by(CachedDataSource.acquired_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_freshness(
        self,
        tenant_id: UUID | None = None,
    ) -> dict[FreshnessStatus, int]:
        """Count entries by freshness status.

        Args:
            tenant_id: Optional tenant filter

        Returns:
            Dictionary of freshness status -> count
        """
        from sqlalchemy import func

        stmt = select(
            CachedDataSource.freshness_status,
            func.count(CachedDataSource.cache_id),
        ).group_by(CachedDataSource.freshness_status)

        if tenant_id is not None:
            stmt = stmt.where(CachedDataSource.customer_id == tenant_id)

        result = await self.db.execute(stmt)
        rows = result.all()

        counts = dict.fromkeys(FreshnessStatus, 0)
        for freshness_status, count in rows:
            # Convert string value back to enum
            status = FreshnessStatus(freshness_status)
            counts[status] = count

        return counts
