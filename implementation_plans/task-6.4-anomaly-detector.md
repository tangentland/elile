# Task 6.4: Anomaly Detector

## Overview

Implemented the AnomalyDetector for identifying unusual patterns, inconsistencies, and deception indicators in subject data using statistical and pattern-based analysis.

## Requirements Met

1. **Statistical Anomaly Detection** - Detect outliers and improbable values
2. **Inconsistency Pattern Detection** - Identify systematic patterns
3. **Timeline Anomaly Detection** - Flag impossibilities and gaps
4. **Credential Inflation Detection** - Detect education/title inflation
5. **Deception Assessment** - Calculate overall deception likelihood

## Files Created

### Source Files

| File | Purpose |
|------|---------|
| `src/elile/risk/anomaly_detector.py` | AnomalyDetector and related models |
| `src/elile/risk/__init__.py` | Updated exports |

### Test Files

| File | Tests |
|------|-------|
| `tests/unit/test_anomaly_detector.py` | 44 unit tests |

## Key Components

### AnomalyDetector

Main detector class for identifying anomalies:
- `detect_anomalies()` - Detect all anomaly types
- `assess_deception()` - Calculate deception likelihood
- `_detect_statistical_anomalies()` - Outliers and frequency
- `_detect_inconsistency_patterns()` - Systematic patterns
- `_detect_timeline_anomalies()` - Impossible dates
- `_detect_credential_anomalies()` - Inflation
- `_detect_deception_indicators()` - Fabrication, concealment

### AnomalyType Enum

18 anomaly types across categories:
- Statistical: STATISTICAL_OUTLIER, UNUSUAL_FREQUENCY, IMPROBABLE_VALUE
- Inconsistency: SYSTEMATIC_INCONSISTENCIES, CROSS_FIELD_PATTERN, DIRECTIONAL_BIAS
- Timeline: TIMELINE_IMPOSSIBLE, CHRONOLOGICAL_GAP, OVERLAPPING_PERIODS
- Credential: CREDENTIAL_INFLATION, EXPERIENCE_INFLATION, QUALIFICATION_GAP
- Deception: DECEPTION_PATTERN, CONCEALMENT_ATTEMPT, FABRICATION_INDICATOR
- Behavioral: UNUSUAL_PATTERN, SUSPICIOUS_ACTIVITY

### Anomaly Dataclass

Complete anomaly record:
- anomaly_id: UUIDv7 identifier
- anomaly_type: Type classification
- severity: LOW/MEDIUM/HIGH/CRITICAL
- confidence: Detection confidence (0.0-1.0)
- description: Human-readable description
- evidence: Supporting evidence list
- affected_fields: Fields involved
- deception_score: Deception likelihood (0.0-1.0)

### DeceptionAssessment Dataclass

Overall deception assessment:
- overall_score: Combined deception score
- risk_level: none/low/moderate/high/critical
- contributing_factors: Factors raising score
- pattern_modifiers: Pattern-based adjustments
- anomaly_count: Total anomalies
- inconsistency_count: Total inconsistencies

### DetectorConfig

Configuration options:
- `systematic_threshold` - Inconsistencies for systematic pattern (default: 4)
- `deception_warning_threshold` - Score for warning (default: 0.5)
- `deception_critical_threshold` - Score for critical (default: 0.75)
- `detect_statistical` - Enable statistical detection
- `detect_timeline` - Enable timeline detection
- `detect_credential` - Enable credential detection
- `detect_deception` - Enable deception scoring
- `min_confidence` - Minimum anomaly confidence (default: 0.3)

## Key Patterns

### Detect Anomalies

```python
detector = AnomalyDetector()

anomalies = detector.detect_anomalies(
    facts=facts,
    inconsistencies=inconsistencies,
)

for anomaly in anomalies:
    print(f"{anomaly.anomaly_type.value}: {anomaly.description}")
    print(f"  Severity: {anomaly.severity.value}")
    print(f"  Deception: {anomaly.deception_score:.2f}")
```

### Assess Deception

```python
assessment = detector.assess_deception(anomalies, inconsistencies)

print(f"Risk Level: {assessment.risk_level}")
print(f"Score: {assessment.overall_score:.2f}")
print(f"Factors: {', '.join(assessment.contributing_factors)}")
```

### Detection Pipeline

```
Input: Facts + Inconsistencies
    ↓
Statistical Analysis (outliers, frequency)
    ↓
Inconsistency Patterns (systematic, cross-field, bias)
    ↓
Timeline Analysis (impossible, overlaps)
    ↓
Credential Analysis (inflation)
    ↓
Deception Indicators (fabrication, concealment)
    ↓
Filter by min_confidence
    ↓
Output: List[Anomaly]
```

### Deception Scoring

```
Base score from inconsistencies (type-weighted)
    +
Anomaly severity contribution
    ×
Pattern modifiers:
  - Directional bias: ×1.2
  - Cross-domain: ×1.15
  - Systematic: ×1.25
    ↓
Risk level classification
```

## Test Results

```
======================== 44 passed, 2 warnings in 1.11s ========================
```

### Test Coverage

| Test Category | Tests |
|---------------|-------|
| Initialization | 4 |
| DetectorConfig | 2 |
| Anomaly Model | 2 |
| DeceptionAssessment Model | 2 |
| Statistical Detection | 4 |
| Inconsistency Patterns | 4 |
| Timeline Detection | 2 |
| Credential Detection | 2 |
| Deception Indicators | 3 |
| Full Pipeline | 4 |
| Deception Assessment | 5 |
| Helper Methods | 3 |
| Constants | 3 |
| Edge Cases | 4 |

## Dependencies

- Task 5.4 (Result Assessor) - Fact, DetectedInconsistency
- Task 6.1 (Finding Classifier) - Category context

## Next Task

Task 6.5: Pattern Recognizer - Recognize risk patterns across investigations.
