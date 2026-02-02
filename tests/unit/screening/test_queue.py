"""Tests for the Screening Queue Manager (Task 7.9).

Tests cover:
- Priority-based queueing
- Resource allocation
- Rate limiting per org
- Load balancing
- Queue monitoring
"""

from uuid import uuid7

import pytest

from elile.agent.state import SearchDegree, ServiceTier, VigilanceLevel
from elile.compliance.types import Locale, RoleCategory
from elile.entity.types import SubjectIdentifiers
from elile.screening.queue import (
    InMemoryQueueStorage,
    QueueConfig,
    QueuedScreening,
    QueueStatus,
    create_queue_manager,
)
from elile.screening.types import ScreeningPriority, ScreeningRequest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def config():
    """Create test configuration."""
    return QueueConfig(
        max_concurrent_standard=10,
        max_concurrent_enhanced=5,
        rate_limit_per_tenant=100,
        rate_limit_window_seconds=3600,
        max_retries=3,
    )


@pytest.fixture
def queue_manager(config):
    """Create in-memory queue manager for testing."""
    return create_queue_manager(config=config, use_redis=False)


@pytest.fixture
def screening_request():
    """Create a sample screening request."""
    return ScreeningRequest(
        tenant_id=uuid7(),
        subject=SubjectIdentifiers(
            full_name="John Doe",
            date_of_birth="1985-06-15",
        ),
        locale=Locale.US,
        service_tier=ServiceTier.STANDARD,
        search_degree=SearchDegree.D1,
        vigilance_level=VigilanceLevel.V0,
        role_category=RoleCategory.STANDARD,
        consent_token="valid-consent-token",
        priority=ScreeningPriority.NORMAL,
    )


def create_request(
    priority: ScreeningPriority = ScreeningPriority.NORMAL,
    tier: ServiceTier = ServiceTier.STANDARD,
    tenant_id=None,
) -> ScreeningRequest:
    """Helper to create screening requests."""
    return ScreeningRequest(
        tenant_id=tenant_id or uuid7(),
        subject=SubjectIdentifiers(
            full_name="Test Subject",
            date_of_birth="1990-01-01",
        ),
        locale=Locale.US,
        service_tier=tier,
        search_degree=SearchDegree.D1,
        vigilance_level=VigilanceLevel.V0,
        role_category=RoleCategory.STANDARD,
        consent_token="test-token",
        priority=priority,
    )


# =============================================================================
# QueuedScreening Tests
# =============================================================================


class TestQueuedScreening:
    """Tests for QueuedScreening data class."""

    def test_from_request(self, screening_request):
        """Test creating queued screening from request."""
        queued = QueuedScreening.from_request(screening_request)

        assert queued.screening_id == screening_request.screening_id
        assert queued.tenant_id == screening_request.tenant_id
        assert queued.tier == screening_request.service_tier
        assert queued.priority == screening_request.priority
        assert queued.priority_score > 0

    def test_priority_score_calculation(self):
        """Test priority score ordering."""
        urgent = create_request(priority=ScreeningPriority.URGENT)
        high = create_request(priority=ScreeningPriority.HIGH)
        normal = create_request(priority=ScreeningPriority.NORMAL)
        low = create_request(priority=ScreeningPriority.LOW)

        urgent_score = QueuedScreening._calculate_priority_score(urgent)
        high_score = QueuedScreening._calculate_priority_score(high)
        normal_score = QueuedScreening._calculate_priority_score(normal)
        low_score = QueuedScreening._calculate_priority_score(low)

        assert urgent_score > high_score > normal_score > low_score

    def test_enhanced_tier_bonus(self):
        """Test that enhanced tier gets priority bonus."""
        standard = create_request(tier=ServiceTier.STANDARD)
        enhanced = create_request(tier=ServiceTier.ENHANCED)

        standard_score = QueuedScreening._calculate_priority_score(standard)
        enhanced_score = QueuedScreening._calculate_priority_score(enhanced)

        assert enhanced_score > standard_score

    def test_to_dict_and_from_dict(self, screening_request):
        """Test serialization round-trip."""
        original = QueuedScreening.from_request(screening_request)
        data = original.to_dict()
        restored = QueuedScreening.from_dict(data)

        # Compare by string value since uuid_utils.UUID and uuid.UUID
        # don't compare equal directly despite having same value
        assert str(restored.queue_id) == str(original.queue_id)
        assert str(restored.screening_id) == str(original.screening_id)
        assert str(restored.tenant_id) == str(original.tenant_id)
        assert restored.priority_score == original.priority_score
        assert restored.tier == original.tier
        assert restored.priority == original.priority
        assert restored.retry_count == original.retry_count


