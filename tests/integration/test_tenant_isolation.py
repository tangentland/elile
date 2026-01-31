"""Integration tests for multi-tenant isolation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid7

import pytest

from elile.core.context import CacheScope, create_context, request_context
from elile.core.tenant import TenantService
from elile.db.models.cache import CachedDataSource, DataOrigin, FreshnessStatus
from elile.db.models.entity import Entity, EntityType
from elile.db.queries.tenant import (
    filter_cache_by_context,
    filter_cache_by_tenant,
    get_tenant_cache_entry,
)
from sqlalchemy import select


@pytest.fixture
async def tenant_a(db_session, request):
    """Create test tenant A with unique slug per test."""
    service = TenantService(db_session)
    # Use full uuid7 for uniqueness
    unique_suffix = str(uuid7()).replace("-", "")[:16]
    tenant = await service.create_tenant(
        name="Tenant A", slug=f"ta-{unique_suffix}"
    )
    await db_session.commit()
    return tenant


@pytest.fixture
async def tenant_b(db_session, request):
    """Create test tenant B with unique slug per test."""
    service = TenantService(db_session)
    # Use full uuid7 for uniqueness
    unique_suffix = str(uuid7()).replace("-", "")[:16]
    tenant = await service.create_tenant(
        name="Tenant B", slug=f"tb-{unique_suffix}"
    )
    await db_session.commit()
    return tenant


@pytest.fixture
async def shared_entity(db_session):
    """Create a shared entity (same person investigated by multiple orgs)."""
    entity = Entity(
        entity_type=EntityType.INDIVIDUAL.value,
        canonical_identifiers={"ssn_last4": "1234", "name": "John Doe"},
    )
    db_session.add(entity)
    await db_session.flush()
    return entity


@pytest.fixture
async def cache_entries(db_session, shared_entity, tenant_a, tenant_b):
    """Create cache entries for isolation testing.

    Creates:
    - Paid external data (visible to all)
    - Customer-provided data for tenant A (only visible to A)
    - Customer-provided data for tenant B (only visible to B)
    """
    now = datetime.now(UTC)
    fresh_until = now + timedelta(days=30)
    stale_until = now + timedelta(days=60)

    # Paid external - visible to all tenants
    paid_entry = CachedDataSource(
        entity_id=shared_entity.entity_id,
        provider_id="sterling",
        check_type="criminal_records",
        data_origin=DataOrigin.PAID_EXTERNAL.value,
        customer_id=None,  # No tenant ownership
        acquired_at=now,
        freshness_status=FreshnessStatus.FRESH.value,
        fresh_until=fresh_until,
        stale_until=stale_until,
        raw_response=b"encrypted_paid_data",
        normalized_data={"records": []},
        cost_incurred=Decimal("15.00"),
        cost_currency="USD",
    )

    # Customer-provided by Tenant A
    tenant_a_entry = CachedDataSource(
        entity_id=shared_entity.entity_id,
        provider_id="hris_upload",
        check_type="employment_verification",
        data_origin=DataOrigin.CUSTOMER_PROVIDED.value,
        customer_id=tenant_a.tenant_id,
        acquired_at=now,
        freshness_status=FreshnessStatus.FRESH.value,
        fresh_until=fresh_until,
        stale_until=stale_until,
        raw_response=b"encrypted_tenant_a_data",
        normalized_data={"employer": "Acme Corp"},
        cost_incurred=Decimal("0.00"),
        cost_currency="USD",
    )

    # Customer-provided by Tenant B
    tenant_b_entry = CachedDataSource(
        entity_id=shared_entity.entity_id,
        provider_id="hris_upload",
        check_type="employment_verification",
        data_origin=DataOrigin.CUSTOMER_PROVIDED.value,
        customer_id=tenant_b.tenant_id,
        acquired_at=now,
        freshness_status=FreshnessStatus.FRESH.value,
        fresh_until=fresh_until,
        stale_until=stale_until,
        raw_response=b"encrypted_tenant_b_data",
        normalized_data={"employer": "Globex Inc"},
        cost_incurred=Decimal("0.00"),
        cost_currency="USD",
    )

    db_session.add_all([paid_entry, tenant_a_entry, tenant_b_entry])
    await db_session.commit()

    return {
        "paid": paid_entry,
        "tenant_a": tenant_a_entry,
        "tenant_b": tenant_b_entry,
    }


@pytest.mark.asyncio
async def test_shared_scope_sees_paid_and_own_data(
    db_session, shared_entity, tenant_a, cache_entries
):
    """Test SHARED scope: tenant sees paid_external + own customer_provided data."""
    query = select(CachedDataSource).where(
        CachedDataSource.entity_id == shared_entity.entity_id
    )
    filtered_query = filter_cache_by_tenant(query, tenant_a.tenant_id, CacheScope.SHARED)

    result = await db_session.execute(filtered_query)
    entries = list(result.scalars().all())

    cache_ids = {e.cache_id for e in entries}

    # Should see paid external data
    assert cache_entries["paid"].cache_id in cache_ids
    # Should see own customer-provided data
    assert cache_entries["tenant_a"].cache_id in cache_ids
    # Should NOT see other tenant's customer-provided data
    assert cache_entries["tenant_b"].cache_id not in cache_ids


@pytest.mark.asyncio
async def test_shared_scope_tenant_b_sees_paid_and_own_data(
    db_session, shared_entity, tenant_b, cache_entries
):
    """Test SHARED scope for tenant B: sees paid_external + own customer_provided."""
    query = select(CachedDataSource).where(
        CachedDataSource.entity_id == shared_entity.entity_id
    )
    filtered_query = filter_cache_by_tenant(query, tenant_b.tenant_id, CacheScope.SHARED)

    result = await db_session.execute(filtered_query)
    entries = list(result.scalars().all())

    cache_ids = {e.cache_id for e in entries}

    # Should see paid external data
    assert cache_entries["paid"].cache_id in cache_ids
    # Should see own customer-provided data
    assert cache_entries["tenant_b"].cache_id in cache_ids
    # Should NOT see tenant A's customer-provided data
    assert cache_entries["tenant_a"].cache_id not in cache_ids


@pytest.mark.asyncio
async def test_tenant_isolated_scope_sees_only_own_data(
    db_session, shared_entity, tenant_a, cache_entries
):
    """Test TENANT_ISOLATED scope: only sees own customer_provided data."""
    query = select(CachedDataSource).where(
        CachedDataSource.entity_id == shared_entity.entity_id
    )
    filtered_query = filter_cache_by_tenant(
        query, tenant_a.tenant_id, CacheScope.TENANT_ISOLATED
    )

    result = await db_session.execute(filtered_query)
    entries = list(result.scalars().all())

    cache_ids = {e.cache_id for e in entries}

    # Should NOT see paid external data (isolated mode)
    assert cache_entries["paid"].cache_id not in cache_ids
    # Should see own customer-provided data
    assert cache_entries["tenant_a"].cache_id in cache_ids
    # Should NOT see other tenant's data
    assert cache_entries["tenant_b"].cache_id not in cache_ids


@pytest.mark.asyncio
async def test_filter_cache_by_context_uses_current_context(
    db_session, shared_entity, tenant_a, cache_entries
):
    """Test filter_cache_by_context extracts tenant from RequestContext."""
    ctx = create_context(
        tenant_id=tenant_a.tenant_id,
        actor_id=uuid7(),
        cache_scope=CacheScope.SHARED,
    )

    with request_context(ctx):
        query = select(CachedDataSource).where(
            CachedDataSource.entity_id == shared_entity.entity_id
        )
        filtered_query = filter_cache_by_context(query)

        result = await db_session.execute(filtered_query)
        entries = list(result.scalars().all())

    cache_ids = {e.cache_id for e in entries}

    # With SHARED scope from context, should see paid + own data
    assert cache_entries["paid"].cache_id in cache_ids
    assert cache_entries["tenant_a"].cache_id in cache_ids
    assert cache_entries["tenant_b"].cache_id not in cache_ids


@pytest.mark.asyncio
async def test_get_tenant_cache_entry_shared_scope(
    db_session, shared_entity, tenant_a, cache_entries
):
    """Test get_tenant_cache_entry with shared scope finds paid data."""
    entry = await get_tenant_cache_entry(
        db_session,
        entity_id=shared_entity.entity_id,
        check_type="criminal_records",
        tenant_id=tenant_a.tenant_id,
        cache_scope=CacheScope.SHARED,
    )

    assert entry is not None
    assert entry.cache_id == cache_entries["paid"].cache_id


@pytest.mark.asyncio
async def test_get_tenant_cache_entry_isolated_scope_no_paid(
    db_session, shared_entity, tenant_a, cache_entries
):
    """Test get_tenant_cache_entry with isolated scope doesn't find paid data."""
    entry = await get_tenant_cache_entry(
        db_session,
        entity_id=shared_entity.entity_id,
        check_type="criminal_records",  # This is the paid data check type
        tenant_id=tenant_a.tenant_id,
        cache_scope=CacheScope.TENANT_ISOLATED,
    )

    # Should not find paid data in isolated mode
    assert entry is None


