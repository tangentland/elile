# Task 6.8: Temporal Risk Tracker

## Overview

Implement temporal risk tracker that monitors risk changes over time for ongoing monitoring, calculates risk deltas, and tracks risk evolution signals.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 6.7: Risk Aggregator
- Task 3.5: Profile Delta Calculator

## Implementation

```python
# src/elile/risk/temporal_risk_tracker.py
class TemporalRiskTracker:
    """Tracks risk changes over time."""

    def calculate_risk_delta(
        self,
        baseline_risk: RiskScore,
        current_risk: RiskScore
    ) -> RiskDelta:
        """Calculate change in risk."""

        delta = RiskDelta(
            score_change=current_risk.overall_score - baseline_risk.overall_score,
            level_change=(baseline_risk.risk_level, current_risk.risk_level),
            new_findings_count=len(current_risk.findings) - len(baseline_risk.findings),
            category_changes=self._calculate_category_deltas(
                baseline_risk, current_risk
            )
        )

        return delta

    def detect_evolution_signals(
        self,
        risk_history: list[RiskScore]
    ) -> list[EvolutionSignal]:
        """Detect risk evolution patterns."""
        signals = []

        # Detect trends
        if self._is_trending_up(risk_history):
            signals.append(EvolutionSignal(
                signal_type="trending_up",
                severity=Severity.HIGH
            ))

        # Detect sudden spikes
        if self._has_sudden_spike(risk_history):
            signals.append(EvolutionSignal(
                signal_type="sudden_spike",
                severity=Severity.CRITICAL
            ))

        return signals
```

## Acceptance Criteria

- [ ] Calculates risk deltas between timepoints
- [ ] Tracks risk score history
- [ ] Detects trending up/down patterns
- [ ] Identifies sudden risk spikes
- [ ] Generates evolution signals

## Deliverables

- `src/elile/risk/temporal_risk_tracker.py`
- `tests/unit/test_temporal_risk_tracker.py`

## References

- Architecture: [04-monitoring.md](../../docs/architecture/04-monitoring.md) - Evolution Signals

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