# =============================================================================
# InMemoryQueueStorage Tests
# =============================================================================


class TestInMemoryQueueStorage:
    """Tests for in-memory queue storage."""

    @pytest.mark.asyncio
    async def test_enqueue_and_dequeue(self, screening_request):
        """Test basic enqueue and dequeue."""
        storage = InMemoryQueueStorage()
        queued = QueuedScreening.from_request(screening_request)

        result = await storage.enqueue(queued)
        assert result is True

        count = await storage.get_pending_count()
        assert count == 1

        dequeued = await storage.dequeue()
        assert dequeued is not None
        assert dequeued.screening_id == queued.screening_id

        count = await storage.get_pending_count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test that dequeue returns highest priority first."""
        storage = InMemoryQueueStorage()

        # Enqueue in reverse priority order
        low = QueuedScreening.from_request(create_request(ScreeningPriority.LOW))
        normal = QueuedScreening.from_request(create_request(ScreeningPriority.NORMAL))
        high = QueuedScreening.from_request(create_request(ScreeningPriority.HIGH))
        urgent = QueuedScreening.from_request(create_request(ScreeningPriority.URGENT))

        await storage.enqueue(low)
        await storage.enqueue(normal)
        await storage.enqueue(high)
        await storage.enqueue(urgent)

        # Dequeue should return in priority order
        first = await storage.dequeue()
        assert first.priority == ScreeningPriority.URGENT

        second = await storage.dequeue()
        assert second.priority == ScreeningPriority.HIGH

        third = await storage.dequeue()
        assert third.priority == ScreeningPriority.NORMAL

        fourth = await storage.dequeue()
        assert fourth.priority == ScreeningPriority.LOW

    @pytest.mark.asyncio
    async def test_tier_specific_dequeue(self):
        """Test dequeuing from specific tier."""
        storage = InMemoryQueueStorage()

        standard = QueuedScreening.from_request(create_request(tier=ServiceTier.STANDARD))
        enhanced = QueuedScreening.from_request(create_request(tier=ServiceTier.ENHANCED))

        await storage.enqueue(standard)
        await storage.enqueue(enhanced)

        # Dequeue only from standard tier
        result = await storage.dequeue(tier=ServiceTier.STANDARD)
        assert result.tier == ServiceTier.STANDARD

        # Enhanced should still be pending
        count = await storage.get_pending_count(ServiceTier.ENHANCED)
        assert count == 1

    @pytest.mark.asyncio
    async def test_peek_does_not_remove(self):
        """Test that peek doesn't remove from queue."""
        storage = InMemoryQueueStorage()
        queued = QueuedScreening.from_request(create_request())

        await storage.enqueue(queued)

        peeked = await storage.peek(limit=1)
        assert len(peeked) == 1

        count = await storage.get_pending_count()
        assert count == 1  # Still in queue

    @pytest.mark.asyncio
    async def test_remove(self):
        """Test removing specific screening."""
        storage = InMemoryQueueStorage()
        queued = QueuedScreening.from_request(create_request())

        await storage.enqueue(queued)
        result = await storage.remove(queued.queue_id)

        assert result is True
        count = await storage.get_pending_count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_requeue(self):
        """Test requeuing a failed screening."""
        storage = InMemoryQueueStorage()
        queued = QueuedScreening.from_request(create_request())

        await storage.enqueue(queued)
        dequeued = await storage.dequeue()

        # Requeue with incremented retry
        original_score = dequeued.priority_score
        await storage.requeue(dequeued)

        requeued = await storage.peek(limit=1)
        assert len(requeued) == 1
        assert requeued[0].retry_count == 1
        assert requeued[0].priority_score < original_score  # Reduced priority


# =============================================================================
# ScreeningQueueManager Tests
# =============================================================================


