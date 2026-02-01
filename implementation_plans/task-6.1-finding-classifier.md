# Task 6.1: Finding Classifier

## Overview

Implemented the FindingClassifier for categorizing investigation findings into risk categories with role-based relevance scoring. This enables consistent categorization of findings for risk analysis.

## Requirements Met

1. **Category Classification** - Categorize findings into 7 primary categories (criminal, financial, regulatory, reputation, verification, behavioral, network)
2. **Sub-category Classification** - Assign granular sub-categories (34 types) for detailed analysis
3. **AI Validation** - Validate AI-assigned categories against keyword rules
4. **Reclassification** - Automatically reclassify when AI confidence is below threshold
5. **Role Relevance** - Calculate role-specific relevance scores using ROLE_RELEVANCE_MATRIX
6. **Batch Processing** - Classify multiple findings efficiently

## Files Created

### Source Files

| File | Purpose |
|------|---------|
| `src/elile/risk/finding_classifier.py` | FindingClassifier and related models |
| `src/elile/risk/__init__.py` | Updated exports |

### Test Files

| File | Tests |
|------|-------|
| `tests/unit/test_finding_classifier.py` | 72 unit tests |

## Key Components

### FindingClassifier

Main classifier class for categorizing findings:
- `classify_finding()` - Classify a single finding
- `classify_findings()` - Batch classification
- `get_category_distribution()` - Count findings by category
- `get_subcategory_distribution()` - Count findings by sub-category

### SubCategory Enum

34 sub-categories organized by parent category:
- **Criminal** (8): felony, misdemeanor, traffic, dui, violent, financial, drug, sex
- **Financial** (6): bankruptcy, lien, judgment, foreclosure, collection, credit
- **Regulatory** (5): license, sanction, enforcement, bar, pep
- **Reputation** (4): litigation, media, complaint, social
- **Verification** (5): identity, employment, education, discrepancy, gap
- **Behavioral** (2): pattern, deception
- **Network** (3): association, shell, pep
- **Default** (1): unclassified

### ClassificationResult

Result dataclass capturing:
- classification_id: UUIDv7 identifier
- original_category: AI-assigned category (if any)
- assigned_category: Final category after validation
- sub_category: Granular sub-category
- category_confidence: Confidence score (0.0-1.0)
- relevance_to_role: Role-specific relevance (0.0-1.0)
- keyword_matches: Keywords that matched
- was_reclassified: Whether category was changed

### ClassifierConfig

Configuration options:
- `min_validation_confidence`: Threshold to keep AI category (default: 0.7)
- `min_keyword_matches`: Min matches for category (default: 1)
- `confidence_per_match`: Confidence boost per keyword (default: 0.15)
- `max_keyword_confidence`: Maximum from keywords alone (default: 0.9)
- `enable_subcategory`: Enable sub-category detection (default: True)
- `default_relevance`: Default role relevance (default: 0.5)

### ROLE_RELEVANCE_MATRIX

Complete coverage of all (FindingCategory, RoleCategory) pairs:
- Criminal: Government/Security = 1.0, Standard = 0.7
- Financial: Financial = 1.0, Standard = 0.5
- Regulatory: Financial/Healthcare = 1.0, Standard = 0.5
- Reputation: Executive = 1.0, Standard = 0.5
- Verification: Government/Security/Financial/Executive = 1.0, Standard = 0.8
- Behavioral: Government/Security = 1.0, Standard = 0.7
- Network: Government/Security = 1.0, Standard = 0.5

## Key Patterns

### Classify Single Finding

```python
classifier = FindingClassifier()

result = classifier.classify_finding(
    finding=finding,
    role_category=RoleCategory.FINANCIAL,
)
print(f"Category: {result.assigned_category}")
print(f"Sub-category: {result.sub_category}")
print(f"Relevance: {result.relevance_to_role}")
```

### AI Category Validation

```python
# Finding with AI-assigned category
finding = Finding(
    summary="Felony conviction for theft",
    category=FindingCategory.CRIMINAL,  # AI-assigned
)

result = classifier.classify_finding(finding, RoleCategory.GOVERNMENT)

# If enough keywords match, keeps AI category
# If not enough matches, reclassifies based on keywords
print(f"Reclassified: {result.was_reclassified}")
```

### Batch Classification

```python
findings = [finding1, finding2, finding3]
results = classifier.classify_findings(findings, RoleCategory.EXECUTIVE)

# Get distribution
distribution = classifier.get_category_distribution(results)
# {CRIMINAL: 2, FINANCIAL: 1}
```

## Test Results

```
======================== 72 passed, 2 warnings in 0.64s ========================
```

### Test Coverage

| Test Category | Tests |
|---------------|-------|
| Initialization | 4 |
| ClassifierConfig | 4 |
| Category Determination | 9 |
| AI Category Validation | 5 |
| Sub-category Classification | 13 |
| Role Relevance | 10 |
| Batch Classification | 4 |
| Distribution | 3 |
| ClassificationResult | 3 |
| Keyword Constants | 3 |
| Edge Cases | 6 |
| SubCategory Enum | 8 |

## Changes to Existing Code

### Finding Class Update

Made `Finding.category` optional (None default) to support unclassified findings:
- Changed `category: FindingCategory = FindingCategory.VERIFICATION` to `category: FindingCategory | None = None`
- Updated `to_dict()` to handle None category

This allows the classifier to distinguish between:
- AI-classified findings (category is set)
- Unclassified findings (category is None)

## Dependencies

- Task 5.10 (Finding Extractor) - Finding and FindingCategory models

## Next Task

Task 6.2: Risk Scorer - Implement risk scoring algorithms based on classified findings.
