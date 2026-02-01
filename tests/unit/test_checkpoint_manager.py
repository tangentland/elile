"""Tests for the Investigation Checkpoint Manager.

Tests cover:
- Checkpoint creation and storage
- Resume from checkpoint
- Branching from checkpoints
- Review point management
- Cleanup and expiry
"""

import pytest
from uuid import uuid4

from elile.agent.state import InformationType
from elile.investigation.checkpoint import (
    CheckpointConfig,
    CheckpointData,
    CheckpointManager,
    CheckpointReason,
    CheckpointStatus,
    InMemoryCheckpointStorage,
    ResumeResult,
    ResumeStrategy,
    create_checkpoint_manager,
)
from elile.investigation.models import SARPhase


class TestCheckpointData:
    """Tests for CheckpointData dataclass."""

    def test_checkpoint_data_defaults(self) -> None:
        """Test default checkpoint data values."""
        checkpoint = CheckpointData()
        assert checkpoint.current_phase == ""
        assert checkpoint.sar_phase == SARPhase.SEARCH
        assert checkpoint.status == CheckpointStatus.ACTIVE
        assert checkpoint.reason == CheckpointReason.AUTO_SAVE
        assert checkpoint.requires_review is False

    def test_checkpoint_data_with_values(self) -> None:
        """Test checkpoint with full values."""
        investigation_id = uuid4()
        checkpoint = CheckpointData(
            investigation_id=investigation_id,
            current_phase="foundation",
            sar_phase=SARPhase.SEARCH,
            active_types=["identity", "employment"],
            completed_types=["education"],
            iteration_count=5,
            queries_executed=12,
            findings_count=8,
            confidence_scores={"identity": 0.85, "employment": 0.75},
            reason=CheckpointReason.PHASE_COMPLETE,
        )
        assert checkpoint.investigation_id == investigation_id
        assert checkpoint.current_phase == "foundation"
        assert len(checkpoint.active_types) == 2
        assert checkpoint.iteration_count == 5

    def test_checkpoint_data_to_dict(self) -> None:
        """Test checkpoint serialization."""
        checkpoint = CheckpointData(
            current_phase="records",
            sar_phase=SARPhase.ASSESS,
            reason=CheckpointReason.MANUAL_PAUSE,
        )
        d = checkpoint.to_dict()
        assert d["current_phase"] == "records"
        assert d["sar_phase"] == "assess"
        assert d["reason"] == "manual_pause"
        assert "checkpoint_id" in d

    def test_checkpoint_data_from_dict(self) -> None:
        """Test checkpoint deserialization."""
        original = CheckpointData(
            current_phase="intelligence",
            sar_phase=SARPhase.REFINE,
            active_types=["criminal", "civil"],
            iteration_count=3,
        )
        d = original.to_dict()
        restored = CheckpointData.from_dict(d)

        assert restored.checkpoint_id == original.checkpoint_id
        assert restored.current_phase == "intelligence"
        assert restored.sar_phase == SARPhase.REFINE
        assert restored.active_types == ["criminal", "civil"]


