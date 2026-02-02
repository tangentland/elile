"""Unit tests for HRIS Integration Gateway (Task 10.1)."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from elile.hris import (
    AlertUpdate,
    BaseHRISAdapter,
    EmployeeInfo,
    GatewayConfig,
    HRISConnection,
    HRISConnectionStatus,
    HRISEvent,
    HRISEventType,
    HRISGateway,
    HRISPlatform,
    MockHRISAdapter,
    ScreeningUpdate,
    WebhookValidationResult,
    create_hris_gateway,
)

# =============================================================================
# GatewayConfig Tests
# =============================================================================


class TestGatewayConfig:
    """Tests for GatewayConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = GatewayConfig()

        assert config.max_retries == 3
        assert config.retry_backoff_seconds == [30, 300, 3600]
        assert config.webhook_timeout_seconds == 30
        assert config.api_timeout_seconds == 60
        assert config.max_events_per_minute == 1000
        assert config.max_outbound_per_minute == 100
        assert config.require_webhook_signature is True
        assert config.allow_unknown_event_types is False
        assert config.event_retention_days == 90

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = GatewayConfig(
            max_retries=5,
            retry_backoff_seconds=[10, 60, 600],
            webhook_timeout_seconds=15,
            require_webhook_signature=False,
        )

        assert config.max_retries == 5
        assert config.retry_backoff_seconds == [10, 60, 600]
        assert config.webhook_timeout_seconds == 15
        assert config.require_webhook_signature is False

    def test_get_retry_delay(self) -> None:
        """Test retry delay calculation."""
        config = GatewayConfig(retry_backoff_seconds=[30, 300, 3600])

        assert config.get_retry_delay(0) == timedelta(seconds=30)
        assert config.get_retry_delay(1) == timedelta(seconds=300)
        assert config.get_retry_delay(2) == timedelta(seconds=3600)
        # Beyond list length uses last value
        assert config.get_retry_delay(5) == timedelta(seconds=3600)

    def test_get_retry_delay_negative_attempt(self) -> None:
        """Test retry delay with negative attempt number."""
        config = GatewayConfig()

        assert config.get_retry_delay(-1) == timedelta(seconds=0)

    def test_config_validation(self) -> None:
        """Test configuration validation bounds."""
        with pytest.raises(ValueError):
            GatewayConfig(max_retries=-1)

        with pytest.raises(ValueError):
            GatewayConfig(max_retries=15)  # Above max

        with pytest.raises(ValueError):
            GatewayConfig(webhook_timeout_seconds=3)  # Below min


# =============================================================================
# HRISEventType Tests
# =============================================================================


class TestHRISEventType:
    """Tests for HRISEventType enum."""

    def test_inbound_event_types(self) -> None:
        """Test inbound event types."""
        inbound = [
            HRISEventType.HIRE_INITIATED,
            HRISEventType.CONSENT_GRANTED,
            HRISEventType.POSITION_CHANGED,
            HRISEventType.EMPLOYEE_TERMINATED,
            HRISEventType.REHIRE_INITIATED,
        ]

        for event_type in inbound:
            assert event_type.value.startswith(("hire", "consent", "position", "employee", "rehire"))

    def test_outbound_event_types(self) -> None:
        """Test outbound event types."""
        outbound = [
            HRISEventType.SCREENING_STARTED,
            HRISEventType.SCREENING_PROGRESS,
            HRISEventType.SCREENING_COMPLETE,
            HRISEventType.REVIEW_REQUIRED,
            HRISEventType.ALERT_GENERATED,
            HRISEventType.ADVERSE_ACTION_PENDING,
        ]

        for event_type in outbound:
            assert event_type.value.startswith(("screening", "review", "alert", "adverse"))


# =============================================================================
# HRISEvent Tests
# =============================================================================


