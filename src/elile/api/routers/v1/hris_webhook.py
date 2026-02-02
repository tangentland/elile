"""HRIS Webhook API endpoints.

This module provides REST API endpoints for receiving HRIS webhooks:
- POST /v1/hris/webhooks/{tenant_id} - Receive webhook from HRIS platform
- POST /v1/hris/webhooks/{tenant_id}/test - Test webhook connectivity
- GET /v1/hris/webhooks/{tenant_id}/status - Check connection status
"""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from elile.api.schemas.hris_webhook import (
    WebhookConnectionStatus,
    WebhookErrorCode,
    WebhookResponse,
    WebhookStatus,
    WebhookTestRequest,
    WebhookTestResponse,
)
from elile.hris import (
    HRISGateway,
    create_hris_gateway,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/hris/webhooks", tags=["hris-webhooks"])


# =============================================================================
# Dependencies
# =============================================================================


# Module-level gateway singleton
_gateway: HRISGateway | None = None


def get_hris_gateway() -> HRISGateway:
    """Get the HRIS gateway instance.

    Returns a singleton gateway instance. In production, this would be
    properly initialized with adapters during app startup.
    """
    global _gateway
    if _gateway is None:
        _gateway = create_hris_gateway(include_mock_adapter=True)
    return _gateway


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/{tenant_id}",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive HRIS webhook",
    description="""
    Receive and process a webhook from an HRIS platform.

    The webhook signature is validated using the configured secret for the tenant.
    Event types include:
    - hire.initiated: New hire process started
    - consent.granted: Subject has consented to screening
    - position.changed: Employee position has changed
    - employee.terminated: Employee has been terminated
    - rehire.initiated: Former employee being rehired

    **Headers:**
    - X-Webhook-Signature or X-Signature: HMAC signature of the payload
    - X-Event-Type: Optional event type hint
    - Content-Type: application/json
    """,
    responses={
        200: {"description": "Webhook received and processed"},
        400: {"description": "Invalid payload format"},
        401: {"description": "Invalid or missing signature"},
        404: {"description": "Unknown tenant or no connection configured"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def receive_webhook(
    tenant_id: UUID,
    request: Request,
    gateway: Annotated[HRISGateway, Depends(get_hris_gateway)],
) -> WebhookResponse:
    """Receive and process an HRIS webhook.

    This endpoint validates the webhook signature, parses the event payload,
    and queues it for processing.

    Args:
        tenant_id: The tenant ID for this webhook.
        request: The incoming FastAPI request.
        gateway: HRIS gateway for validation and parsing.

    Returns:
        WebhookResponse confirming receipt.

    Raises:
        HTTPException: On validation or processing errors.
    """
    request_id = request.headers.get("x-request-id", "unknown")

    logger.info(
        "Receiving HRIS webhook",
        tenant_id=str(tenant_id),
        request_id=request_id,
    )

    # 1. Get connection for tenant
    connection = gateway.get_connection(tenant_id)
    if connection is None:
        logger.warning(
            "Webhook received for unknown tenant",
            tenant_id=str(tenant_id),
            request_id=request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": WebhookErrorCode.UNKNOWN_TENANT.value,
                "message": f"No HRIS connection configured for tenant: {tenant_id}",
                "request_id": request_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    if not connection.enabled:
        logger.warning(
            "Webhook received for disabled connection",
            tenant_id=str(tenant_id),
            request_id=request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": WebhookErrorCode.CONNECTION_DISABLED.value,
                "message": "HRIS connection is disabled for this tenant",
                "request_id": request_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    # 2. Get raw body for signature validation
    try:
        raw_body = await request.body()
    except Exception as e:
        logger.error(
            "Failed to read request body",
            tenant_id=str(tenant_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": WebhookErrorCode.INVALID_PAYLOAD.value,
                "message": "Failed to read request body",
                "request_id": request_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ) from e

    # 3. Validate signature
    headers = {k.lower(): v for k, v in request.headers.items()}
    validation = await gateway.validate_inbound_event(
        tenant_id=tenant_id,
        headers=headers,
        payload=raw_body,
    )

    if not validation.valid:
        logger.warning(
            "Webhook signature validation failed",
            tenant_id=str(tenant_id),
            error=validation.error,
            request_id=request_id,
        )

        # Audit log failed signature validation (security event)
        logger.warning(
            "AUDIT: webhook_signature_failed",
            audit_event_type="security.alert",
            action="webhook_signature_failed",
            tenant_id=str(tenant_id),
            error=validation.error,
            platform=connection.platform.value,
            request_id=request_id,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": WebhookErrorCode.INVALID_SIGNATURE.value,
                "message": validation.error or "Webhook signature validation failed",
                "request_id": request_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    # 4. Parse JSON payload
    try:
        payload: dict[str, Any] = await request.json()
    except Exception as e:
        logger.error(
            "Failed to parse webhook JSON",
            tenant_id=str(tenant_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": WebhookErrorCode.INVALID_PAYLOAD.value,
                "message": "Invalid JSON payload",
                "request_id": request_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ) from e

    # 5. Extract event type from headers or payload
    event_type = (
        headers.get("x-event-type")
        or headers.get("x-webhook-event-type")
        or payload.get("type")
        or payload.get("event_type")
        or payload.get("eventType")
    )

    if not event_type:
        logger.warning(
            "No event type in webhook",
            tenant_id=str(tenant_id),
            request_id=request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": WebhookErrorCode.UNKNOWN_EVENT_TYPE.value,
                "message": "Event type not found in headers or payload",
                "request_id": request_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    # 6. Parse event using gateway
    event = await gateway.parse_inbound_event(
        tenant_id=tenant_id,
        event_type=event_type,
        payload=payload,
    )

    if event is None:
        # Rate limited or parsing failed
        logger.warning(
            "Failed to parse webhook event",
            tenant_id=str(tenant_id),
            event_type=event_type,
            request_id=request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": WebhookErrorCode.RATE_LIMITED.value,
                "message": "Rate limit exceeded for webhook events",
                "request_id": request_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    # 7. Audit log the received event
    logger.info(
        "AUDIT: hris_event_received",
        audit_event_type="hris.event_received",
        action="webhook_received",
        tenant_id=str(tenant_id),
        event_id=str(event.event_id),
        event_type=event.event_type.value,
        employee_id=event.employee_id,
        platform=event.platform.value,
        request_id=request_id,
    )

    logger.info(
        "Webhook received successfully",
        tenant_id=str(tenant_id),
        event_id=str(event.event_id),
        event_type=event.event_type.value,
        employee_id=event.employee_id,
        request_id=request_id,
    )

    # TODO: Task 10.3 - Route event to Event Processor
    # For now, just acknowledge receipt

    return WebhookResponse(
        status=WebhookStatus.RECEIVED,
        event_id=event.event_id,
        timestamp=event.received_at,
        message=f"Event {event.event_type.value} received for employee {event.employee_id}",
    )


@router.post(
    "/{tenant_id}/test",
    response_model=WebhookTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Test webhook connectivity",
    description="""
    Test the webhook connection for a tenant.

    This endpoint verifies that the HRIS connection is properly configured
    and the webhook secret is valid. It does not validate a signature.
    """,
    responses={
        200: {"description": "Connection test successful"},
        404: {"description": "Unknown tenant or no connection configured"},
    },
)
async def test_webhook(
    tenant_id: UUID,
    request: Request,
    gateway: Annotated[HRISGateway, Depends(get_hris_gateway)],
    body: WebhookTestRequest | None = None,
) -> WebhookTestResponse:
    """Test webhook connectivity for a tenant.

    Args:
        tenant_id: The tenant ID to test.
        request: The incoming request.
        gateway: HRIS gateway.
        body: Optional test request body.

    Returns:
        WebhookTestResponse with connection status.

    Raises:
        HTTPException: If tenant or connection not found.
    """
    request_id = request.headers.get("x-request-id", "unknown")

    connection = gateway.get_connection(tenant_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": WebhookErrorCode.UNKNOWN_TENANT.value,
                "message": f"No HRIS connection configured for tenant: {tenant_id}",
                "request_id": request_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    logger.info(
        "Webhook test successful",
        tenant_id=str(tenant_id),
        platform=connection.platform.value,
    )

    return WebhookTestResponse(
        status="ok",
        tenant_id=tenant_id,
        platform=connection.platform.value,
        connection_status=connection.status.value,
        echo_message=body.echo_message if body else None,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/{tenant_id}/status",
    response_model=WebhookConnectionStatus,
    status_code=status.HTTP_200_OK,
    summary="Get webhook connection status",
    description="""
    Get the current status of the HRIS webhook connection for a tenant.

    Returns detailed connection information including:
    - Connection status (connected, disconnected, error, etc.)
    - Whether the connection is enabled
    - Last sync and error timestamps
    """,
    responses={
        200: {"description": "Connection status"},
        404: {"description": "Unknown tenant or no connection configured"},
    },
)
async def get_webhook_status(
    tenant_id: UUID,
    request: Request,
    gateway: Annotated[HRISGateway, Depends(get_hris_gateway)],
) -> WebhookConnectionStatus:
    """Get webhook connection status for a tenant.

    Args:
        tenant_id: The tenant ID.
        request: The incoming request.
        gateway: HRIS gateway.

    Returns:
        WebhookConnectionStatus with detailed status information.

    Raises:
        HTTPException: If tenant or connection not found.
    """
    request_id = request.headers.get("x-request-id", "unknown")

    connection = gateway.get_connection(tenant_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": WebhookErrorCode.UNKNOWN_TENANT.value,
                "message": f"No HRIS connection configured for tenant: {tenant_id}",
                "request_id": request_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    return WebhookConnectionStatus(
        tenant_id=tenant_id,
        platform=connection.platform.value,
        connection_status=connection.status.value,
        enabled=connection.enabled,
        webhook_configured=connection.webhook_secret is not None,
        last_sync_at=connection.last_sync_at,
        last_error_at=connection.last_error_at,
        last_error_message=connection.last_error_message,
    )


# =============================================================================
# Helper for testing/development
# =============================================================================


def reset_gateway() -> None:
    """Reset the global gateway singleton.

    Used for testing to ensure a fresh gateway is created.
    """
    global _gateway
    _gateway = None
