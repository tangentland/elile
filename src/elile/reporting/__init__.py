"""Reporting module for generating persona-specific reports.

This module provides the report generation framework that:
1. Generates persona-specific reports (HR, Compliance, Security, etc.)
2. Applies field visibility and redaction rules per template
3. Supports multiple output formats (PDF, JSON, HTML)
4. Handles compliance disclosures and legal notices

Architecture Reference: docs/architecture/08-reporting.md

Example:
    ```python
    from elile.reporting import (
        ReportGenerator,
        TemplateRegistry,
        ReportPersona,
        OutputFormat,
        create_report_generator,
    )

    # Create generator
    generator = create_report_generator()

    # Generate HR summary report
    report = await generator.generate_report(
        compiled_result=compiled,
        persona=ReportPersona.HR_MANAGER,
        output_format=OutputFormat.PDF,
    )

    # Access report content
    print(f"Report ID: {report.report_id}")
    print(f"Size: {report.metadata.size_bytes} bytes")
    ```
"""

from elile.reporting.report_generator import (
    GeneratorConfig,
    ReportGenerator,
    create_report_generator,
)
from elile.reporting.template_definitions import (
    ReportTemplate,
    TemplateRegistry,
    create_template_registry,
)
from elile.reporting.types import (
    BrandingConfig,
    DisclosureType,
    FieldRule,
    GeneratedReport,
    GeneratedReportMetadata,
    InvalidRedactionError,
    LayoutConfig,
    OutputFormat,
    RedactionLevel,
    RenderingError,
    ReportContent,
    ReportGenerationError,
    ReportPersona,
    ReportRequest,
    ReportSection,
    TemplateNotFoundError,
)

__all__ = [
    # Main classes
    "ReportGenerator",
    "ReportTemplate",
    "TemplateRegistry",
    # Configuration
    "GeneratorConfig",
    "BrandingConfig",
    "LayoutConfig",
    # Data models
    "GeneratedReport",
    "GeneratedReportMetadata",
    "ReportContent",
    "ReportRequest",
    "FieldRule",
    # Enums
    "ReportPersona",
    "OutputFormat",
    "RedactionLevel",
    "ReportSection",
    "DisclosureType",
    # Errors
    "ReportGenerationError",
    "TemplateNotFoundError",
    "InvalidRedactionError",
    "RenderingError",
    # Factory functions
    "create_report_generator",
    "create_template_registry",
]
