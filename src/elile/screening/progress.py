"""Screening progress tracker for real-time progress visibility and ETA estimation.

This module implements progress tracking for screenings, including:
- Granular phase/step progress tracking
- ETA (estimated time to completion) calculation
- Progress notifications via subscribers
- Stalled screening detection
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from statistics import mean, stdev
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from uuid import uuid7

from elile.screening.state_manager import (
    ScreeningPhase,
    ScreeningState,
    ScreeningStateManager,
)
from elile.screening.types import ScreeningStatus

# =============================================================================
# Enums
# =============================================================================


class StallReason(str, Enum):
    """Reasons a screening may be stalled."""

    TIMEOUT = "timeout"  # No progress for too long
    PROVIDER_DELAY = "provider_delay"  # Waiting on external provider
    RESOURCE_CONSTRAINT = "resource_constraint"  # System resource limitation
    MANUAL_INTERVENTION = "manual_intervention"  # Needs manual review
    UNKNOWN = "unknown"  # Unknown reason


class ProgressNotificationType(str, Enum):
    """Types of progress notifications."""

    PROGRESS_UPDATE = "progress_update"  # Regular progress update
    PHASE_CHANGE = "phase_change"  # Phase started or completed
    ETA_UPDATE = "eta_update"  # ETA changed significantly
    STALL_DETECTED = "stall_detected"  # Screening appears stalled
    STALL_RESOLVED = "stall_resolved"  # Stall condition resolved
    MILESTONE_REACHED = "milestone_reached"  # Key progress milestone (25%, 50%, 75%)


# =============================================================================
# Progress Models
# =============================================================================


@dataclass
class ProgressStep:
    """Progress of a single step within a phase."""

    step_id: str
    step_name: str
    phase: ScreeningPhase
    progress_percent: float = 0.0
    status: str = "pending"  # pending, in_progress, complete, failed
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        """Mark step as started."""
        self.status = "in_progress"
        self.started_at = datetime.now(UTC)

    def complete(self) -> None:
        """Mark step as complete."""
        self.status = "complete"
        self.progress_percent = 100.0
        self.completed_at = datetime.now(UTC)

    def fail(self, error: str) -> None:
        """Mark step as failed."""
        self.status = "failed"
        self.error_message = error
        self.completed_at = datetime.now(UTC)

    @property
    def duration_seconds(self) -> float | None:
        """Get step duration in seconds."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now(UTC)
        return (end_time - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "phase": self.phase.value,
            "progress_percent": self.progress_percent,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "details": self.details,
        }


