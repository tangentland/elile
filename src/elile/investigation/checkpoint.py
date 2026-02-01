"""Investigation Checkpoint Manager for pause/resume and state recovery.

This module provides checkpoint management for long-running investigations,
enabling pause/resume operations, failure recovery, and manual review points.

Architecture Reference: docs/architecture/05-investigation.md

Key Features:
    - Checkpoint storage and retrieval
    - Pause and resume operations
    - State recovery after failures
    - Manual review point support
    - Investigation branching
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import InformationType
from elile.core.logging import get_logger
from elile.investigation.models import SARPhase

logger = get_logger(__name__)


class CheckpointStatus(str, Enum):
    """Status of a checkpoint."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RESTORED = "restored"
    EXPIRED = "expired"


class CheckpointReason(str, Enum):
    """Reason for creating a checkpoint."""

    AUTO_SAVE = "auto_save"
    PHASE_COMPLETE = "phase_complete"
    MANUAL_PAUSE = "manual_pause"
    REVIEW_REQUIRED = "review_required"
    ERROR_RECOVERY = "error_recovery"
    BRANCH_POINT = "branch_point"


class ResumeStrategy(str, Enum):
    """Strategy for resuming from checkpoint."""

    CONTINUE = "continue"  # Continue from exact state
    RESTART_PHASE = "restart_phase"  # Restart current phase
    SKIP_TO_NEXT = "skip_to_next"  # Skip to next phase


@dataclass
class CheckpointData:
    """Serializable checkpoint data."""

    # Core identification
    checkpoint_id: UUID = field(default_factory=uuid7)
    investigation_id: UUID | None = None
    parent_checkpoint_id: UUID | None = None  # For branching

    # Investigation state
    current_phase: str = ""
    sar_phase: SARPhase = SARPhase.SEARCH
    active_types: list[str] = field(default_factory=list)
    completed_types: list[str] = field(default_factory=list)

    # Type-level state (serialized)
    type_states: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Knowledge base snapshot
    knowledge_snapshot: dict[str, Any] = field(default_factory=dict)

    # Progress tracking
    iteration_count: int = 0
    queries_executed: int = 0
    findings_count: int = 0

    # Confidence metrics
    confidence_scores: dict[str, float] = field(default_factory=dict)

    # Checkpoint metadata
    reason: CheckpointReason = CheckpointReason.AUTO_SAVE
    status: CheckpointStatus = CheckpointStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    # Notes for manual review
    review_notes: str = ""
    requires_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "checkpoint_id": str(self.checkpoint_id),
            "investigation_id": str(self.investigation_id) if self.investigation_id else None,
            "parent_checkpoint_id": (
                str(self.parent_checkpoint_id) if self.parent_checkpoint_id else None
            ),
            "current_phase": self.current_phase,
            "sar_phase": self.sar_phase.value,
            "active_types": self.active_types,
            "completed_types": self.completed_types,
            "type_states": self.type_states,
            "knowledge_snapshot": self.knowledge_snapshot,
            "iteration_count": self.iteration_count,
            "queries_executed": self.queries_executed,
            "findings_count": self.findings_count,
            "confidence_scores": self.confidence_scores,
            "reason": self.reason.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "review_notes": self.review_notes,
            "requires_review": self.requires_review,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointData":
        """Create from dictionary."""
        return cls(
            checkpoint_id=UUID(data["checkpoint_id"]),
            investigation_id=UUID(data["investigation_id"]) if data.get("investigation_id") else None,
            parent_checkpoint_id=(
                UUID(data["parent_checkpoint_id"]) if data.get("parent_checkpoint_id") else None
            ),
            current_phase=data.get("current_phase", ""),
            sar_phase=SARPhase(data.get("sar_phase", "idle")),
            active_types=data.get("active_types", []),
            completed_types=data.get("completed_types", []),
            type_states=data.get("type_states", {}),
            knowledge_snapshot=data.get("knowledge_snapshot", {}),
            iteration_count=data.get("iteration_count", 0),
            queries_executed=data.get("queries_executed", 0),
            findings_count=data.get("findings_count", 0),
            confidence_scores=data.get("confidence_scores", {}),
            reason=CheckpointReason(data.get("reason", "auto_save")),
            status=CheckpointStatus(data.get("status", "active")),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=(
                datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
            ),
            review_notes=data.get("review_notes", ""),
            requires_review=data.get("requires_review", False),
        )


