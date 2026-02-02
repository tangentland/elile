"""HRIS Integration Gateway for bidirectional HRIS platform communication.

This module provides the core infrastructure for:
- Receiving inbound events from HRIS platforms (hire, consent, position change, termination)
- Publishing outbound events to HRIS platforms (screening status, alerts)
- Managing platform-specific adapters
- Webhook signature validation and event parsing
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field


class HRISEventType(str, Enum):
    """Types of events received from HRIS platforms."""

    # Inbound events (HRIS -> Elile)
    HIRE_INITIATED = "hire.initiated"
    CONSENT_GRANTED = "consent.granted"
    POSITION_CHANGED = "position.changed"
    EMPLOYEE_TERMINATED = "employee.terminated"
    REHIRE_INITIATED = "rehire.initiated"

    # Outbound events (Elile -> HRIS)
    SCREENING_STARTED = "screening.started"
    SCREENING_PROGRESS = "screening.progress"
    SCREENING_COMPLETE = "screening.complete"
    REVIEW_REQUIRED = "review.required"
    ALERT_GENERATED = "alert.generated"
    ADVERSE_ACTION_PENDING = "adverse_action.pending"


class HRISPlatform(str, Enum):
    """Supported HRIS platform types."""

    WORKDAY = "workday"
    SAP_SUCCESSFACTORS = "sap_successfactors"
    ORACLE_HCM = "oracle_hcm"
    ADP = "adp"
    BAMBOO_HR = "bamboo_hr"
    GENERIC_WEBHOOK = "generic_webhook"


class HRISConnectionStatus(str, Enum):
    """Connection status for HRIS integrations."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    PENDING = "pending"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass
class HRISEvent:
    """Normalized event from any HRIS platform.

    This is the canonical representation of HRIS events after parsing
    from platform-specific formats.
    """

    event_id: UUID
    event_type: HRISEventType
    tenant_id: UUID
    employee_id: str  # HRIS-specific employee identifier
    platform: HRISPlatform
    received_at: datetime
    event_data: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] | None = field(default=None, repr=False)

    # Optional fields depending on event type
    consent_reference: str | None = None
    position_info: dict[str, Any] | None = None
    screening_id: UUID | None = None

    def is_inbound(self) -> bool:
        """Check if this is an inbound event (HRIS -> Elile)."""
        return self.event_type in {
            HRISEventType.HIRE_INITIATED,
            HRISEventType.CONSENT_GRANTED,
            HRISEventType.POSITION_CHANGED,
            HRISEventType.EMPLOYEE_TERMINATED,
            HRISEventType.REHIRE_INITIATED,
        }

    def is_outbound(self) -> bool:
        """Check if this is an outbound event (Elile -> HRIS)."""
        return not self.is_inbound()


@dataclass
class ScreeningUpdate:
    """Update to send to HRIS about screening status."""

    screening_id: UUID
    status: str
    timestamp: datetime
    progress_percent: int | None = None
    risk_level: str | None = None
    recommendation: str | None = None
    estimated_completion: datetime | None = None
    findings_summary: dict[str, Any] | None = None
    review_reason: str | None = None


@dataclass
class AlertUpdate:
    """Alert to send to HRIS about monitoring findings."""

    alert_id: UUID
    employee_id: str
    severity: str
    title: str
    description: str
    created_at: datetime
    requires_action: bool = False
    action_url: str | None = None


@dataclass
class EmployeeInfo:
    """Employee information retrieved from HRIS."""

    employee_id: str
    first_name: str
    last_name: str
    email: str
    department: str | None = None
    job_title: str | None = None
    hire_date: datetime | None = None
    manager_id: str | None = None
    location: str | None = None
    additional_data: dict[str, Any] = field(default_factory=dict)


