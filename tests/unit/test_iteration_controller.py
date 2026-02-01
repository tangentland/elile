"""Tests for the IterationController module.

Tests cover:
- Confidence threshold detection
- Max iteration enforcement
- Diminishing returns detection
- Foundation vs. standard type thresholds
- Iteration decision logic
"""

import pytest

from elile.agent.state import InformationType
from elile.investigation.iteration_controller import (
    ControllerConfig,
    DecisionType,
    IterationController,
    IterationDecision,
    create_iteration_controller,
)
from elile.investigation.models import (
    SARConfig,
    SARIterationState,
    SARPhase,
    SARTypeState,
)


class TestIterationDecision:
    """Tests for IterationDecision dataclass."""

    def test_decision_defaults(self) -> None:
        """Test default decision values."""
        decision = IterationDecision()
        assert decision.should_continue is True
        assert decision.decision_type == DecisionType.CONTINUE
        assert decision.next_phase == SARPhase.REFINE
        assert decision.completion_type is None

    def test_decision_completion_type(self) -> None:
        """Test completion_type property."""
        # Continue decision has no completion type
        decision = IterationDecision(should_continue=True)
        assert decision.completion_type is None

        # Stop decision has completion type
        decision = IterationDecision(
            should_continue=False,
            decision_type=DecisionType.THRESHOLD,
        )
        assert decision.completion_type == "threshold"

    def test_decision_to_dict(self) -> None:
        """Test decision serialization."""
        decision = IterationDecision(
            should_continue=False,
            decision_type=DecisionType.CAPPED,
            reason="max_iterations_reached",
            confidence_score=0.75,
        )
        d = decision.to_dict()
        assert d["should_continue"] is False
        assert d["decision_type"] == "capped"
        assert d["reason"] == "max_iterations_reached"
        assert d["confidence_score"] == 0.75


