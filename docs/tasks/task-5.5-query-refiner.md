# Task 5.5: Query Refiner

## Overview

Implement query refiner that generates targeted queries to fill identified gaps in the REFINE phase of the SAR loop. Uses assessment gaps to create focused follow-up queries.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 5.4: Result Assessor (gap identification)
- Task 5.2: Query Planner (query generation)
- Task 5.1: SAR State Machine (refine phase)

## Implementation Checklist

- [ ] Create QueryRefiner for gap-targeted queries
- [ ] Implement gap-specific query strategies
- [ ] Build query prioritization logic
- [ ] Add query optimization (avoid duplicates)
- [ ] Create refinement query templates
- [ ] Write comprehensive refiner tests

## Key Implementation

```python
# src/elile/investigation/query_refiner.py
class QueryRefiner:
    """Refines queries to target identified gaps."""

    def __init__(
        self,
        query_planner: QueryPlanner,
        audit_logger: AuditLogger
    ):
        self.planner = query_planner
        self.audit = audit_logger

    async def refine_queries(
        self,
        info_type: InformationType,
        assessment: AssessmentResult,
        knowledge_base: KnowledgeBase,
        locale: Locale,
        tier: ServiceTier,
        ctx: RequestContext
    ) -> list[SearchQuery]:
        """
        Generate refinement queries targeting assessment gaps.

        Args:
            info_type: Information type to refine
            assessment: Assessment with identified gaps
            knowledge_base: Current knowledge base
            locale: Subject locale
            tier: Service tier
            ctx: Request context

        Returns:
            List of targeted refinement queries
        """
        queries = []

        # Prioritize gaps
        prioritized_gaps = self._prioritize_gaps(assessment.gaps_identified, info_type)

        # Generate queries for each gap
        for gap in prioritized_gaps:
            gap_queries = await self._generate_gap_queries(
                info_type, gap, knowledge_base, locale, tier
            )
            queries.extend(gap_queries)

        # Optimize - remove duplicates
        queries = self._deduplicate_queries(queries)

        # Audit
        await self.audit.log_event(
            AuditEventType.QUERIES_REFINED,
            ctx,
            {
                "info_type": info_type,
                "gaps_addressed": len(prioritized_gaps),
                "queries_generated": len(queries)
            }
        )

        return queries

    def _prioritize_gaps(
        self,
        gaps: list[str],
        info_type: InformationType
    ) -> list[str]:
        """Prioritize gaps by criticality."""
        # Critical gaps that must be filled
        critical = []
        # Standard gaps
        standard = []

        for gap in gaps:
            if "no_" in gap or "missing" in gap:
                # Missing fundamental data
                critical.append(gap)
            else:
                standard.append(gap)

        return critical + standard

    async def _generate_gap_queries(
        self,
        info_type: InformationType,
        gap: str,
        kb: KnowledgeBase,
        locale: Locale,
        tier: ServiceTier
    ) -> list[SearchQuery]:
        """Generate queries targeting specific gap."""
        queries = []

        if "employment" in gap:
            # Employment gap queries
            if "dates" in gap:
                # Target missing employment dates
                queries.append(SearchQuery(
                    query_id=uuid4(),
                    info_type=info_type,
                    query_type="refinement",
                    provider_id="work_number",
                    search_params={
                        "name": kb.get_primary_name(),
                        "focus": "employment_dates"
                    },
                    iteration_number=2,
                    targeting_gap=gap
                ))

        elif "education" in gap:
            # Education gap queries
            if "no_education" in gap:
                # Try alternate sources
                queries.append(SearchQuery(
                    query_id=uuid4(),
                    info_type=info_type,
                    query_type="refinement",
                    provider_id="nsc_alternate",
                    search_params={
                        "name": kb.get_primary_name(),
                        "dob": kb.confirmed_dob
                    },
                    iteration_number=2,
                    targeting_gap=gap
                ))

        return queries

    def _deduplicate_queries(
        self,
        queries: list[SearchQuery]
    ) -> list[SearchQuery]:
        """Remove duplicate queries."""
        seen = set()
        unique = []

        for query in queries:
            # Create signature from provider + params
            signature = (
                query.provider_id,
                frozenset(query.search_params.items())
            )
            if signature not in seen:
                seen.add(signature)
                unique.append(query)

        return unique
```

## Testing Requirements

### Unit Tests
- Gap prioritization logic
- Query generation per gap type
- Query deduplication
- Refinement strategy per information type

### Integration Tests
- Complete refine cycle
- Multi-gap refinement
- Integration with query planner

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] QueryRefiner generates gap-targeted queries
- [ ] Gaps prioritized by criticality
- [ ] Duplicate queries eliminated
- [ ] Refinement queries use updated knowledge base
- [ ] Audit trail for refinement decisions

## Deliverables

- `src/elile/investigation/query_refiner.py`
- `tests/unit/test_query_refiner.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - SAR Refine Phase

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