class TestScreeningQueueManager:
    """Tests for the queue manager."""

    @pytest.mark.asyncio
    async def test_enqueue_success(self, queue_manager, screening_request):
        """Test successful enqueue."""
        queued, rate_limit = await queue_manager.enqueue(screening_request, check_rate_limit=False)

        assert queued is not None
        assert rate_limit is None
        assert queued.screening_id == screening_request.screening_id

    @pytest.mark.asyncio
    async def test_dequeue_success(self, queue_manager, screening_request):
        """Test successful dequeue."""
        await queue_manager.enqueue(screening_request, check_rate_limit=False)

        result = await queue_manager.dequeue(worker_id="worker-1")

        assert result.success is True
        assert result.screening is not None
        assert result.screening.worker_id == "worker-1"

    @pytest.mark.asyncio
    async def test_dequeue_empty_queue(self, queue_manager):
        """Test dequeue from empty queue."""
        result = await queue_manager.dequeue(worker_id="worker-1")

        assert result.success is False
        assert result.error == "Queue empty"

    @pytest.mark.asyncio
    async def test_complete_screening(self, queue_manager, screening_request):
        """Test marking screening complete."""
        queued, _ = await queue_manager.enqueue(screening_request, check_rate_limit=False)
        await queue_manager.dequeue(worker_id="worker-1")

        result = await queue_manager.complete(queued.queue_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_fail_with_retry(self, queue_manager, screening_request):
        """Test handling failed screening with retry."""
        queued, _ = await queue_manager.enqueue(screening_request, check_rate_limit=False)
        dequeue_result = await queue_manager.dequeue(worker_id="worker-1")

        # Fail and retry
        screening = dequeue_result.screening
        await queue_manager.fail(queued.queue_id, screening, retry=True)

        # Should be back in queue
        metrics = await queue_manager.get_metrics()
        assert metrics.total_pending == 1

    @pytest.mark.asyncio
    async def test_fail_max_retries_exceeded(self, queue_manager, screening_request):
        """Test handling failed screening at max retries."""
        queued, _ = await queue_manager.enqueue(screening_request, check_rate_limit=False)
        dequeue_result = await queue_manager.dequeue(worker_id="worker-1")

        # Set retry count to max
        screening = dequeue_result.screening
        screening.retry_count = screening.max_retries

        await queue_manager.fail(queued.queue_id, screening, retry=True)

        # Should not be back in queue
        metrics = await queue_manager.get_metrics()
        assert metrics.total_pending == 0

    @pytest.mark.asyncio
    async def test_cancel_queued_screening(self, queue_manager, screening_request):
        """Test cancelling a queued screening."""
        queued, _ = await queue_manager.enqueue(screening_request, check_rate_limit=False)

        result = await queue_manager.cancel(queued.queue_id)

        assert result is True
        metrics = await queue_manager.get_metrics()
        assert metrics.total_pending == 0

    @pytest.mark.asyncio
    async def test_peek_queue(self, queue_manager):
        """Test peeking at queue contents."""
        # Enqueue multiple
        for _ in range(5):
            await queue_manager.enqueue(create_request(), check_rate_limit=False)

        peeked = await queue_manager.peek(limit=3)

        assert len(peeked) == 3

    @pytest.mark.asyncio
    async def test_get_metrics(self, queue_manager):
        """Test getting queue metrics."""
        # Enqueue some screenings
        await queue_manager.enqueue(
            create_request(tier=ServiceTier.STANDARD), check_rate_limit=False
        )
        await queue_manager.enqueue(
            create_request(tier=ServiceTier.ENHANCED), check_rate_limit=False
        )

        metrics = await queue_manager.get_metrics()

        assert metrics.total_pending == 2
        assert metrics.pending_by_tier[ServiceTier.STANDARD.value] == 1
        assert metrics.pending_by_tier[ServiceTier.ENHANCED.value] == 1
        assert metrics.queue_status == QueueStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_worker_heartbeat(self, queue_manager):
        """Test worker heartbeat recording."""
        await queue_manager.worker_heartbeat("worker-1")
        await queue_manager.worker_heartbeat("worker-2")

        workers = await queue_manager.get_active_workers()

        assert "worker-1" in workers
        assert "worker-2" in workers


# =============================================================================
# Priority Queue Tests
# =============================================================================


class TestPriorityQueue:
    """Tests for priority-based queueing behavior."""

    @pytest.mark.asyncio
    async def test_urgent_processed_first(self, queue_manager):
        """Test that urgent screenings are processed first."""
        # Enqueue in mixed order
        await queue_manager.enqueue(
            create_request(ScreeningPriority.NORMAL), check_rate_limit=False
        )
        await queue_manager.enqueue(create_request(ScreeningPriority.LOW), check_rate_limit=False)
        await queue_manager.enqueue(
            create_request(ScreeningPriority.URGENT), check_rate_limit=False
        )
        await queue_manager.enqueue(create_request(ScreeningPriority.HIGH), check_rate_limit=False)

        # Dequeue should return urgent first
        result = await queue_manager.dequeue("worker-1")
        assert result.screening.priority == ScreeningPriority.URGENT

        result = await queue_manager.dequeue("worker-1")
        assert result.screening.priority == ScreeningPriority.HIGH

    @pytest.mark.asyncio
    async def test_enhanced_tier_priority_over_standard(self, queue_manager):
        """Test enhanced tier priority in multi-tier dequeue."""
        # Both normal priority, but enhanced should come first
        await queue_manager.enqueue(
            create_request(tier=ServiceTier.STANDARD), check_rate_limit=False
        )
        await queue_manager.enqueue(
            create_request(tier=ServiceTier.ENHANCED), check_rate_limit=False
        )

        # Default dequeue checks enhanced first
        result = await queue_manager.dequeue("worker-1")
        assert result.screening.tier == ServiceTier.ENHANCED


# =============================================================================
# Load Balancing Tests
# =============================================================================


class TestLoadBalancing:
    """Tests for load balancing features."""

    @pytest.mark.asyncio
    async def test_multiple_workers_get_work(self, queue_manager):
        """Test that multiple workers can get work."""
        # Enqueue multiple screenings
        for _ in range(5):
            await queue_manager.enqueue(create_request(), check_rate_limit=False)

        # Multiple workers dequeue
        r1 = await queue_manager.dequeue("worker-1")
        r2 = await queue_manager.dequeue("worker-2")
        r3 = await queue_manager.dequeue("worker-3")

        assert r1.success and r2.success and r3.success
        assert r1.screening.worker_id == "worker-1"
        assert r2.screening.worker_id == "worker-2"
        assert r3.screening.worker_id == "worker-3"

    @pytest.mark.asyncio
    async def test_worker_heartbeat_tracking(self, queue_manager):
        """Test worker heartbeat and active worker tracking."""
        # Workers check in
        await queue_manager.worker_heartbeat("worker-1")
        await queue_manager.worker_heartbeat("worker-2")

        workers = await queue_manager.get_active_workers()
        assert len(workers) == 2


# =============================================================================
# Queue Monitoring Tests
# =============================================================================


class TestQueueMonitoring:
    """Tests for queue monitoring and metrics."""

    @pytest.mark.asyncio
    async def test_metrics_accuracy(self, queue_manager):
        """Test that metrics accurately reflect queue state."""
        # Start with empty
        metrics = await queue_manager.get_metrics()
        assert metrics.total_pending == 0
        assert metrics.total_processing == 0

        # Enqueue
        await queue_manager.enqueue(create_request(), check_rate_limit=False)
        metrics = await queue_manager.get_metrics()
        assert metrics.total_pending == 1

        # Dequeue (now processing)
        result = await queue_manager.dequeue("worker-1")
        metrics = await queue_manager.get_metrics()
        assert metrics.total_pending == 0
        assert metrics.total_processing == 1

        # Complete
        await queue_manager.complete(result.screening.queue_id)
        metrics = await queue_manager.get_metrics()
        assert metrics.total_processing == 0

    @pytest.mark.asyncio
    async def test_queue_status_healthy(self, config):
        """Test healthy queue status."""
        config.max_concurrent_standard = 100
        queue_manager = create_queue_manager(config=config, use_redis=False)

        metrics = await queue_manager.get_metrics()
        assert metrics.queue_status == QueueStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_oldest_pending_tracking(self, queue_manager):
        """Test tracking of oldest pending screening."""
        await queue_manager.enqueue(create_request(), check_rate_limit=False)

        metrics = await queue_manager.get_metrics()

        # Should have some age (very small since just added)
        assert metrics.oldest_pending_age_seconds >= 0


# =============================================================================
# Configuration Tests
# =============================================================================


class TestQueueConfig:
    """Tests for queue configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = QueueConfig()

        assert config.max_concurrent_standard == 50
        assert config.max_concurrent_enhanced == 20
        assert config.rate_limit_per_tenant == 100
        assert config.max_retries == 3

    def test_custom_config(self):
        """Test custom configuration values."""
        config = QueueConfig(
            max_concurrent_standard=100,
            max_concurrent_enhanced=50,
            rate_limit_per_tenant=200,
            max_retries=5,
        )

        assert config.max_concurrent_standard == 100
        assert config.max_concurrent_enhanced == 50
        assert config.rate_limit_per_tenant == 200
        assert config.max_retries == 5


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_queue_manager_in_memory(self, config):
        """Test creating in-memory queue manager."""
        manager = create_queue_manager(config=config, use_redis=False)

        assert manager is not None
        assert isinstance(manager.storage, InMemoryQueueStorage)

    def test_create_queue_manager_default_config(self):
        """Test creating queue manager with default config."""
        manager = create_queue_manager(use_redis=False)

        assert manager is not None
        assert manager.config.max_concurrent_standard == 50