@dataclass
class ResumeResult:
    """Result of resuming from a checkpoint."""

    success: bool = True
    checkpoint_id: UUID | None = None
    investigation_id: UUID | None = None
    restored_phase: str = ""
    restored_types: list[str] = field(default_factory=list)
    strategy_used: ResumeStrategy = ResumeStrategy.CONTINUE
    error_message: str | None = None
    resumed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "checkpoint_id": str(self.checkpoint_id) if self.checkpoint_id else None,
            "investigation_id": str(self.investigation_id) if self.investigation_id else None,
            "restored_phase": self.restored_phase,
            "restored_types": self.restored_types,
            "strategy_used": self.strategy_used.value,
            "error_message": self.error_message,
            "resumed_at": self.resumed_at.isoformat(),
        }


class CheckpointStorage(Protocol):
    """Protocol for checkpoint storage backends."""

    def save(self, checkpoint: CheckpointData) -> None:
        """Save a checkpoint."""
        ...

    def load(self, checkpoint_id: UUID) -> CheckpointData | None:
        """Load a checkpoint by ID."""
        ...

    def load_latest(self, investigation_id: UUID) -> CheckpointData | None:
        """Load the most recent checkpoint for an investigation."""
        ...

    def list_checkpoints(
        self,
        investigation_id: UUID,
        limit: int = 10,
    ) -> list[CheckpointData]:
        """List checkpoints for an investigation."""
        ...

    def delete(self, checkpoint_id: UUID) -> bool:
        """Delete a checkpoint."""
        ...

    def mark_superseded(self, checkpoint_id: UUID) -> None:
        """Mark a checkpoint as superseded."""
        ...


class InMemoryCheckpointStorage:
    """In-memory checkpoint storage for testing."""

    def __init__(self) -> None:
        """Initialize storage."""
        self._checkpoints: dict[UUID, CheckpointData] = {}
        self._by_investigation: dict[UUID, list[UUID]] = {}

    def save(self, checkpoint: CheckpointData) -> None:
        """Save a checkpoint."""
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint

        if checkpoint.investigation_id:
            if checkpoint.investigation_id not in self._by_investigation:
                self._by_investigation[checkpoint.investigation_id] = []
            self._by_investigation[checkpoint.investigation_id].append(checkpoint.checkpoint_id)

    def load(self, checkpoint_id: UUID) -> CheckpointData | None:
        """Load a checkpoint by ID."""
        return self._checkpoints.get(checkpoint_id)

    def load_latest(self, investigation_id: UUID) -> CheckpointData | None:
        """Load the most recent active checkpoint for an investigation."""
        checkpoint_ids = self._by_investigation.get(investigation_id, [])
        if not checkpoint_ids:
            return None

        # Find most recent active checkpoint
        latest: CheckpointData | None = None
        for cp_id in reversed(checkpoint_ids):
            cp = self._checkpoints.get(cp_id)
            if cp and cp.status == CheckpointStatus.ACTIVE:
                if latest is None or cp.created_at > latest.created_at:
                    latest = cp
        return latest

    def list_checkpoints(
        self,
        investigation_id: UUID,
        limit: int = 10,
    ) -> list[CheckpointData]:
        """List checkpoints for an investigation."""
        checkpoint_ids = self._by_investigation.get(investigation_id, [])
        checkpoints = [
            self._checkpoints[cp_id]
            for cp_id in checkpoint_ids
            if cp_id in self._checkpoints
        ]
        # Sort by created_at descending
        checkpoints.sort(key=lambda x: x.created_at, reverse=True)
        return checkpoints[:limit]

    def delete(self, checkpoint_id: UUID) -> bool:
        """Delete a checkpoint."""
        if checkpoint_id in self._checkpoints:
            cp = self._checkpoints.pop(checkpoint_id)
            if cp.investigation_id and cp.investigation_id in self._by_investigation:
                try:
                    self._by_investigation[cp.investigation_id].remove(checkpoint_id)
                except ValueError:
                    pass
            return True
        return False

    def mark_superseded(self, checkpoint_id: UUID) -> None:
        """Mark a checkpoint as superseded."""
        if checkpoint_id in self._checkpoints:
            self._checkpoints[checkpoint_id].status = CheckpointStatus.SUPERSEDED


