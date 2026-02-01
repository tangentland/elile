# Task 4.11: Sanctions & Watchlist Provider

**Priority**: P1
**Phase**: 4 - Data Providers
**Estimated Effort**: 3 days
**Dependencies**: Task 4.1 (Provider Interface)

## Context

Integrate sanctions and watchlist databases (OFAC, UN, EU, Interpol) for real-time screening against politically exposed persons and sanctioned entities.

**Architecture Reference**: [06-data-sources.md](../docs/architecture/06-data-sources.md) - Sanctions Checks

## Objectives

1. Integrate OFAC SDN list
2. Add UN Security Council sanctions
3. Support EU sanctions lists
4. Implement fuzzy name matching
5. Enable real-time updates

## Technical Approach

```python
# src/elile/providers/sanctions/ofac_provider.py
class OFACProvider(DataProvider):
    """OFAC sanctions list provider."""

    async def check_sanctions(
        self,
        full_name: str,
        date_of_birth: Optional[str] = None,
        country: Optional[str] = None
    ) -> SanctionsCheckResult:
        """Check against OFAC SDN list."""
        # Fuzzy name matching
        # Check aliases
        # Return match confidence
        pass
```

## Implementation Checklist

- [ ] Integrate OFAC API
- [ ] Add UN sanctions database
- [ ] Implement fuzzy matching
- [ ] Create update scheduler
- [ ] Test match accuracy

## Success Criteria

- [ ] 99.9% match accuracy
- [ ] Real-time screening <2s
- [ ] Daily list updates
- [ ] False positive rate <1%
