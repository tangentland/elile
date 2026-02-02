"""Types and data models for the monitoring module.

Defines configuration, check records, lifecycle events, and other types
used by the monitoring scheduler.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import SearchDegree, ServiceTier, VigilanceLevel
from elile.compliance.types import Locale, RoleCategory

# =============================================================================
# Enums
# =============================================================================


class MonitoringStatus(str, Enum):
    """Status of a monitoring configuration."""

    ACTIVE = "active"  # Monitoring is active
    PAUSED = "paused"  # Temporarily paused (e.g., leave of absence)
    TERMINATED = "terminated"  # Monitoring ended (e.g., employee left)
    PENDING = "pending"  # Awaiting first check


class CheckType(str, Enum):
    """Type of monitoring check."""

    SCHEDULED = "scheduled"  # Regular scheduled check
    TRIGGERED = "triggered"  # Triggered by event (e.g., HRIS update)
    REALTIME = "realtime"  # Real-time alert (V3 only)
    MANUAL = "manual"  # Manually requested check


class CheckStatus(str, Enum):
    """Status of a monitoring check execution."""

    PENDING = "pending"  # Awaiting execution
    IN_PROGRESS = "in_progress"  # Currently executing
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed during execution
    PARTIAL = "partial"  # Partially completed (some sources failed)
    SKIPPED = "skipped"  # Skipped (e.g., monitoring paused)


class LifecycleEventType(str, Enum):
    """Types of employee lifecycle events."""

    POSITION_CHANGE = "position_change"  # Changed job role
    PROMOTION = "promotion"  # Promoted to critical role
    TRANSFER = "transfer"  # Transferred to different location/team
    LEAVE_OF_ABSENCE = "leave_of_absence"  # On leave
    RETURN_FROM_LEAVE = "return_from_leave"  # Returned from leave
    TERMINATION = "termination"  # Employment ended
    REHIRE = "rehire"  # Previously terminated, now rehired
    VIGILANCE_UPGRADE = "vigilance_upgrade"  # Upgraded vigilance level
    VIGILANCE_DOWNGRADE = "vigilance_downgrade"  # Downgraded vigilance level


class DeltaSeverity(str, Enum):
    """Severity of a profile delta/change."""

    CRITICAL = "critical"  # Immediate attention required
    HIGH = "high"  # Significant change
    MEDIUM = "medium"  # Notable change
    LOW = "low"  # Minor change
    POSITIVE = "positive"  # Positive change (e.g., resolved issue)


class AlertSeverity(str, Enum):
    """Severity level for monitoring alerts."""

    CRITICAL = "critical"  # Immediate escalation
    HIGH = "high"  # Urgent review needed
    MEDIUM = "medium"  # Review within SLA
    LOW = "low"  # For awareness only


# =============================================================================
# Configuration Models
# =============================================================================


class MonitoringConfig(BaseModel):
    """Configuration for ongoing monitoring of a subject.

    Defines what checks to perform, how often, and alert routing.

    Attributes:
        config_id: Unique identifier for this configuration.
        subject_id: ID of the subject being monitored.
        entity_id: Associated entity ID in the entity system.
        tenant_id: Tenant that owns this monitoring configuration.
        vigilance_level: Determines check frequency (V1/V2/V3).
        service_tier: Standard or Enhanced tier.
        degrees: Search depth (D1/D2/D3).
        locale: Geographic jurisdiction.
        role_category: Job role category for relevance.
        baseline_profile_id: Reference profile for delta detection.
        status: Current monitoring status.
        start_date: When monitoring began.
        next_check_date: When the next check is scheduled.
        last_check_date: When the last check was executed.
        pause_reason: Reason for pause if paused.
        pause_until: When to resume if paused.
        alert_recipients: Email addresses for alerts.
        escalation_path: Escalation recipients.
        sanctions_realtime: Enable real-time sanctions alerts (V3).
        adverse_media_continuous: Enable continuous adverse media (V3).
        dark_web_monitoring: Enable dark web monitoring (Enhanced V3).
        checks_completed: Total checks completed.
        alerts_generated: Total alerts generated.
        metadata: Additional configuration metadata.
        created_at: When configuration was created.
        updated_at: When configuration was last updated.
    """

    config_id: UUID = Field(default_factory=uuid7)
    subject_id: UUID
    entity_id: UUID | None = None
    tenant_id: UUID

    # Service configuration
    vigilance_level: VigilanceLevel
    service_tier: ServiceTier = ServiceTier.STANDARD
    degrees: SearchDegree = SearchDegree.D1
    locale: Locale = Locale.US
    role_category: RoleCategory = RoleCategory.STANDARD

    # Baseline for delta detection
    baseline_profile_id: UUID

    # Status
    status: MonitoringStatus = MonitoringStatus.PENDING

    # Schedule
    start_date: date = Field(default_factory=lambda: date.today())
    next_check_date: datetime | None = None
    last_check_date: datetime | None = None

    # Pause handling
    pause_reason: str | None = None
    pause_until: datetime | None = None

    # Alert routing
    alert_recipients: list[str] = Field(default_factory=list)
    escalation_path: list[str] = Field(default_factory=list)

    # V3 real-time options
    sanctions_realtime: bool = False
    adverse_media_continuous: bool = False
    dark_web_monitoring: bool = False  # Enhanced tier only

    # Statistics
    checks_completed: int = 0
    alerts_generated: int = 0

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def model_post_init(self, __context: Any) -> None:
        """Validate configuration constraints."""
        # V0 doesn't have ongoing monitoring
        if self.vigilance_level == VigilanceLevel.V0:
            raise ValueError("V0 vigilance level does not support ongoing monitoring")

        # Dark web monitoring requires Enhanced tier
        if self.dark_web_monitoring and self.service_tier != ServiceTier.ENHANCED:
            raise ValueError("Dark web monitoring requires Enhanced service tier")

        # V3 features require V3 vigilance
        if (
            self.vigilance_level != VigilanceLevel.V3
            and (self.sanctions_realtime or self.adverse_media_continuous)
        ):
            raise ValueError("Real-time monitoring features require V3 vigilance level")


# =============================================================================
# Check Models
# =============================================================================


@dataclass
class ProfileDelta:
    """A detected change between monitoring checks.

    Represents a difference found when comparing current profile
    to baseline or previous check.
    """

    delta_id: UUID = field(default_factory=uuid7)
    delta_type: str = ""  # Type of change (e.g., "new_finding", "status_change")
    category: str = ""  # Finding category (e.g., "criminal", "financial")
    severity: DeltaSeverity = DeltaSeverity.LOW
    description: str = ""
    previous_value: str | None = None
    current_value: str | None = None
    source_provider: str | None = None
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    requires_review: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "delta_id": str(self.delta_id),
            "delta_type": self.delta_type,
            "category": self.category,
            "severity": self.severity.value,
            "description": self.description,
            "previous_value": self.previous_value,
            "current_value": self.current_value,
            "source_provider": self.source_provider,
            "detected_at": self.detected_at.isoformat(),
            "requires_review": self.requires_review,
            "metadata": self.metadata,
        }


@dataclass
class MonitoringAlert:
    """An alert generated from a monitoring check.

    Created when deltas exceed severity thresholds.
    """

    alert_id: UUID = field(default_factory=uuid7)
    monitoring_config_id: UUID = field(default_factory=uuid7)
    check_id: UUID = field(default_factory=uuid7)
    severity: AlertSeverity = AlertSeverity.LOW
    title: str = ""
    description: str = ""
    delta_ids: list[UUID] = field(default_factory=list)
    recipients_notified: list[str] = field(default_factory=list)
    escalated: bool = False
    escalated_to: list[str] = field(default_factory=list)
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved: bool = False
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": str(self.alert_id),
            "monitoring_config_id": str(self.monitoring_config_id),
            "check_id": str(self.check_id),
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "delta_ids": [str(d) for d in self.delta_ids],
            "recipients_notified": self.recipients_notified,
            "escalated": self.escalated,
            "escalated_to": self.escalated_to,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved": self.resolved,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class MonitoringCheck:
    """Record of a single monitoring check execution.

    Captures timing, results, and any deltas or alerts generated.
    """

    check_id: UUID = field(default_factory=uuid7)
    monitoring_config_id: UUID = field(default_factory=uuid7)
    check_type: CheckType = CheckType.SCHEDULED

    # Timing
    scheduled_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Results
    status: CheckStatus = CheckStatus.PENDING
    error_message: str | None = None

    # Detected changes
    deltas_detected: list[ProfileDelta] = field(default_factory=list)
    alerts_generated: list[MonitoringAlert] = field(default_factory=list)

    # Profile
    new_profile_id: UUID | None = None  # Created if deltas found

    # Statistics
    data_sources_checked: int = 0
    queries_executed: int = 0

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        """Mark check as started."""
        self.started_at = datetime.now(UTC)
        self.status = CheckStatus.IN_PROGRESS

    def complete(
        self,
        status: CheckStatus = CheckStatus.COMPLETED,
        error: str | None = None,
    ) -> None:
        """Mark check as complete."""
        self.completed_at = datetime.now(UTC)
        self.status = status
        self.error_message = error

    @property
    def duration_seconds(self) -> float | None:
        """Get check duration in seconds."""
        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def has_critical_deltas(self) -> bool:
        """Check if any critical deltas were detected."""
        return any(d.severity == DeltaSeverity.CRITICAL for d in self.deltas_detected)

    @property
    def has_high_deltas(self) -> bool:
        """Check if any high severity deltas were detected."""
        return any(
            d.severity in (DeltaSeverity.CRITICAL, DeltaSeverity.HIGH) for d in self.deltas_detected
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check_id": str(self.check_id),
            "monitoring_config_id": str(self.monitoring_config_id),
            "check_type": self.check_type.value,
            "scheduled_at": self.scheduled_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "error_message": self.error_message,
            "deltas_detected": [d.to_dict() for d in self.deltas_detected],
            "alerts_generated": [a.to_dict() for a in self.alerts_generated],
            "new_profile_id": str(self.new_profile_id) if self.new_profile_id else None,
            "data_sources_checked": self.data_sources_checked,
            "queries_executed": self.queries_executed,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }


# =============================================================================
# Lifecycle Events
# =============================================================================


@dataclass
class LifecycleEvent:
    """An employee lifecycle event that affects monitoring.

    Lifecycle events from HRIS can trigger monitoring changes.
    """

    event_id: UUID = field(default_factory=uuid7)
    subject_id: UUID = field(default_factory=uuid7)
    tenant_id: UUID = field(default_factory=uuid7)
    event_type: LifecycleEventType = LifecycleEventType.POSITION_CHANGE

    # Event details
    event_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    effective_date: date | None = None
    description: str = ""

    # Changes (if applicable)
    previous_value: str | None = None
    new_value: str | None = None

    # New configuration (if applicable)
    new_locale: Locale | None = None
    new_role_category: RoleCategory | None = None
    new_vigilance_level: VigilanceLevel | None = None

    # Processing status
    processed: bool = False
    processed_at: datetime | None = None
    processing_result: str | None = None

    # Metadata
    source_system: str = "hris"  # System that generated the event
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_processed(self, result: str) -> None:
        """Mark event as processed."""
        self.processed = True
        self.processed_at = datetime.now(UTC)
        self.processing_result = result

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": str(self.event_id),
            "subject_id": str(self.subject_id),
            "tenant_id": str(self.tenant_id),
            "event_type": self.event_type.value,
            "event_date": self.event_date.isoformat(),
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "description": self.description,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
            "new_locale": self.new_locale.value if self.new_locale else None,
            "new_role_category": self.new_role_category.value if self.new_role_category else None,
            "new_vigilance_level": (
                self.new_vigilance_level.value if self.new_vigilance_level else None
            ),
            "processed": self.processed,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "processing_result": self.processing_result,
            "source_system": self.source_system,
            "metadata": self.metadata,
        }


# =============================================================================
# Schedule Result
# =============================================================================


@dataclass
class ScheduleResult:
    """Result of scheduling a monitoring configuration."""

    config_id: UUID = field(default_factory=uuid7)
    success: bool = True
    next_check_date: datetime | None = None
    interval_days: int = 0
    message: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "config_id": str(self.config_id),
            "success": self.success,
            "next_check_date": self.next_check_date.isoformat() if self.next_check_date else None,
            "interval_days": self.interval_days,
            "message": self.message,
            "error": self.error,
        }


# =============================================================================
# Errors
# =============================================================================


class MonitoringError(Exception):
    """Base exception for monitoring errors."""

    def __init__(
        self,
        message: str,
        code: str = "MONITORING_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class MonitoringConfigError(MonitoringError):
    """Error with monitoring configuration."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="CONFIG_ERROR", details=details)


class MonitoringExecutionError(MonitoringError):
    """Error during monitoring check execution."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="EXECUTION_ERROR", details=details)


class MonitoringLifecycleError(MonitoringError):
    """Error processing lifecycle event."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="LIFECYCLE_ERROR", details=details)
