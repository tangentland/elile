"""Core types and models for the reporting module.

This module defines the enums, data models, and configuration types
used throughout the report generation system.

Architecture Reference: docs/architecture/08-reporting.md
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

# =============================================================================
# Enums
# =============================================================================


class ReportPersona(str, Enum):
    """Report personas defining who will view the report.

    Each persona has different data visibility, aggregation,
    and redaction requirements.
    """

    HR_MANAGER = "hr_manager"  # Risk level, recommendation, key flags
    COMPLIANCE = "compliance"  # Audit trail, consent, compliance checks
    SECURITY = "security"  # Detailed findings, connections, threats
    INVESTIGATOR = "investigator"  # Complete raw data, evidence chain
    SUBJECT = "subject"  # FCRA compliant disclosure
    EXECUTIVE = "executive"  # Aggregate metrics, trends


class OutputFormat(str, Enum):
    """Supported output formats for reports."""

    PDF = "pdf"
    JSON = "json"
    HTML = "html"


class RedactionLevel(str, Enum):
    """Level of PII redaction to apply."""

    NONE = "none"  # No redaction (internal only)
    MINIMAL = "minimal"  # SSN last 4 only
    STANDARD = "standard"  # Standard PII protection
    STRICT = "strict"  # GDPR-level redaction


class ReportSection(str, Enum):
    """Sections that can be included in reports."""

    # Common sections
    HEADER = "header"
    EXECUTIVE_SUMMARY = "executive_summary"
    RISK_ASSESSMENT = "risk_assessment"

    # Finding sections
    KEY_FINDINGS = "key_findings"
    CATEGORY_BREAKDOWN = "category_breakdown"
    DETAILED_FINDINGS = "detailed_findings"

    # Verification sections
    IDENTITY_VERIFICATION = "identity_verification"
    EMPLOYMENT_HISTORY = "employment_history"
    EDUCATION_HISTORY = "education_history"

    # Record sections
    CRIMINAL_RECORDS = "criminal_records"
    CIVIL_RECORDS = "civil_records"
    FINANCIAL_RECORDS = "financial_records"
    REGULATORY_RECORDS = "regulatory_records"

    # Connection sections
    CONNECTION_NETWORK = "connection_network"
    RISK_CONNECTIONS = "risk_connections"

    # Compliance sections
    CONSENT_VERIFICATION = "consent_verification"
    COMPLIANCE_ATTESTATION = "compliance_attestation"
    DATA_SOURCES = "data_sources"
    AUDIT_TRAIL = "audit_trail"

    # Subject disclosure sections
    CHECKS_PERFORMED = "checks_performed"
    CONSUMER_RIGHTS = "consumer_rights"
    DISPUTE_PROCESS = "dispute_process"
    ADVERSE_ACTION_NOTICE = "adverse_action_notice"

    # Executive sections
    PORTFOLIO_METRICS = "portfolio_metrics"
    RISK_DISTRIBUTION = "risk_distribution"
    TREND_ANALYSIS = "trend_analysis"
    COST_ANALYSIS = "cost_analysis"

    # Footer
    FOOTER = "footer"
    RECOMMENDATIONS = "recommendations"


class DisclosureType(str, Enum):
    """Types of required disclosures for compliance."""

    FCRA_SUMMARY = "fcra_summary"
    FCRA_RIGHTS = "fcra_rights"
    ADVERSE_ACTION = "adverse_action"
    GDPR_NOTICE = "gdpr_notice"
    STATE_SPECIFIC = "state_specific"


# =============================================================================
# Configuration Models
# =============================================================================


class BrandingConfig(BaseModel):
    """Branding configuration for PDF reports."""

    logo_url: str | None = None
    primary_color: str = Field(default="#1a365d", description="Primary brand color (hex)")
    secondary_color: str = Field(default="#4a5568", description="Secondary brand color (hex)")
    font_family: str = Field(default="Helvetica", description="Primary font family")
    company_name: str | None = None
    footer_text: str | None = None


class LayoutConfig(BaseModel):
    """Layout configuration for report rendering."""

    page_size: str = Field(default="letter", description="Page size (letter, a4)")
    orientation: str = Field(default="portrait", description="Page orientation")
    margin_top: float = Field(default=1.0, description="Top margin in inches")
    margin_bottom: float = Field(default=1.0, description="Bottom margin in inches")
    margin_left: float = Field(default=0.75, description="Left margin in inches")
    margin_right: float = Field(default=0.75, description="Right margin in inches")
    include_page_numbers: bool = Field(default=True, description="Include page numbers")
    include_toc: bool = Field(default=False, description="Include table of contents")


# =============================================================================
# Report Data Models
# =============================================================================


@dataclass
class FieldRule:
    """Rule for field visibility in a report.

    Attributes:
        field_path: Dot-separated path to the field (e.g., "findings_summary.critical_findings").
        visible: Whether the field is visible.
        redacted: Whether the field should be redacted.
        aggregated: Whether the field should be aggregated (vs. detailed).
        max_items: Maximum number of items to show (for lists).
    """

    field_path: str
    visible: bool = True
    redacted: bool = False
    aggregated: bool = False
    max_items: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field_path": self.field_path,
            "visible": self.visible,
            "redacted": self.redacted,
            "aggregated": self.aggregated,
            "max_items": self.max_items,
        }


@dataclass
class ReportContent:
    """Content for a single report section.

    Attributes:
        section: The section type.
        title: Section title.
        data: Section data.
        template_key: Template key for rendering.
        visible: Whether section is visible.
    """

    section: ReportSection
    title: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    template_key: str = ""
    visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "section": self.section.value,
            "title": self.title,
            "data": self.data,
            "template_key": self.template_key,
            "visible": self.visible,
        }


@dataclass
class GeneratedReportMetadata:
    """Metadata for a generated report.

    This contains all metadata about the generated report,
    separate from the content itself.
    """

    report_id: UUID = field(default_factory=uuid7)
    screening_id: UUID | None = None
    entity_id: UUID | None = None
    tenant_id: UUID | None = None
    persona: ReportPersona = ReportPersona.HR_MANAGER
    output_format: OutputFormat = OutputFormat.PDF
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    generated_by: str = "system"
    template_version: str = "1.0.0"
    redaction_level: RedactionLevel = RedactionLevel.STANDARD
    sections_included: list[ReportSection] = field(default_factory=list)
    checksum: str = ""
    size_bytes: int = 0
    access_expiry: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_id": str(self.report_id),
            "screening_id": str(self.screening_id) if self.screening_id else None,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "persona": self.persona.value,
            "output_format": self.output_format.value,
            "generated_at": self.generated_at.isoformat(),
            "generated_by": self.generated_by,
            "template_version": self.template_version,
            "redaction_level": self.redaction_level.value,
            "sections_included": [s.value for s in self.sections_included],
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
            "access_expiry": self.access_expiry.isoformat() if self.access_expiry else None,
        }


@dataclass
class GeneratedReport:
    """A complete generated report with content and metadata.

    Attributes:
        metadata: Report metadata.
        content: The report content (bytes for PDF, string for JSON/HTML).
        sections: Section contents for structured access.
    """

    metadata: GeneratedReportMetadata = field(default_factory=GeneratedReportMetadata)
    content: bytes = field(default_factory=bytes)
    sections: list[ReportContent] = field(default_factory=list)

    @property
    def report_id(self) -> UUID:
        """Get report ID."""
        return self.metadata.report_id

    @property
    def persona(self) -> ReportPersona:
        """Get report persona."""
        return self.metadata.persona

    @property
    def output_format(self) -> OutputFormat:
        """Get output format."""
        return self.metadata.output_format

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (without content bytes)."""
        return {
            "metadata": self.metadata.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
        }


