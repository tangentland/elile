"""Tests for the screening progress tracker.

Tests cover:
- Progress initialization and tracking
- Phase/step management
- ETA calculation
- Stall detection
- Progress notifications
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from elile.screening.progress import (
    ETAEstimate,
    HistoricalDuration,
    PhaseProgress,
    ProgressNotification,
    ProgressNotificationType,
    ProgressStep,
    ProgressTracker,
    ProgressTrackerConfig,
    ScreeningProgress,
    StallReason,
    create_progress_tracker,
    get_progress_tracker,
    reset_progress_tracker,
)
from elile.screening.state_manager import ScreeningPhase
from elile.screening.types import ScreeningStatus

# =============================================================================
# ProgressStep Tests
# =============================================================================


class TestProgressStep:
    """Tests for ProgressStep dataclass."""

    def test_create_step(self) -> None:
        """Test creating a progress step."""
        step = ProgressStep(
            step_id="step-1",
            step_name="Verify Identity",
            phase=ScreeningPhase.VALIDATION,
        )
        assert step.step_id == "step-1"
        assert step.step_name == "Verify Identity"
        assert step.phase == ScreeningPhase.VALIDATION
        assert step.status == "pending"
        assert step.progress_percent == 0.0

    def test_start_step(self) -> None:
        """Test starting a step."""
        step = ProgressStep(
            step_id="step-1",
            step_name="Test",
            phase=ScreeningPhase.VALIDATION,
        )
        step.start()
        assert step.status == "in_progress"
        assert step.started_at is not None

    def test_complete_step(self) -> None:
        """Test completing a step."""
        step = ProgressStep(
            step_id="step-1",
            step_name="Test",
            phase=ScreeningPhase.VALIDATION,
        )
        step.start()
        step.complete()
        assert step.status == "complete"
        assert step.progress_percent == 100.0
        assert step.completed_at is not None

    def test_fail_step(self) -> None:
        """Test failing a step."""
        step = ProgressStep(
            step_id="step-1",
            step_name="Test",
            phase=ScreeningPhase.VALIDATION,
        )
        step.start()
        step.fail("Error occurred")
        assert step.status == "failed"
        assert step.error_message == "Error occurred"
        assert step.completed_at is not None

    def test_duration_seconds(self) -> None:
        """Test calculating step duration."""
        step = ProgressStep(
            step_id="step-1",
            step_name="Test",
            phase=ScreeningPhase.VALIDATION,
        )
        assert step.duration_seconds is None  # Not started

        step.start()
        duration = step.duration_seconds
        assert duration is not None
        assert duration >= 0

    def test_to_dict(self) -> None:
        """Test converting step to dictionary."""
        step = ProgressStep(
            step_id="step-1",
            step_name="Test",
            phase=ScreeningPhase.VALIDATION,
        )
        result = step.to_dict()
        assert result["step_id"] == "step-1"
        assert result["step_name"] == "Test"
        assert result["phase"] == "validation"


# =============================================================================
# PhaseProgress Tests
# =============================================================================


class TestPhaseProgress:
    """Tests for PhaseProgress dataclass."""

    def test_create_phase_progress(self) -> None:
        """Test creating phase progress."""
        phase = PhaseProgress(phase=ScreeningPhase.INVESTIGATION)
        assert phase.phase == ScreeningPhase.INVESTIGATION
        assert phase.status == "pending"
        assert phase.progress_percent == 0.0

    def test_start_phase(self) -> None:
        """Test starting a phase."""
        phase = PhaseProgress(phase=ScreeningPhase.INVESTIGATION)
        phase.start()
        assert phase.status == "in_progress"
        assert phase.started_at is not None

    def test_complete_phase(self) -> None:
        """Test completing a phase."""
        phase = PhaseProgress(phase=ScreeningPhase.INVESTIGATION)
        phase.start()
        phase.complete()
        assert phase.status == "complete"
        assert phase.progress_percent == 100.0

    def test_fail_phase(self) -> None:
        """Test failing a phase."""
        phase = PhaseProgress(phase=ScreeningPhase.INVESTIGATION)
        phase.start()
        phase.fail("Phase failed")
        assert phase.status == "failed"
        assert phase.error_message == "Phase failed"

    def test_update_progress_from_steps(self) -> None:
        """Test updating phase progress from steps."""
        phase = PhaseProgress(phase=ScreeningPhase.INVESTIGATION)
        phase.steps = [
            ProgressStep("s1", "Step 1", ScreeningPhase.INVESTIGATION),
            ProgressStep("s2", "Step 2", ScreeningPhase.INVESTIGATION),
        ]
        phase.steps[0].progress_percent = 100.0
        phase.steps[1].progress_percent = 50.0

        phase.update_progress_from_steps()
        assert phase.progress_percent == 75.0

    def test_to_dict(self) -> None:
        """Test converting phase to dictionary."""
        phase = PhaseProgress(phase=ScreeningPhase.INVESTIGATION)
        result = phase.to_dict()
        assert result["phase"] == "investigation"
        assert result["status"] == "pending"


# =============================================================================
# ETAEstimate Tests
# =============================================================================


class TestETAEstimate:
    """Tests for ETAEstimate dataclass."""

    def test_create_eta(self) -> None:
        """Test creating an ETA estimate."""
        eta = ETAEstimate(
            remaining_seconds=120.0,
            confidence=0.8,
        )
        assert eta.remaining_seconds == 120.0
        assert eta.confidence == 0.8

    def test_remaining_human_readable_seconds(self) -> None:
        """Test human-readable format for seconds."""
        eta = ETAEstimate(remaining_seconds=45.0)
        assert eta.remaining_human_readable == "45s"

    def test_remaining_human_readable_minutes(self) -> None:
        """Test human-readable format for minutes."""
        eta = ETAEstimate(remaining_seconds=180.0)
        assert eta.remaining_human_readable == "3m"

    def test_remaining_human_readable_hours(self) -> None:
        """Test human-readable format for hours."""
        eta = ETAEstimate(remaining_seconds=5400.0)  # 1.5 hours
        assert eta.remaining_human_readable == "1h 30m"

    def test_remaining_human_readable_unknown(self) -> None:
        """Test human-readable format when unknown."""
        eta = ETAEstimate()
        assert eta.remaining_human_readable == "Unknown"

    def test_to_dict(self) -> None:
        """Test converting ETA to dictionary."""
        eta = ETAEstimate(remaining_seconds=60.0, confidence=0.5)
        result = eta.to_dict()
        assert result["remaining_seconds"] == 60.0
        assert result["confidence"] == 0.5


# =============================================================================
# ScreeningProgress Tests
# =============================================================================


class TestScreeningProgress:
    """Tests for ScreeningProgress dataclass."""

    def test_create_progress(self) -> None:
        """Test creating screening progress."""
        screening_id = uuid4()
        progress = ScreeningProgress(screening_id=screening_id)
        assert progress.screening_id == screening_id
        assert progress.overall_progress == 0.0
        assert progress.is_stalled is False

    def test_update_overall_progress(self) -> None:
        """Test calculating overall progress from phases."""
        screening_id = uuid4()
        progress = ScreeningProgress(screening_id=screening_id)

        # Add completed phases
        progress.phases["validation"] = PhaseProgress(
            phase=ScreeningPhase.VALIDATION, progress_percent=100.0
        )
        progress.phases["compliance"] = PhaseProgress(
            phase=ScreeningPhase.COMPLIANCE, progress_percent=100.0
        )
        progress.phases["investigation"] = PhaseProgress(
            phase=ScreeningPhase.INVESTIGATION, progress_percent=50.0
        )

        progress.update_overall_progress()
        # validation=5%, compliance=5%, investigation=50%*0.5=25% = 35%
        assert progress.overall_progress == 35.0

    def test_to_dict(self) -> None:
        """Test converting progress to dictionary."""
        screening_id = uuid4()
        progress = ScreeningProgress(screening_id=screening_id)
        result = progress.to_dict()
        assert result["screening_id"] == str(screening_id)
        assert result["overall_progress"] == 0.0


# =============================================================================
# ProgressNotification Tests
# =============================================================================


class TestProgressNotification:
    """Tests for ProgressNotification dataclass."""

    def test_create_notification(self) -> None:
        """Test creating a notification."""
        screening_id = uuid4()
        notification = ProgressNotification(
            screening_id=screening_id,
            notification_type=ProgressNotificationType.MILESTONE_REACHED,
            progress_percent=50.0,
            message="50% complete",
        )
        assert notification.screening_id == screening_id
        assert notification.notification_type == ProgressNotificationType.MILESTONE_REACHED
        assert notification.progress_percent == 50.0

    def test_to_dict(self) -> None:
        """Test converting notification to dictionary."""
        screening_id = uuid4()
        notification = ProgressNotification(
            screening_id=screening_id,
            notification_type=ProgressNotificationType.PROGRESS_UPDATE,
        )
        result = notification.to_dict()
        assert result["screening_id"] == str(screening_id)
        assert result["notification_type"] == "progress_update"


# =============================================================================
# HistoricalDuration Tests
# =============================================================================


class TestHistoricalDuration:
    """Tests for HistoricalDuration dataclass."""

    def test_create_historical(self) -> None:
        """Test creating historical duration tracker."""
        historical = HistoricalDuration(phase=ScreeningPhase.INVESTIGATION)
        assert historical.phase == ScreeningPhase.INVESTIGATION
        assert len(historical.durations_seconds) == 0

    def test_avg_duration(self) -> None:
        """Test calculating average duration."""
        historical = HistoricalDuration(phase=ScreeningPhase.INVESTIGATION)
        historical.durations_seconds = [100.0, 200.0, 300.0]
        assert historical.avg_duration == 200.0

    def test_stddev_duration(self) -> None:
        """Test calculating standard deviation."""
        historical = HistoricalDuration(phase=ScreeningPhase.INVESTIGATION)
        historical.durations_seconds = [100.0, 200.0, 300.0]
        assert historical.stddev_duration is not None
        assert historical.stddev_duration > 0

    def test_add_sample(self) -> None:
        """Test adding duration samples."""
        historical = HistoricalDuration(phase=ScreeningPhase.INVESTIGATION)
        historical.add_sample(100.0)
        historical.add_sample(200.0)
        assert len(historical.durations_seconds) == 2

    def test_sample_limit(self) -> None:
        """Test that samples are limited to 100."""
        historical = HistoricalDuration(phase=ScreeningPhase.INVESTIGATION)
        for i in range(150):
            historical.add_sample(float(i))
        assert len(historical.durations_seconds) == 100
        # Should keep last 100
        assert historical.durations_seconds[0] == 50.0


# =============================================================================
# ProgressTrackerConfig Tests
# =============================================================================


class TestProgressTrackerConfig:
    """Tests for ProgressTrackerConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ProgressTrackerConfig()
        assert config.stall_timeout_seconds == 300
        assert config.emit_notifications is True
        assert 25 in config.milestone_percentages

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = ProgressTrackerConfig(
            stall_timeout_seconds=600,
            emit_notifications=False,
        )
        assert config.stall_timeout_seconds == 600
        assert config.emit_notifications is False


