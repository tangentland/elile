# Task 4.3: Rate Limiter

## Overview

Implement token bucket rate limiter for all provider API calls. Prevents exceeding provider rate limits and manages concurrent request throttling. See [06-data-sources.md](../architecture/06-data-sources.md#rate-limiting) for rate limiting strategy.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 4.1: Provider Gateway

## Implementation Checklist

- [ ] Create TokenBucket rate limiter
- [ ] Implement per-provider rate limit tracking
- [ ] Add distributed rate limiting (Redis-backed)
- [ ] Build rate limit configuration
- [ ] Add rate limit exceeded error handling
- [ ] Implement backoff and retry logic
- [ ] Write rate limiter tests

## Key Implementation

```python
# src/elile/providers/rate_limiter.py
import asyncio
from datetime import datetime, timedelta
from collections import deque

class RateLimitConfig(BaseModel):
    """Rate limit configuration."""
    requests_per_minute: int
    requests_per_hour: int | None = None
    requests_per_day: int | None = None
    burst_allowance: int = 5  # Extra tokens for burst traffic

class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = config.requests_per_minute
        self.max_tokens = config.requests_per_minute + config.burst_allowance
        self.last_refill = datetime.utcnow()
        self.lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens from bucket.

        Returns:
            True if tokens acquired, False if rate limit exceeded
        """
        async with self.lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = datetime.utcnow()
        elapsed = (now - self.last_refill).total_seconds()

        # Refill rate: tokens per second
        refill_rate = self.config.requests_per_minute / 60.0
        new_tokens = elapsed * refill_rate

        self.tokens = min(self.max_tokens, self.tokens + new_tokens)
        self.last_refill = now

    async def wait_for_token(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        while not await self.acquire(tokens):
            await asyncio.sleep(0.1)

class ProviderRateLimiter:
    """Rate limiter for all providers."""

    def __init__(self):
        self._limiters: dict[str, TokenBucket] = {}
        self._configs: dict[str, RateLimitConfig] = {}

    def configure_provider(self, provider_id: str, config: RateLimitConfig):
        """Configure rate limits for provider."""
        self._configs[provider_id] = config
        self._limiters[provider_id] = TokenBucket(config)

    async def acquire(self, provider_id: str, tokens: int = 1) -> bool:
        """Acquire rate limit token for provider."""
        limiter = self._limiters.get(provider_id)
        if not limiter:
            raise ValueError(f"No rate limiter configured for {provider_id}")

        return await limiter.acquire(tokens)

    async def wait_for_token(self, provider_id: str, tokens: int = 1):
        """Wait for rate limit token."""
        limiter = self._limiters.get(provider_id)
        if not limiter:
            raise ValueError(f"No rate limiter configured for {provider_id}")

        await limiter.wait_for_token(tokens)

# Global rate limiter instance
rate_limiter = ProviderRateLimiter()

# src/elile/providers/throttle.py
class RateLimitError(Exception):
    """Rate limit exceeded."""

    def __init__(self, provider_id: str, retry_after: int):
        self.provider_id = provider_id
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded for {provider_id}. Retry after {retry_after}s"
        )

async def with_rate_limit(
    provider_id: str,
    func,
    *args,
    max_retries: int = 3,
    **kwargs
):
    """Execute function with rate limiting and retry."""
    for attempt in range(max_retries):
        # Wait for rate limit token
        await rate_limiter.wait_for_token(provider_id)

        try:
            return await func(*args, **kwargs)
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(e.retry_after)

    raise RateLimitError(provider_id, 60)
```

## Testing Requirements

### Unit Tests
- TokenBucket token acquisition
- Token refill logic
- Burst allowance handling
- Multi-provider rate limiting
- wait_for_token() blocking behavior

### Integration Tests
- Rate limit enforcement under load
- Concurrent request throttling
- Provider-specific limits

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] TokenBucket rate limiter implemented
- [ ] Per-provider rate limit configuration
- [ ] acquire() and wait_for_token() methods work correctly
- [ ] Rate limit errors raised when exceeded
- [ ] Retry logic with backoff
- [ ] Unit tests pass with 90%+ coverage

## Deliverables

- `src/elile/providers/rate_limiter.py`
- `src/elile/providers/throttle.py`
- `tests/unit/test_rate_limiter.py`

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md#rate-limiting)
- Dependencies: Task 4.1 (provider gateway)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
