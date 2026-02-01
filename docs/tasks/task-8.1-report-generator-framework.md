# Task 8.1: Report Generator Framework

## Overview

Implement report generator framework that provides unified interface for generating persona-specific reports with template system, field filtering, and output format support.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 7.6: Result Compiler
- Task 6.7: Risk Aggregator

## Implementation

```python
# src/elile/reporting/report_generator.py
class ReportGenerator:
    """Framework for generating persona-specific reports."""

    def __init__(self, template_registry: TemplateRegistry):
        self.templates = template_registry

    async def generate_report(
        self,
        screening_result: ScreeningResult,
        persona: ReportPersona,
        format: OutputFormat,
        ctx: RequestContext
    ) -> GeneratedReport:
        """Generate report for persona."""

        # Get template for persona
        template = self.templates.get_template(persona)

        # Apply field filtering
        filtered_data = self._apply_field_filter(
            screening_result, template.visible_fields
        )

        # Apply redaction
        redacted_data = self._apply_redaction(
            filtered_data, template.redacted_fields
        )

        # Render report
        if format == OutputFormat.PDF:
            content = await self._render_pdf(redacted_data, template)
        elif format == OutputFormat.JSON:
            content = self._render_json(redacted_data)
        else:
            content = await self._render_html(redacted_data, template)

        return GeneratedReport(
            report_id=uuid4(),
            persona=persona,
            format=format,
            content=content,
            generated_at=datetime.now(timezone.utc)
        )

    def _apply_field_filter(self, data, visible_fields):
        """Filter data to visible fields."""
        pass

    def _apply_redaction(self, data, redacted_fields):
        """Redact sensitive fields."""
        pass
```

## Acceptance Criteria

- [ ] Generates persona-specific reports
- [ ] Applies field visibility rules
- [ ] Redacts sensitive data per template
- [ ] Supports PDF, JSON, HTML formats
- [ ] Template-driven generation

## Deliverables

- `src/elile/reporting/report_generator.py`
- `src/elile/reporting/templates.py`
- `tests/unit/test_report_generator.py`

## References

- Architecture: [08-reporting.md](../../docs/architecture/08-reporting.md)

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
