# Task 5.16: Investigation Resume and Checkpointing

**Priority**: P1
**Phase**: 5 - Investigation Engine
**Estimated Effort**: 2 days
**Dependencies**: Task 5.1 (SAR Loop)

## Context

Implement investigation checkpointing and resume capability to handle long-running investigations, system failures, and manual intervention points.

**Architecture Reference**: [05-investigation.md](../docs/architecture/05-investigation.md) - Investigation Flow

## Objectives

1. Create investigation checkpoint storage
2. Support pause and resume operations
3. Handle investigation state recovery
4. Enable manual review points
5. Support investigation branching

## Technical Approach

```python
# src/elile/investigation/checkpoint.py
class InvestigationCheckpoint:
    """Manage investigation checkpoints."""

    def save_checkpoint(
        self,
        investigation_id: str,
        phase: str,
        state: Dict[str, any]
    ) -> None:
        """Save investigation checkpoint."""
        checkpoint = {
            "investigation_id": investigation_id,
            "phase": phase,
            "state": state,
            "timestamp": datetime.utcnow(),
            "resumable": True
        }
        # Store in database and cache
        pass

    def resume_investigation(
        self,
        investigation_id: str
    ) -> InvestigationState:
        """Resume investigation from checkpoint."""
        checkpoint = self._load_latest_checkpoint(investigation_id)
        return self._restore_state(checkpoint)
```

## Implementation Checklist

- [ ] Implement checkpoint storage
- [ ] Add resume logic
- [ ] Create state recovery
- [ ] Test failure scenarios

## Success Criteria

- [ ] Resume works after failures
- [ ] State fully recovered
- [ ] No data loss on resume
