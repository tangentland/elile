# Task 5.1: SAR State Machine

## Overview

Implement the Search-Assess-Refine (SAR) loop state machine that orchestrates iterative information gathering for each information type. Manages iteration cycles, confidence thresholds, and completion criteria.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 2.1: Service Tiers (tier configuration)
- Task 2.2: Investigation Degrees (degree logic)
- Task 1.2: Audit Logging (audit trail)

## Implementation Checklist

- [ ] Create SARStateMachine with phase tracking
- [ ] Implement iteration controller with max limits
- [ ] Build confidence threshold evaluator
- [ ] Add diminishing returns detector
- [ ] Create information gain calculator
- [ ] Implement phase transition logic
- [ ] Write SAR state persistence
- [ ] Add comprehensive state machine tests

## Key Implementation

```python
# src/elile/investigation/sar_state_machine.py
from enum import Enum
from dataclasses import dataclass
from typing import Literal

class SARPhase(str, Enum):
    """SAR loop phases."""
    SEARCH = "search"
    ASSESS = "assess"
    REFINE = "refine"
    COMPLETE = "complete"
    CAPPED = "capped"  # Max iterations reached
    DIMINISHED = "diminished"  # Diminishing returns

class InformationType(str, Enum):
    """Information types in dependency order."""
    # Phase 1: Foundation
    IDENTITY = "identity"
    EMPLOYMENT = "employment"
    EDUCATION = "education"

    # Phase 2: Records
    CRIMINAL = "criminal"
    CIVIL = "civil"
    FINANCIAL = "financial"
    LICENSES = "licenses"
    REGULATORY = "regulatory"
    SANCTIONS = "sanctions"

    # Phase 3: Intelligence
    ADVERSE_MEDIA = "adverse_media"
    DIGITAL_FOOTPRINT = "digital_footprint"

@dataclass
class SARIterationState:
    """State for a single SAR iteration."""
    iteration_number: int
    queries_generated: int
    results_found: int
    facts_extracted: int
    new_facts_this_iteration: int
    confidence_score: float
    gaps_identified: list[str]
    info_gain_rate: float

@dataclass
class SARTypeState:
    """State for an information type's SAR loop."""
    info_type: InformationType
    phase: SARPhase
    iterations: list[SARIterationState]

    # Completion tracking
    is_complete: bool = False
    completion_reason: str | None = None
    final_confidence: float = 0.0

    # Knowledge accumulated
    total_facts_extracted: int = 0
    total_queries_executed: int = 0

class SARConfig(BaseModel):
    """Configuration for SAR loop."""
    # Confidence thresholds
    confidence_threshold: float = 0.85
    foundation_confidence_threshold: float = 0.90

    # Iteration limits
    max_iterations_per_type: int = 3
    foundation_max_iterations: int = 4

    # Diminishing returns
    min_gain_threshold: float = 0.1

    # Network phase
    network_max_entities_per_degree: int = 20

class SARStateMachine:
    """Orchestrates Search-Assess-Refine loop."""

    def __init__(
        self,
        config: SARConfig,
        audit_logger: AuditLogger
    ):
        self.config = config
        self.audit = audit_logger
        self.type_states: dict[InformationType, SARTypeState] = {}

    def is_foundation_type(self, info_type: InformationType) -> bool:
        """Check if type is in foundation phase."""
        return info_type in {
            InformationType.IDENTITY,
            InformationType.EMPLOYMENT,
            InformationType.EDUCATION
        }

    def get_confidence_threshold(self, info_type: InformationType) -> float:
        """Get confidence threshold for type."""
        if self.is_foundation_type(info_type):
            return self.config.foundation_confidence_threshold
        return self.config.confidence_threshold

    def get_max_iterations(self, info_type: InformationType) -> int:
        """Get max iterations for type."""
        if self.is_foundation_type(info_type):
            return self.config.foundation_max_iterations
        return self.config.max_iterations_per_type

    def initialize_type(self, info_type: InformationType) -> SARTypeState:
        """Initialize SAR state for information type."""
        state = SARTypeState(
            info_type=info_type,
            phase=SARPhase.SEARCH,
            iterations=[]
        )
        self.type_states[info_type] = state
        return state

    def calculate_info_gain_rate(
        self,
        new_facts: int,
        queries_executed: int
    ) -> float:
        """Calculate information gain rate for iteration."""
        if queries_executed == 0:
            return 0.0
        return new_facts / queries_executed

    def should_continue_iteration(
        self,
        state: SARTypeState,
        current_iteration: SARIterationState
    ) -> tuple[bool, str | None]:
        """
        Determine if iteration should continue.

        Returns:
            (should_continue, completion_reason)
        """
        confidence_threshold = self.get_confidence_threshold(state.info_type)
        max_iterations = self.get_max_iterations(state.info_type)

        # Check confidence threshold
        if current_iteration.confidence_score >= confidence_threshold:
            return False, "confidence_threshold_met"

        # Check iteration limit
        if current_iteration.iteration_number >= max_iterations:
            return False, "max_iterations_reached"

        # Check diminishing returns (not on first iteration)
        if current_iteration.iteration_number > 1:
            if current_iteration.info_gain_rate < self.config.min_gain_threshold:
                return False, "diminishing_returns"

        return True, None

    def transition_phase(
        self,
        state: SARTypeState,
        new_phase: SARPhase,
        reason: str | None = None
    ) -> None:
        """Transition SAR state to new phase."""
        old_phase = state.phase
        state.phase = new_phase

        if new_phase in {SARPhase.COMPLETE, SARPhase.CAPPED, SARPhase.DIMINISHED}:
            state.is_complete = True
            state.completion_reason = reason
            if state.iterations:
                state.final_confidence = state.iterations[-1].confidence_score

        # Audit log
        self.audit.log_event(
            AuditEventType.SAR_PHASE_TRANSITION,
            {
                "info_type": state.info_type,
                "old_phase": old_phase,
                "new_phase": new_phase,
                "reason": reason,
                "iterations_completed": len(state.iterations)
            }
        )

    def complete_iteration(
        self,
        state: SARTypeState,
        iteration_data: SARIterationState
    ) -> None:
        """Complete current iteration and determine next action."""
        state.iterations.append(iteration_data)
        state.total_facts_extracted += iteration_data.new_facts_this_iteration
        state.total_queries_executed += iteration_data.queries_generated

        # Decide if we should continue
        should_continue, reason = self.should_continue_iteration(state, iteration_data)

        if not should_continue:
            # Determine completion phase
            if reason == "confidence_threshold_met":
                self.transition_phase(state, SARPhase.COMPLETE, reason)
            elif reason == "max_iterations_reached":
                self.transition_phase(state, SARPhase.CAPPED, reason)
            elif reason == "diminishing_returns":
                self.transition_phase(state, SARPhase.DIMINISHED, reason)
        else:
            # Continue to next iteration - transition to REFINE
            self.transition_phase(state, SARPhase.REFINE)

    def get_type_state(self, info_type: InformationType) -> SARTypeState | None:
        """Get state for information type."""
        return self.type_states.get(info_type)

    def get_summary(self) -> dict:
        """Get summary of all type states."""
        return {
            "types_processed": len(self.type_states),
            "types_complete": sum(1 for s in self.type_states.values() if s.is_complete),
            "total_iterations": sum(len(s.iterations) for s in self.type_states.values()),
            "total_facts": sum(s.total_facts_extracted for s in self.type_states.values()),
            "type_details": {
                info_type: {
                    "phase": state.phase,
                    "iterations": len(state.iterations),
                    "confidence": state.final_confidence if state.is_complete else None,
                    "completion_reason": state.completion_reason
                }
                for info_type, state in self.type_states.items()
            }
        }
```

## Testing Requirements

### Unit Tests
- State initialization for each information type
- Confidence threshold evaluation (foundation vs. standard)
- Max iteration limits (foundation vs. standard)
- Diminishing returns detection
- Info gain rate calculation
- Phase transition logic
- Completion reason determination

### Integration Tests
- Complete SAR cycle for single type
- Multiple information types in sequence
- Early completion (threshold met)
- Capped completion (max iterations)
- Diminished completion (low gain)

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] SARStateMachine tracks state for each information type
- [ ] Foundation types use higher confidence threshold (0.90)
- [ ] Foundation types get more iterations (4 vs. 3)
- [ ] Diminishing returns detection stops iteration
- [ ] Phase transitions logged to audit trail
- [ ] State summary provides complete overview
- [ ] Iteration state persists across phase transitions

## Deliverables

- `src/elile/investigation/sar_state_machine.py`
- `src/elile/investigation/models.py` (SAR models)
- `tests/unit/test_sar_state_machine.py`
- `tests/integration/test_sar_cycle.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - SAR Loop
- Dependencies: Task 2.1 (tiers), Task 2.2 (degrees), Task 1.2 (audit)

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
