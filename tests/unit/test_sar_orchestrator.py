"""Tests for the SARLoopOrchestrator module.

Tests cover:
- Single type SAR cycle execution
- Multi-type investigation execution
- Progress event tracking
- Error handling and recovery
- Configuration options
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from elile.agent.state import InformationType, KnowledgeBase, ServiceTier
from elile.compliance.types import Locale
from elile.investigation.models import CompletionReason, SARPhase
from elile.investigation.sar_orchestrator import (
    InvestigationResult,
    OrchestratorConfig,
    OrchestratorPhase,
    ProgressEvent,
    SARLoopOrchestrator,
    TypeCycleResult,
    create_sar_orchestrator,
)


class TestProgressEvent:
    """Tests for ProgressEvent dataclass."""

    def test_progress_event_defaults(self) -> None:
        """Test default progress event values."""
        event = ProgressEvent()
        assert event.event_type == ""
        assert event.info_type is None
        assert event.phase is None
        assert event.progress_percent == 0.0

    def test_progress_event_to_dict(self) -> None:
        """Test progress event serialization."""
        event = ProgressEvent(
            event_type="type_started",
            info_type=InformationType.IDENTITY,
            phase=OrchestratorPhase.PLANNING,
            iteration_number=1,
            message="Planning queries",
            progress_percent=25.0,
        )
        d = event.to_dict()
        assert d["event_type"] == "type_started"
        assert d["info_type"] == "identity"
        assert d["phase"] == "planning"
        assert d["iteration_number"] == 1
        assert d["progress_percent"] == 25.0


class TestTypeCycleResult:
    """Tests for TypeCycleResult dataclass."""

    def test_type_cycle_result_defaults(self) -> None:
        """Test default result values."""
        result = TypeCycleResult()
        assert result.info_type == InformationType.IDENTITY
        assert result.iterations_completed == 0
        assert result.error_occurred is False

    def test_type_cycle_result_with_values(self) -> None:
        """Test result with populated values."""
        result = TypeCycleResult(
            info_type=InformationType.CRIMINAL,
            iterations_completed=2,
            total_queries_executed=10,
            total_facts_extracted=15,
            final_confidence=0.88,
            completion_reason=CompletionReason.CONFIDENCE_MET,
        )
        assert result.info_type == InformationType.CRIMINAL
        assert result.iterations_completed == 2
        assert result.final_confidence == 0.88

    def test_type_cycle_result_to_dict(self) -> None:
        """Test result serialization."""
        result = TypeCycleResult(
            info_type=InformationType.CRIMINAL,
            iterations_completed=2,
            completion_reason=CompletionReason.CONFIDENCE_MET,
        )
        d = result.to_dict()
        assert d["info_type"] == "criminal"
        assert d["completion_reason"] == "confidence_met"


class TestInvestigationResult:
    """Tests for InvestigationResult dataclass."""

    def test_investigation_result_defaults(self) -> None:
        """Test default investigation result values."""
        result = InvestigationResult()
        assert result.types_completed == 0
        assert result.types_failed == 0
        assert result.is_complete is False
        assert result.has_errors is False

    def test_add_type_result(self) -> None:
        """Test adding type results updates statistics."""
        result = InvestigationResult()

        type_result = TypeCycleResult(
            info_type=InformationType.IDENTITY,
            iterations_completed=2,
            total_queries_executed=5,
            total_facts_extracted=10,
            final_confidence=0.90,
            completion_reason=CompletionReason.CONFIDENCE_MET,
        )
        result.add_type_result(type_result)

        assert result.types_completed == 1
        assert result.total_iterations == 2
        assert result.total_queries == 5
        assert result.total_facts == 10

    def test_add_failed_type_result(self) -> None:
        """Test adding failed type result."""
        result = InvestigationResult()

        type_result = TypeCycleResult(
            info_type=InformationType.CRIMINAL,
            error_occurred=True,
            error_message="Query failed",
        )
        result.add_type_result(type_result)

        assert result.types_failed == 1
        assert result.types_completed == 0
        assert result.has_errors is True

    def test_add_skipped_type_result(self) -> None:
        """Test adding skipped type result."""
        result = InvestigationResult()

        type_result = TypeCycleResult(
            info_type=InformationType.NETWORK_D3,
            completion_reason=CompletionReason.SKIPPED,
        )
        result.add_type_result(type_result)

        assert result.types_skipped == 1
        assert result.types_completed == 0

    def test_confidence_metrics_calculation(self) -> None:
        """Test confidence metrics are calculated correctly."""
        result = InvestigationResult()

        result.add_type_result(
            TypeCycleResult(
                info_type=InformationType.IDENTITY,
                final_confidence=0.90,
                completion_reason=CompletionReason.CONFIDENCE_MET,
            )
        )
        result.add_type_result(
            TypeCycleResult(
                info_type=InformationType.EMPLOYMENT,
                final_confidence=0.80,
                completion_reason=CompletionReason.MAX_ITERATIONS,
            )
        )

        assert result.average_confidence == pytest.approx(0.85)
        assert result.lowest_confidence == 0.80
        assert result.lowest_confidence_type == InformationType.EMPLOYMENT

    def test_finalize(self) -> None:
        """Test finalization sets completion status."""
        result = InvestigationResult()
        result.finalize()

        assert result.is_complete is True
        assert result.completed_at is not None
        assert result.duration_ms >= 0


class TestOrchestratorConfig:
    """Tests for OrchestratorConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = OrchestratorConfig()
        assert config.max_concurrent_types == 1
        assert config.enable_parallel_queries is True
        assert config.continue_on_type_error is True
        assert config.emit_progress_events is True