# =============================================================================
# Request Models
# =============================================================================


class ReportRequest(BaseModel):
    """Request to generate a report.

    Attributes:
        screening_id: ID of the screening to generate report for.
        persona: Report persona (determines content visibility).
        output_format: Desired output format.
        requester_id: ID of the user requesting the report.
        requester_role: Role of the requester.
        redaction_level: Level of PII redaction.
        include_raw_data: Whether to include raw data (security/investigator only).
        custom_sections: Override sections to include.
        branding: Custom branding configuration.
    """

    screening_id: UUID
    persona: ReportPersona = ReportPersona.HR_MANAGER
    output_format: OutputFormat = OutputFormat.PDF
    requester_id: UUID | None = None
    requester_role: str | None = None
    redaction_level: RedactionLevel = RedactionLevel.STANDARD
    include_raw_data: bool = False
    custom_sections: list[ReportSection] | None = None
    branding: BrandingConfig | None = None


# =============================================================================
# Error Types
# =============================================================================


class ReportGenerationError(Exception):
    """Base exception for report generation errors."""

    def __init__(
        self,
        message: str,
        code: str = "REPORT_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class TemplateNotFoundError(ReportGenerationError):
    """Error when a report template is not found."""

    def __init__(self, persona: ReportPersona) -> None:
        super().__init__(
            message=f"No template found for persona: {persona.value}",
            code="TEMPLATE_NOT_FOUND",
            details={"persona": persona.value},
        )


class InvalidRedactionError(ReportGenerationError):
    """Error when redaction fails."""

    def __init__(self, field_path: str, reason: str) -> None:
        super().__init__(
            message=f"Failed to redact field '{field_path}': {reason}",
            code="REDACTION_ERROR",
            details={"field_path": field_path, "reason": reason},
        )


class RenderingError(ReportGenerationError):
    """Error when rendering report content."""

    def __init__(self, output_format: OutputFormat, reason: str) -> None:
        super().__init__(
            message=f"Failed to render {output_format.value} report: {reason}",
            code="RENDERING_ERROR",
            details={"format": output_format.value, "reason": reason},
        )
