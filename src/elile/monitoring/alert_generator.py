"""Alert Generator for monitoring alerts.

This module provides alert generation based on profile deltas,
with vigilance-level based thresholds, notification delivery,
and escalation support.

Classes:
    NotificationChannel: Protocol for notification delivery
    NotificationResult: Result of notification delivery
    AlertStatus: Status of an alert
    AlertConfig: Configuration for alert generator
    GeneratedAlert: Extended alert with delivery tracking
    AlertGenerator: Main alert generation class
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import VigilanceLevel
from elile.core.logging import get_logger
from elile.monitoring.types import (
    AlertSeverity,
    DeltaSeverity,
    MonitoringAlert,
    MonitoringConfig,
    ProfileDelta,
)

logger = get_logger(__name__)


# =============================================================================
# Alert Thresholds (re-exported from scheduler for convenience)
# =============================================================================

# Thresholds for auto-alert by vigilance level
AUTO_ALERT_THRESHOLDS: dict[VigilanceLevel, DeltaSeverity] = {
    VigilanceLevel.V1: DeltaSeverity.CRITICAL,  # V1: Only critical auto-alerts
    VigilanceLevel.V2: DeltaSeverity.HIGH,  # V2: High and above auto-alerts
    VigilanceLevel.V3: DeltaSeverity.MEDIUM,  # V3: Medium and above auto-alerts
}

# Severity ordering for threshold comparison
DELTA_SEVERITY_ORDER = [
    DeltaSeverity.POSITIVE,
    DeltaSeverity.LOW,
    DeltaSeverity.MEDIUM,
    DeltaSeverity.HIGH,
    DeltaSeverity.CRITICAL,
]


# =============================================================================
# Enums
# =============================================================================


class AlertStatus(str, Enum):
    """Status of an alert."""

    PENDING = "pending"  # Alert created, not yet delivered
    DELIVERED = "delivered"  # Notifications sent successfully
    PARTIALLY_DELIVERED = "partially_delivered"  # Some notifications failed
    FAILED = "failed"  # All notifications failed
    ACKNOWLEDGED = "acknowledged"  # Recipient acknowledged
    RESOLVED = "resolved"  # Issue resolved
    ESCALATED = "escalated"  # Escalated to higher level


class NotificationChannelType(str, Enum):
    """Types of notification channels."""

    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    SLACK = "slack"
    TEAMS = "teams"


class EscalationTrigger(str, Enum):
    """Triggers for escalation."""

    SEVERITY = "severity"  # Critical/high severity
    TIMEOUT = "timeout"  # No acknowledgment within SLA
    MULTIPLE_ALERTS = "multiple_alerts"  # Multiple alerts in window
    MANUAL = "manual"  # Manual escalation request


# =============================================================================
# Notification Protocol
# =============================================================================


@dataclass
class NotificationResult:
    """Result of a notification delivery attempt.

    Attributes:
        channel_type: Type of notification channel
        recipient: Recipient identifier
        success: Whether delivery succeeded
        message_id: External message ID if available
        error: Error message if failed
        delivered_at: When delivery completed
        metadata: Additional delivery metadata
    """

    channel_type: NotificationChannelType
    recipient: str
    success: bool
    message_id: str | None = None
    error: str | None = None
    delivered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "channel_type": self.channel_type.value,
            "recipient": self.recipient,
            "success": self.success,
            "message_id": self.message_id,
            "error": self.error,
            "delivered_at": self.delivered_at.isoformat(),
            "metadata": self.metadata,
        }


class NotificationChannel(Protocol):
    """Protocol for notification delivery channels."""

    @property
    def channel_type(self) -> NotificationChannelType:
        """Get the channel type."""
        ...

    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        """Send a notification.

        Args:
            recipient: Recipient identifier (email, phone, webhook URL, etc.)
            subject: Notification subject/title
            body: Notification body content
            metadata: Optional additional metadata

        Returns:
            NotificationResult with delivery status
        """
        ...


# =============================================================================
# Mock Notification Channels (for testing/development)
# =============================================================================


class MockEmailChannel:
    """Mock email notification channel for testing."""

    channel_type = NotificationChannelType.EMAIL

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.sent_messages: list[dict[str, Any]] = []

    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        """Send mock email."""
        message = {
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "metadata": metadata or {},
            "sent_at": datetime.now(UTC),
        }
        self.sent_messages.append(message)

        if self.should_fail:
            return NotificationResult(
                channel_type=self.channel_type,
                recipient=recipient,
                success=False,
                error="Mock email failure",
            )

        return NotificationResult(
            channel_type=self.channel_type,
            recipient=recipient,
            success=True,
            message_id=f"mock-email-{uuid7()}",
        )


class MockWebhookChannel:
    """Mock webhook notification channel for testing."""

    channel_type = NotificationChannelType.WEBHOOK

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.sent_webhooks: list[dict[str, Any]] = []

    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        """Send mock webhook."""
        webhook = {
            "url": recipient,
            "subject": subject,
            "body": body,
            "metadata": metadata or {},
            "sent_at": datetime.now(UTC),
        }
        self.sent_webhooks.append(webhook)

        if self.should_fail:
            return NotificationResult(
                channel_type=self.channel_type,
                recipient=recipient,
                success=False,
                error="Mock webhook failure",
            )

        return NotificationResult(
            channel_type=self.channel_type,
            recipient=recipient,
            success=True,
            message_id=f"mock-webhook-{uuid7()}",
        )


class MockSMSChannel:
    """Mock SMS notification channel for testing."""

    channel_type = NotificationChannelType.SMS

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.sent_sms: list[dict[str, Any]] = []

    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        """Send mock SMS."""
        sms = {
            "phone": recipient,
            "message": f"{subject}: {body[:100]}",
            "metadata": metadata or {},
            "sent_at": datetime.now(UTC),
        }
        self.sent_sms.append(sms)

        if self.should_fail:
            return NotificationResult(
                channel_type=self.channel_type,
                recipient=recipient,
                success=False,
                error="Mock SMS failure",
            )

        return NotificationResult(
            channel_type=self.channel_type,
            recipient=recipient,
            success=True,
            message_id=f"mock-sms-{uuid7()}",
        )


# =============================================================================
# Generated Alert
# =============================================================================


@dataclass
class GeneratedAlert:
    """An alert with delivery tracking.

    Extends the base MonitoringAlert with delivery status,
    notification results, and escalation tracking.

    Attributes:
        alert: The underlying MonitoringAlert
        status: Current alert status
        notification_results: Results of notification attempts
        escalation_trigger: What triggered escalation (if any)
        escalated_at: When alert was escalated
        acknowledged_at: When alert was acknowledged
        acknowledged_by: Who acknowledged the alert
        resolved_at: When alert was resolved
        resolved_by: Who resolved the alert
        resolution_notes: Notes about resolution
        created_at: When alert was generated
        updated_at: Last update time
    """

    alert: MonitoringAlert
    status: AlertStatus = AlertStatus.PENDING
    notification_results: list[NotificationResult] = field(default_factory=list)
    escalation_trigger: EscalationTrigger | None = None
    escalated_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_notes: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def alert_id(self) -> UUID:
        """Get the alert ID."""
        return self.alert.alert_id

    @property
    def severity(self) -> AlertSeverity:
        """Get alert severity."""
        return self.alert.severity

    @property
    def is_critical(self) -> bool:
        """Check if alert is critical."""
        return self.alert.severity == AlertSeverity.CRITICAL

    @property
    def is_escalated(self) -> bool:
        """Check if alert has been escalated."""
        return self.status == AlertStatus.ESCALATED or self.alert.escalated

    @property
    def delivery_success_rate(self) -> float:
        """Calculate notification delivery success rate."""
        if not self.notification_results:
            return 0.0
        successful = sum(1 for r in self.notification_results if r.success)
        return successful / len(self.notification_results)

    def acknowledge(self, by: str) -> None:
        """Mark alert as acknowledged."""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(UTC)
        self.acknowledged_by = by
        self.updated_at = datetime.now(UTC)
        self.alert.acknowledged = True
        self.alert.acknowledged_by = by
        self.alert.acknowledged_at = self.acknowledged_at

    def resolve(self, by: str, notes: str | None = None) -> None:
        """Mark alert as resolved."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(UTC)
        self.resolved_by = by
        self.resolution_notes = notes
        self.updated_at = datetime.now(UTC)
        self.alert.resolved = True
        self.alert.resolved_by = by
        self.alert.resolved_at = self.resolved_at

    def escalate(self, trigger: EscalationTrigger) -> None:
        """Mark alert as escalated."""
        self.status = AlertStatus.ESCALATED
        self.escalation_trigger = trigger
        self.escalated_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        self.alert.escalated = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert": self.alert.to_dict(),
            "status": self.status.value,
            "notification_results": [r.to_dict() for r in self.notification_results],
            "escalation_trigger": self.escalation_trigger.value if self.escalation_trigger else None,
            "escalated_at": self.escalated_at.isoformat() if self.escalated_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "resolution_notes": self.resolution_notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "delivery_success_rate": self.delivery_success_rate,
        }