class TestSARLoopOrchestrator:
    """Tests for SARLoopOrchestrator."""

    @pytest.fixture
    def orchestrator(self) -> SARLoopOrchestrator:
        """Create an orchestrator with default config."""
        return SARLoopOrchestrator()

    def test_orchestrator_initialization(self, orchestrator: SARLoopOrchestrator) -> None:
        """Test orchestrator initializes with all components."""
        assert orchestrator.state is not None
        assert orchestrator.planner is not None
        # assessor is created lazily with knowledge base, so may be None
        assert orchestrator.refiner is not None
        assert orchestrator.controller is not None
        assert orchestrator.types is not None

    def test_add_progress_callback(self, orchestrator: SARLoopOrchestrator) -> None:
        """Test adding progress callback."""
        callback = MagicMock()
        orchestrator.add_progress_callback(callback)

        assert callback in orchestrator._progress_callbacks

    def test_remove_progress_callback(self, orchestrator: SARLoopOrchestrator) -> None:
        """Test removing progress callback."""
        callback = MagicMock()
        orchestrator.add_progress_callback(callback)
        orchestrator.remove_progress_callback(callback)

        assert callback not in orchestrator._progress_callbacks

    def test_get_summary(self, orchestrator: SARLoopOrchestrator) -> None:
        """Test getting SAR summary."""
        summary = orchestrator.get_summary()
        assert summary is not None
        assert summary.types_initialized == 0

    @pytest.mark.asyncio
    async def test_execute_single_type_no_executor(self, orchestrator: SARLoopOrchestrator) -> None:
        """Test executing single type without executor uses mock results."""
        result = await orchestrator.execute_single_type(
            info_type=InformationType.IDENTITY,
            subject_name="John Smith",
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
        )

        # Without a real executor, should still complete with mock results
        assert result.info_type == InformationType.IDENTITY
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_progress_events_emitted(self) -> None:
        """Test that progress events are emitted during execution."""
        orchestrator = SARLoopOrchestrator()
        events: list[ProgressEvent] = []

        def capture_event(event: ProgressEvent) -> None:
            events.append(event)

        orchestrator.add_progress_callback(capture_event)

        await orchestrator.execute_single_type(
            info_type=InformationType.IDENTITY,
            subject_name="John Smith",
        )

        # Should have emitted at least search and assess events
        assert len(events) > 0
        event_types = [e.event_type for e in events]
        assert "search_started" in event_types or "type_started" in event_types

    @pytest.mark.asyncio
    async def test_progress_events_disabled(self) -> None:
        """Test that progress events can be disabled."""
        config = OrchestratorConfig(emit_progress_events=False)
        orchestrator = SARLoopOrchestrator(config=config)
        events: list[ProgressEvent] = []

        def capture_event(event: ProgressEvent) -> None:
            events.append(event)

        orchestrator.add_progress_callback(capture_event)

        await orchestrator.execute_single_type(
            info_type=InformationType.IDENTITY,
            subject_name="John Smith",
        )

        # No events should be emitted
        assert len(events) == 0


class TestCreateSarOrchestrator:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating orchestrator with defaults."""
        orchestrator = create_sar_orchestrator()
        assert isinstance(orchestrator, SARLoopOrchestrator)

    def test_create_with_config(self) -> None:
        """Test creating orchestrator with custom config."""
        config = OrchestratorConfig(max_concurrent_types=3)
        orchestrator = create_sar_orchestrator(config=config)
        assert orchestrator.config.max_concurrent_types == 3
