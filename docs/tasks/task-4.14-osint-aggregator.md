# Task 4.14: OSINT Aggregator

**Priority**: P1
**Phase**: 4 - Data Providers
**Estimated Effort**: 3 days
**Dependencies**: Task 4.1 (Provider Interface)

## Context

Aggregate open-source intelligence from social media, news, public records, and professional networks to build comprehensive subject profiles.

**Architecture Reference**: [06-data-sources.md](../docs/architecture/06-data-sources.md) - OSINT

## Objectives

1. Aggregate multiple OSINT sources
2. Deduplicate and normalize data
3. Extract entities and relationships
4. Score information relevance
5. Support continuous monitoring

## Technical Approach

```python
# src/elile/providers/osint/aggregator.py
class OSINTAggregator:
    """Aggregate OSINT from multiple sources."""

    async def gather_intelligence(
        self,
        subject: Subject
    ) -> OSINTReport:
        """Gather all OSINT for subject."""
        sources = [
            self.linkedin_scraper,
            self.news_search,
            self.public_records,
            self.social_media
        ]
        # Parallel queries
        # Deduplication
        # Entity extraction
        pass
```

## Implementation Checklist

- [ ] Implement source aggregation
- [ ] Add deduplication logic
- [ ] Create relevance scoring
- [ ] Test data quality

## Success Criteria

- [ ] Aggregates 10+ sources
- [ ] Dedup accuracy >95%
- [ ] Relevance scoring accurate
