# Task 9.5: V1 Annual Rescreening

**Priority**: P1
**Phase**: 9 - Ongoing Monitoring
**Estimated Effort**: 2 days
**Dependencies**: Task 9.1 (Vigilance Levels)

## Context

Implement V1 (Basic Vigilance) annual rescreening workflow for periodic full background checks on monitored subjects.

## Objectives

1. Schedule annual rescreens
2. Execute full screening workflow
3. Compare with baseline
4. Generate delta reports
5. Alert on changes

## Technical Approach

```python
# src/elile/monitoring/vigilance/v1_handler.py
class V1AnnualRescreenHandler:
    async def execute_rescreen(self, monitor: Monitor) -> RescreenResult:
        # Run full screening
        new_screening = await self._execute_screening(monitor.subject_id)

        # Compare with baseline
        delta = self._compare_screenings(monitor.baseline_screening_id, new_screening.id)

        # Generate alert if changes
        if delta.has_significant_changes:
            await self._generate_alert(monitor, delta)

        return RescreenResult(screening=new_screening, delta=delta)
```

## Implementation Checklist

- [ ] Implement scheduling
- [ ] Add comparison logic
- [ ] Test delta detection

## Success Criteria

- [ ] Annual rescreens triggered
- [ ] Changes detected accurately
