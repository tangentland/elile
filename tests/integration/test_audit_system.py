"""Integration tests for audit logging system."""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from elile.core.audit import AuditLogger
from elile.db.models.audit import AuditEvent, AuditEventType, AuditSeverity


@pytest.mark.asyncio
async def test_concurrent_audit_logging(db_session):
    """Test concurrent audit logging from multiple requests."""

    async def create_events(tenant_id, correlation_id, count):
        logger = AuditLogger(db_session)
        for i in range(count):
            await logger.log_event(
                AuditEventType.DATA_ACCESSED,
                correlation_id,
                {"iteration": i},
                tenant_id=tenant_id,
            )

    # Create 5 concurrent "requests"
    tasks = []
    for _ in range(5):
        tenant_id = uuid4()
        correlation_id = uuid4()
        tasks.append(create_events(tenant_id, correlation_id, 3))

    # Execute concurrently
    await asyncio.gather(*tasks)
    await db_session.commit()

    # Verify all events created
    logger = AuditLogger(db_session)
    events = await logger.query_events(limit=1000)
    assert len(events) >= 15  # 5 requests * 3 events each


@pytest.mark.asyncio
async def test_date_range_query(db_session):
    """Test querying events by date range."""
    logger = AuditLogger(db_session)
    correlation_id = uuid4()

    # Create event
    event = await logger.log_event(
        AuditEventType.SCREENING_INITIATED, correlation_id, {"test": "data"}
    )
    await db_session.commit()

    # Query with date range around the event
    now = datetime.now(timezone.utc)
    events = await logger.query_events(
        start_date=now - timedelta(minutes=5), end_date=now + timedelta(minutes=5)
    )

    assert len(events) > 0
    assert any(e.audit_id == event.audit_id for e in events)


@pytest.mark.asyncio
async def test_date_range_excludes_outside_events(db_session):
    """Test that date range properly filters events."""
    logger = AuditLogger(db_session)
    correlation_id = uuid4()

    # Create event
    await logger.log_event(
        AuditEventType.SCREENING_INITIATED, correlation_id, {"test": "data"}
    )
    await db_session.commit()

    # Query for future date range (should find nothing)
    future = datetime.now(timezone.utc) + timedelta(days=1)
    events = await logger.query_events(
        start_date=future, end_date=future + timedelta(hours=1)
    )

    assert len(events) == 0


@pytest.mark.asyncio
async def test_multi_filter_query(db_session):
    """Test querying with multiple filters combined."""
    logger = AuditLogger(db_session)
    tenant_id = uuid4()
    entity_id = uuid4()
    correlation_id = uuid4()

    # Create target event
    await logger.log_event(
        AuditEventType.ENTITY_CREATED,
        correlation_id,
        {"test": "target"},
        tenant_id=tenant_id,
        entity_id=entity_id,
        severity=AuditSeverity.INFO,
    )

    # Create noise events with different attributes
    await logger.log_event(
        AuditEventType.ENTITY_CREATED, uuid4(), {"test": "wrong correlation"}, tenant_id=tenant_id
    )
    await logger.log_event(
        AuditEventType.DATA_ACCESSED, correlation_id, {"test": "wrong type"}, tenant_id=tenant_id
    )
    await logger.log_event(
        AuditEventType.ENTITY_CREATED, correlation_id, {"test": "wrong tenant"}, tenant_id=uuid4()
    )

    await db_session.commit()

    # Query with all filters
    events = await logger.query_events(
        tenant_id=tenant_id,
        event_type=AuditEventType.ENTITY_CREATED,
        correlation_id=correlation_id,
        entity_id=entity_id,
    )

    assert len(events) == 1
    assert events[0].event_data["test"] == "target"