# =============================================================================
# Configuration
# =============================================================================


class AlertConfig(BaseModel):
    """Configuration for alert generator.

    Attributes:
        auto_escalate_critical: Auto-escalate critical alerts
        escalation_timeout_minutes: Minutes before timeout escalation
        max_alerts_before_escalation: Max alerts before multi-alert escalation
        alert_window_hours: Window for counting multiple alerts
        include_delta_details: Include delta details in notifications
        notification_retry_count: Number of retry attempts
        notification_retry_delay_seconds: Delay between retries
    """

    auto_escalate_critical: bool = True
    escalation_timeout_minutes: int = Field(default=30, ge=1, le=1440)
    max_alerts_before_escalation: int = Field(default=3, ge=1, le=20)
    alert_window_hours: int = Field(default=24, ge=1, le=168)
    include_delta_details: bool = True
    notification_retry_count: int = Field(default=3, ge=0, le=10)
    notification_retry_delay_seconds: int = Field(default=60, ge=10, le=3600)


# =============================================================================
# Alert Generator
# =============================================================================


class AlertGenerator:
    """Generates and delivers monitoring alerts.

    Evaluates profile deltas against vigilance-level thresholds,
    generates alerts, delivers notifications via multiple channels,
    and handles escalation.

    Attributes:
        config: Alert generator configuration
        channels: Notification channels by type
    """

    def __init__(
        self,
        config: AlertConfig | None = None,
        channels: dict[NotificationChannelType, NotificationChannel] | None = None,
    ) -> None:
        """Initialize the alert generator.

        Args:
            config: Optional configuration
            channels: Optional notification channels
        """
        self.config = config or AlertConfig()
        self.channels: dict[NotificationChannelType, NotificationChannel] = channels or {}
        self._alert_history: list[GeneratedAlert] = []

    def add_channel(self, channel: NotificationChannel) -> None:
        """Add a notification channel.

        Args:
            channel: Notification channel to add
        """
        self.channels[channel.channel_type] = channel

    def remove_channel(self, channel_type: NotificationChannelType) -> None:
        """Remove a notification channel.

        Args:
            channel_type: Type of channel to remove
        """
        self.channels.pop(channel_type, None)

    async def generate_alerts(
        self,
        deltas: list[ProfileDelta],
        monitoring_config: MonitoringConfig,
        check_id: UUID | None = None,
    ) -> list[GeneratedAlert]:
        """Generate alerts from profile deltas.

        Evaluates deltas against vigilance-level thresholds and generates
        alerts for those that meet the threshold.

        Args:
            deltas: Profile deltas to evaluate
            monitoring_config: Monitoring configuration with vigilance level
            check_id: Optional check ID for tracking

        Returns:
            List of generated alerts
        """
        vigilance_level = monitoring_config.vigilance_level
        threshold = AUTO_ALERT_THRESHOLDS.get(vigilance_level, DeltaSeverity.CRITICAL)

        # Filter deltas that meet threshold
        alertable_deltas = [d for d in deltas if self._meets_threshold(d.severity, threshold)]

        if not alertable_deltas:
            logger.debug(
                "No deltas meet alert threshold",
                vigilance_level=vigilance_level.value,
                threshold=threshold.value,
                total_deltas=len(deltas),
            )
            return []

        # Group deltas by severity for alert generation
        alerts = await self._create_alerts(
            alertable_deltas, monitoring_config, check_id
        )

        # Check for escalation conditions
        for alert in alerts:
            self._check_escalation(alert, monitoring_config)

        # Deliver notifications
        for alert in alerts:
            await self._deliver_notifications(alert, monitoring_config)

        # Track in history
        self._alert_history.extend(alerts)

        logger.info(
            "Generated alerts",
            count=len(alerts),
            vigilance_level=vigilance_level.value,
            config_id=str(monitoring_config.config_id),
        )

        return alerts

    async def evaluate_single_delta(
        self,
        delta: ProfileDelta,
        vigilance_level: VigilanceLevel,
        recipients: list[str],
        escalation_path: list[str] | None = None,
    ) -> GeneratedAlert | None:
        """Evaluate a single delta and generate alert if needed.

        Convenience method for evaluating one delta without full config.

        Args:
            delta: Profile delta to evaluate
            vigilance_level: Vigilance level for threshold
            recipients: Alert recipients
            escalation_path: Optional escalation recipients

        Returns:
            Generated alert if delta meets threshold, None otherwise
        """
        threshold = AUTO_ALERT_THRESHOLDS.get(vigilance_level, DeltaSeverity.CRITICAL)

        if not self._meets_threshold(delta.severity, threshold):
            return None

        # Create basic monitoring alert
        alert_severity = self._map_delta_to_alert_severity(delta.severity)
        monitoring_alert = MonitoringAlert(
            severity=alert_severity,
            title=self._generate_title(delta),
            description=self._generate_description(delta),
            delta_ids=[delta.delta_id],
            recipients_notified=list(recipients),
        )

        generated = GeneratedAlert(alert=monitoring_alert)

        # Check for critical escalation
        if self.config.auto_escalate_critical and alert_severity == AlertSeverity.CRITICAL:
            generated.escalate(EscalationTrigger.SEVERITY)
            if escalation_path:
                monitoring_alert.escalated_to = list(escalation_path)

        # Deliver notifications
        await self._deliver_to_recipients(generated, recipients)

        self._alert_history.append(generated)

        return generated

    def _meets_threshold(self, severity: DeltaSeverity, threshold: DeltaSeverity) -> bool:
        """Check if severity meets the alert threshold.

        Args:
            severity: Delta severity to check
            threshold: Minimum severity threshold

        Returns:
            True if severity meets or exceeds threshold
        """
        # Positive changes don't trigger alerts
        if severity == DeltaSeverity.POSITIVE:
            return False

        return DELTA_SEVERITY_ORDER.index(severity) >= DELTA_SEVERITY_ORDER.index(threshold)

    def _map_delta_to_alert_severity(self, delta_severity: DeltaSeverity) -> AlertSeverity:
        """Map delta severity to alert severity.

        Args:
            delta_severity: Delta severity

        Returns:
            Corresponding alert severity
        """
        mapping = {
            DeltaSeverity.CRITICAL: AlertSeverity.CRITICAL,
            DeltaSeverity.HIGH: AlertSeverity.HIGH,
            DeltaSeverity.MEDIUM: AlertSeverity.MEDIUM,
            DeltaSeverity.LOW: AlertSeverity.LOW,
            DeltaSeverity.POSITIVE: AlertSeverity.LOW,
        }
        return mapping.get(delta_severity, AlertSeverity.LOW)

    async def _create_alerts(
        self,
        deltas: list[ProfileDelta],
        config: MonitoringConfig,
        check_id: UUID | None,
    ) -> list[GeneratedAlert]:
        """Create alerts from deltas.

        Groups related deltas into alerts based on severity.

        Args:
            deltas: Deltas to create alerts from
            config: Monitoring configuration
            check_id: Optional check ID

        Returns:
            List of generated alerts
        """
        alerts: list[GeneratedAlert] = []

        # Group deltas by severity
        by_severity: dict[DeltaSeverity, list[ProfileDelta]] = {}
        for delta in deltas:
            by_severity.setdefault(delta.severity, []).append(delta)

        # Create one alert per severity level with multiple deltas
        for severity, severity_deltas in by_severity.items():
            alert_severity = self._map_delta_to_alert_severity(severity)

            # Build title and description
            if len(severity_deltas) == 1:
                title = self._generate_title(severity_deltas[0])
                description = self._generate_description(severity_deltas[0])
            else:
                title = f"{len(severity_deltas)} {severity.value} changes detected"
                description = self._generate_multi_description(severity_deltas)

            monitoring_alert = MonitoringAlert(
                monitoring_config_id=config.config_id,
                check_id=check_id or uuid7(),
                severity=alert_severity,
                title=title,
                description=description,
                delta_ids=[d.delta_id for d in severity_deltas],
                recipients_notified=list(config.alert_recipients),
            )

            generated = GeneratedAlert(alert=monitoring_alert)
            alerts.append(generated)

        return alerts

    def _check_escalation(
        self,
        alert: GeneratedAlert,
        config: MonitoringConfig,
    ) -> None:
        """Check if alert should be escalated.

        Args:
            alert: Alert to check
            config: Monitoring configuration
        """
        # Auto-escalate critical
        if self.config.auto_escalate_critical and alert.is_critical:
            alert.escalate(EscalationTrigger.SEVERITY)
            alert.alert.escalated_to = list(config.escalation_path)
            return

        # Check for multiple alerts in window
        window_start = datetime.now(UTC) - timedelta(hours=self.config.alert_window_hours)
        recent_alerts = [
            a for a in self._alert_history
            if a.created_at >= window_start
            and a.alert.monitoring_config_id == config.config_id
        ]

        if len(recent_alerts) >= self.config.max_alerts_before_escalation:
            alert.escalate(EscalationTrigger.MULTIPLE_ALERTS)
            alert.alert.escalated_to = list(config.escalation_path)

    async def _deliver_notifications(
        self,
        alert: GeneratedAlert,
        config: MonitoringConfig,
    ) -> None:
        """Deliver notifications for an alert.

        Args:
            alert: Alert to deliver
            config: Monitoring configuration
        """
        recipients = list(config.alert_recipients)
        if alert.is_escalated:
            recipients.extend(config.escalation_path)

        await self._deliver_to_recipients(alert, recipients)

    async def _deliver_to_recipients(
        self,
        alert: GeneratedAlert,
        recipients: list[str],
    ) -> None:
        """Deliver notifications to recipients.

        Args:
            alert: Alert to deliver
            recipients: List of recipients
        """
        if not self.channels:
            logger.warning("No notification channels configured")
            alert.status = AlertStatus.PENDING
            return

        subject = f"[{alert.severity.value.upper()}] {alert.alert.title}"
        body = self._format_notification_body(alert)

        results: list[NotificationResult] = []

        for recipient in recipients:
            # Determine channel based on recipient format
            channel = self._get_channel_for_recipient(recipient)
            if not channel:
                logger.warning("No channel for recipient", recipient=recipient)
                continue

            # Send with retries
            result = await self._send_with_retry(channel, recipient, subject, body)
            results.append(result)

        alert.notification_results = results

        # Update status based on results
        if not results:
            alert.status = AlertStatus.PENDING
        elif all(r.success for r in results):
            alert.status = AlertStatus.DELIVERED
        elif any(r.success for r in results):
            alert.status = AlertStatus.PARTIALLY_DELIVERED
        else:
            alert.status = AlertStatus.FAILED

    def _get_channel_for_recipient(self, recipient: str) -> NotificationChannel | None:
        """Determine the appropriate channel for a recipient.

        Args:
            recipient: Recipient identifier

        Returns:
            Notification channel or None
        """
        # Simple heuristics for channel selection
        if "@" in recipient:
            return self.channels.get(NotificationChannelType.EMAIL)
        elif recipient.startswith("http"):
            return self.channels.get(NotificationChannelType.WEBHOOK)
        elif recipient.startswith("+") or recipient.isdigit():
            return self.channels.get(NotificationChannelType.SMS)

        # Default to email if available
        return self.channels.get(NotificationChannelType.EMAIL)

    async def _send_with_retry(
        self,
        channel: NotificationChannel,
        recipient: str,
        subject: str,
        body: str,
    ) -> NotificationResult:
        """Send notification with retry logic.

        Args:
            channel: Notification channel
            recipient: Recipient
            subject: Subject
            body: Body

        Returns:
            Final notification result
        """
        last_result: NotificationResult | None = None

        for attempt in range(self.config.notification_retry_count + 1):
            result = await channel.send(recipient, subject, body)
            last_result = result

            if result.success:
                return result

            if attempt < self.config.notification_retry_count:
                # In production, would use asyncio.sleep
                logger.debug(
                    "Notification failed, will retry",
                    attempt=attempt + 1,
                    recipient=recipient,
                    error=result.error,
                )

        return last_result or NotificationResult(
            channel_type=channel.channel_type,
            recipient=recipient,
            success=False,
            error="Max retries exceeded",
        )

    def _generate_title(self, delta: ProfileDelta) -> str:
        """Generate alert title from delta.

        Args:
            delta: Profile delta

        Returns:
            Alert title
        """
        severity = delta.severity.value.upper()
        category = delta.category or "Unknown"
        delta_type = delta.delta_type.replace("_", " ").title()
        return f"[{severity}] {delta_type} - {category}"

    def _generate_description(self, delta: ProfileDelta) -> str:
        """Generate alert description from delta.

        Args:
            delta: Profile delta

        Returns:
            Alert description
        """
        lines = [delta.description]

        if self.config.include_delta_details:
            if delta.previous_value:
                lines.append(f"Previous: {delta.previous_value}")
            if delta.current_value:
                lines.append(f"Current: {delta.current_value}")
            if delta.source_provider:
                lines.append(f"Source: {delta.source_provider}")

        if delta.requires_review:
            lines.append("\n[REQUIRES REVIEW]")

        return "\n".join(lines)

    def _generate_multi_description(self, deltas: list[ProfileDelta]) -> str:
        """Generate description for multiple deltas.

        Args:
            deltas: List of deltas

        Returns:
            Combined description
        """
        lines = [f"Multiple changes detected ({len(deltas)} total):", ""]

        for i, delta in enumerate(deltas[:5], 1):  # Limit to first 5
            lines.append(f"{i}. [{delta.category or 'unknown'}] {delta.description}")

        if len(deltas) > 5:
            lines.append(f"\n... and {len(deltas) - 5} more")

        return "\n".join(lines)

    def _format_notification_body(self, alert: GeneratedAlert) -> str:
        """Format the notification body.

        Args:
            alert: Generated alert

        Returns:
            Formatted notification body
        """
        lines = [
            f"Severity: {alert.severity.value.upper()}",
            f"Status: {alert.status.value}",
            "",
            alert.alert.description,
            "",
            f"Alert ID: {alert.alert_id}",
            f"Generated: {alert.created_at.isoformat()}",
        ]

        if alert.is_escalated:
            lines.insert(0, "*** ESCALATED ***")
            if alert.escalation_trigger:
                lines.insert(1, f"Escalation reason: {alert.escalation_trigger.value}")

        return "\n".join(lines)

    def get_alert_history(
        self,
        config_id: UUID | None = None,
        limit: int = 100,
    ) -> list[GeneratedAlert]:
        """Get alert history.

        Args:
            config_id: Optional filter by config ID
            limit: Maximum alerts to return

        Returns:
            List of generated alerts
        """
        alerts = self._alert_history
        if config_id:
            alerts = [a for a in alerts if a.alert.monitoring_config_id == config_id]

        # Sort by created_at descending
        alerts = sorted(alerts, key=lambda a: a.created_at, reverse=True)
        return alerts[:limit]

    def get_pending_alerts(self) -> list[GeneratedAlert]:
        """Get alerts pending acknowledgment.

        Returns:
            List of pending alerts
        """
        return [a for a in self._alert_history if a.status == AlertStatus.PENDING]

    def get_unresolved_alerts(self) -> list[GeneratedAlert]:
        """Get unresolved alerts.

        Returns:
            List of unresolved alerts (not resolved or acknowledged)
        """
        resolved_statuses = {AlertStatus.RESOLVED, AlertStatus.ACKNOWLEDGED}
        return [a for a in self._alert_history if a.status not in resolved_statuses]

    def clear_history(self) -> int:
        """Clear alert history.

        Returns:
            Number of alerts cleared
        """
        count = len(self._alert_history)
        self._alert_history.clear()
        return count


# =============================================================================
# Factory Function
# =============================================================================


def create_alert_generator(
    config: AlertConfig | None = None,
    include_mock_channels: bool = False,
) -> AlertGenerator:
    """Create an alert generator.

    Args:
        config: Optional configuration
        include_mock_channels: Add mock channels for testing

    Returns:
        Configured AlertGenerator instance
    """
    generator = AlertGenerator(config=config)

    if include_mock_channels:
        generator.add_channel(MockEmailChannel())
        generator.add_channel(MockWebhookChannel())
        generator.add_channel(MockSMSChannel())

    return generator