class TestInMemoryCheckpointStorage:
    """Tests for InMemoryCheckpointStorage."""

    @pytest.fixture
    def storage(self) -> InMemoryCheckpointStorage:
        """Create storage instance."""
        return InMemoryCheckpointStorage()

    def test_save_and_load(self, storage: InMemoryCheckpointStorage) -> None:
        """Test saving and loading checkpoint."""
        checkpoint = CheckpointData(current_phase="test")
        storage.save(checkpoint)

        loaded = storage.load(checkpoint.checkpoint_id)
        assert loaded is not None
        assert loaded.checkpoint_id == checkpoint.checkpoint_id
        assert loaded.current_phase == "test"

    def test_load_nonexistent(self, storage: InMemoryCheckpointStorage) -> None:
        """Test loading nonexistent checkpoint."""
        loaded = storage.load(uuid4())
        assert loaded is None

    def test_load_latest(self, storage: InMemoryCheckpointStorage) -> None:
        """Test loading latest checkpoint."""
        investigation_id = uuid4()

        cp1 = CheckpointData(investigation_id=investigation_id, current_phase="first")
        storage.save(cp1)

        cp2 = CheckpointData(investigation_id=investigation_id, current_phase="second")
        storage.save(cp2)

        latest = storage.load_latest(investigation_id)
        assert latest is not None
        assert latest.current_phase == "second"

    def test_load_latest_skips_superseded(self, storage: InMemoryCheckpointStorage) -> None:
        """Test that load_latest skips superseded checkpoints."""
        investigation_id = uuid4()

        cp1 = CheckpointData(investigation_id=investigation_id, current_phase="active")
        storage.save(cp1)

        cp2 = CheckpointData(
            investigation_id=investigation_id,
            current_phase="superseded",
            status=CheckpointStatus.SUPERSEDED,
        )
        storage.save(cp2)

        latest = storage.load_latest(investigation_id)
        assert latest is not None
        assert latest.current_phase == "active"

    def test_list_checkpoints(self, storage: InMemoryCheckpointStorage) -> None:
        """Test listing checkpoints."""
        investigation_id = uuid4()

        for i in range(5):
            cp = CheckpointData(investigation_id=investigation_id, current_phase=f"phase_{i}")
            storage.save(cp)

        checkpoints = storage.list_checkpoints(investigation_id, limit=3)
        assert len(checkpoints) == 3

    def test_delete_checkpoint(self, storage: InMemoryCheckpointStorage) -> None:
        """Test deleting checkpoint."""
        checkpoint = CheckpointData(current_phase="to_delete")
        storage.save(checkpoint)

        result = storage.delete(checkpoint.checkpoint_id)
        assert result is True

        loaded = storage.load(checkpoint.checkpoint_id)
        assert loaded is None

    def test_delete_nonexistent(self, storage: InMemoryCheckpointStorage) -> None:
        """Test deleting nonexistent checkpoint."""
        result = storage.delete(uuid4())
        assert result is False

    def test_mark_superseded(self, storage: InMemoryCheckpointStorage) -> None:
        """Test marking checkpoint as superseded."""
        checkpoint = CheckpointData(current_phase="test")
        storage.save(checkpoint)

        storage.mark_superseded(checkpoint.checkpoint_id)

        loaded = storage.load(checkpoint.checkpoint_id)
        assert loaded is not None
        assert loaded.status == CheckpointStatus.SUPERSEDED


