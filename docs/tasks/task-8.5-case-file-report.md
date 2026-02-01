# Task 8.5: Case File Report Generator

**Priority**: P1
**Phase**: 8 - Reporting Engine
**Estimated Effort**: 3 days
**Dependencies**: Task 8.1 (Report Generation)

## Context

Generate comprehensive case file reports for investigators with all findings, raw data, evidence chain, and investigation narrative.

## Objectives

1. Include all investigation data
2. Maintain evidence chain
3. Support multi-format export
4. Add investigator annotations
5. Enable report versioning

## Technical Approach

```python
# src/elile/reporting/generators/case_file.py
class CaseFileReportGenerator:
    def generate(self, screening: Screening) -> CaseFileReport:
        return CaseFileReport(
            findings=all_findings,
            raw_data=raw_sources,
            evidence_chain=chain,
            investigation_narrative=narrative,
            timeline=timeline
        )
```

## Implementation Checklist

- [ ] Generate case file reports
- [ ] Add evidence tracking
- [ ] Test completeness

## Success Criteria

- [ ] All data included
- [ ] Chain of custody maintained
