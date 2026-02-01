# Task 5.7: Confidence Scorer - Implementation Plan

## Overview

Implements a standalone confidence scoring system for SAR loop assessment. The ConfidenceScorer calculates weighted confidence scores across five factors: completeness, corroboration, query success, fact confidence, and source diversity.

## Requirements

1. ConfidenceScorer class with calculate_confidence() method
2. ScorerConfig for configurable factor weights
3. ConfidenceScore dataclass with factor breakdown
4. Five weighted confidence factors
5. Foundation type threshold boost
6. Aggregate confidence calculation
7. Expected fact count configuration

## Design Decisions

### Confidence Factors

| Factor | Weight | Description |
|--------|--------|-------------|
| Completeness | 30% | Ratio of actual to expected facts |
| Corroboration | 25% | Multi-source verification rate |
| Query Success | 20% | Percentage of successful queries |
| Fact Confidence | 15% | Average confidence of extracted facts |
| Source Diversity | 10% | Number of unique data sources |

### Expected Facts Per Type

| Information Type | Expected Facts | Description |
|-----------------|----------------|-------------|
| IDENTITY | 5 | name, dob, ssn_last4, address, phone |
| EMPLOYMENT | 3 | employer, title, dates |
| EDUCATION | 3 | school, degree, dates |
| LICENSES | 2 | license, status |
| CRIMINAL | 1 | records check completed |
| CIVIL | 1 | litigation check completed |
| FINANCIAL | 2 | credit, bankruptcy |
| REGULATORY | 1 | regulatory actions |
| SANCTIONS | 1 | sanctions status |
| ADVERSE_MEDIA | 1 | media mentions |
| DIGITAL_FOOTPRINT | 2 | social, digital presence |
| NETWORK_D2 | 2 | direct associates |
| NETWORK_D3 | 3 | extended network |
| RECONCILIATION | 5 | all verified facts |

### Foundation Type Handling

Foundation types (IDENTITY, EMPLOYMENT, EDUCATION) receive:
- Higher effective threshold (+0.05 boost)
- 1.5x weight in aggregate calculations

## Files Created

### `src/elile/investigation/confidence_scorer.py`

**Classes:**
- **ScorerConfig**: Pydantic model for factor weight configuration
- **FactorBreakdown**: Dataclass for detailed factor analysis
- **ConfidenceScore**: Dataclass for complete score with breakdown
- **ConfidenceScorer**: Main scoring class

**Constants:**
- **DEFAULT_EXPECTED_FACTS**: Dict mapping InformationType to expected count
- **FOUNDATION_TYPES**: Set of foundation type information types

**Key Methods:**
- `calculate_confidence()`: Calculate score for single type
- `calculate_aggregate_confidence()`: Calculate weighted aggregate
- `get_expected_facts()`: Get expected count for type
- `set_expected_facts()`: Configure expected count
- `_calculate_completeness()`: Ratio of actual/expected facts
- `_calculate_corroboration()`: Multi-source verification rate
- `_calculate_query_success()`: Query success percentage
- `_calculate_fact_confidence()`: Average fact confidence
- `_calculate_source_diversity()`: Unique source count

### `tests/unit/test_confidence_scorer.py`

54 unit tests covering:
- ScorerConfig defaults and validation
- Weights sum verification
- FactorBreakdown creation
- ConfidenceScore creation and properties
- gap_to_threshold calculation
- factors_dict and to_dict serialization
- Default expected facts per type
- Foundation type identification
- Scorer creation with defaults and custom config
- Completeness calculation (full, partial, empty, over)
- Corroboration calculation (full, partial, none, empty)
- Query success calculation
- Fact confidence averaging
- Source diversity scaling
- Full confidence calculation
- Foundation type threshold boost
- Non-foundation normal threshold
- Aggregate confidence (empty, single, foundation-weighted)
- Expected facts get/set
- Custom expected facts in calculation
- Factor breakdown in score
- Weighted value verification
- Factory function

## Key Patterns

### Weighted Score Calculation

```python
overall = (
    completeness * weights["completeness"]
    + corroboration * weights["corroboration"]
    + query_success * weights["query_success"]
    + fact_confidence * weights["fact_confidence"]
    + source_diversity * weights["source_diversity"]
)
```

