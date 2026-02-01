"""Unit tests for screening state manager.

Tests state persistence, progress tracking, and resumption.
"""

import pytest
from uuid_utils import uuid7

from elile.screening.state_manager import (
    InMemoryStateStore,
    ProgressEvent,
    ProgressEventType,
    ScreeningPhase,
    ScreeningState,
    ScreeningStateManager,
    StateManagerConfig,
    create_state_manager,
)
from elile.screening.types import ScreeningResult, ScreeningStatus


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def config():
    """Create test configuration."""
    return StateManagerConfig(
        auto_save_interval_seconds=10,
        save_on_phase_change=True,
        max_retries=3,
        emit_progress_events=True,
    )


@pytest.fixture
def store():
    """Create in-memory store."""
    return InMemoryStateStore()


@pytest.fixture
def manager(store, config):
    """Create state manager."""
    return ScreeningStateManager(store=store, config=config)


@pytest.fixture
def screening_id():
    """Create screening ID."""
    return uuid7()


@pytest.fixture
def tenant_id():
    """Create tenant ID."""
    return uuid7()


# =============================================================================
# ScreeningState Tests
# =============================================================================


class TestScreeningState:
    """Tests for ScreeningState."""

    def test_create_state(self):
        """Test state creation."""
        state = ScreeningState()

        assert state.status == ScreeningStatus.PENDING
        assert state.current_phase == ScreeningPhase.PENDING
        assert state.progress_percent == 0.0
        assert state.retry_count == 0

    def test_to_dict(self):
        """Test state serialization."""
        state = ScreeningState(
            status=ScreeningStatus.IN_PROGRESS,
            current_phase=ScreeningPhase.INVESTIGATION,
            progress_percent=45.0,
        )

        data = state.to_dict()

        assert data["status"] == "in_progress"
        assert data["current_phase"] == "investigation"
        assert data["progress_percent"] == 45.0

    def test_from_dict(self):
        """Test state deserialization."""
        data = {
            "state_id": str(uuid7()),
            "screening_id": str(uuid7()),
            "status": "in_progress",
            "current_phase": "risk_analysis",
            "progress_percent": 75.0,
            "completed_phases": ["validation", "compliance"],
            "phase_results": {},
            "retry_count": 1,
            "max_retries": 3,
            "checkpoint_version": 5,
        }

        state = ScreeningState.from_dict(data)

        assert state.status == ScreeningStatus.IN_PROGRESS
        assert state.current_phase == ScreeningPhase.RISK_ANALYSIS
        assert state.progress_percent == 75.0
        assert len(state.completed_phases) == 2
        assert state.retry_count == 1

    def test_roundtrip_serialization(self):
        """Test state serialization roundtrip."""
        original = ScreeningState(
            status=ScreeningStatus.ANALYZING,
            current_phase=ScreeningPhase.RISK_ANALYSIS,
            progress_percent=80.0,
            completed_phases=["validation", "compliance", "consent", "investigation"],
            retry_count=2,
        )

        data = original.to_dict()
        restored = ScreeningState.from_dict(data)

        assert restored.status == original.status
        assert restored.current_phase == original.current_phase
        assert restored.progress_percent == original.progress_percent
        assert restored.completed_phases == original.completed_phases


# =============================================================================
# ProgressEvent Tests
# =============================================================================


class TestProgressEvent:
    """Tests for ProgressEvent."""

    def test_create_event(self):
        """Test event creation."""
        event = ProgressEvent(
            screening_id=uuid7(),
            event_type=ProgressEventType.PHASE_STARTED,
            phase=ScreeningPhase.INVESTIGATION,
            progress_percent=25.0,
            message="Starting investigation",
        )

        assert event.event_type == ProgressEventType.PHASE_STARTED
        assert event.phase == ScreeningPhase.INVESTIGATION

    def test_to_dict(self):
        """Test event serialization."""
        event = ProgressEvent(
            event_type=ProgressEventType.PROGRESS_UPDATE,
            progress_percent=50.0,
            message="Halfway done",
        )

        data = event.to_dict()

        assert data["event_type"] == "progress_update"
        assert data["progress_percent"] == 50.0
        assert data["message"] == "Halfway done"


