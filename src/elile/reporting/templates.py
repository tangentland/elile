"""Report templates and template registry.

This module defines the ReportTemplate structure and TemplateRegistry
for managing persona-specific report templates.

Architecture Reference: docs/architecture/08-reporting.md
"""

from dataclasses import dataclass, field
from typing import Any

from elile.reporting.types import (
    BrandingConfig,
    DisclosureType,
    FieldRule,
    LayoutConfig,
    ReportPersona,
    ReportSection,
    TemplateNotFoundError,
)

# =============================================================================
# Report Template
# =============================================================================


@dataclass
class ReportTemplate:
    """Template defining how to generate a report for a specific persona.

    Attributes:
        persona: The persona this template is for.
        name: Human-readable template name.
        version: Template version string.
        sections: Sections to include in order.
        visible_fields: Field paths that should be visible.
        redacted_fields: Field paths that should be redacted.
        aggregated_fields: Field paths that should be aggregated.
        required_disclosures: Compliance disclosures to include.
        legal_notices: Legal notice text to include.
        branding: Default branding configuration.
        layout: Default layout configuration.
        field_rules: Detailed field rules (overrides simple lists).
    """

    persona: ReportPersona
    name: str
    version: str = "1.0.0"
    sections: list[ReportSection] = field(default_factory=list)
    visible_fields: list[str] = field(default_factory=list)
    redacted_fields: list[str] = field(default_factory=list)
    aggregated_fields: list[str] = field(default_factory=list)
    required_disclosures: list[DisclosureType] = field(default_factory=list)
    legal_notices: list[str] = field(default_factory=list)
    branding: BrandingConfig = field(default_factory=BrandingConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    field_rules: dict[str, FieldRule] = field(default_factory=dict)

    def is_field_visible(self, field_path: str) -> bool:
        """Check if a field is visible in this template.

        Args:
            field_path: Dot-separated path to the field.

        Returns:
            True if field should be visible.
        """
        if field_path in self.field_rules:
            return self.field_rules[field_path].visible
        return field_path in self.visible_fields

    def is_field_redacted(self, field_path: str) -> bool:
        """Check if a field should be redacted.

        Args:
            field_path: Dot-separated path to the field.

        Returns:
            True if field should be redacted.
        """
        if field_path in self.field_rules:
            return self.field_rules[field_path].redacted
        return field_path in self.redacted_fields

    def is_field_aggregated(self, field_path: str) -> bool:
        """Check if a field should be aggregated.

        Args:
            field_path: Dot-separated path to the field.

        Returns:
            True if field should be aggregated.
        """
        if field_path in self.field_rules:
            return self.field_rules[field_path].aggregated
        return field_path in self.aggregated_fields

    def get_max_items(self, field_path: str) -> int | None:
        """Get the max items limit for a list field.

        Args:
            field_path: Dot-separated path to the field.

        Returns:
            Max items limit or None for no limit.
        """
        if field_path in self.field_rules:
            return self.field_rules[field_path].max_items
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "persona": self.persona.value,
            "name": self.name,
            "version": self.version,
            "sections": [s.value for s in self.sections],
            "visible_fields": self.visible_fields,
            "redacted_fields": self.redacted_fields,
            "aggregated_fields": self.aggregated_fields,
            "required_disclosures": [d.value for d in self.required_disclosures],
            "legal_notices": self.legal_notices,
            "branding": self.branding.model_dump(),
            "layout": self.layout.model_dump(),
            "field_rules": {k: v.to_dict() for k, v in self.field_rules.items()},
        }


# =============================================================================
# Default Templates
# =============================================================================


