# Task 3.8: Stale Data Handler (Tier-Aware)

## Overview

Handle stale data according to service tier: Standard tier uses stale data with warning flag, Enhanced tier blocks and refreshes. Integrates freshness policies with screening workflow.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 3.7: Freshness Policy Engine
- Task 2.1: Service Tiers

## Implementation Checklist

- [ ] Create StaleDataHandler service
- [ ] Implement tier-specific handling logic
- [ ] Build stale data flagging for Standard tier
- [ ] Add refresh triggering for Enhanced tier
- [ ] Create stale data audit logging
- [ ] Write stale data handler tests

## Key Implementation

```python
# src/elile/services/stale_data_handler.py
from dataclasses import dataclass

@dataclass
class DataFreshnessResult:
    """Result of data freshness check."""
    cached_data: CachedDataSource | None
    freshness_status: FreshnessStatus
    should_refresh: bool
    can_use_cached: bool
    warnings: list[str]

class StaleDataHandler:
    """Handle stale data according to service tier."""

    def __init__(
        self,
        cache_manager: CacheManager,
        freshness_engine: FreshnessPolicyEngine
    ):
        self.cache = cache_manager
        self.freshness = freshness_engine

    async def get_data_or_refresh(
        self,
        entity_id: UUID,
        check_type: str,
        provider_id: str,
        service_config: ServiceConfig,
        ctx: RequestContext
    ) -> DataFreshnessResult:
        """
        Get cached data if fresh, or determine refresh strategy.

        Standard tier: Use stale data with warning
        Enhanced tier: Refresh stale data
        """
        # Get cached data
        cached = await self.cache.get_cached_response(
            entity_id,
            check_type,
            provider_id
        )

        if not cached:
            return DataFreshnessResult(
                cached_data=None,
                freshness_status=FreshnessStatus.EXPIRED,
                should_refresh=True,
                can_use_cached=False,
                warnings=[]
            )

        # Evaluate freshness
        status = self.freshness.evaluate_freshness(
            cached,
            check_type,
            service_config.tier
        )

        # Determine action based on tier
        should_refresh = self.freshness.should_refresh(
            status,
            service_config.tier
        )

        warnings = []
        can_use_cached = True

        if status == FreshnessStatus.STALE:
            if service_config.tier == ServiceTier.STANDARD:
                # Standard: use stale data with warning
                warnings.append(
                    f"Using stale {check_type} data (age: {(datetime.utcnow() - cached.cached_at).days} days)"
                )
                can_use_cached = True
                should_refresh = False  # Use stale, don't block

            elif service_config.tier == ServiceTier.ENHANCED:
                # Enhanced: must refresh
                warnings.append(f"{check_type} data is stale, refreshing")
                can_use_cached = False
                should_refresh = True

        elif status == FreshnessStatus.EXPIRED:
            warnings.append(f"{check_type} data expired, refreshing required")
            can_use_cached = False
            should_refresh = True

        # Audit log for stale data usage
        if status != FreshnessStatus.FRESH and can_use_cached:
            await audit_logger.log_event(
                AuditEventType.STALE_DATA_USED,
                ctx,
                {
                    "check_type": check_type,
                    "provider_id": provider_id,
                    "age_days": (datetime.utcnow() - cached.cached_at).days,
                    "tier": service_config.tier
                },
                severity=AuditSeverity.WARNING,
                entity_id=entity_id
            )

        return DataFreshnessResult(
            cached_data=cached if can_use_cached else None,
            freshness_status=status,
            should_refresh=should_refresh,
            can_use_cached=can_use_cached,
            warnings=warnings
        )
```

## Testing Requirements

### Unit Tests
- Standard tier uses stale data
- Enhanced tier refreshes stale data
- Expired data always refreshes
- Warning generation

### Integration Tests
- End-to-end stale data workflow
- Audit logging for stale data usage
- Tier-specific behavior verified

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] Standard tier can use stale data with warning
- [ ] Enhanced tier always refreshes stale data
- [ ] Expired data triggers refresh for all tiers
- [ ] Warnings logged for stale data usage
- [ ] Audit events created for stale usage
- [ ] Integration with cache manager

## Deliverables

- `src/elile/services/stale_data_handler.py`
- `tests/unit/test_stale_data_handler.py`
- `tests/integration/test_stale_data_workflow.py`

## References

- Architecture: [03-screening.md](../architecture/03-screening.md) - Tier-based policies
- Dependencies: Task 3.7 (freshness), Task 2.1 (tiers)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
