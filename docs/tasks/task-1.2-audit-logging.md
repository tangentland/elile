# Task 1.2: Audit Logging System

## Overview

Implement a comprehensive audit logging system that captures all critical operations (screenings initiated, data accessed, findings extracted, etc.) for compliance and accountability. The audit log must be tamper-proof, searchable, and support multi-tenant isolation.

**Priority**: P0 (Critical)
**Estimated Effort**: 2-3 days
**Assignee**: [To be assigned]
**Status**: Not Started

## Dependencies

### Phase Dependencies
- Task 1.1 (Database Schema Foundation) - Requires database models

### External Dependencies
- PostgreSQL 15+ with JSONB support
- structlog (optional, for Task 1.11)

## Data Models

### Core SQLAlchemy Models

```python
# src/elile/models/audit.py
from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import String, JSON, DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class AuditEventType(str, Enum):
    # Screening lifecycle
    SCREENING_INITIATED = "screening.initiated"
    SCREENING_COMPLETED = "screening.completed"
    SCREENING_FAILED = "screening.failed"

    # Data access
    DATA_ACCESSED = "data.accessed"
    CACHE_HIT = "cache.hit"
    CACHE_MISS = "cache.miss"
    PROVIDER_QUERY = "provider.query"

    # Entity operations
    ENTITY_CREATED = "entity.created"
    ENTITY_MERGED = "entity.merged"
    PROFILE_CREATED = "profile.created"

    # Consent
    CONSENT_GRANTED = "consent.granted"
    CONSENT_REVOKED = "consent.revoked"

    # Compliance
    COMPLIANCE_CHECK = "compliance.check"
    COMPLIANCE_VIOLATION = "compliance.violation"

    # User actions
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    REPORT_DOWNLOADED = "report.downloaded"

    # Administrative
    CONFIG_CHANGED = "config.changed"
    RULE_MODIFIED = "rule.modified"

    # Data lifecycle
    DATA_RETENTION_APPLIED = "data.retention_applied"
    DATA_ERASED = "data.erased"

class AuditSeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AuditEvent(Base):
    """Immutable audit log entry."""
    __tablename__ = "audit_events"

    # Primary identification
    audit_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[AuditEventType] = mapped_column(String(100), nullable=False)
    severity: Mapped[AuditSeverity] = mapped_column(String(20), nullable=False, default=AuditSeverity.INFO)

    # Context
    tenant_id: Mapped[UUID] = mapped_column(nullable=True)  # null for system events
    user_id: Mapped[UUID] = mapped_column(nullable=True)
    correlation_id: Mapped[UUID] = mapped_column(nullable=False)  # Request context correlation

    # Event details
    entity_id: Mapped[UUID] = mapped_column(nullable=True)  # Entity affected
    resource_type: Mapped[str] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=True)

    # Event data (structured)
    event_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Metadata
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)  # IPv6 support
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)

    # Timestamp (immutable)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Indexes for common queries
    __table_args__ = (
        Index('idx_audit_tenant', 'tenant_id'),
        Index('idx_audit_correlation', 'correlation_id'),
        Index('idx_audit_event_type', 'event_type'),
        Index('idx_audit_entity', 'entity_id'),
        Index('idx_audit_created', 'created_at'),
        Index('idx_audit_severity', 'severity'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
    )
```

### Pydantic Schemas

```python
# src/elile/schemas/audit.py
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any

class AuditEventCreate(BaseModel):
    """Schema for creating audit events."""
    event_type: str
    severity: str = "info"
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    correlation_id: UUID
    entity_id: UUID | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    event_data: dict[str, Any]
    ip_address: str | None = None
    user_agent: str | None = None

class AuditEventResponse(BaseModel):
    """Schema for audit event responses."""
    audit_id: UUID
    event_type: str
    severity: str
    tenant_id: UUID | None
    user_id: UUID | None
    correlation_id: UUID
    entity_id: UUID | None
    resource_type: str | None
    resource_id: str | None
    event_data: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True

class AuditQueryRequest(BaseModel):
    """Schema for querying audit logs."""
    tenant_id: UUID | None = None
    event_type: str | None = None
    entity_id: UUID | None = None
    correlation_id: UUID | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    severity: str | None = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)
```

