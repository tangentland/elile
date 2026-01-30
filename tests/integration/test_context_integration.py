"""Integration tests for Request Context Framework with audit system."""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid7

import pytest

from elile.core.audit import AuditLogger, audit_operation_v2
from elile.core.context import (
    ActorType,
    RequestContext,
    create_context,
    get_current_context,
    get_current_context_or_none,
    request_context,
)
from elile.db.models.audit import AuditEventType, AuditSeverity


@pytest.mark.asyncio
async def test_audit_v2_with_context(db_session):
    """Test audit_operation_v2 extracts context automatically."""
    tenant_id = uuid7()
    actor_id = uuid7()

    @audit_operation_v2(AuditEventType.DATA_ACCESSED)
    async def access_data(db):
        return {"result": "success"}

    ctx = create_context(tenant_id=tenant_id, actor_id=actor_id, locale="EU")

    with request_context(ctx):
        result = await access_data(db=db_session)

    assert result == {"result": "success"}

    # Verify audit event was created with context data
    logger = AuditLogger(db_session)
    events = await logger.query_events(tenant_id=tenant_id)

    assert len(events) == 1
    event = events[0]
    assert event.tenant_id == tenant_id
    assert event.user_id == actor_id  # actor_id becomes user_id
    assert event.correlation_id == ctx.correlation_id
    assert event.event_data["context_used"] is True
    assert event.event_data["locale"] == "EU"
    assert event.event_data["status"] == "success"


@pytest.mark.asyncio
async def test_audit_v2_without_context(db_session):
    """Test audit_operation_v2 falls back to kwargs when no context."""
    correlation_id = uuid7()
    tenant_id = uuid7()

    @audit_operation_v2(AuditEventType.SCREENING_INITIATED)
    async def start_screening(db, correlation_id, tenant_id=None):
        return {"screening_id": "SC-001"}

    # No context set
    assert get_current_context_or_none() is None

    result = await start_screening(
        db=db_session, correlation_id=correlation_id, tenant_id=tenant_id
    )

    assert result == {"screening_id": "SC-001"}

    # Verify audit event was created with kwargs
    logger = AuditLogger(db_session)
    events = await logger.query_events(correlation_id=correlation_id)

    assert len(events) == 1
    event = events[0]
    assert event.tenant_id == tenant_id
    assert event.correlation_id == correlation_id
    assert event.event_data["context_used"] is False


@pytest.mark.asyncio
async def test_audit_v2_kwargs_override_context(db_session):
    """Test that explicit kwargs override context values."""
    context_tenant = uuid7()
    kwarg_tenant = uuid7()
    actor_id = uuid7()

    @audit_operation_v2(AuditEventType.DATA_ACCESSED)
    async def access_data(db, tenant_id=None):
        return "accessed"

    ctx = create_context(tenant_id=context_tenant, actor_id=actor_id)

    with request_context(ctx):
        # Explicitly pass different tenant_id
        await access_data(db=db_session, tenant_id=kwarg_tenant)

    # Verify kwarg took precedence
    logger = AuditLogger(db_session)
    events = await logger.query_events(tenant_id=kwarg_tenant)

    assert len(events) == 1
    assert events[0].tenant_id == kwarg_tenant


@pytest.mark.asyncio
async def test_audit_v2_error_with_context(db_session):
    """Test audit_operation_v2 records errors with context."""
    tenant_id = uuid7()
    actor_id = uuid7()

    @audit_operation_v2(AuditEventType.SCREENING_INITIATED)
    async def failing_operation(db):
        raise ValueError("Test failure")

    ctx = create_context(tenant_id=tenant_id, actor_id=actor_id, locale="CA")

    with pytest.raises(ValueError, match="Test failure"):
        with request_context(ctx):
            await failing_operation(db=db_session)

    # Verify error was logged with context
    logger = AuditLogger(db_session)
    events = await logger.query_events(tenant_id=tenant_id)

    assert len(events) == 1
    event = events[0]
    assert event.severity == AuditSeverity.ERROR.value
    assert event.event_data["status"] == "error"
    assert event.event_data["error"] == "Test failure"
    assert event.event_data["context_used"] is True
    assert event.event_data["locale"] == "CA"