def _create_hr_manager_template() -> ReportTemplate:
    """Create default template for HR Manager persona."""
    return ReportTemplate(
        persona=ReportPersona.HR_MANAGER,
        name="HR Summary Report",
        sections=[
            ReportSection.HEADER,
            ReportSection.EXECUTIVE_SUMMARY,
            ReportSection.RISK_ASSESSMENT,
            ReportSection.KEY_FINDINGS,
            ReportSection.CATEGORY_BREAKDOWN,
            ReportSection.RECOMMENDATIONS,
            ReportSection.FOOTER,
        ],
        visible_fields=[
            "risk_score",
            "risk_level",
            "recommendation",
            "recommendation_reasons",
            "findings_summary.total_findings",
            "findings_summary.by_category",
            "findings_summary.by_severity",
            "findings_summary.overall_narrative",
            "findings_summary.verification_status",
            "investigation_summary.types_processed",
            "investigation_summary.types_completed",
            "investigation_summary.average_confidence",
            "connection_summary.highest_risk_level",
        ],
        redacted_fields=[
            "subject.ssn",
            "subject.drivers_license",
            "subject.passport_number",
            "findings_summary.raw_data",
            "connection_summary.entity_details",
        ],
        aggregated_fields=[
            "findings_summary.by_category",
            "findings_summary.by_severity",
            "connection_summary.risk_connections",
        ],
        required_disclosures=[],
        legal_notices=["This report is confidential and intended for authorized personnel only."],
        field_rules={
            "findings_summary.critical_findings": FieldRule(
                field_path="findings_summary.critical_findings",
                visible=True,
                max_items=5,
            ),
            "findings_summary.high_findings": FieldRule(
                field_path="findings_summary.high_findings",
                visible=True,
                max_items=5,
            ),
        },
    )


def _create_compliance_template() -> ReportTemplate:
    """Create default template for Compliance Officer persona."""
    return ReportTemplate(
        persona=ReportPersona.COMPLIANCE,
        name="Compliance Audit Report",
        sections=[
            ReportSection.HEADER,
            ReportSection.EXECUTIVE_SUMMARY,
            ReportSection.CONSENT_VERIFICATION,
            ReportSection.COMPLIANCE_ATTESTATION,
            ReportSection.DATA_SOURCES,
            ReportSection.AUDIT_TRAIL,
            ReportSection.CATEGORY_BREAKDOWN,
            ReportSection.FOOTER,
        ],
        visible_fields=[
            "risk_score",
            "risk_level",
            "recommendation",
            "recommendation_reasons",
            "findings_summary.total_findings",
            "findings_summary.by_category",
            "findings_summary.by_severity",
            "findings_summary.data_completeness",
            "findings_summary.verification_status",
            "investigation_summary.types_processed",
            "investigation_summary.types_completed",
            "investigation_summary.types_failed",
            "investigation_summary.types_skipped",
            "investigation_summary.total_queries",
            "investigation_summary.by_type",
            "cost_summary.total_cost",
            "cost_summary.cost_by_provider",
            "consent_token",
            "compliance_rules_applied",
            "data_sources_accessed",
            "audit_events",
        ],
        redacted_fields=[
            "subject.ssn",
            "subject.drivers_license",
            "findings_summary.raw_data",
        ],
        aggregated_fields=[],
        required_disclosures=[],
        legal_notices=[
            "This audit report documents compliance with applicable regulations.",
            "Retain per data retention policy requirements.",
        ],
    )


