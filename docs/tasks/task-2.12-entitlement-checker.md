# Task 2.12: Entitlement Checker

**Priority**: P1
**Phase**: 2 - Compliance Engine
**Estimated Effort**: 2 days
**Dependencies**: Task 2.11 (Service Presets), Task 1.4 (Authentication)

## Context

Implement entitlement checking to enforce organization-level permissions for service tiers, data sources, and feature access. Ensures billing compliance and prevents unauthorized service usage.

**Architecture Reference**: [02-core-system.md](../docs/architecture/02-core-system.md) - Authorization
**Related**: [03-screening.md](../docs/architecture/03-screening.md) - Service Tiers

## Objectives

1. Define entitlement models for organizations
2. Implement entitlement checking logic
3. Add usage tracking and limits enforcement
4. Support trial and subscription models
5. Create entitlement caching layer

## Technical Approach

### Entitlement Models

```python
# src/elile/entitlements/models.py
from enum import Enum
from datetime import datetime
from typing import Set, Optional
from pydantic import BaseModel
from elile.screening.models import ServiceTier
from elile.compliance.models import CheckType

class SubscriptionStatus(str, Enum):
    """Subscription status."""
    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

class Entitlement(BaseModel):
    """Organization entitlements."""
    org_id: str
    subscription_status: SubscriptionStatus

    # Tier access
    allowed_tiers: Set[ServiceTier]

    # Check types allowed
    allowed_checks: Set[CheckType]

    # Usage limits
    max_screenings_per_month: int
    max_concurrent_screenings: int
    max_active_monitors: int

    # Data source access
    premium_sources_enabled: bool

    # Feature flags
    api_access_enabled: bool
    bulk_upload_enabled: bool
    custom_branding_enabled: bool

    # Billing
    billing_plan_id: str
    next_billing_date: datetime
    overage_allowed: bool

    # Trial info
    trial_end_date: Optional[datetime] = None
    trial_screenings_used: int = 0
    trial_screenings_limit: int = 10

class UsageMetrics(BaseModel):
    """Current usage metrics."""
    org_id: str
    billing_period_start: datetime
    billing_period_end: datetime

    screenings_this_month: int
    concurrent_screenings: int
    active_monitors: int

    api_calls_this_month: int
    storage_gb: float
```

### Entitlement Repository

```python
# src/elile/entitlements/repository.py
from typing import Optional
from elile.entitlements.models import Entitlement, UsageMetrics
from elile.storage.repository import Repository

class EntitlementRepository:
    """Repository for entitlements."""

    def get_by_org(self, org_id: str) -> Optional[Entitlement]:
        """Get entitlements for organization."""
        # In real implementation, fetch from database
        pass

    def get_usage_metrics(self, org_id: str) -> UsageMetrics:
        """Get current usage metrics."""
        pass

    def increment_usage(
        self,
        org_id: str,
        metric: str,
        amount: int = 1
    ) -> None:
        """Increment usage counter."""
        pass
```

### Entitlement Checker

```python
# src/elile/entitlements/checker.py
from typing import Optional, Set
from datetime import datetime
from elile.entitlements.repository import EntitlementRepository
from elile.entitlements.models import Entitlement, SubscriptionStatus, UsageMetrics
from elile.screening.models import ServiceTier
from elile.compliance.models import CheckType
from elile.cache.cache_service import CacheService

class EntitlementError(Exception):
    """Entitlement check failed."""
    pass

class EntitlementChecker:
    """Check organization entitlements."""

    def __init__(self):
        self.repository = EntitlementRepository()
        self.cache = CacheService("entitlement:", 300)  # 5 min cache

    def get_entitlements(self, org_id: str) -> Entitlement:
        """Get organization entitlements with caching."""
        # Try cache first
        cached = self.cache.get(org_id)
        if cached:
            return Entitlement(**cached)

        # Fetch from database
        entitlement = self.repository.get_by_org(org_id)
        if not entitlement:
            raise EntitlementError(f"No entitlements found for org {org_id}")

        # Cache result
        self.cache.set(org_id, entitlement.dict())
        return entitlement

    def check_subscription_active(self, org_id: str) -> None:
        """Verify subscription is active."""
        entitlement = self.get_entitlements(org_id)

        if entitlement.subscription_status == SubscriptionStatus.SUSPENDED:
            raise EntitlementError("Subscription suspended")

        if entitlement.subscription_status == SubscriptionStatus.CANCELLED:
            raise EntitlementError("Subscription cancelled")

        if entitlement.subscription_status == SubscriptionStatus.EXPIRED:
            raise EntitlementError("Subscription expired")

        # Check trial expiration
        if entitlement.subscription_status == SubscriptionStatus.TRIAL:
            if entitlement.trial_end_date and datetime.utcnow() > entitlement.trial_end_date:
                raise EntitlementError("Trial period expired")

    def check_tier_access(self, org_id: str, tier: ServiceTier) -> None:
        """Verify organization has access to service tier."""
        entitlement = self.get_entitlements(org_id)

        if tier not in entitlement.allowed_tiers:
            raise EntitlementError(
                f"Organization not entitled to {tier.value} tier"
            )

    def check_checks_allowed(
        self,
        org_id: str,
        requested_checks: Set[CheckType]
    ) -> None:
        """Verify all requested checks are allowed."""
        entitlement = self.get_entitlements(org_id)

        disallowed = requested_checks - entitlement.allowed_checks
        if disallowed:
            raise EntitlementError(
                f"Organization not entitled to checks: {disallowed}"
            )

    def check_usage_limits(self, org_id: str) -> None:
        """Verify usage is within limits."""
        entitlement = self.get_entitlements(org_id)
        usage = self.repository.get_usage_metrics(org_id)

        # Check monthly screening limit
        if usage.screenings_this_month >= entitlement.max_screenings_per_month:
            if not entitlement.overage_allowed:
                raise EntitlementError("Monthly screening limit exceeded")

        # Check concurrent screening limit
        if usage.concurrent_screenings >= entitlement.max_concurrent_screenings:
            raise EntitlementError("Concurrent screening limit reached")

        # Check monitor limit
        if usage.active_monitors >= entitlement.max_active_monitors:
            raise EntitlementError("Active monitor limit reached")

        # Check trial limits
        if entitlement.subscription_status == SubscriptionStatus.TRIAL:
            if entitlement.trial_screenings_used >= entitlement.trial_screenings_limit:
                raise EntitlementError("Trial screening limit reached")

    def check_feature_access(self, org_id: str, feature: str) -> None:
        """Verify feature access."""
        entitlement = self.get_entitlements(org_id)

        feature_map = {
            "api_access": entitlement.api_access_enabled,
            "bulk_upload": entitlement.bulk_upload_enabled,
            "custom_branding": entitlement.custom_branding_enabled,
            "premium_sources": entitlement.premium_sources_enabled,
        }

        if feature not in feature_map:
            raise ValueError(f"Unknown feature: {feature}")

        if not feature_map[feature]:
            raise EntitlementError(f"Feature not enabled: {feature}")

    def can_create_screening(
        self,
        org_id: str,
        tier: ServiceTier,
        checks: Set[CheckType]
    ) -> tuple[bool, Optional[str]]:
        """Check if screening creation is allowed."""
        try:
            self.check_subscription_active(org_id)
            self.check_tier_access(org_id, tier)
            self.check_checks_allowed(org_id, checks)
            self.check_usage_limits(org_id)
            return True, None
        except EntitlementError as e:
            return False, str(e)

# Global entitlement checker
entitlement_checker = EntitlementChecker()
```