class TestHRISEvent:
    """Tests for HRISEvent dataclass."""

    def test_create_inbound_event(self) -> None:
        """Test creating an inbound event."""
        event = HRISEvent(
            event_id=uuid4(),
            event_type=HRISEventType.HIRE_INITIATED,
            tenant_id=uuid4(),
            employee_id="EMP-123",
            platform=HRISPlatform.WORKDAY,
            received_at=datetime.now(),
            event_data={"position": "Engineer"},
        )

        assert event.is_inbound() is True
        assert event.is_outbound() is False

    def test_create_outbound_event(self) -> None:
        """Test creating an outbound event."""
        event = HRISEvent(
            event_id=uuid4(),
            event_type=HRISEventType.SCREENING_COMPLETE,
            tenant_id=uuid4(),
            employee_id="EMP-123",
            platform=HRISPlatform.WORKDAY,
            received_at=datetime.now(),
        )

        assert event.is_outbound() is True
        assert event.is_inbound() is False

    def test_event_with_optional_fields(self) -> None:
        """Test event with optional fields."""
        event = HRISEvent(
            event_id=uuid4(),
            event_type=HRISEventType.CONSENT_GRANTED,
            tenant_id=uuid4(),
            employee_id="EMP-456",
            platform=HRISPlatform.SAP_SUCCESSFACTORS,
            received_at=datetime.now(),
            consent_reference="CONSENT-789",
            position_info={"title": "Manager", "department": "Engineering"},
            screening_id=uuid4(),
        )

        assert event.consent_reference == "CONSENT-789"
        assert event.position_info is not None
        assert event.screening_id is not None


# =============================================================================
# WebhookValidationResult Tests
# =============================================================================


