# Task 5.7: Confidence Scorer

## Overview

Implement confidence scoring system that evaluates completeness, corroboration, and quality of gathered information for each type. Provides weighted confidence calculation with contributing factors.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 5.4: Result Assessor (fact extraction)
- Task 5.1: SAR State Machine (confidence thresholds)

## Implementation Checklist

- [ ] Create ConfidenceScorer with multi-factor calculation
- [ ] Implement completeness scoring
- [ ] Build corroboration analysis
- [ ] Add quality metrics
- [ ] Create factor weighting system
- [ ] Write comprehensive scoring tests

## Key Implementation

```python
# src/elile/investigation/confidence_scorer.py
@dataclass
class ConfidenceScore:
    """Confidence score with contributing factors."""
    overall_score: float  # 0.0 - 1.0
    factors: dict[str, float]
    meets_threshold: bool
    threshold_used: float

class ConfidenceScorer:
    """Calculates confidence scores for information types."""

    # Expected fact counts per type
    EXPECTED_FACTS = {
        InformationType.IDENTITY: 5,  # Names, addresses, DOB, SSN
        InformationType.EMPLOYMENT: 3,  # At least 3 employers
        InformationType.EDUCATION: 2,  # At least 2 schools
        InformationType.CRIMINAL: 1,  # At least check completed
        InformationType.FINANCIAL: 3,  # Credit report sections
    }

    # Factor weights
    FACTOR_WEIGHTS = {
        "completeness": 0.35,
        "corroboration": 0.30,
        "query_success": 0.20,
        "fact_confidence": 0.15
    }

    def calculate_confidence(
        self,
        info_type: InformationType,
        facts: list[Fact],
        query_results: list[QueryResult],
        threshold: float
    ) -> ConfidenceScore:
        """Calculate overall confidence score."""

        factors = {}

        # Factor 1: Completeness
        factors["completeness"] = self._calculate_completeness(info_type, facts)

        # Factor 2: Corroboration
        factors["corroboration"] = self._calculate_corroboration(facts)

        # Factor 3: Query success rate
        factors["query_success"] = self._calculate_query_success(query_results)

        # Factor 4: Fact confidence average
        factors["fact_confidence"] = self._calculate_fact_confidence(facts)

        # Weighted average
        overall = sum(
            factors[name] * self.FACTOR_WEIGHTS[name]
            for name in factors
        )

        return ConfidenceScore(
            overall_score=overall,
            factors=factors,
            meets_threshold=overall >= threshold,
            threshold_used=threshold
        )

    def _calculate_completeness(
        self,
        info_type: InformationType,
        facts: list[Fact]
    ) -> float:
        """Calculate data completeness (0.0-1.0)."""
        expected = self.EXPECTED_FACTS.get(info_type, 1)
        actual = len(facts)
        return min(actual / expected, 1.0)

    def _calculate_corroboration(self, facts: list[Fact]) -> float:
        """Calculate multi-source corroboration (0.0-1.0)."""
        if not facts:
            return 0.0

        # Group facts by type
        fact_groups = {}
        for fact in facts:
            if fact.fact_type not in fact_groups:
                fact_groups[fact.fact_type] = []
            fact_groups[fact.fact_type].append(fact)

        # Calculate corroboration per group
        corroborated = 0
        total_groups = len(fact_groups)

        for group in fact_groups.values():
            # Count unique sources
            sources = set(f.source_provider for f in group)
            if len(sources) >= 2:
                corroborated += 1

        return corroborated / total_groups if total_groups else 0.0

    def _calculate_query_success(self, results: list[QueryResult]) -> float:
        """Calculate query success rate (0.0-1.0)."""
        if not results:
            return 0.0

        successful = sum(1 for r in results if r.status == "success")
        return successful / len(results)

    def _calculate_fact_confidence(self, facts: list[Fact]) -> float:
        """Calculate average fact confidence (0.0-1.0)."""
        if not facts:
            return 0.0

        return sum(f.confidence for f in facts) / len(facts)
```

## Testing Requirements

### Unit Tests
- Completeness calculation per type
- Corroboration with multiple sources
- Query success rate calculation
- Fact confidence averaging
- Weighted score calculation
- Threshold evaluation

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] ConfidenceScorer calculates weighted scores
- [ ] Completeness based on expected facts per type
- [ ] Corroboration rewards multiple sources
- [ ] Query success rate factored in
- [ ] Score factors returned with weights
- [ ] Threshold comparison included

## Deliverables

- `src/elile/investigation/confidence_scorer.py`
- `tests/unit/test_confidence_scorer.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - SAR Assess

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
