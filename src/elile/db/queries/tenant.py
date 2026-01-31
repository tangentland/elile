"""Query helpers for tenant-aware database operations."""

from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from elile.core.context import CacheScope, get_current_context
from elile.db.models.cache import CachedDataSource, DataOrigin


def filter_cache_by_tenant(
    query: Select,
    tenant_id: UUID,
    cache_scope: CacheScope,
) -> Select:
    """Add tenant filtering to a CachedDataSource query.

    Implements the tenant isolation logic for cached data:
    - SHARED scope: Returns paid_external (all tenants) + customer_provided (this tenant only)
    - TENANT_ISOLATED scope: Returns customer_provided (this tenant only)

    Args:
        query: SQLAlchemy Select statement for CachedDataSource
        tenant_id: The tenant to filter by
        cache_scope: The cache scope mode

    Returns:
        Modified query with tenant filtering applied
    """
    if cache_scope == CacheScope.SHARED:
        # Shared scope: paid_external is visible to all, customer_provided only to owner
        return query.where(
            or_(
                CachedDataSource.data_origin == DataOrigin.PAID_EXTERNAL.value,
                (CachedDataSource.data_origin == DataOrigin.CUSTOMER_PROVIDED.value)
                & (CachedDataSource.customer_id == tenant_id),
            )
        )
    else:
        # Tenant isolated: only customer_provided for this tenant
        return query.where(
            CachedDataSource.data_origin == DataOrigin.CUSTOMER_PROVIDED.value,
            CachedDataSource.customer_id == tenant_id,
        )


def filter_cache_by_context(query: Select) -> Select:
    """Add tenant filtering using the current RequestContext.

    Convenience wrapper around filter_cache_by_tenant that extracts
    tenant_id and cache_scope from the current context.

    Args:
        query: SQLAlchemy Select statement for CachedDataSource

    Returns:
        Modified query with tenant filtering applied

    Raises:
        ContextNotSetError: If no request context is set
    """
    ctx = get_current_context()
    return filter_cache_by_tenant(query, ctx.tenant_id, ctx.cache_scope)


async def get_tenant_cache_entry(
    db: AsyncSession,
    entity_id: UUID,
    check_type: str,
    tenant_id: UUID,
    cache_scope: CacheScope,
) -> CachedDataSource | None:
    """Get a cache entry respecting tenant isolation.

    Retrieves the most recent cache entry for an entity and check type,
    applying tenant isolation rules based on data origin.

    Args:
        db: Async database session
        entity_id: The entity to look up
        check_type: The type of check (e.g., "criminal_records")
        tenant_id: The tenant to filter by
        cache_scope: The cache scope mode

    Returns:
        Most recent matching CachedDataSource, or None if not found
    """
    query = (
        select(CachedDataSource)
        .where(
            CachedDataSource.entity_id == entity_id,
            CachedDataSource.check_type == check_type,
        )
        .order_by(CachedDataSource.acquired_at.desc())
    )

    query = filter_cache_by_tenant(query, tenant_id, cache_scope)
    query = query.limit(1)

    result = await db.execute(query)
    return result.scalar_one_or_none()
