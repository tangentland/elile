"""Unit tests for Audit Logging System."""

from uuid import uuid7

import pytest

from elile.core.audit import AuditLogger, audit_operation
from elile.db.models.audit import AuditEventType, AuditSeverity


@pytest.mark.asyncio
async def test_log_event_basic(db_session):
    """Test creating a basic audit event."""
    logger = AuditLogger(db_session)
    correlation_id = uuid7()
    tenant_id = uuid7()

    event = await logger.log_event(
        event_type=AuditEventType.SCREENING_INITIATED,
        correlation_id=correlation_id,
        event_data={"subject_name": "John Doe"},
        severity=AuditSeverity.INFO,
        tenant_id=tenant_id,
    )

    assert event.audit_id is not None
    assert event.event_type == AuditEventType.SCREENING_INITIATED.value
    assert event.severity == AuditSeverity.INFO.value
    assert event.tenant_id == tenant_id
    assert event.correlation_id == correlation_id
    assert event.event_data == {"subject_name": "John Doe"}
    assert event.created_at is not None


@pytest.mark.asyncio
async def test_log_event_with_entity(db_session):
    """Test logging event with entity reference."""
    logger = AuditLogger(db_session)
    entity_id = uuid7()
    correlation_id = uuid7()

    event = await logger.log_event(
        event_type=AuditEventType.ENTITY_CREATED,
        correlation_id=correlation_id,
        event_data={"entity_type": "individual"},
        entity_id=entity_id,
    )

    assert event.entity_id == entity_id
    assert event.event_type == AuditEventType.ENTITY_CREATED.value


@pytest.mark.asyncio
async def test_log_event_system_level(db_session):
    """Test system-level event without tenant."""
    logger = AuditLogger(db_session)
    correlation_id = uuid7()

    event = await logger.log_event(
        event_type=AuditEventType.CONFIG_CHANGED,
        correlation_id=correlation_id,
        event_data={"config_key": "max_retries", "old_value": 3, "new_value": 5},
        severity=AuditSeverity.WARNING,
        tenant_id=None,  # System event
    )

    assert event.tenant_id is None
    assert event.severity == AuditSeverity.WARNING.value


@pytest.mark.asyncio
async def test_query_events_by_tenant(db_session):
    """Test querying events by tenant."""
    logger = AuditLogger(db_session)
    tenant1 = uuid7()
    tenant2 = uuid7()
    correlation_id = uuid7()

    # Create events for different tenants
    await logger.log_event(
        AuditEventType.SCREENING_INITIATED, correlation_id, {"test": 1}, tenant_id=tenant1
    )
    await logger.log_event(
        AuditEventType.SCREENING_COMPLETED, correlation_id, {"test": 2}, tenant_id=tenant1
    )
    await logger.log_event(
        AuditEventType.DATA_ACCESSED, correlation_id, {"test": 3}, tenant_id=tenant2
    )
    await db_session.commit()

    # Query by tenant1
    events = await logger.query_events(tenant_id=tenant1)
    assert len(events) == 2
    assert all(e.tenant_id == tenant1 for e in events)


@pytest.mark.asyncio
async def test_query_events_by_event_type(db_session):
    """Test querying events by event type."""
    logger = AuditLogger(db_session)
    correlation_id = uuid7()

    await logger.log_event(AuditEventType.SCREENING_INITIATED, correlation_id, {"test": 1})
    await logger.log_event(AuditEventType.SCREENING_COMPLETED, correlation_id, {"test": 2})
    await logger.log_event(AuditEventType.SCREENING_INITIATED, correlation_id, {"test": 3})
    await db_session.commit()

    # Filter by both event_type and correlation_id to isolate from other tests
    events = await logger.query_events(
        event_type=AuditEventType.SCREENING_INITIATED,
        correlation_id=correlation_id,
    )
    assert len(events) == 2
    assert all(e.event_type == AuditEventType.SCREENING_INITIATED.value for e in events)


