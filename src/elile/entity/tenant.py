"""Tenant-aware entity service.

This module provides tenant isolation for entity operations,
ensuring proper data separation between tenants while allowing
shared cache for paid external data sources.
"""

from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from elile.core.audit import AuditLogger
from elile.core.context import get_current_context
from elile.core.exceptions import TenantAccessDeniedError
from elile.core.logging import get_logger
from elile.db.models.cache import DataOrigin
from elile.db.models.entity import Entity, EntityType

from .manager import EntityCreateResult, EntityManager
from .types import SubjectIdentifiers

logger = get_logger(__name__)


class TenantEntityCreateResult(BaseModel):
    """Result of tenant-scoped entity creation."""

    entity_id: UUID
    created: bool = True
    tenant_id: UUID | None = None
    is_shared: bool = False


class TenantAwareEntityService:
    """Tenant-aware wrapper for EntityManager.

    Enforces tenant isolation for customer-provided data
    while allowing access to shared external data.

    Isolation Rules:
    - Customer-provided data: Strictly tenant-scoped
    - Paid external data: Shared across tenants
    """

    def __init__(
        self,
        session: AsyncSession,
        audit_logger: AuditLogger | None = None,
        tenant_id: UUID | None = None,
    ):
        """Initialize the tenant-aware entity service.

        Args:
            session: Database session
            audit_logger: Optional audit logger
            tenant_id: Optional explicit tenant ID (falls back to context)
        """
        self._session = session
        self._audit = audit_logger
        self._tenant_id = tenant_id
        self._manager = EntityManager(session, audit_logger)

    @property
    def tenant_id(self) -> UUID | None:
        """Get the current tenant ID."""
        if self._tenant_id:
            return self._tenant_id

        try:
            ctx = get_current_context()
            return ctx.tenant_id
        except Exception:
            return None

    async def create_entity(
        self,
        entity_type: EntityType,
        identifiers: SubjectIdentifiers,
        data_origin: DataOrigin = DataOrigin.CUSTOMER_PROVIDED,
    ) -> TenantEntityCreateResult:
        """Create an entity with tenant association.

        Customer-provided entities are strictly tenant-scoped.
        Paid external entities can be shared across tenants.

        Args:
            entity_type: Type of entity
            identifiers: Entity identifiers
            data_origin: Source of data (determines sharing)

        Returns:
            TenantEntityCreateResult with entity_id and tenant info
        """
        tenant_id = self.tenant_id

        if data_origin == DataOrigin.CUSTOMER_PROVIDED and tenant_id is None:
            raise ValueError("Customer-provided entities require tenant context")

        # Create through manager (handles deduplication)
        result = await self._manager.create_entity(entity_type, identifiers)

        if result.created:
            # Set tenant and data origin on new entity
            entity = await self._manager.get_entity(result.entity_id)
            if entity:
                # Set tenant_id only for customer data
                if data_origin == DataOrigin.CUSTOMER_PROVIDED:
                    entity.tenant_id = tenant_id
                else:
                    entity.tenant_id = None  # Shared external data

                entity.data_origin = data_origin.value
                await self._session.flush()

        logger.info(
            "tenant_entity_created",
            entity_id=str(result.entity_id),
            tenant_id=str(tenant_id) if tenant_id else None,
            data_origin=data_origin.value,
            created=result.created,
        )

        return TenantEntityCreateResult(
            entity_id=result.entity_id,
            created=result.created,
            tenant_id=tenant_id if data_origin == DataOrigin.CUSTOMER_PROVIDED else None,
            is_shared=data_origin == DataOrigin.PAID_EXTERNAL,
        )

    async def get_entity(self, entity_id: UUID) -> Entity | None:
        """Get an entity with tenant access check.

        Args:
            entity_id: Entity to retrieve

        Returns:
            Entity if accessible, None if not found

        Raises:
            TenantAccessDeniedError: If tenant cannot access this entity
        """
        entity = await self._manager.get_entity(entity_id)
        if entity is None:
            return None

        # Check access
        if not await self._can_access(entity):
            logger.warning(
                "tenant_access_denied",
                entity_id=str(entity_id),
                tenant_id=str(self.tenant_id),
                entity_tenant_id=str(entity.tenant_id) if entity.tenant_id else None,
            )
            raise TenantAccessDeniedError(
                tenant_id=self.tenant_id or "none",
                resource=f"entity:{entity_id}",
            )

        return entity

    async def search_entities(
        self,
        entity_type: EntityType | None = None,
        include_shared: bool = True,
        limit: int = 100,
    ) -> list[Entity]:
        """Search entities with tenant filtering.

        Args:
            entity_type: Optional filter by entity type
            include_shared: Include shared external data
            limit: Maximum results

        Returns:
            List of accessible entities
        """
        tenant_id = self.tenant_id

        query = TenantScopedQuery(self._session)
        query = query.with_tenant(tenant_id)

        if include_shared:
            query = query.with_shared()
        else:
            query = query.exclude_other_tenants()

        if entity_type:
            query = query.filter_by_type(entity_type)

        return await query.execute(limit=limit)

    async def mark_as_shared(self, entity_id: UUID) -> bool:
        """Mark an entity as shared (paid external data).

        This removes tenant restriction and allows all tenants access.

        Args:
            entity_id: Entity to mark as shared

        Returns:
            True if successful, False if entity not found
        """
        entity = await self._manager.get_entity(entity_id)
        if entity is None:
            return False

        # Check current tenant owns this entity
        if entity.tenant_id and entity.tenant_id != self.tenant_id:
            raise TenantAccessDeniedError(
                tenant_id=self.tenant_id or "none",
                resource=f"entity:{entity_id}",
            )

        entity.tenant_id = None
        entity.data_origin = DataOrigin.PAID_EXTERNAL.value
        await self._session.flush()

        logger.info(
            "entity_marked_shared",
            entity_id=str(entity_id),
        )
        return True

    async def _can_access(self, entity: Entity) -> bool:
        """Check if current tenant can access an entity.

        Args:
            entity: Entity to check

        Returns:
            True if accessible
        """
        tenant_id = self.tenant_id

        # Shared external data is accessible to all
        if entity.data_origin == DataOrigin.PAID_EXTERNAL.value:
            return True

        # No tenant context means no access to tenant-scoped data
        if tenant_id is None:
            return entity.tenant_id is None

        # Check tenant match
        return entity.tenant_id is None or entity.tenant_id == tenant_id


