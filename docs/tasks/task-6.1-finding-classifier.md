# Task 6.1: Finding Classifier

## Overview

Implement finding classifier that categorizes extracted findings into risk categories (criminal, financial, regulatory, reputation, verification, behavioral, network) with category-specific analysis.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 5.10: Finding Extractor (findings)
- Task 2.1: Service Tiers (tier-based categories)

## Implementation Checklist

- [ ] Create FindingClassifier with category rules
- [ ] Implement category assignment logic
- [ ] Build sub-category classification
- [ ] Add category confidence scoring
- [ ] Create classification audit trail
- [ ] Write comprehensive classifier tests

## Key Implementation

```python
# src/elile/risk/finding_classifier.py
class FindingClassifier:
    """Classifies findings into risk categories."""

    # Category keywords
    CATEGORY_KEYWORDS = {
        FindingCategory.CRIMINAL: [
            "arrest", "conviction", "felony", "misdemeanor",
            "charge", "criminal", "offense", "violation"
        ],
        FindingCategory.FINANCIAL: [
            "bankruptcy", "lien", "judgment", "debt",
            "foreclosure", "garnishment", "default"
        ],
        FindingCategory.REGULATORY: [
            "license", "sanction", "enforcement", "violation",
            "suspension", "revocation", "bar", "restriction"
        ],
        FindingCategory.REPUTATION: [
            "litigation", "lawsuit", "complaint", "allegation",
            "adverse media", "controversy", "scandal"
        ],
        FindingCategory.VERIFICATION: [
            "discrepancy", "gap", "inconsistency", "mismatch",
            "unverified", "false", "misleading"
        ]
    }

    def classify_finding(
        self,
        finding: Finding,
        role_category: RoleCategory
    ) -> Finding:
        """
        Classify finding (updates category if needed).

        Args:
            finding: Finding to classify
            role_category: Role for relevance

        Returns:
            Classified finding
        """
        # If already classified by AI, validate
        if finding.category:
            confidence = self._validate_category(finding)
            if confidence < 0.7:
                # Re-classify
                finding.category = self._determine_category(finding)
        else:
            # Classify from scratch
            finding.category = self._determine_category(finding)

        # Update relevance based on category and role
        finding.relevance_to_role = self._calculate_relevance(
            finding.category, role_category
        )

        return finding

    def _determine_category(self, finding: Finding) -> FindingCategory:
        """Determine category from finding content."""
        text = f"{finding.summary} {finding.details}".lower()

        # Count keyword matches per category
        scores = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[category] = score

        # Return highest scoring category
        if not scores or max(scores.values()) == 0:
            return FindingCategory.VERIFICATION  # Default

        return max(scores, key=scores.get)

    def _validate_category(self, finding: Finding) -> float:
        """Validate AI-assigned category (0.0-1.0)."""
        text = f"{finding.summary} {finding.details}".lower()
        keywords = self.CATEGORY_KEYWORDS.get(finding.category, [])

        matches = sum(1 for kw in keywords if kw in text)
        return min(matches / 3.0, 1.0)  # 3+ matches = full confidence

    def _calculate_relevance(
        self,
        category: FindingCategory,
        role: RoleCategory
    ) -> float:
        """Calculate role-specific relevance."""
        # Relevance matrix
        relevance = {
            (FindingCategory.CRIMINAL, RoleCategory.GOVERNMENT): 1.0,
            (FindingCategory.CRIMINAL, RoleCategory.ENERGY): 0.9,
            (FindingCategory.CRIMINAL, RoleCategory.FINANCE): 0.9,
            (FindingCategory.FINANCIAL, RoleCategory.FINANCE): 1.0,
            (FindingCategory.FINANCIAL, RoleCategory.GOVERNMENT): 0.7,
            (FindingCategory.REGULATORY, RoleCategory.FINANCE): 1.0,
            (FindingCategory.REGULATORY, RoleCategory.ENERGY): 0.9,
            # ... more mappings
        }

        return relevance.get((category, role), 0.5)  # Default 0.5
```

## Testing Requirements

### Unit Tests
- Category determination from text
- Keyword matching logic
- Category validation
- Role-based relevance calculation

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] FindingClassifier categorizes findings correctly
- [ ] Category keywords drive classification
- [ ] AI categories validated
- [ ] Role-based relevance calculated
- [ ] Default category assigned when ambiguous

## Deliverables

- `src/elile/risk/finding_classifier.py`
- `tests/unit/test_finding_classifier.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - Finding Categories

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
