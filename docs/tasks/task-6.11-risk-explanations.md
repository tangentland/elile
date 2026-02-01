# Task 6.11: Risk Score Explanations

**Priority**: P1
**Phase**: 6 - Risk Analysis
**Estimated Effort**: 2 days
**Dependencies**: Task 6.1 (Risk Scoring)

## Context

Generate human-readable explanations for risk scores, showing contributing factors and their weights for transparency and compliance.

## Objectives

1. Generate risk score breakdowns
2. Show contributing factors
3. Create natural language explanations
4. Support "what-if" analysis
5. Enable explanation export

## Technical Approach

```python
# src/elile/risk/explanations.py
class RiskExplainer:
    def explain_score(self, risk_result: RiskResult) -> RiskExplanation:
        return RiskExplanation(
            score=risk_result.score,
            level=risk_result.level,
            primary_factors=self._get_primary_factors(risk_result),
            narrative=self._generate_narrative(risk_result)
        )
```

## Implementation Checklist

- [ ] Generate explanations
- [ ] Create narratives
- [ ] Test clarity

## Success Criteria

- [ ] Explanations clear
- [ ] Factors accurate
