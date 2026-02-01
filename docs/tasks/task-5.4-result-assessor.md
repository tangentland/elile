# Task 5.4: Result Assessor

## Overview

Implement result assessor that analyzes query results, extracts findings, calculates confidence scores, identifies gaps, and measures information gain for SAR iteration decisions.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 5.3: Query Executor (query results)
- Task 5.1: SAR State Machine (confidence tracking)
- Task 1.2: Audit Logging

## Implementation Checklist

- [ ] Create ResultAssessor with finding extraction
- [ ] Implement confidence score calculation
- [ ] Build gap identification logic
- [ ] Add information gain measurement
- [ ] Create inconsistency detection
- [ ] Implement entity discovery
- [ ] Write comprehensive assessor tests

## Key Implementation

```python
# src/elile/investigation/result_assessor.py
@dataclass
class AssessmentResult:
    """Assessment of query results for an information type."""
    info_type: InformationType
    iteration_number: int

    # Findings
    facts_extracted: list[Fact]
    new_facts_count: int
    total_facts_count: int

    # Confidence
    confidence_score: float
    confidence_factors: dict[str, float]

    # Gaps
    gaps_identified: list[str]
    expected_but_missing: list[str]

    # Information gain
    info_gain_rate: float
    queries_executed: int
    results_returned: int

    # Discoveries
    discovered_entities: list[Entity]
    inconsistencies: list[Inconsistency]

@dataclass
class Fact:
    """An extracted fact from provider data."""
    fact_type: str
    value: Any
    source_provider: str
    confidence: float
    discovered_at: datetime

@dataclass
class Inconsistency:
    """Detected inconsistency between sources."""
    field: str
    claimed_value: Any
    found_value: Any
    severity: Literal["minor", "moderate", "significant", "critical"]
    deception_score: float

class ResultAssessor:
    """Assesses query results and extracts structured findings."""

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        audit_logger: AuditLogger
    ):
        self.kb = knowledge_base
        self.audit = audit_logger

    async def assess_results(
        self,
        info_type: InformationType,
        results: list[QueryResult],
        iteration_number: int,
        ctx: RequestContext
    ) -> AssessmentResult:
        """
        Assess query results for information type.

        Args:
            info_type: Information type being assessed
            results: Query results to assess
            iteration_number: Current iteration
            ctx: Request context

        Returns:
            Assessment with findings, confidence, gaps
        """
        # Extract facts from results
        facts = []
        for result in results:
            if result.status == "success" and result.raw_data:
                extracted = await self._extract_facts(
                    info_type, result.raw_data, result.provider_id
                )
                facts.extend(extracted)

        # Identify new vs. known facts
        new_facts = self._identify_new_facts(facts)

        # Calculate confidence
        confidence_score, factors = self._calculate_confidence(
            info_type, facts, results
        )

        # Identify gaps
        gaps = self._identify_gaps(info_type, facts)

        # Calculate info gain
        info_gain_rate = len(new_facts) / len(results) if results else 0.0

        # Detect inconsistencies
        inconsistencies = self._detect_inconsistencies(info_type, facts)

        # Discover entities
        entities = self._discover_entities(facts)

        # Update knowledge base with new facts
        self._update_knowledge_base(info_type, new_facts)

        assessment = AssessmentResult(
            info_type=info_type,
            iteration_number=iteration_number,
            facts_extracted=facts,
            new_facts_count=len(new_facts),
            total_facts_count=len(self.kb.get_facts_for_type(info_type)),
            confidence_score=confidence_score,
            confidence_factors=factors,
            gaps_identified=gaps,
            expected_but_missing=[],
            info_gain_rate=info_gain_rate,
            queries_executed=len(results),
            results_returned=sum(1 for r in results if r.status == "success"),
            discovered_entities=entities,
            inconsistencies=inconsistencies
        )

        # Audit
        await self.audit.log_event(
            AuditEventType.RESULTS_ASSESSED,
            ctx,
            {
                "info_type": info_type,
                "iteration": iteration_number,
                "new_facts": len(new_facts),
                "confidence": confidence_score,
                "gaps": len(gaps),
                "inconsistencies": len(inconsistencies)
            }
        )

        return assessment

    async def _extract_facts(
        self,
        info_type: InformationType,
        raw_data: dict,
        provider_id: str
    ) -> list[Fact]:
        """Extract structured facts from raw provider data."""
        facts = []

        if info_type == InformationType.IDENTITY:
            # Extract identity facts
            if "name_variants" in raw_data:
                for name in raw_data["name_variants"]:
                    facts.append(Fact(
                        fact_type="name_variant",
                        value=name,
                        source_provider=provider_id,
                        confidence=0.95,
                        discovered_at=datetime.now(timezone.utc)
                    ))

            if "addresses" in raw_data:
                for addr in raw_data["addresses"]:
                    facts.append(Fact(
                        fact_type="address",
                        value=addr,
                        source_provider=provider_id,
                        confidence=0.90,
                        discovered_at=datetime.now(timezone.utc)
                    ))

        elif info_type == InformationType.EMPLOYMENT:
            # Extract employment facts
            if "employers" in raw_data:
                for emp in raw_data["employers"]:
                    facts.append(Fact(
                        fact_type="employer",
                        value=emp,
                        source_provider=provider_id,
                        confidence=0.85,
                        discovered_at=datetime.now(timezone.utc)
                    ))

        # Add more extraction logic per type...

        return facts

    def _calculate_confidence(
        self,
        info_type: InformationType,
        facts: list[Fact],
        results: list[QueryResult]
    ) -> tuple[float, dict[str, float]]:
        """
        Calculate confidence score for information type.

        Returns:
            (confidence_score, contributing_factors)
        """
        factors = {}

        # Factor 1: Data completeness (0.0-1.0)
        expected_facts = self._get_expected_fact_count(info_type)
        actual_facts = len(facts)
        completeness = min(actual_facts / expected_facts, 1.0) if expected_facts else 0.0
        factors["completeness"] = completeness

        # Factor 2: Multi-source corroboration (0.0-1.0)
        corroboration = self._calculate_corroboration(facts)
        factors["corroboration"] = corroboration

        # Factor 3: Query success rate (0.0-1.0)
        success_rate = sum(
            1 for r in results if r.status == "success"
        ) / len(results) if results else 0.0
        factors["query_success"] = success_rate

        # Factor 4: Fact confidence average (0.0-1.0)
        avg_confidence = sum(f.confidence for f in facts) / len(facts) if facts else 0.0
        factors["fact_confidence"] = avg_confidence

        # Weighted average
        confidence_score = (
            completeness * 0.35 +
            corroboration * 0.30 +
            success_rate * 0.20 +
            avg_confidence * 0.15
        )

        return confidence_score, factors

    def _identify_gaps(
        self,
        info_type: InformationType,
        facts: list[Fact]
    ) -> list[str]:
        """Identify missing expected information."""
        gaps = []

        if info_type == InformationType.EMPLOYMENT:
            # Check for employment gaps
            employers = [f for f in facts if f.fact_type == "employer"]
            if not employers:
                gaps.append("no_employment_found")
            else:
                # Check for date completeness
                for emp in employers:
                    if "end_date" not in emp.value:
                        gaps.append(f"employment_end_date_missing:{emp.value['name']}")

        elif info_type == InformationType.EDUCATION:
            # Check for degree verification
            degrees = [f for f in facts if f.fact_type == "degree"]
            if not degrees:
                gaps.append("no_education_verified")

        return gaps

    def _detect_inconsistencies(
        self,
        info_type: InformationType,
        facts: list[Fact]
    ) -> list[Inconsistency]:
        """Detect inconsistencies in extracted facts."""
        inconsistencies = []

        # Group facts by type
        fact_groups = {}
        for fact in facts:
            if fact.fact_type not in fact_groups:
                fact_groups[fact.fact_type] = []
            fact_groups[fact.fact_type].append(fact)

        # Check for contradictions within groups
        for fact_type, group in fact_groups.items():
            if len(group) > 1:
                # Check if values conflict
                unique_values = set(str(f.value) for f in group)
                if len(unique_values) > 1:
                    # Inconsistency detected
                    inconsistencies.append(Inconsistency(
                        field=fact_type,
                        claimed_value=group[0].value,
                        found_value=group[1].value,
                        severity="moderate",
                        deception_score=0.3
                    ))

        return inconsistencies

    def _discover_entities(self, facts: list[Fact]) -> list[Entity]:
        """Discover entities from facts for network expansion."""
        entities = []

        for fact in facts:
            if fact.fact_type == "employer":
                entities.append(Entity(
                    entity_type=EntityType.ORGANIZATION,
                    name=fact.value.get("name"),
                    discovered_from=fact.fact_type
                ))
            elif fact.fact_type == "associate":
                entities.append(Entity(
                    entity_type=EntityType.INDIVIDUAL,
                    name=fact.value.get("name"),
                    discovered_from=fact.fact_type
                ))

        return entities
```

## Testing Requirements

### Unit Tests
- Fact extraction per information type
- Confidence calculation with factors
- Gap identification logic
- Inconsistency detection
- Entity discovery
- Information gain calculation

### Integration Tests
- Complete assessment cycle
- Multi-source corroboration
- Knowledge base updates

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] ResultAssessor extracts structured facts
- [ ] Confidence score calculated with factors
- [ ] Gaps identified per information type
- [ ] Inconsistencies detected and scored
- [ ] Entities discovered for network expansion
- [ ] Knowledge base updated with new facts
- [ ] Assessment audit trail complete

## Deliverables

- `src/elile/investigation/result_assessor.py`
- `tests/unit/test_result_assessor.py`
- `tests/integration/test_assessment_cycle.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - SAR Assess Phase

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