# =============================================================================
# ProgressTracker Tests
# =============================================================================


class TestProgressTracker:
    """Tests for ProgressTracker class."""

    @pytest.fixture
    def tracker(self) -> ProgressTracker:
        """Create a tracker for testing."""
        return create_progress_tracker()

    @pytest.mark.asyncio
    async def test_initialize_progress(self, tracker: ProgressTracker) -> None:
        """Test initializing progress for a screening."""
        screening_id = uuid4()
        tenant_id = uuid4()

        progress = await tracker.initialize_progress(screening_id, tenant_id)

        assert progress.screening_id == screening_id
        assert progress.tenant_id == tenant_id
        assert progress.overall_progress == 0.0
        assert len(progress.phases) == 6  # All 6 phases initialized

    @pytest.mark.asyncio
    async def test_get_progress(self, tracker: ProgressTracker) -> None:
        """Test getting progress for a screening."""
        screening_id = uuid4()

        # Not found initially
        progress = await tracker.get_progress(screening_id)
        assert progress is None

        # Found after initialization
        await tracker.initialize_progress(screening_id)
        progress = await tracker.get_progress(screening_id)
        assert progress is not None
        assert progress.screening_id == screening_id

    @pytest.mark.asyncio
    async def test_update_progress(self, tracker: ProgressTracker) -> None:
        """Test updating screening progress."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)

        progress = await tracker.update_progress(
            screening_id,
            phase=ScreeningPhase.INVESTIGATION,
            step="Running SAR loop",
            progress_percent=50.0,
        )

        assert progress is not None
        assert progress.current_phase == ScreeningPhase.INVESTIGATION
        assert progress.current_step == "Running SAR loop"
        assert progress.phases["investigation"].progress_percent == 50.0

    @pytest.mark.asyncio
    async def test_start_phase(self, tracker: ProgressTracker) -> None:
        """Test starting a phase."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)

        progress = await tracker.start_phase(screening_id, ScreeningPhase.VALIDATION)

        assert progress is not None
        assert progress.current_phase == ScreeningPhase.VALIDATION
        assert progress.phases["validation"].status == "in_progress"

    @pytest.mark.asyncio
    async def test_complete_phase(self, tracker: ProgressTracker) -> None:
        """Test completing a phase."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)
        await tracker.start_phase(screening_id, ScreeningPhase.VALIDATION)

        progress = await tracker.complete_phase(screening_id, ScreeningPhase.VALIDATION)

        assert progress is not None
        assert progress.phases["validation"].status == "complete"
        assert progress.phases["validation"].progress_percent == 100.0

    @pytest.mark.asyncio
    async def test_fail_phase(self, tracker: ProgressTracker) -> None:
        """Test failing a phase."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)
        await tracker.start_phase(screening_id, ScreeningPhase.INVESTIGATION)

        progress = await tracker.fail_phase(
            screening_id, ScreeningPhase.INVESTIGATION, "Provider timeout"
        )

        assert progress is not None
        assert progress.phases["investigation"].status == "failed"
        assert progress.phases["investigation"].error_message == "Provider timeout"
        assert progress.status == ScreeningStatus.FAILED

    @pytest.mark.asyncio
    async def test_progress_calculation(self, tracker: ProgressTracker) -> None:
        """Test overall progress calculation."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)

        # Complete validation (5%)
        await tracker.start_phase(screening_id, ScreeningPhase.VALIDATION)
        await tracker.complete_phase(screening_id, ScreeningPhase.VALIDATION)

        # Complete compliance (5%)
        await tracker.start_phase(screening_id, ScreeningPhase.COMPLIANCE)
        await tracker.complete_phase(screening_id, ScreeningPhase.COMPLIANCE)

        progress = await tracker.get_progress(screening_id)
        assert progress is not None
        assert progress.overall_progress == 10.0  # 5% + 5%


class TestProgressTrackerSteps:
    """Tests for step-level progress tracking."""

    @pytest.fixture
    def tracker(self) -> ProgressTracker:
        """Create a tracker for testing."""
        return create_progress_tracker()

    @pytest.mark.asyncio
    async def test_add_step(self, tracker: ProgressTracker) -> None:
        """Test adding a step to a phase."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)
        await tracker.start_phase(screening_id, ScreeningPhase.INVESTIGATION)

        step = await tracker.add_step(
            screening_id,
            ScreeningPhase.INVESTIGATION,
            "sar-1",
            "Initial SAR Query",
        )

        assert step is not None
        assert step.step_id == "sar-1"
        assert step.step_name == "Initial SAR Query"
        assert step.status == "pending"

    @pytest.mark.asyncio
    async def test_update_step(self, tracker: ProgressTracker) -> None:
        """Test updating step progress."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)
        await tracker.start_phase(screening_id, ScreeningPhase.INVESTIGATION)
        await tracker.add_step(
            screening_id, ScreeningPhase.INVESTIGATION, "sar-1", "SAR Query"
        )

        step = await tracker.update_step(
            screening_id,
            ScreeningPhase.INVESTIGATION,
            "sar-1",
            progress_percent=50.0,
            status="in_progress",
        )

        assert step is not None
        assert step.progress_percent == 50.0
        assert step.status == "in_progress"

    @pytest.mark.asyncio
    async def test_step_completion_updates_phase(self, tracker: ProgressTracker) -> None:
        """Test that completing steps updates phase progress."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)
        await tracker.start_phase(screening_id, ScreeningPhase.INVESTIGATION)

        # Add two steps
        await tracker.add_step(
            screening_id, ScreeningPhase.INVESTIGATION, "s1", "Step 1"
        )
        await tracker.add_step(
            screening_id, ScreeningPhase.INVESTIGATION, "s2", "Step 2"
        )

        # Complete first step
        await tracker.update_step(
            screening_id,
            ScreeningPhase.INVESTIGATION,
            "s1",
            progress_percent=100.0,
            status="complete",
        )

        progress = await tracker.get_progress(screening_id)
        assert progress is not None
        # Phase progress should be 50% (1 of 2 steps complete)
        assert progress.phases["investigation"].progress_percent == 50.0


