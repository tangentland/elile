# Task 9.11: Change Impact Analysis

**Priority**: P1
**Phase**: 9 - Ongoing Monitoring
**Estimated Effort**: 2 days
**Dependencies**: Task 9.2 (Alert Management)

## Context

Analyze impact of detected changes on risk profile and employment status, generating recommendations for HR action.

## Objectives

1. Calculate change impact
2. Risk reassessment
3. Generate recommendations
4. Support decision workflow
5. Track outcomes

## Technical Approach

```python
# src/elile/monitoring/impact_analysis.py
class ChangeImpactAnalyzer:
    def analyze_impact(
        self,
        baseline: Screening,
        changes: List[Change]
    ) -> ImpactAnalysis:
        # Reassess risk
        # Evaluate policy violations
        # Generate recommendations
        return ImpactAnalysis(
            risk_delta=delta,
            policy_violations=violations,
            recommendations=recommendations
        )
```

## Implementation Checklist

- [ ] Implement impact analysis
- [ ] Add recommendation engine
- [ ] Test accuracy

## Success Criteria

- [ ] Accurate impact assessment
- [ ] Useful recommendations