class TestCheckpointConfig:
    """Tests for CheckpointConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = CheckpointConfig()
        assert config.auto_checkpoint_interval == 5
        assert config.max_checkpoints_per_investigation == 20
        assert config.checkpoint_expiry_hours == 168
        assert config.enable_auto_cleanup is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = CheckpointConfig(
            auto_checkpoint_interval=10,
            max_checkpoints_per_investigation=50,
            enable_auto_cleanup=False,
        )
        assert config.auto_checkpoint_interval == 10
        assert config.max_checkpoints_per_investigation == 50
        assert config.enable_auto_cleanup is False


class TestCheckpointManager:
    """Tests for CheckpointManager."""

    @pytest.fixture
    def manager(self) -> CheckpointManager:
        """Create manager with in-memory storage."""
        storage = InMemoryCheckpointStorage()
        return CheckpointManager(storage=storage)

    def test_create_checkpoint(self, manager: CheckpointManager) -> None:
        """Test creating a checkpoint."""
        investigation_id = uuid4()

        checkpoint = manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="foundation",
            sar_phase=SARPhase.SEARCH,
            active_types=[InformationType.IDENTITY],
            iteration_count=3,
        )

        assert checkpoint.investigation_id == investigation_id
        assert checkpoint.current_phase == "foundation"
        assert checkpoint.status == CheckpointStatus.ACTIVE
        assert "identity" in checkpoint.active_types

    def test_create_checkpoint_marks_previous_superseded(
        self, manager: CheckpointManager
    ) -> None:
        """Test that new checkpoint supersedes previous."""
        investigation_id = uuid4()

        cp1 = manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="first",
        )

        cp2 = manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="second",
        )

        # First checkpoint should be superseded
        loaded = manager.load_checkpoint(cp1.checkpoint_id)
        assert loaded is not None
        assert loaded.status == CheckpointStatus.SUPERSEDED

        # Second checkpoint should be active
        loaded = manager.load_checkpoint(cp2.checkpoint_id)
        assert loaded is not None
        assert loaded.status == CheckpointStatus.ACTIVE

    def test_load_checkpoint(self, manager: CheckpointManager) -> None:
        """Test loading a specific checkpoint."""
        investigation_id = uuid4()

        created = manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="test",
        )

        loaded = manager.load_checkpoint(created.checkpoint_id)
        assert loaded is not None
        assert loaded.checkpoint_id == created.checkpoint_id

    def test_load_latest(self, manager: CheckpointManager) -> None:
        """Test loading latest checkpoint."""
        investigation_id = uuid4()

        manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="first",
        )

        manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="second",
        )

        latest = manager.load_latest(investigation_id)
        assert latest is not None
        assert latest.current_phase == "second"

    def test_resume_continue(self, manager: CheckpointManager) -> None:
        """Test resuming with continue strategy."""
        investigation_id = uuid4()

        manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="records",
            active_types=[InformationType.CRIMINAL],
            completed_types=[InformationType.IDENTITY],
        )

        result = manager.resume(
            investigation_id=investigation_id,
            strategy=ResumeStrategy.CONTINUE,
        )

        assert result.success is True
        assert result.restored_phase == "records"
        assert "criminal" in result.restored_types
        assert "identity" in result.restored_types
        assert result.strategy_used == ResumeStrategy.CONTINUE

    def test_resume_restart_phase(self, manager: CheckpointManager) -> None:
        """Test resuming with restart phase strategy."""
        investigation_id = uuid4()

        manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="records",
            active_types=[InformationType.CRIMINAL],
            completed_types=[InformationType.IDENTITY],
        )

        result = manager.resume(
            investigation_id=investigation_id,
            strategy=ResumeStrategy.RESTART_PHASE,
        )

        assert result.success is True
        assert result.restored_phase == "records"
        # Only completed types restored
        assert "criminal" not in result.restored_types
        assert "identity" in result.restored_types

    def test_resume_skip_to_next(self, manager: CheckpointManager) -> None:
        """Test resuming with skip to next strategy."""
        investigation_id = uuid4()

        manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="foundation",
            active_types=[InformationType.IDENTITY],
        )

        result = manager.resume(
            investigation_id=investigation_id,
            strategy=ResumeStrategy.SKIP_TO_NEXT,
        )

        assert result.success is True
        assert result.restored_phase == "records"  # Next after foundation

    def test_resume_no_checkpoint(self, manager: CheckpointManager) -> None:
        """Test resuming when no checkpoint exists."""
        result = manager.resume(investigation_id=uuid4())

        assert result.success is False
        assert "No checkpoint found" in (result.error_message or "")

    def test_resume_specific_checkpoint(self, manager: CheckpointManager) -> None:
        """Test resuming from specific checkpoint."""
        investigation_id = uuid4()

        cp1 = manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="first",
        )

        manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="second",
        )

        result = manager.resume(
            investigation_id=investigation_id,
            checkpoint_id=cp1.checkpoint_id,
        )

        assert result.success is True
        assert result.checkpoint_id == cp1.checkpoint_id
        assert result.restored_phase == "first"

    def test_create_branch(self, manager: CheckpointManager) -> None:
        """Test creating a branch from checkpoint."""
        original_investigation_id = uuid4()
        new_investigation_id = uuid4()

        parent = manager.create_checkpoint(
            investigation_id=original_investigation_id,
            current_phase="records",
            active_types=[InformationType.CRIMINAL],
            iteration_count=5,
        )

        branch = manager.create_branch(
            parent_checkpoint_id=parent.checkpoint_id,
            investigation_id=new_investigation_id,
            branch_notes="Alternative investigation path",
        )

        assert branch is not None
        assert branch.investigation_id == new_investigation_id
        assert branch.parent_checkpoint_id == parent.checkpoint_id
        assert branch.current_phase == "records"
        assert branch.iteration_count == 5
        assert branch.reason == CheckpointReason.BRANCH_POINT

    def test_create_branch_nonexistent(self, manager: CheckpointManager) -> None:
        """Test branching from nonexistent checkpoint."""
        result = manager.create_branch(
            parent_checkpoint_id=uuid4(),
            investigation_id=uuid4(),
        )
        assert result is None

    def test_mark_review_required(self, manager: CheckpointManager) -> None:
        """Test marking investigation for review."""
        investigation_id = uuid4()

        checkpoint = manager.mark_review_required(
            investigation_id=investigation_id,
            review_notes="Found conflicting data that needs human review",
            current_phase="reconciliation",
        )

        assert checkpoint.requires_review is True
        assert checkpoint.reason == CheckpointReason.REVIEW_REQUIRED
        assert "conflicting data" in checkpoint.review_notes

    def test_list_checkpoints(self, manager: CheckpointManager) -> None:
        """Test listing investigation checkpoints."""
        investigation_id = uuid4()

        for i in range(5):
            # Create with branching to avoid superseding
            manager.create_checkpoint(
                investigation_id=investigation_id,
                current_phase=f"phase_{i}",
                parent_checkpoint_id=uuid4(),  # Fake parent to prevent superseding
            )

        checkpoints = manager.list_checkpoints(investigation_id, limit=3)
        assert len(checkpoints) == 3

    def test_get_pending_reviews(self, manager: CheckpointManager) -> None:
        """Test getting pending review checkpoints."""
        investigation_id = uuid4()

        # Create regular checkpoint
        manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="normal",
            parent_checkpoint_id=uuid4(),
        )

        # Create review checkpoint
        manager.mark_review_required(
            investigation_id=investigation_id,
            review_notes="Needs review",
            current_phase="review",
        )

        pending = manager.get_pending_reviews(investigation_id)
        assert len(pending) == 1
        assert pending[0].current_phase == "review"

    def test_cleanup_old_checkpoints(self) -> None:
        """Test automatic cleanup of old checkpoints."""
        config = CheckpointConfig(
            max_checkpoints_per_investigation=5,  # Minimum allowed
            enable_auto_cleanup=True,
        )
        storage = InMemoryCheckpointStorage()
        manager = CheckpointManager(storage=storage, config=config)

        investigation_id = uuid4()

        # Create more checkpoints than limit
        for i in range(8):
            manager.create_checkpoint(
                investigation_id=investigation_id,
                current_phase=f"phase_{i}",
                parent_checkpoint_id=uuid4(),  # Prevent superseding
            )

        checkpoints = manager.list_checkpoints(investigation_id, limit=20)
        assert len(checkpoints) <= 5


class TestResumeResult:
    """Tests for ResumeResult."""

    def test_result_defaults(self) -> None:
        """Test default result values."""
        result = ResumeResult()
        assert result.success is True
        assert result.strategy_used == ResumeStrategy.CONTINUE

    def test_result_to_dict(self) -> None:
        """Test result serialization."""
        result = ResumeResult(
            success=True,
            checkpoint_id=uuid4(),
            restored_phase="records",
            restored_types=["identity", "employment"],
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["restored_phase"] == "records"
        assert len(d["restored_types"]) == 2


class TestCreateCheckpointManager:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating manager with defaults."""
        manager = create_checkpoint_manager()
        assert isinstance(manager, CheckpointManager)

    def test_create_with_custom_storage(self) -> None:
        """Test creating manager with custom storage."""
        storage = InMemoryCheckpointStorage()
        manager = create_checkpoint_manager(storage=storage)
        assert manager.storage is storage

    def test_create_with_custom_config(self) -> None:
        """Test creating manager with custom config."""
        config = CheckpointConfig(auto_checkpoint_interval=10)
        manager = create_checkpoint_manager(config=config)
        assert manager.config.auto_checkpoint_interval == 10
