# Task 6.3: Severity Calculator

## Overview

Implement severity calculator that determines finding severity (LOW/MEDIUM/HIGH/CRITICAL) based on type, impact, and context using rule-based and AI-assisted assessment.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 6.1: Finding Classifier
- Task 3.9: AI Model Adapter

## Implementation Checklist

- [ ] Create SeverityCalculator with rule engine
- [ ] Implement severity rules per finding type
- [ ] Build AI-assisted severity assessment
- [ ] Add context-based adjustments
- [ ] Create severity audit trail

## Key Implementation

```python
# src/elile/risk/severity_calculator.py
class SeverityCalculator:
    """Calculates finding severity."""

    SEVERITY_RULES = {
        "felony_conviction": Severity.CRITICAL,
        "active_warrant": Severity.CRITICAL,
        "recent_bankruptcy": Severity.HIGH,
        "license_revocation": Severity.HIGH,
        "misdemeanor_conviction": Severity.MEDIUM,
        "civil_judgment": Severity.MEDIUM,
        "employment_gap": Severity.LOW
    }

    def calculate_severity(
        self,
        finding: Finding,
        context: dict
    ) -> Severity:
        """Calculate severity from rules and AI."""

        # Check rule-based severity
        for pattern, severity in self.SEVERITY_RULES.items():
            if pattern in finding.summary.lower():
                return severity

        # Fallback to AI assessment
        return self._ai_assess_severity(finding, context)

    def _ai_assess_severity(self, finding: Finding, context: dict) -> Severity:
        """Use AI to assess severity."""
        # AI implementation
        pass
```

## Acceptance Criteria

- [ ] Severity rules cover common finding types
- [ ] AI fallback for ambiguous cases
- [ ] Context adjusts severity assessment
- [ ] Audit trail for severity decisions

## Deliverables

- `src/elile/risk/severity_calculator.py`
- `tests/unit/test_severity_calculator.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md)

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
