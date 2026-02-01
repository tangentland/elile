# Task 6.3: Severity Calculator

## Overview

Implemented the SeverityCalculator for determining finding severity levels using rule-based assessment with role and recency adjustments.

## Requirements Met

1. **Rule-Based Matching** - Pattern matching against finding text
2. **Subcategory Defaults** - Default severity by subcategory
3. **Role Adjustment** - Severity boost for role-relevant findings
4. **Recency Adjustment** - Severity boost for recent findings
5. **Audit Trail** - SeverityDecision for decision tracking
6. **AI Protocol** - Protocol for future AI-assisted assessment
7. **Batch Processing** - Process multiple findings efficiently

## Files Created

### Source Files

| File | Purpose |
|------|---------|
| `src/elile/risk/severity_calculator.py` | SeverityCalculator and related models |
| `src/elile/risk/__init__.py` | Updated exports |

### Test Files

| File | Tests |
|------|-------|
| `tests/unit/test_severity_calculator.py` | 52 unit tests |

## Key Components

### SeverityCalculator

Main calculator class for determining finding severity:
- `calculate_severity()` - Calculate severity for a single finding
- `calculate_severities()` - Batch processing with optional finding update
- `_match_rules()` - Pattern matching against SEVERITY_RULES
- `_get_subcategory_severity()` - Look up subcategory default
- `_get_role_adjustment()` - Calculate role-based adjustment
- `_get_recency_adjustment()` - Calculate recency-based adjustment
- `_adjust_severity()` - Apply adjustment with capping

### SeverityDecision Dataclass

Complete decision record for audit trail:
- decision_id: UUIDv7 identifier
- finding_id: Associated finding
- initial_severity: Before adjustments
- final_severity: After adjustments
- determination_method: rule/subcategory/ai/default
- matched_rules: Patterns that matched
- role_adjustment: Applied role adjustment
- recency_adjustment: Applied recency adjustment
- context_notes: Human-readable notes
- decided_at: Decision timestamp

### CalculatorConfig

Configuration options:
- `use_rule_matching` - Enable pattern matching
- `use_subcategory_defaults` - Use subcategory defaults as fallback
- `use_ai_fallback` - Enable AI for ambiguous cases
- `enable_role_adjustment` - Apply role-based adjustments
- `enable_recency_adjustment` - Apply recency boosts
- `recent_boost_days` - Days for "recent" classification (default: 365)
- `recency_boost_amount` - Levels to boost (default: 1)
- `default_severity` - Fallback severity (default: MEDIUM)

### SEVERITY_RULES

50+ patterns mapped to severity levels:

| Severity | Example Patterns |
|----------|-----------------|
| CRITICAL | felony conviction, active warrant, sex offense, ofac sanction, pep designation |
| HIGH | recent bankruptcy, dui conviction, finra bar, deception detected |
| MEDIUM | misdemeanor conviction, civil judgment, employment discrepancy |
| LOW | employment gap, address discrepancy, parking violation |

### SUBCATEGORY_SEVERITY

Maps all 34 SubCategory values to default severity:

| Subcategory | Default Severity |
|-------------|-----------------|
| CRIMINAL_FELONY | CRITICAL |
| CRIMINAL_DUI | HIGH |
| CRIMINAL_MISDEMEANOR | MEDIUM |
| CRIMINAL_TRAFFIC | LOW |

### ROLE_SEVERITY_ADJUSTMENTS

Role-based severity adjustments:

| Finding Category | Role | Adjustment |
|-----------------|------|------------|
| CRIMINAL | GOVERNMENT | +1 |
| CRIMINAL | SECURITY | +1 |
| CRIMINAL | EDUCATION | +1 |
| FINANCIAL | FINANCIAL | +1 |
| FINANCIAL | EXECUTIVE | +1 |
| REGULATORY | FINANCIAL | +1 |
| REGULATORY | HEALTHCARE | +1 |
| VERIFICATION | GOVERNMENT | +1 |
| VERIFICATION | SECURITY | +1 |

## Key Patterns

### Calculate Severity

```python
calculator = SeverityCalculator()

severity, decision = calculator.calculate_severity(
    finding=finding,
    role_category=RoleCategory.FINANCIAL,
    subcategory=SubCategory.CRIMINAL_FELONY,
)

print(f"Severity: {severity}")
print(f"Method: {decision.determination_method}")
print(f"Adjustments: {decision.role_adjustment + decision.recency_adjustment}")
```

### Determination Priority

1. Rule matching (pattern in finding text)
2. Subcategory default (if no rule matches)
3. Config default (if no subcategory provided)

### Adjustment Flow

```
Initial Severity (from rules/subcategory/default)
    ↓
Apply Role Adjustment (+1 for relevant category+role)
    ↓
Apply Recency Adjustment (+1 for recent findings)
    ↓
Cap at CRITICAL max, LOW min
    ↓
Final Severity
```

### Batch Processing

```python
results = calculator.calculate_severities(
    findings=findings,
    role_category=RoleCategory.GOVERNMENT,
    subcategories={f.finding_id: subcategory for f in findings},
    update_findings=True,  # Sets finding.severity
)

for severity, decision in results:
    print(f"{decision.finding_id}: {severity.value}")
```

## Test Results

```
======================== 52 passed, 2 warnings in 1.00s ========================
```

### Test Coverage

| Test Category | Tests |
|---------------|-------|
| Initialization | 4 |
| CalculatorConfig | 2 |
| Rule Matching | 13 |
| Subcategory Defaults | 4 |
| Default Severity | 2 |
| Role Adjustment | 6 |
| Recency Adjustment | 4 |
| Combined Adjustments | 2 |
| Batch Processing | 4 |
| SeverityDecision | 2 |
| Constants | 3 |
| Edge Cases | 6 |

## Dependencies

- Task 6.1 (Finding Classifier) - SubCategory enum
- Task 5.10 (Finding Extractor) - Finding, Severity, FindingCategory
- Task 2.1 (Compliance Types) - RoleCategory

## Next Task

Task 6.4: Anomaly Detector - Detect anomalous patterns in findings and behaviors.
