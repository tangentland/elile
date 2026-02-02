"""Unit tests for Sanctions Update Scheduler.

Tests the SanctionsUpdateScheduler class including configuration,
update handlers, scheduling, and callbacks.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from elile.providers.sanctions import (
    ListUpdateConfig,
    ListUpdateResult,
    SanctionsList,
    SanctionsUpdateScheduler,
    UpdateFrequency,
    UpdateSchedulerConfig,
    create_update_scheduler,
    get_update_scheduler,
)

# =============================================================================
# UpdateFrequency Tests
# =============================================================================


class TestUpdateFrequency:
    """Tests for UpdateFrequency enum."""

    def test_hourly_value(self):
        """Test hourly frequency value."""
        assert UpdateFrequency.HOURLY.value == "hourly"
        assert UpdateFrequency.HOURLY.to_seconds() == 3600

    def test_every_4_hours_value(self):
        """Test 4-hour frequency value."""
        assert UpdateFrequency.EVERY_4_HOURS.value == "every_4_hours"
        assert UpdateFrequency.EVERY_4_HOURS.to_seconds() == 14400

    def test_every_12_hours_value(self):
        """Test 12-hour frequency value."""
        assert UpdateFrequency.EVERY_12_HOURS.value == "every_12_hours"
        assert UpdateFrequency.EVERY_12_HOURS.to_seconds() == 43200

    def test_daily_value(self):
        """Test daily frequency value."""
        assert UpdateFrequency.DAILY.value == "daily"
        assert UpdateFrequency.DAILY.to_seconds() == 86400

    def test_weekly_value(self):
        """Test weekly frequency value."""
        assert UpdateFrequency.WEEKLY.value == "weekly"
        assert UpdateFrequency.WEEKLY.to_seconds() == 604800


# =============================================================================
# ListUpdateConfig Tests
# =============================================================================


class TestListUpdateConfig:
    """Tests for ListUpdateConfig model."""

    def test_create_with_defaults(self):
        """Test creating config with defaults."""
        config = ListUpdateConfig(list_source=SanctionsList.OFAC_SDN)
        assert config.list_source == SanctionsList.OFAC_SDN
        assert config.frequency == UpdateFrequency.DAILY
        assert config.enabled is True
        assert config.retry_attempts == 3
        assert config.retry_delay_seconds == 60

    def test_create_with_custom_values(self):
        """Test creating config with custom values."""
        config = ListUpdateConfig(
            list_source=SanctionsList.UN_CONSOLIDATED,
            frequency=UpdateFrequency.HOURLY,
            enabled=False,
            url="https://api.example.com/un",
            api_key_env="UN_API_KEY",
            retry_attempts=5,
            retry_delay_seconds=120,
        )
        assert config.list_source == SanctionsList.UN_CONSOLIDATED
        assert config.frequency == UpdateFrequency.HOURLY
        assert config.enabled is False
        assert config.url == "https://api.example.com/un"
        assert config.api_key_env == "UN_API_KEY"
        assert config.retry_attempts == 5


# =============================================================================
# UpdateSchedulerConfig Tests
# =============================================================================


class TestUpdateSchedulerConfig:
    """Tests for UpdateSchedulerConfig model."""

    def test_create_with_defaults(self):
        """Test creating config with defaults."""
        config = UpdateSchedulerConfig()
        assert config.enabled is True
        assert config.list_configs == []
        assert config.default_frequency == UpdateFrequency.DAILY
        assert config.max_concurrent_updates == 3

    def test_create_with_list_configs(self):
        """Test creating config with list configs."""
        list_config = ListUpdateConfig(
            list_source=SanctionsList.OFAC_SDN,
            frequency=UpdateFrequency.HOURLY,
        )
        config = UpdateSchedulerConfig(list_configs=[list_config])
        assert len(config.list_configs) == 1


# =============================================================================
# ListUpdateResult Tests
# =============================================================================


class TestListUpdateResult:
    """Tests for ListUpdateResult model."""

    def test_create_success_result(self):
        """Test creating successful update result."""
        now = datetime.now(UTC)
        result = ListUpdateResult(
            list_source=SanctionsList.OFAC_SDN,
            success=True,
            entities_count=1000,
            entities_added=10,
            entities_removed=5,
            entities_modified=3,
            started_at=now,
            completed_at=now,
            duration_seconds=5.5,
        )
        assert result.success is True
        assert result.entities_count == 1000
        assert result.entities_added == 10

    def test_create_failure_result(self):
        """Test creating failed update result."""
        now = datetime.now(UTC)
        result = ListUpdateResult(
            list_source=SanctionsList.OFAC_SDN,
            success=False,
            started_at=now,
            completed_at=now,
            error_message="Connection timeout",
        )
        assert result.success is False
        assert result.error_message == "Connection timeout"


# =============================================================================
# SanctionsUpdateScheduler Initialization Tests
# =============================================================================


class TestSchedulerInitialization:
    """Tests for SanctionsUpdateScheduler initialization."""

    def test_create_with_defaults(self):
        """Test creating scheduler with default config."""
        scheduler = SanctionsUpdateScheduler()
        assert scheduler.is_running is False
        assert scheduler.config.enabled is True

    def test_create_with_config(self):
        """Test creating scheduler with custom config."""
        config = UpdateSchedulerConfig(
            enabled=False,
            default_frequency=UpdateFrequency.HOURLY,
        )
        scheduler = SanctionsUpdateScheduler(config)
        assert scheduler.config.enabled is False
        assert scheduler.config.default_frequency == UpdateFrequency.HOURLY

    def test_factory_function(self):
        """Test create_update_scheduler factory."""
        scheduler = create_update_scheduler()
        assert isinstance(scheduler, SanctionsUpdateScheduler)


# =============================================================================
# Handler Registration Tests
# =============================================================================


class TestHandlerRegistration:
    """Tests for update handler registration."""

    def test_register_handler(self):
        """Test registering an update handler."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(return_value={"entities_count": 100})
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)
        assert SanctionsList.OFAC_SDN in scheduler._update_handlers

    def test_register_multiple_handlers(self):
        """Test registering multiple handlers."""
        scheduler = SanctionsUpdateScheduler()
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler1)
        scheduler.register_update_handler(SanctionsList.UN_CONSOLIDATED, handler2)
        assert len(scheduler._update_handlers) == 2


