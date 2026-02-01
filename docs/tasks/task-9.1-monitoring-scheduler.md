# Task 9.1: Monitoring Scheduler

## Overview

Implement monitoring scheduler that manages vigilance-level based scheduling (V1/V2/V3), executes periodic checks, and handles lifecycle events.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 2.3: Vigilance Levels
- Task 7.1: Screening Orchestrator

## Implementation

```python
# src/elile/monitoring/scheduler.py
class MonitoringScheduler:
    """Schedules ongoing monitoring checks."""

    VIGILANCE_INTERVALS = {
        VigilanceLevel.V1: timedelta(days=365),  # Annual
        VigilanceLevel.V2: timedelta(days=30),   # Monthly
        VigilanceLevel.V3: timedelta(days=15)    # Bi-monthly
    }

    async def schedule_monitoring(
        self,
        subject_id: UUID,
        vigilance_level: VigilanceLevel,
        baseline_profile_id: UUID
    ) -> MonitoringConfig:
        """Set up ongoing monitoring schedule."""

        interval = self.VIGILANCE_INTERVALS[vigilance_level]
        next_check = datetime.now(timezone.utc) + interval

        config = MonitoringConfig(
            subject_id=subject_id,
            vigilance_level=vigilance_level,
            baseline_profile_id=baseline_profile_id,
            next_check_date=next_check
        )

        await self.db.add(config)
        return config

    async def execute_scheduled_checks(self) -> None:
        """Execute all due monitoring checks."""
        due_checks = await self._get_due_checks()

        for check in due_checks:
            await self._execute_monitoring_check(check)

    async def _execute_monitoring_check(self, config: MonitoringConfig) -> None:
        """Execute single monitoring check."""
        # Run screening with delta detection
        pass
```

## Acceptance Criteria

- [ ] Schedules V1 (annual), V2 (monthly), V3 (bi-monthly)
- [ ] Executes scheduled checks on time
- [ ] Handles lifecycle events (termination, etc.)
- [ ] Updates next check date after execution

## Deliverables

- `src/elile/monitoring/scheduler.py`
- `tests/unit/test_monitoring_scheduler.py`

## References

- Architecture: [04-monitoring.md](../../docs/architecture/04-monitoring.md)

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
