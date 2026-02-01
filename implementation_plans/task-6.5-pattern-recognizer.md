# Task 6.5: Pattern Recognizer

## Overview

Implemented the PatternRecognizer for identifying behavioral patterns, trends, and risk signals across findings using temporal analysis and pattern matching.

## Requirements Met

1. **Escalation Patterns** - Detect increasing severity/frequency over time
2. **Frequency Patterns** - Identify bursts and recurring issues
3. **Cross-Domain Patterns** - Recognize multi-category and systemic issues
4. **Temporal Patterns** - Analyze timeline clustering and recent concentration
5. **Behavioral Patterns** - Detect repeat offenders and degradation trends

## Files Created

### Source Files

| File | Purpose |
|------|---------|
| `src/elile/risk/pattern_recognizer.py` | PatternRecognizer and related models |
| `src/elile/risk/__init__.py` | Updated exports |

### Test Files

| File | Tests |
|------|-------|
| `tests/unit/test_pattern_recognizer.py` | 36 unit tests |

## Key Components

### PatternRecognizer

Main recognizer class for identifying patterns:
- `recognize_patterns()` - Detect all pattern types
- `summarize_patterns()` - Create summary with risk assessment
- `_detect_escalation_patterns()` - Severity/frequency escalation
- `_detect_frequency_patterns()` - Burst activity, recurring issues
- `_detect_cross_domain_patterns()` - Multi-category, systemic
- `_detect_temporal_patterns()` - Clustering, recent concentration
- `_detect_behavioral_patterns()` - Repeat offender, degradation

### PatternType Enum

15 pattern types across categories:
- Escalation: SEVERITY_ESCALATION, FREQUENCY_ESCALATION
- Frequency: BURST_ACTIVITY, RECURRING_ISSUES, PERIODIC_PATTERN
- Cross-Domain: MULTI_CATEGORY, SYSTEMIC_ISSUES, CORRELATED_FINDINGS
- Temporal: TIMELINE_CLUSTER, DORMANT_PERIOD, RECENT_CONCENTRATION
- Behavioral: REPEAT_OFFENDER, PROGRESSIVE_DEGRADATION, IMPROVEMENT_TREND

### Pattern Dataclass

Complete pattern record:
- pattern_id: UUIDv7 identifier
- pattern_type: Type classification
- severity: LOW/MEDIUM/HIGH/CRITICAL
- confidence: Detection confidence (0.0-1.0)
- description: Human-readable description
- evidence: Supporting evidence list
- affected_categories: Categories involved
- time_span: Duration of pattern
- start_date/end_date: Date range

### PatternSummary Dataclass

Overall pattern analysis:
- total_patterns: Count of detected patterns
- patterns_by_type: Distribution by type
- highest_severity: Most severe pattern
- risk_score: Calculated risk (0.0-1.0)
- key_concerns: Top concerns identified

### RecognizerConfig

Configuration options:
- `escalation_window_days` - Window for escalation (default: 365)
- `burst_window_days` - Window for burst detection (default: 90)
- `burst_threshold` - Findings for burst (default: 3)
- `recurring_threshold` - Same type for recurring (default: 2)
- `min_categories_for_multi` - Categories for multi-domain (default: 3)
- `recent_days` - Days considered recent (default: 180)

## Key Patterns

### Recognize Patterns

```python
recognizer = PatternRecognizer()

patterns = recognizer.recognize_patterns(findings)

for pattern in patterns:
    print(f"{pattern.pattern_type.value}: {pattern.description}")
    print(f"  Severity: {pattern.severity.value}")
    print(f"  Confidence: {pattern.confidence:.2f}")
```

### Summarize Patterns

```python
summary = recognizer.summarize_patterns(patterns, findings)

print(f"Total patterns: {summary.total_patterns}")
print(f"Risk score: {summary.risk_score:.2f}")
print(f"Key concerns: {summary.key_concerns}")
```

### Detection Pipeline

```
Input: Findings (with dates, categories, severities)
    ↓
Escalation Detection (severity increase, frequency increase)
    ↓
Frequency Detection (burst activity, recurring issues)
    ↓
Cross-Domain Detection (multi-category, systemic)
    ↓
Temporal Detection (clustering, recent concentration)
    ↓
Behavioral Detection (repeat offender, degradation)
    ↓
Filter by min_confidence
    ↓
Output: List[Pattern]
```

## Test Results

```
======================== 36 passed, 2 warnings in 0.42s ========================
```

### Test Coverage

| Test Category | Tests |
|---------------|-------|
| Initialization | 4 |
| RecognizerConfig | 2 |
| Pattern Model | 2 |
| PatternSummary Model | 2 |
| Escalation Patterns | 4 |
| Frequency Patterns | 3 |
| Cross-Domain Patterns | 3 |
| Temporal Patterns | 2 |
| Behavioral Patterns | 3 |
| Full Pipeline | 3 |
| Summary | 2 |
| Constants | 2 |
| Edge Cases | 4 |

## Dependencies

- Task 6.1 (Finding Classifier) - FindingCategory
- Task 6.4 (Anomaly Detector) - Complements anomaly detection

## Next Task

Task 6.6: Connection Analyzer - Analyze network connections and risk propagation.
