"""Unit tests for the Alert Generator.

Tests cover:
- Alert generation from deltas
- Vigilance-level thresholds
- Notification delivery
- Escalation logic
- Alert status tracking
- Alert history management
"""

from uuid import uuid7

import pytest

from elile.agent.state import VigilanceLevel
from elile.monitoring.alert_generator import (
    AUTO_ALERT_THRESHOLDS,
    AlertConfig,
    AlertGenerator,
    AlertStatus,
    EscalationTrigger,
    GeneratedAlert,
    MockEmailChannel,
    MockSMSChannel,
    MockWebhookChannel,
    NotificationChannelType,
    NotificationResult,
    create_alert_generator,
)
from elile.monitoring.types import (
    AlertSeverity,
    DeltaSeverity,
    MonitoringAlert,
    MonitoringConfig,
    ProfileDelta,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def generator() -> AlertGenerator:
    """Create alert generator with mock channels."""
    return create_alert_generator(include_mock_channels=True)


@pytest.fixture
def monitoring_config() -> MonitoringConfig:
    """Create a monitoring configuration."""
    return MonitoringConfig(
        subject_id=uuid7(),
        tenant_id=uuid7(),
        vigilance_level=VigilanceLevel.V2,
        baseline_profile_id=uuid7(),
        alert_recipients=["security@example.com", "hr@example.com"],
        escalation_path=["ciso@example.com"],
    )


def make_delta(
    severity: DeltaSeverity = DeltaSeverity.MEDIUM,
    delta_type: str = "new_finding",
    category: str = "criminal",
    description: str = "Test delta",
    requires_review: bool = False,
) -> ProfileDelta:
    """Helper to create a ProfileDelta."""
    return ProfileDelta(
        delta_type=delta_type,
        category=category,
        severity=severity,
        description=description,
        requires_review=requires_review,
    )


# =============================================================================
# Basic Tests
# =============================================================================


class TestAlertGeneratorBasic:
    """Basic alert generator tests."""

    def test_create_generator_default_config(self) -> None:
        """Test creating generator with default config."""
        generator = create_alert_generator()
        assert generator is not None
        assert isinstance(generator.config, AlertConfig)
        assert generator.config.auto_escalate_critical is True

    def test_create_generator_with_mock_channels(self) -> None:
        """Test creating generator with mock channels."""
        generator = create_alert_generator(include_mock_channels=True)
        assert NotificationChannelType.EMAIL in generator.channels
        assert NotificationChannelType.WEBHOOK in generator.channels
        assert NotificationChannelType.SMS in generator.channels

    def test_create_generator_custom_config(self) -> None:
        """Test creating generator with custom config."""
        config = AlertConfig(
            auto_escalate_critical=False,
            escalation_timeout_minutes=60,
        )
        generator = AlertGenerator(config=config)
        assert generator.config.auto_escalate_critical is False
        assert generator.config.escalation_timeout_minutes == 60

    def test_add_remove_channel(self) -> None:
        """Test adding and removing channels."""
        generator = AlertGenerator()
        assert len(generator.channels) == 0

        channel = MockEmailChannel()
        generator.add_channel(channel)
        assert NotificationChannelType.EMAIL in generator.channels

        generator.remove_channel(NotificationChannelType.EMAIL)
        assert NotificationChannelType.EMAIL not in generator.channels


# =============================================================================
# Threshold Tests
# =============================================================================


class TestAlertThresholds:
    """Tests for alert thresholds."""

    def test_v1_threshold_is_critical(self) -> None:
        """Test V1 only alerts on critical."""
        assert AUTO_ALERT_THRESHOLDS[VigilanceLevel.V1] == DeltaSeverity.CRITICAL

    def test_v2_threshold_is_high(self) -> None:
        """Test V2 alerts on high and above."""
        assert AUTO_ALERT_THRESHOLDS[VigilanceLevel.V2] == DeltaSeverity.HIGH

    def test_v3_threshold_is_medium(self) -> None:
        """Test V3 alerts on medium and above."""
        assert AUTO_ALERT_THRESHOLDS[VigilanceLevel.V3] == DeltaSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_v1_only_critical_alerts(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test V1 only generates alerts for critical."""
        monitoring_config.vigilance_level = VigilanceLevel.V1

        deltas = [
            make_delta(severity=DeltaSeverity.LOW),
            make_delta(severity=DeltaSeverity.MEDIUM),
            make_delta(severity=DeltaSeverity.HIGH),
        ]

        alerts = await generator.generate_alerts(deltas, monitoring_config)
        assert len(alerts) == 0

        # Now with critical
        deltas.append(make_delta(severity=DeltaSeverity.CRITICAL))
        alerts = await generator.generate_alerts(deltas, monitoring_config)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_v2_high_and_critical_alerts(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test V2 generates alerts for high and critical."""
        monitoring_config.vigilance_level = VigilanceLevel.V2

        deltas = [
            make_delta(severity=DeltaSeverity.LOW),
            make_delta(severity=DeltaSeverity.MEDIUM),
        ]

        alerts = await generator.generate_alerts(deltas, monitoring_config)
        assert len(alerts) == 0

        # Now with high
        deltas.append(make_delta(severity=DeltaSeverity.HIGH))
        alerts = await generator.generate_alerts(deltas, monitoring_config)
        assert len(alerts) == 1

    @pytest.mark.asyncio
    async def test_v3_medium_and_above_alerts(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test V3 generates alerts for medium and above."""
        monitoring_config.vigilance_level = VigilanceLevel.V3

        deltas = [
            make_delta(severity=DeltaSeverity.LOW),
        ]

        alerts = await generator.generate_alerts(deltas, monitoring_config)
        assert len(alerts) == 0

        # Now with medium
        deltas.append(make_delta(severity=DeltaSeverity.MEDIUM))
        alerts = await generator.generate_alerts(deltas, monitoring_config)
        assert len(alerts) == 1

    @pytest.mark.asyncio
    async def test_positive_never_alerts(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test positive changes never generate alerts."""
        monitoring_config.vigilance_level = VigilanceLevel.V3  # Lowest threshold

        deltas = [make_delta(severity=DeltaSeverity.POSITIVE)]
        alerts = await generator.generate_alerts(deltas, monitoring_config)
        assert len(alerts) == 0


# =============================================================================
# Alert Generation Tests
# =============================================================================


class TestAlertGeneration:
    """Tests for alert generation."""

    @pytest.mark.asyncio
    async def test_generate_single_alert(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test generating a single alert."""
        delta = make_delta(
            severity=DeltaSeverity.HIGH,
            description="New criminal record found",
        )

        alerts = await generator.generate_alerts([delta], monitoring_config)

        assert len(alerts) == 1
        assert alerts[0].alert.severity == AlertSeverity.HIGH
        assert "criminal record" in alerts[0].alert.description.lower()

    @pytest.mark.asyncio
    async def test_generate_multiple_alerts_grouped_by_severity(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test multiple deltas are grouped by severity."""
        deltas = [
            make_delta(severity=DeltaSeverity.HIGH, description="High 1"),
            make_delta(severity=DeltaSeverity.HIGH, description="High 2"),
            make_delta(severity=DeltaSeverity.CRITICAL, description="Critical 1"),
        ]

        alerts = await generator.generate_alerts(deltas, monitoring_config)

        # Should have 2 alerts: one for HIGH, one for CRITICAL
        assert len(alerts) == 2
        severities = {a.severity for a in alerts}
        assert AlertSeverity.HIGH in severities
        assert AlertSeverity.CRITICAL in severities

    @pytest.mark.asyncio
    async def test_alert_includes_delta_ids(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test alert includes delta IDs."""
        delta = make_delta(severity=DeltaSeverity.HIGH)
        alerts = await generator.generate_alerts([delta], monitoring_config)

        assert len(alerts[0].alert.delta_ids) == 1
        assert alerts[0].alert.delta_ids[0] == delta.delta_id

    @pytest.mark.asyncio
    async def test_alert_includes_recipients(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test alert includes recipients."""
        delta = make_delta(severity=DeltaSeverity.HIGH)
        alerts = await generator.generate_alerts([delta], monitoring_config)

        assert "security@example.com" in alerts[0].alert.recipients_notified
        assert "hr@example.com" in alerts[0].alert.recipients_notified

    @pytest.mark.asyncio
    async def test_no_alerts_when_no_deltas(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test no alerts generated when no deltas."""
        alerts = await generator.generate_alerts([], monitoring_config)
        assert len(alerts) == 0


# =============================================================================
# Escalation Tests
# =============================================================================


class TestEscalation:
    """Tests for alert escalation."""

    @pytest.mark.asyncio
    async def test_auto_escalate_critical(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test critical alerts are auto-escalated."""
        delta = make_delta(severity=DeltaSeverity.CRITICAL)
        alerts = await generator.generate_alerts([delta], monitoring_config)

        assert len(alerts) == 1
        assert alerts[0].is_escalated
        assert alerts[0].escalation_trigger == EscalationTrigger.SEVERITY
        assert "ciso@example.com" in alerts[0].alert.escalated_to

    @pytest.mark.asyncio
    async def test_disable_auto_escalate_critical(
        self, monitoring_config: MonitoringConfig
    ) -> None:
        """Test disabling auto-escalation."""
        config = AlertConfig(auto_escalate_critical=False)
        generator = AlertGenerator(config=config)
        generator.add_channel(MockEmailChannel())

        delta = make_delta(severity=DeltaSeverity.CRITICAL)
        alerts = await generator.generate_alerts([delta], monitoring_config)

        assert len(alerts) == 1
        assert not alerts[0].is_escalated

    @pytest.mark.asyncio
    async def test_multiple_alerts_escalation(
        self, monitoring_config: MonitoringConfig
    ) -> None:
        """Test escalation after multiple alerts."""
        config = AlertConfig(max_alerts_before_escalation=2)
        generator = AlertGenerator(config=config)
        generator.add_channel(MockEmailChannel())

        # First alert - no escalation (not critical, history empty)
        delta1 = make_delta(severity=DeltaSeverity.HIGH)
        alerts1 = await generator.generate_alerts([delta1], monitoring_config)
        assert not alerts1[0].is_escalated

        # Second alert - no escalation (1 in history, need 2)
        delta2 = make_delta(severity=DeltaSeverity.HIGH)
        alerts2 = await generator.generate_alerts([delta2], monitoring_config)
        assert not alerts2[0].is_escalated

        # Third alert - should trigger escalation (2 in history >= max)
        delta3 = make_delta(severity=DeltaSeverity.HIGH)
        alerts3 = await generator.generate_alerts([delta3], monitoring_config)
        assert alerts3[0].is_escalated
        assert alerts3[0].escalation_trigger == EscalationTrigger.MULTIPLE_ALERTS

    def test_manual_escalation(self) -> None:
        """Test manual escalation."""
        alert = MonitoringAlert(severity=AlertSeverity.HIGH, title="Test")
        generated = GeneratedAlert(alert=alert)

        assert not generated.is_escalated
        generated.escalate(EscalationTrigger.MANUAL)
        assert generated.is_escalated
        assert generated.escalation_trigger == EscalationTrigger.MANUAL
        assert generated.escalated_at is not None


# =============================================================================
# Notification Tests
# =============================================================================


class TestNotifications:
    """Tests for notification delivery."""

    @pytest.mark.asyncio
    async def test_email_notification_delivered(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test email notifications are delivered."""
        delta = make_delta(severity=DeltaSeverity.HIGH)
        alerts = await generator.generate_alerts([delta], monitoring_config)

        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.DELIVERED
        assert len(alerts[0].notification_results) > 0

        # Check email channel received messages
        email_channel = generator.channels[NotificationChannelType.EMAIL]
        assert len(email_channel.sent_messages) > 0

    @pytest.mark.asyncio
    async def test_notification_failure_handling(
        self, monitoring_config: MonitoringConfig
    ) -> None:
        """Test handling of notification failures."""
        generator = AlertGenerator()
        generator.add_channel(MockEmailChannel(should_fail=True))

        delta = make_delta(severity=DeltaSeverity.HIGH)
        alerts = await generator.generate_alerts([delta], monitoring_config)

        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.FAILED

    @pytest.mark.asyncio
    async def test_partial_delivery(self, monitoring_config: MonitoringConfig) -> None:
        """Test partial delivery when some notifications fail."""
        generator = AlertGenerator()
        generator.add_channel(MockEmailChannel())  # Success
        generator.add_channel(MockWebhookChannel(should_fail=True))  # Fail

        # Add a webhook recipient
        monitoring_config.alert_recipients.append("https://webhook.example.com")

        delta = make_delta(severity=DeltaSeverity.HIGH)
        alerts = await generator.generate_alerts([delta], monitoring_config)

        assert len(alerts) == 1
        # Should be partial since email succeeds but webhook fails
        assert alerts[0].status in (AlertStatus.DELIVERED, AlertStatus.PARTIALLY_DELIVERED)

    @pytest.mark.asyncio
    async def test_no_channels_configured(
        self, monitoring_config: MonitoringConfig
    ) -> None:
        """Test behavior when no channels configured."""
        generator = AlertGenerator()  # No channels

        delta = make_delta(severity=DeltaSeverity.HIGH)
        alerts = await generator.generate_alerts([delta], monitoring_config)

        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.PENDING

    @pytest.mark.asyncio
    async def test_escalated_includes_escalation_path(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test escalated alerts include escalation recipients."""
        delta = make_delta(severity=DeltaSeverity.CRITICAL)
        alerts = await generator.generate_alerts([delta], monitoring_config)

        # CISO should be in escalated_to
        assert "ciso@example.com" in alerts[0].alert.escalated_to


# =============================================================================
# Single Delta Evaluation Tests
# =============================================================================


class TestSingleDeltaEvaluation:
    """Tests for evaluating single deltas."""

    @pytest.mark.asyncio
    async def test_evaluate_single_delta_meets_threshold(
        self, generator: AlertGenerator
    ) -> None:
        """Test evaluating single delta that meets threshold."""
        delta = make_delta(severity=DeltaSeverity.HIGH)

        alert = await generator.evaluate_single_delta(
            delta=delta,
            vigilance_level=VigilanceLevel.V2,
            recipients=["test@example.com"],
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_evaluate_single_delta_below_threshold(
        self, generator: AlertGenerator
    ) -> None:
        """Test evaluating single delta below threshold."""
        delta = make_delta(severity=DeltaSeverity.MEDIUM)

        alert = await generator.evaluate_single_delta(
            delta=delta,
            vigilance_level=VigilanceLevel.V1,  # Requires critical
            recipients=["test@example.com"],
        )

        assert alert is None

    @pytest.mark.asyncio
    async def test_evaluate_single_critical_escalates(
        self, generator: AlertGenerator
    ) -> None:
        """Test single critical delta is escalated."""
        delta = make_delta(severity=DeltaSeverity.CRITICAL)

        alert = await generator.evaluate_single_delta(
            delta=delta,
            vigilance_level=VigilanceLevel.V2,
            recipients=["test@example.com"],
            escalation_path=["ciso@example.com"],
        )

        assert alert is not None
        assert alert.is_escalated
        assert "ciso@example.com" in alert.alert.escalated_to


# =============================================================================
# Alert Status Tests
# =============================================================================


class TestAlertStatus:
    """Tests for alert status management."""

    def test_acknowledge_alert(self) -> None:
        """Test acknowledging an alert."""
        alert = MonitoringAlert(severity=AlertSeverity.HIGH, title="Test")
        generated = GeneratedAlert(alert=alert)

        assert generated.status != AlertStatus.ACKNOWLEDGED
        generated.acknowledge(by="analyst@example.com")

        assert generated.status == AlertStatus.ACKNOWLEDGED
        assert generated.acknowledged_by == "analyst@example.com"
        assert generated.acknowledged_at is not None
        assert generated.alert.acknowledged is True

    def test_resolve_alert(self) -> None:
        """Test resolving an alert."""
        alert = MonitoringAlert(severity=AlertSeverity.HIGH, title="Test")
        generated = GeneratedAlert(alert=alert)

        generated.resolve(by="manager@example.com", notes="False positive")

        assert generated.status == AlertStatus.RESOLVED
        assert generated.resolved_by == "manager@example.com"
        assert generated.resolution_notes == "False positive"
        assert generated.resolved_at is not None
        assert generated.alert.resolved is True

    def test_delivery_success_rate(self) -> None:
        """Test delivery success rate calculation."""
        alert = MonitoringAlert(severity=AlertSeverity.HIGH, title="Test")
        generated = GeneratedAlert(alert=alert)

        # No notifications
        assert generated.delivery_success_rate == 0.0

        # Add some results
        generated.notification_results = [
            NotificationResult(
                channel_type=NotificationChannelType.EMAIL,
                recipient="a@example.com",
                success=True,
            ),
            NotificationResult(
                channel_type=NotificationChannelType.EMAIL,
                recipient="b@example.com",
                success=True,
            ),
            NotificationResult(
                channel_type=NotificationChannelType.EMAIL,
                recipient="c@example.com",
                success=False,
            ),
        ]

        assert generated.delivery_success_rate == pytest.approx(2 / 3)


# =============================================================================
# Alert History Tests
# =============================================================================


class TestAlertHistory:
    """Tests for alert history management."""

    @pytest.mark.asyncio
    async def test_get_alert_history(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test getting alert history."""
        # Generate some alerts
        for _ in range(3):
            delta = make_delta(severity=DeltaSeverity.HIGH)
            await generator.generate_alerts([delta], monitoring_config)

        history = generator.get_alert_history()
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_get_alert_history_with_limit(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test getting limited alert history."""
        for _ in range(5):
            delta = make_delta(severity=DeltaSeverity.HIGH)
            await generator.generate_alerts([delta], monitoring_config)

        history = generator.get_alert_history(limit=3)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_get_alert_history_by_config(
        self, generator: AlertGenerator
    ) -> None:
        """Test filtering history by config ID."""
        config1 = MonitoringConfig(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=uuid7(),
            alert_recipients=["test@example.com"],
        )
        config2 = MonitoringConfig(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=uuid7(),
            alert_recipients=["test@example.com"],
        )

        delta = make_delta(severity=DeltaSeverity.HIGH)
        await generator.generate_alerts([delta], config1)
        await generator.generate_alerts([delta], config1)
        await generator.generate_alerts([delta], config2)

        history1 = generator.get_alert_history(config_id=config1.config_id)
        assert len(history1) == 2

        history2 = generator.get_alert_history(config_id=config2.config_id)
        assert len(history2) == 1

    @pytest.mark.asyncio
    async def test_get_pending_alerts(
        self, monitoring_config: MonitoringConfig
    ) -> None:
        """Test getting pending alerts."""
        generator = AlertGenerator()  # No channels = stays pending

        delta = make_delta(severity=DeltaSeverity.HIGH)
        await generator.generate_alerts([delta], monitoring_config)

        pending = generator.get_pending_alerts()
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_get_unresolved_alerts(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test getting unresolved alerts."""
        delta = make_delta(severity=DeltaSeverity.HIGH)
        alerts = await generator.generate_alerts([delta], monitoring_config)

        unresolved = generator.get_unresolved_alerts()
        assert len(unresolved) == 1

        # Resolve it
        alerts[0].resolve(by="admin")
        unresolved = generator.get_unresolved_alerts()
        assert len(unresolved) == 0

    @pytest.mark.asyncio
    async def test_clear_history(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test clearing alert history."""
        delta = make_delta(severity=DeltaSeverity.HIGH)
        await generator.generate_alerts([delta], monitoring_config)

        assert len(generator.get_alert_history()) == 1

        cleared = generator.clear_history()
        assert cleared == 1
        assert len(generator.get_alert_history()) == 0


# =============================================================================
# Mock Channel Tests
# =============================================================================


class TestMockChannels:
    """Tests for mock notification channels."""

    @pytest.mark.asyncio
    async def test_mock_email_channel(self) -> None:
        """Test mock email channel."""
        channel = MockEmailChannel()
        result = await channel.send(
            recipient="test@example.com",
            subject="Test",
            body="Test body",
        )

        assert result.success
        assert result.channel_type == NotificationChannelType.EMAIL
        assert len(channel.sent_messages) == 1
        assert channel.sent_messages[0]["recipient"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_mock_email_channel_failure(self) -> None:
        """Test mock email channel failure."""
        channel = MockEmailChannel(should_fail=True)
        result = await channel.send(
            recipient="test@example.com",
            subject="Test",
            body="Test body",
        )

        assert not result.success
        assert result.error == "Mock email failure"

    @pytest.mark.asyncio
    async def test_mock_webhook_channel(self) -> None:
        """Test mock webhook channel."""
        channel = MockWebhookChannel()
        result = await channel.send(
            recipient="https://webhook.example.com",
            subject="Test",
            body="Test body",
        )

        assert result.success
        assert result.channel_type == NotificationChannelType.WEBHOOK
        assert len(channel.sent_webhooks) == 1

    @pytest.mark.asyncio
    async def test_mock_sms_channel(self) -> None:
        """Test mock SMS channel."""
        channel = MockSMSChannel()
        result = await channel.send(
            recipient="+1234567890",
            subject="Alert",
            body="Test message",
        )

        assert result.success
        assert result.channel_type == NotificationChannelType.SMS
        assert len(channel.sent_sms) == 1


# =============================================================================
# Configuration Tests
# =============================================================================


class TestAlertConfig:
    """Tests for alert configuration."""

    def test_default_config_values(self) -> None:
        """Test default configuration values."""
        config = AlertConfig()
        assert config.auto_escalate_critical is True
        assert config.escalation_timeout_minutes == 30
        assert config.max_alerts_before_escalation == 3
        assert config.alert_window_hours == 24
        assert config.include_delta_details is True
        assert config.notification_retry_count == 3

    def test_custom_config_values(self) -> None:
        """Test custom configuration values."""
        config = AlertConfig(
            auto_escalate_critical=False,
            escalation_timeout_minutes=60,
            max_alerts_before_escalation=5,
        )
        assert config.auto_escalate_critical is False
        assert config.escalation_timeout_minutes == 60
        assert config.max_alerts_before_escalation == 5

    def test_config_validation(self) -> None:
        """Test configuration validation."""
        with pytest.raises(ValueError):
            AlertConfig(escalation_timeout_minutes=0)

        with pytest.raises(ValueError):
            AlertConfig(max_alerts_before_escalation=0)


# =============================================================================
# Data Class Tests
# =============================================================================


class TestDataClasses:
    """Tests for data class serialization."""

    def test_notification_result_to_dict(self) -> None:
        """Test NotificationResult serialization."""
        result = NotificationResult(
            channel_type=NotificationChannelType.EMAIL,
            recipient="test@example.com",
            success=True,
            message_id="msg-123",
        )

        data = result.to_dict()
        assert data["channel_type"] == "email"
        assert data["recipient"] == "test@example.com"
        assert data["success"] is True
        assert data["message_id"] == "msg-123"

    def test_generated_alert_to_dict(self) -> None:
        """Test GeneratedAlert serialization."""
        alert = MonitoringAlert(severity=AlertSeverity.HIGH, title="Test Alert")
        generated = GeneratedAlert(
            alert=alert,
            status=AlertStatus.DELIVERED,
        )

        data = generated.to_dict()
        assert data["status"] == "delivered"
        assert "alert" in data
        assert data["delivery_success_rate"] == 0.0


# =============================================================================
# Integration-Like Tests
# =============================================================================


class TestIntegrationScenarios:
    """Integration-like tests for realistic scenarios."""

    @pytest.mark.asyncio
    async def test_full_alert_workflow(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test complete alert workflow."""
        # Generate alert
        delta = make_delta(
            severity=DeltaSeverity.HIGH,
            description="New financial judgment",
            category="financial",
        )
        alerts = await generator.generate_alerts([delta], monitoring_config)

        assert len(alerts) == 1
        alert = alerts[0]

        # Verify initial state
        assert alert.status == AlertStatus.DELIVERED
        assert len(alert.notification_results) > 0

        # Acknowledge
        alert.acknowledge(by="analyst@example.com")
        assert alert.status == AlertStatus.ACKNOWLEDGED

        # Resolve
        alert.resolve(by="manager@example.com", notes="Verified and acceptable")
        assert alert.status == AlertStatus.RESOLVED

    @pytest.mark.asyncio
    async def test_critical_alert_full_workflow(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test critical alert with escalation."""
        delta = make_delta(
            severity=DeltaSeverity.CRITICAL,
            description="New felony conviction",
            category="criminal",
        )
        alerts = await generator.generate_alerts([delta], monitoring_config)

        assert len(alerts) == 1
        alert = alerts[0]

        # Should be escalated
        assert alert.is_escalated
        assert alert.escalation_trigger == EscalationTrigger.SEVERITY

        # CISO notified
        assert "ciso@example.com" in alert.alert.escalated_to

    @pytest.mark.asyncio
    async def test_mixed_severity_deltas(
        self, generator: AlertGenerator, monitoring_config: MonitoringConfig
    ) -> None:
        """Test handling mixed severity deltas."""
        monitoring_config.vigilance_level = VigilanceLevel.V3

        deltas = [
            make_delta(severity=DeltaSeverity.POSITIVE, description="Resolved issue"),
            make_delta(severity=DeltaSeverity.LOW, description="Minor change"),
            make_delta(severity=DeltaSeverity.MEDIUM, description="Notable change"),
            make_delta(severity=DeltaSeverity.HIGH, description="Significant issue"),
            make_delta(severity=DeltaSeverity.CRITICAL, description="Critical issue"),
        ]

        alerts = await generator.generate_alerts(deltas, monitoring_config)

        # V3 threshold is MEDIUM, so MEDIUM, HIGH, CRITICAL should alert
        # But POSITIVE and LOW should not
        assert len(alerts) == 3

        severities = {a.severity for a in alerts}
        assert AlertSeverity.MEDIUM in severities
        assert AlertSeverity.HIGH in severities
        assert AlertSeverity.CRITICAL in severities
