# Task 2.1: Service Tier Models

## Overview

Define Standard and Enhanced service tier models with associated data source mappings, cost structures, and feature availability. See [03-screening.md](../architecture/03-screening.md) for tier definitions.

**Priority**: P0 | **Effort**: 1 day | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema

## Implementation Checklist

- [ ] Create ServiceTier enum (Standard/Enhanced)
- [ ] Define tier-specific data source categories
- [ ] Build ServiceTierConfig model with features
- [ ] Implement cost multipliers per tier
- [ ] Create tier validation logic
- [ ] Write tier model tests

## Key Implementation

```python
# src/elile/models/service.py
from enum import Enum
from pydantic import BaseModel

class ServiceTier(str, Enum):
    STANDARD = "standard"  # T1: Core sources (sanctions, criminal, employment, education)
    ENHANCED = "enhanced"  # T2: Core + Premium (behavioral, dark web, OSINT, deep media)

class DataSourceTier(str, Enum):
    T1_CORE = "t1_core"
    T2_PREMIUM = "t2_premium"

class ServiceTierConfig(BaseModel):
    """Configuration for service tier."""
    tier: ServiceTier
    available_sources: set[DataSourceTier]
    cost_multiplier: float
    max_investigation_degree: int  # 2 for Standard, 3 for Enhanced
    features: dict[str, bool]

TIER_CONFIGS = {
    ServiceTier.STANDARD: ServiceTierConfig(
        tier=ServiceTier.STANDARD,
        available_sources={DataSourceTier.T1_CORE},
        cost_multiplier=1.0,
        max_investigation_degree=2,
        features={
            "basic_screening": True,
            "network_analysis": True,
            "premium_sources": False,
            "deep_intelligence": False,
        }
    ),
    ServiceTier.ENHANCED: ServiceTierConfig(
        tier=ServiceTier.ENHANCED,
        available_sources={DataSourceTier.T1_CORE, DataSourceTier.T2_PREMIUM},
        cost_multiplier=2.5,
        max_investigation_degree=3,
        features={
            "basic_screening": True,
            "network_analysis": True,
            "premium_sources": True,
            "deep_intelligence": True,
        }
    )
}

def get_tier_config(tier: ServiceTier) -> ServiceTierConfig:
    """Get configuration for service tier."""
    return TIER_CONFIGS[tier]
```

## Testing Requirements

### Unit Tests
- Tier enum values correct
- Tier configs have required fields
- Standard tier excludes T2 sources
- Enhanced tier includes all sources
- Cost multipliers positive

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] ServiceTier enum with Standard/Enhanced
- [ ] ServiceTierConfig includes source tiers and features
- [ ] TIER_CONFIGS defines both tiers
- [ ] Standard tier max degree = 2
- [ ] Enhanced tier max degree = 3
- [ ] Tier configs immutable

## Deliverables

- `src/elile/models/service.py`
- `tests/unit/test_service_tiers.py`

## References

- Architecture: [03-screening.md](../architecture/03-screening.md) - Service tiers
- Architecture: [06-data-sources.md](../architecture/06-data-sources.md) - T1/T2 sources

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