class TestProgressTrackerETA:
    """Tests for ETA calculation."""

    @pytest.fixture
    def tracker(self) -> ProgressTracker:
        """Create a tracker for testing."""
        return create_progress_tracker()

    @pytest.mark.asyncio
    async def test_initial_eta(self, tracker: ProgressTracker) -> None:
        """Test initial ETA calculation."""
        screening_id = uuid4()
        progress = await tracker.initialize_progress(screening_id)

        assert progress.eta is not None
        assert progress.eta.remaining_seconds is not None
        assert progress.eta.remaining_seconds > 0
        assert progress.eta.confidence > 0

    @pytest.mark.asyncio
    async def test_eta_decreases_with_progress(self, tracker: ProgressTracker) -> None:
        """Test that ETA decreases as progress is made."""
        screening_id = uuid4()
        progress = await tracker.initialize_progress(screening_id)
        initial_eta = progress.eta.remaining_seconds if progress.eta else 0

        # Complete validation phase
        await tracker.start_phase(screening_id, ScreeningPhase.VALIDATION)
        await tracker.complete_phase(screening_id, ScreeningPhase.VALIDATION)

        progress = await tracker.get_progress(screening_id)
        assert progress is not None
        assert progress.eta is not None
        # ETA should have decreased
        assert progress.eta.remaining_seconds is not None
        assert progress.eta.remaining_seconds < initial_eta

    def test_historical_eta(self) -> None:
        """Test ETA calculation with historical data."""
        tracker = create_progress_tracker()

        # Add historical samples
        for _ in range(10):
            tracker._record_phase_duration(ScreeningPhase.VALIDATION, 25.0)

        # Get expected duration
        duration, confidence = tracker._get_expected_duration("validation")
        assert duration == 25.0
        assert confidence > 0.5  # Higher confidence with samples