### Entitlement Middleware

```python
# src/elile/entitlements/middleware.py
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from elile.entitlements.checker import entitlement_checker, EntitlementError

class EntitlementMiddleware(BaseHTTPMiddleware):
    """Middleware to check entitlements on API requests."""

    async def dispatch(self, request: Request, call_next):
        # Skip health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)

        # Get org from auth context
        if hasattr(request.state, "user"):
            org_id = request.state.user.org_id

            try:
                # Check subscription is active
                entitlement_checker.check_subscription_active(org_id)

                # Check API access if needed
                if request.url.path.startswith("/api"):
                    entitlement_checker.check_feature_access(org_id, "api_access")

            except EntitlementError as e:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=str(e)
                )

        return await call_next(request)
```

### Usage Tracker

```python
# src/elile/entitlements/usage_tracker.py
from elile.entitlements.repository import EntitlementRepository
from elile.cache.redis_client import redis_client

class UsageTracker:
    """Track usage metrics."""

    def __init__(self):
        self.repository = EntitlementRepository()

    def increment_screenings(self, org_id: str) -> None:
        """Increment screening count."""
        # Increment in Redis for real-time tracking
        key = f"usage:{org_id}:screenings:month"
        redis_client.increment(key)

        # Also update database periodically
        self.repository.increment_usage(org_id, "screenings_this_month")

    def increment_api_calls(self, org_id: str) -> None:
        """Increment API call count."""
        key = f"usage:{org_id}:api_calls:month"
        redis_client.increment(key)

    def track_concurrent_screening(
        self,
        org_id: str,
        started: bool
    ) -> None:
        """Track concurrent screening start/end."""
        key = f"usage:{org_id}:concurrent"
        if started:
            redis_client.increment(key)
        else:
            redis_client.increment(key, -1)

# Global usage tracker
usage_tracker = UsageTracker()
```

## Implementation Checklist

### Core Infrastructure
- [ ] Define entitlement models
- [ ] Create entitlement repository
- [ ] Implement entitlement checker
- [ ] Add entitlement caching
- [ ] Create usage tracker

### Validation Logic
- [ ] Check subscription status
- [ ] Verify tier access
- [ ] Validate check permissions
- [ ] Enforce usage limits
- [ ] Check feature access

### Integration
- [ ] Add entitlement middleware
- [ ] Integrate with screening creation
- [ ] Add usage tracking hooks
- [ ] Create admin entitlement UI
- [ ] Add billing integration

### Testing
- [ ] Test entitlement checks
- [ ] Test usage limit enforcement
- [ ] Test trial period logic
- [ ] Test caching behavior
- [ ] Test concurrent limits

## Success Criteria

- [ ] All API calls check entitlements
- [ ] Usage limits enforced in real-time
- [ ] Trial period logic works correctly
- [ ] Entitlement cache reduces DB load
- [ ] Clear error messages for violations

## Documentation

- Document entitlement model
- Create billing plan mapping guide
- Add troubleshooting for access denied errors

## Future Enhancements

- Add usage analytics dashboard
- Implement overage billing
- Create usage forecasting
- Add entitlement audit trail
