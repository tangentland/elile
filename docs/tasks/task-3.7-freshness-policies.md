# Task 3.7: Freshness Policy Engine

## Overview

Define and enforce data freshness policies per check type (sanctions: always refresh, criminal: 7 days, employment: 90 days). Determines if cached data is acceptable or requires refresh.

**Priority**: P0 | **Effort**: 1-2 days | **Status**: Not Started

## Dependencies

- Task 3.6: Cache Manager

## Implementation Checklist

- [ ] Define freshness windows by check type
- [ ] Implement freshness evaluation logic
- [ ] Build stale data detection
- [ ] Add tier-specific freshness rules
- [ ] Create freshness status reporting
- [ ] Write freshness policy tests

## Key Implementation

```python
# src/elile/services/freshness_policy.py
from datetime import timedelta
from enum import Enum

class FreshnessStatus(str, Enum):
    FRESH = "fresh"          # Within freshness window
    STALE = "stale"          # Outside freshness, but within stale window
    EXPIRED = "expired"      # Must refresh

# Freshness windows (how long data is considered "fresh")
FRESHNESS_WINDOWS = {
    "sanctions": timedelta(days=0),          # Always refresh
    "criminal": timedelta(days=7),
    "adverse_media": timedelta(hours=24),
    "employment": timedelta(days=90),
    "education": timedelta(days=365),
    "credit": timedelta(days=30),
    "regulatory": timedelta(days=30),
}

# Stale windows (max age before must refresh)
STALE_WINDOWS = {
    "sanctions": timedelta(days=0),          # Never use stale
    "criminal": timedelta(days=30),
    "adverse_media": timedelta(days=7),
    "employment": timedelta(days=180),
    "education": timedelta(days=730),        # 2 years
    "credit": timedelta(days=90),
    "regulatory": timedelta(days=90),
}

class FreshnessPolicyEngine:
    """Evaluates data freshness based on policies."""

    def evaluate_freshness(
        self,
        cached_data: CachedDataSource,
        check_type: str,
        service_tier: ServiceTier
    ) -> FreshnessStatus:
        """Determine if cached data is fresh, stale, or expired."""
        now = datetime.utcnow()
        age = now - cached_data.cached_at

        # Get windows for check type
        fresh_window = FRESHNESS_WINDOWS.get(check_type, timedelta(days=30))
        stale_window = STALE_WINDOWS.get(check_type, timedelta(days=90))

        # Enhanced tier: stricter freshness requirements
        if service_tier == ServiceTier.ENHANCED:
            fresh_window = fresh_window * 0.5  # 50% of standard window
            stale_window = stale_window * 0.7  # 70% of standard window

        # Evaluate
        if age <= fresh_window:
            return FreshnessStatus.FRESH
        elif age <= stale_window:
            return FreshnessStatus.STALE
        else:
            return FreshnessStatus.EXPIRED

    def should_refresh(
        self,
        status: FreshnessStatus,
        service_tier: ServiceTier
    ) -> bool:
        """Determine if data should be refreshed."""
        if status == FreshnessStatus.EXPIRED:
            return True

        if status == FreshnessStatus.STALE:
            # Standard tier: can use stale data
            # Enhanced tier: must refresh stale data
            return service_tier == ServiceTier.ENHANCED

        return False  # FRESH

    def get_refresh_priority(
        self,
        check_type: str,
        age: timedelta
    ) -> int:
        """Get priority for refresh (1=highest, 10=lowest)."""
        if check_type == "sanctions":
            return 1  # Always highest priority
        elif check_type == "criminal":
            return 2 if age > timedelta(days=14) else 5
        elif check_type == "adverse_media":
            return 3 if age > timedelta(days=3) else 6
        else:
            return 7  # Lower priority
```

## Testing Requirements

### Unit Tests
- Freshness evaluation for each check type
- Tier-specific freshness adjustments
- should_refresh() logic
- Refresh priority calculation

### Integration Tests
- Freshness policy with real cache data
- Enhanced tier stricter policies

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] Freshness windows defined for all check types
- [ ] evaluate_freshness() returns correct status
- [ ] Enhanced tier has stricter policies
- [ ] should_refresh() logic correct
- [ ] Refresh priority ordering works

## Deliverables

- `src/elile/services/freshness_policy.py`
- `tests/unit/test_freshness_policy.py`

## References

- Architecture: [03-screening.md](../architecture/03-screening.md) - Freshness policies
- Dependencies: Task 3.6 (cache manager)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
