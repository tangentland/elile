"""HRIS Webhook API schemas.

This module defines request and response schemas for the HRIS webhook endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WebhookStatus(str, Enum):
    """Status of webhook processing."""

    RECEIVED = "received"
    QUEUED = "queued"
    PROCESSED = "processed"


class WebhookResponse(BaseModel):
    """Response for successful webhook receipt."""

    status: WebhookStatus = Field(description="Processing status of the webhook")
    event_id: UUID = Field(description="Unique identifier for this event")
    timestamp: datetime = Field(description="Time the event was received")
    message: str | None = Field(default=None, description="Optional status message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "received",
                "event_id": "01234567-89ab-cdef-0123-456789abcdef",
                "timestamp": "2026-01-30T12:00:00Z",
                "message": None,
            }
        }
    }


class WebhookErrorResponse(BaseModel):
    """Error response for webhook failures."""

    error_code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")
    request_id: str = Field(description="Request ID for troubleshooting")
    timestamp: datetime = Field(description="Time of the error")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error_code": "INVALID_SIGNATURE",
                "message": "Webhook signature validation failed",
                "request_id": "req_abc123",
                "timestamp": "2026-01-30T12:00:00Z",
            }
        }
    }


class WebhookErrorCode(str, Enum):
    """Error codes for webhook failures."""

    INVALID_SIGNATURE = "invalid_signature"
    MISSING_SIGNATURE = "missing_signature"
    INVALID_PAYLOAD = "invalid_payload"
    UNKNOWN_TENANT = "unknown_tenant"
    UNKNOWN_EVENT_TYPE = "unknown_event_type"
    RATE_LIMITED = "rate_limited"
    CONNECTION_DISABLED = "connection_disabled"
    NO_ADAPTER = "no_adapter"
    INTERNAL_ERROR = "internal_error"


class WebhookTestRequest(BaseModel):
    """Request body for webhook test endpoint."""

    echo_message: str | None = Field(
        default=None,
        description="Optional message to echo back",
        max_length=256,
    )


class WebhookTestResponse(BaseModel):
    """Response for webhook test endpoint."""

    status: Literal["ok"] = Field(default="ok", description="Connection status")
    tenant_id: UUID = Field(description="Tenant ID")
    platform: str = Field(description="Connected HRIS platform")
    connection_status: str = Field(description="Current connection status")
    echo_message: str | None = Field(default=None, description="Echoed message")
    timestamp: datetime = Field(description="Time of the test")


class WebhookConnectionStatus(BaseModel):
    """Response for webhook connection status endpoint."""

    tenant_id: UUID = Field(description="Tenant ID")
    platform: str = Field(description="HRIS platform type")
    connection_status: str = Field(description="Current connection status")
    enabled: bool = Field(description="Whether the connection is enabled")
    webhook_configured: bool = Field(description="Whether webhook secret is configured")
    last_sync_at: datetime | None = Field(default=None, description="Last successful sync")
    last_error_at: datetime | None = Field(default=None, description="Last error time")
    last_error_message: str | None = Field(default=None, description="Last error message")


class EventSummary(BaseModel):
    """Summary of a received event."""

    event_id: UUID
    event_type: str
    employee_id: str
    received_at: datetime
    platform: str


class WebhookEvent(BaseModel):
    """Parsed webhook event for API response."""

    event_id: UUID = Field(description="Unique event identifier")
    event_type: str = Field(description="Type of HRIS event")
    tenant_id: UUID = Field(description="Tenant that owns this event")
    employee_id: str = Field(description="HRIS employee identifier")
    platform: str = Field(description="Source HRIS platform")
    received_at: datetime = Field(description="When the event was received")
    event_data: dict[str, Any] = Field(default_factory=dict, description="Event payload data")
    consent_reference: str | None = Field(
        default=None, description="Consent reference if applicable"
    )
