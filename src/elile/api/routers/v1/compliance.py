"""Compliance Portal API endpoints.

This module provides REST API endpoints for the Compliance Portal:
- GET /compliance/audit-log - Query audit events
- GET /compliance/consent-tracking - Consent status and metrics
- POST /compliance/data-erasure - Request GDPR data erasure
- GET /compliance/reports - List compliance reports
- GET /compliance/metrics - Overall compliance metrics
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid7

import structlog
from fastapi import APIRouter, Depends, Query

from elile.api.dependencies import get_request_context
from elile.api.schemas.compliance import (
    AuditEventSummary,
    AuditLogResponse,
    ComplianceMetrics,
    ComplianceMetricsResponse,
    ComplianceReportsListResponse,
    ComplianceReportSummary,
    ComplianceStatus,
    ConsentSummary,
    ConsentTrackingMetrics,
    ConsentTrackingResponse,
    DataErasureRequest,
    DataErasureResponse,
    ErasureStatus,
)
from elile.compliance.consent import Consent, ConsentManager
from elile.core.context import RequestContext
from elile.db.models.audit import AuditEvent, AuditEventType, AuditSeverity

logger = structlog.get_logger()

router = APIRouter(prefix="/compliance", tags=["compliance-portal"])


# =============================================================================
# In-Memory Storage (for demonstration - production uses database)
# =============================================================================

# Audit events storage (in-memory for testing)
_audit_events: list[AuditEvent] = []

# Consent manager
_consent_manager: ConsentManager | None = None

# Erasure requests storage
_erasure_requests: dict[str, DataErasureResponse] = {}

# Compliance reports storage
_compliance_reports: dict[str, ComplianceReportSummary] = {}


def _get_consent_manager() -> ConsentManager:
    """Get or create the consent manager singleton."""
    global _consent_manager
    if _consent_manager is None:
        _consent_manager = ConsentManager()  # type: ignore[no-untyped-call]
    return _consent_manager


def get_consent_manager() -> ConsentManager:
    """Dependency for consent manager."""
    return _get_consent_manager()


# =============================================================================
# Audit Log Endpoint
# =============================================================================


@router.get(
    "/audit-log",
    response_model=AuditLogResponse,
    summary="Query audit log",
    description="""
    Query audit events for compliance review and investigation.

    **Filters:**
    - start_date/end_date: Filter by date range
    - event_type: Filter by specific event type
    - severity: Filter by severity level
    - entity_id: Filter by affected entity
    - user_id: Filter by triggering user

    Results are sorted by creation date (newest first).
    """,
    responses={
        200: {"description": "List of audit events"},
    },
)
async def query_audit_log(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    start_date: Annotated[
        datetime | None,
        Query(description="Filter events after this date (ISO 8601)"),
    ] = None,
    end_date: Annotated[
        datetime | None,
        Query(description="Filter events before this date (ISO 8601)"),
    ] = None,
    event_type: Annotated[
        AuditEventType | None,
        Query(description="Filter by event type"),
    ] = None,
    severity: Annotated[
        AuditSeverity | None,
        Query(description="Filter by severity level"),
    ] = None,
    entity_id: Annotated[
        UUID | None,
        Query(description="Filter by affected entity ID"),
    ] = None,
    user_id: Annotated[
        UUID | None,
        Query(description="Filter by triggering user ID"),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 50,
) -> AuditLogResponse:
    """Query audit log with filters.

    Args:
        ctx: Request context with tenant info.
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        event_type: Optional event type filter.
        severity: Optional severity filter.
        entity_id: Optional entity ID filter.
        user_id: Optional user ID filter.
        page: Page number (1-indexed).
        page_size: Number of items per page.

    Returns:
        AuditLogResponse with paginated audit events.
    """
    logger.debug(
        "Querying audit log",
        tenant_id=str(ctx.tenant_id),
        event_type=event_type.value if event_type else None,
        page=page,
        page_size=page_size,
    )

    # Get audit events for tenant (in-memory storage for now)
    filtered = [e for e in _audit_events if e.tenant_id == ctx.tenant_id]
    filters_applied: dict[str, str | None] = {}

    # Apply filters
    if start_date:
        filtered = [e for e in filtered if e.created_at >= start_date]
        filters_applied["start_date"] = start_date.isoformat()

    if end_date:
        filtered = [e for e in filtered if e.created_at <= end_date]
        filters_applied["end_date"] = end_date.isoformat()

    if event_type:
        filtered = [e for e in filtered if e.event_type == event_type.value]
        filters_applied["event_type"] = event_type.value

    if severity:
        filtered = [e for e in filtered if e.severity == severity.value]
        filters_applied["severity"] = severity.value

    if entity_id:
        filtered = [e for e in filtered if e.entity_id == entity_id]
        filters_applied["entity_id"] = str(entity_id)

    if user_id:
        filtered = [e for e in filtered if e.user_id == user_id]
        filters_applied["user_id"] = str(user_id)

    # Sort by created_at descending
    filtered.sort(key=lambda e: e.created_at, reverse=True)

    # Paginate
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_results = filtered[start:end]

    # Convert to summaries
    items = [_audit_event_to_summary(e) for e in page_results]

    return AuditLogResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
        filters_applied=filters_applied,
    )


# =============================================================================
# Consent Tracking Endpoint
# =============================================================================


@router.get(
    "/consent-tracking",
    response_model=ConsentTrackingResponse,
    summary="Track consent status",
    description="""
    Get consent tracking metrics and recent consent records.

    Provides:
    - Total, active, expired, and revoked consent counts
    - Consents expiring within 30 days (pending renewals)
    - Breakdown by consent scope and verification method
    - Recent consent records
    """,
    responses={
        200: {"description": "Consent tracking data"},
    },
)
async def track_consents(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    consent_manager: Annotated[ConsentManager, Depends(get_consent_manager)],
) -> ConsentTrackingResponse:
    """Get consent tracking metrics.

    Args:
        ctx: Request context with tenant info.
        consent_manager: Consent manager instance.

    Returns:
        ConsentTrackingResponse with consent metrics and recent records.
    """
    logger.debug(
        "Getting consent tracking",
        tenant_id=str(ctx.tenant_id),
    )

    # Get all consents (in-memory - production would filter by tenant)
    all_consents: list[Consent] = []
    for subject_consents in consent_manager._consents.values():
        all_consents.extend(subject_consents)

    # Calculate metrics
    now = datetime.now(UTC)
    thirty_days = now + timedelta(days=30)

    active = [c for c in all_consents if c.is_valid]
    expired = [c for c in all_consents if c.is_expired and not c.is_revoked]
    revoked = [c for c in all_consents if c.is_revoked]
    expiring_soon = [c for c in active if c.expires_at is not None and c.expires_at <= thirty_days]

    # Scope breakdown
    by_scope: dict[str, int] = {}
    for consent in active:
        for scope in consent.scopes:
            by_scope[scope.value] = by_scope.get(scope.value, 0) + 1

    # Verification method breakdown
    by_method: dict[str, int] = {}
    for consent in active:
        method = consent.verification_method.value
        by_method[method] = by_method.get(method, 0) + 1

    metrics = ConsentTrackingMetrics(
        total_consents=len(all_consents),
        active_consents=len(active),
        expired_consents=len(expired),
        revoked_consents=len(revoked),
        pending_renewals=len(expiring_soon),
        by_scope=by_scope,
        by_verification_method=by_method,
    )

    # Get recent consents (last 10)
    recent = sorted(all_consents, key=lambda c: c.granted_at, reverse=True)[:10]
    recent_summaries = [_consent_to_summary(c) for c in recent]

    # Expiring soon summaries
    expiring_summaries = [_consent_to_summary(c) for c in expiring_soon[:10]]

    return ConsentTrackingResponse(
        metrics=metrics,
        recent_consents=recent_summaries,
        expiring_soon=expiring_summaries,
        updated_at=datetime.now(UTC),
    )


# =============================================================================
# Data Erasure Endpoint
# =============================================================================


@router.post(
    "/data-erasure",
    response_model=DataErasureResponse,
    summary="Request GDPR data erasure",
    description="""
    Initiate a GDPR Article 17 "right to be forgotten" data erasure request.

    This creates a data erasure request for a subject, which will:
    - Queue deletion of personal identifiers
    - Queue deletion of screening results and findings
    - Queue deletion of cached data from external providers
    - Maintain audit logs as required for compliance

    **Note:** Some data may be retained for legal or compliance requirements
    (e.g., audit logs for 7 years under FCRA).
    """,
    responses={
        200: {"description": "Erasure request created"},
        400: {"description": "Invalid request"},
    },
)
async def request_data_erasure(
    request: DataErasureRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> DataErasureResponse:
    """Request GDPR data erasure for a subject.

    Args:
        request: The erasure request details.
        ctx: Request context with tenant info.

    Returns:
        DataErasureResponse with erasure request status.
    """
    logger.info(
        "Data erasure requested",
        tenant_id=str(ctx.tenant_id),
        subject_id=str(request.subject_id),
        reason=request.reason,
    )

    # Create erasure request
    erasure_id = uuid7()
    now = datetime.now(UTC)

    # Determine data categories (would be dynamically determined in production)
    data_categories = [
        "personal_identifiers",
        "employment_history",
        "education_records",
        "screening_results",
        "cached_provider_data",
    ]

    # Compliance exceptions (audit logs are typically retained)
    retention_exceptions = ["audit_logs", "compliance_records"]
    if not request.include_audit_records:
        retention_exceptions.append("audit_trails")

    response = DataErasureResponse(
        erasure_id=erasure_id,
        subject_id=request.subject_id,
        status=ErasureStatus.PENDING,
        requested_at=now,
        estimated_completion=now + timedelta(days=7),  # GDPR requires within 30 days
        data_categories_affected=data_categories,
        retention_exceptions=retention_exceptions,
        confirmation_token=f"ERS-{str(erasure_id)[:8].upper()}",
    )

    # Store the request
    _erasure_requests[str(erasure_id)] = response

    # Log the erasure request as an audit event
    _log_audit_event(
        event_type=AuditEventType.DATA_ERASED,
        tenant_id=ctx.tenant_id,
        user_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        entity_id=request.subject_id,
        event_data={
            "erasure_id": str(erasure_id),
            "reason": request.reason,
            "requester_email": request.requester_email,
            "include_audit_records": request.include_audit_records,
        },
    )

    return response


# =============================================================================
# Compliance Reports Endpoint
# =============================================================================


@router.get(
    "/reports",
    response_model=ComplianceReportsListResponse,
    summary="List compliance reports",
    description="""
    List compliance audit reports for review.

    **Filters:**
    - compliance_status: Filter by compliance status
    - screening_id: Filter by related screening
    - locale: Filter by locale/jurisdiction

    Results are sorted by generation date (newest first).
    """,
    responses={
        200: {"description": "List of compliance reports"},
    },
)
async def list_compliance_reports(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    compliance_status: Annotated[
        ComplianceStatus | None,
        Query(description="Filter by compliance status"),
    ] = None,
    screening_id: Annotated[
        UUID | None,
        Query(description="Filter by related screening ID"),
    ] = None,
    locale: Annotated[
        str | None,
        Query(description="Filter by locale (e.g., US, EU)"),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> ComplianceReportsListResponse:
    """List compliance reports with filters.

    Args:
        ctx: Request context with tenant info.
        compliance_status: Optional compliance status filter.
        screening_id: Optional screening ID filter.
        locale: Optional locale filter.
        page: Page number (1-indexed).
        page_size: Number of items per page.

    Returns:
        ComplianceReportsListResponse with paginated reports.
    """
    logger.debug(
        "Listing compliance reports",
        tenant_id=str(ctx.tenant_id),
        compliance_status=compliance_status.value if compliance_status else None,
        page=page,
        page_size=page_size,
    )

    # Get reports from storage
    all_reports = list(_compliance_reports.values())
    filters_applied: dict[str, str | None] = {}

    # Apply filters
    if compliance_status:
        all_reports = [r for r in all_reports if r.compliance_status == compliance_status]
        filters_applied["compliance_status"] = compliance_status.value

    if screening_id:
        all_reports = [r for r in all_reports if r.screening_id == screening_id]
        filters_applied["screening_id"] = str(screening_id)

    if locale:
        all_reports = [r for r in all_reports if r.locale.value == locale]
        filters_applied["locale"] = locale

    # Sort by generated_at descending
    all_reports.sort(key=lambda r: r.generated_at, reverse=True)

    # Paginate
    total = len(all_reports)
    start = (page - 1) * page_size
    end = start + page_size
    page_results = all_reports[start:end]

    return ComplianceReportsListResponse(
        items=page_results,
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
        filters_applied=filters_applied,
    )


# =============================================================================
# Compliance Metrics Endpoint
# =============================================================================


@router.get(
    "/metrics",
    response_model=ComplianceMetricsResponse,
    summary="Get compliance metrics",
    description="""
    Get overall compliance metrics for the organization.

    Provides:
    - Total and compliant screening counts
    - Compliance rate percentage
    - Active consent counts
    - Pending erasure requests
    - Recent violations
    - Breakdown by locale and rule type
    """,
    responses={
        200: {"description": "Compliance metrics"},
    },
)
async def get_compliance_metrics(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    consent_manager: Annotated[ConsentManager, Depends(get_consent_manager)],
) -> ComplianceMetricsResponse:
    """Get overall compliance metrics.

    Args:
        ctx: Request context with tenant info.
        consent_manager: Consent manager instance.

    Returns:
        ComplianceMetricsResponse with compliance metrics.
    """
    logger.debug(
        "Getting compliance metrics",
        tenant_id=str(ctx.tenant_id),
    )

    # Get reports for metrics
    all_reports = list(_compliance_reports.values())

    total = len(all_reports)
    compliant = sum(1 for r in all_reports if r.compliance_status == ComplianceStatus.COMPLIANT)
    partial = sum(1 for r in all_reports if r.compliance_status == ComplianceStatus.PARTIAL)
    non_compliant = sum(
        1 for r in all_reports if r.compliance_status == ComplianceStatus.NON_COMPLIANT
    )

    compliance_rate = (compliant / total * 100) if total > 0 else 100.0

    # Get active consents
    all_consents: list[Consent] = []
    for subject_consents in consent_manager._consents.values():
        all_consents.extend(subject_consents)
    active_consents = sum(1 for c in all_consents if c.is_valid)

    # Pending erasures
    pending_erasures = sum(
        1 for e in _erasure_requests.values() if e.status == ErasureStatus.PENDING
    )

    # Recent violations (last 30 days)
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    recent_violations = sum(
        1 for r in all_reports if r.violations_found > 0 and r.generated_at >= thirty_days_ago
    )

    # Breakdown by locale
    by_locale: dict[str, int] = {}
    for report in all_reports:
        locale = report.locale.value
        by_locale[locale] = by_locale.get(locale, 0) + 1

    # Get recent compliance-related audit events
    compliance_events = [
        e
        for e in _audit_events
        if e.tenant_id == ctx.tenant_id
        and e.event_type
        in [
            AuditEventType.COMPLIANCE_CHECK.value,
            AuditEventType.COMPLIANCE_VIOLATION.value,
            AuditEventType.CONSENT_GRANTED.value,
            AuditEventType.CONSENT_REVOKED.value,
        ]
    ]
    compliance_events.sort(key=lambda e: e.created_at, reverse=True)
    recent_events = [_audit_event_to_summary(e) for e in compliance_events[:10]]

    metrics = ComplianceMetrics(
        total_screenings=total,
        compliant_screenings=compliant,
        partial_compliance=partial,
        non_compliant_screenings=non_compliant,
        compliance_rate=round(compliance_rate, 1),
        active_consents=active_consents,
        pending_erasures=pending_erasures,
        recent_violations=recent_violations,
        by_locale=by_locale,
        by_rule_type={},  # Would be populated from actual rule evaluations
    )

    return ComplianceMetricsResponse(
        metrics=metrics,
        recent_audit_events=recent_events,
        updated_at=datetime.now(UTC),
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _audit_event_to_summary(event: AuditEvent) -> AuditEventSummary:
    """Convert AuditEvent to AuditEventSummary.

    Args:
        event: The audit event.

    Returns:
        AuditEventSummary for API response.
    """
    return AuditEventSummary(
        audit_id=event.audit_id,
        event_type=event.event_type,
        severity=event.severity,
        created_at=event.created_at,
        user_id=event.user_id,
        entity_id=event.entity_id,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        ip_address=event.ip_address,
        event_data=event.event_data,
    )


def _consent_to_summary(consent: Consent) -> ConsentSummary:
    """Convert Consent to ConsentSummary.

    Args:
        consent: The consent record.

    Returns:
        ConsentSummary for API response.
    """
    return ConsentSummary(
        consent_id=consent.consent_id,
        subject_id=consent.subject_id,
        scopes=consent.scopes,
        granted_at=consent.granted_at,
        expires_at=consent.expires_at,
        verification_method=consent.verification_method,
        locale=consent.locale,
        is_valid=consent.is_valid,
        is_revoked=consent.is_revoked,
        revoked_at=consent.revoked_at,
    )


def _log_audit_event(
    event_type: AuditEventType,
    tenant_id: UUID,
    user_id: UUID | None,
    correlation_id: UUID,
    entity_id: UUID | None = None,
    event_data: dict[str, str | bool | None] | None = None,
) -> None:
    """Log an audit event to the in-memory storage.

    Args:
        event_type: Type of audit event.
        tenant_id: Tenant ID.
        user_id: User ID who triggered the event.
        correlation_id: Request correlation ID.
        entity_id: Optional affected entity ID.
        event_data: Optional event details.
    """
    # Create a mock AuditEvent for in-memory storage
    # In production, this would use AuditLogger with database
    event = AuditEvent(
        audit_id=uuid7(),
        event_type=event_type.value,
        severity=AuditSeverity.INFO.value,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        entity_id=entity_id,
        event_data=event_data or {},
        created_at=datetime.now(UTC),
    )
    _audit_events.append(event)


# =============================================================================
# Storage Access Functions (for testing)
# =============================================================================


def _get_audit_events() -> list[AuditEvent]:
    """Get the audit events storage (for testing)."""
    return _audit_events


def _get_erasure_requests() -> dict[str, DataErasureResponse]:
    """Get the erasure requests storage (for testing)."""
    return _erasure_requests


def _get_compliance_reports() -> dict[str, ComplianceReportSummary]:
    """Get the compliance reports storage (for testing)."""
    return _compliance_reports


def _reset_storage() -> None:
    """Reset all storage (for testing)."""
    global _consent_manager
    _audit_events.clear()
    _erasure_requests.clear()
    _compliance_reports.clear()
    _consent_manager = None