### Corroboration Calculation

```python
def _calculate_corroboration(self, facts: list[Fact]) -> float:
    # Group facts by type
    fact_groups: dict[str, list[Fact]] = defaultdict(list)
    for fact in facts:
        fact_groups[fact.fact_type].append(fact)

    # Count groups with multiple sources
    min_sources = self.config.min_sources_for_full_corroboration
    corroborated = 0

    for group_facts in fact_groups.values():
        unique_sources = {f.source_provider for f in group_facts}
        if len(unique_sources) >= min_sources:
            corroborated += 1

    return corroborated / len(fact_groups)
```

### Foundation Type Aggregate Weighting

```python
def calculate_aggregate_confidence(self, scores: list[ConfidenceScore]) -> float:
    for score in scores:
        # Foundation types get 1.5x weight
        weight = 1.5 if score.is_foundation_type else 1.0
        weighted_sum += score.overall_score * weight
        total_weight += weight

    return weighted_sum / total_weight
```

## Test Results

All 54 unit tests passing:
```
tests/unit/test_confidence_scorer.py::TestScorerConfig::test_default_config PASSED
tests/unit/test_confidence_scorer.py::TestScorerConfig::test_weights_sum_to_one PASSED
tests/unit/test_confidence_scorer.py::TestScorerConfig::test_custom_config PASSED
tests/unit/test_confidence_scorer.py::TestScorerConfig::test_get_weights PASSED
tests/unit/test_confidence_scorer.py::TestFactorBreakdown::test_breakdown_creation PASSED
tests/unit/test_confidence_scorer.py::TestConfidenceScore::test_score_creation PASSED
tests/unit/test_confidence_scorer.py::TestConfidenceScore::test_gap_to_threshold PASSED
tests/unit/test_confidence_scorer.py::TestConfidenceScore::test_gap_to_threshold_when_met PASSED
tests/unit/test_confidence_scorer.py::TestConfidenceScore::test_factors_dict PASSED
tests/unit/test_confidence_scorer.py::TestConfidenceScore::test_to_dict PASSED
tests/unit/test_confidence_scorer.py::TestDefaultExpectedFacts::test_identity_expected_facts PASSED
tests/unit/test_confidence_scorer.py::TestDefaultExpectedFacts::test_employment_expected_facts PASSED
tests/unit/test_confidence_scorer.py::TestDefaultExpectedFacts::test_criminal_expected_facts PASSED
tests/unit/test_confidence_scorer.py::TestFoundationTypes::test_identity_is_foundation PASSED
tests/unit/test_confidence_scorer.py::TestFoundationTypes::test_employment_is_foundation PASSED
tests/unit/test_confidence_scorer.py::TestFoundationTypes::test_criminal_not_foundation PASSED
tests/unit/test_confidence_scorer.py::TestConfidenceScorer::test_creation_default PASSED
tests/unit/test_confidence_scorer.py::TestConfidenceScorer::test_creation_custom_config PASSED
tests/unit/test_confidence_scorer.py::TestConfidenceScorer::test_creation_custom_expected_facts PASSED
tests/unit/test_confidence_scorer.py::TestCompletenessCalculation::test_completeness_full PASSED
tests/unit/test_confidence_scorer.py::TestCompletenessCalculation::test_completeness_partial PASSED
tests/unit/test_confidence_scorer.py::TestCompletenessCalculation::test_completeness_empty PASSED
tests/unit/test_confidence_scorer.py::TestCompletenessCalculation::test_completeness_over_expected PASSED
tests/unit/test_confidence_scorer.py::TestCorroborationCalculation::test_corroboration_full PASSED
tests/unit/test_confidence_scorer.py::TestCorroborationCalculation::test_corroboration_partial PASSED
tests/unit/test_confidence_scorer.py::TestCorroborationCalculation::test_corroboration_none PASSED
tests/unit/test_confidence_scorer.py::TestCorroborationCalculation::test_corroboration_empty PASSED
tests/unit/test_confidence_scorer.py::TestQuerySuccessCalculation::test_query_success_all PASSED
tests/unit/test_confidence_scorer.py::TestQuerySuccessCalculation::test_query_success_partial PASSED
tests/unit/test_confidence_scorer.py::TestQuerySuccessCalculation::test_query_success_none PASSED
tests/unit/test_confidence_scorer.py::TestQuerySuccessCalculation::test_query_success_empty PASSED
tests/unit/test_confidence_scorer.py::TestFactConfidenceCalculation::test_fact_confidence_average PASSED
tests/unit/test_confidence_scorer.py::TestFactConfidenceCalculation::test_fact_confidence_single PASSED
tests/unit/test_confidence_scorer.py::TestFactConfidenceCalculation::test_fact_confidence_empty PASSED
tests/unit/test_confidence_scorer.py::TestSourceDiversityCalculation::test_source_diversity_full PASSED
tests/unit/test_confidence_scorer.py::TestSourceDiversityCalculation::test_source_diversity_partial PASSED
tests/unit/test_confidence_scorer.py::TestSourceDiversityCalculation::test_source_diversity_single PASSED
tests/unit/test_confidence_scorer.py::TestSourceDiversityCalculation::test_source_diversity_empty PASSED
tests/unit/test_confidence_scorer.py::TestCalculateConfidence::test_calculate_confidence_full PASSED
tests/unit/test_confidence_scorer.py::TestCalculateConfidence::test_calculate_confidence_returns_factors PASSED
tests/unit/test_confidence_scorer.py::TestCalculateConfidence::test_calculate_confidence_empty PASSED
tests/unit/test_confidence_scorer.py::TestFoundationTypeBoost::test_foundation_type_higher_threshold PASSED
tests/unit/test_confidence_scorer.py::TestFoundationTypeBoost::test_non_foundation_type_normal_threshold PASSED
tests/unit/test_confidence_scorer.py::TestAggregateConfidence::test_aggregate_empty PASSED
tests/unit/test_confidence_scorer.py::TestAggregateConfidence::test_aggregate_single PASSED
tests/unit/test_confidence_scorer.py::TestAggregateConfidence::test_aggregate_foundation_weighted PASSED
tests/unit/test_confidence_scorer.py::TestExpectedFactsConfiguration::test_get_expected_facts PASSED
tests/unit/test_confidence_scorer.py::TestExpectedFactsConfiguration::test_set_expected_facts PASSED
tests/unit/test_confidence_scorer.py::TestExpectedFactsConfiguration::test_custom_expected_facts_in_calculation PASSED
tests/unit/test_confidence_scorer.py::TestFactorBreakdownInScore::test_breakdown_included PASSED
tests/unit/test_confidence_scorer.py::TestFactorBreakdownInScore::test_breakdown_weighted_values PASSED
tests/unit/test_confidence_scorer.py::TestFactoryFunction::test_create_default PASSED
tests/unit/test_confidence_scorer.py::TestFactoryFunction::test_create_with_config PASSED
tests/unit/test_confidence_scorer.py::TestFactoryFunction::test_create_with_expected_facts PASSED
```

