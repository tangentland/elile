# Task 8.3: Audit Report (Compliance Officer)

## Overview

Implement Compliance Officer audit report template with consent verification, compliance rules, data sources, audit trail, and data handling attestation.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 8.1: Report Generator Framework
- Task 1.2: Audit Logging

## Implementation

```python
# src/elile/reporting/templates/compliance_audit.py
class ComplianceAuditTemplate(ReportTemplate):
    """Compliance Officer audit report."""

    persona = ReportPersona.COMPLIANCE

    visible_fields = [
        "consent_verification",
        "compliance_rules_applied",
        "data_sources_accessed",
        "audit_trail",
        "data_handling_compliance"
    ]

    def render(self, data: ScreeningResult) -> dict:
        """Render compliance audit report."""
        return {
            "consent": self._render_consent(data.consent_reference),
            "compliance": self._render_compliance_checks(data.compliance_results),
            "data_sources": self._render_data_sources(data.providers_used),
            "audit_trail": self._render_audit_trail(data.audit_events),
            "attestation": self._generate_attestation(data)
        }

    def _render_audit_trail(self, events):
        """Render key audit events."""
        pass
```

## Acceptance Criteria

- [ ] Consent verification displayed
- [ ] Compliance rules documented
- [ ] Data sources with timestamps/costs
- [ ] Audit trail of key events
- [ ] Data handling attestation

## Deliverables

- `src/elile/reporting/templates/compliance_audit.py`
- `tests/unit/test_compliance_audit_template.py`

## References

- Architecture: [08-reporting.md](../../docs/architecture/08-reporting.md) - Audit Report

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
