"""SAR loop models for state tracking and configuration.

This module provides the core models for the Search-Assess-Refine
(SAR) loop state machine:
- SARPhase: Phases in the SAR loop
- CompletionReason: Reasons for completing an iteration
- SARConfig: Configuration for SAR loop behavior
- SARIterationState: State for a single SAR iteration
- SARTypeState: State for an information type's SAR loop
- SARSummary: Summary of SAR loop execution
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import InformationType


class SARPhase(str, Enum):
    """Phases in the SAR (Search-Assess-Refine) loop."""

    SEARCH = "search"
    ASSESS = "assess"
    REFINE = "refine"
    COMPLETE = "complete"  # Confidence threshold met
    CAPPED = "capped"  # Max iterations reached
    DIMINISHED = "diminished"  # Diminishing returns detected


class CompletionReason(str, Enum):
    """Reasons for completing a SAR loop."""

    CONFIDENCE_MET = "confidence_met"
    CONFIDENCE_THRESHOLD_MET = "confidence_threshold_met"  # Alias
    MAX_ITERATIONS = "max_iterations"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"  # Alias
    DIMINISHING_RETURNS = "diminishing_returns"
    NO_NEW_INFORMATION = "no_new_information"
    USER_STOPPED = "user_stopped"
    SKIPPED = "skipped"
    ERROR = "error"


class SARConfig(BaseModel):
    """Configuration for SAR loop behavior.

    Attributes:
        confidence_threshold: Target confidence for standard types (0.85).
        foundation_confidence_threshold: Target for foundation types (0.90).
        max_iterations_per_type: Max iterations for standard types (3).
        foundation_max_iterations: Max iterations for foundation types (4).
        min_gain_threshold: Minimum info gain to continue (0.1).
        network_max_entities_per_degree: Max entities per degree level (20).
    """

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

    # Diminishing returns
    min_gain_threshold: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Minimum info gain to continue"
    )

    # Network phase limits
    network_max_entities_per_degree: int = Field(
        default=20, ge=1, le=100, description="Max entities per degree level"
    )


@dataclass
class SARIterationState:
    """State for a single SAR iteration.

    Tracks metrics for one iteration of the SAR loop, including
    queries executed, facts extracted, and confidence score.
    """

    iteration_id: UUID = field(default_factory=uuid7)
    iteration_number: int = 1
    phase: SARPhase = SARPhase.SEARCH

    # Query metrics
    queries_generated: int = 0
    queries_executed: int = 0
    queries_successful: int = 0

    # Result metrics
    results_found: int = 0
    facts_extracted: int = 0
    new_facts_this_iteration: int = 0

    # Assessment metrics
    confidence_score: float = 0.0
    confidence_delta: float = 0.0  # Change from previous iteration
    info_gain_rate: float = 0.0

    # Gap tracking
    gaps_identified: list[str] = field(default_factory=list)
    gaps_addressed: int = 0

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_seconds: float = 0.0

    def calculate_info_gain_rate(self) -> float:
        """Calculate the information gain rate for this iteration.

        Info gain rate = new facts / total queries executed.
        This metric helps detect diminishing returns.

        Returns:
            Information gain rate (0.0 if no queries executed).
        """
        if self.queries_executed == 0:
            self.info_gain_rate = 0.0
        else:
            self.info_gain_rate = self.new_facts_this_iteration / self.queries_executed
        return self.info_gain_rate

    def complete(self) -> None:
        """Mark this iteration as complete."""
        self.completed_at = datetime.now(UTC)
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "iteration_id": str(self.iteration_id),
            "iteration_number": self.iteration_number,
            "phase": self.phase.value,
            "queries_generated": self.queries_generated,
            "queries_executed": self.queries_executed,
            "queries_successful": self.queries_successful,
            "results_found": self.results_found,
            "facts_extracted": self.facts_extracted,
            "new_facts_this_iteration": self.new_facts_this_iteration,
            "confidence_score": self.confidence_score,
            "confidence_delta": self.confidence_delta,
            "info_gain_rate": self.info_gain_rate,
            "gaps_identified": self.gaps_identified,
            "gaps_addressed": self.gaps_addressed,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class SARTypeState:
    """State for an information type's SAR loop.

    Tracks the complete state of a SAR loop for a single information
    type, including all iterations and completion status.
    """

    type_id: UUID = field(default_factory=uuid7)
    info_type: InformationType = InformationType.IDENTITY
    phase: SARPhase = SARPhase.SEARCH
    iterations: list[SARIterationState] = field(default_factory=list)

    # Current iteration tracking
    current_iteration_number: int = 0

    # Completion tracking
    is_complete: bool = False
    completion_reason: CompletionReason | None = None
    final_confidence: float = 0.0

    # Knowledge accumulated
    total_facts_extracted: int = 0
    total_queries_executed: int = 0

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def start_iteration(self) -> SARIterationState:
        """Start a new iteration for this type.

        Returns:
            The new SARIterationState.
        """
        self.current_iteration_number += 1
        iteration = SARIterationState(
            iteration_number=self.current_iteration_number,
            phase=SARPhase.SEARCH,
        )
        return iteration

    def complete_iteration(self, iteration: SARIterationState) -> None:
        """Record a completed iteration.

        Updates accumulated metrics and stores the iteration.

        Args:
            iteration: The completed iteration state.
        """
        iteration.complete()
        self.iterations.append(iteration)
        self.total_facts_extracted += iteration.new_facts_this_iteration
        self.total_queries_executed += iteration.queries_executed

        # Update confidence delta if we have previous iterations
        if len(self.iterations) >= 2:
            previous = self.iterations[-2]
            iteration.confidence_delta = iteration.confidence_score - previous.confidence_score

    def mark_complete(self, reason: CompletionReason, confidence: float) -> None:
        """Mark this type as complete.

        Args:
            reason: Why the type completed.
            confidence: Final confidence score.
        """
        self.is_complete = True
        self.completion_reason = reason
        self.final_confidence = confidence
        self.completed_at = datetime.now(UTC)

    def get_latest_iteration(self) -> SARIterationState | None:
        """Get the most recent iteration, if any."""
        return self.iterations[-1] if self.iterations else None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type_id": str(self.type_id),
            "info_type": self.info_type.value,
            "phase": self.phase.value,
            "iterations": [i.to_dict() for i in self.iterations],
            "current_iteration_number": self.current_iteration_number,
            "is_complete": self.is_complete,
            "completion_reason": self.completion_reason.value if self.completion_reason else None,
            "final_confidence": self.final_confidence,
            "total_facts_extracted": self.total_facts_extracted,
            "total_queries_executed": self.total_queries_executed,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class SARSummary:
    """Summary of SAR loop execution across all types.

    Provides an overview of the complete SAR investigation including
    all information types processed and their results.
    """

    summary_id: UUID = field(default_factory=uuid7)
    investigation_id: UUID | None = None

    # Type counts
    types_initialized: int = 0
    types_complete: int = 0
    types_in_progress: int = 0

    # Aggregate metrics
    total_iterations: int = 0
    total_queries: int = 0
    total_facts: int = 0

    # Type details
    type_states: dict[InformationType, SARTypeState] = field(default_factory=dict)

    # Completion info
    completion_reasons: dict[CompletionReason, int] = field(default_factory=dict)
    average_confidence: float = 0.0
    lowest_confidence: float = 0.0
    lowest_confidence_type: InformationType | None = None

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_duration_seconds: float = 0.0

    @classmethod
    def from_type_states(
        cls,
        type_states: dict[InformationType, "SARTypeState"],
    ) -> "SARSummary":
        """Create a summary from type states.

        Args:
            type_states: Dictionary of type states.

        Returns:
            SARSummary with computed aggregate metrics.
        """
        summary = cls(type_states=type_states)

        # Count types
        summary.types_initialized = len(type_states)
        summary.types_complete = sum(1 for s in type_states.values() if s.is_complete)
        summary.types_in_progress = summary.types_initialized - summary.types_complete

        # Aggregate metrics
        for state in type_states.values():
            summary.total_iterations += len(state.iterations)
            summary.total_queries += state.total_queries_executed
            summary.total_facts += state.total_facts_extracted

            # Track completion reasons
            if state.completion_reason:
                if state.completion_reason not in summary.completion_reasons:
                    summary.completion_reasons[state.completion_reason] = 0
                summary.completion_reasons[state.completion_reason] += 1

        # Calculate confidence metrics
        complete_states = [
            s for s in type_states.values() if s.is_complete and s.final_confidence > 0
        ]
        if complete_states:
            confidences = [s.final_confidence for s in complete_states]
            summary.average_confidence = sum(confidences) / len(confidences)
            summary.lowest_confidence = min(confidences)

            # Find lowest confidence type
            for state in complete_states:
                if state.final_confidence == summary.lowest_confidence:
                    summary.lowest_confidence_type = state.info_type
                    break

        return summary

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary_id": str(self.summary_id),
            "investigation_id": str(self.investigation_id) if self.investigation_id else None,
            "types_initialized": self.types_initialized,
            "types_complete": self.types_complete,
            "types_in_progress": self.types_in_progress,
            "total_iterations": self.total_iterations,
            "total_queries": self.total_queries,
            "total_facts": self.total_facts,
            "type_states": {k.value: v.to_dict() for k, v in self.type_states.items()},
            "completion_reasons": {k.value: v for k, v in self.completion_reasons.items()},
            "average_confidence": self.average_confidence,
            "lowest_confidence": self.lowest_confidence,
            "lowest_confidence_type": (
                self.lowest_confidence_type.value if self.lowest_confidence_type else None
            ),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration_seconds": self.total_duration_seconds,
        }
