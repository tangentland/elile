# Task 5.11: SAR Foundation Phase Handler

**Priority**: P1
**Phase**: 5 - Investigation Engine
**Estimated Effort**: 3 days
**Dependencies**: Task 5.1 (SAR Loop Implementation)

## Context

Implement the Foundation phase of Search-Assess-Refine loop, establishing initial search strategy and baseline data collection for screening investigation.

**Architecture Reference**: [05-investigation.md](../docs/architecture/05-investigation.md) - SAR Loop

## Objectives

1. Generate initial search queries
2. Establish search breadth and depth
3. Create baseline entity profile
4. Identify high-value data sources
5. Set investigation parameters

## Technical Approach

```python
# src/elile/investigation/phases/foundation.py
class FoundationPhaseHandler:
    """Handle Foundation phase of investigation."""

    async def execute(
        self,
        subject: Subject,
        tier: ServiceTier,
        degree: Degree
    ) -> FoundationResult:
        """Execute foundation phase."""
        # Generate search queries
        queries = self._generate_base_queries(subject)

        # Select data sources based on tier
        sources = self._select_sources(tier, subject.locale)

        # Execute initial searches
        results = await self._execute_searches(queries, sources)

        # Build baseline profile
        profile = self._build_baseline_profile(subject, results)

        return FoundationResult(
            queries=queries,
            sources=sources,
            baseline_profile=profile,
            next_phase="records"
        )
```

## Implementation Checklist

- [ ] Implement query generation
- [ ] Add source selection
- [ ] Create baseline profiling
- [ ] Test phase transitions

## Success Criteria

- [ ] Queries cover all identity facets
- [ ] Source selection optimal
- [ ] Baseline profile complete
