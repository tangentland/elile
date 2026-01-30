"""Audit logging service for compliance and accountability."""

from datetime import datetime
from functools import wraps
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from elile.db.models.audit import AuditEvent, AuditEventType, AuditSeverity


class AuditLogger:
    """Service for creating and querying audit events.

    Audit events are immutable, append-only logs of all critical operations
    for compliance, security monitoring, and debugging.
    """

    def __init__(self, db: AsyncSession):
        """Initialize audit logger with database session.

        Args:
            db: Async SQLAlchemy session for database operations
        """
        self.db = db

    async def log_event(
        self,
        event_type: AuditEventType | str,
        correlation_id: UUID,
        event_data: dict[str, Any],
        severity: AuditSeverity | str = AuditSeverity.INFO,
        tenant_id: UUID | None = None,
        user_id: UUID | None = None,
        entity_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent:
        """Create an immutable audit log entry.

        Args:
            event_type: Type of event (screening.initiated, data.accessed, etc.)
            correlation_id: Request correlation ID for tracing related events
            event_data: Structured event details (must be JSON serializable)
            severity: Event severity level (default: INFO)
            tenant_id: Tenant ID (null for system events)
            user_id: User ID who triggered the event
            entity_id: Optional entity ID affected by event
            resource_type: Optional resource type (screening, report, etc.)
            resource_id: Optional resource ID
            ip_address: Client IP address
            user_agent: Client user agent string

        Returns:
            Created AuditEvent instance

        Example:
            >>> logger = AuditLogger(db_session)
            >>> event = await logger.log_event(
            ...     AuditEventType.SCREENING_INITIATED,
            ...     correlation_id=uuid4(),
            ...     event_data={"subject_name": "John Doe"},
            ...     tenant_id=tenant_uuid,
            ...     user_id=user_uuid
            ... )
        """
        # Convert enum to string if needed
        if isinstance(event_type, AuditEventType):
            event_type = event_type.value
        if isinstance(severity, AuditSeverity):
            severity = severity.value

        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id,
            entity_id=entity_id,
            resource_type=resource_type,
            resource_id=resource_id,
            event_data=event_data,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(event)
        await self.db.flush()

        return event

    async def query_events(
        self,
        tenant_id: UUID | None = None,
        event_type: AuditEventType | str | None = None,
        entity_id: UUID | None = None,
        correlation_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        severity: AuditSeverity | str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Query audit events with filters.

        Args:
            tenant_id: Filter by tenant
            event_type: Filter by event type
            entity_id: Filter by entity
            correlation_id: Filter by request correlation ID
            start_date: Filter events after this date
            end_date: Filter events before this date
            severity: Filter by severity level
            limit: Max results (max 1000)
            offset: Pagination offset

        Returns:
            List of matching audit events, ordered by created_at DESC

        Example:
            >>> events = await logger.query_events(
            ...     tenant_id=tenant_uuid,
            ...     event_type=AuditEventType.SCREENING_INITIATED,
            ...     limit=50
            ... )
        """
        # Convert enums to strings if needed
        if isinstance(event_type, AuditEventType):
            event_type = event_type.value
        if isinstance(severity, AuditSeverity):
            severity = severity.value

        query = select(AuditEvent).order_by(
            AuditEvent.created_at.desc(),
            AuditEvent.audit_id.desc(),  # Secondary sort for equal timestamps
        )

        # Apply filters
        if tenant_id is not None:
            query = query.where(AuditEvent.tenant_id == tenant_id)
        if event_type is not None:
            query = query.where(AuditEvent.event_type == event_type)
        if entity_id is not None:
            query = query.where(AuditEvent.entity_id == entity_id)
        if correlation_id is not None:
            query = query.where(AuditEvent.correlation_id == correlation_id)
        if start_date is not None:
            query = query.where(AuditEvent.created_at >= start_date)
        if end_date is not None:
            query = query.where(AuditEvent.created_at <= end_date)
        if severity is not None:
            query = query.where(AuditEvent.severity == severity)

        # Apply pagination (enforce max limit)
        query = query.limit(min(limit, 1000)).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())


def audit_operation(
    event_type: AuditEventType,
    severity: AuditSeverity = AuditSeverity.INFO,
    extract_entity_id: Callable[[Any], UUID] | None = None,
):
    """Decorator to automatically audit function calls.

    The decorated function must accept a 'db' parameter (AsyncSession)
    and a 'correlation_id' parameter (UUID) for audit logging.

    Args:
        event_type: Type of audit event to log
        severity: Severity level (default: INFO)
        extract_entity_id: Optional function to extract entity_id from result

    Example:
        >>> @audit_operation(
        ...     AuditEventType.SCREENING_INITIATED,
        ...     extract_entity_id=lambda result: result.entity_id
        ... )
        ... async def initiate_screening(
        ...     db: AsyncSession,
        ...     correlation_id: UUID,
        ...     ...
        ... ) -> ScreeningResult:
        ...     ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract db and correlation_id from kwargs
            db = kwargs.get("db")
            correlation_id = kwargs.get("correlation_id")

            if not db:
                raise ValueError(f"Function {func.__name__} must accept 'db' parameter")
            if not correlation_id:
                raise ValueError(f"Function {func.__name__} must accept 'correlation_id' parameter")

            audit_logger = AuditLogger(db)

            # Execute function
            try:
                result = await func(*args, **kwargs)

                # Extract entity_id from result if extractor provided
                entity_id = None
                if extract_entity_id and result:
                    entity_id = extract_entity_id(result)

                # Log success
                await audit_logger.log_event(
                    event_type=event_type,
                    correlation_id=correlation_id,
                    event_data={
                        "function": func.__name__,
                        "status": "success",
                    },
                    severity=severity,
                    entity_id=entity_id,
                    tenant_id=kwargs.get("tenant_id"),
                    user_id=kwargs.get("user_id"),
                )

                return result

            except Exception as e:
                # Log failure
                await audit_logger.log_event(
                    event_type=event_type,
                    correlation_id=correlation_id,
                    event_data={
                        "function": func.__name__,
                        "status": "error",
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    severity=AuditSeverity.ERROR,
                    tenant_id=kwargs.get("tenant_id"),
                    user_id=kwargs.get("user_id"),
                )
                raise

        return wrapper

    return decorator
