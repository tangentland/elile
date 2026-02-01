# Task 7.6: Result Compiler - Implementation Plan

## Overview

The Result Compiler aggregates screening results from multiple sources (SAR loop, findings, risk assessment, network connections) into comprehensive summaries suitable for report generation and API responses.

## Requirements

From `docs/tasks/task-7.6-result-compiler.md`:
- Compile SAR results across all information types
- Aggregate findings by category and severity
- Include risk assessment and recommendations
- Build connection summaries from D2/D3 analysis
- Format data for report generation
- Support configurable summary formats

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/screening/result_compiler.py` | Main ResultCompiler implementation |
| `tests/unit/test_result_compiler.py` | Comprehensive unit tests (49 tests) |

## Key Classes

### ResultCompiler

Main compiler that orchestrates result aggregation:
- `compile_results()` - Aggregates all inputs into CompiledResult
- `_compile_findings_summary()` - Aggregates findings by category/severity
- `_compile_investigation_summary()` - Summarizes SAR loop execution
- `_compile_connection_summary()` - Summarizes network analysis
- `_generate_findings_narrative()` - Creates human-readable narrative
- `to_screening_result()` - Converts to ScreeningResult for API

### Data Models

| Model | Purpose |
|-------|---------|
| `CompiledResult` | Complete compiled screening result |
| `FindingsSummary` | Aggregated findings with category breakdowns |
| `CategorySummary` | Per-category metrics and key findings |
| `InvestigationSummary` | SAR loop execution statistics |
| `SARSummary` | Per-information-type SAR summary |
| `ConnectionSummary` | D2/D3 network analysis summary |

### Configuration

`CompilerConfig` supports:
- `summary_format` - Brief/Standard/Detailed
- `max_key_findings` - Max findings per category
- `max_critical_findings` - Max critical findings in summary
- `include_narrative` - Toggle narrative generation
- `min_finding_confidence` - Confidence threshold for filtering

## Key Patterns Used

### Category Mapping

Maps InformationType to FindingCategory for aggregation:
```python
INFO_TYPE_TO_CATEGORY: dict[InformationType, FindingCategory] = {
    InformationType.CRIMINAL: FindingCategory.CRIMINAL,
    InformationType.FINANCIAL: FindingCategory.FINANCIAL,
    InformationType.IDENTITY: FindingCategory.VERIFICATION,
    # etc.
}
```

### Findings Aggregation

1. Filter by minimum confidence
2. Group by category
3. Count by severity within each category
4. Extract key findings (sorted by severity)
5. Track corroboration and sources

### Risk Level Determination

From connection analysis:
- Count D2 vs D3 entities
- Track PEP, sanctions, shell company connections
- Determine highest risk level
- Calculate propagation score

## Test Results

```
======================== 49 passed, 2 warnings in 1.46s ========================
```

Test coverage includes:
- Basic compilation scenarios
- Findings summary generation
- Investigation summary generation
- Connection summary generation
- Screening result conversion
- Data model serialization
- Edge cases (empty inputs, missing data)
- Configuration options

## Dependencies Used

### From Investigation Module
- `SARTypeState`, `CompletionReason` - SAR loop results
- `Finding`, `FindingCategory`, `Severity` - Finding types
- `DiscoveredEntity`, `EntityRelation`, `RiskConnection` - Network types

### From Risk Module
- `ComprehensiveRiskAssessment` - Risk assessment results

### From Screening Module
- `ScreeningResult`, `ScreeningStatus` - Output types

## Integration Points

### Upstream
- Receives `SARTypeState` from SAR orchestrator
- Receives `Finding` list from finding extractor
- Receives `ComprehensiveRiskAssessment` from risk aggregator
- Receives `DiscoveredEntity`, `EntityRelation`, `RiskConnection` from network phase

### Downstream
- Outputs `CompiledResult` with all summaries
- Converts to `ScreeningResult` for API responses
- Used by report generators (Phase 8)

## Module Exports

Added to `src/elile/screening/__init__.py`:
```python
from elile.screening.result_compiler import (
    CategorySummary,
    CompiledResult,
    CompilerConfig,
    ConnectionSummary,
    FindingsSummary,
    InvestigationSummary,
    ResultCompiler,
    SARSummary,
    SummaryFormat,
    create_result_compiler,
)
```

## Notes

- Narrative generation can be disabled for performance
- Findings are filtered by configurable confidence threshold
- Connection summary requires `connections` list to process `risk_connections`
- All summary models support `to_dict()` for serialization