class TestProgressTrackerStallDetection:
    """Tests for stall detection."""

    @pytest.fixture
    def tracker(self) -> ProgressTracker:
        """Create a tracker with short stall timeout."""
        config = ProgressTrackerConfig(stall_timeout_seconds=1)
        return create_progress_tracker(config=config)

    @pytest.mark.asyncio
    async def test_detect_stall(self, tracker: ProgressTracker) -> None:
        """Test manual stall detection."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)

        progress = await tracker.detect_stall(screening_id, StallReason.PROVIDER_DELAY)

        assert progress is not None
        assert progress.is_stalled is True
        assert progress.stall_reason == StallReason.PROVIDER_DELAY

    @pytest.mark.asyncio
    async def test_resolve_stall(self, tracker: ProgressTracker) -> None:
        """Test resolving a stall."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)
        await tracker.detect_stall(screening_id, StallReason.TIMEOUT)

        progress = await tracker.resolve_stall(screening_id)

        assert progress is not None
        assert progress.is_stalled is False
        assert progress.stall_reason is None

    @pytest.mark.asyncio
    async def test_stall_cleared_on_progress(self, tracker: ProgressTracker) -> None:
        """Test that stall is cleared when progress is made."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)
        await tracker.detect_stall(screening_id, StallReason.TIMEOUT)

        # Make progress
        progress = await tracker.update_progress(
            screening_id,
            phase=ScreeningPhase.VALIDATION,
            progress_percent=50.0,
        )

        assert progress is not None
        assert progress.is_stalled is False

    @pytest.mark.asyncio
    async def test_check_for_stalls(self, tracker: ProgressTracker) -> None:
        """Test checking all screenings for stalls."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)

        # Manually set old last_activity to trigger stall
        progress = await tracker.get_progress(screening_id)
        if progress:
            progress.last_activity = datetime.now(UTC) - timedelta(seconds=10)
            tracker._progress_cache[str(screening_id)] = progress

        stalled = await tracker.check_for_stalls()
        assert len(stalled) == 1
        assert stalled[0].screening_id == screening_id