class WebhookValidationResult:
    """Result of webhook signature validation."""

    def __init__(self, valid: bool, error: str | None = None) -> None:
        self.valid = valid
        self.error = error

    @classmethod
    def success(cls) -> "WebhookValidationResult":
        """Create a successful validation result."""
        return cls(valid=True)

    @classmethod
    def failure(cls, error: str) -> "WebhookValidationResult":
        """Create a failed validation result."""
        return cls(valid=False, error=error)


class HRISAdapter(Protocol):
    """Protocol for HRIS platform adapters.

    Each HRIS platform (Workday, SAP, ADP, etc.) implements this protocol
    to handle platform-specific webhook formats, API calls, and authentication.
    """

    @property
    def platform_id(self) -> HRISPlatform:
        """Return the platform identifier."""
        ...

    @property
    def platform_name(self) -> str:
        """Return the human-readable platform name."""
        ...

    async def validate_webhook(
        self,
        headers: dict[str, str],
        payload: bytes,
        secret: str,
    ) -> WebhookValidationResult:
        """Validate webhook signature.

        Args:
            headers: HTTP headers from the webhook request
            payload: Raw request body bytes
            secret: Webhook secret for signature verification

        Returns:
            WebhookValidationResult with validation status
        """
        ...

    async def parse_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        tenant_id: UUID,
    ) -> HRISEvent:
        """Parse platform-specific event format to canonical HRISEvent.

        Args:
            event_type: Platform-specific event type string
            payload: Parsed JSON payload
            tenant_id: Tenant ID for this integration

        Returns:
            Normalized HRISEvent
        """
        ...

    async def publish_update(
        self,
        tenant_id: UUID,
        employee_id: str,
        update: ScreeningUpdate,
        credentials: dict[str, Any],
    ) -> bool:
        """Push screening update to HRIS.

        Args:
            tenant_id: Tenant ID for this integration
            employee_id: HRIS employee identifier
            update: Screening status update
            credentials: Platform-specific credentials

        Returns:
            True if update was successfully delivered
        """
        ...

    async def publish_alert(
        self,
        tenant_id: UUID,
        employee_id: str,
        alert: AlertUpdate,
        credentials: dict[str, Any],
    ) -> bool:
        """Push monitoring alert to HRIS.

        Args:
            tenant_id: Tenant ID for this integration
            employee_id: HRIS employee identifier
            alert: Alert to send
            credentials: Platform-specific credentials

        Returns:
            True if alert was successfully delivered
        """
        ...

    async def get_employee(
        self,
        tenant_id: UUID,
        employee_id: str,
        credentials: dict[str, Any],
    ) -> EmployeeInfo | None:
        """Fetch employee details from HRIS.

        Args:
            tenant_id: Tenant ID for this integration
            employee_id: HRIS employee identifier
            credentials: Platform-specific credentials

        Returns:
            EmployeeInfo if found, None otherwise
        """
        ...

    async def test_connection(
        self,
        credentials: dict[str, Any],
    ) -> HRISConnectionStatus:
        """Test the connection to the HRIS platform.

        Args:
            credentials: Platform-specific credentials

        Returns:
            Connection status
        """
        ...


class GatewayConfig(BaseModel):
    """Configuration for the HRIS Integration Gateway."""

    # Retry settings
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_backoff_seconds: list[int] = Field(default=[30, 300, 3600])  # 30s, 5m, 1h

    # Timeout settings
    webhook_timeout_seconds: int = Field(default=30, ge=5, le=120)
    api_timeout_seconds: int = Field(default=60, ge=10, le=300)

    # Rate limiting
    max_events_per_minute: int = Field(default=1000, ge=10)
    max_outbound_per_minute: int = Field(default=100, ge=10)

    # Validation
    require_webhook_signature: bool = Field(default=True)
    allow_unknown_event_types: bool = Field(default=False)

    # Event history
    event_retention_days: int = Field(default=90, ge=7, le=365)

    def get_retry_delay(self, attempt: int) -> timedelta:
        """Get retry delay for a given attempt number."""
        if attempt < 0:
            return timedelta(seconds=0)
        index = min(attempt, len(self.retry_backoff_seconds) - 1)
        return timedelta(seconds=self.retry_backoff_seconds[index])