## Interface Contracts

### Audit Logger Service

```python
# src/elile/core/audit.py
from uuid import UUID
from datetime import datetime
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from .context import RequestContext
from ..models.audit import AuditEvent, AuditEventType, AuditSeverity

class AuditLogger:
    """Service for creating and querying audit events."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_event(
        self,
        event_type: AuditEventType,
        ctx: RequestContext,
        event_data: dict[str, Any],
        severity: AuditSeverity = AuditSeverity.INFO,
        entity_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> AuditEvent:
        """
        Create an immutable audit log entry.

        Args:
            event_type: Type of event (screening.initiated, data.accessed, etc.)
            ctx: Request context with tenant, user, correlation_id
            event_data: Structured event details (must be JSON serializable)
            severity: Event severity level
            entity_id: Optional entity ID affected by event
            resource_type: Optional resource type (screening, report, etc.)
            resource_id: Optional resource ID

        Returns:
            Created AuditEvent
        """
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            correlation_id=ctx.correlation_id,
            entity_id=entity_id,
            resource_type=resource_type,
            resource_id=resource_id,
            event_data=event_data,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
        )

        self.db.add(event)
        await self.db.flush()

        return event

    async def query_events(
        self,
        tenant_id: UUID | None = None,
        event_type: AuditEventType | None = None,
        entity_id: UUID | None = None,
        correlation_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        severity: AuditSeverity | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """
        Query audit events with filters.

        Args:
            tenant_id: Filter by tenant
            event_type: Filter by event type
            entity_id: Filter by entity
            correlation_id: Filter by request correlation ID
            start_date: Filter events after this date
            end_date: Filter events before this date
            severity: Filter by severity
            limit: Max results (max 1000)
            offset: Pagination offset

        Returns:
            List of matching audit events
        """
        from sqlalchemy import select

        query = select(AuditEvent).order_by(AuditEvent.created_at.desc())

        if tenant_id:
            query = query.where(AuditEvent.tenant_id == tenant_id)
        if event_type:
            query = query.where(AuditEvent.event_type == event_type)
        if entity_id:
            query = query.where(AuditEvent.entity_id == entity_id)
        if correlation_id:
            query = query.where(AuditEvent.correlation_id == correlation_id)
        if start_date:
            query = query.where(AuditEvent.created_at >= start_date)
        if end_date:
            query = query.where(AuditEvent.created_at <= end_date)
        if severity:
            query = query.where(AuditEvent.severity == severity)

        query = query.limit(min(limit, 1000)).offset(offset)

        result = await self.db.execute(query)
        return result.scalars().all()
```

### Helper Decorators

```python
# src/elile/core/audit.py (continued)
from functools import wraps
from typing import Callable

def audit_operation(
    event_type: AuditEventType,
    severity: AuditSeverity = AuditSeverity.INFO,
    extract_entity_id: Callable | None = None,
):
    """
    Decorator to automatically audit function calls.

    Usage:
        @audit_operation(
            AuditEventType.SCREENING_INITIATED,
            extract_entity_id=lambda result: result.entity_id
        )
        async def initiate_screening(...) -> ScreeningResult:
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract context from kwargs
            ctx = kwargs.get('ctx') or kwargs.get('context')
            if not ctx:
                raise ValueError("Function must accept 'ctx' or 'context' parameter")

            # Execute function
            try:
                result = await func(*args, **kwargs)

                # Extract entity_id from result if provided
                entity_id = None
                if extract_entity_id:
                    entity_id = extract_entity_id(result)

                # Log success
                audit_logger = AuditLogger(ctx.db)
                await audit_logger.log_event(
                    event_type=event_type,
                    ctx=ctx,
                    event_data={
                        "function": func.__name__,
                        "status": "success",
                    },
                    severity=severity,
                    entity_id=entity_id,
                )

                return result

            except Exception as e:
                # Log failure
                audit_logger = AuditLogger(ctx.db)
                await audit_logger.log_event(
                    event_type=event_type,
                    ctx=ctx,
                    event_data={
                        "function": func.__name__,
                        "status": "error",
                        "error": str(e),
                    },
                    severity=AuditSeverity.ERROR,
                )
                raise

        return wrapper
    return decorator
```

## Implementation Steps

