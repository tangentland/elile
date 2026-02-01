# Task 6.7: Risk Aggregator

## Overview

Implement risk aggregator that combines findings, patterns, anomalies, and connections into comprehensive risk assessment with weighted scoring and recommendation generation.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 6.2: Risk Scorer
- Task 6.5: Pattern Recognizer
- Task 6.6: Connection Analyzer

## Implementation

```python
# src/elile/risk/risk_aggregator.py
class RiskAggregator:
    """Aggregates all risk components."""

    def aggregate_risk(
        self,
        base_score: RiskScore,
        patterns: list[Pattern],
        anomalies: list[Anomaly],
        connections: list[EntityConnection]
    ) -> ComprehensiveRiskAssessment:
        """Aggregate all risk factors."""

        # Start with base score
        final_score = base_score.overall_score

        # Add pattern risk
        pattern_adjustment = self._calculate_pattern_adjustment(patterns)
        final_score += pattern_adjustment

        # Add anomaly risk
        anomaly_adjustment = self._calculate_anomaly_adjustment(anomalies)
        final_score += anomaly_adjustment

        # Add network risk
        network_adjustment = self._calculate_network_adjustment(connections)
        final_score += network_adjustment

        # Cap at 100
        final_score = min(final_score, 100)

        return ComprehensiveRiskAssessment(
            final_score=final_score,
            base_score=base_score,
            adjustments={
                "patterns": pattern_adjustment,
                "anomalies": anomaly_adjustment,
                "network": network_adjustment
            },
            recommendation=self._generate_recommendation(final_score)
        )
```

## Acceptance Criteria

- [ ] Aggregates findings, patterns, anomalies, connections
- [ ] Applies weighted adjustments
- [ ] Generates final 0-100 score
- [ ] Produces comprehensive recommendation
- [ ] Shows adjustment breakdown

## Deliverables

- `src/elile/risk/risk_aggregator.py`
- `tests/unit/test_risk_aggregator.py`

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
