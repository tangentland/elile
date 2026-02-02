# Task 10.2: Webhook Receiver

## Overview

Implement FastAPI endpoints for receiving HRIS webhooks. The webhook receiver validates incoming requests, parses platform-specific payloads, and routes events for processing.

## Priority

P0 (Critical Path)

## Dependencies

- Task 10.1 HRIS Integration Gateway (Complete) ✅

## Implementation Checklist

### Webhook Receiver Router
- [x] Create `/v1/hris/webhooks` router
- [x] POST `/{tenant_id}` - Receive webhook from HRIS platform
- [x] POST `/{tenant_id}/test` - Test webhook connectivity
- [x] GET `/{tenant_id}/status` - Check webhook connection status

### Request Handling
- [x] Extract and validate X-Webhook-Signature header
- [x] Parse raw body for signature validation
- [x] Support multiple signature algorithms (HMAC-SHA256, HMAC-SHA512)
- [x] Rate limiting per tenant (via HRISGateway)

### Event Parsing
- [x] Detect event type from headers or payload
- [x] Use platform adapter to parse to HRISEvent
- [x] Store raw payload for audit trail
- [x] Generate event_id (UUIDv7)

### Response Handling
- [x] Return 200 OK for valid events (processed or queued)
- [x] Return 400 Bad Request for invalid payload
- [x] Return 401 Unauthorized for invalid signature
- [x] Return 404 Not Found for unknown tenant
- [x] Return 429 Too Many Requests when rate limited
- [x] Include X-Request-ID in response headers

### Error Handling
- [x] Log failed validation attempts with details
- [x] Track failed signature attempts (security monitoring)
- [x] Graceful handling of malformed JSON
- [x] Audit log for all webhook events

## Request/Response Schemas

### Webhook Request
```python
class WebhookRequest:
    # Headers
    x_webhook_signature: str  # HMAC signature
    x_event_type: str | None  # Optional event type hint
    content_type: str  # application/json

    # Body
    raw_payload: bytes  # For signature validation
    parsed_payload: dict[str, Any]  # Parsed JSON
```

### Webhook Response
```python
class WebhookResponse(BaseModel):
    status: Literal["received", "queued", "processed"]
    event_id: UUID
    timestamp: datetime
    message: str | None = None
```

### Error Response
```python
class WebhookErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str
    timestamp: datetime
```

## Key Code

```python
@router.post("/{tenant_id}")
async def receive_webhook(
    tenant_id: UUID,
    request: Request,
    gateway: Annotated[HRISGateway, Depends(get_hris_gateway)],
) -> WebhookResponse:
    """Receive and process HRIS webhook."""
    # 1. Get raw body for signature validation
    raw_body = await request.body()

    # 2. Validate signature
    headers = dict(request.headers)
    validation = await gateway.validate_inbound_event(
        tenant_id=tenant_id,
        headers=headers,
        payload=raw_body,
    )

    if not validation.valid:
        raise HTTPException(
            status_code=401,
            detail={"error_code": "INVALID_SIGNATURE", ...}
        )

    # 3. Parse payload
    payload = await request.json()
    event_type = headers.get("x-event-type", payload.get("type"))

    event = await gateway.parse_inbound_event(
        tenant_id=tenant_id,
        event_type=event_type,
        payload=payload,
    )

    # 4. Route event for processing (Task 10.3)
    # For now, just acknowledge receipt

    return WebhookResponse(
        status="received",
        event_id=event.event_id,
        timestamp=event.received_at,
    )
```

## Testing Requirements

### Unit Tests
- [x] Valid webhook processing (happy path)
- [x] Invalid signature rejection
- [x] Missing signature rejection
- [x] Unknown tenant rejection
- [x] Rate limiting enforcement
- [x] Malformed JSON handling
- [x] Event type detection from headers
- [x] Event type detection from payload
- [x] Test endpoint functionality

### Integration Tests
- [ ] End-to-end webhook flow with mock HRIS
- [ ] Rate limit reset behavior
- [ ] Concurrent webhook handling

## Acceptance Criteria

1. Webhooks are validated using platform-specific signature verification
2. Events are parsed to canonical HRISEvent format
3. Appropriate HTTP status codes returned for all scenarios
4. All webhook events are audit logged
5. Rate limiting prevents abuse (configurable per tenant)
6. Test endpoint allows connectivity verification

## Notes

- The webhook receiver handles inbound events only
- Event processing (triggering screenings, etc.) is Task 10.3
- The receiver should be idempotent (same event can be received twice safely)
- Consider adding webhook replay protection (event timestamps)