@pytest.mark.asyncio
async def test_get_tenant_cache_entry_finds_own_customer_data(
    db_session, shared_entity, tenant_a, cache_entries
):
    """Test get_tenant_cache_entry finds tenant's own customer-provided data."""
    entry = await get_tenant_cache_entry(
        db_session,
        entity_id=shared_entity.entity_id,
        check_type="employment_verification",
        tenant_id=tenant_a.tenant_id,
        cache_scope=CacheScope.SHARED,
    )

    assert entry is not None
    assert entry.cache_id == cache_entries["tenant_a"].cache_id
    assert entry.normalized_data["employer"] == "Acme Corp"


@pytest.mark.asyncio
async def test_get_tenant_cache_entry_isolates_other_tenant_data(
    db_session, shared_entity, tenant_a, tenant_b, cache_entries
):
    """Test get_tenant_cache_entry cannot access other tenant's customer data."""
    # Tenant A trying to access employment verification
    # Tenant B also has employment verification for same entity

    entry = await get_tenant_cache_entry(
        db_session,
        entity_id=shared_entity.entity_id,
        check_type="employment_verification",
        tenant_id=tenant_a.tenant_id,
        cache_scope=CacheScope.SHARED,
    )

    # Should only get tenant A's data, not tenant B's
    assert entry is not None
    assert entry.customer_id == tenant_a.tenant_id
    assert entry.normalized_data["employer"] == "Acme Corp"
    assert entry.normalized_data["employer"] != "Globex Inc"


