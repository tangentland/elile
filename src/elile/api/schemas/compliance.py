"""API schemas for Compliance Portal endpoints.

This module defines the request and response schemas for the Compliance Portal API,
providing audit logs, consent tracking, data erasure requests, and compliance reports.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from elile.compliance.consent import ConsentScope, ConsentVerificationMethod
from elile.compliance.types import Locale
from elile.db.models.audit import AuditEventType, AuditSeverity

# =============================================================================
# Enums
# =============================================================================


class ErasureStatus(str, Enum):
    """Status of a data erasure request."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ComplianceStatus(str, Enum):
    """Overall compliance status."""

    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"


# =============================================================================
# Audit Log Schemas
# =============================================================================


class AuditEventSummary(BaseModel):
    """Summary of an audit event for the compliance portal."""

    audit_id: UUID = Field(..., description="Unique audit event identifier")
    event_type: str = Field(..., description="Type of audit event")
    severity: str = Field(..., description="Event severity level")
    created_at: datetime = Field(..., description="When the event occurred")
    user_id: UUID | None = Field(default=None, description="User who triggered the event")
    entity_id: UUID | None = Field(default=None, description="Affected entity ID")
    resource_type: str | None = Field(default=None, description="Type of affected resource")
    resource_id: str | None = Field(default=None, description="ID of affected resource")
    ip_address: str | None = Field(default=None, description="Client IP address")
    event_data: dict[str, Any] = Field(default_factory=dict, description="Event details")

    model_config = {
        "json_schema_extra": {
            "example": {
                "audit_id": "019478f2-1234-7000-8000-abcdef123456",
                "event_type": "screening.initiated",
                "severity": "info",
                "created_at": "2026-01-30T12:00:00Z",
                "user_id": "019478f2-abcd-7000-8000-000000000001",
                "entity_id": "019478f2-abcd-7000-8000-000000000002",
                "resource_type": "screening",
                "resource_id": "SCR-12345",
                "ip_address": "192.168.1.1",
                "event_data": {"subject_name": "John Doe"},
            }
        }
    }


class AuditLogQueryParams(BaseModel):
    """Query parameters for audit log."""

    start_date: datetime | None = Field(default=None, description="Filter events after this date")
    end_date: datetime | None = Field(default=None, description="Filter events before this date")
    event_type: AuditEventType | None = Field(default=None, description="Filter by event type")
    severity: AuditSeverity | None = Field(default=None, description="Filter by severity level")
    entity_id: UUID | None = Field(default=None, description="Filter by entity ID")
    user_id: UUID | None = Field(default=None, description="Filter by user ID")


class AuditLogResponse(BaseModel):
    """Paginated response for audit log query."""

    items: list[AuditEventSummary] = Field(..., description="Audit events")
    total: int = Field(..., ge=0, description="Total matching events")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    has_more: bool = Field(..., description="Whether more pages exist")
    filters_applied: dict[str, Any] = Field(default_factory=dict, description="Applied filters")


# =============================================================================
# Consent Tracking Schemas
# =============================================================================


class ConsentSummary(BaseModel):
    """Summary of a consent record."""

    consent_id: UUID = Field(..., description="Consent identifier")
    subject_id: UUID = Field(..., description="Subject who granted consent")
    scopes: list[ConsentScope] = Field(..., description="Granted consent scopes")
    granted_at: datetime = Field(..., description="When consent was granted")
    expires_at: datetime | None = Field(default=None, description="When consent expires")
    verification_method: ConsentVerificationMethod = Field(
        ..., description="How consent was verified"
    )
    locale: Locale = Field(..., description="Applicable locale")
    is_valid: bool = Field(..., description="Whether consent is currently valid")
    is_revoked: bool = Field(default=False, description="Whether consent was revoked")
    revoked_at: datetime | None = Field(default=None, description="When consent was revoked")

    model_config = {
        "json_schema_extra": {
            "example": {
                "consent_id": "019478f2-1234-7000-8000-abcdef123456",
                "subject_id": "019478f2-abcd-7000-8000-000000000001",
                "scopes": ["background_check", "criminal_records"],
                "granted_at": "2026-01-15T10:00:00Z",
                "expires_at": "2027-01-15T10:00:00Z",
                "verification_method": "e_signature",
                "locale": "US",
                "is_valid": True,
                "is_revoked": False,
                "revoked_at": None,
            }
        }
    }


class ConsentTrackingMetrics(BaseModel):
    """Metrics for consent tracking."""

    total_consents: int = Field(default=0, ge=0, description="Total consent records")
    active_consents: int = Field(default=0, ge=0, description="Currently valid consents")
    expired_consents: int = Field(default=0, ge=0, description="Expired consents")
    revoked_consents: int = Field(default=0, ge=0, description="Revoked consents")
    pending_renewals: int = Field(default=0, ge=0, description="Consents expiring within 30 days")
    by_scope: dict[str, int] = Field(default_factory=dict, description="Consent counts by scope")
    by_verification_method: dict[str, int] = Field(
        default_factory=dict, description="Consent counts by verification method"
    )


class ConsentTrackingResponse(BaseModel):
    """Response for consent tracking endpoint."""

    metrics: ConsentTrackingMetrics = Field(..., description="Consent metrics")
    recent_consents: list[ConsentSummary] = Field(
        default_factory=list, description="Recent consent records (up to 10)"
    )
    expiring_soon: list[ConsentSummary] = Field(
        default_factory=list, description="Consents expiring within 30 days"
    )
    updated_at: datetime = Field(..., description="When data was last updated")


# =============================================================================
# Data Erasure Schemas
# =============================================================================


