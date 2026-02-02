"""Unit tests for the HRIS Result Publisher."""

from datetime import UTC, datetime
from uuid import UUID, uuid7

import pytest

from elile.hris.gateway import (
    GatewayConfig,
    HRISConnection,
    HRISConnectionStatus,
    HRISGateway,
    HRISPlatform,
    MockHRISAdapter,
    create_hris_gateway,
)
from elile.hris.result_publisher import (
    DeliveryRecord,
    HRISResultPublisher,
    PublishEventType,
    PublisherConfig,
    PublishResult,
    PublishStatus,
    create_result_publisher,
)
from elile.monitoring.types import AlertSeverity, MonitoringAlert
from elile.screening.types import ScreeningResult, ScreeningStatus


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tenant_id() -> UUID:
    """Test tenant ID."""
    return uuid7()


@pytest.fixture
def screening_id() -> UUID:
    """Test screening ID."""
    return uuid7()


@pytest.fixture
def employee_id() -> str:
    """Test employee ID."""
    return "EMP-001"


@pytest.fixture
def mock_adapter() -> MockHRISAdapter:
    """Mock HRIS adapter for testing."""
    return MockHRISAdapter()


@pytest.fixture
def gateway(mock_adapter: MockHRISAdapter) -> HRISGateway:
    """HRIS gateway with mock adapter."""
    gateway = HRISGateway()
    gateway.register_adapter(mock_adapter)
    return gateway


