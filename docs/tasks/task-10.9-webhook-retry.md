# Task 10.9: Webhook Retry Logic

**Priority**: P1
**Phase**: 10 - External Integrations
**Estimated Effort**: 2 days
**Dependencies**: Task 10.3 (Webhook System)

## Context

Implement robust webhook retry logic with exponential backoff, dead letter queue, and delivery guarantees.

## Objectives

1. Automatic retry on failure
2. Exponential backoff
3. Dead letter queue
4. Delivery tracking
5. Manual retry interface

## Technical Approach

```python
# src/elile/integrations/webhooks/retry.py
class WebhookRetryHandler:
    async def send_with_retry(
        self,
        webhook: Webhook,
        payload: Dict,
        max_attempts: int = 5
    ) -> DeliveryResult:
        for attempt in range(max_attempts):
            try:
                response = await self._send(webhook, payload)
                return DeliveryResult(success=True, attempts=attempt+1)
            except Exception as e:
                if attempt == max_attempts - 1:
                    await self._move_to_dlq(webhook, payload)
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

## Implementation Checklist

- [ ] Implement retry logic
- [ ] Add DLQ
- [ ] Test delivery

## Success Criteria

- [ ] 99.9% delivery rate
- [ ] Failed webhooks tracked
