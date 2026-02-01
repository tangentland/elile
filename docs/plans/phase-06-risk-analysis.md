# Phase 6: Risk Analysis

## Overview

Phase 6 implements multi-model risk scoring, finding categorization, connection mapping (degree-aware), and rule-based evolution pattern detection. This phase converts raw findings into actionable risk assessments.

**Duration Estimate**: 3-4 weeks
**Team Size**: 2-3 developers
**Risk Level**: Medium (risk scoring accuracy critical)
**Status**: 🟡 In Progress (11/12 tasks complete)
**Last Updated**: 2026-02-01

## Phase Goals

- ✅ Categorize findings by type (criminal, financial, regulatory, etc.)
- ✅ Calculate composite risk scores with severity/recency/corroboration weighting
- ✅ Determine finding severity with rule-based and role-adjusted scoring
- ✅ Detect anomalous patterns in findings and behaviors
- ✅ Recognize risk patterns across investigations
- ✅ Analyze network connections and risk propagation
- ✅ Aggregate multi-dimensional risk scores

## Tasks

| Seq | Task Name | Priority | Status | Dependencies | Plan Document |
|-----|-----------|----------|--------|--------------|---------------|
| 6.1 | Finding Classifier | P0 | ✅ Complete | Phase 5 | [task-6.1-finding-classifier.md](../tasks/task-6.1-finding-classifier.md) |
| 6.2 | Risk Scorer | P0 | ✅ Complete | 6.1 | [task-6.2-risk-scorer.md](../tasks/task-6.2-risk-scorer.md) |
| 6.3 | Severity Calculator | P0 | ✅ Complete | 6.1, 5.10 | [task-6.3-severity-calculator.md](../tasks/task-6.3-severity-calculator.md) |
| 6.4 | Anomaly Detector | P0 | ✅ Complete | 6.1, 6.2 | [task-6.4-anomaly-detector.md](../tasks/task-6.4-anomaly-detector.md) |
| 6.5 | Pattern Recognizer | P0 | ✅ Complete | 6.4 | [task-6.5-pattern-recognizer.md](../tasks/task-6.5-pattern-recognizer.md) |
| 6.6 | Connection Analyzer | P0 | ✅ Complete | 5.14 | [task-6.6-connection-analyzer.md](../tasks/task-6.6-connection-analyzer.md) |
| 6.7 | Risk Aggregator | P0 | ✅ Complete | 6.2, 6.3, 6.4 | [task-6.7-risk-aggregator.md](../tasks/task-6.7-risk-aggregator.md) |
| 6.8 | Temporal Risk Tracker | P1 | ✅ Complete | 6.7 | [task-6.8-temporal-risk-tracker.md](../tasks/task-6.8-temporal-risk-tracker.md) |
| 6.9 | Risk Trends | P1 | ✅ Complete | 6.8 | [task-6.9-risk-trends.md](../tasks/task-6.9-risk-trends.md) |
| 6.10 | Risk Thresholds | P1 | ✅ Complete | 6.7 | [task-6.10-risk-thresholds.md](../tasks/task-6.10-risk-thresholds.md) |
| 6.11 | Risk Explanations | P1 | ✅ Complete | 6.7 | [task-6.11-risk-explanations.md](../tasks/task-6.11-risk-explanations.md) |
| 6.12 | Risk Dashboard | P2 | Not Started | 6.7, 6.10, 6.11 | [task-6.12-risk-dashboard.md](../tasks/task-6.12-risk-dashboard.md) |

## Key Models

### Risk Scoring
```python
class RiskScore(BaseModel):
    overall: float  # 0.0 - 1.0
    category_scores: dict[FindingCategory, float]
    contributing_factors: list[str]
    confidence: float
    model_scores: dict[str, float]  # claude, gpt4, gemini

class FindingCategory(str, Enum):
    CRIMINAL = "criminal"
    FINANCIAL = "financial"
    REGULATORY = "regulatory"
    REPUTATION = "reputation"
    VERIFICATION = "verification"
    BEHAVIORAL = "behavioral"
    NETWORK = "network"

class MultiModelRiskAnalyzer:
    async def compute_risk(
        self,
        findings: list[Finding],
        entity_graph: EntityGraph,
        locale: str
    ) -> RiskScore:
        """Aggregate risk scores from multiple AI models."""
        claude_score = await self.claude_adapter.score_risk(findings)
        gpt4_score = await self.openai_adapter.score_risk(findings)
        gemini_score = await self.gemini_adapter.score_risk(findings)

        return self.aggregate_scores([claude_score, gpt4_score, gemini_score])
```

### Evolution Patterns
```python
class EvolutionSignal(BaseModel):
    signal_type: str  # network_expansion, financial_deterioration, etc.
    confidence: float
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    contributing_factors: list[str]
    pattern_signature: str | None

EVOLUTION_SIGNATURES = {
    "network_expansion_rapid": {
        "condition": "connection_count_change > 200% AND timespan < 180 days",
        "severity": "high",
        "description": "Rapid network expansion (shell company indicator)"
    },
    "financial_deterioration": {
        "condition": "accumulating_judgments AND credit_score_decline",
        "severity": "medium",
        "description": "Progressive financial distress"
    },
}
```

## Phase Acceptance Criteria

### Functional Requirements
- [x] Risk scores computed by all 3 AI models
- [x] Composite risk score aggregates model outputs
- [x] Role-specific weighting applied (financial crimes → finance roles)
- [x] Recent findings weighted higher than old findings
- [x] D2 connection mapping discovers direct associates
- [x] D3 connection mapping discovers second-degree network
- [x] Evolution detector identifies 5+ known patterns

### Testing Requirements
- [x] Unit tests for risk calculation
- [x] Integration tests with mock AI models
- [x] Test case: No findings → low risk score
- [x] Test case: Critical finding → high risk score
- [x] Connection mapping tests for all degrees

### Review Gates
- [x] AI/ML review: Risk scoring methodology
- [x] Business review: Risk thresholds and categories

---

*Phase Owner: [Assign team lead]*
*Last Updated: 2026-01-29*
