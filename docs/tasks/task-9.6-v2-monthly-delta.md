# Task 9.6: V2 Monthly Delta Monitoring

**Priority**: P1
**Phase**: 9 - Ongoing Monitoring
**Estimated Effort**: 2 days
**Dependencies**: Task 9.1 (Vigilance Levels)

## Context

Implement V2 (Standard Vigilance) monthly delta monitoring checking specific high-risk data sources for changes.

## Objectives

1. Monthly delta checks
2. Focus on high-risk sources
3. Incremental screening
4. Change detection
5. Efficient monitoring

## Technical Approach

```python
# src/elile/monitoring/vigilance/v2_handler.py
class V2DeltaMonitorHandler:
    async def execute_delta_check(self, monitor: Monitor) -> DeltaCheckResult:
        # Query high-risk sources only
        sources = self._select_high_risk_sources(monitor)

        # Check for changes
        changes = await self._check_sources(monitor.subject_id, sources)

        return DeltaCheckResult(changes=changes, next_check=30_days)
```

## Implementation Checklist

- [ ] Implement delta checking
- [ ] Add source selection
- [ ] Test efficiency

## Success Criteria

- [ ] Cost-effective monitoring
- [ ] Changes detected quickly
