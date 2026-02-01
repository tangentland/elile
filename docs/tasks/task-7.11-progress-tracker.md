# Task 7.11: Screening Progress Tracker

**Priority**: P1
**Phase**: 7 - Screening Workflows
**Estimated Effort**: 2 days
**Dependencies**: Task 7.1 (Screening Orchestration)

## Context

Implement real-time progress tracking for screenings with granular phase/step visibility and estimated completion times.

## Objectives

1. Track screening progress in real-time
2. Estimate time to completion
3. Report phase/step status
4. Support progress notifications
5. Handle stalled screening detection

## Technical Approach

```python
# src/elile/screening/progress.py
class ProgressTracker:
    def update_progress(
        self,
        screening_id: str,
        phase: str,
        step: str,
        progress_pct: float
    ) -> None:
        progress = ScreeningProgress(
            screening_id=screening_id,
            current_phase=phase,
            current_step=step,
            progress_percentage=progress_pct,
            eta=self._calculate_eta(screening_id)
        )
        # Update cache and notify subscribers
```

## Implementation Checklist

- [ ] Implement progress tracking
- [ ] Add ETA calculation
- [ ] Create notification system

## Success Criteria

- [ ] Real-time updates <1s latency
- [ ] ETA accuracy >80%
