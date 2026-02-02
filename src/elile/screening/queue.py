"""Screening Queue Management System.

Task 7.9: Implements priority queue for screening execution with resource
allocation, rate limiting, and load balancing across workers.

Features:
- Priority-based queueing using Redis sorted sets
- Resource allocation per tier with configurable limits
- Rate limiting per organization
- Load balancing across workers
- Queue monitoring and metrics
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid7

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from elile.agent.state import ServiceTier
from elile.core.redis import RateLimiter, RateLimitResult, get_redis_client
from elile.screening.types import ScreeningPriority, ScreeningRequest

# =============================================================================
# Queue Types
# =============================================================================


class QueueStatus(str, Enum):
    """Status of the queue system."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Some workers unavailable
    PAUSED = "paused"  # Manually paused
    OVERLOADED = "overloaded"  # Above capacity threshold


class WorkerStatus(str, Enum):
    """Status of a queue worker."""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    DRAINING = "draining"  # Finishing current work, not accepting new


@dataclass
class QueuedScreening:
    """A screening request in the queue.

    Tracks the request along with queue metadata like enqueue time
    and priority score.
    """

    queue_id: UUID = field(default_factory=uuid7)
    screening_id: UUID = field(default_factory=uuid7)
    tenant_id: UUID = field(default_factory=uuid7)
    tier: ServiceTier = ServiceTier.STANDARD
    priority: ScreeningPriority = ScreeningPriority.NORMAL
    priority_score: float = 0.0
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    worker_id: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        return {
            "queue_id": str(self.queue_id),
            "screening_id": str(self.screening_id),
            "tenant_id": str(self.tenant_id),
            "tier": self.tier.value,
            "priority": self.priority.value,
            "priority_score": self.priority_score,
            "enqueued_at": self.enqueued_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "worker_id": self.worker_id,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueuedScreening:
        """Create from dictionary."""
        return cls(
            queue_id=UUID(data["queue_id"]),
            screening_id=UUID(data["screening_id"]),
            tenant_id=UUID(data["tenant_id"]),
            tier=ServiceTier(data["tier"]),
            priority=ScreeningPriority(data["priority"]),
            priority_score=data["priority_score"],
            enqueued_at=datetime.fromisoformat(data["enqueued_at"]),
            started_at=(
                datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
            ),
            worker_id=data.get("worker_id"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_request(
        cls,
        request: ScreeningRequest,
        priority_score: float | None = None,
    ) -> QueuedScreening:
        """Create from a ScreeningRequest."""
        return cls(
            screening_id=request.screening_id,
            tenant_id=request.tenant_id,
            tier=request.service_tier,
            priority=request.priority,
            priority_score=priority_score or cls._calculate_priority_score(request),
            metadata={
                "locale": request.locale.value,
                "search_degree": request.search_degree.value,
                "role_category": request.role_category.value,
            },
        )

    @staticmethod
    def _calculate_priority_score(request: ScreeningRequest) -> float:
        """Calculate priority score from request.

        Higher scores = higher priority. Uses a combination of
        explicit priority and implicit factors.

        Score components:
        - Base priority: URGENT=1000, HIGH=100, NORMAL=10, LOW=1
        - Tier bonus: ENHANCED=50, STANDARD=0
        - Age penalty: Reduces priority for very old requests
        """
        base_scores = {
            ScreeningPriority.URGENT: 1000.0,
            ScreeningPriority.HIGH: 100.0,
            ScreeningPriority.NORMAL: 10.0,
            ScreeningPriority.LOW: 1.0,
        }
        score = base_scores.get(request.priority, 10.0)

        # Tier bonus
        if request.service_tier == ServiceTier.ENHANCED:
            score += 50.0

        # Timestamp component for FIFO within same priority
        # Use negative timestamp so earlier requests have higher scores
        timestamp_component = datetime.now(UTC).timestamp() - request.requested_at.timestamp()
        # Add small fraction to avoid score ties
        score += min(timestamp_component / 1000.0, 0.999)

        return score


@dataclass
class QueueMetrics:
    """Metrics for queue monitoring."""

    total_pending: int = 0
    total_processing: int = 0
    pending_by_tier: dict[str, int] = field(default_factory=dict)
    pending_by_priority: dict[str, int] = field(default_factory=dict)
    processing_by_worker: dict[str, int] = field(default_factory=dict)
    avg_wait_time_seconds: float = 0.0
    oldest_pending_age_seconds: float = 0.0
    rate_limited_tenants: list[str] = field(default_factory=list)
    queue_status: QueueStatus = QueueStatus.HEALTHY
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_pending": self.total_pending,
            "total_processing": self.total_processing,
            "pending_by_tier": self.pending_by_tier,
            "pending_by_priority": self.pending_by_priority,
            "processing_by_worker": self.processing_by_worker,
            "avg_wait_time_seconds": self.avg_wait_time_seconds,
            "oldest_pending_age_seconds": self.oldest_pending_age_seconds,
            "rate_limited_tenants": self.rate_limited_tenants,
            "queue_status": self.queue_status.value,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class DequeueResult:
    """Result from dequeue operation."""

    success: bool = False
    screening: QueuedScreening | None = None
    rate_limited: bool = False
    rate_limit_info: RateLimitResult | None = None
    error: str | None = None


# =============================================================================
# Configuration
# =============================================================================


class QueueConfig(BaseModel):
    """Configuration for the screening queue system."""

    # Queue key prefixes
    queue_prefix: str = Field(default="screening:queue", description="Redis key prefix")

    # Resource limits per tier
    max_concurrent_standard: int = Field(
        default=50, ge=1, description="Max concurrent standard tier screenings"
    )
    max_concurrent_enhanced: int = Field(
        default=20, ge=1, description="Max concurrent enhanced tier screenings"
    )

    # Rate limiting per tenant
    rate_limit_per_tenant: int = Field(
        default=100, ge=1, description="Max screenings per tenant per window"
    )
    rate_limit_window_seconds: int = Field(
        default=3600, ge=60, description="Rate limit window in seconds (1 hour default)"
    )

    # Worker settings
    worker_heartbeat_seconds: int = Field(default=30, ge=5, description="Worker heartbeat interval")
    worker_timeout_seconds: int = Field(
        default=120, ge=30, description="Worker timeout before considered offline"
    )

    # Queue behavior
    max_retries: int = Field(default=3, ge=0, description="Max retries for failed screenings")
    retry_delay_seconds: int = Field(default=60, ge=10, description="Delay between retries")
    stale_screening_hours: int = Field(
        default=24, ge=1, description="Hours before screening is considered stale"
    )

    # Monitoring thresholds
    overload_threshold: float = Field(
        default=0.9, ge=0.5, le=1.0, description="Capacity threshold for overload status"
    )
    degraded_threshold: float = Field(
        default=0.7, ge=0.3, le=1.0, description="Capacity threshold for degraded status"
    )


# =============================================================================
# Queue Storage Protocol
# =============================================================================


class QueueStorage(Protocol):
    """Protocol for queue storage backends."""

    async def enqueue(self, screening: QueuedScreening) -> bool:
        """Add screening to queue."""
        ...

    async def dequeue(self, tier: ServiceTier | None = None) -> QueuedScreening | None:
        """Remove and return highest priority screening."""
        ...

    async def peek(self, tier: ServiceTier | None = None, limit: int = 10) -> list[QueuedScreening]:
        """View screenings without removing."""
        ...

    async def remove(self, queue_id: UUID) -> bool:
        """Remove specific screening from queue."""
        ...

    async def get_pending_count(self, tier: ServiceTier | None = None) -> int:
        """Get count of pending screenings."""
        ...

    async def get_processing_count(self) -> int:
        """Get count of screenings being processed."""
        ...


# =============================================================================
# Redis Queue Storage
# =============================================================================


class RedisQueueStorage:
    """Redis-backed queue storage using sorted sets.

    Uses Redis sorted sets for O(log N) enqueue/dequeue operations
    with priority-based ordering.
    """

    def __init__(
        self,
        client: Redis | None = None,
        config: QueueConfig | None = None,
    ) -> None:
        """Initialize Redis queue storage.

        Args:
            client: Redis client (uses global if None).
            config: Queue configuration.
        """
        self._client = client
        self.config = config or QueueConfig()

    async def _get_client(self) -> Redis:
        """Get Redis client."""
        if self._client is not None:
            return self._client
        return await get_redis_client()

    def _queue_key(self, tier: ServiceTier) -> str:
        """Get queue key for tier."""
        return f"{self.config.queue_prefix}:pending:{tier.value}"

    def _processing_key(self) -> str:
        """Get processing set key."""
        return f"{self.config.queue_prefix}:processing"

    def _data_key(self, queue_id: UUID) -> str:
        """Get data key for screening."""
        return f"{self.config.queue_prefix}:data:{queue_id}"

    async def enqueue(self, screening: QueuedScreening) -> bool:
        """Add screening to queue.

        Args:
            screening: Screening to queue.

        Returns:
            True if added successfully.
        """
        client = await self._get_client()
        queue_key = self._queue_key(screening.tier)
        data_key = self._data_key(screening.queue_id)

        # Store data and add to sorted set atomically
        pipe = client.pipeline()
        pipe.set(data_key, json.dumps(screening.to_dict()))
        pipe.zadd(queue_key, {str(screening.queue_id): screening.priority_score})
        results = await pipe.execute()

        return all(r for r in results)

    async def dequeue(self, tier: ServiceTier | None = None) -> QueuedScreening | None:
        """Remove and return highest priority screening.

        Args:
            tier: Specific tier to dequeue from (None = any tier).

        Returns:
            Highest priority screening or None if queue empty.
        """
        client = await self._get_client()

        # Determine which tiers to check
        tiers = [tier] if tier else [ServiceTier.ENHANCED, ServiceTier.STANDARD]

        for check_tier in tiers:
            queue_key = self._queue_key(check_tier)

            # Pop highest score (highest priority)
            result = await client.zpopmax(queue_key, count=1)
            if not result:
                continue

            queue_id_str, _score = result[0]
            queue_id = UUID(queue_id_str)
            data_key = self._data_key(queue_id)

            # Get and delete data
            data = await client.get(data_key)
            if data is None:
                continue

            await client.delete(data_key)

            screening = QueuedScreening.from_dict(json.loads(data))
            screening.started_at = datetime.now(UTC)

            # Add to processing set
            processing_key = self._processing_key()
            await client.sadd(processing_key, str(screening.queue_id))

            return screening

        return None

    async def peek(
        self,
        tier: ServiceTier | None = None,
        limit: int = 10,
    ) -> list[QueuedScreening]:
        """View screenings without removing.

        Args:
            tier: Specific tier to peek (None = all tiers).
            limit: Maximum screenings to return.

        Returns:
            List of screenings (highest priority first).
        """
        client = await self._get_client()
        screenings: list[QueuedScreening] = []

        tiers = [tier] if tier else [ServiceTier.ENHANCED, ServiceTier.STANDARD]

        for check_tier in tiers:
            if len(screenings) >= limit:
                break

            queue_key = self._queue_key(check_tier)
            remaining = limit - len(screenings)

            # Get highest scored items
            items = await client.zrevrange(queue_key, 0, remaining - 1)

            for queue_id_str in items:
                data_key = self._data_key(UUID(queue_id_str))
                data = await client.get(data_key)
                if data:
                    screenings.append(QueuedScreening.from_dict(json.loads(data)))

        return screenings

    async def remove(self, queue_id: UUID) -> bool:
        """Remove specific screening from queue.

        Args:
            queue_id: Queue ID to remove.

        Returns:
            True if screening was found and removed.
        """
        client = await self._get_client()
        data_key = self._data_key(queue_id)

        # Get data to find tier
        data = await client.get(data_key)
        if data is None:
            return False

        screening = QueuedScreening.from_dict(json.loads(data))
        queue_key = self._queue_key(screening.tier)

        pipe = client.pipeline()
        pipe.zrem(queue_key, str(queue_id))
        pipe.delete(data_key)
        results = await pipe.execute()

        return results[0] > 0

    async def mark_complete(self, queue_id: UUID) -> bool:
        """Mark screening as complete (remove from processing).

        Args:
            queue_id: Queue ID to mark complete.

        Returns:
            True if removed from processing set.
        """
        client = await self._get_client()
        processing_key = self._processing_key()
        result = await client.srem(processing_key, str(queue_id))
        return result > 0

    async def requeue(self, screening: QueuedScreening) -> bool:
        """Requeue a failed screening for retry.

        Args:
            screening: Screening to requeue.

        Returns:
            True if requeued successfully.
        """
        # Remove from processing
        await self.mark_complete(screening.queue_id)

        # Increment retry count
        screening.retry_count += 1
        screening.started_at = None
        screening.worker_id = None

        # Lower priority slightly for retried items
        screening.priority_score *= 0.9

        return await self.enqueue(screening)

    async def get_pending_count(self, tier: ServiceTier | None = None) -> int:
        """Get count of pending screenings.

        Args:
            tier: Specific tier to count (None = all tiers).

        Returns:
            Number of pending screenings.
        """
        client = await self._get_client()
        total = 0

        tiers = [tier] if tier else [ServiceTier.ENHANCED, ServiceTier.STANDARD]

        for check_tier in tiers:
            queue_key = self._queue_key(check_tier)
            count = await client.zcard(queue_key)
            total += count

        return total

    async def get_processing_count(self) -> int:
        """Get count of screenings being processed.

        Returns:
            Number of screenings currently processing.
        """
        client = await self._get_client()
        processing_key = self._processing_key()
        return await client.scard(processing_key)


# =============================================================================
# In-Memory Queue Storage (for testing)
# =============================================================================


class InMemoryQueueStorage:
    """In-memory queue storage for testing."""

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._queues: dict[ServiceTier, list[QueuedScreening]] = {
            ServiceTier.STANDARD: [],
            ServiceTier.ENHANCED: [],
        }
        self._processing: set[UUID] = set()

    async def enqueue(self, screening: QueuedScreening) -> bool:
        """Add screening to queue."""
        self._queues[screening.tier].append(screening)
        # Sort by priority score descending
        self._queues[screening.tier].sort(key=lambda x: x.priority_score, reverse=True)
        return True

    async def dequeue(self, tier: ServiceTier | None = None) -> QueuedScreening | None:
        """Remove and return highest priority screening."""
        tiers = [tier] if tier else [ServiceTier.ENHANCED, ServiceTier.STANDARD]

        for check_tier in tiers:
            if self._queues[check_tier]:
                screening = self._queues[check_tier].pop(0)
                screening.started_at = datetime.now(UTC)
                self._processing.add(screening.queue_id)
                return screening

        return None

    async def peek(
        self,
        tier: ServiceTier | None = None,
        limit: int = 10,
    ) -> list[QueuedScreening]:
        """View screenings without removing."""
        tiers = [tier] if tier else [ServiceTier.ENHANCED, ServiceTier.STANDARD]
        result: list[QueuedScreening] = []

        for check_tier in tiers:
            remaining = limit - len(result)
            if remaining <= 0:
                break
            result.extend(self._queues[check_tier][:remaining])

        return result

    async def remove(self, queue_id: UUID) -> bool:
        """Remove specific screening from queue."""
        for tier_queue in self._queues.values():
            for i, screening in enumerate(tier_queue):
                if screening.queue_id == queue_id:
                    tier_queue.pop(i)
                    return True
        return False

    async def mark_complete(self, queue_id: UUID) -> bool:
        """Mark screening as complete."""
        if queue_id in self._processing:
            self._processing.discard(queue_id)
            return True
        return False

    async def requeue(self, screening: QueuedScreening) -> bool:
        """Requeue a failed screening."""
        self._processing.discard(screening.queue_id)
        screening.retry_count += 1
        screening.started_at = None
        screening.worker_id = None
        screening.priority_score *= 0.9
        return await self.enqueue(screening)

    async def get_pending_count(self, tier: ServiceTier | None = None) -> int:
        """Get count of pending screenings."""
        if tier:
            return len(self._queues[tier])
        return sum(len(q) for q in self._queues.values())

    async def get_processing_count(self) -> int:
        """Get count of screenings being processed."""
        return len(self._processing)


# =============================================================================
# Screening Queue Manager
# =============================================================================


class ScreeningQueueManager:
    """Manages screening queue with priority, rate limiting, and load balancing.

    Provides the main interface for queueing and dequeuing screenings
    with built-in resource management and monitoring.

    Features:
    - Priority-based queueing (URGENT > HIGH > NORMAL > LOW)
    - Per-tenant rate limiting
    - Per-tier resource limits
    - Worker load balancing
    - Queue health monitoring
    """

    def __init__(
        self,
        storage: RedisQueueStorage | InMemoryQueueStorage | None = None,
        rate_limiter: RateLimiter | None = None,
        config: QueueConfig | None = None,
    ) -> None:
        """Initialize queue manager.

        Args:
            storage: Queue storage backend.
            rate_limiter: Rate limiter for per-tenant limits.
            config: Queue configuration.
        """
        self.config = config or QueueConfig()
        self.storage = storage or InMemoryQueueStorage()
        self.rate_limiter = rate_limiter or RateLimiter(prefix="screening:ratelimit")
        self._workers: dict[str, datetime] = {}  # worker_id -> last heartbeat

    async def enqueue(
        self,
        request: ScreeningRequest,
        *,
        check_rate_limit: bool = True,
    ) -> tuple[QueuedScreening | None, RateLimitResult | None]:
        """Add screening request to the queue.

        Args:
            request: Screening request to queue.
            check_rate_limit: Whether to check tenant rate limits.

        Returns:
            Tuple of (queued screening, rate limit result if blocked).
        """
        # Check rate limit
        if check_rate_limit:
            rate_result = await self.rate_limiter.check(
                identifier=str(request.tenant_id),
                resource="screening",
                limit=self.config.rate_limit_per_tenant,
                window_seconds=self.config.rate_limit_window_seconds,
            )

            if not rate_result.allowed:
                return None, rate_result

        # Create queued screening
        queued = QueuedScreening.from_request(request)

        # Add to queue
        success = await self.storage.enqueue(queued)
        if not success:
            return None, None

        return queued, None

    async def dequeue(
        self,
        worker_id: str,
        tier: ServiceTier | None = None,
    ) -> DequeueResult:
        """Remove and return next screening for processing.

        Args:
            worker_id: ID of worker requesting work.
            tier: Specific tier to dequeue (None = any tier).

        Returns:
            DequeueResult with screening or error information.
        """
        # Update worker heartbeat
        self._workers[worker_id] = datetime.now(UTC)

        # Check resource limits
        current_processing = await self.storage.get_processing_count()
        max_processing = self.config.max_concurrent_standard + self.config.max_concurrent_enhanced

        if current_processing >= max_processing:
            return DequeueResult(
                success=False,
                error="System at capacity",
            )

        # Check tier-specific limits if tier specified
        if tier:
            tier_limit = (
                self.config.max_concurrent_enhanced
                if tier == ServiceTier.ENHANCED
                else self.config.max_concurrent_standard
            )
            # Note: In a full implementation, we'd track per-tier processing counts
            # For now, use total processing as proxy
            if current_processing >= tier_limit:
                return DequeueResult(
                    success=False,
                    error=f"{tier.value} tier at capacity",
                )

        # Dequeue
        screening = await self.storage.dequeue(tier)
        if screening is None:
            return DequeueResult(
                success=False,
                error="Queue empty",
            )

        # Assign worker
        screening.worker_id = worker_id

        return DequeueResult(
            success=True,
            screening=screening,
        )

    async def complete(self, queue_id: UUID) -> bool:
        """Mark screening as complete.

        Args:
            queue_id: Queue ID of completed screening.

        Returns:
            True if marked complete successfully.
        """
        return await self.storage.mark_complete(queue_id)

    async def fail(
        self,
        queue_id: UUID,
        screening: QueuedScreening,
        *,
        retry: bool = True,
    ) -> bool:
        """Handle failed screening.

        Args:
            queue_id: Queue ID of failed screening.
            screening: The failed screening.
            retry: Whether to requeue for retry.

        Returns:
            True if handled successfully.
        """
        if retry and screening.retry_count < screening.max_retries:
            return await self.storage.requeue(screening)
        else:
            return await self.storage.mark_complete(queue_id)

    async def cancel(self, queue_id: UUID) -> bool:
        """Cancel a queued screening.

        Args:
            queue_id: Queue ID to cancel.

        Returns:
            True if screening was found and cancelled.
        """
        return await self.storage.remove(queue_id)

    async def peek(
        self,
        tier: ServiceTier | None = None,
        limit: int = 10,
    ) -> list[QueuedScreening]:
        """View pending screenings without removing.

        Args:
            tier: Specific tier to view.
            limit: Maximum number to return.

        Returns:
            List of pending screenings.
        """
        return await self.storage.peek(tier, limit)

    async def get_metrics(self) -> QueueMetrics:
        """Get current queue metrics.

        Returns:
            QueueMetrics with current state.
        """
        pending_standard = await self.storage.get_pending_count(ServiceTier.STANDARD)
        pending_enhanced = await self.storage.get_pending_count(ServiceTier.ENHANCED)
        total_pending = pending_standard + pending_enhanced
        total_processing = await self.storage.get_processing_count()

        # Get oldest pending for wait time estimate
        oldest_screenings = await self.storage.peek(limit=1)
        oldest_age = 0.0
        if oldest_screenings:
            oldest = oldest_screenings[0]
            oldest_age = (datetime.now(UTC) - oldest.enqueued_at).total_seconds()

        # Calculate queue status
        max_capacity = self.config.max_concurrent_standard + self.config.max_concurrent_enhanced
        utilization = total_processing / max_capacity if max_capacity > 0 else 0

        if utilization >= self.config.overload_threshold:
            status = QueueStatus.OVERLOADED
        elif utilization >= self.config.degraded_threshold:
            status = QueueStatus.DEGRADED
        else:
            status = QueueStatus.HEALTHY

        # Count pending by priority
        all_pending = await self.storage.peek(limit=1000)
        pending_by_priority: dict[str, int] = {}
        for screening in all_pending:
            key = screening.priority.value
            pending_by_priority[key] = pending_by_priority.get(key, 0) + 1

        return QueueMetrics(
            total_pending=total_pending,
            total_processing=total_processing,
            pending_by_tier={
                ServiceTier.STANDARD.value: pending_standard,
                ServiceTier.ENHANCED.value: pending_enhanced,
            },
            pending_by_priority=pending_by_priority,
            processing_by_worker=dict.fromkeys(self._workers.keys(), 1),
            avg_wait_time_seconds=oldest_age / 2 if oldest_age > 0 else 0,  # Estimate
            oldest_pending_age_seconds=oldest_age,
            rate_limited_tenants=[],  # Would need to track separately
            queue_status=status,
        )

    async def worker_heartbeat(self, worker_id: str) -> None:
        """Record worker heartbeat.

        Args:
            worker_id: ID of the worker.
        """
        self._workers[worker_id] = datetime.now(UTC)

    async def get_active_workers(self) -> list[str]:
        """Get list of active workers.

        Returns:
            List of worker IDs with recent heartbeats.
        """
        now = datetime.now(UTC)
        timeout = self.config.worker_timeout_seconds
        active = [
            worker_id
            for worker_id, last_seen in self._workers.items()
            if (now - last_seen).total_seconds() < timeout
        ]
        return active

    async def cleanup_stale(self) -> int:
        """Clean up stale screenings from queue.

        Returns:
            Number of stale screenings removed.
        """
        stale_threshold = datetime.now(UTC).timestamp() - (self.config.stale_screening_hours * 3600)
        removed = 0

        all_pending = await self.storage.peek(limit=10000)
        for screening in all_pending:
            if screening.enqueued_at.timestamp() < stale_threshold and await self.storage.remove(
                screening.queue_id
            ):
                removed += 1

        return removed


# =============================================================================
# Factory Functions
# =============================================================================


def create_queue_manager(
    config: QueueConfig | None = None,
    use_redis: bool = True,
) -> ScreeningQueueManager:
    """Create a screening queue manager.

    Args:
        config: Queue configuration.
        use_redis: If True, use Redis storage; otherwise use in-memory.

    Returns:
        Configured ScreeningQueueManager.
    """
    config = config or QueueConfig()
    storage = RedisQueueStorage(config=config) if use_redis else InMemoryQueueStorage()

    return ScreeningQueueManager(
        storage=storage,
        config=config,
    )


async def create_queue_manager_async(
    config: QueueConfig | None = None,
) -> ScreeningQueueManager:
    """Create a screening queue manager with Redis client.

    This async version initializes the Redis client.

    Args:
        config: Queue configuration.

    Returns:
        Configured ScreeningQueueManager with Redis.
    """
    config = config or QueueConfig()
    client = await get_redis_client()

    storage = RedisQueueStorage(client=client, config=config)
    rate_limiter = RateLimiter(client=client, prefix="screening:ratelimit")

    return ScreeningQueueManager(
        storage=storage,
        rate_limiter=rate_limiter,
        config=config,
    )