class TestControllerConfig:
    """Tests for ControllerConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ControllerConfig()
        assert config.confidence_threshold == 0.85
        assert config.foundation_confidence_threshold == 0.90
        assert config.max_iterations_per_type == 3
        assert config.foundation_max_iterations == 4
        assert config.min_gain_threshold == 0.1

    def test_from_sar_config(self) -> None:
        """Test creating from SARConfig."""
        sar_config = SARConfig(
            confidence_threshold=0.80,
            max_iterations_per_type=5,
        )
        config = ControllerConfig.from_sar_config(sar_config)
        assert config.confidence_threshold == 0.80
        assert config.max_iterations_per_type == 5


class TestIterationController:
    """Tests for IterationController."""

    @pytest.fixture
    def controller(self) -> IterationController:
        """Create a controller with default config."""
        return IterationController()

    @pytest.fixture
    def state(self) -> SARTypeState:
        """Create a type state for testing."""
        return SARTypeState(info_type=InformationType.IDENTITY)

    def test_is_foundation_type(self, controller: IterationController) -> None:
        """Test foundation type detection."""
        assert controller.is_foundation_type(InformationType.IDENTITY) is True
        assert controller.is_foundation_type(InformationType.EMPLOYMENT) is True
        assert controller.is_foundation_type(InformationType.EDUCATION) is True
        assert controller.is_foundation_type(InformationType.CRIMINAL) is False
        assert controller.is_foundation_type(InformationType.FINANCIAL) is False

    def test_get_confidence_threshold_foundation(self, controller: IterationController) -> None:
        """Test foundation types get higher threshold."""
        # Foundation types get 0.90
        assert controller.get_confidence_threshold(InformationType.IDENTITY) == 0.90
        assert controller.get_confidence_threshold(InformationType.EMPLOYMENT) == 0.90

        # Standard types get 0.85
        assert controller.get_confidence_threshold(InformationType.CRIMINAL) == 0.85

    def test_get_max_iterations_foundation(self, controller: IterationController) -> None:
        """Test foundation types get more iterations."""
        # Foundation types get 4 iterations
        assert controller.get_max_iterations(InformationType.IDENTITY) == 4

        # Standard types get 3 iterations
        assert controller.get_max_iterations(InformationType.CRIMINAL) == 3

    def test_continue_when_criteria_not_met(
        self, controller: IterationController, state: SARTypeState
    ) -> None:
        """Test continue decision when no criteria met."""
        iteration = SARIterationState(
            iteration_number=1,
            confidence_score=0.50,
            info_gain_rate=0.5,
        )

        decision = controller.should_continue_iteration(
            InformationType.CRIMINAL,  # Standard type, threshold 0.85
            iteration,
            state,
        )

        assert decision.should_continue is True
        assert decision.decision_type == DecisionType.CONTINUE
        assert decision.next_phase == SARPhase.REFINE

    def test_stop_on_confidence_threshold(
        self, controller: IterationController, state: SARTypeState
    ) -> None:
        """Test stop when confidence threshold met."""
        iteration = SARIterationState(
            iteration_number=1,
            confidence_score=0.90,  # Above 0.85 threshold
            info_gain_rate=0.5,
        )

        decision = controller.should_continue_iteration(
            InformationType.CRIMINAL,
            iteration,
            state,
        )

        assert decision.should_continue is False
        assert decision.decision_type == DecisionType.THRESHOLD
        assert decision.next_phase == SARPhase.COMPLETE
        assert decision.reason == "confidence_threshold_met"

    def test_stop_on_max_iterations(
        self, controller: IterationController, state: SARTypeState
    ) -> None:
        """Test stop when max iterations reached."""
        iteration = SARIterationState(
            iteration_number=3,  # Max for standard types
            confidence_score=0.70,  # Below threshold
            info_gain_rate=0.5,
        )

        decision = controller.should_continue_iteration(
            InformationType.CRIMINAL,
            iteration,
            state,
        )

        assert decision.should_continue is False
        assert decision.decision_type == DecisionType.CAPPED
        assert decision.next_phase == SARPhase.CAPPED
        assert decision.reason == "max_iterations_reached"

    def test_foundation_type_gets_more_iterations(self, controller: IterationController) -> None:
        """Test foundation types can iterate more."""
        state = SARTypeState(info_type=InformationType.IDENTITY)
        iteration = SARIterationState(
            iteration_number=3,  # Would be max for standard
            confidence_score=0.70,
            info_gain_rate=0.5,
        )

        decision = controller.should_continue_iteration(
            InformationType.IDENTITY,
            iteration,
            state,
        )

        # Foundation types get 4 iterations, so should continue at 3
        assert decision.should_continue is True
        assert decision.decision_type == DecisionType.CONTINUE

    def test_stop_on_diminishing_returns_low_gain(self, controller: IterationController) -> None:
        """Test stop when info gain rate is too low."""
        state = SARTypeState(info_type=InformationType.CRIMINAL)
        # Add a previous iteration for history
        prev_iteration = SARIterationState(
            iteration_number=1,
            confidence_score=0.50,
        )
        state.iterations.append(prev_iteration)

        current = SARIterationState(
            iteration_number=2,
            confidence_score=0.55,
            info_gain_rate=0.05,  # Below 0.1 threshold
        )

        decision = controller.should_continue_iteration(
            InformationType.CRIMINAL,
            current,
            state,
        )

        assert decision.should_continue is False
        assert decision.decision_type == DecisionType.DIMINISHED
        assert decision.next_phase == SARPhase.DIMINISHED

    def test_stop_on_diminishing_returns_low_confidence_improvement(
        self, controller: IterationController
    ) -> None:
        """Test stop when confidence improvement is too small."""
        state = SARTypeState(info_type=InformationType.CRIMINAL)
        prev_iteration = SARIterationState(
            iteration_number=1,
            confidence_score=0.60,
        )
        state.iterations.append(prev_iteration)

        current = SARIterationState(
            iteration_number=2,
            confidence_score=0.62,  # Only 0.02 improvement, below 0.05 threshold
            info_gain_rate=0.2,  # Above threshold
        )

        decision = controller.should_continue_iteration(
            InformationType.CRIMINAL,
            current,
            state,
        )

        assert decision.should_continue is False
        assert decision.decision_type == DecisionType.DIMINISHED

    def test_no_diminishing_returns_on_first_iteration(
        self, controller: IterationController
    ) -> None:
        """Test that diminishing returns not checked on first iteration."""
        state = SARTypeState(info_type=InformationType.CRIMINAL)
        iteration = SARIterationState(
            iteration_number=1,
            confidence_score=0.30,
            info_gain_rate=0.05,  # Low, but shouldn't trigger on first iteration
        )

        decision = controller.should_continue_iteration(
            InformationType.CRIMINAL,
            iteration,
            state,
        )

        # Should continue since first iteration skips diminishing returns check
        assert decision.should_continue is True
        assert decision.decision_type == DecisionType.CONTINUE

    def test_decision_includes_context(
        self, controller: IterationController, state: SARTypeState
    ) -> None:
        """Test that decision includes useful context."""
        iteration = SARIterationState(
            iteration_number=2,
            confidence_score=0.75,
            info_gain_rate=0.3,
        )
        state.iterations.append(SARIterationState(iteration_number=1, confidence_score=0.50))

        decision = controller.should_continue_iteration(
            InformationType.CRIMINAL,
            iteration,
            state,
        )

        assert decision.confidence_score == 0.75
        assert decision.confidence_threshold == 0.85
        assert decision.iteration_number == 2
        assert decision.info_gain_rate == 0.3
        assert "is_foundation" in decision.factors
        assert "max_iterations" in decision.factors

    def test_decision_history_tracking(self, controller: IterationController) -> None:
        """Test that decisions are recorded."""
        state = SARTypeState(info_type=InformationType.CRIMINAL)
        iteration = SARIterationState(iteration_number=1, confidence_score=0.50)

        controller.should_continue_iteration(
            InformationType.CRIMINAL,
            iteration,
            state,
        )

        history = controller.get_decision_history()
        assert len(history) == 1
        assert history[0].factors["info_type"] == "criminal"

    def test_reset_clears_history(self, controller: IterationController) -> None:
        """Test that reset clears decision history."""
        state = SARTypeState(info_type=InformationType.CRIMINAL)
        iteration = SARIterationState(iteration_number=1, confidence_score=0.50)

        controller.should_continue_iteration(
            InformationType.CRIMINAL,
            iteration,
            state,
        )
        assert len(controller.get_decision_history()) == 1

        controller.reset()
        assert len(controller.get_decision_history()) == 0

    def test_custom_config(self) -> None:
        """Test controller with custom configuration."""
        config = ControllerConfig(
            confidence_threshold=0.70,
            max_iterations_per_type=5,
            min_gain_threshold=0.2,
        )
        controller = IterationController(config=config)

        assert controller.get_confidence_threshold(InformationType.CRIMINAL) == 0.70
        assert controller.get_max_iterations(InformationType.CRIMINAL) == 5

    def test_early_stop_disabled(self) -> None:
        """Test that early stopping can be disabled."""
        config = ControllerConfig(enable_early_stop=False)
        controller = IterationController(config=config)

        state = SARTypeState(info_type=InformationType.CRIMINAL)
        state.iterations.append(SARIterationState(iteration_number=1, confidence_score=0.50))

        current = SARIterationState(
            iteration_number=2,
            confidence_score=0.52,  # Very low improvement
            info_gain_rate=0.02,  # Very low gain
        )

        decision = controller.should_continue_iteration(
            InformationType.CRIMINAL,
            current,
            state,
        )

        # Should continue despite low gains because early_stop is disabled
        assert decision.should_continue is True


class TestCreateIterationController:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating controller with defaults."""
        controller = create_iteration_controller()
        assert isinstance(controller, IterationController)
        assert controller.config.confidence_threshold == 0.85

    def test_create_with_sar_config(self) -> None:
        """Test creating controller from SARConfig."""
        sar_config = SARConfig(confidence_threshold=0.75)
        controller = create_iteration_controller(config=sar_config)
        assert controller.config.confidence_threshold == 0.75

    def test_create_with_controller_config(self) -> None:
        """Test creating controller with ControllerConfig."""
        config = ControllerConfig(max_iterations_per_type=10)
        controller = create_iteration_controller(config=config)
        assert controller.config.max_iterations_per_type == 10
