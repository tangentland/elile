# Task 7.6: Result Compiler

## Overview

Implement result compiler that aggregates SAR results, findings, risk assessments, and connections into comprehensive screening results.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 5.9: SAR Loop Orchestrator
- Task 6.7: Risk Aggregator

## Implementation

```python
# src/elile/screening/result_compiler.py
class ResultCompiler:
    """Compiles screening results."""

    def compile_results(
        self,
        sar_results: dict[InformationType, SARTypeState],
        risk_assessment: ComprehensiveRiskAssessment,
        connections: list[EntityConnection]
    ) -> ScreeningResult:
        """Compile complete screening results."""

        return ScreeningResult(
            findings_summary=self._compile_findings_summary(sar_results),
            risk_score=risk_assessment.final_score,
            risk_level=risk_assessment.risk_level,
            recommendation=risk_assessment.recommendation,
            connections=connections,
            sar_summary=self._compile_sar_summary(sar_results),
            completed_at=datetime.now(timezone.utc)
        )

    def _compile_findings_summary(
        self,
        sar_results: dict
    ) -> FindingsSummary:
        """Aggregate findings across types."""
        pass
```

## Acceptance Criteria

- [ ] Compiles SAR results from all types
- [ ] Aggregates findings summaries
- [ ] Includes risk assessment
- [ ] Formats for report generation

## Deliverables

- `src/elile/screening/result_compiler.py`
- `tests/unit/test_result_compiler.py`

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