class CheckpointConfig(BaseModel):
    """Configuration for CheckpointManager."""

    auto_checkpoint_interval: int = Field(
        default=5, ge=1, le=100, description="Iterations between auto checkpoints"
    )
    max_checkpoints_per_investigation: int = Field(
        default=20, ge=5, le=100, description="Max checkpoints to retain"
    )
    checkpoint_expiry_hours: int = Field(
        default=168, ge=1, le=8760, description="Hours until checkpoint expires (default 7 days)"
    )
    enable_auto_cleanup: bool = Field(
        default=True, description="Auto-cleanup old checkpoints"
    )


@dataclass
class CheckpointManager:
    """Manages investigation checkpoints for pause/resume and recovery.

    The CheckpointManager enables:
    - Saving investigation state at key points
    - Resuming investigations after interruptions
    - Recovering from failures
    - Creating branch points for alternative investigation paths
    - Marking review points requiring human attention

    Example:
        ```python
        storage = InMemoryCheckpointStorage()
        manager = CheckpointManager(storage=storage)

        # Save checkpoint during investigation
        checkpoint = manager.create_checkpoint(
            investigation_id=inv_id,
            current_phase="foundation",
            type_states={"identity": state.to_dict()},
            reason=CheckpointReason.PHASE_COMPLETE,
        )

        # Resume from checkpoint
        result = manager.resume(investigation_id=inv_id)
        if result.success:
            print(f"Resumed from phase: {result.restored_phase}")
        ```
    """

    storage: CheckpointStorage
    config: CheckpointConfig = field(default_factory=CheckpointConfig)

    def create_checkpoint(
        self,
        investigation_id: UUID,
        current_phase: str,
        sar_phase: SARPhase = SARPhase.SEARCH,
        active_types: list[InformationType] | None = None,
        completed_types: list[InformationType] | None = None,
        type_states: dict[str, dict[str, Any]] | None = None,
        knowledge_snapshot: dict[str, Any] | None = None,
        iteration_count: int = 0,
        queries_executed: int = 0,
        findings_count: int = 0,
        confidence_scores: dict[str, float] | None = None,
        reason: CheckpointReason = CheckpointReason.AUTO_SAVE,
        review_notes: str = "",
        requires_review: bool = False,
        parent_checkpoint_id: UUID | None = None,
    ) -> CheckpointData:
        """Create and save a new checkpoint.

        Args:
            investigation_id: ID of the investigation.
            current_phase: Current investigation phase name.
            sar_phase: Current SAR phase.
            active_types: Currently active information types.
            completed_types: Completed information types.
            type_states: Serialized state for each type.
            knowledge_snapshot: Snapshot of knowledge base.
            iteration_count: Total iterations completed.
            queries_executed: Total queries executed.
            findings_count: Total findings discovered.
            confidence_scores: Confidence score per type.
            reason: Reason for checkpoint.
            review_notes: Notes for manual review.
            requires_review: Whether review is required.
            parent_checkpoint_id: Parent for branching.

        Returns:
            The created checkpoint.
        """
        checkpoint = CheckpointData(
            investigation_id=investigation_id,
            parent_checkpoint_id=parent_checkpoint_id,
            current_phase=current_phase,
            sar_phase=sar_phase,
            active_types=[t.value for t in (active_types or [])],
            completed_types=[t.value for t in (completed_types or [])],
            type_states=type_states or {},
            knowledge_snapshot=knowledge_snapshot or {},
            iteration_count=iteration_count,
            queries_executed=queries_executed,
            findings_count=findings_count,
            confidence_scores=confidence_scores or {},
            reason=reason,
            requires_review=requires_review,
            review_notes=review_notes,
        )

        # Mark previous checkpoint as superseded (unless branching)
        if parent_checkpoint_id is None:
            latest = self.storage.load_latest(investigation_id)
            if latest and latest.checkpoint_id != checkpoint.checkpoint_id:
                self.storage.mark_superseded(latest.checkpoint_id)

        self.storage.save(checkpoint)

        logger.info(
            "Checkpoint created",
            checkpoint_id=str(checkpoint.checkpoint_id),
            investigation_id=str(investigation_id),
            phase=current_phase,
            reason=reason.value,
        )

        # Cleanup old checkpoints if enabled
        if self.config.enable_auto_cleanup:
            self._cleanup_old_checkpoints(investigation_id)

        return checkpoint

    def load_checkpoint(self, checkpoint_id: UUID) -> CheckpointData | None:
        """Load a specific checkpoint.

        Args:
            checkpoint_id: ID of the checkpoint to load.

        Returns:
            The checkpoint data, or None if not found.
        """
        return self.storage.load(checkpoint_id)

    def load_latest(self, investigation_id: UUID) -> CheckpointData | None:
        """Load the most recent checkpoint for an investigation.

        Args:
            investigation_id: ID of the investigation.

        Returns:
            The latest active checkpoint, or None if not found.
        """
        return self.storage.load_latest(investigation_id)

    def resume(
        self,
        investigation_id: UUID,
        checkpoint_id: UUID | None = None,
        strategy: ResumeStrategy = ResumeStrategy.CONTINUE,
    ) -> ResumeResult:
        """Resume an investigation from a checkpoint.

        Args:
            investigation_id: ID of the investigation to resume.
            checkpoint_id: Specific checkpoint to resume from (optional).
            strategy: Resume strategy to use.

        Returns:
            Result of the resume operation.
        """
        # Load checkpoint
        if checkpoint_id:
            checkpoint = self.storage.load(checkpoint_id)
        else:
            checkpoint = self.storage.load_latest(investigation_id)

        if not checkpoint:
            return ResumeResult(
                success=False,
                investigation_id=investigation_id,
                error_message="No checkpoint found for investigation",
            )

        # Mark checkpoint as restored
        checkpoint.status = CheckpointStatus.RESTORED
        self.storage.save(checkpoint)

        # Determine restored types based on strategy
        if strategy == ResumeStrategy.CONTINUE:
            restored_types = checkpoint.active_types + checkpoint.completed_types
            restored_phase = checkpoint.current_phase
        elif strategy == ResumeStrategy.RESTART_PHASE:
            restored_types = checkpoint.completed_types
            restored_phase = checkpoint.current_phase
        else:  # SKIP_TO_NEXT
            restored_types = checkpoint.active_types + checkpoint.completed_types
            restored_phase = self._get_next_phase(checkpoint.current_phase)

        logger.info(
            "Investigation resumed",
            checkpoint_id=str(checkpoint.checkpoint_id),
            investigation_id=str(investigation_id),
            strategy=strategy.value,
            restored_phase=restored_phase,
        )

        return ResumeResult(
            success=True,
            checkpoint_id=checkpoint.checkpoint_id,
            investigation_id=investigation_id,
            restored_phase=restored_phase,
            restored_types=restored_types,
            strategy_used=strategy,
        )

    def create_branch(
        self,
        parent_checkpoint_id: UUID,
        investigation_id: UUID,
        branch_notes: str = "",
    ) -> CheckpointData | None:
        """Create a branch from an existing checkpoint.

        This allows exploring alternative investigation paths
        from a specific point.

        Args:
            parent_checkpoint_id: Checkpoint to branch from.
            investigation_id: New investigation ID for the branch.
            branch_notes: Notes describing the branch purpose.

        Returns:
            The branch checkpoint, or None if parent not found.
        """
        parent = self.storage.load(parent_checkpoint_id)
        if not parent:
            return None

        branch = CheckpointData(
            investigation_id=investigation_id,
            parent_checkpoint_id=parent_checkpoint_id,
            current_phase=parent.current_phase,
            sar_phase=parent.sar_phase,
            active_types=parent.active_types.copy(),
            completed_types=parent.completed_types.copy(),
            type_states=parent.type_states.copy(),
            knowledge_snapshot=parent.knowledge_snapshot.copy(),
            iteration_count=parent.iteration_count,
            queries_executed=parent.queries_executed,
            findings_count=parent.findings_count,
            confidence_scores=parent.confidence_scores.copy(),
            reason=CheckpointReason.BRANCH_POINT,
            review_notes=branch_notes,
        )

        self.storage.save(branch)

        logger.info(
            "Branch created",
            branch_checkpoint_id=str(branch.checkpoint_id),
            parent_checkpoint_id=str(parent_checkpoint_id),
            new_investigation_id=str(investigation_id),
        )

        return branch

    def mark_review_required(
        self,
        investigation_id: UUID,
        review_notes: str,
        current_phase: str = "",
        **state_kwargs: Any,
    ) -> CheckpointData:
        """Create a checkpoint that requires manual review.

        Args:
            investigation_id: ID of the investigation.
            review_notes: Notes describing what needs review.
            current_phase: Current phase name.
            **state_kwargs: Additional state to save.

        Returns:
            The review checkpoint.
        """
        return self.create_checkpoint(
            investigation_id=investigation_id,
            current_phase=current_phase,
            reason=CheckpointReason.REVIEW_REQUIRED,
            review_notes=review_notes,
            requires_review=True,
            **state_kwargs,
        )

    def list_checkpoints(
        self,
        investigation_id: UUID,
        limit: int = 10,
    ) -> list[CheckpointData]:
        """List checkpoints for an investigation.

        Args:
            investigation_id: ID of the investigation.
            limit: Maximum number to return.

        Returns:
            List of checkpoints, newest first.
        """
        return self.storage.list_checkpoints(investigation_id, limit)

    def get_pending_reviews(self, investigation_id: UUID) -> list[CheckpointData]:
        """Get checkpoints requiring manual review.

        Args:
            investigation_id: ID of the investigation.

        Returns:
            List of checkpoints requiring review.
        """
        all_checkpoints = self.storage.list_checkpoints(investigation_id, limit=100)
        return [cp for cp in all_checkpoints if cp.requires_review and cp.status == CheckpointStatus.ACTIVE]

    def _cleanup_old_checkpoints(self, investigation_id: UUID) -> int:
        """Remove old checkpoints beyond the retention limit.

        Args:
            investigation_id: ID of the investigation.

        Returns:
            Number of checkpoints removed.
        """
        checkpoints = self.storage.list_checkpoints(
            investigation_id,
            limit=self.config.max_checkpoints_per_investigation + 10,
        )

        if len(checkpoints) <= self.config.max_checkpoints_per_investigation:
            return 0

        # Keep the most recent N checkpoints, delete the rest
        to_delete = checkpoints[self.config.max_checkpoints_per_investigation:]
        deleted = 0
        for cp in to_delete:
            # Don't delete checkpoints requiring review
            if not cp.requires_review and self.storage.delete(cp.checkpoint_id):
                deleted += 1

        if deleted > 0:
            logger.debug(
                "Cleaned up old checkpoints",
                investigation_id=str(investigation_id),
                deleted_count=deleted,
            )

        return deleted

    def _get_next_phase(self, current_phase: str) -> str:
        """Get the next phase name after the current one.

        Args:
            current_phase: Current phase name.

        Returns:
            Next phase name.
        """
        # Phase order from architecture
        phase_order = [
            "foundation",
            "records",
            "intelligence",
            "network",
            "reconciliation",
        ]

        try:
            idx = phase_order.index(current_phase.lower())
            if idx < len(phase_order) - 1:
                return phase_order[idx + 1]
        except ValueError:
            pass

        return current_phase  # Stay on current if not found or last


def create_checkpoint_manager(
    storage: CheckpointStorage | None = None,
    config: CheckpointConfig | None = None,
) -> CheckpointManager:
    """Create a checkpoint manager.

    Args:
        storage: Storage backend. Defaults to in-memory.
        config: Manager configuration.

    Returns:
        Configured CheckpointManager.
    """
    return CheckpointManager(
        storage=storage or InMemoryCheckpointStorage(),
        config=config or CheckpointConfig(),
    )