## Dependencies

- Task 5.4: Result Assessor (Fact, QueryResult, QueryStatus)
- Task 5.1: SAR State Machine (state models)
- `elile.agent.state`: InformationType
- `pydantic`: BaseModel for configuration

## API Example

```python
from elile.investigation import (
    ConfidenceScorer,
    ConfidenceScore,
    ScorerConfig,
    create_confidence_scorer,
    DEFAULT_EXPECTED_FACTS,
)
from elile.agent.state import InformationType

# Create scorer with default config
scorer = create_confidence_scorer()

# Calculate confidence for identity type
score = scorer.calculate_confidence(
    info_type=InformationType.IDENTITY,
    facts=extracted_facts,
    query_results=results,
    threshold=0.85,
)

print(f"Overall: {score.overall_score:.2f}")
print(f"Threshold: {score.threshold:.2f}")
print(f"Meets threshold: {score.meets_threshold}")
print(f"Gap: {score.gap_to_threshold:.2f}")

# Factor breakdown
for factor in score.factor_breakdown:
    print(f"  {factor.name}: {factor.raw_value:.2f} * {factor.weight:.2f} = {factor.weighted_value:.2f}")

# Aggregate across multiple types
aggregate = scorer.calculate_aggregate_confidence([
    identity_score,
    employment_score,
    criminal_score,
])
print(f"Aggregate confidence: {aggregate:.2f}")
```

## Completion Date

2026-01-31