@pytest.mark.asyncio
async def test_concurrent_requests_with_different_contexts(db_session, test_engine):
    """Test concurrent requests maintain context isolation for auditing."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    @audit_operation_v2(AuditEventType.DATA_ACCESSED)
    async def access_tenant_data(db):
        # Simulate some async work
        await asyncio.sleep(0.01)
        ctx = get_current_context()
        return {"tenant": str(ctx.tenant_id)}

    async def handle_request(tenant_id, actor_id):
        ctx = create_context(tenant_id=tenant_id, actor_id=actor_id)
        async with async_session_factory() as session:
            with request_context(ctx):
                result = await access_tenant_data(db=session)
                await session.commit()
                return result

    # Create 5 concurrent requests with different tenants
    tenant_ids = [uuid7() for _ in range(5)]
    actor_ids = [uuid7() for _ in range(5)]

    tasks = [
        handle_request(tenant_id, actor_id)
        for tenant_id, actor_id in zip(tenant_ids, actor_ids)
    ]

    results = await asyncio.gather(*tasks)

    # Verify each request got its own tenant in the result
    result_tenants = {r["tenant"] for r in results}
    expected_tenants = {str(t) for t in tenant_ids}
    assert result_tenants == expected_tenants

    # Verify audit events have correct tenant isolation
    logger = AuditLogger(db_session)
    for tenant_id in tenant_ids:
        events = await logger.query_events(tenant_id=tenant_id, limit=100)
        assert len(events) == 1
        assert events[0].tenant_id == tenant_id


@pytest.mark.asyncio
async def test_context_to_audit_dict_integration(db_session):
    """Test that to_audit_dict provides complete audit trail."""
    tenant_id = uuid7()
    actor_id = uuid7()
    consent_token = uuid7()
    consent_expiry = datetime.now(timezone.utc) + timedelta(days=30)

    ctx = create_context(
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_type=ActorType.SERVICE,
        locale="US",
        consent_token=consent_token,
        consent_scope={"identity", "employment"},
        consent_expiry=consent_expiry,
        budget_limit=500.0,
    )
    ctx.cost_accumulated = 125.50

    # Log event with context data
    logger = AuditLogger(db_session)
    event = await logger.log_event(
        event_type=AuditEventType.DATA_ACCESSED,
        correlation_id=ctx.correlation_id,
        event_data={"context": ctx.to_audit_dict(), "operation": "fetch_records"},
        tenant_id=ctx.tenant_id,
        user_id=ctx.actor_id,
    )

    assert event.event_data["context"]["tenant_id"] == str(tenant_id)
    assert event.event_data["context"]["actor_id"] == str(actor_id)
    assert event.event_data["context"]["actor_type"] == "service"
    assert event.event_data["context"]["locale"] == "US"
    assert event.event_data["context"]["consent_token"] == str(consent_token)
    assert event.event_data["context"]["budget_limit"] == 500.0
    assert event.event_data["context"]["cost_accumulated"] == 125.50


@pytest.mark.asyncio
async def test_nested_audited_operations(db_session):
    """Test nested audited operations share context."""
    tenant_id = uuid7()
    actor_id = uuid7()

    @audit_operation_v2(AuditEventType.DATA_ACCESSED)
    async def inner_operation(db):
        ctx = get_current_context()
        return {"inner_locale": ctx.locale}

    @audit_operation_v2(AuditEventType.SCREENING_INITIATED)
    async def outer_operation(db):
        ctx = get_current_context()
        inner_result = await inner_operation(db=db)
        return {"outer_locale": ctx.locale, "inner": inner_result}

    ctx = create_context(tenant_id=tenant_id, actor_id=actor_id, locale="UK")

    with request_context(ctx):
        result = await outer_operation(db=db_session)

    assert result["outer_locale"] == "UK"
    assert result["inner"]["inner_locale"] == "UK"

    # Both operations should be logged with same tenant/correlation
    logger = AuditLogger(db_session)
    events = await logger.query_events(correlation_id=ctx.correlation_id)

    assert len(events) == 2
    assert all(e.tenant_id == tenant_id for e in events)
    assert all(e.correlation_id == ctx.correlation_id for e in events)

    # Check event types
    event_types = {e.event_type for e in events}
    assert AuditEventType.SCREENING_INITIATED.value in event_types
    assert AuditEventType.DATA_ACCESSED.value in event_types


@pytest.mark.asyncio
async def test_context_cost_tracking_in_audit(db_session):
    """Test that cost accumulation is visible in audit events."""
    tenant_id = uuid7()
    actor_id = uuid7()

    @audit_operation_v2(AuditEventType.DATA_ACCESSED)
    async def expensive_operation(db, cost: float):
        ctx = get_current_context()
        ctx.assert_budget_available(cost)
        ctx.record_cost(cost)
        return {"cost_recorded": cost, "total": ctx.cost_accumulated}

    ctx = create_context(
        tenant_id=tenant_id, actor_id=actor_id, budget_limit=100.0
    )

    with request_context(ctx):
        result1 = await expensive_operation(db=db_session, cost=30.0)
        result2 = await expensive_operation(db=db_session, cost=25.0)

    assert result1["total"] == 30.0
    assert result2["total"] == 55.0

    # Final context state
    assert ctx.cost_accumulated == 55.0


@pytest.mark.asyncio
async def test_audit_v2_missing_db_raises(db_session):
    """Test audit_operation_v2 raises when db is missing."""

    @audit_operation_v2(AuditEventType.DATA_ACCESSED)
    async def operation_without_db():
        return "result"

    with pytest.raises(ValueError, match="must accept 'db' parameter"):
        await operation_without_db()


@pytest.mark.asyncio
async def test_audit_v2_missing_correlation_without_context_raises(db_session):
    """Test audit_operation_v2 raises when no context and no correlation_id."""

    @audit_operation_v2(AuditEventType.DATA_ACCESSED)
    async def operation_without_correlation(db):
        return "result"

    # No context set and no correlation_id in kwargs
    assert get_current_context_or_none() is None

    with pytest.raises(ValueError, match="requires either a RequestContext"):
        await operation_without_correlation(db=db_session)
