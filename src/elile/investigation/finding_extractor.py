"""Finding Extractor for extracting structured findings from investigation data.

This module provides:
- Finding: A discrete finding from screening with categorization and severity
- FindingCategory: Categories for findings
- Severity: Severity levels for findings
- ExtractionResult: Result of finding extraction
- DataSourceRef: Reference to a data source
- FindingExtractor: AI-powered finding extraction (stub - Task 5.10)

The core models (Finding, FindingCategory, Severity) are used throughout
the risk analysis pipeline.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.core.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Enums
# =============================================================================


class Severity(str, Enum):
    """Severity levels for findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingCategory(str, Enum):
    """Categories for findings."""

    CRIMINAL = "criminal"
    FINANCIAL = "financial"
    REGULATORY = "regulatory"
    REPUTATION = "reputation"
    VERIFICATION = "verification"
    BEHAVIORAL = "behavioral"
    NETWORK = "network"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class DataSourceRef:
    """Reference to a data source for provenance tracking."""

    ref_id: UUID = field(default_factory=uuid7)
    provider_id: str = ""
    provider_name: str = ""
    query_type: str = ""
    queried_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    record_id: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ref_id": str(self.ref_id),
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "query_type": self.query_type,
            "queried_at": self.queried_at.isoformat(),
            "record_id": self.record_id,
            "confidence": self.confidence,
        }


@dataclass
class Finding:
    """A discrete finding from background screening.

    Findings are the primary output of the investigation process,
    representing categorized and scored pieces of information about
    a subject.

    Attributes:
        finding_id: Unique identifier for this finding.
        finding_type: Type of finding (e.g., "dui", "bankruptcy").
        category: Category this finding belongs to.
        summary: Brief summary of the finding.
        details: Detailed description of the finding.
        raw_data: Raw data from which finding was extracted.
        severity: Severity level of the finding.
        confidence: Confidence in the finding (0.0-1.0).
        relevance_to_role: Relevance to the target role (0.0-1.0).
        sources: Data sources for this finding.
        corroborated: Whether finding is confirmed by multiple sources.
        finding_date: Date the finding relates to (if applicable).
        discovered_at: When the finding was discovered.
        subject_entity_id: Entity this finding relates to.
        connection_path: Path to entity if not direct subject.
    """

    finding_id: UUID = field(default_factory=uuid7)
    finding_type: str = ""
    category: FindingCategory | None = None

    # Content
    summary: str = ""
    details: str = ""
    raw_data: dict[str, Any] | None = None

    # Scoring
    severity: Severity = Severity.MEDIUM
    confidence: float = 0.5
    relevance_to_role: float = 0.5

    # Provenance
    sources: list[DataSourceRef] = field(default_factory=list)
    corroborated: bool = False

    # Temporal
    finding_date: date | None = None
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Entity reference
    subject_entity_id: UUID | None = None
    connection_path: list[UUID] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "finding_id": str(self.finding_id),
            "finding_type": self.finding_type,
            "category": self.category.value if self.category else None,
            "summary": self.summary,
            "details": self.details,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "relevance_to_role": self.relevance_to_role,
            "sources": [s.to_dict() for s in self.sources],
            "corroborated": self.corroborated,
            "finding_date": self.finding_date.isoformat() if self.finding_date else None,
            "discovered_at": self.discovered_at.isoformat(),
            "subject_entity_id": str(self.subject_entity_id) if self.subject_entity_id else None,
            "connection_path": [str(p) for p in self.connection_path] if self.connection_path else None,
        }


@dataclass
class ExtractionResult:
    """Result of finding extraction.

    Contains the extracted findings along with metadata about the
    extraction process.
    """

    result_id: UUID = field(default_factory=uuid7)
    findings: list[Finding] = field(default_factory=list)

    # Extraction metadata
    facts_analyzed: int = 0
    findings_extracted: int = 0
    categories_found: list[FindingCategory] = field(default_factory=list)

    # Severity breakdown
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    # Timing
    extracted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    extraction_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "findings": [f.to_dict() for f in self.findings],
            "facts_analyzed": self.facts_analyzed,
            "findings_extracted": self.findings_extracted,
            "categories_found": [c.value for c in self.categories_found],
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "extracted_at": self.extracted_at.isoformat(),
            "extraction_duration_ms": self.extraction_duration_ms,
        }


class ExtractorConfig(BaseModel):
    """Configuration for FindingExtractor."""

    # AI model settings
    model_id: str = Field(default="claude-3-opus", description="AI model to use")
    max_tokens: int = Field(default=2000, ge=100, le=8000, description="Max response tokens")

    # Extraction behavior
    min_confidence: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Minimum confidence to include finding"
    )
    corroboration_threshold: int = Field(
        default=2, ge=1, description="Sources needed for corroboration"
    )

    # Category filtering
    include_categories: list[FindingCategory] | None = Field(
        default=None, description="Categories to include (None = all)"
    )
    exclude_categories: list[FindingCategory] = Field(
        default_factory=list, description="Categories to exclude"
    )


