# Task 2.8: Data Source Resolver

## Overview

Map service tier + compliance ruleset to specific data providers. Determines which providers to query based on permitted checks, tier availability, and jurisdiction restrictions.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 2.1: Service Tiers
- Task 2.6: Compliance Engine

## Implementation Checklist

- [ ] Create DataSourceMapping model
- [ ] Implement provider selection algorithm
- [ ] Build tier-aware filtering
- [ ] Create compliance-aware filtering
- [ ] Add provider priority ordering
- [ ] Write data source resolver tests

## Key Implementation

```python
# src/elile/compliance/data_source_resolver.py
from dataclasses import dataclass

@dataclass
class DataSourceMapping:
    """Maps check type to provider and tier."""
    check_type: str
    provider_id: str
    tier: DataSourceTier
    priority: int
    jurisdictions: list[str] | None = None  # null = all jurisdictions

# Core data source mappings
DATA_SOURCE_MAPPINGS = [
    # T1 Core Sources
    DataSourceMapping("sanctions", "worldcheck", DataSourceTier.T1_CORE, priority=1),
    DataSourceMapping("sanctions", "ofac", DataSourceTier.T1_CORE, priority=2),
    DataSourceMapping("criminal", "pacer", DataSourceTier.T1_CORE, priority=1, jurisdictions=["US"]),
    DataSourceMapping("employment", "work_number", DataSourceTier.T1_CORE, priority=1, jurisdictions=["US"]),
    DataSourceMapping("education", "clearinghouse", DataSourceTier.T1_CORE, priority=1, jurisdictions=["US"]),
    DataSourceMapping("credit", "experian", DataSourceTier.T1_CORE, priority=1, jurisdictions=["US"]),

    # T2 Premium Sources
    DataSourceMapping("adverse_media", "lexisnexis", DataSourceTier.T2_PREMIUM, priority=1),
    DataSourceMapping("dark_web", "recorded_future", DataSourceTier.T2_PREMIUM, priority=1),
    DataSourceMapping("behavioral", "social_links", DataSourceTier.T2_PREMIUM, priority=1),
]

class DataSourceResolver:
    """Resolves data sources based on tier and compliance."""

    def __init__(self):
        self.mappings = DATA_SOURCE_MAPPINGS

    def resolve_providers(
        self,
        check_types: list[str],
        service_config: ServiceConfig,
        compliance_ruleset: ComplianceRuleset
    ) -> dict[str, list[str]]:
        """
        Determine which providers to query for each check type.

        Args:
            check_types: Requested check types
            service_config: Service tier configuration
            compliance_ruleset: Evaluated compliance rules

        Returns:
            Dict mapping check_type to list of provider_ids (priority ordered)
        """
        tier_config = get_tier_config(service_config.tier)
        available_tiers = tier_config.available_sources
        jurisdiction = compliance_ruleset.jurisdiction

        provider_map = {}

        for check_type in check_types:
            # Check compliance
            if not compliance_ruleset.permitted_checks or \
               check_type not in compliance_ruleset.permitted_checks:
                continue  # Skip non-permitted checks

            # Find matching providers
            providers = []
            for mapping in self.mappings:
                if mapping.check_type != check_type:
                    continue

                # Check tier availability
                if mapping.tier not in available_tiers:
                    continue

                # Check jurisdiction
                if mapping.jurisdictions and jurisdiction not in mapping.jurisdictions:
                    continue

                providers.append((mapping.priority, mapping.provider_id))

            # Sort by priority and extract provider_ids
            providers.sort(key=lambda x: x[0])
            provider_map[check_type] = [p[1] for p in providers]

        return provider_map

    def get_fallback_providers(
        self,
        check_type: str,
        primary_provider: str
    ) -> list[str]:
        """Get fallback providers if primary fails."""
        providers = [
            m.provider_id for m in self.mappings
            if m.check_type == check_type and m.provider_id != primary_provider
        ]
        return providers
```

## Testing Requirements

### Unit Tests
- Provider resolution for Standard tier
- Provider resolution for Enhanced tier
- Compliance filtering works
- Jurisdiction filtering works
- Priority ordering correct

### Integration Tests
- Resolve providers for US + Standard tier
- Resolve providers for EU + Enhanced tier
- Verify T2 sources excluded on Standard tier

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] DataSourceMapping defines check type to provider
- [ ] Resolver filters by service tier
- [ ] Resolver respects compliance permitted checks
- [ ] Jurisdiction filtering works
- [ ] Providers ordered by priority
- [ ] Fallback providers available

## Deliverables

- `src/elile/compliance/data_source_resolver.py`
- `tests/unit/test_data_source_resolver.py`

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md) - Data sources
- Dependencies: Task 2.1 (tiers), Task 2.6 (compliance)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
