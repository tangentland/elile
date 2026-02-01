# Task 8.4: Investigation Report (Security Team)

## Overview

Implement Security Team investigation report template with threat assessment, connection network, detailed findings, and evolution signals.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 8.1: Report Generator Framework
- Task 6.6: Connection Analyzer

## Implementation

```python
# src/elile/reporting/templates/security_investigation.py
class SecurityInvestigationTemplate(ReportTemplate):
    """Security Team investigation report."""

    persona = ReportPersona.SECURITY

    visible_fields = [
        "threat_assessment",
        "connection_network",
        "detailed_findings",
        "evolution_signals",
        "risk_propagation"
    ]

    def render(self, data: ScreeningResult) -> dict:
        """Render security investigation report."""
        return {
            "threat_assessment": self._render_threat_assessment(data),
            "network": self._render_connection_network(data.connections),
            "findings": self._render_detailed_findings(data.findings),
            "evolution": self._render_evolution_signals(data.evolution_signals)
        }

    def _render_connection_network(self, connections):
        """Render network graph with risk propagation."""
        pass
```

## Acceptance Criteria

- [ ] Insider threat score displayed
- [ ] Connection network visualized
- [ ] Detailed findings with confidence
- [ ] Evolution signals tracked
- [ ] Risk propagation analyzed

## Deliverables

- `src/elile/reporting/templates/security_investigation.py`
- `tests/unit/test_security_investigation_template.py`

## References

- Architecture: [08-reporting.md](../../docs/architecture/08-reporting.md) - Investigation Report

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
