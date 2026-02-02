"""Sanctions list update scheduler.

This module provides scheduled updates for sanctions lists from various
sources including OFAC, UN, EU, and other watchlist providers.
"""

import asyncio
import inspect
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from elile.core.logging import get_logger

from .types import SanctionsList

logger = get_logger(__name__)


class UpdateFrequency(str, Enum):
    """Update frequency for sanctions lists."""

    HOURLY = "hourly"
    EVERY_4_HOURS = "every_4_hours"
    EVERY_12_HOURS = "every_12_hours"
    DAILY = "daily"
    WEEKLY = "weekly"

    def to_seconds(self) -> int:
        """Convert frequency to seconds."""
        mapping = {
            UpdateFrequency.HOURLY: 3600,
            UpdateFrequency.EVERY_4_HOURS: 14400,
            UpdateFrequency.EVERY_12_HOURS: 43200,
            UpdateFrequency.DAILY: 86400,
            UpdateFrequency.WEEKLY: 604800,
        }
        return mapping[self]


class ListUpdateConfig(BaseModel):
    """Configuration for a single list update.

    Attributes:
        list_source: The sanctions list to update.
        frequency: How often to update the list.
        enabled: Whether updates are enabled.
        url: Optional custom URL for the list data.
        api_key_env: Environment variable name for API key.
        retry_attempts: Number of retry attempts on failure.
        retry_delay_seconds: Delay between retries.
    """

    list_source: SanctionsList
    frequency: UpdateFrequency = UpdateFrequency.DAILY
    enabled: bool = True
    url: str | None = None
    api_key_env: str | None = None
    retry_attempts: int = Field(ge=0, default=3)
    retry_delay_seconds: int = Field(ge=0, default=60)


class UpdateSchedulerConfig(BaseModel):
    """Configuration for the sanctions update scheduler.

    Attributes:
        enabled: Whether the scheduler is enabled.
        list_configs: Configuration for each list.
        default_frequency: Default update frequency for unconfigured lists.
        on_update_callback: Optional callback after successful update.
        on_error_callback: Optional callback on update error.
        max_concurrent_updates: Maximum concurrent list updates.
    """

    enabled: bool = True
    list_configs: list[ListUpdateConfig] = Field(default_factory=list)
    default_frequency: UpdateFrequency = UpdateFrequency.DAILY
    max_concurrent_updates: int = Field(ge=1, default=3)


class ListUpdateResult(BaseModel):
    """Result of a list update operation.

    Attributes:
        list_source: Which list was updated.
        success: Whether the update succeeded.
        entities_count: Number of entities in the list.
        entities_added: Number of new entities added.
        entities_removed: Number of entities removed.
        entities_modified: Number of entities modified.
        started_at: When the update started.
        completed_at: When the update completed.
        duration_seconds: How long the update took.
        error_message: Error message if failed.
    """

    list_source: SanctionsList
    success: bool
    entities_count: int = 0
    entities_added: int = 0
    entities_removed: int = 0
    entities_modified: int = 0
    started_at: datetime
    completed_at: datetime
    duration_seconds: float = 0.0
    error_message: str | None = None