@pytest.fixture
def gateway_with_connection(
    gateway: HRISGateway, tenant_id: UUID, mock_adapter: MockHRISAdapter
) -> HRISGateway:
    """Gateway with a registered connection for the test tenant."""
    connection = HRISConnection(
        connection_id=uuid7(),
        tenant_id=tenant_id,
        platform=mock_adapter.platform_id,
        status=HRISConnectionStatus.CONNECTED,
        enabled=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    gateway.register_connection(connection)
    return gateway


@pytest.fixture
def publisher(gateway_with_connection: HRISGateway) -> HRISResultPublisher:
    """Result publisher with configured gateway."""
    return HRISResultPublisher(gateway=gateway_with_connection)


@pytest.fixture
def publisher_config() -> PublisherConfig:
    """Custom publisher configuration."""
    return PublisherConfig(
        publish_progress_updates=True,
        publish_review_required=True,
        include_findings_summary=True,
        include_risk_details=True,
    )


@pytest.fixture
def screening_result(screening_id: UUID) -> ScreeningResult:
    """Sample screening result for testing."""
    return ScreeningResult(
        result_id=uuid7(),
        screening_id=screening_id,
        status=ScreeningStatus.COMPLETE,
        risk_score=45,
        risk_level="moderate",
        recommendation="review_required",
        phases=[],
    )


@pytest.fixture
def monitoring_alert() -> MonitoringAlert:
    """Sample monitoring alert for testing."""
    return MonitoringAlert(
        alert_id=uuid7(),
        monitoring_config_id=uuid7(),
        check_id=uuid7(),
        severity=AlertSeverity.HIGH,
        title="New Criminal Record Found",
        description="A new criminal record was found during scheduled monitoring.",
        created_at=datetime.now(UTC),
    )


# =============================================================================
# Factory Tests
# =============================================================================


class TestCreateResultPublisher:
    """Tests for create_result_publisher factory function."""

    def test_create_with_defaults(self, gateway: HRISGateway) -> None:
        """Should create publisher with default configuration."""
        publisher = create_result_publisher(gateway=gateway)

        assert publisher is not None
        assert publisher.config is not None
        assert publisher.config.publish_progress_updates is True
        assert publisher.config.include_risk_details is True

    def test_create_with_custom_config(
        self, gateway: HRISGateway, publisher_config: PublisherConfig
    ) -> None:
        """Should create publisher with custom configuration."""
        publisher = create_result_publisher(gateway=gateway, config=publisher_config)

        assert publisher.config == publisher_config
        assert publisher.config.include_findings_summary is True

    def test_create_with_credentials_store(self, gateway: HRISGateway) -> None:
        """Should accept credentials store."""
        tenant_id = uuid7()
        creds = {tenant_id: {"api_key": "test-key"}}
        publisher = create_result_publisher(gateway=gateway, credentials_store=creds)

        assert publisher._get_credentials(tenant_id) == {"api_key": "test-key"}


# =============================================================================
# Publish Result Model Tests
# =============================================================================


class TestPublishResult:
    """Tests for PublishResult dataclass."""

    def test_default_creation(self) -> None:
        """Should create result with defaults."""
        result = PublishResult()

        assert result.result_id is not None
        assert result.status == PublishStatus.PENDING
        assert result.attempts == 0
        assert result.is_delivered is False
        assert result.is_failed is False

    def test_delivered_status(self) -> None:
        """Should correctly report delivered status."""
        result = PublishResult(status=PublishStatus.DELIVERED)

        assert result.is_delivered is True
        assert result.is_failed is False

    def test_failed_status(self) -> None:
        """Should correctly report failed status."""
        result = PublishResult(status=PublishStatus.FAILED)

        assert result.is_delivered is False
        assert result.is_failed is True

    def test_to_dict(self, screening_id: UUID, tenant_id: UUID) -> None:
        """Should convert to dictionary."""
        result = PublishResult(
            event_type=PublishEventType.SCREENING_COMPLETE,
            screening_id=screening_id,
            tenant_id=tenant_id,
            employee_id="EMP-001",
            status=PublishStatus.DELIVERED,
            attempts=1,
        )

        result_dict = result.to_dict()

        assert result_dict["event_type"] == "screening.complete"
        assert result_dict["screening_id"] == str(screening_id)
        assert result_dict["tenant_id"] == str(tenant_id)
        assert result_dict["employee_id"] == "EMP-001"
        assert result_dict["status"] == "delivered"
        assert result_dict["attempts"] == 1


# =============================================================================
# Delivery Record Tests
# =============================================================================


class TestDeliveryRecord:
    """Tests for DeliveryRecord dataclass."""

    def test_default_creation(self, tenant_id: UUID) -> None:
        """Should create record with defaults."""
        record = DeliveryRecord(
            tenant_id=tenant_id,
            employee_id="EMP-001",
        )

        assert record.record_id is not None
        assert record.attempt_number == 1
        assert record.success is False
        assert record.error_message is None


# =============================================================================
# Publisher Config Tests
# =============================================================================


class TestPublisherConfig:
    """Tests for PublisherConfig."""

    def test_default_config(self) -> None:
        """Should create config with defaults."""
        config = PublisherConfig()

        assert config.publish_progress_updates is True
        assert config.publish_review_required is True
        assert config.progress_update_interval_percent == 25
        assert config.include_findings_summary is False
        assert config.include_risk_details is True

    def test_custom_config(self) -> None:
        """Should accept custom values."""
        config = PublisherConfig(
            publish_progress_updates=False,
            progress_update_interval_percent=10,
            include_findings_summary=True,
        )

        assert config.publish_progress_updates is False
        assert config.progress_update_interval_percent == 10
        assert config.include_findings_summary is True


# =============================================================================
# Screening Started Tests
# =============================================================================


class TestPublishScreeningStarted:
    """Tests for publish_screening_started method."""

    @pytest.mark.asyncio
    async def test_publish_started_success(
        self,
        publisher: HRISResultPublisher,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should publish screening started event."""
        result = await publisher.publish_screening_started(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
        )

        assert result.event_type == PublishEventType.SCREENING_STARTED
        assert result.status == PublishStatus.DELIVERED
        assert result.screening_id == screening_id
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_publish_started_with_estimate(
        self,
        publisher: HRISResultPublisher,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should include estimated completion time."""
        est = datetime.now(UTC)
        result = await publisher.publish_screening_started(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
            estimated_completion=est,
        )

        assert result.status == PublishStatus.DELIVERED


# =============================================================================
# Screening Progress Tests
# =============================================================================


class TestPublishScreeningProgress:
    """Tests for publish_screening_progress method."""

    @pytest.mark.asyncio
    async def test_publish_progress_success(
        self,
        publisher: HRISResultPublisher,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should publish progress update."""
        result = await publisher.publish_screening_progress(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
            progress_percent=50,
        )

        assert result.event_type == PublishEventType.SCREENING_PROGRESS
        assert result.status == PublishStatus.DELIVERED
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_publish_progress_skipped_when_disabled(
        self,
        gateway_with_connection: HRISGateway,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should skip progress update when disabled in config."""
        config = PublisherConfig(publish_progress_updates=False)
        publisher = HRISResultPublisher(gateway=gateway_with_connection, config=config)

        result = await publisher.publish_screening_progress(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
            progress_percent=50,
        )

        assert result.status == PublishStatus.SKIPPED
        assert result.metadata.get("reason") == "progress_updates_disabled"


# =============================================================================
# Screening Complete Tests
# =============================================================================


class TestPublishScreeningComplete:
    """Tests for publish_screening_complete method."""

    @pytest.mark.asyncio
    async def test_publish_complete_success(
        self,
        publisher: HRISResultPublisher,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
        screening_result: ScreeningResult,
    ) -> None:
        """Should publish screening completion."""
        result = await publisher.publish_screening_complete(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
            result=screening_result,
        )

        assert result.event_type == PublishEventType.SCREENING_COMPLETE
        assert result.status == PublishStatus.DELIVERED
        assert result.screening_id == screening_id
        assert result.attempts == 1
        assert result.delivered_at is not None

    @pytest.mark.asyncio
    async def test_publish_complete_includes_risk_details(
        self,
        publisher: HRISResultPublisher,
        mock_adapter: MockHRISAdapter,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
        screening_result: ScreeningResult,
    ) -> None:
        """Should include risk details when configured."""
        await publisher.publish_screening_complete(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
            result=screening_result,
        )

        # Check the mock adapter received the update
        assert len(mock_adapter.published_updates) == 1
        update = mock_adapter.published_updates[0]
        assert update.risk_level == "moderate"
        assert update.recommendation == "review_required"

    @pytest.mark.asyncio
    async def test_publish_complete_excludes_risk_when_disabled(
        self,
        gateway_with_connection: HRISGateway,
        mock_adapter: MockHRISAdapter,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
        screening_result: ScreeningResult,
    ) -> None:
        """Should exclude risk details when disabled."""
        config = PublisherConfig(include_risk_details=False)
        publisher = HRISResultPublisher(gateway=gateway_with_connection, config=config)

        await publisher.publish_screening_complete(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
            result=screening_result,
        )

        update = mock_adapter.published_updates[0]
        assert update.risk_level is None
        assert update.recommendation is None


# =============================================================================
# Review Required Tests
# =============================================================================


class TestPublishReviewRequired:
    """Tests for publish_review_required method."""

    @pytest.mark.asyncio
    async def test_publish_review_required_success(
        self,
        publisher: HRISResultPublisher,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should publish review required notification."""
        result = await publisher.publish_review_required(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
            reason="High risk score requires manual review",
            risk_level="high",
        )

        assert result.event_type == PublishEventType.REVIEW_REQUIRED
        assert result.status == PublishStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_publish_review_skipped_when_disabled(
        self,
        gateway_with_connection: HRISGateway,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should skip review required when disabled."""
        config = PublisherConfig(publish_review_required=False)
        publisher = HRISResultPublisher(gateway=gateway_with_connection, config=config)

        result = await publisher.publish_review_required(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
            reason="Test reason",
        )

        assert result.status == PublishStatus.SKIPPED


# =============================================================================
# Adverse Action Pending Tests
# =============================================================================


class TestPublishAdverseActionPending:
    """Tests for publish_adverse_action_pending method."""

    @pytest.mark.asyncio
    async def test_publish_adverse_action_success(
        self,
        publisher: HRISResultPublisher,
        mock_adapter: MockHRISAdapter,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should publish adverse action pending notification."""
        result = await publisher.publish_adverse_action_pending(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
            reason="Criminal record disqualifies candidate",
            pre_adverse_notice_sent=True,
        )

        assert result.event_type == PublishEventType.ADVERSE_ACTION_PENDING
        assert result.status == PublishStatus.DELIVERED

        # Verify update content
        update = mock_adapter.published_updates[0]
        assert update.status == "adverse_action_pending"
        assert update.findings_summary["adverse_action_pending"] is True
        assert update.findings_summary["pre_adverse_notice_sent"] is True


# =============================================================================
# Alert Tests
# =============================================================================


class TestPublishAlert:
    """Tests for publish_alert method."""

    @pytest.mark.asyncio
    async def test_publish_alert_success(
        self,
        publisher: HRISResultPublisher,
        mock_adapter: MockHRISAdapter,
        tenant_id: UUID,
        employee_id: str,
        monitoring_alert: MonitoringAlert,
    ) -> None:
        """Should publish monitoring alert."""
        result = await publisher.publish_alert(
            alert=monitoring_alert,
            employee_id=employee_id,
            tenant_id=tenant_id,
        )

        assert result.event_type == PublishEventType.ALERT_GENERATED
        assert result.status == PublishStatus.DELIVERED
        assert result.alert_id == monitoring_alert.alert_id

        # Verify alert content
        assert len(mock_adapter.published_alerts) == 1
        alert_update = mock_adapter.published_alerts[0]
        assert alert_update.severity == "high"
        assert alert_update.title == monitoring_alert.title
        assert alert_update.requires_action is True  # High severity

    @pytest.mark.asyncio
    async def test_publish_alert_low_severity(
        self,
        publisher: HRISResultPublisher,
        mock_adapter: MockHRISAdapter,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should publish low severity alert without requiring action."""
        alert = MonitoringAlert(
            alert_id=uuid7(),
            monitoring_config_id=uuid7(),
            check_id=uuid7(),
            severity=AlertSeverity.LOW,
            title="Minor Update",
            description="Address change detected",
            created_at=datetime.now(UTC),
        )

        result = await publisher.publish_alert(
            alert=alert,
            employee_id=employee_id,
            tenant_id=tenant_id,
        )

        assert result.status == PublishStatus.DELIVERED
        alert_update = mock_adapter.published_alerts[0]
        assert alert_update.requires_action is False  # Low severity


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_publish_fails_no_connection(
        self,
        gateway: HRISGateway,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should fail when no connection exists for tenant."""
        publisher = HRISResultPublisher(gateway=gateway)
        tenant_id = uuid7()  # No connection for this tenant

        result = await publisher.publish_screening_started(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
        )

        # Gateway returns False when no connection
        assert result.status == PublishStatus.FAILED

    @pytest.mark.asyncio
    async def test_publish_fails_adapter_error(
        self,
        gateway: HRISGateway,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should handle adapter failures."""
        # Create adapter that fails publishing
        failing_adapter = MockHRISAdapter(should_fail_publish=True)
        gateway.register_adapter(failing_adapter)

        connection = HRISConnection(
            connection_id=uuid7(),
            tenant_id=tenant_id,
            platform=failing_adapter.platform_id,
            status=HRISConnectionStatus.CONNECTED,
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        gateway.register_connection(connection)

        publisher = HRISResultPublisher(gateway=gateway)

        result = await publisher.publish_screening_started(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
        )

        assert result.status == PublishStatus.FAILED
        assert result.error_message is not None


# =============================================================================
# Statistics Tests
# =============================================================================


class TestStatistics:
    """Tests for statistics and history tracking."""

    @pytest.mark.asyncio
    async def test_get_statistics(
        self,
        publisher: HRISResultPublisher,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should track publishing statistics."""
        # Publish some events
        await publisher.publish_screening_started(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
        )
        await publisher.publish_screening_progress(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
            progress_percent=50,
        )

        stats = publisher.get_statistics()

        assert stats["total_deliveries"] == 2
        assert stats["successful_deliveries"] == 2
        assert stats["success_rate"] == 1.0
        assert PublishEventType.SCREENING_STARTED.value in str(stats["events_published"])

    @pytest.mark.asyncio
    async def test_get_delivery_history(
        self,
        publisher: HRISResultPublisher,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should retrieve delivery history."""
        await publisher.publish_screening_started(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
        )

        history = publisher.get_delivery_history(tenant_id=tenant_id)

        assert len(history) == 1
        assert history[0].tenant_id == tenant_id
        assert history[0].success is True

    @pytest.mark.asyncio
    async def test_get_delivery_history_filtered(
        self,
        publisher: HRISResultPublisher,
        tenant_id: UUID,
        screening_id: UUID,
        employee_id: str,
    ) -> None:
        """Should filter delivery history by event type."""
        await publisher.publish_screening_started(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
        )
        await publisher.publish_screening_progress(
            screening_id=screening_id,
            employee_id=employee_id,
            tenant_id=tenant_id,
            progress_percent=50,
        )

        history = publisher.get_delivery_history(
            event_type=PublishEventType.SCREENING_STARTED,
        )

        assert len(history) == 1
        assert history[0].event_type == PublishEventType.SCREENING_STARTED

    def test_clear_history(self, publisher: HRISResultPublisher) -> None:
        """Should clear delivery history."""
        publisher._delivery_history.append(
            DeliveryRecord(
                tenant_id=uuid7(),
                employee_id="EMP-001",
            )
        )

        assert len(publisher._delivery_history) == 1
        publisher.clear_history()
        assert len(publisher._delivery_history) == 0


# =============================================================================
# Credentials Tests
# =============================================================================


class TestCredentials:
    """Tests for credentials handling."""

    def test_get_credentials_found(self, gateway: HRISGateway) -> None:
        """Should return credentials when found."""
        tenant_id = uuid7()
        creds = {"api_key": "secret"}
        publisher = HRISResultPublisher(
            gateway=gateway,
            credentials_store={tenant_id: creds},
        )

        result = publisher._get_credentials(tenant_id)
        assert result == creds

    def test_get_credentials_not_found(self, gateway: HRISGateway) -> None:
        """Should return empty dict when credentials not found."""
        publisher = HRISResultPublisher(gateway=gateway)

        result = publisher._get_credentials(uuid7())
        assert result == {}