@pytest.mark.asyncio
async def test_query_events_by_correlation_id(db_session):
    """Test querying events by correlation ID."""
    logger = AuditLogger(db_session)
    correlation1 = uuid7()
    correlation2 = uuid7()

    await logger.log_event(AuditEventType.SCREENING_INITIATED, correlation1, {"test": 1})
    await logger.log_event(AuditEventType.DATA_ACCESSED, correlation1, {"test": 2})
    await logger.log_event(AuditEventType.SCREENING_COMPLETED, correlation2, {"test": 3})
    await db_session.commit()

    events = await logger.query_events(correlation_id=correlation1)
    assert len(events) == 2
    assert all(e.correlation_id == correlation1 for e in events)


@pytest.mark.asyncio
async def test_query_events_pagination(db_session):
    """Test query pagination."""
    logger = AuditLogger(db_session)
    correlation_id = uuid7()

    # Create 25 events
    for i in range(25):
        await logger.log_event(
            AuditEventType.DATA_ACCESSED, correlation_id, {"iteration": i}
        )
    await db_session.commit()

    # Test limit
    events = await logger.query_events(limit=10)
    assert len(events) == 10

    # Test offset
    events_page1 = await logger.query_events(limit=10, offset=0)
    events_page2 = await logger.query_events(limit=10, offset=10)
    assert events_page1[0].audit_id != events_page2[0].audit_id


@pytest.mark.asyncio
async def test_query_events_max_limit(db_session):
    """Test that query enforces max limit of 1000."""
    logger = AuditLogger(db_session)

    events = await logger.query_events(limit=5000)  # Request more than max
    # Should be limited to 1000 (or actual count if less)
    assert len(events) <= 1000


@pytest.mark.asyncio
async def test_audit_decorator_success(db_session):
    """Test audit decorator on successful function call."""
    correlation_id = uuid7()

    @audit_operation(AuditEventType.DATA_ACCESSED)
    async def test_function(db, correlation_id):
        return "success"

    result = await test_function(db=db_session, correlation_id=correlation_id)
    assert result == "success"

    # Verify audit event created
    logger = AuditLogger(db_session)
    events = await logger.query_events(correlation_id=correlation_id)
    assert len(events) == 1
    assert events[0].event_type == AuditEventType.DATA_ACCESSED.value
    assert events[0].event_data["status"] == "success"


@pytest.mark.asyncio
async def test_audit_decorator_error(db_session):
    """Test audit decorator on failed function call."""
    correlation_id = uuid7()

    @audit_operation(AuditEventType.SCREENING_INITIATED, severity=AuditSeverity.INFO)
    async def failing_function(db, correlation_id):
        raise ValueError("Test error")

    with pytest.raises(ValueError, match="Test error"):
        await failing_function(db=db_session, correlation_id=correlation_id)

    # Verify error audit event created
    logger = AuditLogger(db_session)
    events = await logger.query_events(correlation_id=correlation_id)
    assert len(events) == 1
    assert events[0].event_data["status"] == "error"
    assert events[0].event_data["error"] == "Test error"
    assert events[0].severity == AuditSeverity.ERROR.value


@pytest.mark.asyncio
async def test_event_type_string_conversion(db_session):
    """Test that event types can be strings or enums."""
    logger = AuditLogger(db_session)
    correlation_id = uuid7()

    # Using enum
    event1 = await logger.log_event(
        AuditEventType.SCREENING_INITIATED, correlation_id, {"test": 1}
    )
    # Using string
    event2 = await logger.log_event("screening.initiated", correlation_id, {"test": 2})

    assert event1.event_type == event2.event_type


@pytest.mark.asyncio
async def test_large_event_data(db_session):
    """Test logging event with large JSON payload."""
    logger = AuditLogger(db_session)
    correlation_id = uuid7()

    # Create 5KB of event data
    large_data = {"items": [f"item_{i}" for i in range(500)]}

    event = await logger.log_event(
        AuditEventType.DATA_ACCESSED, correlation_id, large_data
    )

    assert event.event_data == large_data
    assert len(str(large_data)) > 5000  # Verify it's actually large
