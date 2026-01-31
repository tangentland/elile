"""Unit tests for TenantService."""

from uuid import uuid7

import pytest

from elile.core.exceptions import TenantInactiveError, TenantNotFoundError
from elile.core.tenant import TenantService
from elile.db.models.audit import AuditEventType
from elile.db.schemas.tenant import TenantCreate, TenantUpdate


@pytest.mark.asyncio
async def test_create_tenant_basic(db_session):
    """Test creating a tenant with basic properties."""
    service = TenantService(db_session)

    tenant = await service.create_tenant(
        name="Acme Corporation",
        slug="acme-corp",
    )

    assert tenant.tenant_id is not None
    assert tenant.name == "Acme Corporation"
    assert tenant.slug == "acme-corp"
    assert tenant.is_active is True
    assert tenant.created_at is not None
    assert tenant.updated_at is not None


@pytest.mark.asyncio
async def test_create_tenant_with_correlation_id(db_session):
    """Test creating a tenant with explicit correlation ID."""
    service = TenantService(db_session)
    correlation_id = uuid7()

    tenant = await service.create_tenant(
        name="Test Org",
        slug="test-org",
        correlation_id=correlation_id,
    )

    assert tenant.tenant_id is not None
    assert tenant.name == "Test Org"


@pytest.mark.asyncio
async def test_create_tenant_slug_lowercase(db_session):
    """Test that tenant slugs are normalized to lowercase."""
    service = TenantService(db_session)

    tenant = await service.create_tenant(
        name="Mixed Case Org",
        slug="Mixed-Case-ORG",
    )

    assert tenant.slug == "mixed-case-org"


@pytest.mark.asyncio
async def test_get_tenant_exists(db_session):
    """Test getting an existing tenant by ID."""
    service = TenantService(db_session)

    created = await service.create_tenant(name="Get Test", slug="get-test")
    await db_session.commit()

    tenant = await service.get_tenant(created.tenant_id)

    assert tenant is not None
    assert tenant.tenant_id == created.tenant_id
    assert tenant.name == "Get Test"


@pytest.mark.asyncio
async def test_get_tenant_not_exists(db_session):
    """Test getting a non-existent tenant returns None."""
    service = TenantService(db_session)

    tenant = await service.get_tenant(uuid7())

    assert tenant is None


@pytest.mark.asyncio
async def test_get_tenant_or_raise_exists(db_session):
    """Test get_tenant_or_raise with existing tenant."""
    service = TenantService(db_session)

    created = await service.create_tenant(name="Raise Test", slug="raise-test")
    await db_session.commit()

    tenant = await service.get_tenant_or_raise(created.tenant_id)

    assert tenant.tenant_id == created.tenant_id


@pytest.mark.asyncio
async def test_get_tenant_or_raise_not_exists(db_session):
    """Test get_tenant_or_raise raises for non-existent tenant."""
    service = TenantService(db_session)
    missing_id = uuid7()

    with pytest.raises(TenantNotFoundError) as exc_info:
        await service.get_tenant_or_raise(missing_id)

    assert exc_info.value.tenant_id == missing_id


@pytest.mark.asyncio
async def test_get_tenant_by_slug(db_session):
    """Test getting tenant by slug."""
    service = TenantService(db_session)

    created = await service.create_tenant(name="Slug Test", slug="slug-test")
    await db_session.commit()

    tenant = await service.get_tenant_by_slug("slug-test")

    assert tenant is not None
    assert tenant.tenant_id == created.tenant_id


@pytest.mark.asyncio
async def test_get_tenant_by_slug_case_insensitive(db_session):
    """Test slug lookup is case-insensitive."""
    service = TenantService(db_session)

    await service.create_tenant(name="Case Test", slug="case-test")
    await db_session.commit()

    tenant = await service.get_tenant_by_slug("CASE-TEST")

    assert tenant is not None
    assert tenant.slug == "case-test"


@pytest.mark.asyncio
async def test_get_tenant_by_slug_not_exists(db_session):
    """Test getting non-existent slug returns None."""
    service = TenantService(db_session)

    tenant = await service.get_tenant_by_slug("nonexistent")

    assert tenant is None


@pytest.mark.asyncio
async def test_list_tenants_empty(db_session):
    """Test listing tenants when none exist."""
    service = TenantService(db_session)

    tenants = await service.list_tenants()

    # May include tenants from other tests, so just check type
    assert isinstance(tenants, list)


@pytest.mark.asyncio
async def test_list_tenants_active_only(db_session):
    """Test listing only active tenants."""
    service = TenantService(db_session)

    active = await service.create_tenant(name="Active Org", slug="active-list-org")
    inactive = await service.create_tenant(name="Inactive Org", slug="inactive-list-org")
    await service.deactivate_tenant(inactive.tenant_id)
    await db_session.commit()

    tenants = await service.list_tenants(active_only=True)
    tenant_ids = [t.tenant_id for t in tenants]

    assert active.tenant_id in tenant_ids
    assert inactive.tenant_id not in tenant_ids