class DataErasureRequest(BaseModel):
    """Request to initiate GDPR data erasure."""

    subject_id: UUID = Field(..., description="Subject requesting erasure")
    reason: str = Field(
        ..., min_length=10, max_length=500, description="Reason for erasure request"
    )
    requester_email: str | None = Field(default=None, description="Email for erasure confirmation")
    include_audit_records: bool = Field(
        default=False,
        description="Whether to include audit records (may be retained for compliance)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "subject_id": "019478f2-abcd-7000-8000-000000000001",
                "reason": "Subject requested data deletion under GDPR Article 17",
                "requester_email": "subject@example.com",
                "include_audit_records": False,
            }
        }
    }


class DataErasureResponse(BaseModel):
    """Response for data erasure request."""

    erasure_id: UUID = Field(..., description="Unique erasure request identifier")
    subject_id: UUID = Field(..., description="Subject whose data is being erased")
    status: ErasureStatus = Field(..., description="Current status of erasure request")
    requested_at: datetime = Field(..., description="When erasure was requested")
    estimated_completion: datetime | None = Field(
        default=None, description="Estimated completion time"
    )
    data_categories_affected: list[str] = Field(
        default_factory=list, description="Categories of data to be erased"
    )
    retention_exceptions: list[str] = Field(
        default_factory=list, description="Data categories retained for compliance"
    )
    confirmation_token: str | None = Field(
        default=None, description="Token for tracking erasure status"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "erasure_id": "019478f2-1234-7000-8000-abcdef123456",
                "subject_id": "019478f2-abcd-7000-8000-000000000001",
                "status": "pending",
                "requested_at": "2026-01-30T12:00:00Z",
                "estimated_completion": "2026-02-06T12:00:00Z",
                "data_categories_affected": [
                    "personal_identifiers",
                    "employment_history",
                    "screening_results",
                ],
                "retention_exceptions": ["audit_logs", "compliance_records"],
                "confirmation_token": "ERS-ABC123",
            }
        }
    }


# =============================================================================
# Compliance Reports Schemas
# =============================================================================


class ComplianceReportSummary(BaseModel):
    """Summary of a compliance report."""

    report_id: UUID = Field(..., description="Report identifier")
    report_type: str = Field(..., description="Type of compliance report")
    screening_id: UUID | None = Field(default=None, description="Related screening ID")
    subject_id: UUID | None = Field(default=None, description="Related subject ID")
    locale: Locale = Field(..., description="Locale for compliance rules")
    generated_at: datetime = Field(..., description="When report was generated")
    compliance_status: ComplianceStatus = Field(..., description="Overall compliance status")
    rules_evaluated: int = Field(default=0, ge=0, description="Number of rules evaluated")
    violations_found: int = Field(default=0, ge=0, description="Number of violations found")

    model_config = {
        "json_schema_extra": {
            "example": {
                "report_id": "019478f2-1234-7000-8000-abcdef123456",
                "report_type": "screening_audit",
                "screening_id": "019478f2-abcd-7000-8000-000000000001",
                "subject_id": "019478f2-abcd-7000-8000-000000000002",
                "locale": "US",
                "generated_at": "2026-01-30T12:00:00Z",
                "compliance_status": "compliant",
                "rules_evaluated": 15,
                "violations_found": 0,
            }
        }
    }


class ComplianceReportsListResponse(BaseModel):
    """Paginated response for compliance reports list."""

    items: list[ComplianceReportSummary] = Field(..., description="Compliance reports")
    total: int = Field(..., ge=0, description="Total reports")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    has_more: bool = Field(..., description="Whether more pages exist")
    filters_applied: dict[str, Any] = Field(default_factory=dict, description="Applied filters")


# =============================================================================
# Compliance Metrics Schemas
# =============================================================================


class ComplianceMetrics(BaseModel):
    """Overall compliance metrics for the portal."""

    total_screenings: int = Field(default=0, ge=0, description="Total screenings audited")
    compliant_screenings: int = Field(default=0, ge=0, description="Fully compliant screenings")
    partial_compliance: int = Field(default=0, ge=0, description="Screenings with minor issues")
    non_compliant_screenings: int = Field(default=0, ge=0, description="Non-compliant screenings")
    compliance_rate: float = Field(
        default=100.0, ge=0, le=100, description="Overall compliance percentage"
    )
    active_consents: int = Field(default=0, ge=0, description="Active consent records")
    pending_erasures: int = Field(default=0, ge=0, description="Pending erasure requests")
    recent_violations: int = Field(default=0, ge=0, description="Violations in last 30 days")
    by_locale: dict[str, int] = Field(default_factory=dict, description="Screenings by locale")
    by_rule_type: dict[str, int] = Field(
        default_factory=dict, description="Violations by rule type"
    )


class ComplianceMetricsResponse(BaseModel):
    """Response for compliance metrics endpoint."""

    metrics: ComplianceMetrics = Field(..., description="Compliance metrics")
    recent_audit_events: list[AuditEventSummary] = Field(
        default_factory=list, description="Recent compliance-related events"
    )
    updated_at: datetime = Field(..., description="When data was last updated")

    model_config = {
        "json_schema_extra": {
            "example": {
                "metrics": {
                    "total_screenings": 150,
                    "compliant_screenings": 142,
                    "partial_compliance": 5,
                    "non_compliant_screenings": 3,
                    "compliance_rate": 94.7,
                    "active_consents": 200,
                    "pending_erasures": 2,
                    "recent_violations": 1,
                    "by_locale": {"US": 100, "EU": 30, "UK": 20},
                    "by_rule_type": {"FCRA": 2, "GDPR": 1},
                },
                "recent_audit_events": [],
                "updated_at": "2026-01-30T12:00:00Z",
            }
        }
    }
