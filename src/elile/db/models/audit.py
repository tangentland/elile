"""Audit event models for compliance and accountability."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid7

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, PortableJSON, PortableUUID


class AuditEventType(str, Enum):
    """Types of audit events tracked in the system."""

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

    # Tenant operations
    TENANT_CREATED = "tenant.created"
    TENANT_UPDATED = "tenant.updated"
    TENANT_DEACTIVATED = "tenant.deactivated"

    # Data lifecycle
    DATA_RETENTION_APPLIED = "data.retention_applied"
    DATA_ERASED = "data.erased"

    # API operations
    API_REQUEST = "api.request"
    API_ERROR = "api.error"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEvent(Base):
    """Immutable audit log entry for compliance tracking.

    Audit events are append-only and capture all critical operations
    in the system for compliance, security, and debugging purposes.
    """

    __tablename__ = "audit_events"

    # Primary identification
    # UUIDv7 is time-ordered, making audit events naturally sortable by ID
    audit_id: Mapped[UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid7)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")

    # Context
    tenant_id: Mapped[UUID | None] = mapped_column(
        PortableUUID(), nullable=True
    )  # null for system events
    user_id: Mapped[UUID | None] = mapped_column(PortableUUID(), nullable=True)
    correlation_id: Mapped[UUID] = mapped_column(
        PortableUUID(), nullable=False
    )  # Request correlation

    # Event details
    entity_id: Mapped[UUID | None] = mapped_column(
        PortableUUID(), nullable=True
    )  # Entity affected
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Event data (structured JSON)
    event_data: Mapped[dict] = mapped_column(PortableJSON(), nullable=False)

    # Metadata
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 support
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamp (immutable, set on creation)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_audit_tenant", "tenant_id"),
        Index("idx_audit_correlation", "correlation_id"),
        Index("idx_audit_event_type", "event_type"),
        Index("idx_audit_entity", "entity_id"),
        Index("idx_audit_created", "created_at"),
        Index("idx_audit_severity", "severity"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditEvent(id={self.audit_id}, type={self.event_type}, "
            f"severity={self.severity})>"
        )