@pytest.mark.asyncio
async def test_query_ordering(db_session):
    """Test that events are returned in reverse chronological order."""
    logger = AuditLogger(db_session)
    correlation_id = uuid4()

    # Create events in sequence
    event1 = await logger.log_event(
        AuditEventType.SCREENING_INITIATED, correlation_id, {"order": 1}
    )
    await db_session.flush()

    # Small delay to ensure different timestamps
    await asyncio.sleep(0.01)

    event2 = await logger.log_event(
        AuditEventType.SCREENING_COMPLETED, correlation_id, {"order": 2}
    )
    await db_session.commit()

    events = await logger.query_events(correlation_id=correlation_id)

    # Should be reverse chronological (newest first)
    assert len(events) == 2
    assert events[0].audit_id == event2.audit_id  # Newest first
    assert events[1].audit_id == event1.audit_id


@pytest.mark.asyncio
async def test_severity_filtering(db_session):
    """Test filtering events by severity."""
    logger = AuditLogger(db_session)
    correlation_id = uuid4()

    await logger.log_event(
        AuditEventType.COMPLIANCE_CHECK,
        correlation_id,
        {"test": 1},
        severity=AuditSeverity.INFO,
    )
    await logger.log_event(
        AuditEventType.COMPLIANCE_VIOLATION,
        correlation_id,
        {"test": 2},
        severity=AuditSeverity.ERROR,
    )
    await logger.log_event(
        AuditEventType.CONFIG_CHANGED,
        correlation_id,
        {"test": 3},
        severity=AuditSeverity.WARNING,
    )
    await db_session.commit()

    # Query only ERROR events
    error_events = await logger.query_events(severity=AuditSeverity.ERROR)
    assert len(error_events) == 1
    assert error_events[0].severity == AuditSeverity.ERROR.value


@pytest.mark.asyncio
async def test_resource_tracking(db_session):
    """Test tracking resources in audit events."""
    logger = AuditLogger(db_session)
    correlation_id = uuid4()
    report_id = "RPT-2026-001"

    event = await logger.log_event(
        AuditEventType.REPORT_DOWNLOADED,
        correlation_id,
        {"format": "PDF"},
        resource_type="report",
        resource_id=report_id,
    )

    assert event.resource_type == "report"
    assert event.resource_id == report_id


@pytest.mark.asyncio
async def test_ip_and_user_agent_tracking(db_session):
    """Test tracking IP address and user agent."""
    logger = AuditLogger(db_session)
    correlation_id = uuid4()

    event = await logger.log_event(
        AuditEventType.USER_LOGIN,
        correlation_id,
        {"username": "john.doe"},
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0...",
    )

    assert event.ip_address == "192.168.1.100"
    assert event.user_agent == "Mozilla/5.0..."


@pytest.mark.asyncio
async def test_audit_event_immutability(db_session):
    """Test that audit events are immutable after creation."""
    logger = AuditLogger(db_session)
    correlation_id = uuid4()

    event = await logger.log_event(
        AuditEventType.SCREENING_INITIATED, correlation_id, {"original": "data"}
    )
    original_id = event.audit_id
    original_data = event.event_data.copy()
    await db_session.commit()

    # Attempt to modify (this modifies the object but shouldn't persist)
    event.event_data = {"modified": "data"}
    await db_session.commit()

    # Re-fetch from database
    stmt = select(AuditEvent).where(AuditEvent.audit_id == original_id)
    result = await db_session.execute(stmt)
    refetched = result.scalar_one()

    # Should still have original data (SQLAlchemy won't track JSONB mutations)
    assert refetched.event_data == original_data


@pytest.mark.asyncio
async def test_bulk_event_creation_performance(db_session):
    """Test performance of bulk event creation."""
    logger = AuditLogger(db_session)
    correlation_id = uuid4()
    count = 100

    # Create 100 events
    for i in range(count):
        await logger.log_event(
            AuditEventType.DATA_ACCESSED, correlation_id, {"iteration": i}
        )

    await db_session.commit()

    # Verify all created
    events = await logger.query_events(correlation_id=correlation_id, limit=1000)
    assert len(events) == count
