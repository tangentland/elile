# Task 10.7: API Rate Limiting

**Priority**: P1
**Phase**: 10 - External Integrations
**Estimated Effort**: 2 days
**Dependencies**: Task 10.1 (API Framework)

## Context

Implement rate limiting for API endpoints to prevent abuse, ensure fair usage, and protect system resources.

## Objectives

1. Per-org rate limits
2. Endpoint-specific limits
3. Token bucket algorithm
4. Rate limit headers
5. Burst handling

## Technical Approach

```python
# src/elile/api/rate_limiting.py
class RateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def check_limit(
        self,
        org_id: str,
        endpoint: str,
        limit: int,
        window: int
    ) -> bool:
        key = f"ratelimit:{org_id}:{endpoint}"
        current = await self.redis.increment(key)

        if current == 1:
            await self.redis.expire(key, window)

        return current <= limit
```

## Implementation Checklist

- [ ] Implement rate limiter
- [ ] Add middleware
- [ ] Test limits

## Success Criteria

- [ ] Limits enforced
- [ ] Headers accurate
