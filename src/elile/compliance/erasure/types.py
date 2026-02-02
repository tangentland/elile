"""Type definitions for GDPR erasure processing.

This module defines the types used in GDPR Article 17 "Right to Erasure"
processing, including erasure operations, confirmation reports, and exceptions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.compliance.retention.types import DataType
from elile.compliance.types import Locale


class ErasureType(str, Enum):
    """Type of erasure operation requested."""

    FULL_ERASURE = "full_erasure"
    """Complete deletion of all personal data."""

    ANONYMIZE = "anonymize"
    """Anonymize PII while preserving statistical data."""

    EXPORT = "export"
    """Export data before erasure (data portability)."""

    SELECTIVE = "selective"
    """Delete only specific data types."""


class ErasureStatus(str, Enum):
    """Status of an erasure operation."""

    PENDING = "pending"
    """Request received, awaiting verification."""

    VERIFIED = "verified"
    """Identity verified, awaiting processing."""

    PROCESSING = "processing"
    """Currently being processed."""

    COMPLETED = "completed"
    """Successfully completed."""

    PARTIALLY_COMPLETED = "partially_completed"
    """Some data deleted, some retained due to exemptions."""

    REJECTED = "rejected"
    """Request rejected (invalid, duplicate, etc.)."""

    BLOCKED = "blocked"
    """Blocked by legal hold or regulatory requirement."""


class ErasureExemption(str, Enum):
    """Reasons why data may be exempt from erasure."""

    LEGAL_HOLD = "legal_hold"
    """Data under legal hold (litigation, investigation)."""

    REGULATORY_REQUIREMENT = "regulatory_requirement"
    """Regulatory requirement to retain (FCRA, AML, etc.)."""

    CONTRACT_OBLIGATION = "contract_obligation"
    """Contractual obligation to retain."""

    LEGITIMATE_INTEREST = "legitimate_interest"
    """Legitimate business interest override (Article 17(3))."""

    PUBLIC_INTEREST = "public_interest"
    """Public interest in archiving (Article 17(3)(d))."""

    LEGAL_CLAIMS = "legal_claims"
    """Establishment, exercise, or defense of legal claims."""

    FREEDOM_OF_EXPRESSION = "freedom_of_expression"
    """Freedom of expression and information."""


class AnonymizationMethod(str, Enum):
    """Methods for anonymizing personal data."""

    PSEUDONYMIZATION = "pseudonymization"
    """Replace identifiers with pseudonyms (reversible with key)."""

    MASKING = "masking"
    """Mask portions of data (e.g., ***-**-6789)."""

    GENERALIZATION = "generalization"
    """Replace with broader category (e.g., age range)."""

    TOKENIZATION = "tokenization"
    """Replace with random tokens."""

    REDACTION = "redaction"
    """Complete removal of field value."""

    HASHING = "hashing"
    """One-way hash of values (irreversible)."""


@dataclass
class AnonymizationRule:
    """Rule for anonymizing a specific field."""

    field_name: str
    """Name of the field to anonymize."""

    method: AnonymizationMethod
    """Anonymization method to use."""

    preserve_format: bool = False
    """Whether to preserve the format (e.g., date stays date)."""

    preserve_length: bool = False
    """Whether to preserve the length of the value."""

    custom_value: str | None = None
    """Custom replacement value (for redaction)."""


@dataclass
class ErasedItem:
    """Record of a single erased data item."""

    data_id: UUID
    """ID of the erased data item."""

    data_type: DataType
    """Type of data that was erased."""

    action_taken: str
    """Action taken (deleted, anonymized, etc.)."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    """When the action was taken."""

    original_hash: str | None = None
    """Hash of original data (for audit verification)."""


@dataclass
class RetainedItem:
    """Record of data retained with exemption."""

    data_id: UUID
    """ID of the retained data item."""

    data_type: DataType
    """Type of data retained."""

    exemption: ErasureExemption
    """Reason for retention."""

    exemption_details: str = ""
    """Additional details about the exemption."""

    legal_basis: str | None = None
    """Legal basis (e.g., 'FCRA 604(b)(1)')."""

    retention_until: datetime | None = None
    """When the retention requirement expires."""


class ErasureOperation(BaseModel):
    """Complete record of an erasure operation."""

    operation_id: UUID = Field(default_factory=uuid7)
    """Unique identifier for this operation."""

    subject_id: UUID
    """ID of the data subject."""

    tenant_id: UUID
    """Tenant that owns the data."""

    locale: Locale
    """Locale for compliance requirements."""

    # Request details
    erasure_type: ErasureType
    """Type of erasure requested."""

    requested_data_types: list[DataType] = Field(default_factory=list)
    """Specific data types to erase (empty = all)."""

    reason: str | None = None
    """Reason provided for the request."""

    # Verification
    requester_id: str | None = None
    """ID of the person making the request."""

    verification_method: str | None = None
    """How identity was verified."""

    verified_at: datetime | None = None
    """When identity was verified."""

    # Processing
    status: ErasureStatus = ErasureStatus.PENDING
    """Current status of the operation."""

    started_at: datetime | None = None
    """When processing started."""

    completed_at: datetime | None = None
    """When processing completed."""

    # Timestamps
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    """When the request was received."""

    deadline: datetime | None = None
    """Deadline for completion (GDPR: 30 days)."""

    # Results
    erased_items: list[dict[str, Any]] = Field(default_factory=list)
    """Items that were erased."""

    retained_items: list[dict[str, Any]] = Field(default_factory=list)
    """Items retained with exemptions."""

    errors: list[str] = Field(default_factory=list)
    """Errors encountered during processing."""

    # Audit
    audit_log: list[dict[str, Any]] = Field(default_factory=list)
    """Audit trail of all actions."""

    def add_audit_entry(self, action: str, details: dict[str, Any] | None = None) -> None:
        """Add an entry to the audit log."""
        self.audit_log.append(
            {
                "action": action,
                "timestamp": datetime.utcnow().isoformat(),
                "details": details or {},
            }
        )

    @property
    def items_erased_count(self) -> int:
        """Count of items erased."""
        return len(self.erased_items)

    @property
    def items_retained_count(self) -> int:
        """Count of items retained."""
        return len(self.retained_items)

    @property
    def is_complete(self) -> bool:
        """Check if operation is complete."""
        return self.status in (
            ErasureStatus.COMPLETED,
            ErasureStatus.PARTIALLY_COMPLETED,
            ErasureStatus.REJECTED,
            ErasureStatus.BLOCKED,
        )


class ErasureConfirmationReport(BaseModel):
    """Confirmation report for completed erasure operations.

    Generated after erasure to confirm what was deleted
    and what was retained with explanations.
    """

    report_id: UUID = Field(default_factory=uuid7)
    """Unique identifier for this report."""

    operation_id: UUID
    """ID of the erasure operation."""

    subject_id: UUID
    """ID of the data subject."""

    tenant_id: UUID
    """Tenant that owns the data."""

    locale: Locale
    """Locale for compliance requirements."""

    # Timing
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    """When the report was generated."""

    request_date: datetime
    """When the erasure was requested."""

    completion_date: datetime
    """When the erasure was completed."""

    processing_days: int = 0
    """Days from request to completion."""

    # Status
    status: ErasureStatus
    """Final status of the operation."""

    is_fully_completed: bool = False
    """Whether all requested data was erased."""

    # Summary
    data_categories_requested: list[str] = Field(default_factory=list)
    """Categories of data requested for erasure."""

    data_categories_erased: list[str] = Field(default_factory=list)
    """Categories of data actually erased."""

    data_categories_retained: list[str] = Field(default_factory=list)
    """Categories of data retained with exemptions."""

    # Counts
    total_items_processed: int = 0
    """Total items processed."""

    items_erased: int = 0
    """Count of items erased."""

    items_anonymized: int = 0
    """Count of items anonymized."""

    items_retained: int = 0
    """Count of items retained."""

    # Details
    erased_data_summary: list[dict[str, Any]] = Field(default_factory=list)
    """Summary of erased data by category."""

    retained_data_explanation: list[dict[str, Any]] = Field(default_factory=list)
    """Explanation for each retained item."""

    # Compliance
    gdpr_compliance_statement: str = ""
    """Statement of GDPR compliance."""

    legal_basis_for_retention: list[str] = Field(default_factory=list)
    """Legal bases cited for any retention."""

    # Verification
    verification_hash: str | None = None
    """Hash for report integrity verification."""

    authorized_by: str | None = None
    """Who authorized the erasure."""


class LegalHoldException(Exception):
    """Exception raised when erasure is blocked by legal hold."""

    def __init__(
        self,
        subject_id: UUID,
        hold_reason: str,
        hold_placed_at: datetime | None = None,
    ):
        """Initialize with hold details.

        Args:
            subject_id: ID of the subject
            hold_reason: Reason for the legal hold
            hold_placed_at: When the hold was placed
        """
        self.subject_id = subject_id
        self.hold_reason = hold_reason
        self.hold_placed_at = hold_placed_at
        super().__init__(f"Subject {subject_id} has active legal hold: {hold_reason}")


class ErasureBlockedException(Exception):
    """Exception raised when erasure is blocked for any reason."""

    def __init__(
        self,
        subject_id: UUID,
        exemption: ErasureExemption,
        reason: str,
    ):
        """Initialize with block details.

        Args:
            subject_id: ID of the subject
            exemption: Type of exemption
            reason: Detailed reason for blocking
        """
        self.subject_id = subject_id
        self.exemption = exemption
        self.reason = reason
        super().__init__(f"Erasure blocked for subject {subject_id}: {reason}")


class ErasureVerificationError(Exception):
    """Exception raised when identity verification fails."""

    def __init__(self, subject_id: UUID, reason: str):
        """Initialize with verification error details.

        Args:
            subject_id: ID of the subject
            reason: Why verification failed
        """
        self.subject_id = subject_id
        self.reason = reason
        super().__init__(f"Identity verification failed for subject {subject_id}: {reason}")
