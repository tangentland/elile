"""Unit tests for Provider Cost Tracking Service.

Tests the ProviderCostService and related classes.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from elile.providers import (
    BudgetConfig,
    BudgetExceededError,
    BudgetStatus,
    CostRecord,
    CostSummary,
    ProviderCostService,
    get_cost_service,
    reset_cost_service,
)


# =============================================================================
# BudgetConfig Tests
# =============================================================================


class TestBudgetConfig:
    """Tests for BudgetConfig model."""

    def test_defaults(self):
        """Test default configuration values."""
        tenant_id = uuid4()
        config = BudgetConfig(tenant_id=tenant_id)

        assert config.tenant_id == tenant_id
        assert config.monthly_limit is None
        assert config.daily_limit is None
        assert config.warning_threshold == 0.8
        assert config.hard_limit is True

    def test_custom_values(self):
        """Test custom configuration values."""
        tenant_id = uuid4()
        config = BudgetConfig(
            tenant_id=tenant_id,
            monthly_limit=Decimal("1000.00"),
            daily_limit=Decimal("100.00"),
            warning_threshold=0.75,
            hard_limit=False,
        )

        assert config.monthly_limit == Decimal("1000.00")
        assert config.daily_limit == Decimal("100.00")
        assert config.warning_threshold == 0.75
        assert config.hard_limit is False


# =============================================================================
# CostRecord Tests
# =============================================================================


class TestCostRecord:
    """Tests for CostRecord dataclass."""

    def test_create(self):
        """Test creating a cost record."""
        record = CostRecord(
            record_id=uuid4(),
            query_id=uuid4(),
            provider_id="sterling",
            check_type="criminal_national",
            tenant_id=uuid4(),
            cost_amount=Decimal("5.00"),
        )

        assert record.provider_id == "sterling"
        assert record.cost_amount == Decimal("5.00")
        assert record.cost_currency == "USD"
        assert record.cache_hit is False

    def test_with_cache_hit(self):
        """Test cost record with cache hit."""
        record = CostRecord(
            record_id=uuid4(),
            query_id=uuid4(),
            provider_id="sterling",
            check_type="criminal_national",
            tenant_id=uuid4(),
            cost_amount=Decimal("0.00"),
            cache_hit=True,
            cache_savings=Decimal("5.00"),
        )

        assert record.cache_hit is True
        assert record.cache_savings == Decimal("5.00")


# =============================================================================
# CostSummary Tests
# =============================================================================


class TestCostSummary:
    """Tests for CostSummary dataclass."""

    def test_initial_values(self):
        """Test initial summary values."""
        summary = CostSummary(
            tenant_id=uuid4(),
            start_date=datetime.now(UTC) - timedelta(days=30),
            end_date=datetime.now(UTC),
        )

        assert summary.total_cost == Decimal("0.00")
        assert summary.total_queries == 0
        assert summary.cache_hits == 0
        assert summary.cache_hit_rate == 0.0

    def test_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        summary = CostSummary(
            tenant_id=uuid4(),
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC),
            total_queries=100,
            cache_hits=25,
        )

        assert summary.cache_hit_rate == 0.25

    def test_would_have_cost(self):
        """Test would_have_cost calculation."""
        summary = CostSummary(
            tenant_id=uuid4(),
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC),
            total_cost=Decimal("75.00"),
            cache_savings=Decimal("25.00"),
        )

        assert summary.effective_cost == Decimal("75.00")
        assert summary.would_have_cost == Decimal("100.00")


# =============================================================================
# BudgetStatus Tests
# =============================================================================


class TestBudgetStatus:
    """Tests for BudgetStatus dataclass."""

    def test_no_config(self):
        """Test status without budget configuration."""
        status = BudgetStatus(
            tenant_id=uuid4(),
            config=None,
            daily_used=Decimal("50.00"),
            monthly_used=Decimal("500.00"),
        )

        assert status.has_warning is False
        assert status.is_exceeded is False
        assert status.hard_limit is False

    def test_with_warning(self):
        """Test status with warning threshold exceeded."""
        tenant_id = uuid4()
        config = BudgetConfig(
            tenant_id=tenant_id,
            monthly_limit=Decimal("1000.00"),
            warning_threshold=0.8,
        )

        status = BudgetStatus(
            tenant_id=tenant_id,
            config=config,
            monthly_used=Decimal("850.00"),
            monthly_warning=True,
        )

        assert status.has_warning is True
        assert status.is_exceeded is False

    def test_exceeded(self):
        """Test status with limit exceeded."""
        tenant_id = uuid4()
        config = BudgetConfig(
            tenant_id=tenant_id,
            daily_limit=Decimal("100.00"),
            hard_limit=True,
        )

        status = BudgetStatus(
            tenant_id=tenant_id,
            config=config,
            daily_used=Decimal("110.00"),
            daily_exceeded=True,
        )

        assert status.is_exceeded is True
        assert status.hard_limit is True

    def test_would_exceed(self):
        """Test would_exceed calculation."""
        tenant_id = uuid4()
        config = BudgetConfig(
            tenant_id=tenant_id,
            daily_limit=Decimal("100.00"),
        )

        status = BudgetStatus(
            tenant_id=tenant_id,
            config=config,
            daily_used=Decimal("95.00"),
            daily_remaining=Decimal("5.00"),
        )

        assert status.would_exceed(Decimal("10.00")) is True
        assert status.would_exceed(Decimal("3.00")) is False


# =============================================================================
# BudgetExceededError Tests
# =============================================================================


class TestBudgetExceededError:
    """Tests for BudgetExceededError exception."""

    def test_error_message(self):
        """Test error message format."""
        tenant_id = uuid4()
        status = BudgetStatus(
            tenant_id=tenant_id,
            config=None,
            daily_used=Decimal("110.00"),
            daily_exceeded=True,
        )

        error = BudgetExceededError(tenant_id, status)

        assert str(tenant_id) in str(error)
        assert "daily limit" in str(error)
        assert error.tenant_id == tenant_id
        assert error.status == status


# =============================================================================
# ProviderCostService Tests
# =============================================================================


class TestProviderCostService:
    """Tests for ProviderCostService class."""

    @pytest.fixture
    def service(self):
        """Create cost service."""
        return ProviderCostService()

    @pytest.fixture
    def tenant_id(self):
        """Create tenant ID."""
        return uuid4()

    @pytest.mark.asyncio
    async def test_record_cost(self, service, tenant_id):
        """Test recording a cost."""
        query_id = uuid4()

        record = await service.record_cost(
            query_id=query_id,
            provider_id="sterling",
            check_type="criminal_national",
            cost=Decimal("5.00"),
            tenant_id=tenant_id,
        )

        assert record.query_id == query_id
        assert record.provider_id == "sterling"
        assert record.cost_amount == Decimal("5.00")
        assert record.tenant_id == tenant_id
        assert record.cache_hit is False

    @pytest.mark.asyncio
    async def test_record_cost_with_screening(self, service, tenant_id):
        """Test recording cost with screening attribution."""
        screening_id = uuid4()

        record = await service.record_cost(
            query_id=uuid4(),
            provider_id="sterling",
            check_type="criminal_national",
            cost=Decimal("5.00"),
            tenant_id=tenant_id,
            screening_id=screening_id,
        )

        assert record.screening_id == screening_id

    @pytest.mark.asyncio
    async def test_record_cache_savings(self, service, tenant_id):
        """Test recording cache savings."""
        await service.record_cache_savings(
            query_id=uuid4(),
            provider_id="sterling",
            saved_amount=Decimal("5.00"),
            tenant_id=tenant_id,
        )

        total_savings = service.get_total_savings()
        assert total_savings == Decimal("5.00")

    @pytest.mark.asyncio
    async def test_get_tenant_costs(self, service, tenant_id):
        """Test getting tenant costs."""
        now = datetime.now(UTC)

        # Record some costs
        for i in range(5):
            await service.record_cost(
                query_id=uuid4(),
                provider_id="sterling",
                check_type="criminal_national",
                cost=Decimal("5.00"),
                tenant_id=tenant_id,
            )

        await service.record_cache_savings(
            query_id=uuid4(),
            provider_id="sterling",
            saved_amount=Decimal("10.00"),
            tenant_id=tenant_id,
        )

        summary = await service.get_tenant_costs(
            tenant_id=tenant_id,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )

        assert summary.total_cost == Decimal("25.00")
        assert summary.total_queries == 5
        assert summary.cache_savings == Decimal("10.00")
        assert "sterling" in summary.by_provider
        assert summary.by_provider["sterling"] == Decimal("25.00")

    @pytest.mark.asyncio
    async def test_get_provider_costs(self, service, tenant_id):
        """Test getting provider costs."""
        now = datetime.now(UTC)

        # Record costs for different providers
        for _ in range(3):
            await service.record_cost(
                query_id=uuid4(),
                provider_id="sterling",
                check_type="criminal_national",
                cost=Decimal("5.00"),
                tenant_id=tenant_id,
            )

        for _ in range(2):
            await service.record_cost(
                query_id=uuid4(),
                provider_id="checkr",
                check_type="criminal_national",
                cost=Decimal("4.00"),
                tenant_id=tenant_id,
            )

        summary = await service.get_provider_costs(
            provider_id="sterling",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )

        assert summary.total_cost == Decimal("15.00")
        assert summary.total_queries == 3

    @pytest.mark.asyncio
    async def test_set_budget(self, service, tenant_id):
        """Test setting budget."""
        config = BudgetConfig(
            tenant_id=tenant_id,
            monthly_limit=Decimal("1000.00"),
            daily_limit=Decimal("100.00"),
        )

        await service.set_budget(config)

        retrieved = await service.get_budget(tenant_id)
        assert retrieved is not None
        assert retrieved.monthly_limit == Decimal("1000.00")

    @pytest.mark.asyncio
    async def test_check_budget_no_config(self, service, tenant_id):
        """Test checking budget without configuration."""
        status = await service.check_budget(tenant_id)

        assert status.config is None
        assert status.is_exceeded is False
        assert status.hard_limit is False

    @pytest.mark.asyncio
    async def test_check_budget_within_limits(self, service, tenant_id):
        """Test checking budget within limits."""
        config = BudgetConfig(
            tenant_id=tenant_id,
            daily_limit=Decimal("100.00"),
        )
        await service.set_budget(config)

        # Record some usage
        await service.record_cost(
            query_id=uuid4(),
            provider_id="sterling",
            check_type="criminal",
            cost=Decimal("25.00"),
            tenant_id=tenant_id,
        )

        status = await service.check_budget(tenant_id)

        assert status.daily_used == Decimal("25.00")
        assert status.daily_remaining == Decimal("75.00")
        assert status.daily_exceeded is False
        assert status.daily_warning is False

    @pytest.mark.asyncio
    async def test_check_budget_warning(self, service, tenant_id):
        """Test budget warning threshold."""
        config = BudgetConfig(
            tenant_id=tenant_id,
            daily_limit=Decimal("100.00"),
            warning_threshold=0.8,
        )
        await service.set_budget(config)

        # Record usage past warning threshold
        await service.record_cost(
            query_id=uuid4(),
            provider_id="sterling",
            check_type="criminal",
            cost=Decimal("85.00"),
            tenant_id=tenant_id,
        )

        status = await service.check_budget(tenant_id)

        assert status.daily_warning is True
        assert status.daily_exceeded is False
        assert status.has_warning is True

    @pytest.mark.asyncio
    async def test_check_budget_exceeded(self, service, tenant_id):
        """Test budget exceeded."""
        config = BudgetConfig(
            tenant_id=tenant_id,
            daily_limit=Decimal("100.00"),
        )
        await service.set_budget(config)

        # Record usage past limit
        await service.record_cost(
            query_id=uuid4(),
            provider_id="sterling",
            check_type="criminal",
            cost=Decimal("110.00"),
            tenant_id=tenant_id,
        )

        status = await service.check_budget(tenant_id)

        assert status.daily_exceeded is True
        assert status.is_exceeded is True

    @pytest.mark.asyncio
    async def test_check_budget_or_raise_success(self, service, tenant_id):
        """Test check_budget_or_raise within limits."""
        config = BudgetConfig(
            tenant_id=tenant_id,
            daily_limit=Decimal("100.00"),
        )
        await service.set_budget(config)

        status = await service.check_budget_or_raise(tenant_id)
        assert status.is_exceeded is False

    @pytest.mark.asyncio
    async def test_check_budget_or_raise_exceeded(self, service, tenant_id):
        """Test check_budget_or_raise raises when exceeded."""
        config = BudgetConfig(
            tenant_id=tenant_id,
            daily_limit=Decimal("100.00"),
            hard_limit=True,
        )
        await service.set_budget(config)

        # Exceed limit
        await service.record_cost(
            query_id=uuid4(),
            provider_id="sterling",
            check_type="criminal",
            cost=Decimal("110.00"),
            tenant_id=tenant_id,
        )

        with pytest.raises(BudgetExceededError) as exc_info:
            await service.check_budget_or_raise(tenant_id)

        assert exc_info.value.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_check_budget_or_raise_soft_limit(self, service, tenant_id):
        """Test check_budget_or_raise with soft limit."""
        config = BudgetConfig(
            tenant_id=tenant_id,
            daily_limit=Decimal("100.00"),
            hard_limit=False,  # Soft limit
        )
        await service.set_budget(config)

        # Exceed limit
        await service.record_cost(
            query_id=uuid4(),
            provider_id="sterling",
            check_type="criminal",
            cost=Decimal("110.00"),
            tenant_id=tenant_id,
        )

        # Should not raise with soft limit
        status = await service.check_budget_or_raise(tenant_id)
        assert status.is_exceeded is True

    @pytest.mark.asyncio
    async def test_get_total_recorded(self, service, tenant_id):
        """Test getting total recorded costs."""
        for _ in range(3):
            await service.record_cost(
                query_id=uuid4(),
                provider_id="sterling",
                check_type="criminal",
                cost=Decimal("5.00"),
                tenant_id=tenant_id,
            )

        total = service.get_total_recorded()
        assert total == Decimal("15.00")

    def test_reset(self, service):
        """Test resetting service."""
        service._records.append(
            CostRecord(
                record_id=uuid4(),
                query_id=uuid4(),
                provider_id="test",
                check_type="test",
                tenant_id=uuid4(),
                cost_amount=Decimal("10.00"),
            )
        )

        service.reset()

        assert len(service._records) == 0
        assert len(service._budgets) == 0
        assert service.get_total_recorded() == Decimal("0.00")


# =============================================================================
# Global Service Tests
# =============================================================================


class TestGlobalCostService:
    """Tests for global cost service functions."""

    def test_get_cost_service(self):
        """Test getting global service."""
        reset_cost_service()
        service1 = get_cost_service()
        service2 = get_cost_service()
        assert service1 is service2

    def test_reset_cost_service(self):
        """Test resetting global service."""
        service1 = get_cost_service()
        reset_cost_service()
        service2 = get_cost_service()
        assert service1 is not service2


# =============================================================================
# Multi-Tenant Tests
# =============================================================================


class TestMultiTenant:
    """Tests for multi-tenant cost tracking."""

    @pytest.fixture
    def service(self):
        """Create cost service."""
        return ProviderCostService()

    @pytest.mark.asyncio
    async def test_costs_isolated_by_tenant(self, service):
        """Test that costs are isolated by tenant."""
        tenant_a = uuid4()
        tenant_b = uuid4()
        now = datetime.now(UTC)

        # Record costs for tenant A
        for _ in range(3):
            await service.record_cost(
                query_id=uuid4(),
                provider_id="sterling",
                check_type="criminal",
                cost=Decimal("5.00"),
                tenant_id=tenant_a,
            )

        # Record costs for tenant B
        for _ in range(2):
            await service.record_cost(
                query_id=uuid4(),
                provider_id="sterling",
                check_type="criminal",
                cost=Decimal("5.00"),
                tenant_id=tenant_b,
            )

        # Check tenant A
        summary_a = await service.get_tenant_costs(
            tenant_id=tenant_a,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )
        assert summary_a.total_cost == Decimal("15.00")
        assert summary_a.total_queries == 3

        # Check tenant B
        summary_b = await service.get_tenant_costs(
            tenant_id=tenant_b,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )
        assert summary_b.total_cost == Decimal("10.00")
        assert summary_b.total_queries == 2

    @pytest.mark.asyncio
    async def test_budgets_isolated_by_tenant(self, service):
        """Test that budgets are isolated by tenant."""
        tenant_a = uuid4()
        tenant_b = uuid4()

        # Set different budgets
        await service.set_budget(BudgetConfig(
            tenant_id=tenant_a,
            daily_limit=Decimal("100.00"),
        ))
        await service.set_budget(BudgetConfig(
            tenant_id=tenant_b,
            daily_limit=Decimal("500.00"),
        ))

        # Record costs
        await service.record_cost(
            query_id=uuid4(),
            provider_id="sterling",
            check_type="criminal",
            cost=Decimal("90.00"),
            tenant_id=tenant_a,
        )

        # Tenant A should be near limit
        status_a = await service.check_budget(tenant_a)
        assert status_a.daily_warning is True

        # Tenant B should be fine
        status_b = await service.check_budget(tenant_b)
        assert status_b.daily_warning is False
        assert status_b.daily_used == Decimal("0.00")