@dataclass
class PhaseProgress:
    """Progress of a screening phase."""

    phase: ScreeningPhase
    status: str = "pending"  # pending, in_progress, complete, failed
    progress_percent: float = 0.0
    steps: list[ProgressStep] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None

    def start(self) -> None:
        """Mark phase as started."""
        self.status = "in_progress"
        self.started_at = datetime.now(UTC)

    def complete(self) -> None:
        """Mark phase as complete."""
        self.status = "complete"
        self.progress_percent = 100.0
        self.completed_at = datetime.now(UTC)

    def fail(self, error: str) -> None:
        """Mark phase as failed."""
        self.status = "failed"
        self.error_message = error
        self.completed_at = datetime.now(UTC)

    @property
    def duration_seconds(self) -> float | None:
        """Get phase duration in seconds."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now(UTC)
        return (end_time - self.started_at).total_seconds()

    def update_progress_from_steps(self) -> None:
        """Update phase progress based on step completion."""
        if not self.steps:
            return
        total_progress = sum(step.progress_percent for step in self.steps)
        self.progress_percent = total_progress / len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "phase": self.phase.value,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "steps": [step.to_dict() for step in self.steps],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }


@dataclass
class ETAEstimate:
    """Estimated time to completion."""

    estimated_completion: datetime | None = None
    remaining_seconds: float | None = None
    confidence: float = 0.0  # 0.0 to 1.0
    calculation_method: str = "default"  # default, historical, adaptive
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def remaining_human_readable(self) -> str:
        """Get human-readable remaining time."""
        if self.remaining_seconds is None:
            return "Unknown"
        if self.remaining_seconds < 60:
            return f"{int(self.remaining_seconds)}s"
        if self.remaining_seconds < 3600:
            return f"{int(self.remaining_seconds / 60)}m"
        hours = int(self.remaining_seconds / 3600)
        minutes = int((self.remaining_seconds % 3600) / 60)
        return f"{hours}h {minutes}m"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "estimated_completion": (
                self.estimated_completion.isoformat() if self.estimated_completion else None
            ),
            "remaining_seconds": self.remaining_seconds,
            "remaining_human_readable": self.remaining_human_readable,
            "confidence": self.confidence,
            "calculation_method": self.calculation_method,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class ScreeningProgress:
    """Complete progress state for a screening."""

    screening_id: UUID
    tenant_id: UUID | None = None
    overall_progress: float = 0.0
    current_phase: ScreeningPhase = ScreeningPhase.PENDING
    current_step: str | None = None
    status: ScreeningStatus = ScreeningStatus.PENDING
    phases: dict[str, PhaseProgress] = field(default_factory=dict)
    eta: ETAEstimate | None = None
    is_stalled: bool = False
    stall_reason: StallReason | None = None
    stall_detected_at: datetime | None = None
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def update_overall_progress(self) -> None:
        """Calculate overall progress from phase completion."""
        # Define phase weights (total = 100)
        phase_weights = {
            ScreeningPhase.VALIDATION.value: 5,
            ScreeningPhase.COMPLIANCE.value: 5,
            ScreeningPhase.CONSENT.value: 5,
            ScreeningPhase.INVESTIGATION.value: 50,
            ScreeningPhase.RISK_ANALYSIS.value: 20,
            ScreeningPhase.REPORT_GENERATION.value: 15,
        }

        progress = 0.0
        for phase_name, weight in phase_weights.items():
            if phase_name in self.phases:
                phase = self.phases[phase_name]
                progress += (phase.progress_percent / 100.0) * weight

        self.overall_progress = min(100.0, progress)
        self.updated_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "screening_id": str(self.screening_id),
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "overall_progress": self.overall_progress,
            "current_phase": self.current_phase.value,
            "current_step": self.current_step,
            "status": self.status.value,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "eta": self.eta.to_dict() if self.eta else None,
            "is_stalled": self.is_stalled,
            "stall_reason": self.stall_reason.value if self.stall_reason else None,
            "stall_detected_at": (
                self.stall_detected_at.isoformat() if self.stall_detected_at else None
            ),
            "last_activity": self.last_activity.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ProgressNotification:
    """Notification emitted when progress changes."""

    notification_id: UUID = field(default_factory=uuid7)
    screening_id: UUID = field(default_factory=uuid7)
    notification_type: ProgressNotificationType = ProgressNotificationType.PROGRESS_UPDATE
    phase: ScreeningPhase | None = None
    step: str | None = None
    progress_percent: float = 0.0
    eta: ETAEstimate | None = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "notification_id": str(self.notification_id),
            "screening_id": str(self.screening_id),
            "notification_type": self.notification_type.value,
            "phase": self.phase.value if self.phase else None,
            "step": self.step,
            "progress_percent": self.progress_percent,
            "eta": self.eta.to_dict() if self.eta else None,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HistoricalDuration:
    """Historical duration data for ETA estimation."""

    phase: ScreeningPhase
    durations_seconds: list[float] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def avg_duration(self) -> float | None:
        """Get average duration."""
        if not self.durations_seconds:
            return None
        return mean(self.durations_seconds)

    @property
    def stddev_duration(self) -> float | None:
        """Get duration standard deviation."""
        if len(self.durations_seconds) < 2:
            return None
        return stdev(self.durations_seconds)

    def add_sample(self, duration_seconds: float) -> None:
        """Add a duration sample."""
        self.durations_seconds.append(duration_seconds)
        # Keep last 100 samples
        if len(self.durations_seconds) > 100:
            self.durations_seconds = self.durations_seconds[-100:]
        self.last_updated = datetime.now(UTC)


# =============================================================================
# Configuration
# =============================================================================


class ProgressTrackerConfig(BaseModel):
    """Configuration for progress tracker."""

    # Stall detection
    stall_timeout_seconds: int = Field(
        default=300, description="Seconds without progress before stall detection"
    )
    stall_check_interval_seconds: int = Field(
        default=30, description="How often to check for stalls"
    )

    # ETA calculation
    default_phase_durations_seconds: dict[str, float] = Field(
        default_factory=lambda: {
            "validation": 30.0,
            "compliance": 30.0,
            "consent": 30.0,
            "investigation": 180.0,
            "risk_analysis": 60.0,
            "report_generation": 45.0,
        },
        description="Default phase durations for ETA",
    )
    eta_confidence_threshold: float = Field(
        default=0.7, description="Minimum confidence for historical ETA"
    )
    min_samples_for_historical_eta: int = Field(
        default=5, description="Minimum samples for historical ETA"
    )

    # Notifications
    emit_notifications: bool = Field(default=True, description="Whether to emit notifications")
    milestone_percentages: list[int] = Field(
        default_factory=lambda: [25, 50, 75, 100], description="Progress milestones to notify on"
    )
    eta_change_threshold_percent: float = Field(
        default=20.0, description="% change in ETA to trigger notification"
    )


# =============================================================================
# Progress Tracker
# =============================================================================


class ProgressTracker:
    """Tracks screening progress with ETA estimation and stall detection.

    Provides:
    - Granular phase/step progress tracking
    - ETA calculation based on historical data
    - Stalled screening detection
    - Progress notifications via subscribers
    """

    def __init__(
        self,
        state_manager: ScreeningStateManager | None = None,
        config: ProgressTrackerConfig | None = None,
    ) -> None:
        """Initialize progress tracker.

        Args:
            state_manager: State manager for persistence.
            config: Tracker configuration.
        """
        self._state_manager = state_manager
        self._config = config or ProgressTrackerConfig()

        # In-memory progress cache
        self._progress_cache: dict[str, ScreeningProgress] = {}

        # Historical duration data for ETA
        self._historical_durations: dict[str, HistoricalDuration] = {}

        # Notification subscribers
        self._subscribers: list[Callable[[ProgressNotification], None]] = []

        # Milestones reached (to avoid duplicate notifications)
        self._milestones_reached: dict[str, set[int]] = {}

    # =========================================================================
    # Progress Management
    # =========================================================================

    async def get_progress(self, screening_id: UUID) -> ScreeningProgress | None:
        """Get current progress for a screening.

        Args:
            screening_id: Screening identifier.

        Returns:
            ScreeningProgress or None if not found.
        """
        key = str(screening_id)

        # Check cache first
        if key in self._progress_cache:
            return self._progress_cache[key]

        # Try to load from state manager
        if self._state_manager:
            state = await self._state_manager.load_state(screening_id)
            if state:
                progress = self._state_to_progress(state)
                self._progress_cache[key] = progress
                return progress

        return None

    async def initialize_progress(
        self,
        screening_id: UUID,
        tenant_id: UUID | None = None,
    ) -> ScreeningProgress:
        """Initialize progress tracking for a screening.

        Args:
            screening_id: Screening identifier.
            tenant_id: Optional tenant identifier.

        Returns:
            New ScreeningProgress.
        """
        key = str(screening_id)

        progress = ScreeningProgress(
            screening_id=screening_id,
            tenant_id=tenant_id,
        )

        # Initialize phase progress
        for phase in [
            ScreeningPhase.VALIDATION,
            ScreeningPhase.COMPLIANCE,
            ScreeningPhase.CONSENT,
            ScreeningPhase.INVESTIGATION,
            ScreeningPhase.RISK_ANALYSIS,
            ScreeningPhase.REPORT_GENERATION,
        ]:
            progress.phases[phase.value] = PhaseProgress(phase=phase)

        # Calculate initial ETA
        progress.eta = self._calculate_eta(progress)

        self._progress_cache[key] = progress
        self._milestones_reached[key] = set()

        return progress

    async def update_progress(
        self,
        screening_id: UUID,
        phase: ScreeningPhase,
        step: str | None = None,
        progress_percent: float | None = None,
    ) -> ScreeningProgress | None:
        """Update screening progress.

        Args:
            screening_id: Screening identifier.
            phase: Current phase.
            step: Optional current step name.
            progress_percent: Optional progress percentage for the phase.

        Returns:
            Updated ScreeningProgress or None.
        """
        progress = await self.get_progress(screening_id)
        if not progress:
            return None

        # Update current phase and step
        progress.current_phase = phase
        progress.current_step = step
        progress.last_activity = datetime.now(UTC)

        # Update phase progress
        if phase.value in progress.phases:
            phase_progress = progress.phases[phase.value]
            if phase_progress.status == "pending":
                phase_progress.start()
            if progress_percent is not None:
                phase_progress.progress_percent = min(100.0, max(0.0, progress_percent))

        # Recalculate overall progress
        progress.update_overall_progress()

        # Update ETA
        old_eta = progress.eta
        progress.eta = self._calculate_eta(progress)

        # Clear stall if activity detected
        if progress.is_stalled:
            progress.is_stalled = False
            progress.stall_reason = None
            if self._config.emit_notifications:
                await self._emit_notification(
                    screening_id=screening_id,
                    notification_type=ProgressNotificationType.STALL_RESOLVED,
                    phase=phase,
                    step=step,
                    progress_percent=progress.overall_progress,
                    eta=progress.eta,
                    message="Stall condition resolved",
                )

        # Emit notifications
        if self._config.emit_notifications:
            await self._emit_progress_notification(
                progress, phase, step, old_eta
            )

        # Cache update
        self._progress_cache[str(screening_id)] = progress

        return progress

    async def start_phase(
        self,
        screening_id: UUID,
        phase: ScreeningPhase,
    ) -> ScreeningProgress | None:
        """Mark a phase as started.

        Args:
            screening_id: Screening identifier.
            phase: Phase to start.

        Returns:
            Updated ScreeningProgress or None.
        """
        progress = await self.get_progress(screening_id)
        if not progress:
            return None

        if phase.value in progress.phases:
            phase_progress = progress.phases[phase.value]
            phase_progress.start()

        progress.current_phase = phase
        progress.last_activity = datetime.now(UTC)
        progress.update_overall_progress()
        progress.eta = self._calculate_eta(progress)

        if self._config.emit_notifications:
            await self._emit_notification(
                screening_id=screening_id,
                notification_type=ProgressNotificationType.PHASE_CHANGE,
                phase=phase,
                progress_percent=progress.overall_progress,
                eta=progress.eta,
                message=f"Started phase: {phase.value}",
            )

        self._progress_cache[str(screening_id)] = progress
        return progress

    async def complete_phase(
        self,
        screening_id: UUID,
        phase: ScreeningPhase,
    ) -> ScreeningProgress | None:
        """Mark a phase as complete.

        Args:
            screening_id: Screening identifier.
            phase: Phase to complete.

        Returns:
            Updated ScreeningProgress or None.
        """
        progress = await self.get_progress(screening_id)
        if not progress:
            return None

        if phase.value in progress.phases:
            phase_progress = progress.phases[phase.value]
            phase_progress.complete()

            # Record duration for ETA estimation
            if phase_progress.duration_seconds is not None:
                self._record_phase_duration(phase, phase_progress.duration_seconds)

        progress.last_activity = datetime.now(UTC)
        progress.update_overall_progress()
        progress.eta = self._calculate_eta(progress)

        if self._config.emit_notifications:
            await self._emit_notification(
                screening_id=screening_id,
                notification_type=ProgressNotificationType.PHASE_CHANGE,
                phase=phase,
                progress_percent=progress.overall_progress,
                eta=progress.eta,
                message=f"Completed phase: {phase.value}",
            )

        self._progress_cache[str(screening_id)] = progress
        return progress

    async def fail_phase(
        self,
        screening_id: UUID,
        phase: ScreeningPhase,
        error: str,
    ) -> ScreeningProgress | None:
        """Mark a phase as failed.

        Args:
            screening_id: Screening identifier.
            phase: Phase that failed.
            error: Error message.

        Returns:
            Updated ScreeningProgress or None.
        """
        progress = await self.get_progress(screening_id)
        if not progress:
            return None

        if phase.value in progress.phases:
            phase_progress = progress.phases[phase.value]
            phase_progress.fail(error)

        progress.status = ScreeningStatus.FAILED
        progress.last_activity = datetime.now(UTC)
        progress.eta = None  # No ETA for failed screenings

        self._progress_cache[str(screening_id)] = progress
        return progress

    # =========================================================================
    # Step Management
    # =========================================================================

    async def add_step(
        self,
        screening_id: UUID,
        phase: ScreeningPhase,
        step_id: str,
        step_name: str,
    ) -> ProgressStep | None:
        """Add a step to a phase.

        Args:
            screening_id: Screening identifier.
            phase: Phase the step belongs to.
            step_id: Unique step identifier.
            step_name: Human-readable step name.

        Returns:
            New ProgressStep or None.
        """
        progress = await self.get_progress(screening_id)
        if not progress:
            return None

        if phase.value not in progress.phases:
            return None

        step = ProgressStep(
            step_id=step_id,
            step_name=step_name,
            phase=phase,
        )

        progress.phases[phase.value].steps.append(step)
        self._progress_cache[str(screening_id)] = progress

        return step

    async def update_step(
        self,
        screening_id: UUID,
        phase: ScreeningPhase,
        step_id: str,
        progress_percent: float | None = None,
        status: str | None = None,
    ) -> ProgressStep | None:
        """Update a step's progress.

        Args:
            screening_id: Screening identifier.
            phase: Phase the step belongs to.
            step_id: Step identifier.
            progress_percent: Optional progress percentage.
            status: Optional new status.

        Returns:
            Updated ProgressStep or None.
        """
        progress = await self.get_progress(screening_id)
        if not progress:
            return None

        if phase.value not in progress.phases:
            return None

        phase_progress = progress.phases[phase.value]
        step = next((s for s in phase_progress.steps if s.step_id == step_id), None)
        if not step:
            return None

        if progress_percent is not None:
            step.progress_percent = min(100.0, max(0.0, progress_percent))
        if status is not None:
            step.status = status
            if status == "in_progress" and step.started_at is None:
                step.start()
            elif status == "complete":
                step.complete()

        # Update phase progress based on steps
        phase_progress.update_progress_from_steps()

        # Update current step
        progress.current_step = step.step_name

        # Recalculate overall progress
        progress.last_activity = datetime.now(UTC)
        progress.update_overall_progress()
        progress.eta = self._calculate_eta(progress)

        self._progress_cache[str(screening_id)] = progress
        return step

    # =========================================================================
    # ETA Calculation
    # =========================================================================

    def _calculate_eta(self, progress: ScreeningProgress) -> ETAEstimate:
        """Calculate ETA for screening completion.

        Args:
            progress: Current progress state.

        Returns:
            ETAEstimate with calculated values.
        """
        now = datetime.now(UTC)

        # Calculate remaining time
        remaining_seconds = 0.0
        total_confidence = 0.0
        phase_count = 0

        for phase_name, phase_progress in progress.phases.items():
            if phase_progress.status == "complete":
                continue

            # Get expected duration for this phase
            duration, confidence = self._get_expected_duration(phase_name)

            if phase_progress.status == "in_progress":
                # Partial progress - adjust remaining
                remaining_percent = 1.0 - (phase_progress.progress_percent / 100.0)
                remaining_seconds += duration * remaining_percent
            else:
                # Phase not started yet
                remaining_seconds += duration

            total_confidence += confidence
            phase_count += 1

        # Calculate average confidence
        avg_confidence = total_confidence / max(1, phase_count)

        # Estimate completion time
        estimated_completion = now + timedelta(seconds=remaining_seconds) if remaining_seconds > 0 else now

        # Determine calculation method
        method = "default"
        if avg_confidence >= self._config.eta_confidence_threshold:
            method = "historical"

        return ETAEstimate(
            estimated_completion=estimated_completion,
            remaining_seconds=remaining_seconds if remaining_seconds > 0 else None,
            confidence=avg_confidence,
            calculation_method=method,
            last_updated=now,
        )

    def _get_expected_duration(self, phase_name: str) -> tuple[float, float]:
        """Get expected duration for a phase.

        Args:
            phase_name: Name of the phase.

        Returns:
            Tuple of (duration_seconds, confidence).
        """
        # Try historical data first
        if phase_name in self._historical_durations:
            historical = self._historical_durations[phase_name]
            if len(historical.durations_seconds) >= self._config.min_samples_for_historical_eta:
                avg = historical.avg_duration
                if avg is not None:
                    # Higher confidence with more samples
                    sample_count = len(historical.durations_seconds)
                    confidence = min(0.95, 0.5 + (sample_count / 100) * 0.45)
                    return (avg, confidence)

        # Fall back to defaults
        default_duration = self._config.default_phase_durations_seconds.get(phase_name, 60.0)
        return (default_duration, 0.3)  # Low confidence for defaults

    def _record_phase_duration(self, phase: ScreeningPhase, duration_seconds: float) -> None:
        """Record phase duration for historical ETA.

        Args:
            phase: Completed phase.
            duration_seconds: Actual duration.
        """
        key = phase.value
        if key not in self._historical_durations:
            self._historical_durations[key] = HistoricalDuration(phase=phase)
        self._historical_durations[key].add_sample(duration_seconds)

    # =========================================================================
    # Stall Detection
    # =========================================================================

    async def check_for_stalls(self) -> list[ScreeningProgress]:
        """Check all tracked screenings for stalls.

        Returns:
            List of stalled screenings.
        """
        stalled = []
        now = datetime.now(UTC)
        threshold = timedelta(seconds=self._config.stall_timeout_seconds)

        for progress in self._progress_cache.values():
            # Skip completed/failed screenings
            if progress.status in [ScreeningStatus.COMPLETE, ScreeningStatus.FAILED]:
                continue

            # Check if stalled
            if (now - progress.last_activity) > threshold:
                if not progress.is_stalled:
                    await self._mark_as_stalled(progress, StallReason.TIMEOUT)
                stalled.append(progress)

        return stalled

    async def detect_stall(
        self,
        screening_id: UUID,
        reason: StallReason | None = None,
    ) -> ScreeningProgress | None:
        """Mark a screening as stalled.

        Args:
            screening_id: Screening identifier.
            reason: Reason for stall.

        Returns:
            Updated ScreeningProgress or None.
        """
        progress = await self.get_progress(screening_id)
        if not progress:
            return None

        await self._mark_as_stalled(progress, reason or StallReason.UNKNOWN)
        return progress

    async def _mark_as_stalled(
        self,
        progress: ScreeningProgress,
        reason: StallReason,
    ) -> None:
        """Mark progress as stalled and notify.

        Args:
            progress: Progress to mark.
            reason: Stall reason.
        """
        progress.is_stalled = True
        progress.stall_reason = reason
        progress.stall_detected_at = datetime.now(UTC)

        if self._config.emit_notifications:
            await self._emit_notification(
                screening_id=progress.screening_id,
                notification_type=ProgressNotificationType.STALL_DETECTED,
                phase=progress.current_phase,
                step=progress.current_step,
                progress_percent=progress.overall_progress,
                message=f"Screening stalled: {reason.value}",
                details={"stall_reason": reason.value},
            )

        self._progress_cache[str(progress.screening_id)] = progress

    async def resolve_stall(
        self,
        screening_id: UUID,
    ) -> ScreeningProgress | None:
        """Resolve a stall condition.

        Args:
            screening_id: Screening identifier.

        Returns:
            Updated ScreeningProgress or None.
        """
        progress = await self.get_progress(screening_id)
        if not progress:
            return None

        if progress.is_stalled:
            progress.is_stalled = False
            progress.stall_reason = None
            progress.stall_detected_at = None
            progress.last_activity = datetime.now(UTC)

            if self._config.emit_notifications:
                await self._emit_notification(
                    screening_id=screening_id,
                    notification_type=ProgressNotificationType.STALL_RESOLVED,
                    phase=progress.current_phase,
                    progress_percent=progress.overall_progress,
                    message="Stall condition resolved",
                )

            self._progress_cache[str(screening_id)] = progress

        return progress

    # =========================================================================
    # Notifications
    # =========================================================================

    def subscribe(self, callback: Callable[[ProgressNotification], None]) -> None:
        """Subscribe to progress notifications.

        Args:
            callback: Function to call on notifications.
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[ProgressNotification], None]) -> None:
        """Unsubscribe from progress notifications.

        Args:
            callback: Callback to remove.
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def _emit_notification(
        self,
        screening_id: UUID,
        notification_type: ProgressNotificationType,
        phase: ScreeningPhase | None = None,
        step: str | None = None,
        progress_percent: float = 0.0,
        eta: ETAEstimate | None = None,
        message: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Emit a progress notification.

        Args:
            screening_id: Screening identifier.
            notification_type: Type of notification.
            phase: Current phase.
            step: Current step.
            progress_percent: Progress percentage.
            eta: ETA estimate.
            message: Notification message.
            details: Additional details.
        """
        notification = ProgressNotification(
            screening_id=screening_id,
            notification_type=notification_type,
            phase=phase,
            step=step,
            progress_percent=progress_percent,
            eta=eta,
            message=message,
            details=details or {},
        )

        import contextlib

        for subscriber in self._subscribers:
            with contextlib.suppress(Exception):
                subscriber(notification)

    async def _emit_progress_notification(
        self,
        progress: ScreeningProgress,
        phase: ScreeningPhase,
        step: str | None,
        old_eta: ETAEstimate | None,
    ) -> None:
        """Emit appropriate notification for progress update.

        Args:
            progress: Current progress.
            phase: Current phase.
            step: Current step.
            old_eta: Previous ETA for comparison.
        """
        key = str(progress.screening_id)
        milestones = self._milestones_reached.get(key, set())

        # Check for milestone
        for milestone in self._config.milestone_percentages:
            if (
                progress.overall_progress >= milestone
                and milestone not in milestones
            ):
                milestones.add(milestone)
                self._milestones_reached[key] = milestones
                await self._emit_notification(
                    screening_id=progress.screening_id,
                    notification_type=ProgressNotificationType.MILESTONE_REACHED,
                    phase=phase,
                    step=step,
                    progress_percent=progress.overall_progress,
                    eta=progress.eta,
                    message=f"Milestone reached: {milestone}%",
                    details={"milestone": milestone},
                )
                return

        # Check for significant ETA change
        if old_eta and progress.eta:
            old_remaining = old_eta.remaining_seconds or 0
            new_remaining = progress.eta.remaining_seconds or 0
            if old_remaining > 0:
                change_percent = abs(new_remaining - old_remaining) / old_remaining * 100
                if change_percent >= self._config.eta_change_threshold_percent:
                    await self._emit_notification(
                        screening_id=progress.screening_id,
                        notification_type=ProgressNotificationType.ETA_UPDATE,
                        phase=phase,
                        step=step,
                        progress_percent=progress.overall_progress,
                        eta=progress.eta,
                        message=f"ETA updated: {progress.eta.remaining_human_readable}",
                    )
                    return

        # Standard progress update
        await self._emit_notification(
            screening_id=progress.screening_id,
            notification_type=ProgressNotificationType.PROGRESS_UPDATE,
            phase=phase,
            step=step,
            progress_percent=progress.overall_progress,
            eta=progress.eta,
            message=f"Progress: {progress.overall_progress:.1f}%",
        )

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def complete_tracking(self, screening_id: UUID) -> None:
        """Complete progress tracking for a screening.

        Args:
            screening_id: Screening identifier.
        """
        key = str(screening_id)
        progress = self._progress_cache.get(key)

        if progress:
            progress.status = ScreeningStatus.COMPLETE
            progress.overall_progress = 100.0
            progress.eta = None

            if self._config.emit_notifications:
                await self._emit_notification(
                    screening_id=screening_id,
                    notification_type=ProgressNotificationType.MILESTONE_REACHED,
                    phase=ScreeningPhase.COMPLETE,
                    progress_percent=100.0,
                    message="Screening completed",
                    details={"milestone": 100},
                )

        # Cleanup
        if key in self._progress_cache:
            del self._progress_cache[key]
        if key in self._milestones_reached:
            del self._milestones_reached[key]

    async def cancel_tracking(self, screening_id: UUID) -> None:
        """Cancel progress tracking for a screening.

        Args:
            screening_id: Screening identifier.
        """
        key = str(screening_id)

        progress = self._progress_cache.get(key)
        if progress:
            progress.status = ScreeningStatus.CANCELLED
            progress.eta = None

        # Cleanup
        if key in self._progress_cache:
            del self._progress_cache[key]
        if key in self._milestones_reached:
            del self._milestones_reached[key]

    # =========================================================================
    # Helpers
    # =========================================================================

    def _state_to_progress(self, state: ScreeningState) -> ScreeningProgress:
        """Convert ScreeningState to ScreeningProgress.

        Args:
            state: State to convert.

        Returns:
            ScreeningProgress instance.
        """
        progress = ScreeningProgress(
            screening_id=state.screening_id,
            tenant_id=state.tenant_id,
            overall_progress=state.progress_percent,
            current_phase=state.current_phase,
            status=state.status,
        )

        # Initialize phases from state
        for phase in [
            ScreeningPhase.VALIDATION,
            ScreeningPhase.COMPLIANCE,
            ScreeningPhase.CONSENT,
            ScreeningPhase.INVESTIGATION,
            ScreeningPhase.RISK_ANALYSIS,
            ScreeningPhase.REPORT_GENERATION,
        ]:
            phase_progress = PhaseProgress(phase=phase)
            if phase.value in state.completed_phases:
                phase_progress.status = "complete"
                phase_progress.progress_percent = 100.0
            elif phase == state.current_phase:
                phase_progress.status = "in_progress"
            progress.phases[phase.value] = phase_progress

        return progress

    def get_active_screenings_count(self) -> int:
        """Get count of actively tracked screenings.

        Returns:
            Number of screenings being tracked.
        """
        return len(self._progress_cache)

    def get_stalled_screenings_count(self) -> int:
        """Get count of stalled screenings.

        Returns:
            Number of stalled screenings.
        """
        return sum(1 for p in self._progress_cache.values() if p.is_stalled)

    def get_historical_stats(self, phase: ScreeningPhase) -> dict[str, Any] | None:
        """Get historical statistics for a phase.

        Args:
            phase: Phase to get stats for.

        Returns:
            Dict with avg, stddev, sample_count or None.
        """
        key = phase.value
        if key not in self._historical_durations:
            return None

        historical = self._historical_durations[key]
        return {
            "phase": phase.value,
            "avg_duration_seconds": historical.avg_duration,
            "stddev_duration_seconds": historical.stddev_duration,
            "sample_count": len(historical.durations_seconds),
            "last_updated": historical.last_updated.isoformat(),
        }


# =============================================================================
# Factory Functions
# =============================================================================


_progress_tracker_instance: ProgressTracker | None = None


def create_progress_tracker(
    state_manager: ScreeningStateManager | None = None,
    config: ProgressTrackerConfig | None = None,
) -> ProgressTracker:
    """Create a progress tracker with configuration.

    Args:
        state_manager: Optional state manager.
        config: Optional configuration.

    Returns:
        Configured ProgressTracker.
    """
    return ProgressTracker(
        state_manager=state_manager,
        config=config or ProgressTrackerConfig(),
    )


def get_progress_tracker() -> ProgressTracker:
    """Get or create the default progress tracker.

    Returns:
        Default ProgressTracker instance.
    """
    global _progress_tracker_instance
    if _progress_tracker_instance is None:
        _progress_tracker_instance = create_progress_tracker()
    return _progress_tracker_instance


def reset_progress_tracker() -> None:
    """Reset the default progress tracker instance."""
    global _progress_tracker_instance
    _progress_tracker_instance = None
