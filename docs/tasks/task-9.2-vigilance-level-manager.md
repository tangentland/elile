# Task 9.2: Vigilance Level Manager

## Overview

Implement vigilance level manager that determines appropriate monitoring frequency based on role, updates levels on position changes, and manages escalation/de-escalation.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 2.3: Vigilance Levels
- Task 9.1: Monitoring Scheduler

## Implementation

```python
# src/elile/monitoring/vigilance_manager.py
class VigilanceManager:
    """Manages vigilance level assignments."""

    ROLE_DEFAULT_VIGILANCE = {
        RoleCategory.GOVERNMENT: VigilanceLevel.V2,
        RoleCategory.ENERGY: VigilanceLevel.V3,
        RoleCategory.FINANCE: VigilanceLevel.V2,
        RoleCategory.OTHER: VigilanceLevel.V1
    }

    def determine_vigilance_level(
        self,
        role_category: RoleCategory,
        risk_score: int
    ) -> VigilanceLevel:
        """Determine appropriate vigilance level."""

        # Start with role default
        base_level = self.ROLE_DEFAULT_VIGILANCE.get(
            role_category, VigilanceLevel.V1
        )

        # Escalate based on risk
        if risk_score >= 75:
            return VigilanceLevel.V3
        elif risk_score >= 50 and base_level < VigilanceLevel.V2:
            return VigilanceLevel.V2

        return base_level

    async def update_vigilance(
        self,
        subject_id: UUID,
        new_level: VigilanceLevel,
        reason: str
    ) -> None:
        """Update subject's vigilance level."""
        config = await self.get_monitoring_config(subject_id)
        config.vigilance_level = new_level

        # Recalculate next check date
        await self.scheduler.reschedule(config)
```

## Acceptance Criteria

- [ ] Determines vigilance by role + risk
- [ ] Updates vigilance on position change
- [ ] Escalates for high-risk subjects
- [ ] Reschedules checks after updates

## Deliverables

- `src/elile/monitoring/vigilance_manager.py`
- `tests/unit/test_vigilance_manager.py`

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