### Step 1: Create Audit Models (0.5 days)
1. Create `src/elile/models/audit.py` with `AuditEvent` model
2. Add enums for event types and severity
3. Write unit tests for model structure

### Step 2: Create Alembic Migration (0.5 days)
1. Generate migration: `alembic revision --autogenerate -m "Add audit_events table"`
2. Review and adjust migration (add indexes)
3. Test migration up/down
4. Verify table partitioning strategy (future: partition by year)

### Step 3: Implement AuditLogger Service (1 day)
1. Create `src/elile/core/audit.py` with `AuditLogger` class
2. Implement `log_event()` method
3. Implement `query_events()` method with filters
4. Write unit tests for service methods

### Step 4: Create Audit Decorators (0.5 days)
1. Implement `@audit_operation` decorator
2. Add support for automatic entity_id extraction
3. Write unit tests for decorator behavior

### Step 5: Integration Testing (0.5 days)
1. Write integration tests with database
2. Test concurrent audit logging (thread safety)
3. Test query filters and pagination
4. Verify immutability (no update/delete operations)

## Testing Requirements

### Unit Tests (80%+ coverage)

```python
# tests/unit/test_audit_logger.py
import pytest
from uuid import uuid4
from src.elile.core.audit import AuditLogger
from src.elile.models.audit import AuditEventType, AuditSeverity
from src.elile.core.context import RequestContext

@pytest.mark.asyncio
async def test_log_event(db_session, request_context):
    """Test creating audit event."""
    logger = AuditLogger(db_session)

    event = await logger.log_event(
        event_type=AuditEventType.SCREENING_INITIATED,
        ctx=request_context,
        event_data={"subject_name": "John Doe"},
        severity=AuditSeverity.INFO,
    )

    assert event.audit_id is not None
    assert event.event_type == AuditEventType.SCREENING_INITIATED
    assert event.tenant_id == request_context.tenant_id
    assert event.correlation_id == request_context.correlation_id

@pytest.mark.asyncio
async def test_query_events_by_tenant(db_session, request_context):
    """Test querying events by tenant."""
    logger = AuditLogger(db_session)

    # Create multiple events
    await logger.log_event(
        AuditEventType.SCREENING_INITIATED,
        request_context,
        {"test": 1}
    )
    await logger.log_event(
        AuditEventType.SCREENING_COMPLETED,
        request_context,
        {"test": 2}
    )
    await db_session.commit()

    # Query by tenant
    events = await logger.query_events(tenant_id=request_context.tenant_id)
    assert len(events) == 2

@pytest.mark.asyncio
async def test_audit_decorator(db_session, request_context):
    """Test audit decorator."""
    from src.elile.core.audit import audit_operation

    @audit_operation(AuditEventType.DATA_ACCESSED)
    async def test_function(ctx: RequestContext):
        return "success"

    result = await test_function(ctx=request_context)
    assert result == "success"

    # Verify audit event created
    logger = AuditLogger(db_session)
    events = await logger.query_events(
        correlation_id=request_context.correlation_id
    )
    assert len(events) == 1
    assert events[0].event_type == AuditEventType.DATA_ACCESSED
```

### Integration Tests

```python
# tests/integration/test_audit_system.py
import pytest
from datetime import datetime, timedelta
from src.elile.core.audit import AuditLogger
from src.elile.models.audit import AuditEventType

@pytest.mark.asyncio
async def test_audit_immutability(db_session, request_context):
    """Test that audit events cannot be modified."""
    logger = AuditLogger(db_session)

    event = await logger.log_event(
        AuditEventType.SCREENING_INITIATED,
        request_context,
        {"test": "data"}
    )
    await db_session.commit()

    # Attempt to modify (should fail or be ignored)
    event.event_data = {"modified": "data"}
    await db_session.commit()

    # Re-fetch and verify original data
    events = await logger.query_events(audit_id=event.audit_id)
    assert events[0].event_data == {"test": "data"}

@pytest.mark.asyncio
async def test_concurrent_audit_logging(db_session):
    """Test concurrent audit logging from multiple requests."""
    import asyncio

    async def create_events(ctx, count):
        logger = AuditLogger(db_session)
        for i in range(count):
            await logger.log_event(
                AuditEventType.DATA_ACCESSED,
                ctx,
                {"iteration": i}
            )

    # Create contexts for 10 concurrent requests
    contexts = [create_request_context() for _ in range(10)]

    # Execute concurrently
    await asyncio.gather(*[create_events(ctx, 5) for ctx in contexts])
    await db_session.commit()

    # Verify all events created
    logger = AuditLogger(db_session)
    events = await logger.query_events(limit=1000)
    assert len(events) == 50  # 10 contexts * 5 events each

@pytest.mark.asyncio
async def test_date_range_query(db_session, request_context):
    """Test querying events by date range."""
    logger = AuditLogger(db_session)

    # Create events
    await logger.log_event(
        AuditEventType.SCREENING_INITIATED,
        request_context,
        {"test": "old"}
    )
    await db_session.commit()

    # Query with date range
    now = datetime.utcnow()
    events = await logger.query_events(
        start_date=now - timedelta(minutes=5),
        end_date=now + timedelta(minutes=5)
    )

    assert len(events) > 0
```

