# Implementation Plan: Task 8.2 - Summary Report (HR Manager)

## Overview

Task 8.2 implements the HR Summary report content builder, which transforms compiled screening results into user-friendly summaries suitable for HR decision-making.

## Requirements

- Risk assessment visualization with score bar (0-100)
- Pass/Flag/Fail indicators for each check category
- Category breakdown with severity-based scoring
- Recommended actions based on findings
- Human-readable narrative summary
- Configurable thresholds and display options

## Files Created/Modified

### Created
- `src/elile/reporting/templates/__init__.py` - Package exports
- `src/elile/reporting/templates/hr_summary.py` - HRSummaryBuilder class
- `tests/unit/test_hr_summary_template.py` - 55 unit tests

### Modified
- `src/elile/reporting/templates.py` -> `src/elile/reporting/template_definitions.py` (renamed)
- `src/elile/reporting/__init__.py` - Updated import path
- `src/elile/reporting/report_generator.py` - Updated import path

## Key Components

### HRSummaryBuilder
Main builder class that transforms CompiledResult into HRSummaryContent.

### Data Models
- **RiskAssessmentDisplay**: Visual risk score with bar and recommendation text
- **FindingIndicator**: Pass/Flag/Fail status for each check type
- **CategoryScore**: Detailed scoring per category
- **RecommendedAction**: Prioritized action items
- **HRSummaryContent**: Complete report content aggregation

### Status Determination
Categories are assigned status based on configurable thresholds:
- CLEAR: Score >= 75
- REVIEW: Score >= 50 (< 75)
- FLAG: Score >= 25 (< 50)
- FAIL: Score < 25

### Score Calculation
```
deductions = critical_count * 30 + high_count * 20 + medium_count * 10 + low_count * 3
if corroborated and critical: deductions += 10
score = max(0, 100 - deductions)
```

## Test Coverage

- 55 unit tests organized into 13 test classes
- Factory function tests
- Minimal, moderate, and high risk scenario tests
- Key findings and category breakdown tests
- Recommended actions and narrative tests
- Connection summary handling tests
- Edge case and configuration tests

## Patterns Used

- Builder pattern for content assembly
- Factory function for instance creation
- Dataclasses with to_dict() serialization
- Pydantic config for validation

## Dependencies

- Task 8.1: Report Generator Framework (templates, types)
- Phase 7: Screening result compiler (CompiledResult)
- Phase 6: Risk analysis types (RiskLevel, Severity)

## Test Results

All 55 tests pass. Full test suite passes (2318 tests).
