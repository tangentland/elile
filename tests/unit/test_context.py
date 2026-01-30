"""Unit tests for Request Context Framework."""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4, uuid7

import pytest

from elile.agent.state import SearchDegree, ServiceTier
from elile.core.context import (
    ActorType,
    CacheScope,
    RequestContext,
    create_context,
    get_current_context,
    get_current_context_or_none,
    request_context,
    reset_context,
    set_context,
)
from elile.core.exceptions import (
    BudgetExceededError,
    ComplianceError,
    ConsentExpiredError,
    ConsentScopeError,
    ContextNotSetError,
)


class TestRequestContextCreation:
    """Tests for RequestContext creation and validation."""

    def test_create_context_minimal(self):
        """Test creating context with minimal required fields."""
        tenant_id = uuid7()
        actor_id = uuid7()

        ctx = create_context(tenant_id=tenant_id, actor_id=actor_id)

        assert ctx.tenant_id == tenant_id
        assert ctx.actor_id == actor_id
        assert ctx.actor_type == ActorType.HUMAN
        assert ctx.locale == "US"
        assert ctx.service_tier == ServiceTier.STANDARD
        assert ctx.investigation_degree == SearchDegree.D1
        assert ctx.cache_scope == CacheScope.TENANT_ISOLATED
        assert ctx.request_id is not None
        assert ctx.correlation_id is not None
        assert ctx.initiated_at is not None
        assert ctx.budget_limit is None
        assert ctx.cost_accumulated == 0.0

    def test_create_context_full(self):
        """Test creating context with all fields."""
        tenant_id = uuid7()
        actor_id = uuid7()
        consent_token = uuid7()
        correlation_id = uuid7()
        consent_expiry = datetime.now(timezone.utc) + timedelta(hours=24)

        ctx = create_context(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_type=ActorType.SERVICE,
            locale="EU",
            permitted_checks={"identity", "employment"},
            permitted_sources={"provider_a", "provider_b"},
            consent_token=consent_token,
            consent_scope={"identity", "employment", "education"},
            consent_expiry=consent_expiry,
            service_tier=ServiceTier.ENHANCED,
            investigation_degree=SearchDegree.D2,
            correlation_id=correlation_id,
            budget_limit=100.0,
            cache_scope=CacheScope.SHARED,
        )

        assert ctx.tenant_id == tenant_id
        assert ctx.actor_id == actor_id
        assert ctx.actor_type == ActorType.SERVICE
        assert ctx.locale == "EU"
        assert ctx.permitted_checks == {"identity", "employment"}
        assert ctx.permitted_sources == {"provider_a", "provider_b"}
        assert ctx.consent_token == consent_token
        assert ctx.consent_scope == {"identity", "employment", "education"}
        assert ctx.consent_expiry == consent_expiry
        assert ctx.service_tier == ServiceTier.ENHANCED
        assert ctx.investigation_degree == SearchDegree.D2
        assert ctx.correlation_id == correlation_id
        assert ctx.budget_limit == 100.0
        assert ctx.cache_scope == CacheScope.SHARED

    def test_request_context_direct_creation(self):
        """Test creating RequestContext directly."""
        tenant_id = uuid7()
        actor_id = uuid7()

        ctx = RequestContext(tenant_id=tenant_id, actor_id=actor_id)

        assert ctx.tenant_id == tenant_id
        assert ctx.actor_id == actor_id

    def test_consent_validation_requires_scope(self):
        """Test that consent_token requires consent_scope."""
        tenant_id = uuid7()
        actor_id = uuid7()
        consent_token = uuid7()
        consent_expiry = datetime.now(timezone.utc) + timedelta(hours=24)

        with pytest.raises(ValueError, match="consent_scope required"):
            RequestContext(
                tenant_id=tenant_id,
                actor_id=actor_id,
                consent_token=consent_token,
                consent_expiry=consent_expiry,
                # consent_scope is missing
            )

    def test_consent_validation_requires_expiry(self):
        """Test that consent_token requires consent_expiry."""
        tenant_id = uuid7()
        actor_id = uuid7()
        consent_token = uuid7()

        with pytest.raises(ValueError, match="consent_expiry required"):
            RequestContext(
                tenant_id=tenant_id,
                actor_id=actor_id,
                consent_token=consent_token,
                consent_scope={"identity"},
                # consent_expiry is missing
            )


