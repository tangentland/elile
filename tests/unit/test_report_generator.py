"""Unit tests for the Report Generator Framework.

Tests the ReportGenerator, TemplateRegistry, and related components
for persona-specific report generation.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid7

import pytest

from elile.investigation.finding_extractor import FindingCategory, Severity
from elile.reporting import (
    BrandingConfig,
    DisclosureType,
    FieldRule,
    GeneratedReport,
    GeneratedReportMetadata,
    GeneratorConfig,
    InvalidRedactionError,
    LayoutConfig,
    OutputFormat,
    RedactionLevel,
    RenderingError,
    ReportContent,
    ReportGenerator,
    ReportPersona,
    ReportRequest,
    ReportSection,
    ReportTemplate,
    TemplateNotFoundError,
    TemplateRegistry,
    create_report_generator,
    create_template_registry,
)
from elile.screening.result_compiler import (
    CategorySummary,
    CompiledResult,
    ConnectionSummary,
    FindingsSummary,
    InvestigationSummary,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_compiled_result() -> CompiledResult:
    """Create a sample compiled result for testing."""
    findings_summary = FindingsSummary(
        total_findings=5,
        by_category={
            FindingCategory.CRIMINAL: CategorySummary(
                category=FindingCategory.CRIMINAL,
                total_findings=2,
                critical_count=1,
                high_count=1,
            ),
            FindingCategory.VERIFICATION: CategorySummary(
                category=FindingCategory.VERIFICATION,
                total_findings=3,
                medium_count=2,
                low_count=1,
            ),
        },
        by_severity={
            Severity.CRITICAL: 1,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 1,
        },
        critical_findings=["Felony conviction found"],
        high_findings=["Employment verification discrepancy"],
        overall_narrative="The investigation identified 5 findings, including 1 critical.",
        verification_status="complete",
    )

    investigation_summary = InvestigationSummary(
        types_processed=8,
        types_completed=7,
        types_failed=0,
        types_skipped=1,
        total_iterations=15,
        total_queries=50,
        total_facts=120,
        average_confidence=0.85,
    )

    connection_summary = ConnectionSummary(
        entities_discovered=10,
        d2_entities=7,
        d3_entities=3,
        relations_mapped=15,
        risk_connections=2,
        critical_connections=1,
        high_risk_connections=1,
        pep_connections=0,
        sanctions_connections=1,
    )

    return CompiledResult(
        screening_id=uuid7(),
        entity_id=uuid7(),
        tenant_id=uuid7(),
        findings_summary=findings_summary,
        investigation_summary=investigation_summary,
        connection_summary=connection_summary,
        risk_score=65,
        risk_level="high",
        recommendation="review_required",
    )


@pytest.fixture
def template_registry() -> TemplateRegistry:
    """Create a template registry for testing."""
    return create_template_registry()


@pytest.fixture
def report_generator(template_registry: TemplateRegistry) -> ReportGenerator:
    """Create a report generator for testing."""
    config = GeneratorConfig(require_context=False)
    return ReportGenerator(template_registry=template_registry, config=config)


# =============================================================================
# ReportPersona Tests
# =============================================================================


class TestReportPersona:
    """Tests for ReportPersona enum."""

    def test_all_personas_defined(self):
        """Test that all expected personas are defined."""
        expected_personas = [
            "hr_manager",
            "compliance",
            "security",
            "investigator",
            "subject",
            "executive",
        ]
        for persona_value in expected_personas:
            assert ReportPersona(persona_value) is not None

    def test_persona_string_values(self):
        """Test that persona values are lowercase strings."""
        for persona in ReportPersona:
            assert persona.value == persona.value.lower()
            assert "_" not in persona.value or persona.value.count("_") <= 1


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_all_formats_defined(self):
        """Test that all expected formats are defined."""
        assert OutputFormat.PDF.value == "pdf"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.HTML.value == "html"


class TestRedactionLevel:
    """Tests for RedactionLevel enum."""

    def test_all_levels_defined(self):
        """Test that all expected redaction levels are defined."""
        assert RedactionLevel.NONE.value == "none"
        assert RedactionLevel.MINIMAL.value == "minimal"
        assert RedactionLevel.STANDARD.value == "standard"
        assert RedactionLevel.STRICT.value == "strict"


# =============================================================================
# TemplateRegistry Tests
# =============================================================================


class TestTemplateRegistry:
    """Tests for TemplateRegistry."""

    def test_registry_creates_with_defaults(self, template_registry: TemplateRegistry):
        """Test that registry initializes with default templates."""
        for persona in ReportPersona:
            assert template_registry.has_template(persona)

    def test_get_template_returns_correct_persona(self, template_registry: TemplateRegistry):
        """Test that get_template returns the correct template."""
        for persona in ReportPersona:
            template = template_registry.get_template(persona)
            assert template.persona == persona

    def test_get_template_raises_for_unknown(self):
        """Test that get_template raises for unknown persona."""
        registry = TemplateRegistry()
        # Clear templates
        registry._templates = {}

        with pytest.raises(TemplateNotFoundError):
            registry.get_template(ReportPersona.HR_MANAGER)

    def test_register_custom_template(self, template_registry: TemplateRegistry):
        """Test registering a custom template."""
        custom_template = ReportTemplate(
            persona=ReportPersona.HR_MANAGER,
            name="Custom HR Report",
            version="2.0.0",
            sections=[ReportSection.EXECUTIVE_SUMMARY],
        )

        template_registry.register_template(custom_template)
        retrieved = template_registry.get_template(ReportPersona.HR_MANAGER)

        assert retrieved.name == "Custom HR Report"
        assert retrieved.version == "2.0.0"

    def test_list_templates(self, template_registry: TemplateRegistry):
        """Test listing all registered templates."""
        templates = template_registry.list_templates()
        assert len(templates) == len(ReportPersona)
        for persona in ReportPersona:
            assert persona in templates

    def test_get_all_templates(self, template_registry: TemplateRegistry):
        """Test getting all templates as dictionary."""
        all_templates = template_registry.get_all_templates()
        assert isinstance(all_templates, dict)
        assert len(all_templates) == len(ReportPersona)


# =============================================================================
# ReportTemplate Tests
# =============================================================================


class TestReportTemplate:
    """Tests for ReportTemplate."""

    def test_hr_template_sections(self, template_registry: TemplateRegistry):
        """Test that HR template has expected sections."""
        template = template_registry.get_template(ReportPersona.HR_MANAGER)
        assert ReportSection.EXECUTIVE_SUMMARY in template.sections
        assert ReportSection.RISK_ASSESSMENT in template.sections
        assert ReportSection.KEY_FINDINGS in template.sections

    def test_compliance_template_sections(self, template_registry: TemplateRegistry):
        """Test that Compliance template has audit-specific sections."""
        template = template_registry.get_template(ReportPersona.COMPLIANCE)
        assert ReportSection.AUDIT_TRAIL in template.sections
        assert ReportSection.CONSENT_VERIFICATION in template.sections
        assert ReportSection.DATA_SOURCES in template.sections

    def test_security_template_sections(self, template_registry: TemplateRegistry):
        """Test that Security template has connection network sections."""
        template = template_registry.get_template(ReportPersona.SECURITY)
        assert ReportSection.CONNECTION_NETWORK in template.sections
        assert ReportSection.RISK_CONNECTIONS in template.sections
        assert ReportSection.DETAILED_FINDINGS in template.sections

    def test_subject_template_has_fcra_disclosures(self, template_registry: TemplateRegistry):
        """Test that Subject template includes FCRA disclosures."""
        template = template_registry.get_template(ReportPersona.SUBJECT)
        assert DisclosureType.FCRA_SUMMARY in template.required_disclosures
        assert DisclosureType.FCRA_RIGHTS in template.required_disclosures
        assert ReportSection.CONSUMER_RIGHTS in template.sections
        assert ReportSection.DISPUTE_PROCESS in template.sections

    def test_investigator_template_sees_all_fields(self, template_registry: TemplateRegistry):
        """Test that Investigator template has full field access."""
        template = template_registry.get_template(ReportPersona.INVESTIGATOR)
        assert "*" in template.visible_fields
        assert len(template.redacted_fields) == 0

    def test_template_field_visibility(self, template_registry: TemplateRegistry):
        """Test field visibility checking."""
        template = template_registry.get_template(ReportPersona.HR_MANAGER)

        # Visible field
        assert template.is_field_visible("risk_score")

        # Check field rules
        template.field_rules["test_field"] = FieldRule(
            field_path="test_field", visible=False
        )
        assert not template.is_field_visible("test_field")

    def test_template_field_redaction(self, template_registry: TemplateRegistry):
        """Test field redaction checking."""
        template = template_registry.get_template(ReportPersona.HR_MANAGER)

        # Redacted field
        assert template.is_field_redacted("subject.ssn")

        # Field rule override
        template.field_rules["custom_field"] = FieldRule(
            field_path="custom_field", redacted=True
        )
        assert template.is_field_redacted("custom_field")

    def test_template_max_items(self, template_registry: TemplateRegistry):
        """Test max items limit for list fields."""
        template = template_registry.get_template(ReportPersona.HR_MANAGER)

        # Check field rule with max_items
        max_items = template.get_max_items("findings_summary.critical_findings")
        assert max_items == 5

    def test_template_to_dict(self, template_registry: TemplateRegistry):
        """Test template serialization."""
        template = template_registry.get_template(ReportPersona.HR_MANAGER)
        data = template.to_dict()

        assert data["persona"] == "hr_manager"
        assert "name" in data
        assert "version" in data
        assert "sections" in data


# =============================================================================
# ReportGenerator Tests
# =============================================================================


class TestReportGenerator:
    """Tests for ReportGenerator."""

    @pytest.mark.asyncio
    async def test_generate_json_report(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test generating a JSON report."""
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.HR_MANAGER,
            output_format=OutputFormat.JSON,
        )

        assert report is not None
        assert report.output_format == OutputFormat.JSON
        assert len(report.content) > 0
        assert report.metadata.persona == ReportPersona.HR_MANAGER

    @pytest.mark.asyncio
    async def test_generate_html_report(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test generating an HTML report."""
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.SECURITY,
            output_format=OutputFormat.HTML,
        )

        assert report is not None
        assert report.output_format == OutputFormat.HTML
        content = report.content.decode("utf-8")
        assert "<!DOCTYPE html>" in content
        assert "<html>" in content

    @pytest.mark.asyncio
    async def test_generate_pdf_report(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test generating a PDF report (placeholder)."""
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.HR_MANAGER,
            output_format=OutputFormat.PDF,
        )

        assert report is not None
        assert report.output_format == OutputFormat.PDF
        assert len(report.content) > 0

    @pytest.mark.asyncio
    async def test_generate_reports_for_multiple_personas(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test generating reports for multiple personas."""
        personas = [ReportPersona.HR_MANAGER, ReportPersona.COMPLIANCE, ReportPersona.SECURITY]

        reports = await report_generator.generate_reports(
            compiled_result=sample_compiled_result,
            personas=personas,
            output_format=OutputFormat.JSON,
        )

        assert len(reports) == 3
        for i, report in enumerate(reports):
            assert report.persona == personas[i]

    @pytest.mark.asyncio
    async def test_report_metadata(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test that report metadata is correctly populated."""
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.HR_MANAGER,
            output_format=OutputFormat.JSON,
        )

        metadata = report.metadata
        assert metadata.persona == ReportPersona.HR_MANAGER
        assert metadata.output_format == OutputFormat.JSON
        assert metadata.screening_id == sample_compiled_result.screening_id
        assert metadata.entity_id == sample_compiled_result.entity_id
        assert metadata.tenant_id == sample_compiled_result.tenant_id
        assert metadata.size_bytes > 0
        assert metadata.checksum != ""
        assert metadata.access_expiry is not None

    @pytest.mark.asyncio
    async def test_report_sections_included(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test that report contains expected sections."""
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.HR_MANAGER,
            output_format=OutputFormat.JSON,
        )

        assert len(report.sections) > 0

        section_types = [s.section for s in report.sections]
        assert ReportSection.EXECUTIVE_SUMMARY in section_types
        assert ReportSection.RISK_ASSESSMENT in section_types

    @pytest.mark.asyncio
    async def test_field_filtering(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test that field filtering works correctly."""
        # HR Manager should not see raw data
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.HR_MANAGER,
            output_format=OutputFormat.JSON,
        )

        # Find the executive summary section
        exec_summary = next(
            (s for s in report.sections if s.section == ReportSection.EXECUTIVE_SUMMARY),
            None,
        )
        assert exec_summary is not None
        assert "risk_score" in exec_summary.data
        assert "risk_level" in exec_summary.data

    @pytest.mark.asyncio
    async def test_redaction_standard_level(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test standard redaction level."""
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.HR_MANAGER,
            output_format=OutputFormat.JSON,
            redaction_level=RedactionLevel.STANDARD,
        )

        assert report.metadata.redaction_level == RedactionLevel.STANDARD

    @pytest.mark.asyncio
    async def test_redaction_none_level(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test no redaction for investigators."""
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.INVESTIGATOR,
            output_format=OutputFormat.JSON,
            redaction_level=RedactionLevel.NONE,
        )

        assert report.metadata.redaction_level == RedactionLevel.NONE

    @pytest.mark.asyncio
    async def test_subject_report_includes_fcra_content(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test that subject report includes FCRA content."""
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.SUBJECT,
            output_format=OutputFormat.JSON,
        )

        section_types = [s.section for s in report.sections]
        assert ReportSection.CONSUMER_RIGHTS in section_types
        assert ReportSection.DISPUTE_PROCESS in section_types

    @pytest.mark.asyncio
    async def test_security_report_includes_connections(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test that security report includes connection details."""
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.SECURITY,
            output_format=OutputFormat.JSON,
        )

        section_types = [s.section for s in report.sections]
        assert ReportSection.CONNECTION_NETWORK in section_types
        assert ReportSection.RISK_CONNECTIONS in section_types