class TestWebhookValidationResult:
    """Tests for WebhookValidationResult."""

    def test_success_result(self) -> None:
        """Test successful validation result."""
        result = WebhookValidationResult.success()

        assert result.valid is True
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test failed validation result."""
        result = WebhookValidationResult.failure("Invalid signature")

        assert result.valid is False
        assert result.error == "Invalid signature"


# =============================================================================
# HRISPlatform Tests
# =============================================================================


class TestHRISPlatform:
    """Tests for HRISPlatform enum."""

    def test_all_platforms(self) -> None:
        """Test all supported platforms."""
        platforms = [
            HRISPlatform.WORKDAY,
            HRISPlatform.SAP_SUCCESSFACTORS,
            HRISPlatform.ORACLE_HCM,
            HRISPlatform.ADP,
            HRISPlatform.BAMBOO_HR,
            HRISPlatform.GENERIC_WEBHOOK,
        ]

        assert len(platforms) == 6
        for platform in platforms:
            assert isinstance(platform.value, str)


# =============================================================================
# HRISConnection Tests
# =============================================================================


class TestHRISConnection:
    """Tests for HRISConnection model."""

    def test_create_connection(self) -> None:
        """Test creating a connection."""
        now = datetime.now()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=uuid4(),
            platform=HRISPlatform.WORKDAY,
            webhook_secret="secret123",
            created_at=now,
            updated_at=now,
        )

        assert connection.status == HRISConnectionStatus.PENDING
        assert connection.enabled is True
        assert connection.webhook_secret == "secret123"

    def test_connection_with_error(self) -> None:
        """Test connection with error state."""
        now = datetime.now()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=uuid4(),
            platform=HRISPlatform.ADP,
            status=HRISConnectionStatus.ERROR,
            last_error_at=now,
            last_error_message="Connection timeout",
            created_at=now,
            updated_at=now,
        )

        assert connection.status == HRISConnectionStatus.ERROR
        assert connection.last_error_message == "Connection timeout"


# =============================================================================
# ScreeningUpdate Tests
# =============================================================================


class TestScreeningUpdate:
    """Tests for ScreeningUpdate dataclass."""

    def test_create_screening_update(self) -> None:
        """Test creating a screening update."""
        update = ScreeningUpdate(
            screening_id=uuid4(),
            status="complete",
            timestamp=datetime.now(),
            progress_percent=100,
            risk_level="low",
            recommendation="proceed",
        )

        assert update.progress_percent == 100
        assert update.risk_level == "low"
        assert update.recommendation == "proceed"


# =============================================================================
# AlertUpdate Tests
# =============================================================================


class TestAlertUpdate:
    """Tests for AlertUpdate dataclass."""

    def test_create_alert_update(self) -> None:
        """Test creating an alert update."""
        alert = AlertUpdate(
            alert_id=uuid4(),
            employee_id="EMP-123",
            severity="high",
            title="New Criminal Record Found",
            description="A new felony was detected.",
            created_at=datetime.now(),
            requires_action=True,
        )

        assert alert.severity == "high"
        assert alert.requires_action is True


# =============================================================================
# EmployeeInfo Tests
# =============================================================================


class TestEmployeeInfo:
    """Tests for EmployeeInfo dataclass."""

    def test_create_employee_info(self) -> None:
        """Test creating employee info."""
        employee = EmployeeInfo(
            employee_id="EMP-789",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            department="Engineering",
            job_title="Senior Engineer",
        )

        assert employee.first_name == "John"
        assert employee.department == "Engineering"


# =============================================================================
# MockHRISAdapter Tests
# =============================================================================


class TestMockHRISAdapter:
    """Tests for MockHRISAdapter."""

    def test_create_mock_adapter(self) -> None:
        """Test creating a mock adapter."""
        adapter = MockHRISAdapter()

        assert adapter.platform_id == HRISPlatform.GENERIC_WEBHOOK
        assert adapter.platform_name == "Mock HRIS"

    def test_custom_mock_adapter(self) -> None:
        """Test creating a custom mock adapter."""
        adapter = MockHRISAdapter(
            platform=HRISPlatform.WORKDAY,
            name="Mock Workday",
        )

        assert adapter.platform_id == HRISPlatform.WORKDAY
        assert adapter.platform_name == "Mock Workday"

    @pytest.mark.asyncio
    async def test_validate_webhook_success(self) -> None:
        """Test successful webhook validation."""
        adapter = MockHRISAdapter()

        result = await adapter.validate_webhook(
            headers={"x-signature": "valid"},
            payload=b"{}",
            secret="secret",
        )

        assert result.valid is True

    @pytest.mark.asyncio
    async def test_validate_webhook_failure(self) -> None:
        """Test failed webhook validation."""
        adapter = MockHRISAdapter(should_fail_validation=True)

        result = await adapter.validate_webhook(
            headers={"x-signature": "invalid"},
            payload=b"{}",
            secret="secret",
        )

        assert result.valid is False
        assert "Mock validation failure" in (result.error or "")

    @pytest.mark.asyncio
    async def test_parse_event(self) -> None:
        """Test event parsing."""
        adapter = MockHRISAdapter()
        tenant_id = uuid4()

        event = await adapter.parse_event(
            event_type="hire.initiated",
            payload={"employee_id": "EMP-123", "consent_reference": "CONSENT-456"},
            tenant_id=tenant_id,
        )

        assert event.event_type == HRISEventType.HIRE_INITIATED
        assert event.tenant_id == tenant_id
        assert event.employee_id == "EMP-123"
        assert event.consent_reference == "CONSENT-456"

    @pytest.mark.asyncio
    async def test_parse_event_consent_granted(self) -> None:
        """Test parsing consent granted event."""
        adapter = MockHRISAdapter()

        event = await adapter.parse_event(
            event_type="consent.granted",
            payload={"employee_id": "EMP-789"},
            tenant_id=uuid4(),
        )

        assert event.event_type == HRISEventType.CONSENT_GRANTED

    @pytest.mark.asyncio
    async def test_publish_update_success(self) -> None:
        """Test successful update publishing."""
        adapter = MockHRISAdapter()
        update = ScreeningUpdate(
            screening_id=uuid4(),
            status="complete",
            timestamp=datetime.now(),
        )

        result = await adapter.publish_update(
            tenant_id=uuid4(),
            employee_id="EMP-123",
            update=update,
            credentials={},
        )

        assert result is True
        assert len(adapter.published_updates) == 1
        assert adapter.published_updates[0] == update

    @pytest.mark.asyncio
    async def test_publish_update_failure(self) -> None:
        """Test failed update publishing."""
        adapter = MockHRISAdapter(should_fail_publish=True)
        update = ScreeningUpdate(
            screening_id=uuid4(),
            status="complete",
            timestamp=datetime.now(),
        )

        result = await adapter.publish_update(
            tenant_id=uuid4(),
            employee_id="EMP-123",
            update=update,
            credentials={},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_publish_alert_success(self) -> None:
        """Test successful alert publishing."""
        adapter = MockHRISAdapter()
        alert = AlertUpdate(
            alert_id=uuid4(),
            employee_id="EMP-123",
            severity="high",
            title="Test Alert",
            description="Test description",
            created_at=datetime.now(),
        )

        result = await adapter.publish_alert(
            tenant_id=uuid4(),
            employee_id="EMP-123",
            alert=alert,
            credentials={},
        )

        assert result is True
        assert len(adapter.published_alerts) == 1

    @pytest.mark.asyncio
    async def test_get_employee_found(self) -> None:
        """Test getting an existing employee."""
        adapter = MockHRISAdapter()
        employee = EmployeeInfo(
            employee_id="EMP-123",
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
        )
        adapter.add_employee(employee)

        result = await adapter.get_employee(
            tenant_id=uuid4(),
            employee_id="EMP-123",
            credentials={},
        )

        assert result is not None
        assert result.first_name == "Jane"

    @pytest.mark.asyncio
    async def test_get_employee_not_found(self) -> None:
        """Test getting a non-existent employee."""
        adapter = MockHRISAdapter()

        result = await adapter.get_employee(
            tenant_id=uuid4(),
            employee_id="EMP-UNKNOWN",
            credentials={},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_test_connection(self) -> None:
        """Test connection testing."""
        adapter = MockHRISAdapter(connection_status=HRISConnectionStatus.CONNECTED)

        status = await adapter.test_connection(credentials={})

        assert status == HRISConnectionStatus.CONNECTED


# =============================================================================
# HRISGateway Tests
# =============================================================================


class TestHRISGateway:
    """Tests for HRISGateway."""

    def test_create_gateway(self) -> None:
        """Test creating a gateway."""
        gateway = HRISGateway()

        assert gateway.config is not None
        assert len(gateway.list_adapters()) == 0

    def test_create_gateway_with_config(self) -> None:
        """Test creating a gateway with custom config."""
        config = GatewayConfig(max_retries=5)
        gateway = HRISGateway(config)

        assert gateway.config.max_retries == 5

    def test_register_adapter(self) -> None:
        """Test registering an adapter."""
        gateway = HRISGateway()
        adapter = MockHRISAdapter()

        gateway.register_adapter(adapter)

        assert HRISPlatform.GENERIC_WEBHOOK in gateway.list_adapters()
        assert gateway.get_adapter(HRISPlatform.GENERIC_WEBHOOK) is adapter

    def test_unregister_adapter(self) -> None:
        """Test unregistering an adapter."""
        gateway = HRISGateway()
        adapter = MockHRISAdapter()
        gateway.register_adapter(adapter)

        result = gateway.unregister_adapter(HRISPlatform.GENERIC_WEBHOOK)

        assert result is True
        assert gateway.get_adapter(HRISPlatform.GENERIC_WEBHOOK) is None

    def test_unregister_nonexistent_adapter(self) -> None:
        """Test unregistering a non-existent adapter."""
        gateway = HRISGateway()

        result = gateway.unregister_adapter(HRISPlatform.WORKDAY)

        assert result is False

    def test_register_connection(self) -> None:
        """Test registering a connection."""
        gateway = HRISGateway()
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.WORKDAY,
            created_at=now,
            updated_at=now,
        )

        gateway.register_connection(connection)

        assert gateway.get_connection(tenant_id) is connection

    def test_get_connection_not_found(self) -> None:
        """Test getting a non-existent connection."""
        gateway = HRISGateway()

        assert gateway.get_connection(uuid4()) is None

    def test_update_connection_status(self) -> None:
        """Test updating connection status."""
        gateway = HRISGateway()
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.WORKDAY,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        result = gateway.update_connection_status(
            tenant_id=tenant_id,
            status=HRISConnectionStatus.CONNECTED,
        )

        assert result is True
        assert connection.status == HRISConnectionStatus.CONNECTED

    def test_update_connection_status_with_error(self) -> None:
        """Test updating connection status with error message."""
        gateway = HRISGateway()
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.ADP,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        gateway.update_connection_status(
            tenant_id=tenant_id,
            status=HRISConnectionStatus.ERROR,
            error_message="Connection failed",
        )

        assert connection.status == HRISConnectionStatus.ERROR
        assert connection.last_error_message == "Connection failed"
        assert connection.last_error_at is not None

    def test_update_connection_status_not_found(self) -> None:
        """Test updating status for non-existent connection."""
        gateway = HRISGateway()

        result = gateway.update_connection_status(
            tenant_id=uuid4(),
            status=HRISConnectionStatus.CONNECTED,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_inbound_event_no_connection(self) -> None:
        """Test validation when no connection exists."""
        gateway = HRISGateway()

        result = await gateway.validate_inbound_event(
            tenant_id=uuid4(),
            headers={},
            payload=b"{}",
        )

        assert result.valid is False
        assert "No connection configured" in (result.error or "")

    @pytest.mark.asyncio
    async def test_validate_inbound_event_disabled(self) -> None:
        """Test validation when connection is disabled."""
        gateway = HRISGateway()
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.WORKDAY,
            enabled=False,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        result = await gateway.validate_inbound_event(
            tenant_id=tenant_id,
            headers={},
            payload=b"{}",
        )

        assert result.valid is False
        assert "disabled" in (result.error or "")

    @pytest.mark.asyncio
    async def test_validate_inbound_event_no_adapter(self) -> None:
        """Test validation when no adapter is registered."""
        gateway = HRISGateway()
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.WORKDAY,
            webhook_secret="secret",
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        result = await gateway.validate_inbound_event(
            tenant_id=tenant_id,
            headers={},
            payload=b"{}",
        )

        assert result.valid is False
        assert "No adapter registered" in (result.error or "")

    @pytest.mark.asyncio
    async def test_validate_inbound_event_no_secret(self) -> None:
        """Test validation when webhook secret is not configured."""
        gateway = HRISGateway()
        gateway.register_adapter(MockHRISAdapter())
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.GENERIC_WEBHOOK,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        result = await gateway.validate_inbound_event(
            tenant_id=tenant_id,
            headers={},
            payload=b"{}",
        )

        assert result.valid is False
        assert "secret not configured" in (result.error or "")

    @pytest.mark.asyncio
    async def test_validate_inbound_event_success(self) -> None:
        """Test successful event validation."""
        gateway = HRISGateway()
        gateway.register_adapter(MockHRISAdapter())
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.GENERIC_WEBHOOK,
            webhook_secret="secret123",
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        result = await gateway.validate_inbound_event(
            tenant_id=tenant_id,
            headers={"x-signature": "valid"},
            payload=b"{}",
        )

        assert result.valid is True

    @pytest.mark.asyncio
    async def test_validate_inbound_event_skip_signature(self) -> None:
        """Test validation with signature check disabled."""
        config = GatewayConfig(require_webhook_signature=False)
        gateway = HRISGateway(config)
        gateway.register_adapter(MockHRISAdapter())
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.GENERIC_WEBHOOK,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        result = await gateway.validate_inbound_event(
            tenant_id=tenant_id,
            headers={},
            payload=b"{}",
        )

        assert result.valid is True

    @pytest.mark.asyncio
    async def test_parse_inbound_event_no_connection(self) -> None:
        """Test parsing when no connection exists."""
        gateway = HRISGateway()

        result = await gateway.parse_inbound_event(
            tenant_id=uuid4(),
            event_type="hire.initiated",
            payload={},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_parse_inbound_event_success(self) -> None:
        """Test successful event parsing."""
        gateway = HRISGateway()
        gateway.register_adapter(MockHRISAdapter())
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.GENERIC_WEBHOOK,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        result = await gateway.parse_inbound_event(
            tenant_id=tenant_id,
            event_type="hire.initiated",
            payload={"employee_id": "EMP-123"},
        )

        assert result is not None
        assert result.event_type == HRISEventType.HIRE_INITIATED
        assert result.employee_id == "EMP-123"

    @pytest.mark.asyncio
    async def test_publish_screening_update_no_connection(self) -> None:
        """Test publishing when no connection exists."""
        gateway = HRISGateway()
        update = ScreeningUpdate(
            screening_id=uuid4(),
            status="complete",
            timestamp=datetime.now(),
        )

        result = await gateway.publish_screening_update(
            tenant_id=uuid4(),
            employee_id="EMP-123",
            update=update,
            credentials={},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_publish_screening_update_success(self) -> None:
        """Test successful screening update publishing."""
        gateway = HRISGateway()
        adapter = MockHRISAdapter()
        gateway.register_adapter(adapter)
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.GENERIC_WEBHOOK,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)
        update = ScreeningUpdate(
            screening_id=uuid4(),
            status="complete",
            timestamp=datetime.now(),
        )

        result = await gateway.publish_screening_update(
            tenant_id=tenant_id,
            employee_id="EMP-123",
            update=update,
            credentials={},
        )

        assert result is True
        assert len(adapter.published_updates) == 1
        assert connection.status == HRISConnectionStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_publish_alert_success(self) -> None:
        """Test successful alert publishing."""
        gateway = HRISGateway()
        adapter = MockHRISAdapter()
        gateway.register_adapter(adapter)
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.GENERIC_WEBHOOK,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)
        alert = AlertUpdate(
            alert_id=uuid4(),
            employee_id="EMP-123",
            severity="high",
            title="Test",
            description="Test alert",
            created_at=datetime.now(),
        )

        result = await gateway.publish_alert(
            tenant_id=tenant_id,
            employee_id="EMP-123",
            alert=alert,
            credentials={},
        )

        assert result is True
        assert len(adapter.published_alerts) == 1

    @pytest.mark.asyncio
    async def test_get_employee_success(self) -> None:
        """Test successful employee retrieval."""
        gateway = HRISGateway()
        adapter = MockHRISAdapter()
        employee = EmployeeInfo(
            employee_id="EMP-123",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
        )
        adapter.add_employee(employee)
        gateway.register_adapter(adapter)
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.GENERIC_WEBHOOK,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        result = await gateway.get_employee(
            tenant_id=tenant_id,
            employee_id="EMP-123",
            credentials={},
        )

        assert result is not None
        assert result.first_name == "John"

    @pytest.mark.asyncio
    async def test_test_connection_success(self) -> None:
        """Test successful connection test."""
        gateway = HRISGateway()
        adapter = MockHRISAdapter(connection_status=HRISConnectionStatus.CONNECTED)
        gateway.register_adapter(adapter)
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.GENERIC_WEBHOOK,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        status = await gateway.test_connection(
            tenant_id=tenant_id,
            credentials={},
        )

        assert status == HRISConnectionStatus.CONNECTED
        assert connection.status == HRISConnectionStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_test_connection_no_connection(self) -> None:
        """Test connection test when no connection exists."""
        gateway = HRISGateway()

        status = await gateway.test_connection(
            tenant_id=uuid4(),
            credentials={},
        )

        assert status == HRISConnectionStatus.DISCONNECTED

    def test_reset_rate_limits(self) -> None:
        """Test resetting rate limit counters."""
        gateway = HRISGateway()
        # Manually set some counts
        gateway._event_counts[uuid4()] = 100
        gateway._event_counts[uuid4()] = 50

        gateway.reset_rate_limits()

        assert len(gateway._event_counts) == 0

    def test_get_connection_stats(self) -> None:
        """Test getting connection statistics."""
        gateway = HRISGateway()
        now = datetime.now()

        # Add connections with different statuses
        for status in [
            HRISConnectionStatus.CONNECTED,
            HRISConnectionStatus.CONNECTED,
            HRISConnectionStatus.ERROR,
        ]:
            connection = HRISConnection(
                connection_id=uuid4(),
                tenant_id=uuid4(),
                platform=HRISPlatform.GENERIC_WEBHOOK,
                status=status,
                created_at=now,
                updated_at=now,
            )
            gateway.register_connection(connection)

        stats = gateway.get_connection_stats()

        assert stats[HRISConnectionStatus.CONNECTED] == 2
        assert stats[HRISConnectionStatus.ERROR] == 1


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateHRISGateway:
    """Tests for create_hris_gateway factory function."""

    def test_create_default_gateway(self) -> None:
        """Test creating gateway with defaults."""
        gateway = create_hris_gateway()

        assert gateway is not None
        assert len(gateway.list_adapters()) == 0

    def test_create_gateway_with_config(self) -> None:
        """Test creating gateway with custom config."""
        config = GatewayConfig(max_retries=7)

        gateway = create_hris_gateway(config)

        assert gateway.config.max_retries == 7

    def test_create_gateway_with_mock_adapter(self) -> None:
        """Test creating gateway with mock adapter."""
        gateway = create_hris_gateway(include_mock_adapter=True)

        assert HRISPlatform.GENERIC_WEBHOOK in gateway.list_adapters()


# =============================================================================
# BaseHRISAdapter Tests
# =============================================================================


class TestBaseHRISAdapter:
    """Tests for BaseHRISAdapter abstract class."""

    def test_mock_adapter_is_base_adapter(self) -> None:
        """Test that MockHRISAdapter is a BaseHRISAdapter."""
        adapter = MockHRISAdapter()

        assert isinstance(adapter, BaseHRISAdapter)

    def test_mock_adapter_implements_protocol(self) -> None:
        """Test that MockHRISAdapter implements HRISAdapter protocol."""
        adapter = MockHRISAdapter()

        # Check that adapter has all required methods
        assert hasattr(adapter, "platform_id")
        assert hasattr(adapter, "platform_name")
        assert hasattr(adapter, "validate_webhook")
        assert hasattr(adapter, "parse_event")
        assert hasattr(adapter, "publish_update")
        assert hasattr(adapter, "publish_alert")
        assert hasattr(adapter, "get_employee")
        assert hasattr(adapter, "test_connection")


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiting_blocks_excess_events(self) -> None:
        """Test that rate limiting blocks events exceeding the limit."""
        config = GatewayConfig(max_events_per_minute=10)  # Minimum allowed value
        gateway = HRISGateway(config)
        gateway.register_adapter(MockHRISAdapter())
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.GENERIC_WEBHOOK,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        # Send 10 events (up to limit)
        for i in range(10):
            result = await gateway.parse_inbound_event(
                tenant_id=tenant_id,
                event_type="hire.initiated",
                payload={"employee_id": f"EMP-{i}"},
            )
            assert result is not None, f"Event {i} should succeed"

        # 11th event should be rate limited
        result_limited = await gateway.parse_inbound_event(
            tenant_id=tenant_id,
            event_type="hire.initiated",
            payload={"employee_id": "EMP-limited"},
        )

        assert result_limited is None  # Rate limited

    @pytest.mark.asyncio
    async def test_rate_limit_reset(self) -> None:
        """Test that rate limits reset properly."""
        config = GatewayConfig(max_events_per_minute=10)
        gateway = HRISGateway(config)
        gateway.register_adapter(MockHRISAdapter())
        now = datetime.now()
        tenant_id = uuid4()
        connection = HRISConnection(
            connection_id=uuid4(),
            tenant_id=tenant_id,
            platform=HRISPlatform.GENERIC_WEBHOOK,
            created_at=now,
            updated_at=now,
        )
        gateway.register_connection(connection)

        # Fill up to rate limit
        for i in range(10):
            result = await gateway.parse_inbound_event(
                tenant_id=tenant_id,
                event_type="hire.initiated",
                payload={"employee_id": f"EMP-{i}"},
            )
            assert result is not None

        # Next event is rate limited
        result_limited = await gateway.parse_inbound_event(
            tenant_id=tenant_id,
            event_type="hire.initiated",
            payload={"employee_id": "EMP-limited"},
        )
        assert result_limited is None

        # Reset rate limits
        gateway.reset_rate_limits()

        # Now event should succeed again
        result_after_reset = await gateway.parse_inbound_event(
            tenant_id=tenant_id,
            event_type="hire.initiated",
            payload={"employee_id": "EMP-after-reset"},
        )
        assert result_after_reset is not None