class TestProgressTrackerNotifications:
    """Tests for progress notifications."""

    @pytest.fixture
    def tracker(self) -> ProgressTracker:
        """Create a tracker for testing."""
        return create_progress_tracker()

    @pytest.mark.asyncio
    async def test_subscribe_notifications(self, tracker: ProgressTracker) -> None:
        """Test subscribing to notifications."""
        notifications: list[ProgressNotification] = []

        def handler(notification: ProgressNotification) -> None:
            notifications.append(notification)

        tracker.subscribe(handler)

        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)
        await tracker.start_phase(screening_id, ScreeningPhase.VALIDATION)

        assert len(notifications) > 0
        assert any(
            n.notification_type == ProgressNotificationType.PHASE_CHANGE for n in notifications
        )

    @pytest.mark.asyncio
    async def test_unsubscribe_notifications(self, tracker: ProgressTracker) -> None:
        """Test unsubscribing from notifications."""
        notifications: list[ProgressNotification] = []

        def handler(notification: ProgressNotification) -> None:
            notifications.append(notification)

        tracker.subscribe(handler)
        tracker.unsubscribe(handler)

        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)
        await tracker.start_phase(screening_id, ScreeningPhase.VALIDATION)

        assert len(notifications) == 0

    @pytest.mark.asyncio
    async def test_milestone_notifications(self, tracker: ProgressTracker) -> None:
        """Test milestone notifications."""
        notifications: list[ProgressNotification] = []

        def handler(notification: ProgressNotification) -> None:
            notifications.append(notification)

        tracker.subscribe(handler)

        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)

        # Complete phases to reach 25%
        await tracker.start_phase(screening_id, ScreeningPhase.VALIDATION)
        await tracker.complete_phase(screening_id, ScreeningPhase.VALIDATION)
        await tracker.start_phase(screening_id, ScreeningPhase.COMPLIANCE)
        await tracker.complete_phase(screening_id, ScreeningPhase.COMPLIANCE)
        await tracker.start_phase(screening_id, ScreeningPhase.CONSENT)
        await tracker.complete_phase(screening_id, ScreeningPhase.CONSENT)
        await tracker.start_phase(screening_id, ScreeningPhase.INVESTIGATION)
        await tracker.update_progress(
            screening_id, ScreeningPhase.INVESTIGATION, progress_percent=20.0
        )

        # Check for milestone notification
        milestone_notifications = [
            n
            for n in notifications
            if n.notification_type == ProgressNotificationType.MILESTONE_REACHED
        ]
        assert len(milestone_notifications) >= 1