# =============================================================================
# Field Filtering Tests
# =============================================================================


class TestFieldFiltering:
    """Tests for field filtering functionality."""

    @pytest.mark.asyncio
    async def test_nested_field_filtering(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test filtering of nested fields."""
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.HR_MANAGER,
            output_format=OutputFormat.JSON,
        )

        # HR should see findings summary
        cat_breakdown = next(
            (s for s in report.sections if s.section == ReportSection.CATEGORY_BREAKDOWN),
            None,
        )
        assert cat_breakdown is not None

    @pytest.mark.asyncio
    async def test_investigator_sees_all_fields(
        self, report_generator: ReportGenerator, sample_compiled_result: CompiledResult
    ):
        """Test that investigator sees all fields."""
        report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.INVESTIGATOR,
            output_format=OutputFormat.JSON,
        )

        # Should have more sections than HR
        hr_report = await report_generator.generate_report(
            compiled_result=sample_compiled_result,
            persona=ReportPersona.HR_MANAGER,
            output_format=OutputFormat.JSON,
        )

        assert len(report.sections) > len(hr_report.sections)


# =============================================================================
# Redaction Tests
# =============================================================================


class TestRedaction:
    """Tests for redaction functionality."""

    def test_redact_ssn_minimal(self, report_generator: ReportGenerator):
        """Test SSN redaction at minimal level."""
        data = {"subject": {"ssn": "123-45-6789"}}
        template = report_generator.templates.get_template(ReportPersona.HR_MANAGER)

        redacted = report_generator._apply_redaction(data, template, RedactionLevel.MINIMAL)

        assert redacted["subject"]["ssn"] == "***-**-6789"

    def test_redact_ssn_standard(self, report_generator: ReportGenerator):
        """Test SSN redaction at standard level."""
        data = {"subject": {"ssn": "123-45-6789"}}
        template = report_generator.templates.get_template(ReportPersona.HR_MANAGER)

        redacted = report_generator._apply_redaction(data, template, RedactionLevel.STANDARD)

        assert redacted["subject"]["ssn"] == "[REDACTED]"

    def test_redact_email_minimal(self, report_generator: ReportGenerator):
        """Test email redaction at minimal level."""
        data = {"subject": {"email": "test@example.com"}}
        template = report_generator.templates.get_template(ReportPersona.HR_MANAGER)
        template.redacted_fields.append("subject.email")

        redacted = report_generator._apply_redaction(data, template, RedactionLevel.MINIMAL)

        assert "example.com" in redacted["subject"]["email"]
        assert "test" not in redacted["subject"]["email"]

    def test_no_redaction_for_none_level(self, report_generator: ReportGenerator):
        """Test that no redaction is applied at NONE level."""
        data = {"subject": {"ssn": "123-45-6789"}}
        template = report_generator.templates.get_template(ReportPersona.HR_MANAGER)

        redacted = report_generator._apply_redaction(data, template, RedactionLevel.NONE)

        assert redacted["subject"]["ssn"] == "123-45-6789"


# =============================================================================
# Configuration Tests
# =============================================================================


class TestGeneratorConfig:
    """Tests for GeneratorConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = GeneratorConfig()
        assert config.default_format == OutputFormat.PDF
        assert config.default_redaction == RedactionLevel.STANDARD
        assert config.access_expiry_hours == 24
        assert config.enable_pdf is True
        assert config.enable_html is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = GeneratorConfig(
            default_format=OutputFormat.JSON,
            default_redaction=RedactionLevel.STRICT,
            access_expiry_hours=48,
        )
        assert config.default_format == OutputFormat.JSON
        assert config.default_redaction == RedactionLevel.STRICT
        assert config.access_expiry_hours == 48

    @pytest.mark.asyncio
    async def test_disabled_pdf_raises_error(
        self, template_registry: TemplateRegistry, sample_compiled_result: CompiledResult
    ):
        """Test that disabled PDF raises error."""
        config = GeneratorConfig(enable_pdf=False, require_context=False)
        generator = ReportGenerator(template_registry=template_registry, config=config)

        with pytest.raises(RenderingError):
            await generator.generate_report(
                compiled_result=sample_compiled_result,
                persona=ReportPersona.HR_MANAGER,
                output_format=OutputFormat.PDF,
            )

    @pytest.mark.asyncio
    async def test_disabled_html_raises_error(
        self, template_registry: TemplateRegistry, sample_compiled_result: CompiledResult
    ):
        """Test that disabled HTML raises error."""
        config = GeneratorConfig(enable_html=False, require_context=False)
        generator = ReportGenerator(template_registry=template_registry, config=config)

        with pytest.raises(RenderingError):
            await generator.generate_report(
                compiled_result=sample_compiled_result,
                persona=ReportPersona.HR_MANAGER,
                output_format=OutputFormat.HTML,
            )


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_report_generator(self):
        """Test create_report_generator factory."""
        generator = create_report_generator()
        assert generator is not None
        assert generator.templates is not None
        assert generator.config is not None

    def test_create_template_registry(self):
        """Test create_template_registry factory."""
        registry = create_template_registry()
        assert registry is not None
        assert len(registry.list_templates()) == len(ReportPersona)

    def test_create_generator_with_custom_config(self):
        """Test creating generator with custom config."""
        config = GeneratorConfig(default_format=OutputFormat.HTML)
        generator = create_report_generator(config=config)
        assert generator.config.default_format == OutputFormat.HTML


# =============================================================================
# Data Model Tests
# =============================================================================


class TestDataModels:
    """Tests for data models."""

    def test_generated_report_metadata_to_dict(self):
        """Test GeneratedReportMetadata serialization."""
        metadata = GeneratedReportMetadata(
            persona=ReportPersona.HR_MANAGER,
            output_format=OutputFormat.PDF,
        )
        data = metadata.to_dict()

        assert data["persona"] == "hr_manager"
        assert data["output_format"] == "pdf"
        assert "report_id" in data
        assert "generated_at" in data

    def test_report_content_to_dict(self):
        """Test ReportContent serialization."""
        content = ReportContent(
            section=ReportSection.EXECUTIVE_SUMMARY,
            title="Executive Summary",
            data={"risk_score": 65},
        )
        data = content.to_dict()

        assert data["section"] == "executive_summary"
        assert data["title"] == "Executive Summary"
        assert data["data"]["risk_score"] == 65

    def test_field_rule_to_dict(self):
        """Test FieldRule serialization."""
        rule = FieldRule(
            field_path="test.field",
            visible=True,
            redacted=True,
            max_items=5,
        )
        data = rule.to_dict()

        assert data["field_path"] == "test.field"
        assert data["visible"] is True
        assert data["redacted"] is True
        assert data["max_items"] == 5

    def test_branding_config_defaults(self):
        """Test BrandingConfig default values."""
        config = BrandingConfig()
        assert config.primary_color == "#1a365d"
        assert config.font_family == "Helvetica"

    def test_layout_config_defaults(self):
        """Test LayoutConfig default values."""
        config = LayoutConfig()
        assert config.page_size == "letter"
        assert config.orientation == "portrait"
        assert config.include_page_numbers is True


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_template_not_found_error(self):
        """Test TemplateNotFoundError."""
        error = TemplateNotFoundError(ReportPersona.HR_MANAGER)
        assert "hr_manager" in error.message
        assert error.code == "TEMPLATE_NOT_FOUND"

    def test_invalid_redaction_error(self):
        """Test InvalidRedactionError."""
        error = InvalidRedactionError("subject.ssn", "Value is None")
        assert "subject.ssn" in error.message
        assert error.code == "REDACTION_ERROR"

    def test_rendering_error(self):
        """Test RenderingError."""
        error = RenderingError(OutputFormat.PDF, "Failed to create PDF")
        assert "pdf" in error.message.lower()
        assert error.code == "RENDERING_ERROR"