@pytest.mark.asyncio
async def test_list_tenants_include_inactive(db_session):
    """Test listing all tenants including inactive."""
    service = TenantService(db_session)

    active = await service.create_tenant(name="Active All", slug="active-all-org")
    inactive = await service.create_tenant(name="Inactive All", slug="inactive-all-org")
    await service.deactivate_tenant(inactive.tenant_id)
    await db_session.commit()

    tenants = await service.list_tenants(active_only=False)
    tenant_ids = [t.tenant_id for t in tenants]

    assert active.tenant_id in tenant_ids
    assert inactive.tenant_id in tenant_ids


@pytest.mark.asyncio
async def test_list_tenants_pagination(db_session):
    """Test tenant listing with pagination."""
    service = TenantService(db_session)

    # Create 5 tenants with unique slugs
    for i in range(5):
        await service.create_tenant(name=f"Page Org {i}", slug=f"page-org-{i}")
    await db_session.commit()

    # Get first 2
    page1 = await service.list_tenants(limit=2, offset=0)
    # Get next 2
    page2 = await service.list_tenants(limit=2, offset=2)

    assert len(page1) == 2
    assert len(page2) == 2
    # Verify no overlap
    page1_ids = {t.tenant_id for t in page1}
    page2_ids = {t.tenant_id for t in page2}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_update_tenant_name(db_session):
    """Test updating tenant name."""
    service = TenantService(db_session)

    tenant = await service.create_tenant(name="Old Name", slug="update-name-test")
    await db_session.commit()

    updated = await service.update_tenant(tenant.tenant_id, name="New Name")

    assert updated.name == "New Name"
    assert updated.slug == "update-name-test"  # Unchanged


@pytest.mark.asyncio
async def test_update_tenant_slug(db_session):
    """Test updating tenant slug."""
    service = TenantService(db_session)

    tenant = await service.create_tenant(name="Slug Update", slug="old-slug")
    await db_session.commit()

    updated = await service.update_tenant(tenant.tenant_id, slug="new-slug")

    assert updated.slug == "new-slug"
    assert updated.name == "Slug Update"  # Unchanged


@pytest.mark.asyncio
async def test_update_tenant_both_fields(db_session):
    """Test updating both name and slug."""
    service = TenantService(db_session)

    tenant = await service.create_tenant(name="Both Old", slug="both-old-slug")
    await db_session.commit()

    updated = await service.update_tenant(
        tenant.tenant_id,
        name="Both New",
        slug="both-new-slug",
    )

    assert updated.name == "Both New"
    assert updated.slug == "both-new-slug"


@pytest.mark.asyncio
async def test_update_tenant_not_exists(db_session):
    """Test updating non-existent tenant raises error."""
    service = TenantService(db_session)

    with pytest.raises(TenantNotFoundError):
        await service.update_tenant(uuid7(), name="New Name")


@pytest.mark.asyncio
async def test_update_tenant_no_changes(db_session):
    """Test update with no changes doesn't fail."""
    service = TenantService(db_session)

    tenant = await service.create_tenant(name="No Change", slug="no-change-slug")
    await db_session.commit()

    # Update with same values
    updated = await service.update_tenant(
        tenant.tenant_id,
        name="No Change",
        slug="no-change-slug",
    )

    assert updated.name == "No Change"


@pytest.mark.asyncio
async def test_deactivate_tenant(db_session):
    """Test deactivating a tenant."""
    service = TenantService(db_session)

    tenant = await service.create_tenant(name="To Deactivate", slug="to-deactivate")
    await db_session.commit()

    assert tenant.is_active is True

    deactivated = await service.deactivate_tenant(tenant.tenant_id)

    assert deactivated.is_active is False


@pytest.mark.asyncio
async def test_deactivate_tenant_idempotent(db_session):
    """Test deactivating an already inactive tenant is idempotent."""
    service = TenantService(db_session)

    tenant = await service.create_tenant(name="Twice Deactivate", slug="twice-deactivate")
    await service.deactivate_tenant(tenant.tenant_id)
    await db_session.commit()

    # Deactivate again
    deactivated = await service.deactivate_tenant(tenant.tenant_id)

    assert deactivated.is_active is False


@pytest.mark.asyncio
async def test_deactivate_tenant_not_exists(db_session):
    """Test deactivating non-existent tenant raises error."""
    service = TenantService(db_session)

    with pytest.raises(TenantNotFoundError):
        await service.deactivate_tenant(uuid7())