class TestProgressTrackerCleanup:
    """Tests for progress tracking cleanup."""

    @pytest.fixture
    def tracker(self) -> ProgressTracker:
        """Create a tracker for testing."""
        return create_progress_tracker()

    @pytest.mark.asyncio
    async def test_complete_tracking(self, tracker: ProgressTracker) -> None:
        """Test completing progress tracking."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)

        await tracker.complete_tracking(screening_id)

        # Should be removed from cache
        progress = await tracker.get_progress(screening_id)
        assert progress is None

    @pytest.mark.asyncio
    async def test_cancel_tracking(self, tracker: ProgressTracker) -> None:
        """Test cancelling progress tracking."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)

        await tracker.cancel_tracking(screening_id)

        # Should be removed from cache
        progress = await tracker.get_progress(screening_id)
        assert progress is None


class TestProgressTrackerStats:
    """Tests for progress tracker statistics."""

    @pytest.fixture
    def tracker(self) -> ProgressTracker:
        """Create a tracker for testing."""
        return create_progress_tracker()

    @pytest.mark.asyncio
    async def test_active_screenings_count(self, tracker: ProgressTracker) -> None:
        """Test getting active screenings count."""
        assert tracker.get_active_screenings_count() == 0

        await tracker.initialize_progress(uuid4())
        await tracker.initialize_progress(uuid4())

        assert tracker.get_active_screenings_count() == 2

    @pytest.mark.asyncio
    async def test_stalled_screenings_count(self, tracker: ProgressTracker) -> None:
        """Test getting stalled screenings count."""
        screening_id = uuid4()
        await tracker.initialize_progress(screening_id)

        assert tracker.get_stalled_screenings_count() == 0

        await tracker.detect_stall(screening_id, StallReason.TIMEOUT)

        assert tracker.get_stalled_screenings_count() == 1

    def test_historical_stats(self) -> None:
        """Test getting historical statistics."""
        tracker = create_progress_tracker()

        # No stats initially
        stats = tracker.get_historical_stats(ScreeningPhase.VALIDATION)
        assert stats is None

        # Add samples
        for i in range(5):
            tracker._record_phase_duration(ScreeningPhase.VALIDATION, float(i + 1) * 10)

        stats = tracker.get_historical_stats(ScreeningPhase.VALIDATION)
        assert stats is not None
        assert stats["sample_count"] == 5
        assert stats["avg_duration_seconds"] == 30.0  # (10+20+30+40+50)/5


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_progress_tracker(self) -> None:
        """Test creating a progress tracker."""
        tracker = create_progress_tracker()
        assert tracker is not None
        assert isinstance(tracker, ProgressTracker)

    def test_create_with_config(self) -> None:
        """Test creating with custom config."""
        config = ProgressTrackerConfig(stall_timeout_seconds=600)
        tracker = create_progress_tracker(config=config)
        assert tracker._config.stall_timeout_seconds == 600

    def test_get_progress_tracker_singleton(self) -> None:
        """Test that get_progress_tracker returns singleton."""
        reset_progress_tracker()

        tracker1 = get_progress_tracker()
        tracker2 = get_progress_tracker()

        assert tracker1 is tracker2

    def test_reset_progress_tracker(self) -> None:
        """Test resetting the singleton."""
        tracker1 = get_progress_tracker()
        reset_progress_tracker()
        tracker2 = get_progress_tracker()

        assert tracker1 is not tracker2