class HRISConnection(BaseModel):
    """HRIS connection configuration for a tenant."""

    connection_id: UUID
    tenant_id: UUID
    platform: HRISPlatform
    status: HRISConnectionStatus = HRISConnectionStatus.PENDING
    enabled: bool = True

    # Webhook configuration
    webhook_secret: str | None = None
    webhook_url: str | None = None  # For outbound webhooks

    # API credentials (encrypted reference)
    credentials_ref: str | None = None

    # Platform-specific settings
    platform_settings: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_sync_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None


class HRISGateway:
    """Core gateway for HRIS platform integration.

    The gateway manages:
    - Registration and lookup of platform-specific adapters
    - Inbound event validation and routing
    - Outbound event publishing with retry logic
    - Connection health monitoring
    """

    def __init__(self, config: GatewayConfig | None = None) -> None:
        """Initialize the HRIS gateway.

        Args:
            config: Gateway configuration. Uses defaults if not provided.
        """
        self._config = config or GatewayConfig()
        self._adapters: dict[HRISPlatform, HRISAdapter] = {}
        self._connections: dict[UUID, HRISConnection] = {}  # tenant_id -> connection
        self._event_counts: dict[UUID, int] = {}  # tenant_id -> events this minute

    @property
    def config(self) -> GatewayConfig:
        """Get the gateway configuration."""
        return self._config

    def register_adapter(self, adapter: HRISAdapter) -> None:
        """Register a platform adapter.

        Args:
            adapter: HRISAdapter implementation for a specific platform
        """
        self._adapters[adapter.platform_id] = adapter

    def unregister_adapter(self, platform: HRISPlatform) -> bool:
        """Unregister a platform adapter.

        Args:
            platform: Platform to unregister

        Returns:
            True if adapter was found and removed
        """
        if platform in self._adapters:
            del self._adapters[platform]
            return True
        return False

    def get_adapter(self, platform: HRISPlatform) -> HRISAdapter | None:
        """Get the adapter for a platform.

        Args:
            platform: Platform to get adapter for

        Returns:
            HRISAdapter if registered, None otherwise
        """
        return self._adapters.get(platform)

    def list_adapters(self) -> list[HRISPlatform]:
        """List all registered platform adapters.

        Returns:
            List of registered platform types
        """
        return list(self._adapters.keys())

    def register_connection(self, connection: HRISConnection) -> None:
        """Register an HRIS connection for a tenant.

        Args:
            connection: Connection configuration
        """
        self._connections[connection.tenant_id] = connection

    def get_connection(self, tenant_id: UUID) -> HRISConnection | None:
        """Get the HRIS connection for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            HRISConnection if found, None otherwise
        """
        return self._connections.get(tenant_id)

    def update_connection_status(
        self,
        tenant_id: UUID,
        status: HRISConnectionStatus,
        error_message: str | None = None,
    ) -> bool:
        """Update the connection status for a tenant.

        Args:
            tenant_id: Tenant ID
            status: New connection status
            error_message: Optional error message if status is ERROR

        Returns:
            True if connection was found and updated
        """
        connection = self._connections.get(tenant_id)
        if not connection:
            return False

        connection.status = status
        connection.updated_at = datetime.now()

        if error_message:
            connection.last_error_at = datetime.now()
            connection.last_error_message = error_message
        elif status == HRISConnectionStatus.CONNECTED:
            connection.last_sync_at = datetime.now()

        return True

    async def validate_inbound_event(
        self,
        tenant_id: UUID,
        headers: dict[str, str],
        payload: bytes,
    ) -> WebhookValidationResult:
        """Validate an inbound webhook event.

        Args:
            tenant_id: Tenant ID for this request
            headers: HTTP headers from the request
            payload: Raw request body

        Returns:
            Validation result
        """
        connection = self.get_connection(tenant_id)
        if not connection:
            return WebhookValidationResult.failure("No connection configured for tenant")

        if not connection.enabled:
            return WebhookValidationResult.failure("Connection is disabled")

        adapter = self.get_adapter(connection.platform)
        if not adapter:
            return WebhookValidationResult.failure(
                f"No adapter registered for platform: {connection.platform.value}"
            )

        if self._config.require_webhook_signature:
            if not connection.webhook_secret:
                return WebhookValidationResult.failure("Webhook secret not configured")

            return await adapter.validate_webhook(
                headers=headers,
                payload=payload,
                secret=connection.webhook_secret,
            )

        return WebhookValidationResult.success()

    async def parse_inbound_event(
        self,
        tenant_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> HRISEvent | None:
        """Parse an inbound webhook event.

        Args:
            tenant_id: Tenant ID for this request
            event_type: Platform-specific event type
            payload: Parsed JSON payload

        Returns:
            Parsed HRISEvent or None if parsing failed
        """
        connection = self.get_connection(tenant_id)
        if not connection:
            return None

        adapter = self.get_adapter(connection.platform)
        if not adapter:
            return None

        # Check rate limiting
        current_count = self._event_counts.get(tenant_id, 0)
        if current_count >= self._config.max_events_per_minute:
            return None  # Rate limited

        self._event_counts[tenant_id] = current_count + 1

        return await adapter.parse_event(
            event_type=event_type,
            payload=payload,
            tenant_id=tenant_id,
        )

    async def publish_screening_update(
        self,
        tenant_id: UUID,
        employee_id: str,
        update: ScreeningUpdate,
        credentials: dict[str, Any],
    ) -> bool:
        """Publish a screening update to the HRIS.

        Args:
            tenant_id: Tenant ID
            employee_id: HRIS employee identifier
            update: Screening status update
            credentials: Platform credentials

        Returns:
            True if update was successfully published
        """
        connection = self.get_connection(tenant_id)
        if not connection or not connection.enabled:
            return False

        adapter = self.get_adapter(connection.platform)
        if not adapter:
            return False

        # Retry logic
        for attempt in range(self._config.max_retries + 1):
            try:
                result = await adapter.publish_update(
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    update=update,
                    credentials=credentials,
                )
                if result:
                    self.update_connection_status(tenant_id, HRISConnectionStatus.CONNECTED)
                    return True
            except Exception:
                if attempt < self._config.max_retries:
                    # Would normally await delay here
                    continue
                self.update_connection_status(
                    tenant_id,
                    HRISConnectionStatus.ERROR,
                    "Failed to publish update after retries",
                )
                return False

        return False

    async def publish_alert(
        self,
        tenant_id: UUID,
        employee_id: str,
        alert: AlertUpdate,
        credentials: dict[str, Any],
    ) -> bool:
        """Publish a monitoring alert to the HRIS.

        Args:
            tenant_id: Tenant ID
            employee_id: HRIS employee identifier
            alert: Alert to send
            credentials: Platform credentials

        Returns:
            True if alert was successfully published
        """
        connection = self.get_connection(tenant_id)
        if not connection or not connection.enabled:
            return False

        adapter = self.get_adapter(connection.platform)
        if not adapter:
            return False

        # Retry logic
        for attempt in range(self._config.max_retries + 1):
            try:
                result = await adapter.publish_alert(
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    alert=alert,
                    credentials=credentials,
                )
                if result:
                    self.update_connection_status(tenant_id, HRISConnectionStatus.CONNECTED)
                    return True
            except Exception:
                if attempt < self._config.max_retries:
                    continue
                self.update_connection_status(
                    tenant_id,
                    HRISConnectionStatus.ERROR,
                    "Failed to publish alert after retries",
                )
                return False

        return False

    async def get_employee(
        self,
        tenant_id: UUID,
        employee_id: str,
        credentials: dict[str, Any],
    ) -> EmployeeInfo | None:
        """Fetch employee details from the HRIS.

        Args:
            tenant_id: Tenant ID
            employee_id: HRIS employee identifier
            credentials: Platform credentials

        Returns:
            EmployeeInfo if found, None otherwise
        """
        connection = self.get_connection(tenant_id)
        if not connection or not connection.enabled:
            return None

        adapter = self.get_adapter(connection.platform)
        if not adapter:
            return None

        return await adapter.get_employee(
            tenant_id=tenant_id,
            employee_id=employee_id,
            credentials=credentials,
        )

    async def test_connection(
        self,
        tenant_id: UUID,
        credentials: dict[str, Any],
    ) -> HRISConnectionStatus:
        """Test the HRIS connection for a tenant.

        Args:
            tenant_id: Tenant ID
            credentials: Platform credentials

        Returns:
            Connection status
        """
        connection = self.get_connection(tenant_id)
        if not connection:
            return HRISConnectionStatus.DISCONNECTED

        adapter = self.get_adapter(connection.platform)
        if not adapter:
            return HRISConnectionStatus.ERROR

        status = await adapter.test_connection(credentials)
        self.update_connection_status(tenant_id, status)
        return status

    def reset_rate_limits(self) -> None:
        """Reset per-minute rate limit counters.

        This should be called by a scheduler every minute.
        """
        self._event_counts.clear()

    def get_connection_stats(self) -> dict[HRISConnectionStatus, int]:
        """Get connection status statistics.

        Returns:
            Dictionary of status -> count
        """
        stats: dict[HRISConnectionStatus, int] = {}
        for connection in self._connections.values():
            stats[connection.status] = stats.get(connection.status, 0) + 1
        return stats


class BaseHRISAdapter(ABC):
    """Abstract base class for HRIS adapters.

    Provides common functionality and enforces implementation of
    platform-specific methods.
    """

    @property
    @abstractmethod
    def platform_id(self) -> HRISPlatform:
        """Return the platform identifier."""
        ...

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the human-readable platform name."""
        ...

    @abstractmethod
    async def validate_webhook(
        self,
        headers: dict[str, str],
        payload: bytes,
        secret: str,
    ) -> WebhookValidationResult:
        """Validate webhook signature."""
        ...

    @abstractmethod
    async def parse_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        tenant_id: UUID,
    ) -> HRISEvent:
        """Parse platform-specific event format to canonical HRISEvent."""
        ...

    @abstractmethod
    async def publish_update(
        self,
        tenant_id: UUID,
        employee_id: str,
        update: ScreeningUpdate,
        credentials: dict[str, Any],
    ) -> bool:
        """Push screening update to HRIS."""
        ...

    @abstractmethod
    async def publish_alert(
        self,
        tenant_id: UUID,
        employee_id: str,
        alert: AlertUpdate,
        credentials: dict[str, Any],
    ) -> bool:
        """Push monitoring alert to HRIS."""
        ...

    @abstractmethod
    async def get_employee(
        self,
        tenant_id: UUID,
        employee_id: str,
        credentials: dict[str, Any],
    ) -> EmployeeInfo | None:
        """Fetch employee details from HRIS."""
        ...

    @abstractmethod
    async def test_connection(
        self,
        credentials: dict[str, Any],
    ) -> HRISConnectionStatus:
        """Test the connection to the HRIS platform."""
        ...


class MockHRISAdapter(BaseHRISAdapter):
    """Mock HRIS adapter for testing.

    This adapter simulates HRIS platform behavior for unit testing
    and development without requiring actual HRIS connections.
    """

    def __init__(
        self,
        platform: HRISPlatform = HRISPlatform.GENERIC_WEBHOOK,
        name: str = "Mock HRIS",
        *,
        should_fail_validation: bool = False,
        should_fail_publish: bool = False,
        connection_status: HRISConnectionStatus = HRISConnectionStatus.CONNECTED,
    ) -> None:
        self._platform = platform
        self._name = name
        self._should_fail_validation = should_fail_validation
        self._should_fail_publish = should_fail_publish
        self._connection_status = connection_status
        self._employees: dict[str, EmployeeInfo] = {}
        self._published_updates: list[ScreeningUpdate] = []
        self._published_alerts: list[AlertUpdate] = []

    @property
    def platform_id(self) -> HRISPlatform:
        return self._platform

    @property
    def platform_name(self) -> str:
        return self._name

    @property
    def published_updates(self) -> list[ScreeningUpdate]:
        """Get all published updates (for testing)."""
        return self._published_updates

    @property
    def published_alerts(self) -> list[AlertUpdate]:
        """Get all published alerts (for testing)."""
        return self._published_alerts

    def add_employee(self, employee: EmployeeInfo) -> None:
        """Add a mock employee (for testing)."""
        self._employees[employee.employee_id] = employee

    async def validate_webhook(
        self,
        headers: dict[str, str],
        payload: bytes,  # noqa: ARG002
        secret: str,  # noqa: ARG002
    ) -> WebhookValidationResult:
        if self._should_fail_validation:
            return WebhookValidationResult.failure("Mock validation failure")

        # Simple mock validation: check for presence of signature header
        if "x-signature" in headers or "x-webhook-signature" in headers:
            return WebhookValidationResult.success()

        # Also succeed if no signature required (testing mode)
        return WebhookValidationResult.success()

    async def parse_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        tenant_id: UUID,
    ) -> HRISEvent:
        from uuid import uuid4

        # Map common event type strings to our enum
        event_type_map = {
            "hire.initiated": HRISEventType.HIRE_INITIATED,
            "consent.granted": HRISEventType.CONSENT_GRANTED,
            "position.changed": HRISEventType.POSITION_CHANGED,
            "employee.terminated": HRISEventType.EMPLOYEE_TERMINATED,
            "rehire.initiated": HRISEventType.REHIRE_INITIATED,
        }

        mapped_type = event_type_map.get(event_type, HRISEventType.HIRE_INITIATED)

        return HRISEvent(
            event_id=uuid4(),
            event_type=mapped_type,
            tenant_id=tenant_id,
            employee_id=payload.get("employee_id", "UNKNOWN"),
            platform=self._platform,
            received_at=datetime.now(),
            event_data=payload,
            raw_payload=payload,
            consent_reference=payload.get("consent_reference"),
            position_info=payload.get("position"),
        )

    async def publish_update(
        self,
        tenant_id: UUID,  # noqa: ARG002
        employee_id: str,  # noqa: ARG002
        update: ScreeningUpdate,
        credentials: dict[str, Any],  # noqa: ARG002
    ) -> bool:
        if self._should_fail_publish:
            return False
        self._published_updates.append(update)
        return True

    async def publish_alert(
        self,
        tenant_id: UUID,  # noqa: ARG002
        employee_id: str,  # noqa: ARG002
        alert: AlertUpdate,
        credentials: dict[str, Any],  # noqa: ARG002
    ) -> bool:
        if self._should_fail_publish:
            return False
        self._published_alerts.append(alert)
        return True

    async def get_employee(
        self,
        tenant_id: UUID,  # noqa: ARG002
        employee_id: str,
        credentials: dict[str, Any],  # noqa: ARG002
    ) -> EmployeeInfo | None:
        return self._employees.get(employee_id)

    async def test_connection(
        self,
        credentials: dict[str, Any],  # noqa: ARG002
    ) -> HRISConnectionStatus:
        return self._connection_status


def create_hris_gateway(
    config: GatewayConfig | None = None,
    *,
    include_mock_adapter: bool = False,
) -> HRISGateway:
    """Factory function to create an HRIS gateway.

    Args:
        config: Gateway configuration
        include_mock_adapter: If True, registers a MockHRISAdapter for testing

    Returns:
        Configured HRISGateway instance
    """
    gateway = HRISGateway(config)

    if include_mock_adapter:
        gateway.register_adapter(MockHRISAdapter())

    return gateway
