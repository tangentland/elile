# Task 9.3: Delta Detector - Implementation Plan

## Overview

Implemented delta detector that compares current monitoring results against baseline, identifying new findings, changed findings, resolved findings, risk score changes, and connection changes.

**Priority**: P0 | **Status**: Complete | **Completed**: 2026-02-02

## Dependencies

- Task 3.5: Profile Delta Calculator (data models)
- Task 9.1: Monitoring Scheduler (integration point)

## Implementation Summary

### Files Created

1. **`src/elile/monitoring/delta_detector.py`** - Main delta detector module
   - `DeltaType` enum - Types of detected changes (new/resolved/severity changes)
   - `FindingChange` dataclass - Details of a changed finding
   - `ConnectionChange` dataclass - Details of a changed connection
   - `RiskScoreChange` dataclass - Details of risk score changes
   - `DeltaResult` dataclass - Complete delta detection result
   - `DetectorConfig` Pydantic model - Configuration for detection
   - `DeltaDetector` class - Main detection logic
   - `create_delta_detector()` factory function

2. **`tests/unit/test_delta_detector.py`** - Comprehensive unit tests (50 tests)

### Files Modified

1. **`src/elile/monitoring/__init__.py`** - Added exports for delta detector

## Key Features

### Finding Comparison
- Detects new findings (in current but not baseline)
- Detects resolved findings (in baseline but not current)
- Detects severity changes (increased/decreased)
- Optional detail change tracking

### Risk Score Comparison
- Tracks overall score changes
- Detects risk level changes (escalation/de-escalation)
- Tracks per-category score changes
- Configurable significance threshold

### Connection Comparison (D2/D3)
- Detects new connections
- Detects lost connections
- Tracks connection risk changes
- Configurable risk change threshold

### Escalation Detection
- New critical findings trigger escalation
- Risk level increase triggers escalation
- Severity increase to critical triggers escalation
- Configurable escalation rules

### Review Requirement Detection
- Escalation always requires review
- New high/critical findings require review
- Significant risk increases require review
- Configurable review thresholds

### ProfileDelta Generation
- Generates ProfileDelta objects for alerting
- Maps severity levels appropriately
- Includes metadata for tracking
- Human-readable summaries

## Configuration Options

```python
DetectorConfig(
    risk_score_threshold=5,           # Min score change to report
    risk_level_change_is_escalation=True,
    new_critical_finding_is_escalation=True,
    new_high_finding_requires_review=True,
    track_detail_changes=False,       # Track finding detail changes
    compare_connections=True,         # Include connection comparison
    connection_risk_threshold=0.2,    # Min connection risk change
)
```

## Usage Example

```python
from elile.monitoring import DeltaDetector, create_delta_detector
from elile.investigation.finding_extractor import Finding
from elile.risk.risk_scorer import RiskScore

detector = create_delta_detector()

result = detector.detect_deltas(
    baseline_findings=baseline_findings,
    current_findings=current_findings,
    baseline_risk_score=baseline_risk,
    current_risk_score=current_risk,
    baseline_connections=baseline_connections,
    current_connections=current_connections,
    entity_id=entity_id,
)

if result.has_escalation:
    # Handle escalation
    pass

for delta in result.deltas:
    # Process ProfileDelta for alerting
    pass
```

## Test Coverage

50 unit tests covering:
- Basic detector creation and configuration
- Finding comparison (all change types)
- Risk score comparison
- Connection comparison
- Escalation detection
- Review requirement detection
- ProfileDelta generation
- Data class serialization
- Configuration validation
- Integration scenarios

## Integration Points

The DeltaDetector is designed to be used by:
- MonitoringScheduler's `_perform_delta_detection` method
- Alert Generator (Task 9.4) - uses ProfileDelta objects
- V1/V2/V3 schedulers for periodic monitoring checks

## Key Patterns Used

- Factory function for easy instantiation
- Pydantic for configuration validation
- Dataclasses for result objects with serialization
- Configurable behavior through DetectorConfig
- Comprehensive type hints

## Acceptance Criteria Met

- [x] Detects new findings
- [x] Detects changed findings (severity)
- [x] Detects resolved findings
- [x] Compares risk scores
- [x] Identifies escalations
- [x] Generates ProfileDelta objects for alerting
- [x] Comprehensive test coverage (50 tests)

---

*Completed: 2026-02-02*