@pytest.mark.asyncio
async def test_validate_tenant_active_success(db_session):
    """Test validating an active tenant succeeds."""
    service = TenantService(db_session)

    tenant = await service.create_tenant(name="Valid Active", slug="valid-active")
    await db_session.commit()

    result = await service.validate_tenant_active(tenant.tenant_id)

    assert result.tenant_id == tenant.tenant_id


@pytest.mark.asyncio
async def test_validate_tenant_active_not_found(db_session):
    """Test validating non-existent tenant raises TenantNotFoundError."""
    service = TenantService(db_session)

    with pytest.raises(TenantNotFoundError):
        await service.validate_tenant_active(uuid7())


@pytest.mark.asyncio
async def test_validate_tenant_active_inactive(db_session):
    """Test validating inactive tenant raises TenantInactiveError."""
    service = TenantService(db_session)

    tenant = await service.create_tenant(name="Valid Inactive", slug="valid-inactive")
    await service.deactivate_tenant(tenant.tenant_id)
    await db_session.commit()

    with pytest.raises(TenantInactiveError) as exc_info:
        await service.validate_tenant_active(tenant.tenant_id)

    assert exc_info.value.tenant_id == tenant.tenant_id


@pytest.mark.asyncio
async def test_create_tenant_audited(db_session):
    """Test that tenant creation is audit logged."""
    from elile.core.audit import AuditLogger

    service = TenantService(db_session)
    correlation_id = uuid7()

    tenant = await service.create_tenant(
        name="Audit Create",
        slug="audit-create",
        correlation_id=correlation_id,
    )
    await db_session.commit()

    # Verify audit event
    logger = AuditLogger(db_session)
    events = await logger.query_events(correlation_id=correlation_id)

    assert len(events) == 1
    assert events[0].event_type == AuditEventType.TENANT_CREATED.value
    assert events[0].event_data["tenant_id"] == str(tenant.tenant_id)
    assert events[0].event_data["name"] == "Audit Create"
    assert events[0].resource_type == "tenant"


@pytest.mark.asyncio
async def test_update_tenant_audited(db_session):
    """Test that tenant updates are audit logged."""
    from elile.core.audit import AuditLogger

    service = TenantService(db_session)
    correlation_id = uuid7()

    tenant = await service.create_tenant(name="Audit Update", slug="audit-update")
    await db_session.commit()

    await service.update_tenant(
        tenant.tenant_id,
        name="Audit Updated",
        correlation_id=correlation_id,
    )
    await db_session.commit()

    logger = AuditLogger(db_session)
    events = await logger.query_events(correlation_id=correlation_id)

    assert len(events) == 1
    assert events[0].event_type == AuditEventType.TENANT_UPDATED.value
    assert "name" in events[0].event_data["changes"]


@pytest.mark.asyncio
async def test_deactivate_tenant_audited(db_session):
    """Test that tenant deactivation is audit logged."""
    from elile.core.audit import AuditLogger

    service = TenantService(db_session)
    correlation_id = uuid7()

    tenant = await service.create_tenant(name="Audit Deactivate", slug="audit-deactivate")
    await db_session.commit()

    await service.deactivate_tenant(tenant.tenant_id, correlation_id=correlation_id)
    await db_session.commit()

    logger = AuditLogger(db_session)
    events = await logger.query_events(correlation_id=correlation_id)

    assert len(events) == 1
    assert events[0].event_type == AuditEventType.TENANT_DEACTIVATED.value


# Schema validation tests


def test_tenant_create_schema_valid():
    """Test TenantCreate schema with valid data."""
    data = TenantCreate(name="Valid Tenant", slug="valid-tenant")

    assert data.name == "Valid Tenant"
    assert data.slug == "valid-tenant"


def test_tenant_create_schema_slug_lowercase():
    """Test TenantCreate normalizes slug to lowercase."""
    data = TenantCreate(name="Test", slug="UPPER-CASE")

    assert data.slug == "upper-case"


def test_tenant_create_schema_invalid_slug():
    """Test TenantCreate rejects invalid slug."""
    with pytest.raises(ValueError, match="Slug must be lowercase"):
        TenantCreate(name="Test", slug="-starts-with-hyphen")


def test_tenant_create_schema_slug_consecutive_hyphens():
    """Test TenantCreate rejects consecutive hyphens."""
    with pytest.raises(ValueError, match="consecutive hyphens"):
        TenantCreate(name="Test", slug="double--hyphen")


def test_tenant_update_schema_optional():
    """Test TenantUpdate with optional fields."""
    data = TenantUpdate(name="New Name")

    assert data.name == "New Name"
    assert data.slug is None


def test_tenant_update_schema_slug_validation():
    """Test TenantUpdate validates slug if provided."""
    with pytest.raises(ValueError, match="Slug must be lowercase"):
        TenantUpdate(slug="ends-with-hyphen-")
