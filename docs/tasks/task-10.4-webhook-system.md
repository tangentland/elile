# Task 10.4: Webhook System

## Overview

Implement webhook system for async event delivery to customer endpoints with HMAC signatures, retry logic, and event filtering.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 10.1: API Gateway

## Implementation

```python
# src/elile/webhooks/webhook_sender.py
class WebhookSender:
    """Sends webhooks to customer endpoints."""

    async def send_webhook(
        self,
        webhook_config: WebhookConfig,
        event: Event
    ) -> WebhookDelivery:
        """Send webhook with retry logic."""

        # Generate HMAC signature
        signature = self._generate_signature(
            event.to_json(), webhook_config.secret
        )

        # Attempt delivery
        for attempt in range(webhook_config.max_retries):
            try:
                response = await httpx.post(
                    webhook_config.url,
                    json=event.to_dict(),
                    headers={"X-Elile-Signature": signature},
                    timeout=10
                )

                if response.status_code == 200:
                    return WebhookDelivery(
                        status="delivered",
                        attempts=attempt + 1
                    )

            except Exception as e:
                if attempt < webhook_config.max_retries - 1:
                    await asyncio.sleep(
                        webhook_config.backoff_seconds[attempt]
                    )

        return WebhookDelivery(status="failed", attempts=attempt + 1)

    def _generate_signature(self, payload: str, secret: str) -> str:
        """Generate HMAC signature."""
        import hmac
        import hashlib
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
```

## Acceptance Criteria

- [ ] Sends webhooks to customer URLs
- [ ] HMAC signature verification
- [ ] Retry logic with backoff (3 attempts: 30s, 5m, 1h)
- [ ] Event filtering by subscription
- [ ] Delivery tracking

## Deliverables

- `src/elile/webhooks/webhook_sender.py`
- `tests/unit/test_webhook_system.py`

## References

- Architecture: [09-integration.md](../../docs/architecture/09-integration.md) - Webhooks

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