def _create_security_template() -> ReportTemplate:
    """Create default template for Security Team persona."""
    return ReportTemplate(
        persona=ReportPersona.SECURITY,
        name="Security Investigation Report",
        sections=[
            ReportSection.HEADER,
            ReportSection.EXECUTIVE_SUMMARY,
            ReportSection.RISK_ASSESSMENT,
            ReportSection.DETAILED_FINDINGS,
            ReportSection.CONNECTION_NETWORK,
            ReportSection.RISK_CONNECTIONS,
            ReportSection.CRIMINAL_RECORDS,
            ReportSection.REGULATORY_RECORDS,
            ReportSection.RECOMMENDATIONS,
            ReportSection.FOOTER,
        ],
        visible_fields=[
            "risk_score",
            "risk_level",
            "recommendation",
            "recommendation_reasons",
            "findings_summary.total_findings",
            "findings_summary.by_category",
            "findings_summary.by_severity",
            "findings_summary.critical_findings",
            "findings_summary.high_findings",
            "findings_summary.overall_narrative",
            "investigation_summary.by_type",
            "investigation_summary.average_confidence",
            "connection_summary.entities_discovered",
            "connection_summary.d2_entities",
            "connection_summary.d3_entities",
            "connection_summary.relations_mapped",
            "connection_summary.risk_connections",
            "connection_summary.critical_connections",
            "connection_summary.high_risk_connections",
            "connection_summary.pep_connections",
            "connection_summary.sanctions_connections",
            "connection_summary.shell_company_connections",
            "connection_summary.highest_risk_level",
            "connection_summary.key_risks",
            "risk_assessment.pattern_score",
            "risk_assessment.anomaly_score",
            "risk_assessment.network_score",
            "risk_assessment.deception_score",
        ],
        redacted_fields=[
            "subject.ssn",
            "subject.drivers_license",
        ],
        aggregated_fields=[],
        required_disclosures=[],
        legal_notices=[
            "CONFIDENTIAL - Security Assessment",
            "Distribution restricted to authorized security personnel.",
        ],
    )


def _create_investigator_template() -> ReportTemplate:
    """Create default template for Investigator persona."""
    return ReportTemplate(
        persona=ReportPersona.INVESTIGATOR,
        name="Investigator Case File",
        sections=[
            ReportSection.HEADER,
            ReportSection.EXECUTIVE_SUMMARY,
            ReportSection.RISK_ASSESSMENT,
            ReportSection.IDENTITY_VERIFICATION,
            ReportSection.EMPLOYMENT_HISTORY,
            ReportSection.EDUCATION_HISTORY,
            ReportSection.DETAILED_FINDINGS,
            ReportSection.CRIMINAL_RECORDS,
            ReportSection.CIVIL_RECORDS,
            ReportSection.FINANCIAL_RECORDS,
            ReportSection.REGULATORY_RECORDS,
            ReportSection.CONNECTION_NETWORK,
            ReportSection.RISK_CONNECTIONS,
            ReportSection.DATA_SOURCES,
            ReportSection.AUDIT_TRAIL,
            ReportSection.RECOMMENDATIONS,
            ReportSection.FOOTER,
        ],
        # Investigator sees everything
        visible_fields=["*"],
        redacted_fields=[],  # No redaction for investigators
        aggregated_fields=[],  # Full detail for investigators
        required_disclosures=[],
        legal_notices=[
            "CONFIDENTIAL - Case File",
            "Contains complete investigation data including raw findings.",
            "Access restricted to assigned investigators.",
        ],
    )


def _create_subject_template() -> ReportTemplate:
    """Create default template for Subject (FCRA disclosure) persona."""
    return ReportTemplate(
        persona=ReportPersona.SUBJECT,
        name="Subject Disclosure Report",
        sections=[
            ReportSection.HEADER,
            ReportSection.EXECUTIVE_SUMMARY,
            ReportSection.CHECKS_PERFORMED,
            ReportSection.KEY_FINDINGS,
            ReportSection.CONSUMER_RIGHTS,
            ReportSection.DISPUTE_PROCESS,
            ReportSection.ADVERSE_ACTION_NOTICE,
            ReportSection.FOOTER,
        ],
        visible_fields=[
            "findings_summary.total_findings",
            "findings_summary.verification_status",
            "investigation_summary.types_processed",
            "checks_performed",
            "data_sources_used",
        ],
        redacted_fields=[
            "risk_score",
            "risk_level",
            "risk_assessment",
            "connection_summary",
            "findings_summary.by_category",
            "internal_notes",
            "source_system_ids",
        ],
        aggregated_fields=[
            "findings_summary.by_category",
        ],
        required_disclosures=[
            DisclosureType.FCRA_SUMMARY,
            DisclosureType.FCRA_RIGHTS,
        ],
        legal_notices=[
            "A Summary of Your Rights Under the Fair Credit Reporting Act",
        ],
    )


