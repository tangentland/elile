"""HRIS Result Publisher for sending screening results and alerts to HRIS platforms.

This module provides the HRISResultPublisher class for publishing:
- Screening completion notifications
- Screening progress updates
- Monitoring alerts
- Adverse action pending notifications (FCRA compliance)
- Review required notifications

All publishing uses the HRISGateway for delivery with retry logic.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

import structlog
from pydantic import BaseModel, Field

from elile.hris.gateway import (
    AlertUpdate,
    HRISGateway,
    ScreeningUpdate,
)
from elile.monitoring.types import MonitoringAlert
from elile.screening.types import ScreeningResult, ScreeningStatus

logger = structlog.get_logger()


# =============================================================================
# Enums and Types
# =============================================================================


class PublishStatus(str, Enum):
    """Status of a publish operation."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED = "skipped"


class PublishEventType(str, Enum):
    """Types of events that can be published to HRIS."""

    SCREENING_STARTED = "screening.started"
    SCREENING_PROGRESS = "screening.progress"
    SCREENING_COMPLETE = "screening.complete"
    REVIEW_REQUIRED = "review.required"
    ALERT_GENERATED = "alert.generated"
    ADVERSE_ACTION_PENDING = "adverse_action.pending"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class PublishResult:
    """Result of a publish operation.

    Tracks the outcome, delivery attempts, and any error information.
    """

    result_id: UUID = field(default_factory=uuid7)
    event_type: PublishEventType = PublishEventType.SCREENING_COMPLETE
    status: PublishStatus = PublishStatus.PENDING

    # Identifiers
    screening_id: UUID | None = None
    alert_id: UUID | None = None
    tenant_id: UUID | None = None
    employee_id: str = ""

    # Delivery tracking
    attempts: int = 0
    delivered_at: datetime | None = None
    error_message: str | None = None

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_attempt_at: datetime | None = None

    # Additional context
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "event_type": self.event_type.value,
            "status": self.status.value,
            "screening_id": str(self.screening_id) if self.screening_id else None,
            "alert_id": str(self.alert_id) if self.alert_id else None,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "employee_id": self.employee_id,
            "attempts": self.attempts,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            "metadata": self.metadata,
        }

    @property
    def is_delivered(self) -> bool:
        """Check if the event was delivered."""
        return self.status == PublishStatus.DELIVERED

    @property
    def is_failed(self) -> bool:
        """Check if delivery failed."""
        return self.status == PublishStatus.FAILED


@dataclass
class DeliveryRecord:
    """Record of a delivery attempt for audit purposes."""

    record_id: UUID = field(default_factory=uuid7)
    publish_result_id: UUID = field(default_factory=uuid7)
    event_type: PublishEventType = PublishEventType.SCREENING_COMPLETE

    # Target information
    tenant_id: UUID = field(default_factory=uuid7)
    employee_id: str = ""

    # Delivery info
    attempt_number: int = 1
    attempted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    success: bool = False
    error_message: str | None = None

    # Response data
    response_code: int | None = None
    response_time_ms: int | None = None


# =============================================================================
# Configuration
# =============================================================================


class PublisherConfig(BaseModel):
    """Configuration for the HRISResultPublisher."""

    # Feature flags
    publish_progress_updates: bool = Field(
        default=True,
        description="Whether to publish progress updates during screening",
    )
    publish_review_required: bool = Field(
        default=True,
        description="Whether to publish review required notifications",
    )

    # Progress update frequency
    progress_update_interval_percent: int = Field(
        default=25,
        ge=10,
        le=50,
        description="Publish progress every N percent complete",
    )

    # Mapping
    include_findings_summary: bool = Field(
        default=False,
        description="Include findings summary in screening complete (may have PII)",
    )
    include_risk_details: bool = Field(
        default=True,
        description="Include risk level and recommendation in updates",
    )

    # Credentials (reference to secure storage)
    default_credentials_ref: str | None = Field(
        default=None,
        description="Default credentials reference if not specified per-tenant",
    )


# =============================================================================
# HRIS Result Publisher
# =============================================================================


