"""SAR (Search-Assess-Refine) State Machine.

This module implements the state machine that orchestrates the iterative
Search-Assess-Refine loop for each information type during an investigation.

The SAR loop is the core investigation algorithm:
1. SEARCH: Generate and execute queries based on accumulated knowledge
2. ASSESS: Analyze results, extract findings, calculate confidence
3. REFINE: Decide whether to continue (more iterations) or complete

Each information type runs through this loop independently, with the
state machine managing iteration limits, confidence thresholds, and
diminishing returns detection.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid7

from elile.agent.state import PHASE_TYPES, InformationType, SearchPhase
from elile.investigation.models import (
    CompletionReason,
    SARConfig,
    SARIterationState,
    SARPhase,
    SARSummary,
    SARTypeState,
)

if TYPE_CHECKING:
    from elile.core.audit import AuditLogger


# Foundation types that require higher confidence and more iterations
FOUNDATION_TYPES: set[InformationType] = {
    InformationType.IDENTITY,
    InformationType.EMPLOYMENT,
    InformationType.EDUCATION,
}


class SARStateMachine:
    """Orchestrates the Search-Assess-Refine loop for investigations.

    This state machine tracks progress through the SAR loop for each
    information type, managing:
    - Iteration lifecycle (start, complete, transition)
    - Confidence threshold evaluation
    - Max iteration limits
    - Diminishing returns detection
    - Phase transitions and completion

    Example:
        ```python
        config = SARConfig(confidence_threshold=0.85, max_iterations_per_type=3)
        machine = SARStateMachine(config, audit_logger)

        # Initialize and run SAR loop for identity verification
        state = machine.initialize_type(InformationType.IDENTITY)
        iteration = machine.start_iteration(InformationType.IDENTITY)

        # ... execute queries, collect results ...

        # Record iteration metrics
        iteration.queries_executed = 5
        iteration.facts_extracted = 12
        iteration.new_facts_this_iteration = 10
        iteration.confidence_score = 0.75

        # Complete iteration and check if we should continue
        should_continue = machine.complete_iteration(
            InformationType.IDENTITY,
            iteration
        )

        if should_continue:
            # Start next iteration
            iteration = machine.start_iteration(InformationType.IDENTITY)
        else:
            # Type is complete
            print(f"Completed: {state.completion_reason}")
        ```
    """

    def __init__(
        self,
        config: SARConfig | None = None,
        audit_logger: "AuditLogger | None" = None,
    ):
        """Initialize the SAR state machine.

        Args:
            config: Configuration for thresholds and limits. Uses defaults if None.
            audit_logger: Optional audit logger for tracking phase transitions.
        """
        self.config = config or SARConfig()
        self.audit = audit_logger
        self.type_states: dict[InformationType, SARTypeState] = {}
        self._investigation_id: UUID = uuid7()
        self._started_at: datetime = datetime.now(UTC)

    @property
    def investigation_id(self) -> UUID:
        """Get the unique identifier for this investigation."""
        return self._investigation_id

    def is_foundation_type(self, info_type: InformationType) -> bool:
        """Check if the information type is a foundation type.

        Foundation types (identity, employment, education) require higher
        confidence thresholds and get more iteration attempts.
        """
        return info_type in FOUNDATION_TYPES

    def get_confidence_threshold(self, info_type: InformationType) -> float:
        """Get the confidence threshold for an information type.

        Foundation types use a higher threshold (0.90 default) because
        they form the basis for all subsequent searches.
        """
        if self.is_foundation_type(info_type):
            return self.config.foundation_confidence_threshold
        return self.config.confidence_threshold

    def get_max_iterations(self, info_type: InformationType) -> int:
        """Get the maximum iterations allowed for an information type.

        Foundation types get more iterations (4 default) because their
        accuracy is critical for downstream types.
        """
        if self.is_foundation_type(info_type):
            return self.config.foundation_max_iterations
        return self.config.max_iterations_per_type

    def initialize_type(self, info_type: InformationType) -> SARTypeState:
        """Initialize SAR state tracking for an information type.

        Args:
            info_type: The information type to initialize.

        Returns:
            The initialized SARTypeState.

        Raises:
            ValueError: If the type is already initialized.
        """
        if info_type in self.type_states:
            raise ValueError(f"Type {info_type} is already initialized")

        state = SARTypeState(info_type=info_type)
        self.type_states[info_type] = state

        self._log_event(
            "sar_type_initialized",
            {
                "info_type": info_type.value,
                "is_foundation": self.is_foundation_type(info_type),
                "confidence_threshold": self.get_confidence_threshold(info_type),
                "max_iterations": self.get_max_iterations(info_type),
            },
        )

        return state

    def get_type_state(self, info_type: InformationType) -> SARTypeState | None:
        """Get the current state for an information type."""
        return self.type_states.get(info_type)

    def start_iteration(self, info_type: InformationType) -> SARIterationState:
        """Start a new SAR iteration for an information type.

        Args:
            info_type: The information type to iterate on.

        Returns:
            The new SARIterationState.

        Raises:
            ValueError: If the type is not initialized or already complete.
        """
        state = self.type_states.get(info_type)
        if state is None:
            raise ValueError(f"Type {info_type} not initialized")
        if state.is_complete:
            raise ValueError(f"Type {info_type} is already complete")

        # Transition to SEARCH phase
        self._transition_phase(state, SARPhase.SEARCH)

        # Create new iteration
        iteration = state.start_iteration()

        self._log_event(
            "sar_iteration_started",
            {
                "info_type": info_type.value,
                "iteration_number": iteration.iteration_number,
            },
        )

        return iteration

    def complete_iteration(
        self,
        info_type: InformationType,
        iteration: SARIterationState,
    ) -> bool:
        """Complete an iteration and determine if we should continue.

        This is called after the Search and Assess phases have collected
        metrics. It evaluates whether to continue iterating or complete
        the information type.

        Args:
            info_type: The information type being processed.
            iteration: The iteration state with metrics populated.

        Returns:
            True if another iteration should be started, False if complete.

        Raises:
            ValueError: If the type is not initialized.
        """
        state = self.type_states.get(info_type)
        if state is None:
            raise ValueError(f"Type {info_type} not initialized")

        # Calculate info gain rate
        iteration.calculate_info_gain_rate()

        # Record metrics
        state.complete_iteration(iteration)

        # Transition to ASSESS phase (we're assessing whether to continue)
        self._transition_phase(state, SARPhase.ASSESS)

        # Evaluate continuation criteria
        should_continue, reason = self._should_continue_iteration(state, iteration)

        if not should_continue:
            # Complete the type - reason is always set when should_continue is False
            assert reason is not None
            self._complete_type(state, reason, iteration.confidence_score)
            return False
        else:
            # Transition to REFINE phase (preparing for next iteration)
            self._transition_phase(state, SARPhase.REFINE)
            return True

    def _should_continue_iteration(
        self,
        state: SARTypeState,
        iteration: SARIterationState,
    ) -> tuple[bool, CompletionReason | None]:
        """Determine if iteration should continue.

        Evaluates three criteria in order:
        1. Confidence threshold met -> COMPLETE
        2. Max iterations reached -> CAPPED
        3. Diminishing returns detected -> DIMINISHED

        Args:
            state: The type state.
            iteration: The current iteration with metrics.

        Returns:
            Tuple of (should_continue, completion_reason).
            If should_continue is True, completion_reason is None.
        """
        threshold = self.get_confidence_threshold(state.info_type)
        max_iter = self.get_max_iterations(state.info_type)

        # Check confidence threshold
        if iteration.confidence_score >= threshold:
            return False, CompletionReason.CONFIDENCE_MET

        # Check iteration limit
        if iteration.iteration_number >= max_iter:
            return False, CompletionReason.MAX_ITERATIONS

        # Check diminishing returns (skip on first iteration)
        if (
            iteration.iteration_number > 1
            and iteration.info_gain_rate < self.config.min_gain_threshold
        ):
            return False, CompletionReason.DIMINISHING_RETURNS

        return True, None

    def _complete_type(
        self,
        state: SARTypeState,
        reason: CompletionReason,
        confidence: float,
    ) -> None:
        """Mark an information type as complete.

        Args:
            state: The type state to complete.
            reason: Why the type completed.
            confidence: Final confidence score.
        """
        # Determine completion phase based on reason
        if reason == CompletionReason.CONFIDENCE_MET:
            completion_phase = SARPhase.COMPLETE
        elif reason == CompletionReason.MAX_ITERATIONS:
            completion_phase = SARPhase.CAPPED
        elif reason == CompletionReason.DIMINISHING_RETURNS:
            completion_phase = SARPhase.DIMINISHED
        else:
            completion_phase = SARPhase.COMPLETE

        self._transition_phase(state, completion_phase)
        state.mark_complete(reason, confidence)

        self._log_event(
            "sar_type_completed",
            {
                "info_type": state.info_type.value,
                "completion_reason": reason.value,
                "final_confidence": confidence,
                "iterations_completed": len(state.iterations),
                "total_facts": state.total_facts_extracted,
                "total_queries": state.total_queries_executed,
            },
        )

    def skip_type(self, info_type: InformationType, reason: str = "not enabled") -> None:
        """Mark an information type as skipped.

        Use this when a type is not enabled for the service tier or
        is excluded by configuration.

        Args:
            info_type: The information type to skip.
            reason: Human-readable reason for skipping.
        """
        if info_type in self.type_states:
            state = self.type_states[info_type]
        else:
            state = SARTypeState(info_type=info_type)
            self.type_states[info_type] = state

        state.mark_complete(CompletionReason.SKIPPED, confidence=0.0)
        state.phase = SARPhase.COMPLETE

        self._log_event(
            "sar_type_skipped",
            {
                "info_type": info_type.value,
                "reason": reason,
            },
        )

    def _transition_phase(self, state: SARTypeState, new_phase: SARPhase) -> None:
        """Transition a type to a new SAR phase.

        Args:
            state: The type state to transition.
            new_phase: The new phase to enter.
        """
        old_phase = state.phase
        state.phase = new_phase

        self._log_event(
            "sar_phase_transition",
            {
                "info_type": state.info_type.value,
                "old_phase": old_phase.value,
                "new_phase": new_phase.value,
                "iteration": len(state.iterations),
            },
        )

    def get_summary(self) -> SARSummary:
        """Get a summary of the current investigation state.

        Returns:
            SARSummary with aggregate statistics.
        """
        summary = SARSummary.from_type_states(self.type_states)
        summary.investigation_id = self._investigation_id
        summary.started_at = self._started_at
        return summary

    def get_type_summary(self, info_type: InformationType) -> dict[str, object]:
        """Get a summary dict for a specific information type.

        Args:
            info_type: The information type to summarize.

        Returns:
            Dict with type state summary, or empty dict if not found.
        """
        state = self.type_states.get(info_type)
        if state is None:
            return {}

        return {
            "info_type": info_type.value,
            "phase": state.phase.value,
            "is_complete": state.is_complete,
            "completion_reason": state.completion_reason.value if state.completion_reason else None,
            "iterations": len(state.iterations),
            "final_confidence": state.final_confidence,
            "total_facts": state.total_facts_extracted,
            "total_queries": state.total_queries_executed,
        }

    def get_pending_types(self) -> list[InformationType]:
        """Get information types that haven't been processed yet.

        Returns:
            List of InformationType that are not in type_states.
        """
        all_types = set(InformationType)
        processed = set(self.type_states.keys())
        return list(all_types - processed)

    def get_incomplete_types(self) -> list[InformationType]:
        """Get information types that are started but not complete.

        Returns:
            List of InformationType that are in progress.
        """
        return [info_type for info_type, state in self.type_states.items() if not state.is_complete]

    def get_complete_types(self) -> list[InformationType]:
        """Get information types that are complete.

        Returns:
            List of completed InformationType.
        """
        return [info_type for info_type, state in self.type_states.items() if state.is_complete]

    def is_phase_complete(self, phase: SearchPhase) -> bool:
        """Check if all types in a search phase are complete.

        Args:
            phase: The SearchPhase to check.

        Returns:
            True if all types in the phase are complete.
        """
        phase_types = PHASE_TYPES.get(phase, [])
        for info_type in phase_types:
            state = self.type_states.get(info_type)
            if state is None or not state.is_complete:
                return False
        return True

    def get_next_type_for_phase(self, phase: SearchPhase) -> InformationType | None:
        """Get the next incomplete information type for a phase.

        Args:
            phase: The SearchPhase to search in.

        Returns:
            Next InformationType to process, or None if phase is complete.
        """
        phase_types = PHASE_TYPES.get(phase, [])
        for info_type in phase_types:
            state = self.type_states.get(info_type)
            if state is None:
                return info_type
            if not state.is_complete:
                return info_type
        return None

    def _log_event(self, event_type: str, data: dict[str, object]) -> None:
        """Log an audit event if audit logger is available.

        Args:
            event_type: Type of event (e.g., "sar_phase_transition").
            data: Event data to log.
        """
        if self.audit is None:
            return

        # Add investigation context
        data["investigation_id"] = str(self._investigation_id)

        # Note: AuditLogger.log_event is async. For synchronous SAR state machine,
        # we store events for later async processing or use a sync callback if available.
        # TODO: Add sync logging interface or event queue for proper audit integration
        _ = event_type, data  # Mark as intentionally unused for now


def create_sar_machine(
    config: SARConfig | None = None,
    audit_logger: "AuditLogger | None" = None,
) -> SARStateMachine:
    """Factory function to create a configured SAR state machine.

    Args:
        config: Optional configuration. Uses defaults if None.
        audit_logger: Optional audit logger for tracking.

    Returns:
        Configured SARStateMachine instance.
    """
    return SARStateMachine(config=config, audit_logger=audit_logger)
