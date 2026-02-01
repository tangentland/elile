# Task 5.3: Query Executor

## Overview

Implement query executor that dispatches search queries to data providers with retry logic, rate limiting, and result collection. Handles provider failures gracefully with fallback strategies.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 4.1: Provider Gateway (provider interface)
- Task 4.2: Provider Health Monitor (health checks)
- Task 5.2: Query Planner (search queries)

## Implementation Checklist

- [ ] Create QueryExecutor with async execution
- [ ] Implement retry logic with exponential backoff
- [ ] Add rate limiting per provider
- [ ] Build fallback provider selection
- [ ] Create result collection and aggregation
- [ ] Add execution timeout handling
- [ ] Write comprehensive executor tests

## Key Implementation

```python
# src/elile/investigation/query_executor.py
from asyncio import gather, TimeoutError as AsyncTimeoutError
from datetime import datetime, timedelta

@dataclass
class QueryResult:
    """Result from query execution."""
    query_id: UUID
    provider_id: str
    status: Literal["success", "failed", "timeout", "rate_limited"]

    # Results
    raw_data: dict | None = None
    findings: list[dict] = field(default_factory=list)

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    duration_ms: int | None = None

    # Error info
    error: str | None = None
    retry_count: int = 0

class ExecutorConfig(BaseModel):
    """Configuration for query executor."""
    # Timeouts
    query_timeout_seconds: int = 30
    provider_timeout_seconds: int = 20

    # Retries
    max_retries: int = 3
    retry_backoff_seconds: list[int] = [1, 5, 15]

    # Concurrency
    max_concurrent_queries: int = 10

    # Rate limiting
    provider_rate_limit: int = 100  # Queries per minute
    rate_limit_window_seconds: int = 60

class QueryExecutor:
    """Executes search queries against data providers."""

    def __init__(
        self,
        provider_gateway: ProviderGateway,
        health_monitor: ProviderHealthMonitor,
        config: ExecutorConfig,
        audit_logger: AuditLogger
    ):
        self.gateway = provider_gateway
        self.health = health_monitor
        self.config = config
        self.audit = audit_logger

        # Rate limiting state
        self._rate_limiters: dict[str, deque] = {}

    async def execute_queries(
        self,
        queries: list[SearchQuery],
        ctx: RequestContext
    ) -> list[QueryResult]:
        """
        Execute multiple queries with concurrency control.

        Args:
            queries: List of search queries
            ctx: Request context

        Returns:
            List of query results
        """
        # Execute queries with concurrency limit
        results = []
        for i in range(0, len(queries), self.config.max_concurrent_queries):
            batch = queries[i:i + self.config.max_concurrent_queries]
            batch_results = await gather(
                *[self._execute_single_query(q, ctx) for q in batch],
                return_exceptions=True
            )

            # Handle exceptions
            for result in batch_results:
                if isinstance(result, Exception):
                    # Create failed result
                    results.append(QueryResult(
                        query_id=uuid4(),
                        provider_id="unknown",
                        status="failed",
                        error=str(result)
                    ))
                else:
                    results.append(result)

        # Audit summary
        self.audit.log_event(
            AuditEventType.QUERIES_EXECUTED,
            ctx,
            {
                "total_queries": len(queries),
                "successful": sum(1 for r in results if r.status == "success"),
                "failed": sum(1 for r in results if r.status == "failed"),
                "providers": list(set(r.provider_id for r in results))
            }
        )

        return results

    async def _execute_single_query(
        self,
        query: SearchQuery,
        ctx: RequestContext
    ) -> QueryResult:
        """
        Execute single query with retry logic.

        Args:
            query: Search query
            ctx: Request context

        Returns:
            Query result
        """
        result = QueryResult(
            query_id=query.query_id,
            provider_id=query.provider_id
        )

        # Check provider health
        if not self.health.is_healthy(query.provider_id):
            # Try to find alternate provider
            alternate = await self._find_alternate_provider(query, ctx)
            if alternate:
                query.provider_id = alternate
                result.provider_id = alternate
            else:
                result.status = "failed"
                result.error = "Provider unhealthy, no alternates available"
                return result

        # Execute with retries
        for attempt in range(self.config.max_retries + 1):
            result.retry_count = attempt

            try:
                # Rate limit check
                await self._wait_for_rate_limit(query.provider_id)

                # Execute query
                start = datetime.now(timezone.utc)
                raw_data = await asyncio.wait_for(
                    self.gateway.execute_query(query, ctx),
                    timeout=self.config.query_timeout_seconds
                )
                end = datetime.now(timezone.utc)

                # Success
                result.status = "success"
                result.raw_data = raw_data
                result.completed_at = end
                result.duration_ms = int((end - start).total_seconds() * 1000)

                # Audit
                await self.audit.log_event(
                    AuditEventType.QUERY_EXECUTED,
                    ctx,
                    {
                        "query_id": str(query.query_id),
                        "provider_id": query.provider_id,
                        "info_type": query.info_type,
                        "duration_ms": result.duration_ms,
                        "retry_count": attempt
                    }
                )

                return result

            except AsyncTimeoutError:
                result.error = f"Query timeout after {self.config.query_timeout_seconds}s"
                if attempt < self.config.max_retries:
                    # Retry with backoff
                    await asyncio.sleep(self.config.retry_backoff_seconds[attempt])
                else:
                    result.status = "timeout"

            except ProviderRateLimitError:
                result.error = "Provider rate limit exceeded"
                result.status = "rate_limited"
                # Don't retry rate limits
                break

            except ProviderError as e:
                result.error = str(e)
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_backoff_seconds[attempt])
                else:
                    result.status = "failed"

            except Exception as e:
                result.error = f"Unexpected error: {str(e)}"
                result.status = "failed"
                # Don't retry unexpected errors
                break

        result.completed_at = datetime.now(timezone.utc)
        return result

    async def _wait_for_rate_limit(self, provider_id: str) -> None:
        """Wait if provider rate limit would be exceeded."""
        if provider_id not in self._rate_limiters:
            self._rate_limiters[provider_id] = deque()

        rate_limiter = self._rate_limiters[provider_id]
        now = datetime.now(timezone.utc)

        # Remove old timestamps outside window
        cutoff = now - timedelta(seconds=self.config.rate_limit_window_seconds)
        while rate_limiter and rate_limiter[0] < cutoff:
            rate_limiter.popleft()

        # Check if we're at limit
        if len(rate_limiter) >= self.config.provider_rate_limit:
            # Wait until oldest timestamp expires
            wait_seconds = (
                rate_limiter[0] - cutoff
            ).total_seconds()
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

        # Record this query
        rate_limiter.append(now)

    async def _find_alternate_provider(
        self,
        query: SearchQuery,
        ctx: RequestContext
    ) -> str | None:
        """Find alternate provider for failed query."""
        # Get other providers for this check type
        check_type = query.info_type  # Simplified mapping
        alternates = await self.gateway.get_providers_for_check(check_type)

        # Filter out unhealthy and current provider
        healthy_alternates = [
            p for p in alternates
            if p.provider_id != query.provider_id
            and self.health.is_healthy(p.provider_id)
        ]

        if healthy_alternates:
            # Return first healthy alternate
            return healthy_alternates[0].provider_id

        return None
```

## Testing Requirements

### Unit Tests
- Single query execution success
- Retry logic with backoff
- Timeout handling
- Rate limiting per provider
- Alternate provider selection
- Error handling for each failure type

### Integration Tests
- Batch query execution
- Concurrent query limits
- Provider fallback scenarios
- Rate limit across multiple queries

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] QueryExecutor executes queries asynchronously
- [ ] Retry logic with exponential backoff (3 attempts)
- [ ] Query timeout enforced (30s default)
- [ ] Rate limiting per provider (100/min)
- [ ] Failed queries fallback to alternates
- [ ] Concurrent query limit enforced
- [ ] Complete execution audit trail

## Deliverables

- `src/elile/investigation/query_executor.py`
- `tests/unit/test_query_executor.py`
- `tests/integration/test_query_execution.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - Query Execution
- Dependencies: Task 4.1 (gateway), Task 4.2 (health), Task 5.2 (planner)

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
