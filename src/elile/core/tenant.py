"""Tenant management service for multi-tenancy support."""

from uuid import UUID, uuid7

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from elile.core.audit import AuditLogger
from elile.core.exceptions import TenantInactiveError, TenantNotFoundError
from elile.db.models.audit import AuditEventType, AuditSeverity
from elile.db.models.tenant import Tenant


class TenantService:
    """Service for tenant CRUD operations.

    All operations are audit-logged for compliance and accountability.
    """

    def __init__(self, db: AsyncSession):
        """Initialize tenant service with database session.

        Args:
            db: Async SQLAlchemy session for database operations
        """
        self.db = db
        self.audit = AuditLogger(db)

    async def create_tenant(
        self,
        name: str,
        slug: str,
        correlation_id: UUID | None = None,
    ) -> Tenant:
        """Create a new tenant.

        Args:
            name: Display name for the tenant
            slug: URL-safe identifier (must be unique)
            correlation_id: Request correlation ID for audit trail

        Returns:
            Created Tenant instance

        Raises:
            IntegrityError: If slug already exists
        """
        if correlation_id is None:
            correlation_id = uuid7()

        tenant = Tenant(
            name=name,
            slug=slug.lower(),
            is_active=True,
        )

        self.db.add(tenant)
        await self.db.flush()

        await self.audit.log_event(
            event_type=AuditEventType.TENANT_CREATED,
            correlation_id=correlation_id,
            event_data={
                "tenant_id": str(tenant.tenant_id),
                "name": name,
                "slug": slug,
            },
            severity=AuditSeverity.INFO,
            resource_type="tenant",
            resource_id=str(tenant.tenant_id),
        )

        return tenant

    async def get_tenant(self, tenant_id: UUID) -> Tenant | None:
        """Get a tenant by ID.

        Args:
            tenant_id: The tenant's unique identifier

        Returns:
            Tenant if found, None otherwise
        """
        query = select(Tenant).where(Tenant.tenant_id == tenant_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_tenant_or_raise(self, tenant_id: UUID) -> Tenant:
        """Get a tenant by ID, raising if not found.

        Args:
            tenant_id: The tenant's unique identifier

        Returns:
            The Tenant instance

        Raises:
            TenantNotFoundError: If tenant does not exist
        """
        tenant = await self.get_tenant(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(tenant_id)
        return tenant

    async def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        """Get a tenant by slug.

        Args:
            slug: The tenant's URL-safe identifier

        Returns:
            Tenant if found, None otherwise
        """
        query = select(Tenant).where(Tenant.slug == slug.lower())
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_tenants(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Tenant]:
        """List tenants with pagination.

        Args:
            active_only: If True, only return active tenants
            limit: Maximum number of tenants to return (max 1000)
            offset: Pagination offset

        Returns:
            List of Tenant instances
        """
        query = select(Tenant).order_by(Tenant.created_at.desc(), Tenant.tenant_id.desc())

        if active_only:
            query = query.where(Tenant.is_active == True)  # noqa: E712

        query = query.limit(min(limit, 1000)).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_tenant(
        self,
        tenant_id: UUID,
        name: str | None = None,
        slug: str | None = None,
        correlation_id: UUID | None = None,
    ) -> Tenant:
        """Update a tenant's properties.

        Args:
            tenant_id: The tenant's unique identifier
            name: New display name (optional)
            slug: New URL-safe identifier (optional)
            correlation_id: Request correlation ID for audit trail

        Returns:
            Updated Tenant instance

        Raises:
            TenantNotFoundError: If tenant does not exist
            IntegrityError: If new slug conflicts with existing tenant
        """
        if correlation_id is None:
            correlation_id = uuid7()

        tenant = await self.get_tenant_or_raise(tenant_id)

        changes: dict[str, dict[str, str]] = {}

        if name is not None and name != tenant.name:
            changes["name"] = {"old": tenant.name, "new": name}
            tenant.name = name

        if slug is not None and slug.lower() != tenant.slug:
            changes["slug"] = {"old": tenant.slug, "new": slug.lower()}
            tenant.slug = slug.lower()

        if changes:
            await self.db.flush()

            await self.audit.log_event(
                event_type=AuditEventType.TENANT_UPDATED,
                correlation_id=correlation_id,
                event_data={
                    "tenant_id": str(tenant_id),
                    "changes": changes,
                },
                severity=AuditSeverity.INFO,
                resource_type="tenant",
                resource_id=str(tenant_id),
            )

        return tenant

    async def deactivate_tenant(
        self,
        tenant_id: UUID,
        correlation_id: UUID | None = None,
    ) -> Tenant:
        """Deactivate (soft delete) a tenant.

        Args:
            tenant_id: The tenant's unique identifier
            correlation_id: Request correlation ID for audit trail

        Returns:
            Deactivated Tenant instance

        Raises:
            TenantNotFoundError: If tenant does not exist
        """
        if correlation_id is None:
            correlation_id = uuid7()

        tenant = await self.get_tenant_or_raise(tenant_id)

        if tenant.is_active:
            tenant.is_active = False
            await self.db.flush()

            await self.audit.log_event(
                event_type=AuditEventType.TENANT_DEACTIVATED,
                correlation_id=correlation_id,
                event_data={
                    "tenant_id": str(tenant_id),
                    "name": tenant.name,
                    "slug": tenant.slug,
                },
                severity=AuditSeverity.WARNING,
                resource_type="tenant",
                resource_id=str(tenant_id),
            )

        return tenant

    async def validate_tenant_active(self, tenant_id: UUID) -> Tenant:
        """Validate that a tenant exists and is active.

        Args:
            tenant_id: The tenant's unique identifier

        Returns:
            The active Tenant instance

        Raises:
            TenantNotFoundError: If tenant does not exist
            TenantInactiveError: If tenant is deactivated
        """
        tenant = await self.get_tenant_or_raise(tenant_id)
        if not tenant.is_active:
            raise TenantInactiveError(tenant_id)
        return tenant