# =============================================================================
# Integration Tests
# =============================================================================


class TestProgressTrackerIntegration:
    """Integration tests for progress tracker."""

    @pytest.fixture
    def tracker(self) -> ProgressTracker:
        """Create a tracker for testing."""
        return create_progress_tracker()

    @pytest.mark.asyncio
    async def test_full_screening_lifecycle(self, tracker: ProgressTracker) -> None:
        """Test tracking a complete screening lifecycle."""
        screening_id = uuid4()
        tenant_id = uuid4()

        notifications: list[ProgressNotification] = []
        tracker.subscribe(lambda n: notifications.append(n))

        # Initialize
        progress = await tracker.initialize_progress(screening_id, tenant_id)
        assert progress.overall_progress == 0.0

        # Validation phase
        await tracker.start_phase(screening_id, ScreeningPhase.VALIDATION)
        await tracker.complete_phase(screening_id, ScreeningPhase.VALIDATION)

        # Compliance phase
        await tracker.start_phase(screening_id, ScreeningPhase.COMPLIANCE)
        await tracker.complete_phase(screening_id, ScreeningPhase.COMPLIANCE)

        # Consent phase
        await tracker.start_phase(screening_id, ScreeningPhase.CONSENT)
        await tracker.complete_phase(screening_id, ScreeningPhase.CONSENT)

        # Investigation phase with steps
        await tracker.start_phase(screening_id, ScreeningPhase.INVESTIGATION)
        await tracker.add_step(
            screening_id, ScreeningPhase.INVESTIGATION, "sar-1", "Initial Query"
        )
        await tracker.update_step(
            screening_id, ScreeningPhase.INVESTIGATION, "sar-1", progress_percent=100.0
        )
        await tracker.complete_phase(screening_id, ScreeningPhase.INVESTIGATION)

        # Risk analysis phase
        await tracker.start_phase(screening_id, ScreeningPhase.RISK_ANALYSIS)
        await tracker.complete_phase(screening_id, ScreeningPhase.RISK_ANALYSIS)

        # Report generation phase
        await tracker.start_phase(screening_id, ScreeningPhase.REPORT_GENERATION)
        await tracker.complete_phase(screening_id, ScreeningPhase.REPORT_GENERATION)

        # Complete tracking
        await tracker.complete_tracking(screening_id)

        # Verify we received notifications
        assert len(notifications) > 0
        phase_changes = [
            n for n in notifications if n.notification_type == ProgressNotificationType.PHASE_CHANGE
        ]
        assert len(phase_changes) >= 12  # Start + complete for each of 6 phases

    @pytest.mark.asyncio
    async def test_screening_with_failure_and_recovery(
        self, tracker: ProgressTracker
    ) -> None:
        """Test tracking a screening that fails and recovers."""
        screening_id = uuid4()

        await tracker.initialize_progress(screening_id)

        # Start and complete early phases
        await tracker.start_phase(screening_id, ScreeningPhase.VALIDATION)
        await tracker.complete_phase(screening_id, ScreeningPhase.VALIDATION)

        # Investigation fails
        await tracker.start_phase(screening_id, ScreeningPhase.INVESTIGATION)
        await tracker.fail_phase(
            screening_id, ScreeningPhase.INVESTIGATION, "Provider timeout"
        )

        progress = await tracker.get_progress(screening_id)
        assert progress is not None
        assert progress.status == ScreeningStatus.FAILED

    @pytest.mark.asyncio
    async def test_eta_accuracy(self, tracker: ProgressTracker) -> None:
        """Test that ETA becomes more accurate with historical data."""
        # Record historical durations (need ~45+ samples to reach 0.7 confidence threshold)
        for _ in range(50):
            tracker._record_phase_duration(ScreeningPhase.VALIDATION, 30.0)
            tracker._record_phase_duration(ScreeningPhase.COMPLIANCE, 25.0)
            tracker._record_phase_duration(ScreeningPhase.CONSENT, 20.0)
            tracker._record_phase_duration(ScreeningPhase.INVESTIGATION, 180.0)
            tracker._record_phase_duration(ScreeningPhase.RISK_ANALYSIS, 60.0)
            tracker._record_phase_duration(ScreeningPhase.REPORT_GENERATION, 45.0)

        # Initialize new screening
        screening_id = uuid4()
        progress = await tracker.initialize_progress(screening_id)

        # ETA should use historical method with high confidence
        assert progress.eta is not None
        assert progress.eta.calculation_method == "historical"
        assert progress.eta.confidence >= 0.7
