# Task 6.2: Risk Scorer

## Overview

Implemented the RiskScorer for calculating composite risk scores (0-100) from findings with severity weighting, recency decay, corroboration bonuses, and category-weighted aggregation.

## Requirements Met

1. **Composite Scoring** - Calculate 0-100 overall risk scores
2. **Severity Weighting** - Base scores by severity level (10/25/50/75)
3. **Recency Decay** - Recent findings weighted more heavily (1.0 → 0.5)
4. **Corroboration Bonus** - Multi-source findings get 1.2x multiplier
5. **Category Breakdown** - Per-category scoring with weights
6. **Risk Level Classification** - LOW/MODERATE/HIGH/CRITICAL
7. **Recommendation Generation** - Hiring recommendations based on risk

## Files Created

### Source Files

| File | Purpose |
|------|---------|
| `src/elile/risk/risk_scorer.py` | RiskScorer and related models |
| `src/elile/risk/__init__.py` | Updated exports |

### Test Files

| File | Tests |
|------|-------|
| `tests/unit/test_risk_scorer.py` | 56 unit tests |

## Key Components

### RiskScorer

Main scorer class for calculating composite risk scores:
- `calculate_risk_score()` - Calculate overall score from findings
- `get_category_breakdown()` - Get sorted category scores with descriptions
- `_calculate_category_scores()` - Per-category scoring
- `_calculate_overall_score()` - Weighted average calculation
- `_calculate_recency_factor()` - Decay based on finding age
- `_determine_risk_level()` - Score to level classification
- `_determine_recommendation()` - Level to recommendation
- `_identify_factors()` - Contributing factor analysis

### RiskScore Dataclass

Complete score model capturing:
- score_id: UUIDv7 identifier
- overall_score: Composite score (0-100)
- risk_level: Classification (LOW/MODERATE/HIGH/CRITICAL)
- category_scores: Per-category breakdown
- contributing_factors: Factor counts and statistics
- recommendation: Hiring recommendation
- entity_id/screening_id: Tracking identifiers

### RiskLevel Enum

Risk classification levels:
- `LOW` - Score 0-25
- `MODERATE` - Score 26-50
- `HIGH` - Score 51-75
- `CRITICAL` - Score 76-100

### Recommendation Enum

Hiring recommendations:
- `PROCEED` - Low risk, proceed with hire
- `PROCEED_WITH_CAUTION` - Moderate risk, some concerns
- `REVIEW_REQUIRED` - High risk, requires human review
- `DO_NOT_PROCEED` - Critical risk, recommend against

### ScorerConfig

Configuration options:
- `severity_*` - Base scores for each severity level
- `*_weight` - Category multipliers (criminal 1.5x, regulatory 1.3x, etc.)
- `recency_*` - Decay factors by age bracket
- `corroboration_bonus` - Multiplier for multi-source findings
- `*_threshold` - Risk level score thresholds

## Key Patterns

### Calculate Risk Score

```python
scorer = RiskScorer()

score = scorer.calculate_risk_score(
    findings=findings,
    role_category=RoleCategory.FINANCIAL,
    entity_id=entity_id,
    screening_id=screening_id,
)

print(f"Overall: {score.overall_score}")
print(f"Level: {score.risk_level}")
print(f"Recommendation: {score.recommendation}")
```

### Scoring Formula

For each finding:
```
finding_score = base_severity * recency_factor * confidence * corroboration * relevance
```

Where:
- base_severity: 10/25/50/75 for LOW/MEDIUM/HIGH/CRITICAL
- recency_factor: 1.0 (≤1yr), 0.9 (1-3yr), 0.7 (3-7yr), 0.5 (7+yr), 0.8 (unknown)
- confidence: Finding confidence score (0.0-1.0)
- corroboration: 1.2 if corroborated, 1.0 otherwise
- relevance: Finding relevance to role (0.0-1.0)

Category score = sum of finding scores (capped at 100)

Overall score = weighted average of category scores

### Category Weights

| Category | Weight | Rationale |
|----------|--------|-----------|
| CRIMINAL | 1.5 | High impact on suitability |
| REGULATORY | 1.3 | Compliance implications |
| VERIFICATION | 1.2 | Identity/credential concerns |
| FINANCIAL | 1.0 | Standard weight |
| BEHAVIORAL | 1.0 | Standard weight |
| NETWORK | 0.9 | Indirect concern |
| REPUTATION | 0.8 | Lower direct impact |

### Custom Configuration

```python
config = ScorerConfig(
    severity_critical=80,  # Higher base for critical
    criminal_weight=2.0,   # Double weight for criminal
    corroboration_bonus=1.5,  # 50% bonus for corroboration
    critical_threshold=70,  # Lower threshold for critical
)
scorer = RiskScorer(config=config)
```

## Test Results

```
======================== 56 passed, 2 warnings in 0.82s ========================
```

### Test Coverage

| Test Category | Tests |
|---------------|-------|
| Initialization | 4 |
| ScorerConfig | 4 |
| Empty Findings | 2 |
| Category Scores | 4 |
| Severity Weighting | 5 |
| Recency Decay | 5 |
| Corroboration | 3 |
| Confidence/Relevance | 3 |
| Overall Score | 2 |
| Risk Level | 4 |
| Recommendation | 5 |
| Contributing Factors | 5 |
| RiskScore Model | 2 |
| Category Breakdown | 2 |
| Enums | 2 |
| Edge Cases | 4 |

## Dependencies

- Task 6.1 (Finding Classifier) - Categorized findings
- Task 5.10 (Finding Extractor) - Finding model

## Next Task

Task 6.3: Multi-Model Risk Aggregator - Aggregate scores from multiple AI models.