class EntityAccessControl:
    """Entity access control for tenant isolation.

    Provides verification methods for entity access rights
    based on tenant context and data origin.
    """

    def __init__(self, session: AsyncSession):
        """Initialize access control.

        Args:
            session: Database session
        """
        self._session = session

    async def can_access(
        self,
        entity_id: UUID,
        tenant_id: UUID | None = None,
    ) -> bool:
        """Check if a tenant can access an entity.

        Args:
            entity_id: Entity to check
            tenant_id: Tenant ID (or None for no tenant context)

        Returns:
            True if tenant can access the entity
        """
        stmt = select(Entity).where(Entity.entity_id == entity_id)
        result = await self._session.execute(stmt)
        entity = result.scalar_one_or_none()

        if entity is None:
            return False

        # Shared external data is accessible to all
        if entity.data_origin == DataOrigin.PAID_EXTERNAL.value:
            return True

        # No tenant context means no access to tenant-scoped data
        if tenant_id is None:
            return entity.tenant_id is None

        # Check tenant match
        return entity.tenant_id is None or entity.tenant_id == tenant_id

    async def get_accessible_entities(
        self,
        tenant_id: UUID | None,
        entity_type: EntityType | None = None,
        limit: int = 100,
    ) -> list[UUID]:
        """Get IDs of entities accessible to a tenant.

        Args:
            tenant_id: Tenant ID
            entity_type: Optional filter by type
            limit: Maximum results

        Returns:
            List of accessible entity IDs
        """
        conditions = []

        if tenant_id:
            # Own tenant's data + shared external
            conditions.append(
                or_(
                    Entity.tenant_id == tenant_id,
                    Entity.data_origin == DataOrigin.PAID_EXTERNAL.value,
                )
            )
        else:
            # Only shared external or null tenant
            conditions.append(
                or_(
                    Entity.tenant_id.is_(None),
                    Entity.data_origin == DataOrigin.PAID_EXTERNAL.value,
                )
            )

        stmt = select(Entity.entity_id).where(*conditions)

        if entity_type:
            stmt = stmt.where(Entity.entity_type == entity_type.value)

        stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def verify_isolation(self, entity_id: UUID) -> dict:
        """Audit isolation status of an entity.

        Args:
            entity_id: Entity to verify

        Returns:
            Dict with isolation details
        """
        stmt = select(Entity).where(Entity.entity_id == entity_id)
        result = await self._session.execute(stmt)
        entity = result.scalar_one_or_none()

        if entity is None:
            return {
                "entity_id": str(entity_id),
                "found": False,
            }

        return {
            "entity_id": str(entity_id),
            "found": True,
            "tenant_id": str(entity.tenant_id) if entity.tenant_id else None,
            "data_origin": entity.data_origin,
            "is_tenant_scoped": entity.tenant_id is not None,
            "is_shared": entity.data_origin == DataOrigin.PAID_EXTERNAL.value,
        }


