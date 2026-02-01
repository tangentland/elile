# Task 5.8: Iteration Controller

## Overview

Implement iteration controller that manages SAR loop iterations, enforces max limits, detects diminishing returns, and controls iteration flow with proper state transitions.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 5.1: SAR State Machine (state management)
- Task 5.7: Confidence Scorer (confidence evaluation)
- Task 5.4: Result Assessor (info gain)

## Implementation Checklist

- [ ] Create IterationController with flow control
- [ ] Implement max iteration enforcement
- [ ] Build diminishing returns detection
- [ ] Add iteration state persistence
- [ ] Create iteration decision logic
- [ ] Write comprehensive controller tests

## Key Implementation

```python
# src/elile/investigation/iteration_controller.py
@dataclass
class IterationDecision:
    """Decision about continuing iteration."""
    should_continue: bool
    reason: str
    next_phase: SARPhase
    completion_type: Literal["threshold", "capped", "diminished", "continue"] | None

class IterationController:
    """Controls SAR loop iteration flow."""

    def __init__(
        self,
        config: SARConfig,
        confidence_scorer: ConfidenceScorer,
        audit_logger: AuditLogger
    ):
        self.config = config
        self.scorer = confidence_scorer
        self.audit = audit_logger

    def should_continue_iteration(
        self,
        info_type: InformationType,
        current_iteration: SARIterationState,
        state: SARTypeState
    ) -> IterationDecision:
        """
        Determine if iteration should continue.

        Args:
            info_type: Information type being processed
            current_iteration: Current iteration state
            state: Overall type state

        Returns:
            Decision about continuing
        """
        # Get thresholds
        confidence_threshold = self._get_confidence_threshold(info_type)
        max_iterations = self._get_max_iterations(info_type)

        # Check 1: Confidence threshold met
        if current_iteration.confidence_score >= confidence_threshold:
            return IterationDecision(
                should_continue=False,
                reason="confidence_threshold_met",
                next_phase=SARPhase.COMPLETE,
                completion_type="threshold"
            )

        # Check 2: Max iterations reached
        if current_iteration.iteration_number >= max_iterations:
            return IterationDecision(
                should_continue=False,
                reason="max_iterations_reached",
                next_phase=SARPhase.CAPPED,
                completion_type="capped"
            )

        # Check 3: Diminishing returns (not on first iteration)
        if current_iteration.iteration_number > 1:
            if self._is_diminishing_returns(current_iteration, state):
                return IterationDecision(
                    should_continue=False,
                    reason="diminishing_returns",
                    next_phase=SARPhase.DIMINISHED,
                    completion_type="diminished"
                )

        # Continue iterating
        return IterationDecision(
            should_continue=True,
            reason="criteria_not_met",
            next_phase=SARPhase.REFINE,
            completion_type="continue"
        )

    def _is_diminishing_returns(
        self,
        current: SARIterationState,
        state: SARTypeState
    ) -> bool:
        """Detect diminishing returns."""
        # Check info gain rate
        if current.info_gain_rate < self.config.min_gain_threshold:
            return True

        # Check if confidence improvement is minimal
        if len(state.iterations) >= 2:
            previous = state.iterations[-1]
            confidence_gain = current.confidence_score - previous.confidence_score
            if confidence_gain < 0.05:  # Less than 5% improvement
                return True

        return False

    def _get_confidence_threshold(self, info_type: InformationType) -> float:
        """Get confidence threshold for type."""
        if info_type in {
            InformationType.IDENTITY,
            InformationType.EMPLOYMENT,
            InformationType.EDUCATION
        }:
            return self.config.foundation_confidence_threshold
        return self.config.confidence_threshold

    def _get_max_iterations(self, info_type: InformationType) -> int:
        """Get max iterations for type."""
        if info_type in {
            InformationType.IDENTITY,
            InformationType.EMPLOYMENT,
            InformationType.EDUCATION
        }:
            return self.config.foundation_max_iterations
        return self.config.max_iterations_per_type
```

## Testing Requirements

### Unit Tests
- Confidence threshold detection
- Max iteration enforcement
- Diminishing returns detection
- Foundation vs. standard thresholds
- Iteration decision logic

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] IterationController enforces max iterations
- [ ] Diminishing returns detected (low gain + low improvement)
- [ ] Foundation types get higher limits
- [ ] Iteration decisions fully reasoned
- [ ] State transitions triggered correctly

## Deliverables

- `src/elile/investigation/iteration_controller.py`
- `tests/unit/test_iteration_controller.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - SAR Loop

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
