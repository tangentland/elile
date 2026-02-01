# Task 7.5: Screening State Manager

## Overview

Implement screening state manager that persists screening state, tracks progress, handles resumption after failures, and provides status updates.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 7.1: Screening Orchestrator
- Task 1.1: Database Schema

## Implementation

```python
# src/elile/screening/state_manager.py
class ScreeningStateManager:
    """Manages screening state persistence."""

    async def save_state(
        self,
        screening_id: UUID,
        state: ScreeningState
    ) -> None:
        """Persist screening state."""
        await self.db.execute(
            update(Screening)
            .where(Screening.screening_id == screening_id)
            .values(
                status=state.status,
                current_phase=state.current_phase,
                progress_percent=state.progress_percent,
                state_data=state.to_dict()
            )
        )

    async def load_state(
        self,
        screening_id: UUID
    ) -> ScreeningState:
        """Load screening state."""
        result = await self.db.execute(
            select(Screening).where(Screening.screening_id == screening_id)
        )
        screening = result.scalar_one()
        return ScreeningState.from_dict(screening.state_data)

    async def resume_screening(
        self,
        screening_id: UUID
    ) -> ScreeningResult:
        """Resume failed screening."""
        state = await self.load_state(screening_id)
        # Resume from last checkpoint
        pass
```

## Acceptance Criteria

- [ ] Persists screening state to DB
- [ ] Loads state for resumption
- [ ] Tracks progress percentage
- [ ] Enables failure recovery

## Deliverables

- `src/elile/screening/state_manager.py`
- `tests/unit/test_state_manager.py`

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
