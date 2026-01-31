"""FastAPI dependencies for database and tenant management."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from elile.core.exceptions import TenantInactiveError, TenantNotFoundError
from elile.core.tenant import TenantService


# Note: This is a placeholder type hint. The actual get_db dependency
# should be defined in the application's database configuration module.
# Applications should define their own get_db function that yields an AsyncSession.
async def get_db() -> AsyncSession:  # type: ignore[empty-body]
    """Placeholder for database session dependency.

    This should be overridden in application configuration:

    Example:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

        engine = create_async_engine(DATABASE_URL)
        async_session = async_sessionmaker(engine)

        async def get_db():
            async with async_session() as session:
                yield session
    """
    ...


def get_tenant_id_from_header(
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> UUID | None:
    """Extract tenant ID from X-Tenant-ID header.

    Args:
        x_tenant_id: The X-Tenant-ID header value

    Returns:
        Parsed UUID or None if header not provided

    Raises:
        HTTPException: If header value is not a valid UUID
    """
    if x_tenant_id is None:
        return None

    try:
        return UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid X-Tenant-ID header: must be a valid UUID",
        )


def get_required_tenant_id_from_header(
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> UUID:
    """Extract required tenant ID from X-Tenant-ID header.

    Args:
        x_tenant_id: The X-Tenant-ID header value (required)

    Returns:
        Parsed UUID

    Raises:
        HTTPException: If header is missing or not a valid UUID
    """
    try:
        return UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid X-Tenant-ID header: must be a valid UUID",
        )


async def get_validated_tenant_id(
    tenant_id: Annotated[UUID, Depends(get_required_tenant_id_from_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UUID:
    """Validate that tenant exists and is active.

    Args:
        tenant_id: The tenant ID from header
        db: Database session

    Returns:
        Validated tenant ID

    Raises:
        HTTPException: If tenant not found or inactive
    """
    service = TenantService(db)
    try:
        await service.validate_tenant_active(tenant_id)
        return tenant_id
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant not found: {tenant_id}",
        )
    except TenantInactiveError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant is inactive: {tenant_id}",
        )


@dataclass
class TenantDatabaseSession:
    """Database session scoped to a specific tenant.

    Combines a database session with a validated tenant ID for use
    in tenant-aware operations.
    """

    session: AsyncSession
    tenant_id: UUID


async def get_tenant_db(
    tenant_id: Annotated[UUID, Depends(get_validated_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantDatabaseSession:
    """Get a tenant-scoped database session.

    Returns a TenantDatabaseSession that combines the database session
    with the validated tenant ID for tenant-aware operations.

    Args:
        tenant_id: Validated tenant ID
        db: Database session

    Returns:
        TenantDatabaseSession with session and tenant_id
    """
    return TenantDatabaseSession(session=db, tenant_id=tenant_id)