class FindingExtractor:
    """Extracts structured findings from investigation data.

    This class provides AI-powered finding extraction that converts
    raw facts into categorized, scored findings.

    Note: Full AI integration is implemented in Task 5.10.
    This is a stub implementation providing the interface.

    Example:
        ```python
        extractor = FindingExtractor()

        # Extract findings from facts
        result = await extractor.extract_findings(
            facts=accumulated_facts,
            info_type=InformationType.CRIMINAL,
            role_category=RoleCategory.FINANCIAL,
            entity_id=subject_id,
        )

        for finding in result.findings:
            print(f"{finding.category}: {finding.summary}")
        ```
    """

    def __init__(
        self,
        config: ExtractorConfig | None = None,
        # ai_model and audit_logger will be added in Task 5.10
    ):
        """Initialize the finding extractor.

        Args:
            config: Extractor configuration.
        """
        self.config = config or ExtractorConfig()

    async def extract_findings(
        self,
        facts: list[Any],  # Will be list[Fact] when that's defined
        info_type: Any,  # InformationType
        role_category: Any | None = None,  # RoleCategory
        entity_id: UUID | None = None,
    ) -> ExtractionResult:
        """Extract findings from facts.

        This is a stub implementation. Full AI-powered extraction
        will be implemented in Task 5.10.

        Args:
            facts: List of facts to analyze.
            info_type: Information type being processed.
            role_category: Role category for relevance scoring.
            entity_id: Entity the findings relate to.

        Returns:
            ExtractionResult with extracted findings.
        """
        logger.info(
            "Finding extraction (stub)",
            facts_count=len(facts) if facts else 0,
            info_type=str(info_type),
        )

        # Stub implementation - return empty result
        # Full implementation in Task 5.10 will use AI model
        return ExtractionResult(
            facts_analyzed=len(facts) if facts else 0,
            findings_extracted=0,
        )

    def categorize_finding(
        self,
        finding_type: str,
        raw_data: dict[str, Any] | None = None,
    ) -> FindingCategory:
        """Categorize a finding based on its type.

        Args:
            finding_type: Type of the finding.
            raw_data: Optional raw data for context.

        Returns:
            FindingCategory for the finding.
        """
        # Simple keyword-based categorization
        finding_lower = finding_type.lower()

        if any(kw in finding_lower for kw in ["criminal", "arrest", "conviction", "felony", "misdemeanor"]):
            return FindingCategory.CRIMINAL
        elif any(kw in finding_lower for kw in ["financial", "bankruptcy", "debt", "lien", "credit"]):
            return FindingCategory.FINANCIAL
        elif any(kw in finding_lower for kw in ["regulatory", "sanction", "license", "compliance"]):
            return FindingCategory.REGULATORY
        elif any(kw in finding_lower for kw in ["media", "news", "reputation", "social"]):
            return FindingCategory.REPUTATION
        elif any(kw in finding_lower for kw in ["verify", "identity", "education", "employment"]):
            return FindingCategory.VERIFICATION
        elif any(kw in finding_lower for kw in ["behavior", "pattern", "inconsistency"]):
            return FindingCategory.BEHAVIORAL
        elif any(kw in finding_lower for kw in ["network", "connection", "association"]):
            return FindingCategory.NETWORK
        else:
            return FindingCategory.VERIFICATION  # Default

    def assess_severity(
        self,
        finding_type: str,
        category: FindingCategory,
        raw_data: dict[str, Any] | None = None,
    ) -> Severity:
        """Assess severity of a finding.

        Args:
            finding_type: Type of the finding.
            category: Category of the finding.
            raw_data: Optional raw data for context.

        Returns:
            Severity level.
        """
        finding_lower = finding_type.lower()

        # Critical indicators
        if any(kw in finding_lower for kw in ["felony", "sanction", "fraud", "terrorist"]):
            return Severity.CRITICAL

        # High severity indicators
        if any(kw in finding_lower for kw in ["conviction", "bankruptcy", "fabrication", "pep"]):
            return Severity.HIGH

        # Medium severity indicators
        if any(kw in finding_lower for kw in ["misdemeanor", "lien", "inconsistency", "gap"]):
            return Severity.MEDIUM

        # Category-based defaults
        category_defaults = {
            FindingCategory.CRIMINAL: Severity.HIGH,
            FindingCategory.REGULATORY: Severity.HIGH,
            FindingCategory.FINANCIAL: Severity.MEDIUM,
            FindingCategory.REPUTATION: Severity.MEDIUM,
            FindingCategory.BEHAVIORAL: Severity.MEDIUM,
            FindingCategory.NETWORK: Severity.MEDIUM,
            FindingCategory.VERIFICATION: Severity.LOW,
        }

        return category_defaults.get(category, Severity.MEDIUM)


def create_finding_extractor(
    config: ExtractorConfig | None = None,
) -> FindingExtractor:
    """Create a finding extractor.

    Args:
        config: Optional extractor configuration.

    Returns:
        Configured FindingExtractor.
    """
    return FindingExtractor(config=config)