def _create_executive_template() -> ReportTemplate:
    """Create default template for Executive persona."""
    return ReportTemplate(
        persona=ReportPersona.EXECUTIVE,
        name="Executive Portfolio Report",
        sections=[
            ReportSection.HEADER,
            ReportSection.EXECUTIVE_SUMMARY,
            ReportSection.PORTFOLIO_METRICS,
            ReportSection.RISK_DISTRIBUTION,
            ReportSection.TREND_ANALYSIS,
            ReportSection.COST_ANALYSIS,
            ReportSection.RECOMMENDATIONS,
            ReportSection.FOOTER,
        ],
        visible_fields=[
            "portfolio_summary.total_screenings",
            "portfolio_summary.risk_distribution",
            "portfolio_summary.average_risk_score",
            "portfolio_summary.by_business_unit",
            "portfolio_summary.trend_data",
            "cost_summary.total_cost",
            "cost_summary.cost_by_business_unit",
            "cost_summary.cache_savings",
            "efficiency_metrics",
            "alert_count",
        ],
        redacted_fields=[
            "individual_findings",
            "subject_details",
            "connection_details",
        ],
        aggregated_fields=[
            "portfolio_summary.risk_distribution",
            "portfolio_summary.by_business_unit",
            "cost_summary.cost_by_business_unit",
        ],
        required_disclosures=[],
        legal_notices=[
            "Executive Summary - Confidential",
            "Aggregate metrics for portfolio oversight.",
        ],
    )


# =============================================================================
# Template Registry
# =============================================================================


class TemplateRegistry:
    """Registry for managing report templates.

    Provides access to persona-specific templates and supports
    custom template registration.

    Example:
        ```python
        registry = TemplateRegistry()

        # Get template for HR Manager
        template = registry.get_template(ReportPersona.HR_MANAGER)

        # Register custom template
        registry.register_template(custom_template)

        # List available templates
        templates = registry.list_templates()
        ```
    """

    def __init__(self) -> None:
        """Initialize the registry with default templates."""
        self._templates: dict[ReportPersona, ReportTemplate] = {}
        self._load_default_templates()

    def _load_default_templates(self) -> None:
        """Load all default templates."""
        self._templates[ReportPersona.HR_MANAGER] = _create_hr_manager_template()
        self._templates[ReportPersona.COMPLIANCE] = _create_compliance_template()
        self._templates[ReportPersona.SECURITY] = _create_security_template()
        self._templates[ReportPersona.INVESTIGATOR] = _create_investigator_template()
        self._templates[ReportPersona.SUBJECT] = _create_subject_template()
        self._templates[ReportPersona.EXECUTIVE] = _create_executive_template()

    def get_template(self, persona: ReportPersona) -> ReportTemplate:
        """Get the template for a persona.

        Args:
            persona: The report persona.

        Returns:
            The report template for the persona.

        Raises:
            TemplateNotFoundError: If no template exists for the persona.
        """
        if persona not in self._templates:
            raise TemplateNotFoundError(persona)
        return self._templates[persona]

    def register_template(self, template: ReportTemplate) -> None:
        """Register a custom template.

        Args:
            template: The template to register. Overwrites existing
                     template for the same persona.
        """
        self._templates[template.persona] = template

    def list_templates(self) -> list[ReportPersona]:
        """List all registered template personas.

        Returns:
            List of personas with registered templates.
        """
        return list(self._templates.keys())

    def has_template(self, persona: ReportPersona) -> bool:
        """Check if a template exists for a persona.

        Args:
            persona: The report persona.

        Returns:
            True if a template is registered.
        """
        return persona in self._templates

    def get_all_templates(self) -> dict[ReportPersona, ReportTemplate]:
        """Get all registered templates.

        Returns:
            Dictionary of persona to template.
        """
        return dict(self._templates)


def create_template_registry() -> TemplateRegistry:
    """Factory function to create a template registry.

    Returns:
        A new TemplateRegistry with default templates.
    """
    return TemplateRegistry()
