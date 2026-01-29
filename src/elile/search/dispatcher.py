"""Centralized query dispatcher with priority queue and rate limiting."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel

from elile.agent.state import InformationType, SearchPhase, SearchResult
from elile.search.query import SearchQuery

if TYPE_CHECKING:
    from elile.search.engine import SearchEngine

logger = structlog.get_logger()


class QueryPriority(BaseModel):
    """Priority metadata for a query in the dispatch queue.

    Priority scoring determines execution order when rate-limited.
    Lower effective_priority values execute first.
    """

    query: SearchQuery
    info_type: InformationType
    phase: SearchPhase
    base_priority: int
    modifiers: list[str] = []  # For debugging priority adjustments
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def effective_priority(self) -> int:
        """Calculate effective priority including modifiers.

        Returns:
            Priority score (lower = higher priority).
        """
        adjustment = 0
        for modifier in self.modifiers:
            if modifier.startswith("+"):
                adjustment -= 1  # + modifiers increase priority (lower number)
            elif modifier.startswith("-"):
                adjustment += 1  # - modifiers decrease priority (higher number)
        return self.base_priority + adjustment

    def __lt__(self, other: QueryPriority) -> bool:
        """Compare for priority queue ordering."""
        if self.effective_priority != other.effective_priority:
            return self.effective_priority < other.effective_priority
        # FIFO within same priority
        return self.submitted_at < other.submitted_at


@dataclass
class DispatchResult:
    """Result from dispatching a query."""

    query: SearchQuery
    info_type: InformationType
    results: list[SearchResult]
    success: bool
    error: str | None = None
    duration_ms: float = 0.0


class PriorityConfig(BaseModel):
    """Configuration for phase-based priority scoring."""

    foundation: int = 5  # Highest priority (blocking other phases)
    records: int = 3
    intelligence: int = 2
    network: int = 2
    reconciliation: int = 4  # High priority to resolve conflicts


class QueryDispatcher:
    """Central rate-limited query dispatcher with priority queue.

    Manages query execution across all phases and information types,
    respecting rate limits while prioritizing critical queries.
    """

    def __init__(
        self,
        search_engine: SearchEngine,
        rate_limit_rpm: int = 60,
        priority_config: PriorityConfig | None = None,
    ) -> None:
        """Initialize the query dispatcher.

        Args:
            search_engine: Engine to execute queries through.
            rate_limit_rpm: Maximum requests per minute.
            priority_config: Phase-based priority configuration.
        """
        self._engine = search_engine
        self._rate_limit = rate_limit_rpm
        self._priority_config = priority_config or PriorityConfig()

        # Rate limiting via semaphore (allow burst of 10% of rate limit)
        burst_size = max(1, rate_limit_rpm // 10)
        self._semaphore = asyncio.Semaphore(burst_size)

        # Token bucket for sustained rate limiting
        self._tokens = float(rate_limit_rpm)
        self._max_tokens = float(rate_limit_rpm)
        self._refill_rate = rate_limit_rpm / 60.0  # tokens per second
        self._last_refill = datetime.now(timezone.utc)

        # Priority queue implemented as sorted list
        self._queue: list[QueryPriority] = []
        self._queue_lock = asyncio.Lock()

        # Tracking
        self._total_dispatched = 0
        self._total_errors = 0
        self._type_results: dict[str, list[DispatchResult]] = {}

        # Background processing
        self._processing = False
        self._process_task: asyncio.Task | None = None

    async def submit(
        self,
        query: SearchQuery,
        info_type: InformationType,
        phase: SearchPhase,
        priority_modifiers: list[str] | None = None,
    ) -> None:
        """Submit a query to the priority queue.

        Args:
            query: The query to execute.
            info_type: Information type this query is for.
            phase: Current search phase.
            priority_modifiers: Optional priority adjustments.
        """
        base_priority = self._get_base_priority(phase)
        modifiers = priority_modifiers or []

        priority_item = QueryPriority(
            query=query,
            info_type=info_type,
            phase=phase,
            base_priority=base_priority,
            modifiers=modifiers,
        )

        async with self._queue_lock:
            # Insert in sorted order
            self._queue.append(priority_item)
            self._queue.sort()

        logger.debug(
            "Query submitted",
            query=query.query[:50],
            info_type=info_type.value,
            priority=priority_item.effective_priority,
            queue_size=len(self._queue),
        )

    async def submit_batch(
        self,
        queries: list[SearchQuery],
        info_type: InformationType,
        phase: SearchPhase,
    ) -> None:
        """Submit multiple queries to the queue.

        Args:
            queries: List of queries to submit.
            info_type: Information type for all queries.
            phase: Current search phase.
        """
        for query in queries:
            await self.submit(query, info_type, phase)

    def _get_base_priority(self, phase: SearchPhase) -> int:
        """Get base priority for a phase.

        Args:
            phase: The search phase.

        Returns:
            Base priority value (lower = higher priority).
        """
        match phase:
            case SearchPhase.FOUNDATION:
                return self._priority_config.foundation
            case SearchPhase.RECORDS:
                return self._priority_config.records
            case SearchPhase.INTELLIGENCE:
                return self._priority_config.intelligence
            case SearchPhase.NETWORK:
                return self._priority_config.network
            case SearchPhase.RECONCILIATION:
                return self._priority_config.reconciliation

    async def _refill_tokens(self) -> None:
        """Refill rate limit tokens based on elapsed time."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_refill).total_seconds()
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    async def _acquire_token(self) -> None:
        """Acquire a rate limit token, waiting if necessary."""
        while True:
            await self._refill_tokens()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            # Wait for token refill
            wait_time = (1.0 - self._tokens) / self._refill_rate
            await asyncio.sleep(wait_time)

    async def dispatch_one(self) -> DispatchResult | None:
        """Dispatch the highest priority query from the queue.

        Returns:
            DispatchResult if a query was executed, None if queue is empty.
        """
        # Get next query from queue
        async with self._queue_lock:
            if not self._queue:
                return None
            priority_item = self._queue.pop(0)

        # Acquire rate limit token
        await self._acquire_token()

        # Execute query
        start_time = datetime.now(timezone.utc)
        try:
            async with self._semaphore:
                results = await self._engine.search([priority_item.query])

            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            dispatch_result = DispatchResult(
                query=priority_item.query,
                info_type=priority_item.info_type,
                results=results,
                success=True,
                duration_ms=duration,
            )

            self._total_dispatched += 1
            logger.debug(
                "Query dispatched",
                query=priority_item.query.query[:50],
                results=len(results),
                duration_ms=duration,
            )

        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            dispatch_result = DispatchResult(
                query=priority_item.query,
                info_type=priority_item.info_type,
                results=[],
                success=False,
                error=str(e),
                duration_ms=duration,
            )

            self._total_errors += 1
            logger.error(
                "Query dispatch failed",
                query=priority_item.query.query[:50],
                error=str(e),
            )

        # Track results by type
        type_key = priority_item.info_type.value
        if type_key not in self._type_results:
            self._type_results[type_key] = []
        self._type_results[type_key].append(dispatch_result)

        return dispatch_result

    async def dispatch_all(self) -> list[DispatchResult]:
        """Dispatch all queued queries.

        Returns:
            List of all dispatch results.
        """
        results = []
        while True:
            result = await self.dispatch_one()
            if result is None:
                break
            results.append(result)
        return results

    async def dispatch_for_type(
        self,
        info_type: InformationType,
    ) -> list[DispatchResult]:
        """Dispatch all queued queries for a specific information type.

        Args:
            info_type: The information type to dispatch queries for.

        Returns:
            List of dispatch results for this type.
        """
        results = []

        while True:
            # Check if next query is for this type
            async with self._queue_lock:
                # Find first query for this type
                type_idx = None
                for i, item in enumerate(self._queue):
                    if item.info_type == info_type:
                        type_idx = i
                        break

                if type_idx is None:
                    break

                # Remove and process this query
                priority_item = self._queue.pop(type_idx)

            # Acquire rate limit token
            await self._acquire_token()

            # Execute query
            start_time = datetime.now(timezone.utc)
            try:
                async with self._semaphore:
                    search_results = await self._engine.search([priority_item.query])

                duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

                dispatch_result = DispatchResult(
                    query=priority_item.query,
                    info_type=priority_item.info_type,
                    results=search_results,
                    success=True,
                    duration_ms=duration,
                )
                self._total_dispatched += 1

            except Exception as e:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

                dispatch_result = DispatchResult(
                    query=priority_item.query,
                    info_type=priority_item.info_type,
                    results=[],
                    success=False,
                    error=str(e),
                    duration_ms=duration,
                )
                self._total_errors += 1

            results.append(dispatch_result)

        return results

    async def start_background_processing(self) -> None:
        """Start background processing of the queue."""
        if self._processing:
            return

        self._processing = True
        self._process_task = asyncio.create_task(self._background_loop())
        logger.info("Started background query processing")

    async def stop_background_processing(self) -> None:
        """Stop background processing."""
        self._processing = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
            self._process_task = None
        logger.info("Stopped background query processing")

    async def _background_loop(self) -> None:
        """Background loop for processing queries."""
        while self._processing:
            result = await self.dispatch_one()
            if result is None:
                # Queue empty, wait a bit
                await asyncio.sleep(0.1)

    def get_results_for_type(self, info_type: InformationType) -> list[DispatchResult]:
        """Get accumulated results for an information type.

        Args:
            info_type: The information type.

        Returns:
            List of dispatch results for this type.
        """
        return self._type_results.get(info_type.value, [])

    def clear_results_for_type(self, info_type: InformationType) -> None:
        """Clear accumulated results for an information type.

        Args:
            info_type: The information type to clear.
        """
        self._type_results.pop(info_type.value, None)

    @property
    def queue_size(self) -> int:
        """Current queue size."""
        return len(self._queue)

    @property
    def total_dispatched(self) -> int:
        """Total queries dispatched."""
        return self._total_dispatched

    @property
    def total_errors(self) -> int:
        """Total dispatch errors."""
        return self._total_errors

    @property
    def utilization(self) -> float:
        """Current rate limit utilization (0.0 to 1.0)."""
        return 1.0 - (self._tokens / self._max_tokens)

    def get_stats(self) -> dict:
        """Get dispatcher statistics.

        Returns:
            Dictionary of statistics.
        """
        return {
            "queue_size": self.queue_size,
            "total_dispatched": self._total_dispatched,
            "total_errors": self._total_errors,
            "utilization": self.utilization,
            "tokens_available": self._tokens,
            "rate_limit_rpm": self._rate_limit,
        }
