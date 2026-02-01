"""Screening state manager for persistence and resumption.

This module implements state management for screenings, including:
- State persistence and recovery
- Progress tracking
- Failure handling and resumption
- Status updates and notifications
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable
from uuid import UUID

from pydantic import BaseModel, Field
from uuid_utils import uuid7

from elile.screening.types import ScreeningPhaseResult, ScreeningResult, ScreeningStatus


# =============================================================================
# Enums
# =============================================================================


class ScreeningPhase(str, Enum):
    """Phases of a screening workflow."""

    PENDING = "pending"  # Initial state
    VALIDATION = "validation"  # Validating request
    COMPLIANCE = "compliance"  # Checking compliance rules
    CONSENT = "consent"  # Verifying consent
    INVESTIGATION = "investigation"  # Running SAR loop
    RISK_ANALYSIS = "risk_analysis"  # Analyzing risk
    REPORT_GENERATION = "report_generation"  # Generating reports
    COMPLETE = "complete"  # Successfully finished
    FAILED = "failed"  # Failed with error
    CANCELLED = "cancelled"  # Cancelled


class ProgressEventType(str, Enum):
    """Types of progress events."""

    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"
    PROGRESS_UPDATE = "progress_update"
    STATUS_CHANGED = "status_changed"
    CHECKPOINT_SAVED = "checkpoint_saved"


# =============================================================================
# State Models
# =============================================================================


@dataclass
class ScreeningState:
    """State of a screening in progress.

    Tracks all information needed to persist and resume a screening.
    """

    state_id: UUID = field(default_factory=uuid7)
    screening_id: UUID = field(default_factory=uuid7)
    tenant_id: UUID | None = None

    # Current status
    status: ScreeningStatus = ScreeningStatus.PENDING
    current_phase: ScreeningPhase = ScreeningPhase.PENDING
    progress_percent: float = 0.0

    # Phase tracking
    completed_phases: list[str] = field(default_factory=list)
    phase_results: dict[str, ScreeningPhaseResult] = field(default_factory=dict)

    # Error tracking
    last_error: str | None = None
    error_phase: ScreeningPhase | None = None
    retry_count: int = 0
    max_retries: int = 3

    # Checkpoint data
    checkpoint_data: dict[str, Any] = field(default_factory=dict)
    checkpoint_version: int = 0

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "state_id": str(self.state_id),
            "screening_id": str(self.screening_id),
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "status": self.status.value,
            "current_phase": self.current_phase.value,
            "progress_percent": self.progress_percent,
            "completed_phases": self.completed_phases,
            "phase_results": {k: v.to_dict() for k, v in self.phase_results.items()},
            "last_error": self.last_error,
            "error_phase": self.error_phase.value if self.error_phase else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "checkpoint_data": self.checkpoint_data,
            "checkpoint_version": self.checkpoint_version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScreeningState":
        """Create state from dictionary."""
        # Parse phase results
        phase_results = {}
        if data.get("phase_results"):
            for k, v in data["phase_results"].items():
                phase_results[k] = ScreeningPhaseResult(
                    phase_name=v["phase_name"],
                    started_at=datetime.fromisoformat(v["started_at"]),
                    completed_at=datetime.fromisoformat(v["completed_at"]) if v.get("completed_at") else None,
                    status=v["status"],
                    error_message=v.get("error_message"),
                    details=v.get("details", {}),
                )

        return cls(
            state_id=UUID(data["state_id"]) if data.get("state_id") else uuid7(),
            screening_id=UUID(data["screening_id"]) if data.get("screening_id") else uuid7(),
            tenant_id=UUID(data["tenant_id"]) if data.get("tenant_id") else None,
            status=ScreeningStatus(data.get("status", "pending")),
            current_phase=ScreeningPhase(data.get("current_phase", "pending")),
            progress_percent=data.get("progress_percent", 0.0),
            completed_phases=data.get("completed_phases", []),
            phase_results=phase_results,
            last_error=data.get("last_error"),
            error_phase=ScreeningPhase(data["error_phase"]) if data.get("error_phase") else None,
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            checkpoint_data=data.get("checkpoint_data", {}),
            checkpoint_version=data.get("checkpoint_version", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(UTC),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(UTC),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )


@dataclass
class ProgressEvent:
    """Event emitted when screening progress changes."""

    event_id: UUID = field(default_factory=uuid7)
    screening_id: UUID = field(default_factory=uuid7)
    event_type: ProgressEventType = ProgressEventType.PROGRESS_UPDATE
    phase: ScreeningPhase | None = None
    progress_percent: float = 0.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": str(self.event_id),
            "screening_id": str(self.screening_id),
            "event_type": self.event_type.value,
            "phase": self.phase.value if self.phase else None,
            "progress_percent": self.progress_percent,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Configuration
# =============================================================================


class StateManagerConfig(BaseModel):
    """Configuration for state manager."""

    # Persistence settings
    auto_save_interval_seconds: int = Field(default=30, description="Auto-save interval")
    save_on_phase_change: bool = Field(default=True, description="Save on phase transitions")

    # Retry settings
    max_retries: int = Field(default=3, description="Max retry attempts")
    retry_delay_seconds: int = Field(default=60, description="Delay between retries")
    exponential_backoff: bool = Field(default=True, description="Use exponential backoff")

    # Progress tracking
    emit_progress_events: bool = Field(default=True, description="Emit progress events")


# =============================================================================
# State Store Protocol
# =============================================================================


class StateStore:
    """Protocol for state persistence backends."""

    async def save(self, screening_id: UUID, state: ScreeningState) -> None:
        """Save screening state."""
        ...

    async def load(self, screening_id: UUID) -> ScreeningState | None:
        """Load screening state."""
        ...

    async def delete(self, screening_id: UUID) -> bool:
        """Delete screening state."""
        ...

    async def list_by_status(
        self,
        status: ScreeningStatus,
        tenant_id: UUID | None = None,
    ) -> list[ScreeningState]:
        """List states by status."""
        ...


# =============================================================================
# In-Memory State Store
# =============================================================================


class InMemoryStateStore(StateStore):
    """In-memory state store for testing."""

    def __init__(self) -> None:
        self._states: dict[UUID, ScreeningState] = {}

    async def save(self, screening_id: UUID, state: ScreeningState) -> None:
        """Save screening state."""
        state.updated_at = datetime.now(UTC)
        self._states[screening_id] = state

    async def load(self, screening_id: UUID) -> ScreeningState | None:
        """Load screening state."""
        return self._states.get(screening_id)

    async def delete(self, screening_id: UUID) -> bool:
        """Delete screening state."""
        if screening_id in self._states:
            del self._states[screening_id]
            return True
        return False

    async def list_by_status(
        self,
        status: ScreeningStatus,
        tenant_id: UUID | None = None,
    ) -> list[ScreeningState]:
        """List states by status."""
        results = []
        for state in self._states.values():
            if state.status == status:
                if tenant_id is None or state.tenant_id == tenant_id:
                    results.append(state)
        return results


# =============================================================================
# Screening State Manager
# =============================================================================


class ScreeningStateManager:
    """Manages screening state persistence and resumption.

    Provides:
    - State persistence across phases
    - Progress tracking and notifications
    - Failure recovery with retry logic
    - Checkpoint-based resumption
    """

    def __init__(
        self,
        store: StateStore | None = None,
        config: StateManagerConfig | None = None,
    ) -> None:
        """Initialize state manager.

        Args:
            store: State persistence backend.
            config: Manager configuration.
        """
        self.store = store or InMemoryStateStore()
        self.config = config or StateManagerConfig()
        self._progress_callbacks: list[Callable[[ProgressEvent], None]] = []

    # =========================================================================
    # State CRUD Operations
    # =========================================================================

    async def create_state(
        self,
        screening_id: UUID,
        tenant_id: UUID | None = None,
    ) -> ScreeningState:
        """Create initial state for a screening.

        Args:
            screening_id: Screening identifier.
            tenant_id: Optional tenant identifier.

        Returns:
            New ScreeningState.
        """
        state = ScreeningState(
            screening_id=screening_id,
            tenant_id=tenant_id,
            status=ScreeningStatus.PENDING,
            current_phase=ScreeningPhase.PENDING,
        )
        await self.save_state(screening_id, state)
        return state

    async def save_state(self, screening_id: UUID, state: ScreeningState) -> None:
        """Persist screening state.

        Args:
            screening_id: Screening identifier.
            state: State to persist.
        """
        state.checkpoint_version += 1
        await self.store.save(screening_id, state)

        if self.config.emit_progress_events:
            await self._emit_event(
                screening_id=screening_id,
                event_type=ProgressEventType.CHECKPOINT_SAVED,
                phase=state.current_phase,
                progress_percent=state.progress_percent,
                message=f"Checkpoint saved (version {state.checkpoint_version})",
            )

    async def load_state(self, screening_id: UUID) -> ScreeningState | None:
        """Load screening state.

        Args:
            screening_id: Screening identifier.

        Returns:
            ScreeningState or None if not found.
        """
        return await self.store.load(screening_id)

    async def delete_state(self, screening_id: UUID) -> bool:
        """Delete screening state.

        Args:
            screening_id: Screening identifier.

        Returns:
            True if deleted.
        """
        return await self.store.delete(screening_id)

    # =========================================================================
    # Phase Management
    # =========================================================================

    async def start_phase(
        self,
        screening_id: UUID,
        phase: ScreeningPhase,
    ) -> ScreeningState | None:
        """Start a screening phase.

        Args:
            screening_id: Screening identifier.
            phase: Phase to start.

        Returns:
            Updated state or None.
        """
        state = await self.load_state(screening_id)
        if not state:
            return None

        # Record phase start
        state.current_phase = phase
        if state.started_at is None:
            state.started_at = datetime.now(UTC)

        # Create phase result
        phase_result = ScreeningPhaseResult(phase_name=phase.value)
        state.phase_results[phase.value] = phase_result

        # Update status based on phase
        status_map = {
            ScreeningPhase.VALIDATION: ScreeningStatus.VALIDATING,
            ScreeningPhase.COMPLIANCE: ScreeningStatus.VALIDATING,
            ScreeningPhase.CONSENT: ScreeningStatus.VALIDATING,
            ScreeningPhase.INVESTIGATION: ScreeningStatus.IN_PROGRESS,
            ScreeningPhase.RISK_ANALYSIS: ScreeningStatus.ANALYZING,
            ScreeningPhase.REPORT_GENERATION: ScreeningStatus.GENERATING_REPORT,
        }
        if phase in status_map:
            state.status = status_map[phase]

        if self.config.save_on_phase_change:
            await self.save_state(screening_id, state)

        if self.config.emit_progress_events:
            await self._emit_event(
                screening_id=screening_id,
                event_type=ProgressEventType.PHASE_STARTED,
                phase=phase,
                progress_percent=state.progress_percent,
                message=f"Started phase: {phase.value}",
            )

        return state

    async def complete_phase(
        self,
        screening_id: UUID,
        phase: ScreeningPhase,
        details: dict[str, Any] | None = None,
    ) -> ScreeningState | None:
        """Complete a screening phase.

        Args:
            screening_id: Screening identifier.
            phase: Phase to complete.
            details: Optional phase completion details.

        Returns:
            Updated state or None.
        """
        state = await self.load_state(screening_id)
        if not state:
            return None

        # Update phase result
        if phase.value in state.phase_results:
            phase_result = state.phase_results[phase.value]
            phase_result.complete(status="complete")
            if details:
                phase_result.details.update(details)

        # Mark phase as completed
        if phase.value not in state.completed_phases:
            state.completed_phases.append(phase.value)

        # Update progress
        state.progress_percent = self._calculate_progress(state)

        if self.config.save_on_phase_change:
            await self.save_state(screening_id, state)

        if self.config.emit_progress_events:
            await self._emit_event(
                screening_id=screening_id,
                event_type=ProgressEventType.PHASE_COMPLETED,
                phase=phase,
                progress_percent=state.progress_percent,
                message=f"Completed phase: {phase.value}",
            )

        return state

    async def fail_phase(
        self,
        screening_id: UUID,
        phase: ScreeningPhase,
        error: str,
    ) -> ScreeningState | None:
        """Mark a phase as failed.

        Args:
            screening_id: Screening identifier.
            phase: Phase that failed.
            error: Error message.

        Returns:
            Updated state or None.
        """
        state = await self.load_state(screening_id)
        if not state:
            return None

        # Update phase result
        if phase.value in state.phase_results:
            phase_result = state.phase_results[phase.value]
            phase_result.complete(status="failed", error=error)

        # Record error
        state.last_error = error
        state.error_phase = phase
        state.retry_count += 1

        # Update status
        if state.retry_count >= state.max_retries:
            state.status = ScreeningStatus.FAILED
            state.current_phase = ScreeningPhase.FAILED
            state.completed_at = datetime.now(UTC)

        if self.config.save_on_phase_change:
            await self.save_state(screening_id, state)

        if self.config.emit_progress_events:
            await self._emit_event(
                screening_id=screening_id,
                event_type=ProgressEventType.PHASE_FAILED,
                phase=phase,
                progress_percent=state.progress_percent,
                message=f"Phase failed: {error}",
            )

        return state

    # =========================================================================
    # Progress Tracking
    # =========================================================================

    async def update_progress(
        self,
        screening_id: UUID,
        progress_percent: float,
        message: str | None = None,
    ) -> ScreeningState | None:
        """Update screening progress.

        Args:
            screening_id: Screening identifier.
            progress_percent: Progress percentage (0-100).
            message: Optional progress message.

        Returns:
            Updated state or None.
        """
        state = await self.load_state(screening_id)
        if not state:
            return None

        state.progress_percent = min(100.0, max(0.0, progress_percent))
        await self.save_state(screening_id, state)

        if self.config.emit_progress_events:
            await self._emit_event(
                screening_id=screening_id,
                event_type=ProgressEventType.PROGRESS_UPDATE,
                phase=state.current_phase,
                progress_percent=state.progress_percent,
                message=message or f"Progress: {state.progress_percent:.1f}%",
            )

        return state

    def _calculate_progress(self, state: ScreeningState) -> float:
        """Calculate progress percentage based on completed phases.

        Args:
            state: Current screening state.

        Returns:
            Progress percentage (0-100).
        """
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
            if phase_name in state.completed_phases:
                progress += weight

        return min(100.0, progress)

    # =========================================================================
    # Resumption
    # =========================================================================

    async def can_resume(self, screening_id: UUID) -> bool:
        """Check if a screening can be resumed.

        Args:
            screening_id: Screening identifier.

        Returns:
            True if resumable.
        """
        state = await self.load_state(screening_id)
        if not state:
            return False

        # Can't resume completed or cancelled screenings
        if state.status in [ScreeningStatus.COMPLETE, ScreeningStatus.CANCELLED]:
            return False

        # Can resume if not exceeded max retries
        return state.retry_count < state.max_retries

    async def get_resume_point(self, screening_id: UUID) -> ScreeningPhase | None:
        """Get the phase to resume from.

        Args:
            screening_id: Screening identifier.

        Returns:
            Phase to resume from or None.
        """
        state = await self.load_state(screening_id)
        if not state:
            return None

        # Resume from error phase if available
        if state.error_phase:
            return state.error_phase

        # Resume from current phase
        if state.current_phase not in [ScreeningPhase.COMPLETE, ScreeningPhase.FAILED]:
            return state.current_phase

        # Start from beginning
        return ScreeningPhase.VALIDATION

    async def prepare_for_resume(self, screening_id: UUID) -> ScreeningState | None:
        """Prepare state for resumption.

        Args:
            screening_id: Screening identifier.

        Returns:
            Updated state or None.
        """
        state = await self.load_state(screening_id)
        if not state:
            return None

        # Clear error state
        state.last_error = None

        # Update status to in progress
        state.status = ScreeningStatus.IN_PROGRESS

        await self.save_state(screening_id, state)
        return state

    # =========================================================================
    # Completion
    # =========================================================================

    async def complete_screening(
        self,
        screening_id: UUID,
        result: ScreeningResult | None = None,
    ) -> ScreeningState | None:
        """Mark screening as complete.

        Args:
            screening_id: Screening identifier.
            result: Optional screening result.

        Returns:
            Updated state or None.
        """
        state = await self.load_state(screening_id)
        if not state:
            return None

        state.status = ScreeningStatus.COMPLETE
        state.current_phase = ScreeningPhase.COMPLETE
        state.progress_percent = 100.0
        state.completed_at = datetime.now(UTC)

        if result:
            state.checkpoint_data["result_id"] = str(result.result_id)
            state.checkpoint_data["risk_score"] = result.risk_score
            state.checkpoint_data["risk_level"] = result.risk_level

        await self.save_state(screening_id, state)

        if self.config.emit_progress_events:
            await self._emit_event(
                screening_id=screening_id,
                event_type=ProgressEventType.STATUS_CHANGED,
                phase=ScreeningPhase.COMPLETE,
                progress_percent=100.0,
                message="Screening completed successfully",
            )

        return state

    async def cancel_screening(
        self,
        screening_id: UUID,
        reason: str | None = None,
    ) -> ScreeningState | None:
        """Cancel a screening.

        Args:
            screening_id: Screening identifier.
            reason: Optional cancellation reason.

        Returns:
            Updated state or None.
        """
        state = await self.load_state(screening_id)
        if not state:
            return None

        state.status = ScreeningStatus.CANCELLED
        state.current_phase = ScreeningPhase.CANCELLED
        state.completed_at = datetime.now(UTC)
        if reason:
            state.checkpoint_data["cancellation_reason"] = reason

        await self.save_state(screening_id, state)

        if self.config.emit_progress_events:
            await self._emit_event(
                screening_id=screening_id,
                event_type=ProgressEventType.STATUS_CHANGED,
                phase=ScreeningPhase.CANCELLED,
                progress_percent=state.progress_percent,
                message=reason or "Screening cancelled",
            )

        return state

    # =========================================================================
    # Event Handling
    # =========================================================================

    def on_progress(self, callback: Callable[[ProgressEvent], None]) -> None:
        """Register a progress callback.

        Args:
            callback: Function to call on progress events.
        """
        self._progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: Callable[[ProgressEvent], None]) -> None:
        """Remove a progress callback.

        Args:
            callback: Callback to remove.
        """
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    async def _emit_event(
        self,
        screening_id: UUID,
        event_type: ProgressEventType,
        phase: ScreeningPhase | None,
        progress_percent: float,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Emit a progress event.

        Args:
            screening_id: Screening identifier.
            event_type: Type of event.
            phase: Current phase.
            progress_percent: Progress percentage.
            message: Event message.
            details: Optional event details.
        """
        event = ProgressEvent(
            screening_id=screening_id,
            event_type=event_type,
            phase=phase,
            progress_percent=progress_percent,
            message=message,
            details=details or {},
        )

        for callback in self._progress_callbacks:
            try:
                callback(event)
            except Exception:
                pass  # Don't let callback errors break the flow

    # =========================================================================
    # Queries
    # =========================================================================

    async def get_pending_screenings(
        self,
        tenant_id: UUID | None = None,
    ) -> list[ScreeningState]:
        """Get screenings in pending status.

        Args:
            tenant_id: Optional tenant filter.

        Returns:
            List of pending screening states.
        """
        return await self.store.list_by_status(ScreeningStatus.PENDING, tenant_id)

    async def get_failed_screenings(
        self,
        tenant_id: UUID | None = None,
    ) -> list[ScreeningState]:
        """Get screenings in failed status.

        Args:
            tenant_id: Optional tenant filter.

        Returns:
            List of failed screening states.
        """
        return await self.store.list_by_status(ScreeningStatus.FAILED, tenant_id)

    async def get_resumable_screenings(
        self,
        tenant_id: UUID | None = None,
    ) -> list[ScreeningState]:
        """Get screenings that can be resumed.

        Args:
            tenant_id: Optional tenant filter.

        Returns:
            List of resumable screening states.
        """
        # Get failed screenings
        failed = await self.store.list_by_status(ScreeningStatus.FAILED, tenant_id)

        # Filter to those with retries remaining
        return [s for s in failed if s.retry_count < s.max_retries]


# =============================================================================
# Factory Functions
# =============================================================================


def create_state_manager(
    store: StateStore | None = None,
    config: StateManagerConfig | None = None,
) -> ScreeningStateManager:
    """Create a state manager with default configuration.

    Args:
        store: Optional state store.
        config: Optional configuration.

    Returns:
        Configured ScreeningStateManager.
    """
    return ScreeningStateManager(
        store=store or InMemoryStateStore(),
        config=config or StateManagerConfig(),
    )