### Edge Cases

1. **Null tenant_id**: Test system-level events (no tenant)
2. **Large event_data**: Test with 10KB JSON payload
3. **Special characters**: Test with Unicode, SQL injection attempts
4. **Pagination**: Test offset/limit with 10,000+ events
5. **Concurrent queries**: Test read performance under load

## Acceptance Criteria

### Functional Requirements
- [ ] AuditEvent model created with all required fields
- [ ] Immutable audit events (no update/delete operations)
- [ ] Audit logger supports all event types
- [ ] Query interface supports filtering by tenant, event_type, entity_id, date range
- [ ] Pagination works correctly (limit/offset)
- [ ] Decorator automatically logs function execution
- [ ] Multi-tenant isolation (tenant_id filter)

### Data Integrity
- [ ] Audit events are append-only
- [ ] Correlation IDs link related events
- [ ] Timestamps are immutable and timezone-aware
- [ ] No orphaned audit events (even if referenced entity deleted)

### Performance
- [ ] Can log 1000 events/second
- [ ] Query by tenant_id uses index (<10ms)
- [ ] Query by correlation_id uses index (<10ms)
- [ ] Date range queries efficient (indexed)

### Testing
- [ ] Unit test coverage ≥80%
- [ ] All integration tests passing
- [ ] Concurrent logging tested
- [ ] Immutability verified

### Documentation
- [ ] All event types documented with examples
- [ ] Query API documented
- [ ] Decorator usage examples provided

## Review Sign-offs

- [ ] **Code Review**: Senior developer reviews audit implementation
- [ ] **Security Review**: Audit log tamper-proofing validated
- [ ] **Compliance Review**: Audit events cover all required operations

## Deliverables

1. **Source Files**:
   - `src/elile/models/audit.py`
   - `src/elile/core/audit.py`
   - `src/elile/schemas/audit.py`
   - `migrations/versions/002_add_audit_events.py`

2. **Test Files**:
   - `tests/unit/test_audit_logger.py`
   - `tests/integration/test_audit_system.py`

3. **Documentation**:
   - Audit event type reference (markdown)
   - Query examples

## Verification Steps

After implementation, verify:

```bash
# 1. Run migration
alembic upgrade head

# 2. Verify table created
psql -d elile_dev -c "\d audit_events"
# Should show all columns and indexes

# 3. Run tests
pytest tests/unit/test_audit_logger.py -v
pytest tests/integration/test_audit_system.py -v

# 4. Test audit logging manually
python -c "
from src.elile.core.audit import AuditLogger
from src.elile.models.audit import AuditEventType
# ... create test event
"

# 5. Check coverage
pytest --cov=src/elile/core/audit --cov-report=term-missing
```

## Notes

- **Partitioning**: For high-volume production, partition `audit_events` by year (e.g., `audit_events_2026`, `audit_events_2027`)
- **Encryption**: Consider encrypting `event_data` for sensitive audit events (Task 1.6)
- **Retention**: Audit events should be retained per compliance requirements (Task 3.9)
- **Export**: Future task may add export capability for SIEM integration

---

*Task Owner: [To be assigned]*
*Created: 2026-01-29*
*Last Updated: 2026-01-29*
