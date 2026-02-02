"""Data retention type definitions.

This module defines the core types for the data retention framework:
- DataType: Categories of data subject to retention policies
- DeletionMethod: Methods for removing data
- RetentionPolicy: Policy configuration for data retention
- RetentionStatus: Status of data retention lifecycle
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.compliance.types import Locale


class DataType(str, Enum):
    """Categories of data subject to retention policies.

    Each data type has specific retention requirements based on
    regulatory frameworks and business needs.
    """

    # Screening data
    SCREENING_RESULT = "screening_result"
    """Final screening results and risk assessments."""

    SCREENING_FINDING = "screening_finding"
    """Individual findings from screening investigations."""

    SCREENING_RAW_DATA = "screening_raw_data"
    """Raw data from provider searches (minimized retention)."""

    # Entity data
    ENTITY_PROFILE = "entity_profile"
    """Subject profile information (PII)."""

    ENTITY_RELATION = "entity_relation"
    """Entity relationship data."""

    # Audit and compliance
    AUDIT_LOG = "audit_log"
    """Audit trail entries (immutable, extended retention)."""

    CONSENT_RECORD = "consent_record"
    """Consent documentation and verification."""

    DISCLOSURE_RECORD = "disclosure_record"
    """FCRA/GDPR disclosure records."""

    ADVERSE_ACTION = "adverse_action"
    """Adverse action documentation."""

    # Reports
    REPORT = "report"
    """Generated reports (may contain PII)."""

    # Provider data
    PROVIDER_RESPONSE = "provider_response"
    """Raw provider API responses."""

    CACHE_ENTRY = "cache_entry"
    """Cached data from providers."""

    # Monitoring
    MONITORING_ALERT = "monitoring_alert"
    """Ongoing monitoring alerts."""

    MONITORING_CHECK = "monitoring_check"
    """Monitoring check records."""


class DeletionMethod(str, Enum):
    """Methods for removing data when retention period expires.

    Different methods provide different levels of data removal
    based on compliance requirements and recoverability needs.
    """

    SOFT_DELETE = "soft_delete"
    """Mark as deleted but retain in database (recoverable)."""

    HARD_DELETE = "hard_delete"
    """Permanently remove from database."""

    ANONYMIZE = "anonymize"
    """Remove PII but retain anonymized record for statistics."""

    ARCHIVE = "archive"
    """Move to cold storage before deletion."""

    CRYPTO_SHRED = "crypto_shred"
    """Delete encryption keys, rendering data unreadable."""


class RetentionAction(str, Enum):
    """Actions taken during retention lifecycle."""

    CREATED = "created"
    """Data was created and retention clock started."""

    ARCHIVED = "archived"
    """Data was moved to archive storage."""

    ANONYMIZED = "anonymized"
    """Data was anonymized."""

    DELETED = "deleted"
    """Data was deleted."""

    EXTENDED = "extended"
    """Retention was extended (e.g., legal hold)."""

    HOLD_PLACED = "hold_placed"
    """Legal hold placed on data."""

    HOLD_RELEASED = "hold_released"
    """Legal hold released."""


class RetentionPolicy(BaseModel):
    """Data retention policy configuration.

    Defines how long data should be retained and what action
    to take when the retention period expires.
    """

    policy_id: UUID = Field(default_factory=uuid7)
    """Unique identifier for this policy."""

    name: str
    """Human-readable policy name."""

    description: str = ""
    """Policy description."""

    # Scope
    data_type: DataType
    """Type of data this policy applies to."""

    locale: Locale | None = None
    """Locale this policy applies to (None = all locales)."""

    # Timing
    retention_days: int
    """Days to retain data from creation."""

    archive_after_days: int | None = None
    """Days before moving to archive (None = no archive)."""

    warning_days: int = 30
    """Days before expiry to generate warnings."""

    # Actions
    deletion_method: DeletionMethod = DeletionMethod.SOFT_DELETE
    """Method to use when deleting data."""

    archive_before_delete: bool = False
    """Whether to archive data before deletion."""

    # Compliance
    regulatory_basis: str | None = None
    """Regulatory basis for this policy (e.g., 'FCRA 7-year rule')."""

    # Overrides
    subject_request_override: bool = True
    """Whether subjects can request early deletion (GDPR right to erasure)."""

    legal_hold_exempt: bool = False
    """Whether legal holds can override this policy."""

    @property
    def retention_period(self) -> timedelta:
        """Get retention period as timedelta."""
        return timedelta(days=self.retention_days)

    @property
    def archive_period(self) -> timedelta | None:
        """Get archive period as timedelta."""
        if self.archive_after_days is None:
            return None
        return timedelta(days=self.archive_after_days)

    @property
    def warning_period(self) -> timedelta:
        """Get warning period as timedelta."""
        return timedelta(days=self.warning_days)

    def calculate_expiry(self, created_at: datetime) -> datetime:
        """Calculate when data expires based on creation date."""
        return created_at + self.retention_period

    def calculate_archive_date(self, created_at: datetime) -> datetime | None:
        """Calculate when data should be archived."""
        if self.archive_after_days is None:
            return None
        return created_at + timedelta(days=self.archive_after_days)

    def calculate_warning_date(self, created_at: datetime) -> datetime:
        """Calculate when to start warning about expiry."""
        return self.calculate_expiry(created_at) - self.warning_period


class RetentionStatus(str, Enum):
    """Current retention status of data."""

    ACTIVE = "active"
    """Data is within retention period."""

    ARCHIVE_PENDING = "archive_pending"
    """Data is scheduled for archival."""

    ARCHIVED = "archived"
    """Data has been archived."""

    EXPIRY_WARNING = "expiry_warning"
    """Data is approaching expiry."""

    DELETION_PENDING = "deletion_pending"
    """Data is scheduled for deletion."""

    DELETED = "deleted"
    """Data has been deleted."""

    LEGAL_HOLD = "legal_hold"
    """Data is under legal hold."""


@dataclass
class RetentionRecord:
    """Tracks retention lifecycle for a piece of data.

    Records all retention-related events and current status.
    """

    record_id: UUID = field(default_factory=uuid7)
    """Unique identifier for this retention record."""

    data_type: DataType = DataType.SCREENING_RESULT
    """Type of data being tracked."""

    data_id: UUID = field(default_factory=uuid7)
    """ID of the data item being tracked."""

    tenant_id: UUID = field(default_factory=uuid7)
    """Tenant that owns this data."""

    policy_id: UUID = field(default_factory=uuid7)
    """ID of the retention policy applied."""

    status: RetentionStatus = RetentionStatus.ACTIVE
    """Current retention status."""

    created_at: datetime = field(default_factory=datetime.utcnow)
    """When the data was created."""

    expires_at: datetime = field(default_factory=datetime.utcnow)
    """When the data expires."""

    archive_at: datetime | None = None
    """When the data should be archived."""

    deleted_at: datetime | None = None
    """When the data was deleted."""

    legal_hold: bool = False
    """Whether data is under legal hold."""

    legal_hold_reason: str | None = None
    """Reason for legal hold."""

    legal_hold_placed_at: datetime | None = None
    """When legal hold was placed."""

    events: list[dict[str, Any]] = field(default_factory=list)
    """History of retention events."""

    def add_event(self, action: RetentionAction, details: dict[str, Any] | None = None) -> None:
        """Record a retention event."""
        event = {
            "action": action.value,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {},
        }
        self.events.append(event)

    def place_legal_hold(self, reason: str) -> None:
        """Place a legal hold on this data."""
        self.legal_hold = True
        self.legal_hold_reason = reason
        self.legal_hold_placed_at = datetime.utcnow()
        self.status = RetentionStatus.LEGAL_HOLD
        self.add_event(RetentionAction.HOLD_PLACED, {"reason": reason})

    def release_legal_hold(self) -> None:
        """Release legal hold on this data."""
        self.legal_hold = False
        self.legal_hold_reason = None
        self.status = RetentionStatus.ACTIVE
        self.add_event(RetentionAction.HOLD_RELEASED)

    @property
    def is_expired(self) -> bool:
        """Check if data has expired."""
        if self.legal_hold:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_warning_period(self) -> bool:
        """Check if data is in warning period before expiry."""
        if self.legal_hold:
            return False
        # Default 30-day warning period
        warning_start = self.expires_at - timedelta(days=30)
        return warning_start <= datetime.utcnow() < self.expires_at

    @property
    def days_until_expiry(self) -> int:
        """Get days until data expires."""
        if self.legal_hold:
            return -1  # Indefinite
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)


@dataclass
class RetentionReport:
    """Summary report of retention status across data."""

    report_id: UUID = field(default_factory=uuid7)
    """Unique identifier for this report."""

    generated_at: datetime = field(default_factory=datetime.utcnow)
    """When the report was generated."""

    tenant_id: UUID | None = None
    """Tenant this report covers (None = all tenants)."""

    # Counts by status
    active_count: int = 0
    """Count of active data items."""

    archived_count: int = 0
    """Count of archived data items."""

    expiry_warning_count: int = 0
    """Count of items approaching expiry."""

    deletion_pending_count: int = 0
    """Count of items pending deletion."""

    legal_hold_count: int = 0
    """Count of items under legal hold."""

    # Counts by data type
    counts_by_type: dict[str, int] = field(default_factory=dict)
    """Counts broken down by data type."""

    # Upcoming expirations
    expiring_next_7_days: int = 0
    """Items expiring in next 7 days."""

    expiring_next_30_days: int = 0
    """Items expiring in next 30 days."""

    expiring_next_90_days: int = 0
    """Items expiring in next 90 days."""

    # Compliance metrics
    compliant_count: int = 0
    """Items with valid retention policies."""

    non_compliant_count: int = 0
    """Items missing or with invalid policies."""

    @property
    def total_count(self) -> int:
        """Get total count of tracked items."""
        return (
            self.active_count
            + self.archived_count
            + self.expiry_warning_count
            + self.deletion_pending_count
            + self.legal_hold_count
        )

    @property
    def compliance_rate(self) -> float:
        """Get compliance rate as percentage."""
        total = self.compliant_count + self.non_compliant_count
        if total == 0:
            return 100.0
        return (self.compliant_count / total) * 100


class ErasureRequest(BaseModel):
    """Request for data erasure (GDPR right to be forgotten).

    Tracks subject requests for data deletion.
    """

    request_id: UUID = Field(default_factory=uuid7)
    """Unique identifier for this request."""

    subject_id: UUID
    """ID of the subject requesting erasure."""

    tenant_id: UUID
    """Tenant that owns the data."""

    locale: Locale
    """Locale for determining compliance requirements."""

    requested_at: datetime = Field(default_factory=datetime.utcnow)
    """When the request was made."""

    requested_data_types: list[DataType] = Field(default_factory=list)
    """Types of data to be erased (empty = all)."""

    reason: str | None = None
    """Reason for erasure request."""

    verified: bool = False
    """Whether the requester's identity has been verified."""

    verified_at: datetime | None = None
    """When identity was verified."""

    verification_method: str | None = None
    """Method used to verify identity."""

    status: str = "pending"
    """Status: pending, processing, completed, rejected."""

    completed_at: datetime | None = None
    """When the request was completed."""

    rejection_reason: str | None = None
    """Reason if request was rejected."""

    items_deleted: int = 0
    """Count of items deleted."""

    items_retained: int = 0
    """Count of items retained (exempt from erasure)."""

    retention_reasons: list[str] = Field(default_factory=list)
    """Reasons for retaining any data."""
