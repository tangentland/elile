# Task 5.13: SAR Intelligence Phase Handler

**Priority**: P1
**Phase**: 5 - Investigation Engine
**Estimated Effort**: 3 days
**Dependencies**: Task 5.12 (Records Phase)

## Context

Implement Intelligence phase for open-source intelligence gathering from news, social media, professional networks, and public information sources.

**Architecture Reference**: [05-investigation.md](../docs/architecture/05-investigation.md) - SAR Loop

## Objectives

1. Execute OSINT data collection
2. Analyze social media presence
3. Search news and adverse media
4. Extract entities and relationships
5. Score information relevance

## Technical Approach

```python
# src/elile/investigation/phases/intelligence.py
class IntelligencePhaseHandler:
    """Handle Intelligence phase of investigation."""

    async def execute(
        self,
        records: RecordsResult
    ) -> IntelligenceResult:
        """Execute OSINT intelligence gathering."""
        # Social media analysis
        social = await self._analyze_social_media(records)

        # News and adverse media
        news = await self._search_adverse_media(records)

        # Professional networks
        professional = await self._query_professional_networks(records)

        return IntelligenceResult(
            social_profile=social,
            media_findings=news,
            professional_profile=professional,
            next_phase="network"
        )
```

## Implementation Checklist

- [ ] Implement OSINT collection
- [ ] Add social media analysis
- [ ] Create relevance scoring
- [ ] Test data quality

## Success Criteria

- [ ] Multi-source OSINT aggregation
- [ ] High relevance accuracy
- [ ] Entity extraction works
