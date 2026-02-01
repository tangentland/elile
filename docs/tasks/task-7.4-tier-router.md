# Task 7.4: Tier Router

## Overview

Implement tier router that determines service tier capabilities, routes requests to appropriate handlers, and enforces tier-based access controls.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 2.1: Service Tiers
- Task 2.8: Data Source Resolver

## Implementation

```python
# src/elile/screening/tier_router.py
class TierRouter:
    """Routes requests based on service tier."""

    def route_screening(
        self,
        request: ScreeningRequest
    ) -> ScreeningHandler:
        """Route to appropriate handler based on tier."""

        if request.tier == ServiceTier.STANDARD:
            return self.standard_handler
        elif request.tier == ServiceTier.ENHANCED:
            return self.enhanced_handler
        else:
            raise ValueError(f"Unknown tier: {request.tier}")

    def get_available_data_sources(
        self,
        tier: ServiceTier
    ) -> list[DataSourceSpec]:
        """Get available data sources for tier."""

        if tier == ServiceTier.STANDARD:
            return self.resolver.get_core_sources()
        elif tier == ServiceTier.ENHANCED:
            return self.resolver.get_all_sources()  # Core + Premium
```

## Acceptance Criteria

- [ ] Routes Standard tier to core sources
- [ ] Routes Enhanced tier to all sources
- [ ] Enforces tier-based access
- [ ] Returns appropriate handlers

## Deliverables

- `src/elile/screening/tier_router.py`
- `tests/unit/test_tier_router.py`

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
