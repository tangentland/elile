"""Unit tests for Multi-Tenant Entity Isolation.

Tests the TenantAwareEntityService, EntityAccessControl, and TenantScopedQuery classes.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid7

import pytest

from elile.db.models.cache import DataOrigin
from elile.db.models.entity import Entity, EntityType
from elile.entity import (
    EntityAccessControl,
    TenantAwareEntityService,
    TenantEntityCreateResult,
    TenantScopedQuery,
    SubjectIdentifiers,
)


# =============================================================================
# TenantAwareEntityService Tests
# =============================================================================


class TestTenantAwareEntityService:
    """Tests for TenantAwareEntityService class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def tenant_id(self):
        """Create a test tenant ID."""
        return uuid7()

    @pytest.fixture
    def service(self, mock_session, tenant_id):
        """Create a TenantAwareEntityService instance."""
        return TenantAwareEntityService(
            session=mock_session,
            tenant_id=tenant_id,
        )

    def test_init(self, mock_session, tenant_id):
        """Test TenantAwareEntityService initialization."""
        service = TenantAwareEntityService(
            session=mock_session,
            tenant_id=tenant_id,
        )
        assert service._session is mock_session
        assert service._tenant_id == tenant_id

    def test_tenant_id_from_explicit(self, mock_session, tenant_id):
        """Test tenant_id returns explicit tenant ID."""
        service = TenantAwareEntityService(
            session=mock_session,
            tenant_id=tenant_id,
        )
        assert service.tenant_id == tenant_id

    def test_tenant_id_from_context(self, mock_session):
        """Test tenant_id returns from context when not explicitly set."""
        service = TenantAwareEntityService(session=mock_session)
        context_tenant_id = uuid7()

        with patch("elile.entity.tenant.get_current_context") as mock_ctx:
            mock_ctx.return_value.tenant_id = context_tenant_id
            assert service.tenant_id == context_tenant_id

    def test_tenant_id_none_when_no_context(self, mock_session):
        """Test tenant_id returns None when no context set."""
        service = TenantAwareEntityService(session=mock_session)

        with patch("elile.entity.tenant.get_current_context") as mock_ctx:
            mock_ctx.side_effect = Exception("No context")
            assert service.tenant_id is None

    @pytest.mark.asyncio
    async def test_create_entity_customer_provided(self, service, mock_session, tenant_id):
        """Test creating a customer-provided entity with tenant association."""
        entity_id = uuid7()
        identifiers = SubjectIdentifiers(full_name="John Smith")

        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = None
        mock_entity.data_origin = None

        with patch.object(service._manager, "create_entity") as mock_create:
            mock_create.return_value = MagicMock(entity_id=entity_id, created=True)

            with patch.object(service._manager, "get_entity") as mock_get:
                mock_get.return_value = mock_entity

                result = await service.create_entity(
                    entity_type=EntityType.INDIVIDUAL,
                    identifiers=identifiers,
                    data_origin=DataOrigin.CUSTOMER_PROVIDED,
                )

        assert result.entity_id == entity_id
        assert result.created is True
        assert result.tenant_id == tenant_id
        assert result.is_shared is False
        assert mock_entity.tenant_id == tenant_id
        assert mock_entity.data_origin == DataOrigin.CUSTOMER_PROVIDED.value

    @pytest.mark.asyncio
    async def test_create_entity_paid_external(self, service, mock_session, tenant_id):
        """Test creating a paid external entity (shared across tenants)."""
        entity_id = uuid7()
        identifiers = SubjectIdentifiers(full_name="Jane Doe")

        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = None
        mock_entity.data_origin = None

        with patch.object(service._manager, "create_entity") as mock_create:
            mock_create.return_value = MagicMock(entity_id=entity_id, created=True)

            with patch.object(service._manager, "get_entity") as mock_get:
                mock_get.return_value = mock_entity

                result = await service.create_entity(
                    entity_type=EntityType.INDIVIDUAL,
                    identifiers=identifiers,
                    data_origin=DataOrigin.PAID_EXTERNAL,
                )

        assert result.entity_id == entity_id
        assert result.created is True
        assert result.tenant_id is None
        assert result.is_shared is True
        assert mock_entity.tenant_id is None
        assert mock_entity.data_origin == DataOrigin.PAID_EXTERNAL.value

    @pytest.mark.asyncio
    async def test_create_entity_customer_provided_requires_tenant(self, mock_session):
        """Test that customer-provided entities require tenant context."""
        service = TenantAwareEntityService(session=mock_session)
        identifiers = SubjectIdentifiers(full_name="No Tenant")

        with patch("elile.entity.tenant.get_current_context") as mock_ctx:
            mock_ctx.side_effect = Exception("No context")

            with pytest.raises(ValueError, match="Customer-provided entities require tenant context"):
                await service.create_entity(
                    entity_type=EntityType.INDIVIDUAL,
                    identifiers=identifiers,
                    data_origin=DataOrigin.CUSTOMER_PROVIDED,
                )

    @pytest.mark.asyncio
    async def test_create_entity_existing_not_created(self, service, mock_session, tenant_id):
        """Test creating entity when it already exists (deduplication)."""
        entity_id = uuid7()
        identifiers = SubjectIdentifiers(full_name="Existing Person")

        with patch.object(service._manager, "create_entity") as mock_create:
            mock_create.return_value = MagicMock(entity_id=entity_id, created=False)

            result = await service.create_entity(
                entity_type=EntityType.INDIVIDUAL,
                identifiers=identifiers,
            )

        assert result.entity_id == entity_id
        assert result.created is False

    @pytest.mark.asyncio
    async def test_get_entity_accessible(self, service, mock_session, tenant_id):
        """Test getting an entity that is accessible to the tenant."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = tenant_id
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value

        with patch.object(service._manager, "get_entity") as mock_get:
            mock_get.return_value = mock_entity

            result = await service.get_entity(entity_id)

        assert result is mock_entity

    @pytest.mark.asyncio
    async def test_get_entity_shared_accessible(self, service, mock_session):
        """Test getting a shared entity is accessible to any tenant."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = None
        mock_entity.data_origin = DataOrigin.PAID_EXTERNAL.value

        with patch.object(service._manager, "get_entity") as mock_get:
            mock_get.return_value = mock_entity

            result = await service.get_entity(entity_id)

        assert result is mock_entity

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, service, mock_session):
        """Test getting a non-existent entity."""
        entity_id = uuid7()

        with patch.object(service._manager, "get_entity") as mock_get:
            mock_get.return_value = None

            result = await service.get_entity(entity_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_entity_access_denied(self, service, mock_session, tenant_id):
        """Test getting an entity belonging to another tenant."""
        entity_id = uuid7()
        other_tenant_id = uuid7()

        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = other_tenant_id
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value

        with patch.object(service._manager, "get_entity") as mock_get:
            mock_get.return_value = mock_entity

            from elile.core.exceptions import TenantAccessDeniedError

            with pytest.raises(TenantAccessDeniedError):
                await service.get_entity(entity_id)

    @pytest.mark.asyncio
    async def test_mark_as_shared_success(self, service, mock_session, tenant_id):
        """Test marking an owned entity as shared."""
        entity_id = uuid7()
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = tenant_id
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value

        with patch.object(service._manager, "get_entity") as mock_get:
            mock_get.return_value = mock_entity

            result = await service.mark_as_shared(entity_id)

        assert result is True
        assert mock_entity.tenant_id is None
        assert mock_entity.data_origin == DataOrigin.PAID_EXTERNAL.value

    @pytest.mark.asyncio
    async def test_mark_as_shared_not_found(self, service, mock_session):
        """Test marking a non-existent entity as shared."""
        entity_id = uuid7()

        with patch.object(service._manager, "get_entity") as mock_get:
            mock_get.return_value = None

            result = await service.mark_as_shared(entity_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_mark_as_shared_other_tenant(self, service, mock_session, tenant_id):
        """Test marking another tenant's entity as shared fails."""
        entity_id = uuid7()
        other_tenant_id = uuid7()

        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = other_tenant_id
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value

        with patch.object(service._manager, "get_entity") as mock_get:
            mock_get.return_value = mock_entity

            from elile.core.exceptions import TenantAccessDeniedError

            with pytest.raises(TenantAccessDeniedError):
                await service.mark_as_shared(entity_id)

    @pytest.mark.asyncio
    async def test_search_entities(self, service, mock_session):
        """Test searching entities with tenant filtering."""
        # This test verifies the query builder is used correctly
        # The actual query execution is handled by TenantScopedQuery
        pass  # Covered by integration tests


# =============================================================================
# EntityAccessControl Tests
# =============================================================================


class TestEntityAccessControl:
    """Tests for EntityAccessControl class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def access_control(self, mock_session):
        """Create an EntityAccessControl instance."""
        return EntityAccessControl(mock_session)

    def test_init(self, mock_session):
        """Test EntityAccessControl initialization."""
        ac = EntityAccessControl(mock_session)
        assert ac._session is mock_session

    @pytest.mark.asyncio
    async def test_can_access_own_tenant_data(self, access_control, mock_session):
        """Test access to own tenant's customer data."""
        tenant_id = uuid7()
        entity_id = uuid7()

        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = tenant_id
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await access_control.can_access(entity_id, tenant_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_can_access_shared_data(self, access_control, mock_session):
        """Test access to shared external data."""
        tenant_id = uuid7()
        entity_id = uuid7()

        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = None
        mock_entity.data_origin = DataOrigin.PAID_EXTERNAL.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await access_control.can_access(entity_id, tenant_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_can_access_other_tenant_denied(self, access_control, mock_session):
        """Test access denied for another tenant's data."""
        tenant_id = uuid7()
        other_tenant_id = uuid7()
        entity_id = uuid7()

        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = other_tenant_id
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await access_control.can_access(entity_id, tenant_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_can_access_not_found(self, access_control, mock_session):
        """Test access check for non-existent entity."""
        entity_id = uuid7()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await access_control.can_access(entity_id, uuid7())

        assert result is False

    @pytest.mark.asyncio
    async def test_can_access_no_tenant_context(self, access_control, mock_session):
        """Test access with no tenant context."""
        entity_id = uuid7()

        # Null tenant entity should be accessible
        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = None
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await access_control.can_access(entity_id, None)

        assert result is True

    @pytest.mark.asyncio
    async def test_can_access_no_tenant_context_tenant_scoped_data(self, access_control, mock_session):
        """Test access denied for tenant-scoped data with no tenant context."""
        entity_id = uuid7()
        owner_tenant_id = uuid7()

        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = owner_tenant_id
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await access_control.can_access(entity_id, None)

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_isolation_found(self, access_control, mock_session):
        """Test verify_isolation for existing entity."""
        entity_id = uuid7()
        tenant_id = uuid7()

        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = tenant_id
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await access_control.verify_isolation(entity_id)

        assert result["found"] is True
        assert result["entity_id"] == str(entity_id)
        assert result["tenant_id"] == str(tenant_id)
        assert result["data_origin"] == DataOrigin.CUSTOMER_PROVIDED.value
        assert result["is_tenant_scoped"] is True
        assert result["is_shared"] is False

    @pytest.mark.asyncio
    async def test_verify_isolation_shared(self, access_control, mock_session):
        """Test verify_isolation for shared entity."""
        entity_id = uuid7()

        mock_entity = MagicMock(spec=Entity)
        mock_entity.entity_id = entity_id
        mock_entity.tenant_id = None
        mock_entity.data_origin = DataOrigin.PAID_EXTERNAL.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_session.execute.return_value = mock_result

        result = await access_control.verify_isolation(entity_id)

        assert result["found"] is True
        assert result["tenant_id"] is None
        assert result["is_tenant_scoped"] is False
        assert result["is_shared"] is True

    @pytest.mark.asyncio
    async def test_verify_isolation_not_found(self, access_control, mock_session):
        """Test verify_isolation for non-existent entity."""
        entity_id = uuid7()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await access_control.verify_isolation(entity_id)

        assert result["found"] is False
        assert result["entity_id"] == str(entity_id)


# =============================================================================
# TenantScopedQuery Tests
# =============================================================================


class TestTenantScopedQuery:
    """Tests for TenantScopedQuery class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def query(self, mock_session):
        """Create a TenantScopedQuery instance."""
        return TenantScopedQuery(mock_session)

    def test_init(self, mock_session):
        """Test TenantScopedQuery initialization."""
        query = TenantScopedQuery(mock_session)
        assert query._session is mock_session
        assert query._tenant_id is None
        assert query._include_shared is False
        assert query._strict_isolation is False
        assert query._entity_type is None

    def test_with_tenant(self, query):
        """Test with_tenant method."""
        tenant_id = uuid7()
        result = query.with_tenant(tenant_id)

        assert result is query  # Returns self for chaining
        assert query._tenant_id == tenant_id

    def test_with_shared(self, query):
        """Test with_shared method."""
        result = query.with_shared()

        assert result is query
        assert query._include_shared is True

    def test_exclude_other_tenants(self, query):
        """Test exclude_other_tenants method."""
        result = query.exclude_other_tenants()

        assert result is query
        assert query._strict_isolation is True
        assert query._include_shared is False

    def test_filter_by_type(self, query):
        """Test filter_by_type method."""
        result = query.filter_by_type(EntityType.INDIVIDUAL)

        assert result is query
        assert query._entity_type == EntityType.INDIVIDUAL

    def test_chaining(self, query):
        """Test method chaining."""
        tenant_id = uuid7()
        result = (
            query
            .with_tenant(tenant_id)
            .with_shared()
            .filter_by_type(EntityType.ORGANIZATION)
        )

        assert result is query
        assert query._tenant_id == tenant_id
        assert query._include_shared is True
        assert query._entity_type == EntityType.ORGANIZATION

    def test_build_no_filters(self, query):
        """Test build with no filters."""
        stmt = query.build()
        assert stmt is not None
        # Verify it's a Select statement
        assert hasattr(stmt, "limit")

    def test_build_with_tenant_and_shared(self, query):
        """Test build with tenant and shared data."""
        tenant_id = uuid7()
        query.with_tenant(tenant_id).with_shared()

        stmt = query.build()
        assert stmt is not None

    def test_build_strict_isolation(self, query):
        """Test build with strict isolation."""
        tenant_id = uuid7()
        query.with_tenant(tenant_id).exclude_other_tenants()

        stmt = query.build()
        assert stmt is not None

    def test_build_with_entity_type(self, query):
        """Test build with entity type filter."""
        query.filter_by_type(EntityType.ADDRESS)

        stmt = query.build()
        assert stmt is not None

    @pytest.mark.asyncio
    async def test_execute(self, query, mock_session):
        """Test execute method."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await query.execute(limit=50)

        assert result == []
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_results(self, query, mock_session):
        """Test execute method with results."""
        entity1 = MagicMock(spec=Entity)
        entity2 = MagicMock(spec=Entity)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [entity1, entity2]

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await query.execute()

        assert len(result) == 2
        assert entity1 in result
        assert entity2 in result

    @pytest.mark.asyncio
    async def test_count(self, query, mock_session):
        """Test count method."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_session.execute.return_value = mock_result

        count = await query.count()

        assert count == 42

    @pytest.mark.asyncio
    async def test_count_zero(self, query, mock_session):
        """Test count method with no results."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        count = await query.count()

        assert count == 0


# =============================================================================
# TenantEntityCreateResult Tests
# =============================================================================


class TestTenantEntityCreateResult:
    """Tests for TenantEntityCreateResult model."""

    def test_create_with_all_fields(self):
        """Test creating result with all fields."""
        entity_id = uuid7()
        tenant_id = uuid7()

        result = TenantEntityCreateResult(
            entity_id=entity_id,
            created=True,
            tenant_id=tenant_id,
            is_shared=False,
        )

        assert result.entity_id == entity_id
        assert result.created is True
        assert result.tenant_id == tenant_id
        assert result.is_shared is False

    def test_create_shared(self):
        """Test creating result for shared entity."""
        entity_id = uuid7()

        result = TenantEntityCreateResult(
            entity_id=entity_id,
            created=True,
            tenant_id=None,
            is_shared=True,
        )

        assert result.entity_id == entity_id
        assert result.tenant_id is None
        assert result.is_shared is True

    def test_defaults(self):
        """Test default values."""
        entity_id = uuid7()

        result = TenantEntityCreateResult(entity_id=entity_id)

        assert result.created is True
        assert result.tenant_id is None
        assert result.is_shared is False


# =============================================================================
# Access Control Logic Tests
# =============================================================================


class TestAccessControlLogic:
    """Tests for access control logic in TenantAwareEntityService._can_access."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def tenant_id(self):
        """Create a test tenant ID."""
        return uuid7()

    @pytest.fixture
    def service(self, mock_session, tenant_id):
        """Create a TenantAwareEntityService instance."""
        return TenantAwareEntityService(
            session=mock_session,
            tenant_id=tenant_id,
        )

    @pytest.mark.asyncio
    async def test_can_access_shared_external_always(self, service):
        """Test that shared external data is always accessible."""
        mock_entity = MagicMock(spec=Entity)
        mock_entity.data_origin = DataOrigin.PAID_EXTERNAL.value
        mock_entity.tenant_id = uuid7()  # Even with tenant_id set

        result = await service._can_access(mock_entity)

        assert result is True

    @pytest.mark.asyncio
    async def test_can_access_own_tenant(self, service, tenant_id):
        """Test access to own tenant's data."""
        mock_entity = MagicMock(spec=Entity)
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value
        mock_entity.tenant_id = tenant_id

        result = await service._can_access(mock_entity)

        assert result is True

    @pytest.mark.asyncio
    async def test_can_access_null_tenant_data(self, service):
        """Test access to null tenant data."""
        mock_entity = MagicMock(spec=Entity)
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value
        mock_entity.tenant_id = None

        result = await service._can_access(mock_entity)

        assert result is True

    @pytest.mark.asyncio
    async def test_cannot_access_other_tenant(self, service, tenant_id):
        """Test denied access to other tenant's data."""
        other_tenant_id = uuid7()

        mock_entity = MagicMock(spec=Entity)
        mock_entity.data_origin = DataOrigin.CUSTOMER_PROVIDED.value
        mock_entity.tenant_id = other_tenant_id

        result = await service._can_access(mock_entity)

        assert result is False

    @pytest.mark.asyncio
    async def test_no_tenant_context_only_null_tenant_access(self, mock_session):
        """Test that no tenant context only allows null tenant data."""
        service = TenantAwareEntityService(session=mock_session)

        with patch("elile.entity.tenant.get_current_context") as mock_ctx:
            mock_ctx.side_effect = Exception("No context")

            # Can access null tenant
            mock_entity_null = MagicMock(spec=Entity)
            mock_entity_null.data_origin = DataOrigin.CUSTOMER_PROVIDED.value
            mock_entity_null.tenant_id = None

            result = await service._can_access(mock_entity_null)
            assert result is True

            # Cannot access tenant-scoped
            mock_entity_scoped = MagicMock(spec=Entity)
            mock_entity_scoped.data_origin = DataOrigin.CUSTOMER_PROVIDED.value
            mock_entity_scoped.tenant_id = uuid7()

            result = await service._can_access(mock_entity_scoped)
            assert result is False
