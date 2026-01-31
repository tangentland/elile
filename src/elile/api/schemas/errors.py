"""Error response schemas for API."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""

    # Authentication & Authorization
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"

    # Tenant errors
    TENANT_NOT_FOUND = "tenant_not_found"
    TENANT_INACTIVE = "tenant_inactive"
    TENANT_ACCESS_DENIED = "tenant_access_denied"

    # Request errors
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    VALIDATION_ERROR = "validation_error"

    # Compliance errors
    COMPLIANCE_BLOCKED = "compliance_blocked"
    CONSENT_MISSING = "consent_missing"
    CONSENT_EXPIRED = "consent_expired"
    CONSENT_SCOPE_ERROR = "consent_scope_error"

    # Resource errors
    BUDGET_EXCEEDED = "budget_exceeded"
    RATE_LIMITED = "rate_limited"

    # Provider errors
    PROVIDER_ERROR = "provider_error"
    PROVIDER_UNAVAILABLE = "provider_unavailable"

    # System errors
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"


class APIError(BaseModel):
    """Standardized API error response format.

    All API errors return this format for consistency.
    """

    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional error context"
    )
    request_id: str = Field(..., description="Request ID for tracing (UUIDv7)")
    timestamp: datetime = Field(..., description="When the error occurred")

    model_config = {"json_schema_extra": {"example": {
        "error_code": "not_found",
        "message": "Tenant not found: 01234567-89ab-cdef-0123-456789abcdef",
        "details": {"tenant_id": "01234567-89ab-cdef-0123-456789abcdef"},
        "request_id": "019478f2-1234-7000-8000-abcdef123456",
        "timestamp": "2026-01-30T12:00:00Z",
    }}}