# =============================================================================
# Callback Tests
# =============================================================================


class TestCallbacks:
    """Tests for scheduler callbacks."""

    def test_set_on_update_callback(self):
        """Test setting update callback."""
        scheduler = SanctionsUpdateScheduler()
        callback = MagicMock()
        scheduler.set_on_update_callback(callback)
        assert scheduler._on_update_callback is callback

    def test_set_on_error_callback(self):
        """Test setting error callback."""
        scheduler = SanctionsUpdateScheduler()
        callback = MagicMock()
        scheduler.set_on_error_callback(callback)
        assert scheduler._on_error_callback is callback


# =============================================================================
# Trigger Update Tests
# =============================================================================


class TestTriggerUpdate:
    """Tests for manual update triggering."""

    @pytest.mark.asyncio
    async def test_trigger_update_no_handler(self):
        """Test triggering update with no handler."""
        scheduler = SanctionsUpdateScheduler()
        result = await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        assert result.success is False
        assert "No handler" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_trigger_update_success(self):
        """Test triggering successful update."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(
            return_value={
                "entities_count": 100,
                "entities_added": 5,
            }
        )
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        result = await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        assert result.success is True
        assert result.entities_count == 100
        assert result.entities_added == 5
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_update_with_error(self):
        """Test triggering update that fails."""
        config = UpdateSchedulerConfig()
        scheduler = SanctionsUpdateScheduler(config)
        handler = AsyncMock(side_effect=Exception("API error"))
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        # Set retry attempts to 0 for faster test
        scheduler._list_configs[SanctionsList.OFAC_SDN] = ListUpdateConfig(
            list_source=SanctionsList.OFAC_SDN,
            retry_attempts=0,
        )

        result = await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        assert result.success is False
        assert "API error" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_trigger_update_skips_recent(self):
        """Test triggering update skips if recently updated."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(return_value={})
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        # First update
        await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        assert handler.call_count == 1

        # Second update without force - should skip
        result = await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        assert "recently updated" in (result.error_message or "").lower()

    @pytest.mark.asyncio
    async def test_trigger_update_force(self):
        """Test forcing update even if recently updated."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(return_value={})
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        # First update
        await scheduler.trigger_update(SanctionsList.OFAC_SDN)

        # Force second update
        await scheduler.trigger_update(SanctionsList.OFAC_SDN, force=True)
        assert handler.call_count == 2

    @pytest.mark.asyncio
    async def test_trigger_all_updates(self):
        """Test triggering all updates."""
        scheduler = SanctionsUpdateScheduler()
        handler1 = AsyncMock(return_value={"entities_count": 100})
        handler2 = AsyncMock(return_value={"entities_count": 200})
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler1)
        scheduler.register_update_handler(SanctionsList.UN_CONSOLIDATED, handler2)

        results = await scheduler.trigger_all_updates()
        assert len(results) == 2
        assert all(r.success for r in results)


# =============================================================================
# Callback Invocation Tests
# =============================================================================


class TestCallbackInvocation:
    """Tests for callback invocation during updates."""

    @pytest.mark.asyncio
    async def test_on_update_callback_called(self):
        """Test update callback is called on success."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(return_value={"entities_count": 100})
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        callback = MagicMock()
        scheduler.set_on_update_callback(callback)

        await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        callback.assert_called_once()
        result = callback.call_args[0][0]
        assert isinstance(result, ListUpdateResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_on_error_callback_called(self):
        """Test error callback is called on failure."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(side_effect=Exception("Test error"))
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        # Set retry attempts to 0
        scheduler._list_configs[SanctionsList.OFAC_SDN] = ListUpdateConfig(
            list_source=SanctionsList.OFAC_SDN,
            retry_attempts=0,
        )

        error_callback = MagicMock()
        scheduler.set_on_error_callback(error_callback)

        await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        error_callback.assert_called_once()
        call_args = error_callback.call_args[0]
        assert call_args[0] == SanctionsList.OFAC_SDN
        assert isinstance(call_args[1], Exception)


# =============================================================================
# Status and Tracking Tests
# =============================================================================


class TestStatusTracking:
    """Tests for status and update tracking."""

    @pytest.mark.asyncio
    async def test_get_last_update(self):
        """Test getting last update time."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(return_value={})
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        # Initially None
        assert scheduler.get_last_update(SanctionsList.OFAC_SDN) is None

        # After update
        await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        last_update = scheduler.get_last_update(SanctionsList.OFAC_SDN)
        assert last_update is not None
        assert isinstance(last_update, datetime)

    @pytest.mark.asyncio
    async def test_get_update_result(self):
        """Test getting update result."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(return_value={"entities_count": 50})
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        # Initially None
        assert scheduler.get_update_result(SanctionsList.OFAC_SDN) is None

        # After update
        await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        result = scheduler.get_update_result(SanctionsList.OFAC_SDN)
        assert result is not None
        assert result.success is True
        assert result.entities_count == 50

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting scheduler status."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(return_value={"entities_count": 100})
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        status = scheduler.get_status()
        assert "running" in status
        assert "enabled" in status
        assert "registered_handlers" in status
        assert status["registered_handlers"] == 1


# =============================================================================
# Start/Stop Tests
# =============================================================================


class TestStartStop:
    """Tests for scheduler start and stop."""

    @pytest.mark.asyncio
    async def test_start_disabled_scheduler(self):
        """Test starting disabled scheduler."""
        config = UpdateSchedulerConfig(enabled=False)
        scheduler = SanctionsUpdateScheduler(config)
        await scheduler.start()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """Test starting and stopping scheduler."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(return_value={})
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        await scheduler.start()
        assert scheduler.is_running is True
        assert len(scheduler._tasks) == 1

        await scheduler.stop()
        assert scheduler.is_running is False
        assert len(scheduler._tasks) == 0

    @pytest.mark.asyncio
    async def test_start_twice(self):
        """Test starting scheduler twice."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(return_value={})
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        await scheduler.start()
        await scheduler.start()  # Should log warning but not error
        assert scheduler.is_running is True

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        """Test stopping scheduler that's not running."""
        scheduler = SanctionsUpdateScheduler()
        await scheduler.stop()  # Should not error
        assert scheduler.is_running is False


# =============================================================================
# Retry Tests
# =============================================================================


class TestRetryLogic:
    """Tests for retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test retry behavior on failure."""
        scheduler = SanctionsUpdateScheduler()

        # Handler fails twice then succeeds
        handler = AsyncMock(
            side_effect=[
                Exception("First failure"),
                Exception("Second failure"),
                {"entities_count": 100},
            ]
        )
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        # Configure 2 retries with minimal delay
        scheduler._list_configs[SanctionsList.OFAC_SDN] = ListUpdateConfig(
            list_source=SanctionsList.OFAC_SDN,
            retry_attempts=2,
            retry_delay_seconds=0,
        )

        result = await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        assert result.success is True
        assert handler.call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test behavior when max retries exceeded."""
        scheduler = SanctionsUpdateScheduler()
        handler = AsyncMock(side_effect=Exception("Always fails"))
        scheduler.register_update_handler(SanctionsList.OFAC_SDN, handler)

        # Configure 1 retry with minimal delay
        scheduler._list_configs[SanctionsList.OFAC_SDN] = ListUpdateConfig(
            list_source=SanctionsList.OFAC_SDN,
            retry_attempts=1,
            retry_delay_seconds=0,
        )

        result = await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        assert result.success is False
        assert handler.call_count == 2  # Initial + 1 retry


# =============================================================================
# Concurrent Update Tests
# =============================================================================


class TestConcurrentUpdates:
    """Tests for concurrent update limiting."""

    @pytest.mark.asyncio
    async def test_max_concurrent_updates(self):
        """Test max concurrent updates is respected when scheduler is started."""
        config = UpdateSchedulerConfig(max_concurrent_updates=2)
        scheduler = SanctionsUpdateScheduler(config)

        # Track concurrent execution
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def slow_handler():
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.1)  # Simulate work
            async with lock:
                current_concurrent -= 1
            return {"entities_count": 10}

        # Register 4 handlers
        for lst in [
            SanctionsList.OFAC_SDN,
            SanctionsList.UN_CONSOLIDATED,
            SanctionsList.EU_CONSOLIDATED,
            SanctionsList.WORLD_PEP,
        ]:
            scheduler.register_update_handler(lst, slow_handler)

        # Start scheduler to initialize semaphore
        # Note: start() creates update loop tasks, so we need to stop quickly
        # Instead, manually initialize semaphore for testing
        scheduler._semaphore = asyncio.Semaphore(config.max_concurrent_updates)

        # Trigger all updates
        await scheduler.trigger_all_updates(force=True)

        # Max concurrent should be <= 2
        assert max_concurrent <= 2


# =============================================================================
# Sync Handler Tests
# =============================================================================


class TestSyncHandlers:
    """Tests for synchronous handlers."""

    @pytest.mark.asyncio
    async def test_sync_handler_works(self):
        """Test synchronous handler is supported."""
        scheduler = SanctionsUpdateScheduler()

        def sync_handler():
            return {"entities_count": 42}

        scheduler.register_update_handler(SanctionsList.OFAC_SDN, sync_handler)
        result = await scheduler.trigger_update(SanctionsList.OFAC_SDN)
        assert result.success is True
        assert result.entities_count == 42


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_update_scheduler_singleton(self):
        """Test get_update_scheduler returns singleton."""
        import elile.providers.sanctions.scheduler as scheduler_module

        scheduler_module._scheduler_instance = None

        scheduler1 = get_update_scheduler()
        scheduler2 = get_update_scheduler()
        assert scheduler1 is scheduler2

        # Clean up
        scheduler_module._scheduler_instance = None

    def test_create_update_scheduler_new_instance(self):
        """Test create_update_scheduler returns new instance."""
        scheduler1 = create_update_scheduler()
        scheduler2 = create_update_scheduler()
        assert scheduler1 is not scheduler2