class HRISResultPublisher:
    """Publishes screening results and alerts to HRIS platforms.

    The publisher handles:
    - Screening completion notifications with risk assessment
    - Screening progress updates during processing
    - Monitoring alerts from vigilance checks
    - Adverse action pending notifications for FCRA compliance
    - Review required notifications when manual review is needed

    Example:
        publisher = HRISResultPublisher(gateway=gateway)

        # Publish screening completion
        result = await publisher.publish_screening_complete(
            screening_id=screening_id,
            employee_id="EMP-001",
            tenant_id=tenant_id,
            result=screening_result,
        )

        if result.is_delivered:
            print("HRIS notified successfully")

        # Publish monitoring alert
        result = await publisher.publish_alert(
            alert=alert,
            employee_id="EMP-001",
            tenant_id=tenant_id,
        )
    """

    def __init__(
        self,
        gateway: HRISGateway,
        config: PublisherConfig | None = None,
        credentials_store: dict[UUID, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the result publisher.

        Args:
            gateway: HRIS gateway for publishing events.
            config: Publisher configuration.
            credentials_store: Optional mapping of tenant_id to credentials.
        """
        self._gateway = gateway
        self.config = config or PublisherConfig()
        self._credentials_store = credentials_store or {}
        self._delivery_history: list[DeliveryRecord] = []
        self._published_count: dict[PublishEventType, int] = {}

    def _get_credentials(self, tenant_id: UUID) -> dict[str, Any]:
        """Get credentials for a tenant.

        Args:
            tenant_id: Tenant ID to get credentials for.

        Returns:
            Credentials dictionary (may be empty for mock adapter).
        """
        return self._credentials_store.get(tenant_id, {})

    async def publish_screening_started(
        self,
        screening_id: UUID,
        employee_id: str,
        tenant_id: UUID,
        estimated_completion: datetime | None = None,
    ) -> PublishResult:
        """Publish screening started notification.

        Args:
            screening_id: ID of the screening.
            employee_id: HRIS employee identifier.
            tenant_id: Tenant ID.
            estimated_completion: Optional estimated completion time.

        Returns:
            PublishResult with delivery status.
        """
        result = PublishResult(
            event_type=PublishEventType.SCREENING_STARTED,
            screening_id=screening_id,
            tenant_id=tenant_id,
            employee_id=employee_id,
        )

        update = ScreeningUpdate(
            screening_id=screening_id,
            status="started",
            timestamp=datetime.now(UTC),
            progress_percent=0,
            estimated_completion=estimated_completion,
        )

        return await self._publish_update(result, update, employee_id, tenant_id)

    async def publish_screening_progress(
        self,
        screening_id: UUID,
        employee_id: str,
        tenant_id: UUID,
        progress_percent: int,
        status: str = "in_progress",
        estimated_completion: datetime | None = None,
    ) -> PublishResult:
        """Publish screening progress update.

        Args:
            screening_id: ID of the screening.
            employee_id: HRIS employee identifier.
            tenant_id: Tenant ID.
            progress_percent: Progress percentage (0-100).
            status: Current status string.
            estimated_completion: Optional updated completion estimate.

        Returns:
            PublishResult with delivery status.
        """
        if not self.config.publish_progress_updates:
            return PublishResult(
                event_type=PublishEventType.SCREENING_PROGRESS,
                screening_id=screening_id,
                tenant_id=tenant_id,
                employee_id=employee_id,
                status=PublishStatus.SKIPPED,
                metadata={"reason": "progress_updates_disabled"},
            )

        result = PublishResult(
            event_type=PublishEventType.SCREENING_PROGRESS,
            screening_id=screening_id,
            tenant_id=tenant_id,
            employee_id=employee_id,
        )

        update = ScreeningUpdate(
            screening_id=screening_id,
            status=status,
            timestamp=datetime.now(UTC),
            progress_percent=progress_percent,
            estimated_completion=estimated_completion,
        )

        return await self._publish_update(result, update, employee_id, tenant_id)

    async def publish_screening_complete(
        self,
        screening_id: UUID,
        employee_id: str,
        tenant_id: UUID,
        result: ScreeningResult,
    ) -> PublishResult:
        """Publish screening completion notification.

        This is the primary method for notifying HRIS that a screening
        has completed, including the risk assessment results.

        Args:
            screening_id: ID of the screening.
            employee_id: HRIS employee identifier.
            tenant_id: Tenant ID.
            result: Complete screening result with risk assessment.

        Returns:
            PublishResult with delivery status.
        """
        publish_result = PublishResult(
            event_type=PublishEventType.SCREENING_COMPLETE,
            screening_id=screening_id,
            tenant_id=tenant_id,
            employee_id=employee_id,
        )

        # Build findings summary if configured
        findings_summary = None
        if self.config.include_findings_summary and result.phases:
            findings_summary = {
                "phases_completed": len(result.phases),
                "total_findings": len(result.phases),  # Simplified
            }

        # Build screening update
        update = ScreeningUpdate(
            screening_id=screening_id,
            status=(
                result.status.value if isinstance(result.status, ScreeningStatus) else "complete"
            ),
            timestamp=datetime.now(UTC),
            progress_percent=100,
            risk_level=result.risk_level if self.config.include_risk_details else None,
            recommendation=result.recommendation if self.config.include_risk_details else None,
            findings_summary=findings_summary,
        )

        logger.info(
            "Publishing screening complete",
            screening_id=str(screening_id),
            tenant_id=str(tenant_id),
            employee_id=employee_id,
            risk_level=result.risk_level,
            recommendation=result.recommendation,
        )

        return await self._publish_update(publish_result, update, employee_id, tenant_id)

    async def publish_review_required(
        self,
        screening_id: UUID,
        employee_id: str,
        tenant_id: UUID,
        reason: str,
        risk_level: str | None = None,
    ) -> PublishResult:
        """Publish review required notification.

        Notifies HRIS that manual review is required before proceeding.

        Args:
            screening_id: ID of the screening.
            employee_id: HRIS employee identifier.
            tenant_id: Tenant ID.
            reason: Reason review is required.
            risk_level: Current risk level if available.

        Returns:
            PublishResult with delivery status.
        """
        if not self.config.publish_review_required:
            return PublishResult(
                event_type=PublishEventType.REVIEW_REQUIRED,
                screening_id=screening_id,
                tenant_id=tenant_id,
                employee_id=employee_id,
                status=PublishStatus.SKIPPED,
                metadata={"reason": "review_required_disabled"},
            )

        publish_result = PublishResult(
            event_type=PublishEventType.REVIEW_REQUIRED,
            screening_id=screening_id,
            tenant_id=tenant_id,
            employee_id=employee_id,
        )

        update = ScreeningUpdate(
            screening_id=screening_id,
            status="review_required",
            timestamp=datetime.now(UTC),
            risk_level=risk_level,
            review_reason=reason,
        )

        return await self._publish_update(publish_result, update, employee_id, tenant_id)

    async def publish_adverse_action_pending(
        self,
        screening_id: UUID,
        employee_id: str,
        tenant_id: UUID,
        reason: str,
        pre_adverse_notice_sent: bool = False,
    ) -> PublishResult:
        """Publish adverse action pending notification.

        Used for FCRA compliance to notify HRIS that adverse action
        may be taken based on screening results.

        Args:
            screening_id: ID of the screening.
            employee_id: HRIS employee identifier.
            tenant_id: Tenant ID.
            reason: Reason for potential adverse action.
            pre_adverse_notice_sent: Whether pre-adverse notice was sent.

        Returns:
            PublishResult with delivery status.
        """
        publish_result = PublishResult(
            event_type=PublishEventType.ADVERSE_ACTION_PENDING,
            screening_id=screening_id,
            tenant_id=tenant_id,
            employee_id=employee_id,
        )

        update = ScreeningUpdate(
            screening_id=screening_id,
            status="adverse_action_pending",
            timestamp=datetime.now(UTC),
            review_reason=reason,
            findings_summary={
                "adverse_action_pending": True,
                "pre_adverse_notice_sent": pre_adverse_notice_sent,
            },
        )

        logger.info(
            "Publishing adverse action pending",
            screening_id=str(screening_id),
            tenant_id=str(tenant_id),
            employee_id=employee_id,
            reason=reason,
        )

        return await self._publish_update(publish_result, update, employee_id, tenant_id)

    async def publish_alert(
        self,
        alert: MonitoringAlert,
        employee_id: str,
        tenant_id: UUID,
    ) -> PublishResult:
        """Publish monitoring alert to HRIS.

        Args:
            alert: Monitoring alert to publish.
            employee_id: HRIS employee identifier.
            tenant_id: Tenant ID.

        Returns:
            PublishResult with delivery status.
        """
        publish_result = PublishResult(
            event_type=PublishEventType.ALERT_GENERATED,
            alert_id=alert.alert_id,
            tenant_id=tenant_id,
            employee_id=employee_id,
        )

        # Convert MonitoringAlert to AlertUpdate
        # MonitoringAlert may not have requires_action/action_url, use defaults
        requires_action = getattr(
            alert,
            "requires_action",
            alert.severity
            in {
                "critical",
                "high",
                alert.severity.__class__.CRITICAL if hasattr(alert.severity, "CRITICAL") else None,
                alert.severity.__class__.HIGH if hasattr(alert.severity, "HIGH") else None,
            },
        )
        # Simplify: requires_action if severity is critical or high
        if isinstance(alert.severity, Enum):
            requires_action = alert.severity.value in ("critical", "high")
        else:
            requires_action = alert.severity in ("critical", "high")

        alert_update = AlertUpdate(
            alert_id=alert.alert_id,
            employee_id=employee_id,
            severity=alert.severity.value if isinstance(alert.severity, Enum) else alert.severity,
            title=alert.title,
            description=alert.description,
            created_at=alert.created_at,
            requires_action=requires_action,
            action_url=getattr(alert, "action_url", None),
        )

        return await self._publish_alert(publish_result, alert_update, employee_id, tenant_id)

    async def _publish_update(
        self,
        publish_result: PublishResult,
        update: ScreeningUpdate,
        employee_id: str,
        tenant_id: UUID,
    ) -> PublishResult:
        """Internal method to publish a screening update.

        Args:
            publish_result: The result object to populate.
            update: Screening update to publish.
            employee_id: HRIS employee identifier.
            tenant_id: Tenant ID.

        Returns:
            Updated PublishResult.
        """
        credentials = self._get_credentials(tenant_id)
        publish_result.last_attempt_at = datetime.now(UTC)
        publish_result.attempts += 1

        # Create delivery record
        delivery_record = DeliveryRecord(
            publish_result_id=publish_result.result_id,
            event_type=publish_result.event_type,
            tenant_id=tenant_id,
            employee_id=employee_id,
            attempt_number=publish_result.attempts,
        )

        try:
            success = await self._gateway.publish_screening_update(
                tenant_id=tenant_id,
                employee_id=employee_id,
                update=update,
                credentials=credentials,
            )

            delivery_record.success = success
            if success:
                publish_result.status = PublishStatus.DELIVERED
                publish_result.delivered_at = datetime.now(UTC)

                logger.info(
                    "AUDIT: hris_update_published",
                    audit_event_type="hris.update_published",
                    event_type=publish_result.event_type.value,
                    screening_id=str(update.screening_id),
                    tenant_id=str(tenant_id),
                    employee_id=employee_id,
                    status=update.status,
                )
            else:
                publish_result.status = PublishStatus.FAILED
                publish_result.error_message = "Gateway returned failure"
                delivery_record.error_message = "Gateway returned failure"

        except Exception as e:
            publish_result.status = PublishStatus.FAILED
            publish_result.error_message = str(e)
            delivery_record.success = False
            delivery_record.error_message = str(e)

            logger.error(
                "Failed to publish HRIS update",
                event_type=publish_result.event_type.value,
                tenant_id=str(tenant_id),
                employee_id=employee_id,
                error=str(e),
            )

        # Record delivery attempt
        self._delivery_history.append(delivery_record)

        # Update statistics
        self._published_count[publish_result.event_type] = (
            self._published_count.get(publish_result.event_type, 0) + 1
        )

        return publish_result

    async def _publish_alert(
        self,
        publish_result: PublishResult,
        alert_update: AlertUpdate,
        employee_id: str,
        tenant_id: UUID,
    ) -> PublishResult:
        """Internal method to publish an alert.

        Args:
            publish_result: The result object to populate.
            alert_update: Alert update to publish.
            employee_id: HRIS employee identifier.
            tenant_id: Tenant ID.

        Returns:
            Updated PublishResult.
        """
        credentials = self._get_credentials(tenant_id)
        publish_result.last_attempt_at = datetime.now(UTC)
        publish_result.attempts += 1

        # Create delivery record
        delivery_record = DeliveryRecord(
            publish_result_id=publish_result.result_id,
            event_type=publish_result.event_type,
            tenant_id=tenant_id,
            employee_id=employee_id,
            attempt_number=publish_result.attempts,
        )

        try:
            success = await self._gateway.publish_alert(
                tenant_id=tenant_id,
                employee_id=employee_id,
                alert=alert_update,
                credentials=credentials,
            )

            delivery_record.success = success
            if success:
                publish_result.status = PublishStatus.DELIVERED
                publish_result.delivered_at = datetime.now(UTC)

                logger.info(
                    "AUDIT: hris_alert_published",
                    audit_event_type="hris.alert_published",
                    alert_id=str(alert_update.alert_id),
                    tenant_id=str(tenant_id),
                    employee_id=employee_id,
                    severity=alert_update.severity,
                )
            else:
                publish_result.status = PublishStatus.FAILED
                publish_result.error_message = "Gateway returned failure"
                delivery_record.error_message = "Gateway returned failure"

        except Exception as e:
            publish_result.status = PublishStatus.FAILED
            publish_result.error_message = str(e)
            delivery_record.success = False
            delivery_record.error_message = str(e)

            logger.error(
                "Failed to publish HRIS alert",
                alert_id=str(alert_update.alert_id),
                tenant_id=str(tenant_id),
                employee_id=employee_id,
                error=str(e),
            )

        # Record delivery attempt
        self._delivery_history.append(delivery_record)

        # Update statistics
        self._published_count[publish_result.event_type] = (
            self._published_count.get(publish_result.event_type, 0) + 1
        )

        return publish_result

    def get_delivery_history(
        self,
        tenant_id: UUID | None = None,
        event_type: PublishEventType | None = None,
        limit: int = 100,
    ) -> list[DeliveryRecord]:
        """Get delivery history with optional filters.

        Args:
            tenant_id: Filter by tenant ID.
            event_type: Filter by event type.
            limit: Maximum records to return.

        Returns:
            List of delivery records matching filters.
        """
        records = self._delivery_history

        if tenant_id is not None:
            records = [r for r in records if r.tenant_id == tenant_id]

        if event_type is not None:
            records = [r for r in records if r.event_type == event_type]

        # Return most recent first
        return list(reversed(records[-limit:]))

    def get_statistics(self) -> dict[str, Any]:
        """Get publishing statistics.

        Returns:
            Dictionary with publishing counts by event type and delivery success rates.
        """
        total_deliveries = len(self._delivery_history)
        successful_deliveries = sum(1 for r in self._delivery_history if r.success)

        return {
            "events_published": dict(self._published_count),
            "total_deliveries": total_deliveries,
            "successful_deliveries": successful_deliveries,
            "failed_deliveries": total_deliveries - successful_deliveries,
            "success_rate": successful_deliveries / total_deliveries if total_deliveries > 0 else 0,
        }

    def clear_history(self) -> None:
        """Clear delivery history (for testing/maintenance)."""
        self._delivery_history.clear()


# =============================================================================
# Factory Function
# =============================================================================


def create_result_publisher(
    gateway: HRISGateway,
    config: PublisherConfig | None = None,
    credentials_store: dict[UUID, dict[str, Any]] | None = None,
) -> HRISResultPublisher:
    """Create an HRIS result publisher.

    Args:
        gateway: HRIS gateway for publishing events.
        config: Optional publisher configuration.
        credentials_store: Optional mapping of tenant_id to credentials.

    Returns:
        Configured HRISResultPublisher instance.
    """
    return HRISResultPublisher(
        gateway=gateway,
        config=config,
        credentials_store=credentials_store,
    )