@pytest.mark.asyncio
async def test_tenant_cannot_access_deactivated_tenant_data(db_session, shared_entity, tenant_a):
    """Test that deactivated tenant's data remains isolated."""
    service = TenantService(db_session)

    # Create some data for tenant A
    now = datetime.now(UTC)
    entry = CachedDataSource(
        entity_id=shared_entity.entity_id,
        provider_id="internal",
        check_type="special_check",
        data_origin=DataOrigin.CUSTOMER_PROVIDED.value,
        customer_id=tenant_a.tenant_id,
        acquired_at=now,
        freshness_status=FreshnessStatus.FRESH.value,
        fresh_until=now + timedelta(days=30),
        stale_until=now + timedelta(days=60),
        raw_response=b"data",
        normalized_data={"test": True},
        cost_incurred=Decimal("0.00"),
        cost_currency="USD",
    )
    db_session.add(entry)
    await db_session.commit()

    # Deactivate tenant A
    await service.deactivate_tenant(tenant_a.tenant_id)
    await db_session.commit()

    # Create tenant C
    unique_suffix = str(uuid7()).replace("-", "")[:16]
    tenant_c = await service.create_tenant(name="Tenant C", slug=f"tc-{unique_suffix}")
    await db_session.commit()

    # Tenant C should not see deactivated tenant A's data
    found = await get_tenant_cache_entry(
        db_session,
        entity_id=shared_entity.entity_id,
        check_type="special_check",
        tenant_id=tenant_c.tenant_id,
        cache_scope=CacheScope.SHARED,
    )

    assert found is None  # Cannot see other tenant's customer data


@pytest.mark.asyncio
async def test_entities_shared_across_tenants(db_session, shared_entity, tenant_a, tenant_b):
    """Test that entities are shared (not duplicated) across tenants."""
    # Both tenants should see the same entity
    query = select(Entity).where(Entity.entity_id == shared_entity.entity_id)

    result = await db_session.execute(query)
    entity = result.scalar_one_or_none()

    assert entity is not None
    assert entity.entity_id == shared_entity.entity_id

    # Verify the entity has the expected identifiers (shared across tenants)
    assert entity.canonical_identifiers["name"] == "John Doe"
    assert entity.canonical_identifiers["ssn_last4"] == "1234"

    # Both tenant_a and tenant_b can reference the same entity
    # (this is verified by cache_entries fixture which links both tenants to shared_entity)


@pytest.mark.asyncio
async def test_audit_events_have_tenant_context(db_session, tenant_a):
    """Test that audit events capture tenant context."""
    from elile.core.audit import AuditLogger
    from elile.db.models.audit import AuditEventType

    service = TenantService(db_session)
    correlation_id = uuid7()

    # Update tenant (generates audit event)
    await service.update_tenant(
        tenant_a.tenant_id,
        name="Updated Tenant A",
        correlation_id=correlation_id,
    )
    await db_session.commit()

    # Query audit events
    logger = AuditLogger(db_session)
    events = await logger.query_events(correlation_id=correlation_id)

    assert len(events) == 1
    assert events[0].event_type == AuditEventType.TENANT_UPDATED.value
    assert events[0].resource_type == "tenant"
    assert events[0].resource_id == str(tenant_a.tenant_id)
