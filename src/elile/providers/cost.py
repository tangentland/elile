"""Provider cost tracking service for Elile.

This module provides cost tracking, budget management, and cost analytics
for provider queries to enable billing attribution and cost optimization.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.core.logging import get_logger

logger = get_logger(__name__)


class BudgetConfig(BaseModel):
    """Budget configuration for a tenant.

    Defines spending limits and alert thresholds.
    """

    tenant_id: UUID
    monthly_limit: Decimal | None = Field(
        default=None,
        description="Maximum monthly spend (None = unlimited)",
    )
    daily_limit: Decimal | None = Field(
        default=None,
        description="Maximum daily spend (None = unlimited)",
    )
    warning_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Warn when usage exceeds this fraction of limit",
    )
    hard_limit: bool = Field(
        default=True,
        description="Block requests when budget exceeded",
    )


@dataclass
class CostRecord:
    """Record of a single cost incurrence."""

    record_id: UUID
    query_id: UUID
    provider_id: str
    check_type: str
    tenant_id: UUID

    # Cost details
    cost_amount: Decimal
    cost_currency: str = "USD"

    # Attribution
    screening_id: UUID | None = None

    # Cache impact
    cache_hit: bool = False
    cache_savings: Decimal = field(default_factory=lambda: Decimal("0.00"))

    # Timestamps
    incurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class CostSummary:
    """Aggregated cost summary for a period."""

    tenant_id: UUID | None
    start_date: datetime
    end_date: datetime

    # Totals
    total_cost: Decimal = field(default_factory=lambda: Decimal("0.00"))
    total_queries: int = 0
    cache_hits: int = 0
    cache_savings: Decimal = field(default_factory=lambda: Decimal("0.00"))

    # Breakdowns
    by_provider: dict[str, Decimal] = field(default_factory=dict)
    by_check_type: dict[str, Decimal] = field(default_factory=dict)
    by_day: dict[str, Decimal] = field(default_factory=dict)

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_queries == 0:
            return 0.0
        return self.cache_hits / self.total_queries

    @property
    def effective_cost(self) -> Decimal:
        """Cost after cache savings."""
        return self.total_cost

    @property
    def would_have_cost(self) -> Decimal:
        """What cost would have been without caching."""
        return self.total_cost + self.cache_savings


@dataclass
class BudgetStatus:
    """Current budget status for a tenant."""

    tenant_id: UUID
    config: BudgetConfig | None

    # Current usage
    daily_used: Decimal = field(default_factory=lambda: Decimal("0.00"))
    monthly_used: Decimal = field(default_factory=lambda: Decimal("0.00"))

    # Limit status
    daily_remaining: Decimal | None = None
    monthly_remaining: Decimal | None = None

    # Flags
    daily_warning: bool = False
    monthly_warning: bool = False
    daily_exceeded: bool = False
    monthly_exceeded: bool = False

    @property
    def has_warning(self) -> bool:
        """Check if any warning threshold exceeded."""
        return self.daily_warning or self.monthly_warning

    @property
    def is_exceeded(self) -> bool:
        """Check if any limit exceeded."""
        return self.daily_exceeded or self.monthly_exceeded

    @property
    def hard_limit(self) -> bool:
        """Check if hard limit is enabled."""
        return self.config.hard_limit if self.config else False

    def would_exceed(self, estimated_cost: Decimal) -> bool:
        """Check if estimated cost would exceed limits."""
        if self.daily_remaining is not None:
            if self.daily_used + estimated_cost > (
                self.config.daily_limit if self.config and self.config.daily_limit else Decimal("inf")
            ):
                return True

        if self.monthly_remaining is not None:
            if self.monthly_used + estimated_cost > (
                self.config.monthly_limit
                if self.config and self.config.monthly_limit
                else Decimal("inf")
            ):
                return True

        return False


class BudgetExceededError(Exception):
    """Raised when a budget limit is exceeded."""

    def __init__(self, tenant_id: UUID, status: BudgetStatus):
        self.tenant_id = tenant_id
        self.status = status

        details = []
        if status.daily_exceeded:
            details.append(f"daily limit (used: ${status.daily_used})")
        if status.monthly_exceeded:
            details.append(f"monthly limit (used: ${status.monthly_used})")

        message = f"Budget exceeded for tenant {tenant_id}: {', '.join(details)}"
        super().__init__(message)


class ProviderCostService:
    """Service for tracking provider query costs.

    Provides cost recording, budget management, and analytics.

    Usage:
        cost_service = ProviderCostService()

        # Record query cost
        record = await cost_service.record_cost(
            query_id=query_id,
            provider_id="sterling",
            check_type="criminal_national",
            cost=Decimal("5.00"),
            tenant_id=tenant_id,
        )

        # Check budget before query
        status = await cost_service.check_budget(tenant_id, Decimal("10.00"))
        if status.would_exceed(Decimal("10.00")):
            raise BudgetExceededError(tenant_id, status)

        # Get cost analytics
        summary = await cost_service.get_tenant_costs(
            tenant_id, start_date, end_date
        )
    """

    def __init__(self):
        """Initialize cost service."""
        # In-memory storage (would be database in production)
        self._records: list[CostRecord] = []
        self._budgets: dict[UUID, BudgetConfig] = {}
        self._cache_savings: dict[UUID, list[tuple[datetime, Decimal]]] = {}

    async def record_cost(
        self,
        query_id: UUID,
        provider_id: str,
        check_type: str,
        cost: Decimal,
        tenant_id: UUID,
        *,
        screening_id: UUID | None = None,
        cache_hit: bool = False,
        currency: str = "USD",
    ) -> CostRecord:
        """Record a cost incurrence.

        Args:
            query_id: ID of the query that incurred cost.
            provider_id: Provider that was queried.
            check_type: Type of check performed.
            cost: Cost amount incurred.
            tenant_id: Tenant to attribute cost to.
            screening_id: Optional screening session ID.
            cache_hit: Whether this was a cache hit (no actual cost).
            currency: Currency code.

        Returns:
            Created CostRecord.
        """
        record = CostRecord(
            record_id=uuid7(),
            query_id=query_id,
            provider_id=provider_id,
            check_type=check_type if isinstance(check_type, str) else check_type.value,
            tenant_id=tenant_id,
            cost_amount=cost,
            cost_currency=currency,
            screening_id=screening_id,
            cache_hit=cache_hit,
        )

        self._records.append(record)

        logger.info(
            "cost_recorded",
            record_id=str(record.record_id),
            query_id=str(query_id),
            provider_id=provider_id,
            check_type=record.check_type,
            cost=float(cost),
            tenant_id=str(tenant_id),
            cache_hit=cache_hit,
        )

        return record

    async def record_cache_savings(
        self,
        query_id: UUID,
        provider_id: str,
        saved_amount: Decimal,
        tenant_id: UUID,
        *,
        check_type: str | None = None,
    ) -> None:
        """Record cost savings from cache hit.

        Args:
            query_id: ID of the query that benefited from cache.
            provider_id: Provider that would have been queried.
            saved_amount: Amount saved by using cache.
            tenant_id: Tenant that benefited.
            check_type: Type of check that was cached.
        """
        now = datetime.now(UTC)

        if tenant_id not in self._cache_savings:
            self._cache_savings[tenant_id] = []

        self._cache_savings[tenant_id].append((now, saved_amount))

        logger.info(
            "cache_savings_recorded",
            query_id=str(query_id),
            provider_id=provider_id,
            saved_amount=float(saved_amount),
            tenant_id=str(tenant_id),
        )

    async def get_tenant_costs(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> CostSummary:
        """Get cost summary for a tenant.

        Args:
            tenant_id: Tenant to get costs for.
            start_date: Start of period (inclusive).
            end_date: End of period (inclusive).

        Returns:
            CostSummary for the period.
        """
        summary = CostSummary(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

        for record in self._records:
            if record.tenant_id != tenant_id:
                continue
            if record.incurred_at < start_date or record.incurred_at > end_date:
                continue

            summary.total_queries += 1
            summary.total_cost += record.cost_amount

            if record.cache_hit:
                summary.cache_hits += 1

            # By provider
            if record.provider_id not in summary.by_provider:
                summary.by_provider[record.provider_id] = Decimal("0.00")
            summary.by_provider[record.provider_id] += record.cost_amount

            # By check type
            if record.check_type not in summary.by_check_type:
                summary.by_check_type[record.check_type] = Decimal("0.00")
            summary.by_check_type[record.check_type] += record.cost_amount

            # By day
            day_key = record.incurred_at.strftime("%Y-%m-%d")
            if day_key not in summary.by_day:
                summary.by_day[day_key] = Decimal("0.00")
            summary.by_day[day_key] += record.cost_amount

        # Add cache savings
        if tenant_id in self._cache_savings:
            for saved_at, amount in self._cache_savings[tenant_id]:
                if start_date <= saved_at <= end_date:
                    summary.cache_savings += amount

        return summary

    async def get_provider_costs(
        self,
        provider_id: str,
        start_date: datetime,
        end_date: datetime,
        *,
        tenant_id: UUID | None = None,
    ) -> CostSummary:
        """Get cost summary for a provider.

        Args:
            provider_id: Provider to get costs for.
            start_date: Start of period (inclusive).
            end_date: End of period (inclusive).
            tenant_id: Optional tenant filter.

        Returns:
            CostSummary for the period.
        """
        summary = CostSummary(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

        for record in self._records:
            if record.provider_id != provider_id:
                continue
            if tenant_id is not None and record.tenant_id != tenant_id:
                continue
            if record.incurred_at < start_date or record.incurred_at > end_date:
                continue

            summary.total_queries += 1
            summary.total_cost += record.cost_amount

            if record.cache_hit:
                summary.cache_hits += 1

            # By check type
            if record.check_type not in summary.by_check_type:
                summary.by_check_type[record.check_type] = Decimal("0.00")
            summary.by_check_type[record.check_type] += record.cost_amount

            # By day
            day_key = record.incurred_at.strftime("%Y-%m-%d")
            if day_key not in summary.by_day:
                summary.by_day[day_key] = Decimal("0.00")
            summary.by_day[day_key] += record.cost_amount

        return summary

    async def set_budget(self, config: BudgetConfig) -> None:
        """Set budget configuration for a tenant.

        Args:
            config: Budget configuration.
        """
        self._budgets[config.tenant_id] = config

        logger.info(
            "budget_configured",
            tenant_id=str(config.tenant_id),
            monthly_limit=float(config.monthly_limit) if config.monthly_limit else None,
            daily_limit=float(config.daily_limit) if config.daily_limit else None,
            hard_limit=config.hard_limit,
        )

    async def get_budget(self, tenant_id: UUID) -> BudgetConfig | None:
        """Get budget configuration for a tenant.

        Args:
            tenant_id: Tenant to get budget for.

        Returns:
            BudgetConfig or None if not configured.
        """
        return self._budgets.get(tenant_id)

    async def check_budget(
        self,
        tenant_id: UUID,
        estimated_cost: Decimal = Decimal("0.00"),
    ) -> BudgetStatus:
        """Check current budget status for a tenant.

        Args:
            tenant_id: Tenant to check.
            estimated_cost: Estimated cost of upcoming query.

        Returns:
            BudgetStatus with current usage and limits.
        """
        config = self._budgets.get(tenant_id)
        now = datetime.now(UTC)

        # Calculate current day and month boundaries
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Sum up usage
        daily_used = Decimal("0.00")
        monthly_used = Decimal("0.00")

        for record in self._records:
            if record.tenant_id != tenant_id:
                continue

            if record.incurred_at >= month_start:
                monthly_used += record.cost_amount

            if record.incurred_at >= day_start:
                daily_used += record.cost_amount

        # Build status
        status = BudgetStatus(
            tenant_id=tenant_id,
            config=config,
            daily_used=daily_used,
            monthly_used=monthly_used,
        )

        if config:
            # Calculate remaining and flags
            if config.daily_limit is not None:
                status.daily_remaining = config.daily_limit - daily_used
                if daily_used >= config.daily_limit:
                    status.daily_exceeded = True
                elif daily_used >= config.daily_limit * Decimal(str(config.warning_threshold)):
                    status.daily_warning = True

            if config.monthly_limit is not None:
                status.monthly_remaining = config.monthly_limit - monthly_used
                if monthly_used >= config.monthly_limit:
                    status.monthly_exceeded = True
                elif monthly_used >= config.monthly_limit * Decimal(str(config.warning_threshold)):
                    status.monthly_warning = True

        return status

    async def check_budget_or_raise(
        self,
        tenant_id: UUID,
        estimated_cost: Decimal = Decimal("0.00"),
    ) -> BudgetStatus:
        """Check budget and raise if exceeded.

        Args:
            tenant_id: Tenant to check.
            estimated_cost: Estimated cost of upcoming query.

        Returns:
            BudgetStatus if within budget.

        Raises:
            BudgetExceededError: If budget exceeded and hard limit enabled.
        """
        status = await self.check_budget(tenant_id, estimated_cost)

        if status.is_exceeded and status.hard_limit:
            raise BudgetExceededError(tenant_id, status)

        return status

    def get_total_recorded(self) -> Decimal:
        """Get total costs recorded across all tenants.

        Returns:
            Total cost amount.
        """
        return sum((r.cost_amount for r in self._records), Decimal("0.00"))

    def get_total_savings(self) -> Decimal:
        """Get total cache savings across all tenants.

        Returns:
            Total savings amount.
        """
        total = Decimal("0.00")
        for savings_list in self._cache_savings.values():
            for _, amount in savings_list:
                total += amount
        return total

    def reset(self) -> None:
        """Reset all records (for testing)."""
        self._records.clear()
        self._budgets.clear()
        self._cache_savings.clear()


# Global service instance
_cost_service: ProviderCostService | None = None


def get_cost_service() -> ProviderCostService:
    """Get the global cost service.

    Returns:
        Shared ProviderCostService instance.
    """
    global _cost_service
    if _cost_service is None:
        _cost_service = ProviderCostService()
    return _cost_service


def reset_cost_service() -> None:
    """Reset the global cost service.

    Primarily for testing purposes.
    """
    global _cost_service
    _cost_service = None
