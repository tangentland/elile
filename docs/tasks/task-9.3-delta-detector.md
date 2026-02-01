# Task 9.3: Delta Detector

## Overview

Implement delta detector that compares current monitoring results against baseline, identifies new findings, changed findings, and resolved findings.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 3.5: Profile Delta Calculator
- Task 6.8: Temporal Risk Tracker

## Implementation

```python
# src/elile/monitoring/delta_detector.py
class DeltaDetector:
    """Detects changes in monitoring checks."""

    async def detect_deltas(
        self,
        baseline_profile: Profile,
        current_profile: Profile
    ) -> list[ProfileDelta]:
        """Detect deltas between baseline and current."""

        deltas = []

        # Compare findings
        deltas.extend(self._compare_findings(
            baseline_profile.findings,
            current_profile.findings
        ))

        # Compare risk scores
        deltas.extend(self._compare_risk_scores(
            baseline_profile.risk_score,
            current_profile.risk_score
        ))

        return deltas

    def _compare_findings(
        self,
        baseline_findings: list[Finding],
        current_findings: list[Finding]
    ) -> list[ProfileDelta]:
        """Compare findings for changes."""

        deltas = []

        # New findings
        baseline_ids = {f.finding_id for f in baseline_findings}
        for finding in current_findings:
            if finding.finding_id not in baseline_ids:
                deltas.append(ProfileDelta(
                    delta_type=DeltaType.NEW_FINDING,
                    field="findings",
                    old_value=None,
                    new_value=finding
                ))

        return deltas
```

## Acceptance Criteria

- [ ] Detects new findings
- [ ] Detects changed findings
- [ ] Detects resolved findings
- [ ] Compares risk scores
- [ ] Identifies escalations

## Deliverables

- `src/elile/monitoring/delta_detector.py`
- `tests/unit/test_delta_detector.py`

## References

- Architecture: [04-monitoring.md](../../docs/architecture/04-monitoring.md) - Delta Detection

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
