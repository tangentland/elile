"""Report Generator Framework for persona-specific reports.

This module provides the ReportGenerator that:
1. Generates reports for different personas from compiled screening results
2. Applies field visibility and redaction rules per template
3. Supports multiple output formats (PDF, JSON, HTML)
4. Handles compliance disclosures and legal notices

Architecture Reference: docs/architecture/08-reporting.md
"""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from elile.core.context import RequestContext, get_current_context
from elile.core.logging import get_logger
from elile.reporting.template_definitions import ReportTemplate, TemplateRegistry, create_template_registry
from elile.reporting.types import (
    GeneratedReport,
    GeneratedReportMetadata,
    OutputFormat,
    RedactionLevel,
    RenderingError,
    ReportContent,
    ReportPersona,
    ReportSection,
)
from elile.screening.result_compiler import CompiledResult

logger = get_logger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class GeneratorConfig(BaseModel):
    """Configuration for the ReportGenerator."""

    # Output settings
    default_format: OutputFormat = Field(
        default=OutputFormat.PDF, description="Default output format"
    )
    default_redaction: RedactionLevel = Field(
        default=RedactionLevel.STANDARD, description="Default redaction level"
    )

    # Access control
    access_expiry_hours: int = Field(
        default=24, ge=1, le=168, description="Hours until report access expires"
    )
    require_context: bool = Field(default=True, description="Require RequestContext for generation")

    # Content settings
    max_findings_per_category: int = Field(
        default=10, ge=1, le=100, description="Max findings to include per category"
    )
    max_key_findings: int = Field(default=5, ge=1, le=20, description="Max key findings to include")
    include_metadata: bool = Field(default=True, description="Include metadata in JSON output")

    # Rendering settings
    enable_pdf: bool = Field(default=True, description="Enable PDF generation")
    enable_html: bool = Field(default=True, description="Enable HTML generation")


# =============================================================================
# Report Generator
# =============================================================================


