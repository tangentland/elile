"""Iteration Controller for SAR loop flow control.

This module provides the IterationController that manages SAR loop iterations,
enforcing max limits, detecting diminishing returns, and controlling iteration
flow with proper state transitions.

The controller makes decisions about:
- Whether to continue iterating
- When confidence threshold is met
- When max iterations are reached
- When diminishing returns are detected

Architecture Reference: docs/architecture/05-investigation.md
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import InformationType
from elile.core.logging import get_logger
from elile.investigation.models import (
    CompletionReason,
    SARConfig,
    SARIterationState,
    SARPhase,
    SARTypeState,
)

if TYPE_CHECKING:
    from elile.core.audit import AuditLogger
    from elile.investigation.confidence_scorer import ConfidenceScorer

logger = get_logger(__name__)


# Foundation types that require higher confidence and more iterations
FOUNDATION_TYPES: set[InformationType] = {
    InformationType.IDENTITY,
    InformationType.EMPLOYMENT,
    InformationType.EDUCATION,
}


class DecisionType(str, Enum):
    """Types of iteration decisions."""

    CONTINUE = "continue"
    THRESHOLD = "threshold"
    CAPPED = "capped"
    DIMINISHED = "diminished"


@dataclass
class IterationDecision:
    """Decision about continuing a SAR iteration.

    Contains the decision, reasoning, and context for the next phase.

    Attributes:
        decision_id: Unique identifier for this decision.
        should_continue: Whether iteration should continue.
        decision_type: Type of decision made.
        reason: Human-readable reason for the decision.
        next_phase: The next SAR phase to transition to.
        confidence_score: Current confidence score.
        confidence_threshold: Threshold that was evaluated.
        iteration_number: Current iteration number.
        info_gain_rate: Information gain rate for this iteration.
        factors: Additional decision factors for debugging.
        decided_at: When the decision was made.
    """

    decision_id: UUID = field(default_factory=uuid7)
    should_continue: bool = True
    decision_type: DecisionType = DecisionType.CONTINUE
    reason: str = "criteria_not_met"
    next_phase: SARPhase = SARPhase.REFINE

    # Context
    confidence_score: float = 0.0
    confidence_threshold: float = 0.85
    iteration_number: int = 1
    info_gain_rate: float = 0.0

    # Additional factors
    factors: dict[str, Any] = field(default_factory=dict)

    # Timing
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def completion_type(self) -> str | None:
        """Get completion type if not continuing."""
        if self.should_continue:
            return None
        return self.decision_type.value

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision_id": str(self.decision_id),
            "should_continue": self.should_continue,
            "decision_type": self.decision_type.value,
            "reason": self.reason,
            "next_phase": self.next_phase.value,
            "confidence_score": self.confidence_score,
            "confidence_threshold": self.confidence_threshold,
            "iteration_number": self.iteration_number,
            "info_gain_rate": self.info_gain_rate,
            "completion_type": self.completion_type,
            "factors": self.factors,
            "decided_at": self.decided_at.isoformat(),
        }


class ControllerConfig(BaseModel):
    """Configuration for IterationController."""

    # Confidence thresholds
    confidence_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Target confidence for standard types"
    )
    foundation_confidence_threshold: float = Field(
        default=0.90, ge=0.0, le=1.0, description="Target confidence for foundation types"
    )

    # Iteration limits
    max_iterations_per_type: int = Field(
        default=3, ge=1, le=10, description="Max iterations for standard types"
    )
    foundation_max_iterations: int = Field(
        default=4, ge=1, le=10, description="Max iterations for foundation types"
    )

    # Diminishing returns detection
    min_gain_threshold: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Minimum info gain to continue"
    )
    min_confidence_improvement: float = Field(
        default=0.05, ge=0.0, le=0.5, description="Minimum confidence improvement to continue"
    )
    diminishing_returns_window: int = Field(
        default=2, ge=1, le=5, description="Iterations to look back for diminishing returns"
    )

    # Advanced settings
    enable_early_stop: bool = Field(
        default=True, description="Enable early stopping on diminishing returns"
    )
    strict_foundation: bool = Field(
        default=True, description="Apply stricter thresholds to foundation types"
    )

    @classmethod
    def from_sar_config(cls, sar_config: SARConfig) -> "ControllerConfig":
        """Create from SARConfig for compatibility."""
        return cls(
            confidence_threshold=sar_config.confidence_threshold,
            foundation_confidence_threshold=sar_config.foundation_confidence_threshold,
            max_iterations_per_type=sar_config.max_iterations_per_type,
            foundation_max_iterations=sar_config.foundation_max_iterations,
            min_gain_threshold=sar_config.min_gain_threshold,
        )


class IterationController:
    """Controls SAR loop iteration flow.

    The IterationController makes decisions about whether to continue
    iterating on an information type based on:
    1. Confidence threshold - has sufficient confidence been reached?
    2. Max iterations - have we hit the iteration limit?
    3. Diminishing returns - is additional iteration yielding value?

    Foundation types (identity, employment, education) receive higher
    thresholds and more iteration attempts because their accuracy is
    critical for downstream investigation.

    Example:
        ```python
        controller = IterationController()

        # After completing an iteration
        decision = controller.should_continue_iteration(
            info_type=InformationType.IDENTITY,
            current_iteration=iteration_state,
            type_state=sar_type_state,
        )

        if decision.should_continue:
            # Start next iteration
            next_iteration = type_state.start_iteration()
        else:
            # Complete the type
            print(f"Completed: {decision.decision_type}")
        ```
    """

    def __init__(
        self,
        config: ControllerConfig | SARConfig | None = None,
        confidence_scorer: "ConfidenceScorer | None" = None,
        audit_logger: "AuditLogger | None" = None,
    ):
        """Initialize the iteration controller.

        Args:
            config: Controller configuration. Uses defaults if None.
            confidence_scorer: Optional confidence scorer for advanced scoring.
            audit_logger: Optional audit logger for tracking decisions.
        """
        if isinstance(config, SARConfig):
            self.config = ControllerConfig.from_sar_config(config)
        else:
            self.config = config or ControllerConfig()

        self.scorer = confidence_scorer
        self.audit = audit_logger
        self._decisions: list[IterationDecision] = []

    def is_foundation_type(self, info_type: InformationType) -> bool:
        """Check if the information type is a foundation type."""
        return info_type in FOUNDATION_TYPES

    def get_confidence_threshold(self, info_type: InformationType) -> float:
        """Get the confidence threshold for an information type."""
        if self.is_foundation_type(info_type) and self.config.strict_foundation:
            return self.config.foundation_confidence_threshold
        return self.config.confidence_threshold

    def get_max_iterations(self, info_type: InformationType) -> int:
        """Get the maximum iterations allowed for an information type."""
        if self.is_foundation_type(info_type):
            return self.config.foundation_max_iterations
        return self.config.max_iterations_per_type

    def should_continue_iteration(
        self,
        info_type: InformationType,
        current_iteration: SARIterationState,
        state: SARTypeState,
    ) -> IterationDecision:
        """Determine if iteration should continue.

        Evaluates three criteria in order:
        1. Confidence threshold met -> THRESHOLD (stop)
        2. Max iterations reached -> CAPPED (stop)
        3. Diminishing returns detected -> DIMINISHED (stop)

        Args:
            info_type: Information type being processed.
            current_iteration: Current iteration state with metrics.
            state: Overall type state with iteration history.

        Returns:
            IterationDecision with continue/stop decision and context.
        """
        threshold = self.get_confidence_threshold(info_type)
        max_iterations = self.get_max_iterations(info_type)

        # Build factors for debugging
        factors = {
            "is_foundation": self.is_foundation_type(info_type),
            "max_iterations": max_iterations,
            "total_iterations_completed": len(state.iterations),
            "total_facts_extracted": state.total_facts_extracted,
        }

        # Check 1: Confidence threshold met
        if current_iteration.confidence_score >= threshold:
            decision = IterationDecision(
                should_continue=False,
                decision_type=DecisionType.THRESHOLD,
                reason="confidence_threshold_met",
                next_phase=SARPhase.COMPLETE,
                confidence_score=current_iteration.confidence_score,
                confidence_threshold=threshold,
                iteration_number=current_iteration.iteration_number,
                info_gain_rate=current_iteration.info_gain_rate,
                factors=factors,
            )
            self._record_decision(decision, info_type)
            return decision

        # Check 2: Max iterations reached
        if current_iteration.iteration_number >= max_iterations:
            decision = IterationDecision(
                should_continue=False,
                decision_type=DecisionType.CAPPED,
                reason="max_iterations_reached",
                next_phase=SARPhase.CAPPED,
                confidence_score=current_iteration.confidence_score,
                confidence_threshold=threshold,
                iteration_number=current_iteration.iteration_number,
                info_gain_rate=current_iteration.info_gain_rate,
                factors=factors,
            )
            self._record_decision(decision, info_type)
            return decision

        # Check 3: Diminishing returns (not on first iteration)
        if self.config.enable_early_stop and current_iteration.iteration_number > 1:
            if self._is_diminishing_returns(current_iteration, state):
                decision = IterationDecision(
                    should_continue=False,
                    decision_type=DecisionType.DIMINISHED,
                    reason="diminishing_returns_detected",
                    next_phase=SARPhase.DIMINISHED,
                    confidence_score=current_iteration.confidence_score,
                    confidence_threshold=threshold,
                    iteration_number=current_iteration.iteration_number,
                    info_gain_rate=current_iteration.info_gain_rate,
                    factors=factors,
                )
                self._record_decision(decision, info_type)
                return decision

        # Continue iterating
        decision = IterationDecision(
            should_continue=True,
            decision_type=DecisionType.CONTINUE,
            reason="criteria_not_met",
            next_phase=SARPhase.REFINE,
            confidence_score=current_iteration.confidence_score,
            confidence_threshold=threshold,
            iteration_number=current_iteration.iteration_number,
            info_gain_rate=current_iteration.info_gain_rate,
            factors=factors,
        )
        self._record_decision(decision, info_type)
        return decision

    def _is_diminishing_returns(
        self,
        current: SARIterationState,
        state: SARTypeState,
    ) -> bool:
        """Detect diminishing returns from iteration.

        Checks both information gain rate and confidence improvement
        to determine if additional iterations are likely to be valuable.

        Args:
            current: Current iteration state.
            state: Type state with iteration history.

        Returns:
            True if diminishing returns detected.
        """
        # Check info gain rate
        if current.info_gain_rate < self.config.min_gain_threshold:
            logger.debug(
                "Low info gain rate detected",
                info_gain_rate=current.info_gain_rate,
                threshold=self.config.min_gain_threshold,
            )
            return True

        # Check confidence improvement over recent iterations
        window = min(self.config.diminishing_returns_window, len(state.iterations))
        if window >= 1:
            previous = state.iterations[-1]
            confidence_gain = current.confidence_score - previous.confidence_score

            if confidence_gain < self.config.min_confidence_improvement:
                logger.debug(
                    "Low confidence improvement detected",
                    confidence_gain=confidence_gain,
                    threshold=self.config.min_confidence_improvement,
                )
                return True

        return False

    def evaluate_completion(
        self,
        info_type: InformationType,
        state: SARTypeState,
    ) -> tuple[CompletionReason, float]:
        """Evaluate final completion status for a type.

        Called when an iteration decision says to stop.
        Determines the appropriate completion reason.

        Args:
            info_type: Information type.
            state: Type state with all iterations.

        Returns:
            Tuple of (CompletionReason, final_confidence).
        """
        if not state.iterations:
            return CompletionReason.ERROR, 0.0

        latest = state.iterations[-1]
        threshold = self.get_confidence_threshold(info_type)
        max_iter = self.get_max_iterations(info_type)

        # Determine reason
        if latest.confidence_score >= threshold:
            return CompletionReason.CONFIDENCE_MET, latest.confidence_score
        elif latest.iteration_number >= max_iter:
            return CompletionReason.MAX_ITERATIONS, latest.confidence_score
        elif latest.info_gain_rate < self.config.min_gain_threshold:
            return CompletionReason.DIMINISHING_RETURNS, latest.confidence_score
        else:
            return CompletionReason.NO_NEW_INFORMATION, latest.confidence_score

    def get_decision_history(self) -> list[IterationDecision]:
        """Get all decisions made by this controller."""
        return self._decisions.copy()

    def get_decisions_for_type(self, info_type: InformationType) -> list[IterationDecision]:
        """Get decisions for a specific information type."""
        return [d for d in self._decisions if d.factors.get("info_type") == info_type.value]

    def reset(self) -> None:
        """Reset decision history."""
        self._decisions.clear()

    def _record_decision(self, decision: IterationDecision, info_type: InformationType) -> None:
        """Record a decision for tracking.

        Args:
            decision: The decision made.
            info_type: Information type the decision was for.
        """
        decision.factors["info_type"] = info_type.value
        self._decisions.append(decision)

        logger.info(
            "Iteration decision",
            info_type=info_type.value,
            should_continue=decision.should_continue,
            decision_type=decision.decision_type.value,
            confidence=decision.confidence_score,
            threshold=decision.confidence_threshold,
            iteration=decision.iteration_number,
        )

        # Audit logging if available
        if self.audit:
            # Note: Audit logging is async, would need async wrapper
            pass


def create_iteration_controller(
    config: ControllerConfig | SARConfig | None = None,
    confidence_scorer: "ConfidenceScorer | None" = None,
    audit_logger: "AuditLogger | None" = None,
) -> IterationController:
    """Factory function to create an IterationController.

    Args:
        config: Optional controller configuration.
        confidence_scorer: Optional confidence scorer.
        audit_logger: Optional audit logger.

    Returns:
        Configured IterationController instance.
    """
    return IterationController(
        config=config,
        confidence_scorer=confidence_scorer,
        audit_logger=audit_logger,
    )
