# Task 8.2: Summary Report (HR Manager)

## Overview

Implement HR Manager summary report template with risk assessment, category breakdown, key findings, and recommended actions in user-friendly format.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 8.1: Report Generator Framework

## Implementation

```python
# src/elile/reporting/templates/hr_summary.py
class HRSummaryTemplate(ReportTemplate):
    """HR Manager summary report template."""

    persona = ReportPersona.HR_MANAGER

    visible_fields = [
        "overall_risk_score",
        "risk_level",
        "recommendation",
        "category_breakdown",
        "key_findings_summary",
        "recommended_actions"
    ]

    redacted_fields = [
        "raw_provider_data",
        "specific_financial_amounts",
        "connection_details",
        "source_identifiers"
    ]

    def render(self, data: ScreeningResult) -> dict:
        """Render HR summary report."""
        return {
            "overall_assessment": {
                "score": data.risk_score,
                "level": data.risk_level,
                "recommendation": data.recommendation
            },
            "key_findings": self._summarize_findings(data.findings),
            "category_breakdown": self._render_categories(data.category_scores),
            "recommended_actions": self._generate_actions(data)
        }

    def _summarize_findings(self, findings):
        """Create pass/flag/fail summary."""
        pass
```

## Acceptance Criteria

- [ ] High-level risk assessment displayed
- [ ] Category breakdown with scores
- [ ] Pass/Flag/Fail indicators
- [ ] Recommended actions generated
- [ ] User-friendly formatting

## Deliverables

- `src/elile/reporting/templates/hr_summary.py`
- `tests/unit/test_hr_summary_template.py`

## References

- Architecture: [08-reporting.md](../../docs/architecture/08-reporting.md) - HR Summary

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