class TenantScopedQuery:
    """Query builder with automatic tenant filtering.

    Provides a fluent interface for building tenant-aware queries.
    """

    def __init__(self, session: AsyncSession):
        """Initialize query builder.

        Args:
            session: Database session
        """
        self._session = session
        self._tenant_id: UUID | None = None
        self._include_shared: bool = False
        self._strict_isolation: bool = False
        self._entity_type: EntityType | None = None

    def with_tenant(self, tenant_id: UUID | None) -> "TenantScopedQuery":
        """Set the tenant scope.

        Args:
            tenant_id: Tenant to scope queries to

        Returns:
            Self for chaining
        """
        self._tenant_id = tenant_id
        return self

    def with_shared(self) -> "TenantScopedQuery":
        """Include shared external entities.

        Returns:
            Self for chaining
        """
        self._include_shared = True
        return self

    def exclude_other_tenants(self) -> "TenantScopedQuery":
        """Strict tenant isolation (exclude all other tenant data).

        Returns:
            Self for chaining
        """
        self._strict_isolation = True
        self._include_shared = False
        return self

    def filter_by_type(self, entity_type: EntityType) -> "TenantScopedQuery":
        """Filter by entity type.

        Args:
            entity_type: Type to filter by

        Returns:
            Self for chaining
        """
        self._entity_type = entity_type
        return self

    def build(self):
        """Build the SQLAlchemy select statement.

        Returns:
            SQLAlchemy Select statement
        """
        stmt = select(Entity)

        # Build tenant filter conditions
        conditions = []

        if self._strict_isolation:
            # Only this tenant's data
            if self._tenant_id:
                conditions.append(Entity.tenant_id == self._tenant_id)
            else:
                conditions.append(Entity.tenant_id.is_(None))
        else:
            if self._tenant_id:
                # Tenant's own data
                tenant_condition = Entity.tenant_id == self._tenant_id

                if self._include_shared:
                    # Also include shared external data
                    tenant_condition = or_(
                        tenant_condition,
                        Entity.data_origin == DataOrigin.PAID_EXTERNAL.value,
                    )

                conditions.append(tenant_condition)
            elif self._include_shared:
                # No tenant context, only shared data
                conditions.append(
                    or_(
                        Entity.tenant_id.is_(None),
                        Entity.data_origin == DataOrigin.PAID_EXTERNAL.value,
                    )
                )

        if conditions:
            stmt = stmt.where(*conditions)

        # Entity type filter
        if self._entity_type:
            stmt = stmt.where(Entity.entity_type == self._entity_type.value)

        return stmt

    async def execute(self, limit: int = 100) -> list[Entity]:
        """Execute the query and return results.

        Args:
            limit: Maximum results

        Returns:
            List of matching entities
        """
        stmt = self.build().limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Count matching entities.

        Returns:
            Count of matching entities
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.build().subquery())
        result = await self._session.execute(stmt)
        return result.scalar() or 0
