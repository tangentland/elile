# Task 5.10: Finding Extractor

## Overview

Implement AI-powered finding extractor that converts raw provider data and accumulated facts into structured findings with categorization, severity scoring, and risk assessment.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 3.9: AI Model Adapter (Claude/GPT-4 integration)
- Task 5.4: Result Assessor (facts)
- Task 1.2: Audit Logging

## Implementation Checklist

- [ ] Create FindingExtractor with AI integration
- [ ] Implement structured finding extraction
- [ ] Build finding categorization logic
- [ ] Add severity assessment
- [ ] Create entity reference tracking
- [ ] Write comprehensive extractor tests

## Key Implementation

```python
# src/elile/investigation/finding_extractor.py
@dataclass
class Finding:
    """A discrete finding from screening."""
    finding_id: UUID
    finding_type: str
    category: FindingCategory

    # Content
    summary: str
    details: str
    raw_data: dict | None

    # Scoring
    severity: Severity
    confidence: float
    relevance_to_role: float

    # Provenance
    sources: list[DataSourceRef]
    corroborated: bool

    # Temporal
    finding_date: date | None
    discovered_at: datetime

    # Entity reference
    subject_entity_id: UUID
    connection_path: list[UUID] | None

class FindingCategory(str, Enum):
    CRIMINAL = "criminal"
    FINANCIAL = "financial"
    REGULATORY = "regulatory"
    REPUTATION = "reputation"
    VERIFICATION = "verification"
    BEHAVIORAL = "behavioral"
    NETWORK = "network"

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class FindingExtractor:
    """Extracts structured findings using AI."""

    def __init__(
        self,
        ai_model: AIModelAdapter,
        audit_logger: AuditLogger
    ):
        self.ai = ai_model
        self.audit = audit_logger

    async def extract_findings(
        self,
        facts: list[Fact],
        info_type: InformationType,
        role_category: RoleCategory,
        entity_id: UUID,
        ctx: RequestContext
    ) -> list[Finding]:
        """
        Extract findings from facts using AI analysis.

        Args:
            facts: Extracted facts
            info_type: Information type
            role_category: Role category for relevance
            entity_id: Subject entity ID
            ctx: Request context

        Returns:
            List of structured findings
        """
        if not facts:
            return []

        # Prepare context for AI
        prompt = self._build_extraction_prompt(facts, info_type, role_category)

        # Query AI model
        response = await self.ai.query(
            prompt=prompt,
            response_format="json",
            max_tokens=2000
        )

        # Parse AI response
        findings_data = json.loads(response)

        # Create Finding objects
        findings = []
        for data in findings_data.get("findings", []):
            finding = Finding(
                finding_id=uuid4(),
                finding_type=data["type"],
                category=FindingCategory(data["category"]),
                summary=data["summary"],
                details=data["details"],
                raw_data={"facts": [f.to_dict() for f in facts]},
                severity=Severity(data["severity"]),
                confidence=data["confidence"],
                relevance_to_role=data["relevance"],
                sources=self._extract_sources(facts),
                corroborated=self._is_corroborated(facts, data["type"]),
                finding_date=self._parse_date(data.get("date")),
                discovered_at=datetime.now(timezone.utc),
                subject_entity_id=entity_id,
                connection_path=None
            )
            findings.append(finding)

        # Audit
        await self.audit.log_event(
            AuditEventType.FINDINGS_EXTRACTED,
            ctx,
            {
                "info_type": info_type,
                "findings_count": len(findings),
                "categories": [f.category for f in findings]
            }
        )

        return findings

    def _build_extraction_prompt(
        self,
        facts: list[Fact],
        info_type: InformationType,
        role_category: RoleCategory
    ) -> str:
        """Build prompt for AI finding extraction."""
        facts_text = "\n".join([
            f"- {f.fact_type}: {f.value} (confidence: {f.confidence})"
            for f in facts
        ])

        return f"""
You are analyzing background check data for a {role_category} role.

Information Type: {info_type}

Facts collected:
{facts_text}

Extract structured findings from these facts. For each finding:
1. Categorize (criminal/financial/regulatory/reputation/verification/behavioral/network)
2. Assess severity (low/medium/high/critical)
3. Rate confidence (0.0-1.0)
4. Rate relevance to role (0.0-1.0)
5. Provide summary and details

Return JSON:
{{
  "findings": [
    {{
      "type": "string",
      "category": "criminal|financial|regulatory|reputation|verification|behavioral|network",
      "summary": "brief summary",
      "details": "detailed explanation",
      "severity": "low|medium|high|critical",
      "confidence": 0.0-1.0,
      "relevance": 0.0-1.0,
      "date": "YYYY-MM-DD or null"
    }}
  ]
}}
"""

    def _extract_sources(self, facts: list[Fact]) -> list[DataSourceRef]:
        """Extract unique data sources."""
        sources = {}
        for fact in facts:
            if fact.source_provider not in sources:
                sources[fact.source_provider] = DataSourceRef(
                    provider_id=fact.source_provider,
                    queried_at=fact.discovered_at
                )
        return list(sources.values())

    def _is_corroborated(self, facts: list[Fact], finding_type: str) -> bool:
        """Check if finding is corroborated by multiple sources."""
        relevant_facts = [f for f in facts if finding_type in str(f.fact_type)]
        sources = set(f.source_provider for f in relevant_facts)
        return len(sources) >= 2

    def _parse_date(self, date_str: str | None) -> date | None:
        """Parse date string."""
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except (ValueError, AttributeError):
            return None
```

## Testing Requirements

### Unit Tests
- Finding extraction from facts
- AI prompt construction
- Categorization logic
- Severity assessment
- Source extraction
- Corroboration detection

### Integration Tests
- Complete extraction with AI
- Multi-category findings
- Role-based relevance scoring

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] FindingExtractor uses AI for structured extraction
- [ ] Findings categorized correctly
- [ ] Severity assessed per finding
- [ ] Relevance scored based on role
- [ ] Multi-source corroboration detected
- [ ] Complete provenance tracking

## Deliverables

- `src/elile/investigation/finding_extractor.py`
- `src/elile/models/finding.py`
- `tests/unit/test_finding_extractor.py`
- `tests/integration/test_ai_extraction.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - Finding Extractor

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
