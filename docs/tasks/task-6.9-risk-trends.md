# Task 6.9: Risk Trends Analysis

**Priority**: P1
**Phase**: 6 - Risk Analysis Engine
**Estimated Effort**: 2 days
**Dependencies**: Task 6.1 (Risk Scoring)

## Context

Analyze risk score trends over time for subjects under ongoing monitoring, detecting risk trajectory changes and emerging patterns.

**Architecture Reference**: [06-data-sources.md](../docs/architecture/06-data-sources.md) - Risk Analysis

## Objectives

1. Track risk score history
2. Calculate risk trajectories
3. Detect anomalous changes
4. Generate trend predictions
5. Support portfolio risk analysis

## Technical Approach

```python
# src/elile/risk/trends.py
class RiskTrendAnalyzer:
    """Analyze risk score trends."""

    def analyze_trend(
        self,
        subject_id: str,
        lookback_days: int = 90
    ) -> RiskTrend:
        """Analyze risk trend for subject."""
        history = self._get_risk_history(subject_id, lookback_days)

        return RiskTrend(
            direction="increasing" | "stable" | "decreasing",
            velocity=self._calculate_velocity(history),
            acceleration=self._calculate_acceleration(history),
            anomalies=self._detect_anomalies(history)
        )
```

## Implementation Checklist

- [ ] Implement trend calculation
- [ ] Add anomaly detection
- [ ] Create prediction models
- [ ] Test accuracy

## Success Criteria

- [ ] Trend detection accurate
- [ ] Anomalies identified
- [ ] Predictions useful
