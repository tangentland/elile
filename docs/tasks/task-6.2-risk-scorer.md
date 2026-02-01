# Task 6.2: Risk Scorer

## Overview

Implement risk scorer that calculates composite risk scores from findings with category breakdown, severity weighting, recency factors, and corroboration bonuses.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 6.1: Finding Classifier (categorized findings)
- Task 5.10: Finding Extractor (findings)

## Implementation Checklist

- [ ] Create RiskScorer with composite calculation
- [ ] Implement severity weighting
- [ ] Build recency decay function
- [ ] Add corroboration multipliers
- [ ] Create category breakdown scoring
- [ ] Write comprehensive scorer tests

## Key Implementation

```python
# src/elile/risk/risk_scorer.py
@dataclass
class RiskScore:
    """Composite risk score with breakdown."""
    overall_score: int  # 0-100
    risk_level: RiskLevel
    category_scores: dict[FindingCategory, int]
    contributing_factors: dict[str, float]
    recommendation: Recommendation

class RiskLevel(str, Enum):
    LOW = "low"  # 0-25
    MODERATE = "moderate"  # 26-50
    HIGH = "high"  # 51-75
    CRITICAL = "critical"  # 76-100

class Recommendation(str, Enum):
    PROCEED = "proceed"
    PROCEED_WITH_CAUTION = "proceed_with_caution"
    REVIEW_REQUIRED = "review_required"
    DO_NOT_PROCEED = "do_not_proceed"

class RiskScorer:
    """Calculates composite risk scores."""

    # Severity base scores
    SEVERITY_SCORES = {
        Severity.LOW: 10,
        Severity.MEDIUM: 25,
        Severity.HIGH: 50,
        Severity.CRITICAL: 75
    }

    # Category weights
    CATEGORY_WEIGHTS = {
        FindingCategory.CRIMINAL: 1.5,
        FindingCategory.FINANCIAL: 1.0,
        FindingCategory.REGULATORY: 1.3,
        FindingCategory.REPUTATION: 0.8,
        FindingCategory.VERIFICATION: 1.2,
        FindingCategory.BEHAVIORAL: 1.0,
        FindingCategory.NETWORK: 0.9
    }

    def calculate_risk_score(
        self,
        findings: list[Finding],
        role_category: RoleCategory
    ) -> RiskScore:
        """Calculate overall risk score from findings."""

        if not findings:
            return RiskScore(
                overall_score=0,
                risk_level=RiskLevel.LOW,
                category_scores={},
                contributing_factors={},
                recommendation=Recommendation.PROCEED
            )

        # Calculate category scores
        category_scores = self._calculate_category_scores(findings)

        # Calculate weighted overall
        overall = self._calculate_overall_score(findings, category_scores)

        # Determine level and recommendation
        level = self._determine_risk_level(overall)
        recommendation = self._determine_recommendation(level, findings)

        # Identify contributing factors
        factors = self._identify_factors(findings)

        return RiskScore(
            overall_score=min(int(overall), 100),
            risk_level=level,
            category_scores=category_scores,
            contributing_factors=factors,
            recommendation=recommendation
        )

    def _calculate_category_scores(
        self,
        findings: list[Finding]
    ) -> dict[FindingCategory, int]:
        """Calculate score per category."""
        scores = {}

        # Group by category
        by_category = {}
        for f in findings:
            if f.category not in by_category:
                by_category[f.category] = []
            by_category[f.category].append(f)

        # Score each category
        for category, category_findings in by_category.items():
            category_score = 0

            for finding in category_findings:
                # Base score from severity
                base = self.SEVERITY_SCORES[finding.severity]

                # Apply recency decay
                recency_factor = self._calculate_recency_factor(finding.finding_date)

                # Apply confidence
                confidence_factor = finding.confidence

                # Apply corroboration bonus
                corroboration_bonus = 1.2 if finding.corroborated else 1.0

                # Apply relevance
                relevance_factor = finding.relevance_to_role

                # Calculate finding score
                finding_score = (
                    base *
                    recency_factor *
                    confidence_factor *
                    corroboration_bonus *
                    relevance_factor
                )

                category_score += finding_score

            scores[category] = min(int(category_score), 100)

        return scores

    def _calculate_overall_score(
        self,
        findings: list[Finding],
        category_scores: dict[FindingCategory, int]
    ) -> float:
        """Calculate weighted overall score."""
        if not category_scores:
            return 0.0

        weighted_sum = sum(
            score * self.CATEGORY_WEIGHTS.get(category, 1.0)
            for category, score in category_scores.items()
        )

        weight_total = sum(
            self.CATEGORY_WEIGHTS.get(category, 1.0)
            for category in category_scores.keys()
        )

        return weighted_sum / weight_total if weight_total else 0.0

    def _calculate_recency_factor(self, finding_date: date | None) -> float:
        """Calculate recency decay factor (1.0 = recent, 0.5 = old)."""
        if not finding_date:
            return 0.8  # Unknown date = moderate recency

        years_ago = (date.today() - finding_date).days / 365.25

        if years_ago <= 1:
            return 1.0  # Last year: full weight
        elif years_ago <= 3:
            return 0.9  # 1-3 years: 90%
        elif years_ago <= 7:
            return 0.7  # 3-7 years: 70%
        else:
            return 0.5  # 7+ years: 50%

    def _determine_risk_level(self, score: float) -> RiskLevel:
        """Determine risk level from score."""
        if score >= 76:
            return RiskLevel.CRITICAL
        elif score >= 51:
            return RiskLevel.HIGH
        elif score >= 26:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW

    def _determine_recommendation(
        self,
        level: RiskLevel,
        findings: list[Finding]
    ) -> Recommendation:
        """Determine hiring recommendation."""
        # Check for any critical findings
        has_critical = any(f.severity == Severity.CRITICAL for f in findings)

        if has_critical or level == RiskLevel.CRITICAL:
            return Recommendation.DO_NOT_PROCEED
        elif level == RiskLevel.HIGH:
            return Recommendation.REVIEW_REQUIRED
        elif level == RiskLevel.MODERATE:
            return Recommendation.PROCEED_WITH_CAUTION
        else:
            return Recommendation.PROCEED

    def _identify_factors(self, findings: list[Finding]) -> dict[str, float]:
        """Identify contributing risk factors."""
        factors = {
            "total_findings": len(findings),
            "critical_findings": sum(1 for f in findings if f.severity == Severity.CRITICAL),
            "high_findings": sum(1 for f in findings if f.severity == Severity.HIGH),
            "corroborated_findings": sum(1 for f in findings if f.corroborated),
            "recent_findings": sum(
                1 for f in findings
                if f.finding_date and (date.today() - f.finding_date).days <= 365
            )
        }
        return factors
```

## Testing Requirements

### Unit Tests
- Category score calculation
- Overall score weighting
- Recency decay function
- Corroboration bonuses
- Risk level determination
- Recommendation logic

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] RiskScorer calculates 0-100 composite score
- [ ] Category scores broken down
- [ ] Recency decay applied (1.0 → 0.5 over 7 years)
- [ ] Corroboration bonus (1.2x)
- [ ] Risk level determined (LOW/MODERATE/HIGH/CRITICAL)
- [ ] Recommendation generated

## Deliverables

- `src/elile/risk/risk_scorer.py`
- `src/elile/models/risk_score.py`
- `tests/unit/test_risk_scorer.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - Risk Scorer

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