class SanctionsUpdateScheduler:
    """Scheduler for sanctions list updates.

    Manages periodic updates to sanctions lists from various sources.
    Supports configurable update frequencies per list, retry logic,
    and callbacks for monitoring.

    Usage:
        scheduler = SanctionsUpdateScheduler()

        # Register update handler
        scheduler.register_update_handler(
            SanctionsList.OFAC_SDN,
            my_update_handler,
        )

        # Start the scheduler
        await scheduler.start()

        # Stop when done
        await scheduler.stop()
    """

    def __init__(self, config: UpdateSchedulerConfig | None = None) -> None:
        """Initialize the scheduler.

        Args:
            config: Optional scheduler configuration.
        """
        self._config = config or UpdateSchedulerConfig()
        self._running = False
        self._tasks: dict[SanctionsList, asyncio.Task[None]] = {}
        self._update_handlers: dict[SanctionsList, Callable[[], Any]] = {}
        self._last_updates: dict[SanctionsList, datetime] = {}
        self._update_results: dict[SanctionsList, ListUpdateResult] = {}
        self._on_update_callback: Callable[[ListUpdateResult], Any] | None = None
        self._on_error_callback: Callable[[SanctionsList, Exception], Any] | None = None
        self._semaphore: asyncio.Semaphore | None = None

        # Build list config lookup
        self._list_configs: dict[SanctionsList, ListUpdateConfig] = {
            cfg.list_source: cfg for cfg in self._config.list_configs
        }

        logger.info(
            "sanctions_scheduler_initialized",
            enabled=self._config.enabled,
            configured_lists=len(self._list_configs),
        )

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._running

    @property
    def config(self) -> UpdateSchedulerConfig:
        """Get the scheduler configuration."""
        return self._config

    def register_update_handler(
        self,
        list_source: SanctionsList,
        handler: Callable[[], Any],
    ) -> None:
        """Register an update handler for a list.

        The handler is called when the list needs to be updated.
        It should fetch and process the list data.

        Args:
            list_source: The list to handle updates for.
            handler: Async callable that performs the update.
        """
        self._update_handlers[list_source] = handler
        logger.info(
            "update_handler_registered",
            list_source=list_source.value,
        )

    def set_on_update_callback(
        self,
        callback: Callable[[ListUpdateResult], Any],
    ) -> None:
        """Set callback for successful updates.

        Args:
            callback: Callback function receiving update result.
        """
        self._on_update_callback = callback

    def set_on_error_callback(
        self,
        callback: Callable[[SanctionsList, Exception], Any],
    ) -> None:
        """Set callback for update errors.

        Args:
            callback: Callback function receiving list and exception.
        """
        self._on_error_callback = callback

    async def start(self) -> None:
        """Start the scheduler.

        Begins periodic updates for all registered lists.
        """
        if not self._config.enabled:
            logger.warning("sanctions_scheduler_disabled")
            return

        if self._running:
            logger.warning("sanctions_scheduler_already_running")
            return

        self._running = True
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_updates)

        # Start update tasks for each registered handler
        for list_source in self._update_handlers:
            config = self._get_list_config(list_source)
            if config.enabled:
                task = asyncio.create_task(
                    self._update_loop(list_source),
                    name=f"sanctions_update_{list_source.value}",
                )
                self._tasks[list_source] = task

        logger.info(
            "sanctions_scheduler_started",
            active_lists=len(self._tasks),
        )

    async def stop(self) -> None:
        """Stop the scheduler.

        Cancels all pending update tasks.
        """
        if not self._running:
            return

        self._running = False

        # Cancel all tasks
        for task in self._tasks.values():
            task.cancel()

        # Wait for cancellation
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

        self._tasks.clear()
        logger.info("sanctions_scheduler_stopped")

    async def trigger_update(
        self,
        list_source: SanctionsList,
        *,
        force: bool = False,
    ) -> ListUpdateResult:
        """Manually trigger an update for a list.

        Args:
            list_source: The list to update.
            force: Force update even if recently updated.

        Returns:
            ListUpdateResult with update details.
        """
        if list_source not in self._update_handlers:
            return ListUpdateResult(
                list_source=list_source,
                success=False,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error_message=f"No handler registered for {list_source.value}",
            )

        # Check if recently updated
        if not force:
            last_update = self._last_updates.get(list_source)
            if last_update:
                config = self._get_list_config(list_source)
                min_interval = timedelta(seconds=config.frequency.to_seconds() // 4)
                if datetime.now(UTC) - last_update < min_interval:
                    return ListUpdateResult(
                        list_source=list_source,
                        success=True,
                        started_at=last_update,
                        completed_at=last_update,
                        error_message="Skipped - recently updated",
                    )

        return await self._execute_update(list_source)

    async def trigger_all_updates(
        self,
        *,
        force: bool = False,
    ) -> list[ListUpdateResult]:
        """Trigger updates for all registered lists.

        Args:
            force: Force updates even if recently updated.

        Returns:
            List of update results.
        """
        tasks = [
            self.trigger_update(list_source, force=force) for list_source in self._update_handlers
        ]
        return list(await asyncio.gather(*tasks))

    def get_last_update(self, list_source: SanctionsList) -> datetime | None:
        """Get the last update time for a list.

        Args:
            list_source: The list to check.

        Returns:
            Last update datetime or None if never updated.
        """
        return self._last_updates.get(list_source)

    def get_update_result(self, list_source: SanctionsList) -> ListUpdateResult | None:
        """Get the last update result for a list.

        Args:
            list_source: The list to check.

        Returns:
            Last update result or None.
        """
        return self._update_results.get(list_source)

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status summary.

        Returns:
            Dictionary with scheduler status.
        """
        return {
            "running": self._running,
            "enabled": self._config.enabled,
            "active_tasks": len(self._tasks),
            "registered_handlers": len(self._update_handlers),
            "last_updates": {
                lst.value: dt.isoformat() if dt else None for lst, dt in self._last_updates.items()
            },
            "latest_results": {
                lst.value: {
                    "success": result.success,
                    "entities_count": result.entities_count,
                    "duration_seconds": result.duration_seconds,
                }
                for lst, result in self._update_results.items()
            },
        }

    async def _update_loop(self, list_source: SanctionsList) -> None:
        """Main update loop for a list.

        Args:
            list_source: The list to update.
        """
        config = self._get_list_config(list_source)
        interval_seconds = config.frequency.to_seconds()

        logger.info(
            "update_loop_started",
            list_source=list_source.value,
            interval_seconds=interval_seconds,
        )

        # Run initial update
        if self._running:
            await self._execute_update(list_source)

        while self._running:
            try:
                await asyncio.sleep(interval_seconds)
                if self._running:
                    await self._execute_update(list_source)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "update_loop_error",
                    list_source=list_source.value,
                    error=str(e),
                )
                # Continue loop after error
                await asyncio.sleep(config.retry_delay_seconds)

    async def _execute_update(self, list_source: SanctionsList) -> ListUpdateResult:
        """Execute an update for a list.

        Args:
            list_source: The list to update.

        Returns:
            ListUpdateResult with details.
        """
        started_at = datetime.now(UTC)
        config = self._get_list_config(list_source)
        handler = self._update_handlers[list_source]

        logger.info(
            "update_started",
            list_source=list_source.value,
        )

        # Acquire semaphore to limit concurrent updates
        if self._semaphore:
            await self._semaphore.acquire()

        try:
            # Execute with retries
            last_error: Exception | None = None
            for attempt in range(config.retry_attempts + 1):
                try:
                    # Call the handler
                    if inspect.iscoroutinefunction(handler):
                        handler_result = await handler()
                    else:
                        handler_result = handler()

                    # Build success result
                    completed_at = datetime.now(UTC)
                    result = ListUpdateResult(
                        list_source=list_source,
                        success=True,
                        entities_count=(
                            handler_result.get("entities_count", 0)
                            if isinstance(handler_result, dict)
                            else 0
                        ),
                        entities_added=(
                            handler_result.get("entities_added", 0)
                            if isinstance(handler_result, dict)
                            else 0
                        ),
                        entities_removed=(
                            handler_result.get("entities_removed", 0)
                            if isinstance(handler_result, dict)
                            else 0
                        ),
                        entities_modified=(
                            handler_result.get("entities_modified", 0)
                            if isinstance(handler_result, dict)
                            else 0
                        ),
                        started_at=started_at,
                        completed_at=completed_at,
                        duration_seconds=(completed_at - started_at).total_seconds(),
                    )

                    # Update tracking
                    self._last_updates[list_source] = completed_at
                    self._update_results[list_source] = result

                    # Call success callback
                    if self._on_update_callback:
                        try:
                            callback_result = self._on_update_callback(result)
                            if asyncio.iscoroutine(callback_result):
                                await callback_result
                        except Exception as cb_error:
                            logger.warning(
                                "update_callback_error",
                                list_source=list_source.value,
                                error=str(cb_error),
                            )

                    logger.info(
                        "update_completed",
                        list_source=list_source.value,
                        entities_count=result.entities_count,
                        duration_seconds=result.duration_seconds,
                    )

                    return result

                except Exception as e:
                    last_error = e
                    if attempt < config.retry_attempts:
                        logger.warning(
                            "update_retry",
                            list_source=list_source.value,
                            attempt=attempt + 1,
                            max_attempts=config.retry_attempts + 1,
                            error=str(e),
                        )
                        await asyncio.sleep(config.retry_delay_seconds)

            # All retries failed
            completed_at = datetime.now(UTC)
            result = ListUpdateResult(
                list_source=list_source,
                success=False,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
                error_message=str(last_error) if last_error else "Unknown error",
            )

            self._update_results[list_source] = result

            # Call error callback
            if self._on_error_callback and last_error:
                try:
                    callback_result = self._on_error_callback(list_source, last_error)
                    if asyncio.iscoroutine(callback_result):
                        await callback_result
                except Exception as cb_error:
                    logger.warning(
                        "error_callback_error",
                        list_source=list_source.value,
                        error=str(cb_error),
                    )

            logger.error(
                "update_failed",
                list_source=list_source.value,
                attempts=config.retry_attempts + 1,
                error=result.error_message,
            )

            return result

        finally:
            if self._semaphore:
                self._semaphore.release()

    def _get_list_config(self, list_source: SanctionsList) -> ListUpdateConfig:
        """Get configuration for a list.

        Args:
            list_source: The list to get config for.

        Returns:
            ListUpdateConfig (from config or default).
        """
        if list_source in self._list_configs:
            return self._list_configs[list_source]

        # Return default config
        return ListUpdateConfig(
            list_source=list_source,
            frequency=self._config.default_frequency,
        )


# =============================================================================
# Factory Functions
# =============================================================================


_scheduler_instance: SanctionsUpdateScheduler | None = None


def get_update_scheduler(
    config: UpdateSchedulerConfig | None = None,
) -> SanctionsUpdateScheduler:
    """Get the singleton scheduler instance.

    Args:
        config: Optional configuration for first initialization.

    Returns:
        The SanctionsUpdateScheduler singleton.
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SanctionsUpdateScheduler(config)
    return _scheduler_instance


def create_update_scheduler(
    config: UpdateSchedulerConfig | None = None,
) -> SanctionsUpdateScheduler:
    """Create a new scheduler instance.

    Use this for testing or when you need a fresh scheduler.

    Args:
        config: Optional configuration.

    Returns:
        A new SanctionsUpdateScheduler instance.
    """
    return SanctionsUpdateScheduler(config)