class TestContextAssertions:
    """Tests for RequestContext assertion methods."""

    def test_assert_check_permitted_success(self):
        """Test assert_check_permitted with allowed check."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            permitted_checks={"identity", "employment", "education"},
        )

        # Should not raise
        ctx.assert_check_permitted("identity")
        ctx.assert_check_permitted("employment")
        ctx.assert_check_permitted("education")

    def test_assert_check_permitted_failure(self):
        """Test assert_check_permitted with disallowed check."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            locale="EU",
            permitted_checks={"identity", "employment"},
        )

        with pytest.raises(ComplianceError) as exc_info:
            ctx.assert_check_permitted("criminal_records")

        assert exc_info.value.check_type == "criminal_records"
        assert exc_info.value.locale == "EU"
        assert "not permitted" in str(exc_info.value)

    def test_assert_check_permitted_empty_allows_all(self):
        """Test that empty permitted_checks allows all checks."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            permitted_checks=set(),
        )

        # Should not raise for any check type
        ctx.assert_check_permitted("anything")
        ctx.assert_check_permitted("criminal_records")

    def test_assert_source_permitted_success(self):
        """Test assert_source_permitted with allowed source."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            permitted_sources={"checkr", "sterling"},
        )

        ctx.assert_source_permitted("checkr")
        ctx.assert_source_permitted("sterling")

    def test_assert_source_permitted_failure(self):
        """Test assert_source_permitted with disallowed source."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            locale="US",
            permitted_sources={"checkr"},
        )

        with pytest.raises(ComplianceError) as exc_info:
            ctx.assert_source_permitted("unknown_provider")

        assert exc_info.value.check_type == "unknown_provider"
        assert exc_info.value.locale == "US"

    def test_assert_budget_available_success(self):
        """Test assert_budget_available within budget."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            budget_limit=100.0,
        )

        # Should not raise
        ctx.assert_budget_available(50.0)
        ctx.assert_budget_available(100.0)

    def test_assert_budget_available_failure(self):
        """Test assert_budget_available exceeding budget."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            budget_limit=100.0,
        )
        ctx.cost_accumulated = 80.0

        with pytest.raises(BudgetExceededError) as exc_info:
            ctx.assert_budget_available(30.0)

        assert exc_info.value.cost == 30.0
        assert exc_info.value.budget_limit == 100.0
        assert exc_info.value.accumulated == 80.0

    def test_assert_budget_available_no_limit(self):
        """Test assert_budget_available with no limit allows any cost."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            budget_limit=None,
        )

        # Should not raise for any amount
        ctx.assert_budget_available(1000000.0)

    def test_assert_consent_valid_success(self):
        """Test assert_consent_valid with valid consent."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            consent_token=uuid7(),
            consent_scope={"identity"},
            consent_expiry=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        # Should not raise
        ctx.assert_consent_valid()

    def test_assert_consent_valid_expired(self):
        """Test assert_consent_valid with expired consent."""
        consent_token = uuid7()
        consent_expiry = datetime.now(timezone.utc) - timedelta(hours=1)

        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            consent_token=consent_token,
            consent_scope={"identity"},
            consent_expiry=consent_expiry,
        )

        with pytest.raises(ConsentExpiredError) as exc_info:
            ctx.assert_consent_valid()

        assert exc_info.value.consent_token == consent_token
        assert exc_info.value.expiry == consent_expiry

    def test_assert_consent_valid_no_consent(self):
        """Test assert_consent_valid with no consent set."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
        )

        # Should not raise when no consent is required
        ctx.assert_consent_valid()

    def test_assert_consent_scope_success(self):
        """Test assert_consent_scope with valid scope."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            consent_token=uuid7(),
            consent_scope={"identity", "employment", "education"},
            consent_expiry=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        ctx.assert_consent_scope("identity")
        ctx.assert_consent_scope("employment")

    def test_assert_consent_scope_failure(self):
        """Test assert_consent_scope with invalid scope."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            consent_token=uuid7(),
            consent_scope={"identity", "employment"},
            consent_expiry=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        with pytest.raises(ConsentScopeError) as exc_info:
            ctx.assert_consent_scope("criminal_records")

        assert exc_info.value.required_scope == "criminal_records"
        assert exc_info.value.granted_scope == {"identity", "employment"}

    def test_assert_consent_scope_empty_allows_all(self):
        """Test that empty consent_scope allows all data types."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
        )

        # Should not raise
        ctx.assert_consent_scope("anything")


class TestCostTracking:
    """Tests for cost recording and accumulation."""

    def test_record_cost_accumulates(self):
        """Test that record_cost accumulates costs."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
        )

        assert ctx.cost_accumulated == 0.0

        ctx.record_cost(10.0)
        assert ctx.cost_accumulated == 10.0

        ctx.record_cost(25.0)
        assert ctx.cost_accumulated == 35.0

        ctx.record_cost(5.5)
        assert ctx.cost_accumulated == 40.5

    def test_record_cost_exceeds_budget(self):
        """Test that record_cost allows exceeding budget (after the fact)."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            budget_limit=100.0,
        )

        ctx.cost_accumulated = 90.0

        # record_cost doesn't check budget - it just records
        ctx.record_cost(50.0)
        assert ctx.cost_accumulated == 140.0


class TestToAuditDict:
    """Tests for to_audit_dict method."""

    def test_to_audit_dict_basic(self):
        """Test to_audit_dict returns expected fields."""
        tenant_id = uuid7()
        actor_id = uuid7()
        correlation_id = uuid7()

        ctx = create_context(
            tenant_id=tenant_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            locale="EU",
            service_tier=ServiceTier.ENHANCED,
            investigation_degree=SearchDegree.D2,
            budget_limit=500.0,
        )
        ctx.cost_accumulated = 123.45

        audit_dict = ctx.to_audit_dict()

        assert audit_dict["tenant_id"] == str(tenant_id)
        assert audit_dict["actor_id"] == str(actor_id)
        assert audit_dict["correlation_id"] == str(correlation_id)
        assert audit_dict["locale"] == "EU"
        assert audit_dict["service_tier"] == "enhanced"
        assert audit_dict["investigation_degree"] == "d2"
        assert audit_dict["budget_limit"] == 500.0
        assert audit_dict["cost_accumulated"] == 123.45
        assert audit_dict["actor_type"] == "human"
        assert audit_dict["cache_scope"] == "tenant_isolated"
        assert audit_dict["request_id"] is not None
        assert audit_dict["initiated_at"] is not None

    def test_to_audit_dict_with_consent(self):
        """Test to_audit_dict includes consent info."""
        consent_token = uuid7()

        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            consent_token=consent_token,
            consent_scope={"identity"},
            consent_expiry=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        audit_dict = ctx.to_audit_dict()
        assert audit_dict["consent_token"] == str(consent_token)

    def test_to_audit_dict_no_consent(self):
        """Test to_audit_dict handles None consent."""
        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
        )

        audit_dict = ctx.to_audit_dict()
        assert audit_dict["consent_token"] is None


class TestContextManager:
    """Tests for context manager functionality."""

    def test_request_context_sets_and_restores(self):
        """Test that request_context sets and restores context."""
        # Initially no context
        assert get_current_context_or_none() is None

        ctx = create_context(tenant_id=uuid7(), actor_id=uuid7())

        with request_context(ctx):
            current = get_current_context()
            assert current is ctx
            assert current.tenant_id == ctx.tenant_id

        # After context manager, context should be None again
        assert get_current_context_or_none() is None

    def test_nested_contexts(self):
        """Test nested context managers restore correctly."""
        outer_tenant = uuid7()
        inner_tenant = uuid7()

        outer_ctx = create_context(tenant_id=outer_tenant, actor_id=uuid7())
        inner_ctx = create_context(tenant_id=inner_tenant, actor_id=uuid7())

        with request_context(outer_ctx):
            assert get_current_context().tenant_id == outer_tenant

            with request_context(inner_ctx):
                assert get_current_context().tenant_id == inner_tenant

            # Back to outer context
            assert get_current_context().tenant_id == outer_tenant

        # No context
        assert get_current_context_or_none() is None

    def test_context_exception_restores(self):
        """Test that context is restored even when exception occurs."""
        ctx = create_context(tenant_id=uuid7(), actor_id=uuid7())

        with pytest.raises(ValueError):
            with request_context(ctx):
                assert get_current_context() is ctx
                raise ValueError("Test error")

        # Context should still be restored
        assert get_current_context_or_none() is None

    def test_get_current_context_raises_when_not_set(self):
        """Test get_current_context raises ContextNotSetError."""
        # Ensure no context
        assert get_current_context_or_none() is None

        with pytest.raises(ContextNotSetError) as exc_info:
            get_current_context()

        assert "request_context()" in str(exc_info.value)

    def test_set_and_reset_context_low_level(self):
        """Test low-level set_context and reset_context."""
        ctx = create_context(tenant_id=uuid7(), actor_id=uuid7())

        token = set_context(ctx)
        assert get_current_context() is ctx

        reset_context(token)
        assert get_current_context_or_none() is None


class TestAsyncContextIsolation:
    """Tests for async context isolation."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test context manager works in async code."""
        ctx = create_context(tenant_id=uuid7(), actor_id=uuid7())

        # Context manager works in async
        with request_context(ctx):
            current = get_current_context()
            assert current is ctx

            # Can await things inside
            await asyncio.sleep(0)
            assert get_current_context() is ctx

        assert get_current_context_or_none() is None

    @pytest.mark.asyncio
    async def test_context_isolated_across_tasks(self):
        """Test that context is isolated across concurrent async tasks."""
        tenant1 = uuid7()
        tenant2 = uuid7()

        results = {}

        async def task1():
            ctx = create_context(tenant_id=tenant1, actor_id=uuid7())
            with request_context(ctx):
                results["task1_start"] = get_current_context().tenant_id
                await asyncio.sleep(0.01)  # Yield to other task
                results["task1_end"] = get_current_context().tenant_id

        async def task2():
            ctx = create_context(tenant_id=tenant2, actor_id=uuid7())
            with request_context(ctx):
                results["task2_start"] = get_current_context().tenant_id
                await asyncio.sleep(0.01)  # Yield to other task
                results["task2_end"] = get_current_context().tenant_id

        await asyncio.gather(task1(), task2())

        # Each task should maintain its own context
        assert results["task1_start"] == tenant1
        assert results["task1_end"] == tenant1
        assert results["task2_start"] == tenant2
        assert results["task2_end"] == tenant2

    @pytest.mark.asyncio
    async def test_context_propagates_to_subtask(self):
        """Test that context propagates to subtasks created within context."""
        tenant_id = uuid7()
        ctx = create_context(tenant_id=tenant_id, actor_id=uuid7())

        results = {}

        async def subtask():
            # Context should be visible in subtask
            current = get_current_context_or_none()
            results["subtask_context"] = current.tenant_id if current else None

        with request_context(ctx):
            # Create a task within the context
            await subtask()

        assert results["subtask_context"] == tenant_id


class TestEnums:
    """Tests for enum values."""

    def test_actor_type_values(self):
        """Test ActorType enum values."""
        assert ActorType.HUMAN.value == "human"
        assert ActorType.SERVICE.value == "service"
        assert ActorType.SYSTEM.value == "system"

    def test_cache_scope_values(self):
        """Test CacheScope enum values."""
        assert CacheScope.SHARED.value == "shared"
        assert CacheScope.TENANT_ISOLATED.value == "tenant_isolated"
