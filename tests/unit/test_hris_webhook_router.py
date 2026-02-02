"""Unit tests for HRIS Webhook API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from elile.api.app import create_app
from elile.api.routers.v1.hris_webhook import get_hris_gateway, reset_gateway
from elile.hris import (
    HRISConnection,
    HRISConnectionStatus,
    HRISGateway,
    HRISPlatform,
    MockHRISAdapter,
    WebhookValidationResult,
    create_hris_gateway,
)


@pytest.fixture
def tenant_id() -> UUID:
    """Generate a test tenant ID."""
    return uuid4()


@pytest.fixture
def gateway(tenant_id: UUID) -> HRISGateway:
    """Create a test HRIS gateway with mock adapter."""
    gateway = create_hris_gateway(include_mock_adapter=True)

    # Register a connection for the test tenant
    connection = HRISConnection(
        connection_id=uuid4(),
        tenant_id=tenant_id,
        platform=HRISPlatform.GENERIC_WEBHOOK,
        status=HRISConnectionStatus.CONNECTED,
        enabled=True,
        webhook_secret="test_secret_123",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    gateway.register_connection(connection)

    return gateway


@pytest.fixture
def client(gateway: HRISGateway) -> TestClient:
    """Create a test client with mocked gateway."""
    reset_gateway()  # Reset any existing gateway

    app = create_app()

    # Override the gateway dependency
    def override_gateway() -> HRISGateway:
        return gateway

    app.dependency_overrides[get_hris_gateway] = override_gateway

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    # Clean up
    app.dependency_overrides.clear()
    reset_gateway()


class TestReceiveWebhook:
    """Tests for POST /v1/hris/webhooks/{tenant_id}."""

    def test_receive_webhook_success(self, client: TestClient, tenant_id: UUID) -> None:
        """Test successful webhook receipt."""
        payload = {
            "type": "hire.initiated",
            "employee_id": "EMP-001",
            "data": {"name": "John Doe"},
        }

        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            json=payload,
            headers={
                "x-signature": "valid_signature",
                "content-type": "application/json",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Event processor returns "processed" for successfully processed events
        assert data["status"] == "processed"
        assert "event_id" in data
        assert "timestamp" in data
        assert "processing_result" in data
        # Message includes the processing action
        assert "screening_initiated" in data["message"]

    def test_receive_webhook_with_event_type_header(
        self, client: TestClient, tenant_id: UUID
    ) -> None:
        """Test webhook with event type in header."""
        payload = {
            "employee_id": "EMP-002",
            "data": {"name": "Jane Doe"},
        }

        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            json=payload,
            headers={
                "x-signature": "valid_signature",
                "x-event-type": "consent.granted",
                "content-type": "application/json",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # consent.granted without pending screening is skipped
        assert data["status"] == "received"
        assert "no action required" in data["message"].lower()

    def test_receive_webhook_unknown_tenant(self, client: TestClient) -> None:
        """Test webhook for unknown tenant returns 404."""
        unknown_tenant_id = uuid4()
        payload = {"type": "hire.initiated", "employee_id": "EMP-001"}

        response = client.post(
            f"/v1/hris/webhooks/{unknown_tenant_id}",
            json=payload,
            headers={"x-signature": "valid_signature"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()["detail"]
        assert data["error_code"] == "unknown_tenant"

    def test_receive_webhook_disabled_connection(
        self, client: TestClient, gateway: HRISGateway, tenant_id: UUID
    ) -> None:
        """Test webhook for disabled connection returns 404."""
        # Disable the connection
        connection = gateway.get_connection(tenant_id)
        connection.enabled = False

        payload = {"type": "hire.initiated", "employee_id": "EMP-001"}

        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            json=payload,
            headers={"x-signature": "valid_signature"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()["detail"]
        assert data["error_code"] == "connection_disabled"

    def test_receive_webhook_missing_event_type(
        self, client: TestClient, tenant_id: UUID
    ) -> None:
        """Test webhook without event type returns 400."""
        payload = {
            "employee_id": "EMP-001",
            "data": {"name": "John Doe"},
        }

        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            json=payload,
            headers={"x-signature": "valid_signature"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()["detail"]
        assert data["error_code"] == "unknown_event_type"

    def test_receive_webhook_invalid_json(
        self, client: TestClient, tenant_id: UUID
    ) -> None:
        """Test webhook with invalid JSON returns 400."""
        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            content=b"not valid json",
            headers={
                "x-signature": "valid_signature",
                "content-type": "application/json",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()["detail"]
        assert data["error_code"] == "invalid_payload"

    def test_receive_webhook_invalid_signature(
        self, client: TestClient, gateway: HRISGateway, tenant_id: UUID
    ) -> None:
        """Test webhook with invalid signature returns 401."""
        # Create a mock adapter that fails validation
        mock_adapter = MockHRISAdapter(should_fail_validation=True)
        gateway.register_adapter(mock_adapter)

        payload = {"type": "hire.initiated", "employee_id": "EMP-001"}

        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            json=payload,
            headers={"x-signature": "invalid_signature"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()["detail"]
        assert data["error_code"] == "invalid_signature"

    def test_receive_webhook_rate_limited(
        self, client: TestClient, gateway: HRISGateway, tenant_id: UUID
    ) -> None:
        """Test webhook rate limiting returns 429."""
        # Fill up the rate limit counter
        gateway._event_counts[tenant_id] = gateway.config.max_events_per_minute

        payload = {"type": "hire.initiated", "employee_id": "EMP-001"}

        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            json=payload,
            headers={"x-signature": "valid_signature"},
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        data = response.json()["detail"]
        assert data["error_code"] == "rate_limited"


class TestTestWebhook:
    """Tests for POST /v1/hris/webhooks/{tenant_id}/test."""

    def test_test_webhook_success(self, client: TestClient, tenant_id: UUID) -> None:
        """Test successful webhook connectivity test."""
        response = client.post(f"/v1/hris/webhooks/{tenant_id}/test")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert data["tenant_id"] == str(tenant_id)
        assert data["platform"] == "generic_webhook"
        assert data["connection_status"] == "connected"

    def test_test_webhook_with_echo(self, client: TestClient, tenant_id: UUID) -> None:
        """Test webhook test with echo message."""
        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}/test",
            json={"echo_message": "Hello, HRIS!"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["echo_message"] == "Hello, HRIS!"

    def test_test_webhook_unknown_tenant(self, client: TestClient) -> None:
        """Test webhook test for unknown tenant returns 404."""
        unknown_tenant_id = uuid4()

        response = client.post(f"/v1/hris/webhooks/{unknown_tenant_id}/test")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()["detail"]
        assert data["error_code"] == "unknown_tenant"


class TestGetWebhookStatus:
    """Tests for GET /v1/hris/webhooks/{tenant_id}/status."""

    def test_get_status_success(self, client: TestClient, tenant_id: UUID) -> None:
        """Test successful status retrieval."""
        response = client.get(f"/v1/hris/webhooks/{tenant_id}/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["tenant_id"] == str(tenant_id)
        assert data["platform"] == "generic_webhook"
        assert data["connection_status"] == "connected"
        assert data["enabled"] is True
        assert data["webhook_configured"] is True

    def test_get_status_unknown_tenant(self, client: TestClient) -> None:
        """Test status for unknown tenant returns 404."""
        unknown_tenant_id = uuid4()

        response = client.get(f"/v1/hris/webhooks/{unknown_tenant_id}/status")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()["detail"]
        assert data["error_code"] == "unknown_tenant"

    def test_get_status_with_error(
        self, client: TestClient, gateway: HRISGateway, tenant_id: UUID
    ) -> None:
        """Test status shows error information."""
        # Set an error on the connection
        gateway.update_connection_status(
            tenant_id=tenant_id,
            status=HRISConnectionStatus.ERROR,
            error_message="Connection timeout",
        )

        response = client.get(f"/v1/hris/webhooks/{tenant_id}/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["connection_status"] == "error"
        assert data["last_error_message"] == "Connection timeout"
        assert data["last_error_at"] is not None


class TestWebhookEventTypes:
    """Tests for different HRIS event types."""

    @pytest.mark.parametrize(
        "event_type",
        [
            "hire.initiated",
            "consent.granted",
            "position.changed",
            "employee.terminated",
            "rehire.initiated",
        ],
    )
    def test_all_event_types(
        self, client: TestClient, tenant_id: UUID, event_type: str
    ) -> None:
        """Test all supported event types are handled."""
        payload = {
            "type": event_type,
            "employee_id": "EMP-001",
            "data": {"timestamp": "2026-01-30T12:00:00Z"},
        }

        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            json=payload,
            headers={"x-signature": "valid_signature"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Event processor returns different statuses based on event type:
        # - hire.initiated and rehire.initiated: "processed" (creates pending screening)
        # - Others without subject mapping or pending screening: "received"
        assert data["status"] in ["received", "processed"]

    @pytest.mark.parametrize(
        "header_name",
        [
            "x-event-type",
            "x-webhook-event-type",
        ],
    )
    def test_event_type_headers(
        self, client: TestClient, tenant_id: UUID, header_name: str
    ) -> None:
        """Test event type detection from various headers."""
        payload = {"employee_id": "EMP-001"}

        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            json=payload,
            headers={
                "x-signature": "valid_signature",
                header_name: "hire.initiated",
            },
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize(
        "payload_field",
        [
            "type",
            "event_type",
            "eventType",
        ],
    )
    def test_event_type_payload_fields(
        self, client: TestClient, tenant_id: UUID, payload_field: str
    ) -> None:
        """Test event type detection from various payload fields."""
        payload = {
            payload_field: "hire.initiated",
            "employee_id": "EMP-001",
        }

        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            json=payload,
            headers={"x-signature": "valid_signature"},
        )

        assert response.status_code == status.HTTP_200_OK


class TestWebhookSignatureValidation:
    """Tests for webhook signature validation."""

    def test_signature_in_x_signature_header(
        self, client: TestClient, tenant_id: UUID
    ) -> None:
        """Test signature validation with x-signature header."""
        payload = {"type": "hire.initiated", "employee_id": "EMP-001"}

        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            json=payload,
            headers={"x-signature": "valid_signature"},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_signature_in_x_webhook_signature_header(
        self, client: TestClient, tenant_id: UUID
    ) -> None:
        """Test signature validation with x-webhook-signature header."""
        payload = {"type": "hire.initiated", "employee_id": "EMP-001"}

        response = client.post(
            f"/v1/hris/webhooks/{tenant_id}",
            json=payload,
            headers={"x-webhook-signature": "valid_signature"},
        )

        assert response.status_code == status.HTTP_200_OK