# =============================================================================
# InMemoryStateStore Tests
# =============================================================================


class TestInMemoryStateStore:
    """Tests for InMemoryStateStore."""

    @pytest.mark.asyncio
    async def test_save_and_load(self):
        """Test save and load."""
        store = InMemoryStateStore()
        screening_id = uuid7()
        state = ScreeningState(screening_id=screening_id)

        await store.save(screening_id, state)
        loaded = await store.load(screening_id)

        assert loaded is not None
        assert loaded.screening_id == screening_id

    @pytest.mark.asyncio
    async def test_load_not_found(self):
        """Test load nonexistent state."""
        store = InMemoryStateStore()

        loaded = await store.load(uuid7())

        assert loaded is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test delete."""
        store = InMemoryStateStore()
        screening_id = uuid7()
        state = ScreeningState(screening_id=screening_id)

        await store.save(screening_id, state)
        deleted = await store.delete(screening_id)
        loaded = await store.load(screening_id)

        assert deleted is True
        assert loaded is None

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """Test delete nonexistent."""
        store = InMemoryStateStore()

        deleted = await store.delete(uuid7())

        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_by_status(self):
        """Test list by status."""
        store = InMemoryStateStore()
        tenant_id = uuid7()

        # Create states with different statuses
        pending = ScreeningState(
            screening_id=uuid7(),
            tenant_id=tenant_id,
            status=ScreeningStatus.PENDING,
        )
        in_progress = ScreeningState(
            screening_id=uuid7(),
            tenant_id=tenant_id,
            status=ScreeningStatus.IN_PROGRESS,
        )
        complete = ScreeningState(
            screening_id=uuid7(),
            tenant_id=tenant_id,
            status=ScreeningStatus.COMPLETE,
        )

        await store.save(pending.screening_id, pending)
        await store.save(in_progress.screening_id, in_progress)
        await store.save(complete.screening_id, complete)

        # Query by status
        pending_list = await store.list_by_status(ScreeningStatus.PENDING)
        in_progress_list = await store.list_by_status(ScreeningStatus.IN_PROGRESS)

        assert len(pending_list) == 1
        assert len(in_progress_list) == 1


# =============================================================================
# ScreeningStateManager Tests
# =============================================================================


class TestScreeningStateManager:
    """Tests for ScreeningStateManager."""

    def test_create_manager(self, config, store):
        """Test manager creation."""
        manager = create_state_manager(store=store, config=config)

        assert manager is not None
        assert manager.config == config

    @pytest.mark.asyncio
    async def test_create_state(self, manager, screening_id, tenant_id):
        """Test creating initial state."""
        state = await manager.create_state(screening_id, tenant_id)

        assert state is not None
        assert state.screening_id == screening_id
        assert state.tenant_id == tenant_id
        assert state.status == ScreeningStatus.PENDING

    @pytest.mark.asyncio
    async def test_save_and_load_state(self, manager, screening_id):
        """Test save and load."""
        state = await manager.create_state(screening_id)
        state.progress_percent = 50.0

        await manager.save_state(screening_id, state)
        loaded = await manager.load_state(screening_id)

        assert loaded is not None
        assert loaded.progress_percent == 50.0

    @pytest.mark.asyncio
    async def test_delete_state(self, manager, screening_id):
        """Test delete."""
        await manager.create_state(screening_id)
        deleted = await manager.delete_state(screening_id)
        loaded = await manager.load_state(screening_id)

        assert deleted is True
        assert loaded is None

    # Phase Management Tests

    @pytest.mark.asyncio
    async def test_start_phase(self, manager, screening_id):
        """Test starting a phase."""
        await manager.create_state(screening_id)

        state = await manager.start_phase(screening_id, ScreeningPhase.VALIDATION)

        assert state is not None
        assert state.current_phase == ScreeningPhase.VALIDATION
        assert state.status == ScreeningStatus.VALIDATING
        assert ScreeningPhase.VALIDATION.value in state.phase_results

    @pytest.mark.asyncio
    async def test_complete_phase(self, manager, screening_id):
        """Test completing a phase."""
        await manager.create_state(screening_id)
        await manager.start_phase(screening_id, ScreeningPhase.VALIDATION)

        state = await manager.complete_phase(
            screening_id,
            ScreeningPhase.VALIDATION,
            details={"checks_passed": 5},
        )

        assert state is not None
        assert ScreeningPhase.VALIDATION.value in state.completed_phases
        assert state.progress_percent > 0

    @pytest.mark.asyncio
    async def test_fail_phase(self, manager, screening_id):
        """Test failing a phase."""
        await manager.create_state(screening_id)
        await manager.start_phase(screening_id, ScreeningPhase.INVESTIGATION)

        state = await manager.fail_phase(
            screening_id,
            ScreeningPhase.INVESTIGATION,
            error="Provider timeout",
        )

        assert state is not None
        assert state.last_error == "Provider timeout"
        assert state.error_phase == ScreeningPhase.INVESTIGATION
        assert state.retry_count == 1

    @pytest.mark.asyncio
    async def test_fail_phase_max_retries(self, manager, screening_id):
        """Test failing phase exceeds max retries."""
        state = await manager.create_state(screening_id)
        state.retry_count = 2  # Already retried twice
        await manager.save_state(screening_id, state)

        await manager.start_phase(screening_id, ScreeningPhase.INVESTIGATION)
        state = await manager.fail_phase(
            screening_id,
            ScreeningPhase.INVESTIGATION,
            error="Third failure",
        )

        assert state.status == ScreeningStatus.FAILED
        assert state.current_phase == ScreeningPhase.FAILED

    # Progress Tracking Tests

    @pytest.mark.asyncio
    async def test_update_progress(self, manager, screening_id):
        """Test updating progress."""
        await manager.create_state(screening_id)

        state = await manager.update_progress(screening_id, 65.5, "Processing...")

        assert state is not None
        assert state.progress_percent == 65.5

    @pytest.mark.asyncio
    async def test_update_progress_bounds(self, manager, screening_id):
        """Test progress is bounded 0-100."""
        await manager.create_state(screening_id)

        state = await manager.update_progress(screening_id, 150.0)
        assert state.progress_percent == 100.0

        state = await manager.update_progress(screening_id, -10.0)
        assert state.progress_percent == 0.0

    @pytest.mark.asyncio
    async def test_progress_calculation(self, manager, screening_id):
        """Test automatic progress calculation."""
        await manager.create_state(screening_id)

        # Complete phases and check progress increases
        await manager.start_phase(screening_id, ScreeningPhase.VALIDATION)
        state = await manager.complete_phase(screening_id, ScreeningPhase.VALIDATION)
        progress1 = state.progress_percent

        await manager.start_phase(screening_id, ScreeningPhase.COMPLIANCE)
        state = await manager.complete_phase(screening_id, ScreeningPhase.COMPLIANCE)
        progress2 = state.progress_percent

        assert progress2 > progress1

    # Resumption Tests

    @pytest.mark.asyncio
    async def test_can_resume_pending(self, manager, screening_id):
        """Test can resume pending screening."""
        await manager.create_state(screening_id)

        can_resume = await manager.can_resume(screening_id)

        # Pending screenings can be resumed (started)
        assert can_resume is True

    @pytest.mark.asyncio
    async def test_can_resume_failed(self, manager, screening_id):
        """Test can resume failed screening."""
        state = await manager.create_state(screening_id)
        state.status = ScreeningStatus.FAILED
        state.retry_count = 1
        await manager.save_state(screening_id, state)

        can_resume = await manager.can_resume(screening_id)

        assert can_resume is True

    @pytest.mark.asyncio
    async def test_cannot_resume_completed(self, manager, screening_id):
        """Test cannot resume completed screening."""
        state = await manager.create_state(screening_id)
        state.status = ScreeningStatus.COMPLETE
        await manager.save_state(screening_id, state)

        can_resume = await manager.can_resume(screening_id)

        assert can_resume is False

    @pytest.mark.asyncio
    async def test_cannot_resume_max_retries(self, manager, screening_id):
        """Test cannot resume after max retries."""
        state = await manager.create_state(screening_id)
        state.status = ScreeningStatus.FAILED
        state.retry_count = 3  # Max retries
        await manager.save_state(screening_id, state)

        can_resume = await manager.can_resume(screening_id)

        assert can_resume is False

    @pytest.mark.asyncio
    async def test_get_resume_point(self, manager, screening_id):
        """Test getting resume point."""
        state = await manager.create_state(screening_id)
        state.error_phase = ScreeningPhase.INVESTIGATION
        await manager.save_state(screening_id, state)

        resume_point = await manager.get_resume_point(screening_id)

        assert resume_point == ScreeningPhase.INVESTIGATION

    @pytest.mark.asyncio
    async def test_prepare_for_resume(self, manager, screening_id):
        """Test preparing for resume."""
        state = await manager.create_state(screening_id)
        state.status = ScreeningStatus.FAILED
        state.last_error = "Previous error"
        await manager.save_state(screening_id, state)

        state = await manager.prepare_for_resume(screening_id)

        assert state.status == ScreeningStatus.IN_PROGRESS
        assert state.last_error is None

    # Completion Tests

    @pytest.mark.asyncio
    async def test_complete_screening(self, manager, screening_id):
        """Test completing screening."""
        await manager.create_state(screening_id)

        result = ScreeningResult(
            screening_id=screening_id,
            risk_score=25,
            risk_level="low",
        )

        state = await manager.complete_screening(screening_id, result)

        assert state.status == ScreeningStatus.COMPLETE
        assert state.current_phase == ScreeningPhase.COMPLETE
        assert state.progress_percent == 100.0
        assert state.completed_at is not None
        assert state.checkpoint_data["risk_score"] == 25

    @pytest.mark.asyncio
    async def test_cancel_screening(self, manager, screening_id):
        """Test cancelling screening."""
        await manager.create_state(screening_id)

        state = await manager.cancel_screening(screening_id, reason="User requested")

        assert state.status == ScreeningStatus.CANCELLED
        assert state.current_phase == ScreeningPhase.CANCELLED
        assert state.checkpoint_data["cancellation_reason"] == "User requested"

    # Progress Callback Tests

    @pytest.mark.asyncio
    async def test_progress_callback(self, manager, screening_id):
        """Test progress callbacks."""
        events = []

        def on_progress(event):
            events.append(event)

        manager.on_progress(on_progress)
        await manager.create_state(screening_id)
        await manager.start_phase(screening_id, ScreeningPhase.VALIDATION)

        # Should have received events
        assert len(events) > 0
        assert any(e.event_type == ProgressEventType.PHASE_STARTED for e in events)

    @pytest.mark.asyncio
    async def test_remove_progress_callback(self, manager, screening_id):
        """Test removing progress callback."""
        events = []

        def on_progress(event):
            events.append(event)

        manager.on_progress(on_progress)
        manager.remove_progress_callback(on_progress)

        await manager.create_state(screening_id)

        # Should not receive events after removal
        # (only checkpoint event, no callback)
        assert len(events) == 0

    # Query Tests

    @pytest.mark.asyncio
    async def test_get_pending_screenings(self, manager):
        """Test getting pending screenings."""
        tenant_id = uuid7()

        # Create pending screening
        state1 = await manager.create_state(uuid7(), tenant_id)

        # Create and complete another
        state2 = await manager.create_state(uuid7(), tenant_id)
        await manager.complete_screening(state2.screening_id)

        pending = await manager.get_pending_screenings(tenant_id)

        assert len(pending) == 1
        assert pending[0].screening_id == state1.screening_id

    @pytest.mark.asyncio
    async def test_get_failed_screenings(self, manager):
        """Test getting failed screenings."""
        tenant_id = uuid7()

        # Create and fail a screening
        state = await manager.create_state(uuid7(), tenant_id)
        state.status = ScreeningStatus.FAILED
        await manager.save_state(state.screening_id, state)

        failed = await manager.get_failed_screenings(tenant_id)

        assert len(failed) == 1

    @pytest.mark.asyncio
    async def test_get_resumable_screenings(self, manager):
        """Test getting resumable screenings."""
        tenant_id = uuid7()

        # Create resumable (failed but retries remaining)
        state1 = await manager.create_state(uuid7(), tenant_id)
        state1.status = ScreeningStatus.FAILED
        state1.retry_count = 1
        await manager.save_state(state1.screening_id, state1)

        # Create non-resumable (max retries)
        state2 = await manager.create_state(uuid7(), tenant_id)
        state2.status = ScreeningStatus.FAILED
        state2.retry_count = 3
        await manager.save_state(state2.screening_id, state2)

        resumable = await manager.get_resumable_screenings(tenant_id)

        assert len(resumable) == 1
        assert resumable[0].screening_id == state1.screening_id


# =============================================================================
# Configuration Tests
# =============================================================================


class TestStateManagerConfig:
    """Tests for StateManagerConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = StateManagerConfig()

        assert config.max_retries == 3
        assert config.save_on_phase_change is True
        assert config.emit_progress_events is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = StateManagerConfig(
            max_retries=5,
            retry_delay_seconds=120,
            save_on_phase_change=False,
        )

        assert config.max_retries == 5
        assert config.retry_delay_seconds == 120
        assert config.save_on_phase_change is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestStateManagerIntegration:
    """Integration tests for state manager."""

    @pytest.mark.asyncio
    async def test_full_screening_lifecycle(self, manager):
        """Test full screening lifecycle."""
        screening_id = uuid7()

        # Create
        await manager.create_state(screening_id)

        # Progress through phases
        phases = [
            ScreeningPhase.VALIDATION,
            ScreeningPhase.COMPLIANCE,
            ScreeningPhase.CONSENT,
            ScreeningPhase.INVESTIGATION,
            ScreeningPhase.RISK_ANALYSIS,
            ScreeningPhase.REPORT_GENERATION,
        ]

        for phase in phases:
            await manager.start_phase(screening_id, phase)
            await manager.complete_phase(screening_id, phase)

        # Complete
        result = ScreeningResult(screening_id=screening_id, risk_score=30)
        state = await manager.complete_screening(screening_id, result)

        assert state.status == ScreeningStatus.COMPLETE
        assert state.progress_percent == 100.0
        assert len(state.completed_phases) == 6

    @pytest.mark.asyncio
    async def test_failure_and_resume(self, manager):
        """Test failure and resumption."""
        screening_id = uuid7()

        # Create and progress
        await manager.create_state(screening_id)
        await manager.start_phase(screening_id, ScreeningPhase.VALIDATION)
        await manager.complete_phase(screening_id, ScreeningPhase.VALIDATION)
        await manager.start_phase(screening_id, ScreeningPhase.INVESTIGATION)

        # Fail
        await manager.fail_phase(screening_id, ScreeningPhase.INVESTIGATION, "Error")

        # Check resumable
        assert await manager.can_resume(screening_id) is True
        resume_point = await manager.get_resume_point(screening_id)
        assert resume_point == ScreeningPhase.INVESTIGATION

        # Resume
        await manager.prepare_for_resume(screening_id)
        state = await manager.load_state(screening_id)
        assert state.status == ScreeningStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_multiple_screenings(self, manager):
        """Test managing multiple screenings."""
        tenant_id = uuid7()
        screening_ids = [uuid7() for _ in range(5)]

        # Create all
        for sid in screening_ids:
            await manager.create_state(sid, tenant_id)

        # Progress some
        await manager.start_phase(screening_ids[0], ScreeningPhase.VALIDATION)
        await manager.complete_phase(screening_ids[0], ScreeningPhase.VALIDATION)

        # Fail one
        state = await manager.load_state(screening_ids[1])
        state.status = ScreeningStatus.FAILED
        await manager.save_state(screening_ids[1], state)

        # Complete one
        await manager.complete_screening(screening_ids[2])

        # Query states
        pending = await manager.get_pending_screenings(tenant_id)
        failed = await manager.get_failed_screenings(tenant_id)

        # screening_ids[3] and [4] are still pending (2 total)
        # screening_ids[0] is in_progress after completing validation
        # So we might have 2 pending
        assert len(pending) >= 2
        assert len(failed) == 1