class ReportGenerator:
    """Framework for generating persona-specific reports.

    The ReportGenerator transforms compiled screening results into
    persona-appropriate reports with proper field visibility,
    redaction, and formatting.

    Example:
        ```python
        # Create generator with template registry
        registry = TemplateRegistry()
        generator = ReportGenerator(template_registry=registry)

        # Generate HR summary report
        report = await generator.generate_report(
            compiled_result=compiled,
            persona=ReportPersona.HR_MANAGER,
            output_format=OutputFormat.PDF,
            screening_id=screening_id,
        )

        # Access report content
        print(f"Report ID: {report.report_id}")
        print(f"Size: {report.metadata.size_bytes} bytes")
        ```

    Attributes:
        templates: Template registry for persona templates.
        config: Generator configuration.
    """

    def __init__(
        self,
        template_registry: TemplateRegistry | None = None,
        config: GeneratorConfig | None = None,
    ) -> None:
        """Initialize the report generator.

        Args:
            template_registry: Template registry. Creates default if not provided.
            config: Generator configuration.
        """
        self.templates = template_registry or create_template_registry()
        self.config = config or GeneratorConfig()

    async def generate_report(
        self,
        compiled_result: CompiledResult,
        persona: ReportPersona,
        output_format: OutputFormat | None = None,
        screening_id: UUID | None = None,
        redaction_level: RedactionLevel | None = None,
        ctx: RequestContext | None = None,
    ) -> GeneratedReport:
        """Generate a report for a specific persona.

        Args:
            compiled_result: The compiled screening result.
            persona: Report persona (determines content visibility).
            output_format: Output format. Uses default from config if not specified.
            screening_id: Screening ID for metadata.
            redaction_level: Redaction level. Uses default from config if not specified.
            ctx: Request context. Gets current context if not provided.

        Returns:
            GeneratedReport with content and metadata.

        Raises:
            TemplateNotFoundError: If no template exists for the persona.
            RenderingError: If rendering fails.
        """
        output_format = output_format or self.config.default_format
        redaction_level = redaction_level or self.config.default_redaction

        # Get context if required
        if self.config.require_context:
            ctx = ctx or get_current_context()

        logger.info(
            "Generating report",
            persona=persona.value,
            format=output_format.value,
            screening_id=str(screening_id) if screening_id else None,
        )

        # Get template for persona
        template = self.templates.get_template(persona)

        # Convert compiled result to dictionary for processing
        data = compiled_result.to_dict()

        # Apply field filtering
        filtered_data = self._apply_field_filter(data, template)

        # Apply redaction
        redacted_data = self._apply_redaction(filtered_data, template, redaction_level)

        # Build section contents
        sections = self._build_sections(redacted_data, template, compiled_result)

        # Render report content
        if output_format == OutputFormat.PDF:
            content = await self._render_pdf(redacted_data, template, sections)
        elif output_format == OutputFormat.JSON:
            content = self._render_json(redacted_data, template, sections)
        else:
            content = await self._render_html(redacted_data, template, sections)

        # Calculate checksum
        checksum = hashlib.sha256(content).hexdigest()

        # Build metadata
        metadata = GeneratedReportMetadata(
            screening_id=screening_id or compiled_result.screening_id,
            entity_id=compiled_result.entity_id,
            tenant_id=compiled_result.tenant_id,
            persona=persona,
            output_format=output_format,
            generated_by=str(ctx.actor_id) if ctx else "system",
            template_version=template.version,
            redaction_level=redaction_level,
            sections_included=template.sections,
            checksum=checksum,
            size_bytes=len(content),
            access_expiry=datetime.now(UTC) + timedelta(hours=self.config.access_expiry_hours),
        )

        report = GeneratedReport(
            metadata=metadata,
            content=content,
            sections=sections,
        )

        logger.info(
            "Report generated",
            report_id=str(report.report_id),
            persona=persona.value,
            size_bytes=len(content),
        )

        return report

    async def generate_reports(
        self,
        compiled_result: CompiledResult,
        personas: list[ReportPersona],
        output_format: OutputFormat | None = None,
        screening_id: UUID | None = None,
        ctx: RequestContext | None = None,
    ) -> list[GeneratedReport]:
        """Generate reports for multiple personas.

        Args:
            compiled_result: The compiled screening result.
            personas: List of personas to generate reports for.
            output_format: Output format for all reports.
            screening_id: Screening ID for metadata.
            ctx: Request context.

        Returns:
            List of generated reports.
        """
        reports = []
        for persona in personas:
            report = await self.generate_report(
                compiled_result=compiled_result,
                persona=persona,
                output_format=output_format,
                screening_id=screening_id,
                ctx=ctx,
            )
            reports.append(report)
        return reports

    def _apply_field_filter(self, data: dict[str, Any], template: ReportTemplate) -> dict[str, Any]:
        """Filter data to only include visible fields.

        Args:
            data: The full data dictionary.
            template: The report template with visibility rules.

        Returns:
            Filtered data dictionary.
        """
        # For investigator persona with "*" wildcard, return all data
        if "*" in template.visible_fields:
            return deepcopy(data)

        filtered: dict[str, Any] = {}

        for field_path in template.visible_fields:
            self._copy_field(data, filtered, field_path)

        # Also copy fields from field_rules if visible
        for field_path, rule in template.field_rules.items():
            if rule.visible:
                self._copy_field(data, filtered, field_path, max_items=rule.max_items)

        return filtered

    def _copy_field(
        self,
        source: dict[str, Any],
        dest: dict[str, Any],
        field_path: str,
        max_items: int | None = None,
    ) -> None:
        """Copy a field from source to dest, creating nested dicts as needed.

        Args:
            source: Source dictionary.
            dest: Destination dictionary.
            field_path: Dot-separated field path.
            max_items: Maximum items to copy for lists.
        """
        parts = field_path.split(".")
        src = source
        dst = dest

        # Navigate to the parent in source and create path in dest
        for part in parts[:-1]:
            if part not in src or not isinstance(src[part], dict):
                return  # Source doesn't have this field or it's not a dict
            src = src[part]
            if part not in dst:
                dst[part] = {}
            dst = dst[part]

        # Copy the final value
        final_key = parts[-1]
        if src is not None and isinstance(src, dict) and final_key in src:
            value = src[final_key]
            if max_items is not None and isinstance(value, list):
                value = value[:max_items]
            dst[final_key] = deepcopy(value)

    def _apply_redaction(
        self,
        data: dict[str, Any],
        template: ReportTemplate,
        redaction_level: RedactionLevel,
    ) -> dict[str, Any]:
        """Apply redaction to sensitive fields.

        Args:
            data: The data dictionary to redact.
            template: The report template with redaction rules.
            redaction_level: Level of redaction to apply.

        Returns:
            Redacted data dictionary.
        """
        if redaction_level == RedactionLevel.NONE:
            return data

        redacted = deepcopy(data)

        # Apply template redaction rules
        for field_path in template.redacted_fields:
            self._redact_field(redacted, field_path, redaction_level)

        # Apply field_rules redaction
        for field_path, rule in template.field_rules.items():
            if rule.redacted:
                self._redact_field(redacted, field_path, redaction_level)

        # Apply standard PII redaction based on level
        if redaction_level in (RedactionLevel.STANDARD, RedactionLevel.STRICT):
            pii_fields = [
                "subject.ssn",
                "subject.drivers_license",
                "subject.passport_number",
                "subject.date_of_birth",
            ]
            for field_path in pii_fields:
                self._redact_field(redacted, field_path, redaction_level)

        # GDPR strict redaction
        if redaction_level == RedactionLevel.STRICT:
            gdpr_fields = [
                "subject.phone",
                "subject.email",
                "subject.full_address",
            ]
            for field_path in gdpr_fields:
                self._redact_field(redacted, field_path, redaction_level)

        return redacted

    def _redact_field(self, data: dict[str, Any], field_path: str, level: RedactionLevel) -> None:
        """Redact a single field in the data dictionary.

        Args:
            data: The data dictionary (modified in place).
            field_path: Dot-separated field path.
            level: Redaction level.
        """
        parts = field_path.split(".")
        obj = data

        # Navigate to the parent
        for part in parts[:-1]:
            if part not in obj or not isinstance(obj[part], dict):
                return
            obj = obj[part]

        # Redact the final value
        final_key = parts[-1]
        if final_key not in obj:
            return

        value = obj[final_key]
        if value is None:
            return

        # Apply redaction based on field type and level
        if isinstance(value, str):
            if "ssn" in field_path.lower():
                # Show last 4 digits for SSN at minimal level
                if level == RedactionLevel.MINIMAL and len(value) >= 4:
                    obj[final_key] = f"***-**-{value[-4:]}"
                else:
                    obj[final_key] = "[REDACTED]"
            elif "email" in field_path.lower():
                # Redact email but preserve domain
                if "@" in value and level == RedactionLevel.MINIMAL:
                    domain = value.split("@")[1]
                    obj[final_key] = f"***@{domain}"
                else:
                    obj[final_key] = "[REDACTED]"
            else:
                obj[final_key] = "[REDACTED]"
        elif isinstance(value, (int, float)):
            obj[final_key] = 0
        elif isinstance(value, list):
            obj[final_key] = []
        elif isinstance(value, dict):
            obj[final_key] = {}

    def _build_sections(
        self,
        data: dict[str, Any],
        template: ReportTemplate,
        compiled_result: CompiledResult,
    ) -> list[ReportContent]:
        """Build report sections from data and template.

        Args:
            data: The filtered and redacted data.
            template: The report template.
            compiled_result: Original compiled result for additional data.

        Returns:
            List of ReportContent sections.
        """
        sections = []

        for section in template.sections:
            content = self._build_section_content(section, data, template, compiled_result)
            if content:
                sections.append(content)

        return sections

    def _build_section_content(
        self,
        section: ReportSection,
        data: dict[str, Any],
        template: ReportTemplate,
        _compiled_result: CompiledResult,
    ) -> ReportContent | None:
        """Build content for a single section.

        Args:
            section: The section type.
            data: The filtered and redacted data.
            template: The report template.
            _compiled_result: Original compiled result (for future extensions).
            compiled_result: Original compiled result.

        Returns:
            ReportContent or None if section should be skipped.
        """
        section_data: dict[str, Any] = {}
        title = self._get_section_title(section)

        if section == ReportSection.HEADER:
            section_data = {
                "persona": template.persona.value,
                "template_name": template.name,
                "template_version": template.version,
                "generated_at": datetime.now(UTC).isoformat(),
            }

        elif section == ReportSection.EXECUTIVE_SUMMARY:
            section_data = {
                "risk_score": data.get("risk_score", 0),
                "risk_level": data.get("risk_level", "unknown"),
                "recommendation": data.get("recommendation", "unknown"),
                "recommendation_reasons": data.get("recommendation_reasons", []),
                "narrative": data.get("findings_summary", {}).get("overall_narrative", ""),
            }

        elif section == ReportSection.RISK_ASSESSMENT:
            section_data = {
                "risk_score": data.get("risk_score", 0),
                "risk_level": data.get("risk_level", "unknown"),
                "recommendation": data.get("recommendation", "unknown"),
                "risk_assessment": data.get("risk_assessment", {}),
            }

        elif section == ReportSection.KEY_FINDINGS:
            findings_summary = data.get("findings_summary", {})
            section_data = {
                "total_findings": findings_summary.get("total_findings", 0),
                "critical_findings": findings_summary.get("critical_findings", []),
                "high_findings": findings_summary.get("high_findings", []),
            }

        elif section == ReportSection.CATEGORY_BREAKDOWN:
            findings_summary = data.get("findings_summary", {})
            section_data = {
                "by_category": findings_summary.get("by_category", {}),
                "by_severity": findings_summary.get("by_severity", {}),
            }

        elif section == ReportSection.DETAILED_FINDINGS:
            findings_summary = data.get("findings_summary", {})
            section_data = {
                "total_findings": findings_summary.get("total_findings", 0),
                "by_category": findings_summary.get("by_category", {}),
                "verification_status": findings_summary.get("verification_status", "unknown"),
            }

        elif section == ReportSection.CONNECTION_NETWORK:
            connection_summary = data.get("connection_summary", {})
            section_data = {
                "entities_discovered": connection_summary.get("entities_discovered", 0),
                "d2_entities": connection_summary.get("d2_entities", 0),
                "d3_entities": connection_summary.get("d3_entities", 0),
                "relations_mapped": connection_summary.get("relations_mapped", 0),
            }

        elif section == ReportSection.RISK_CONNECTIONS:
            connection_summary = data.get("connection_summary", {})
            section_data = {
                "risk_connections": connection_summary.get("risk_connections", 0),
                "critical_connections": connection_summary.get("critical_connections", 0),
                "high_risk_connections": connection_summary.get("high_risk_connections", 0),
                "pep_connections": connection_summary.get("pep_connections", 0),
                "sanctions_connections": connection_summary.get("sanctions_connections", 0),
                "key_risks": connection_summary.get("key_risks", []),
            }

        elif section == ReportSection.DATA_SOURCES:
            investigation_summary = data.get("investigation_summary", {})
            section_data = {
                "types_processed": investigation_summary.get("types_processed", 0),
                "total_queries": investigation_summary.get("total_queries", 0),
                "by_type": investigation_summary.get("by_type", {}),
            }

        elif section == ReportSection.AUDIT_TRAIL:
            investigation_summary = data.get("investigation_summary", {})
            section_data = {
                "types_processed": investigation_summary.get("types_processed", 0),
                "types_completed": investigation_summary.get("types_completed", 0),
                "types_failed": investigation_summary.get("types_failed", 0),
                "total_queries": investigation_summary.get("total_queries", 0),
            }

        elif section == ReportSection.CONSENT_VERIFICATION:
            section_data = {
                "consent_verified": True,  # Would be populated from screening context
                "consent_timestamp": datetime.now(UTC).isoformat(),
            }

        elif section == ReportSection.COMPLIANCE_ATTESTATION:
            section_data = {
                "compliance_verified": True,
                "rules_applied": [],  # Would be populated from compliance engine
            }

        elif section == ReportSection.CONSUMER_RIGHTS:
            section_data = {
                "disclosures": [d.value for d in template.required_disclosures],
                "fcra_rights": self._get_fcra_rights_text(),
            }

        elif section == ReportSection.DISPUTE_PROCESS:
            section_data = {
                "dispute_instructions": self._get_dispute_instructions_text(),
            }

        elif section == ReportSection.RECOMMENDATIONS:
            section_data = {
                "recommendation": data.get("recommendation", "unknown"),
                "recommendation_reasons": data.get("recommendation_reasons", []),
            }

        elif section == ReportSection.FOOTER:
            section_data = {
                "legal_notices": template.legal_notices,
                "generated_at": datetime.now(UTC).isoformat(),
            }

        else:
            # Generic section with direct data mapping
            section_data = {"section_type": section.value}

        return ReportContent(
            section=section,
            title=title,
            data=section_data,
            template_key=f"{template.persona.value}_{section.value}",
            visible=True,
        )

    def _get_section_title(self, section: ReportSection) -> str:
        """Get human-readable title for a section."""
        titles = {
            ReportSection.HEADER: "Report Header",
            ReportSection.EXECUTIVE_SUMMARY: "Executive Summary",
            ReportSection.RISK_ASSESSMENT: "Risk Assessment",
            ReportSection.KEY_FINDINGS: "Key Findings",
            ReportSection.CATEGORY_BREAKDOWN: "Category Breakdown",
            ReportSection.DETAILED_FINDINGS: "Detailed Findings",
            ReportSection.IDENTITY_VERIFICATION: "Identity Verification",
            ReportSection.EMPLOYMENT_HISTORY: "Employment History",
            ReportSection.EDUCATION_HISTORY: "Education History",
            ReportSection.CRIMINAL_RECORDS: "Criminal Records",
            ReportSection.CIVIL_RECORDS: "Civil Records",
            ReportSection.FINANCIAL_RECORDS: "Financial Records",
            ReportSection.REGULATORY_RECORDS: "Regulatory Records",
            ReportSection.CONNECTION_NETWORK: "Connection Network",
            ReportSection.RISK_CONNECTIONS: "Risk Connections",
            ReportSection.CONSENT_VERIFICATION: "Consent Verification",
            ReportSection.COMPLIANCE_ATTESTATION: "Compliance Attestation",
            ReportSection.DATA_SOURCES: "Data Sources",
            ReportSection.AUDIT_TRAIL: "Audit Trail",
            ReportSection.CHECKS_PERFORMED: "Checks Performed",
            ReportSection.CONSUMER_RIGHTS: "Consumer Rights",
            ReportSection.DISPUTE_PROCESS: "Dispute Process",
            ReportSection.ADVERSE_ACTION_NOTICE: "Adverse Action Notice",
            ReportSection.PORTFOLIO_METRICS: "Portfolio Metrics",
            ReportSection.RISK_DISTRIBUTION: "Risk Distribution",
            ReportSection.TREND_ANALYSIS: "Trend Analysis",
            ReportSection.COST_ANALYSIS: "Cost Analysis",
            ReportSection.FOOTER: "Footer",
            ReportSection.RECOMMENDATIONS: "Recommendations",
        }
        return titles.get(section, section.value.replace("_", " ").title())

    async def _render_pdf(
        self,
        data: dict[str, Any],
        template: ReportTemplate,
        sections: list[ReportContent],
    ) -> bytes:
        """Render report as PDF.

        Args:
            data: The report data.
            template: The report template.
            sections: The report sections.

        Returns:
            PDF content as bytes.

        Raises:
            RenderingError: If PDF rendering fails.
        """
        if not self.config.enable_pdf:
            raise RenderingError(OutputFormat.PDF, "PDF rendering is disabled")

        # For now, return a placeholder PDF structure
        # Actual PDF rendering will be implemented in Task 8.6
        try:
            # Create a minimal PDF-like structure
            # This will be replaced with actual PDF generation
            pdf_header = b"%PDF-1.4\n"
            pdf_content = self._create_pdf_placeholder(data, template, sections)
            pdf_trailer = b"\n%%EOF"
            return pdf_header + pdf_content + pdf_trailer
        except Exception as e:
            raise RenderingError(OutputFormat.PDF, str(e)) from e

    def _create_pdf_placeholder(
        self,
        data: dict[str, Any],
        template: ReportTemplate,
        sections: list[ReportContent],
    ) -> bytes:
        """Create placeholder PDF content.

        This is a minimal implementation that will be replaced
        by proper PDF rendering in Task 8.6.
        """
        content_lines = [
            f"% Report: {template.name}",
            f"% Persona: {template.persona.value}",
            f"% Sections: {len(sections)}",
            f"% Risk Score: {data.get('risk_score', 0)}",
        ]
        return "\n".join(content_lines).encode("utf-8")

    def _render_json(
        self,
        data: dict[str, Any],
        template: ReportTemplate,
        sections: list[ReportContent],
    ) -> bytes:
        """Render report as JSON.

        Args:
            data: The report data.
            template: The report template.
            sections: The report sections.

        Returns:
            JSON content as bytes.
        """
        output: dict[str, Any] = {
            "template": {
                "persona": template.persona.value,
                "name": template.name,
                "version": template.version,
            },
            "sections": [s.to_dict() for s in sections],
        }

        if self.config.include_metadata:
            output["data"] = data

        return json.dumps(output, indent=2, default=str).encode("utf-8")

    async def _render_html(
        self,
        _data: dict[str, Any],
        template: ReportTemplate,
        sections: list[ReportContent],
    ) -> bytes:
        """Render report as HTML.

        Args:
            _data: The report data (for future extensions).
            template: The report template.
            sections: The report sections.

        Returns:
            HTML content as bytes.

        Raises:
            RenderingError: If HTML rendering fails.
        """
        if not self.config.enable_html:
            raise RenderingError(OutputFormat.HTML, "HTML rendering is disabled")

        try:
            html_parts = [
                "<!DOCTYPE html>",
                "<html>",
                "<head>",
                f"<title>{template.name}</title>",
                "<style>",
                self._get_default_css(template),
                "</style>",
                "</head>",
                "<body>",
                f"<h1>{template.name}</h1>",
            ]

            for section in sections:
                html_parts.append(self._render_section_html(section))

            html_parts.extend(["</body>", "</html>"])
            return "\n".join(html_parts).encode("utf-8")
        except Exception as e:
            raise RenderingError(OutputFormat.HTML, str(e)) from e

    def _get_default_css(self, template: ReportTemplate) -> str:
        """Get default CSS for HTML reports."""
        branding = template.branding
        return f"""
            body {{ font-family: {branding.font_family}, sans-serif; margin: 40px; }}
            h1 {{ color: {branding.primary_color}; }}
            h2 {{ color: {branding.secondary_color}; border-bottom: 1px solid #eee; }}
            .section {{ margin-bottom: 30px; }}
            .risk-score {{ font-size: 24px; font-weight: bold; }}
            .risk-low {{ color: #22c55e; }}
            .risk-moderate {{ color: #f59e0b; }}
            .risk-high {{ color: #f97316; }}
            .risk-critical {{ color: #ef4444; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f3f4f6; }}
        """

    def _render_section_html(self, section: ReportContent) -> str:
        """Render a single section as HTML."""
        html = f'<div class="section" id="{section.section.value}">'
        html += f"<h2>{section.title}</h2>"

        # Simple data rendering
        data = section.data
        if data:
            html += "<dl>"
            for key, value in data.items():
                if isinstance(value, list):
                    html += f"<dt>{key}</dt><dd>{', '.join(str(v) for v in value)}</dd>"
                elif isinstance(value, dict):
                    html += f"<dt>{key}</dt><dd><pre>{json.dumps(value, indent=2)}</pre></dd>"
                else:
                    html += f"<dt>{key}</dt><dd>{value}</dd>"
            html += "</dl>"

        html += "</div>"
        return html

    def _get_fcra_rights_text(self) -> str:
        """Get standard FCRA consumer rights text."""
        return """A Summary of Your Rights Under the Fair Credit Reporting Act

The federal Fair Credit Reporting Act (FCRA) promotes the accuracy, fairness, and privacy
of information in the files of consumer reporting agencies. There are many types of consumer
reporting agencies, including credit bureaus and specialty agencies (such as agencies that
sell information about check writing histories, medical records, and rental history records).

You have the right to:
- Know what is in your file
- Ask for your credit score
- Dispute incomplete or inaccurate information
- Have consumer reporting agencies correct or delete inaccurate information
- Have outdated information not be reported
- Limit prescreened offers of credit
- Seek damages from violators"""

    def _get_dispute_instructions_text(self) -> str:
        """Get dispute process instructions text."""
        return """How to Dispute Information

If you believe any information in this report is inaccurate or incomplete, you have
the right to dispute it. To file a dispute:

1. Contact the consumer reporting agency in writing
2. Identify the specific information you are disputing
3. Explain why you believe the information is inaccurate
4. Provide supporting documentation

The consumer reporting agency must investigate your dispute within 30 days and
provide you with the results of their investigation."""


# =============================================================================
# Factory Functions
# =============================================================================


def create_report_generator(
    template_registry: TemplateRegistry | None = None,
    config: GeneratorConfig | None = None,
) -> ReportGenerator:
    """Factory function to create a report generator.

    Args:
        template_registry: Optional custom template registry.
        config: Optional generator configuration.

    Returns:
        Configured ReportGenerator instance.
    """
    return ReportGenerator(template_registry=template_registry, config=config)
