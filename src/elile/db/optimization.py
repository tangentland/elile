"""Database optimization module for Elile.

This module provides:
- Optimized connection pooling configuration
- Query performance monitoring and slow query logging
- Query optimization utilities with eager loading patterns
- Database statistics collection for Prometheus metrics
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.pool import QueuePool

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine
    from sqlalchemy.orm.strategy_options import _AbstractLoad

__all__ = [
    "OptimizedPoolConfig",
    "SlowQueryConfig",
    "QueryStats",
    "OptimizedEngine",
    "QueryOptimizer",
    "SlowQueryLogger",
    "create_optimized_engine",
    "get_pool_statistics",
    "observe_query",
]

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger(__name__)


@dataclass
class OptimizedPoolConfig:
    """Configuration for optimized database connection pooling.

    These settings are tuned for production workloads with:
    - Adequate pool size for concurrent requests
    - Overflow capacity for burst traffic
    - Connection health checks to prevent stale connections
    - Regular connection recycling to prevent memory leaks
    """

    # Core pool settings
    pool_size: int = 20
    """Number of connections to keep in the pool."""

    max_overflow: int = 10
    """Maximum overflow connections beyond pool_size."""

    # Health and recycling
    pool_pre_ping: bool = True
    """Enable connection health checks before use (prevents stale connection errors)."""

    pool_recycle: int = 3600
    """Recycle connections after this many seconds (prevents connection timeout issues)."""

    pool_timeout: int = 30
    """Seconds to wait for a connection from the pool before timing out."""

    # Performance tuning
    echo_pool: bool = False
    """Log pool checkouts/checkins (useful for debugging, disable in production)."""

    echo: bool = False
    """Log all SQL statements (disable in production)."""

    # Connection settings
    connect_args: dict[str, Any] = field(default_factory=dict)
    """Additional connection arguments for the database driver."""

    @classmethod
    def for_production(cls) -> OptimizedPoolConfig:
        """Create production-optimized pool configuration."""
        return cls(
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_timeout=30,
            echo_pool=False,
            echo=False,
            connect_args={
                "server_settings": {
                    "statement_timeout": "30000",  # 30 second query timeout
                    "lock_timeout": "10000",  # 10 second lock timeout
                }
            },
        )

    @classmethod
    def for_development(cls) -> OptimizedPoolConfig:
        """Create development configuration with more logging."""
        return cls(
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_timeout=30,
            echo_pool=True,
            echo=True,
        )

    @classmethod
    def for_testing(cls) -> OptimizedPoolConfig:
        """Create test configuration with minimal pooling."""
        return cls(
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=False,
            pool_recycle=300,
            pool_timeout=10,
            echo_pool=False,
            echo=False,
        )


@dataclass
class SlowQueryConfig:
    """Configuration for slow query logging and detection.

    Attributes:
        threshold_ms: Queries taking longer than this are logged as slow.
        log_query_plan: Whether to log EXPLAIN output for slow queries.
        sample_rate: Fraction of queries to sample for performance tracking (0.0-1.0).
    """

    threshold_ms: float = 100.0
    """Threshold in milliseconds for slow query detection."""

    log_query_plan: bool = True
    """Log EXPLAIN ANALYZE output for slow queries."""

    sample_rate: float = 0.1
    """Sample rate for query performance tracking (0.1 = 10% of queries)."""

    enable_query_logging: bool = True
    """Enable query logging."""

    log_parameters: bool = False
    """Log query parameters (may expose sensitive data, disable in production)."""


@dataclass
class QueryStats:
    """Statistics for a database query execution.

    Attributes:
        query_text: The SQL query text.
        duration_ms: Execution time in milliseconds.
        rows_affected: Number of rows affected/returned.
        table_name: Primary table involved in the query.
        operation: Type of operation (SELECT, INSERT, UPDATE, DELETE).
        is_slow: Whether the query exceeded the slow threshold.
        timestamp: When the query was executed.
    """

    query_text: str
    duration_ms: float
    rows_affected: int = 0
    table_name: str = "unknown"
    operation: str = "unknown"
    is_slow: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/metrics."""
        return {
            "query_text": self.query_text[:500],  # Truncate long queries
            "duration_ms": self.duration_ms,
            "rows_affected": self.rows_affected,
            "table_name": self.table_name,
            "operation": self.operation,
            "is_slow": self.is_slow,
            "timestamp": self.timestamp.isoformat(),
        }


class SlowQueryLogger:
    """Logs slow queries and collects query statistics.

    This logger integrates with SQLAlchemy events to capture query execution
    times and log queries that exceed the configured threshold.
    """

    def __init__(self, config: SlowQueryConfig | None = None) -> None:
        """Initialize the slow query logger.

        Args:
            config: Configuration for slow query detection.
        """
        self.config = config or SlowQueryConfig()
        self._query_stats: list[QueryStats] = []
        self._slow_queries: list[QueryStats] = []
        self._max_stored_stats = 1000

    def record_query(
        self,
        query_text: str,
        duration_ms: float,
        rows_affected: int = 0,
        table_name: str = "unknown",
        operation: str = "unknown",
    ) -> QueryStats:
        """Record a query execution.

        Args:
            query_text: The SQL query text.
            duration_ms: Execution time in milliseconds.
            rows_affected: Number of rows affected/returned.
            table_name: Primary table involved.
            operation: Type of operation.

        Returns:
            QueryStats object for the recorded query.
        """
        is_slow = duration_ms >= self.config.threshold_ms

        stats = QueryStats(
            query_text=query_text,
            duration_ms=duration_ms,
            rows_affected=rows_affected,
            table_name=table_name,
            operation=operation,
            is_slow=is_slow,
        )

        # Store stats (with rolling window)
        self._query_stats.append(stats)
        if len(self._query_stats) > self._max_stored_stats:
            self._query_stats = self._query_stats[-self._max_stored_stats :]

        # Log and store slow queries
        if is_slow:
            self._slow_queries.append(stats)
            if len(self._slow_queries) > self._max_stored_stats:
                self._slow_queries = self._slow_queries[-self._max_stored_stats :]

            if self.config.enable_query_logging:
                logger.warning(
                    "Slow query detected",
                    extra={
                        "duration_ms": duration_ms,
                        "threshold_ms": self.config.threshold_ms,
                        "table": table_name,
                        "operation": operation,
                        "query": query_text[:200] if not self.config.log_parameters else query_text,
                    },
                )

        return stats

    def get_slow_queries(self, limit: int = 100) -> list[QueryStats]:
        """Get recent slow queries.

        Args:
            limit: Maximum number of queries to return.

        Returns:
            List of slow query statistics.
        """
        return self._slow_queries[-limit:]

    def get_query_stats(self, limit: int = 100) -> list[QueryStats]:
        """Get recent query statistics.

        Args:
            limit: Maximum number of stats to return.

        Returns:
            List of query statistics.
        """
        return self._query_stats[-limit:]

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics.

        Returns:
            Dictionary with summary metrics.
        """
        if not self._query_stats:
            return {
                "total_queries": 0,
                "slow_queries": 0,
                "slow_query_rate": 0.0,
                "avg_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "p95_duration_ms": 0.0,
            }

        durations = [s.duration_ms for s in self._query_stats]
        sorted_durations = sorted(durations)
        p95_index = int(len(sorted_durations) * 0.95)

        return {
            "total_queries": len(self._query_stats),
            "slow_queries": len(self._slow_queries),
            "slow_query_rate": len(self._slow_queries) / len(self._query_stats),
            "avg_duration_ms": sum(durations) / len(durations),
            "max_duration_ms": max(durations),
            "p95_duration_ms": (
                sorted_durations[p95_index] if p95_index < len(sorted_durations) else 0.0
            ),
        }

    def clear(self) -> None:
        """Clear stored query statistics."""
        self._query_stats.clear()
        self._slow_queries.clear()


class QueryOptimizer:
    """Provides optimized query patterns with eager loading.

    This class provides factory methods to create eager loading configurations
    for common query patterns to avoid N+1 query problems.

    Note: SQLAlchemy 2.x requires class-bound attributes for loader options.
    Use the factory methods with the actual model classes.
    """

    @staticmethod
    def with_selectinload(relationship_attr: Any) -> _AbstractLoad:
        """Create a selectinload option for a relationship.

        Args:
            relationship_attr: The class-bound relationship attribute (e.g., Entity.profiles).

        Returns:
            Loader option for the relationship.
        """
        return selectinload(relationship_attr)

    @staticmethod
    def with_joinedload(relationship_attr: Any) -> _AbstractLoad:
        """Create a joinedload option for a relationship.

        Args:
            relationship_attr: The class-bound relationship attribute (e.g., EntityProfile.entity).

        Returns:
            Loader option for the relationship.
        """
        return joinedload(relationship_attr)


class OptimizedEngine:
    """Wrapper for optimized async database engine with monitoring.

    This class wraps an async SQLAlchemy engine with:
    - Optimized connection pool settings
    - Slow query logging
    - Prometheus metrics integration
    - Query performance monitoring
    """

    def __init__(
        self,
        database_url: str,
        pool_config: OptimizedPoolConfig | None = None,
        slow_query_config: SlowQueryConfig | None = None,
    ) -> None:
        """Initialize the optimized engine.

        Args:
            database_url: Database connection URL.
            pool_config: Connection pool configuration.
            slow_query_config: Slow query logging configuration.
        """
        self.database_url = database_url
        self.pool_config = pool_config or OptimizedPoolConfig()
        self.slow_query_config = slow_query_config or SlowQueryConfig()
        self.slow_query_logger = SlowQueryLogger(self.slow_query_config)

        # Create the engine with optimized settings
        self._engine = create_async_engine(
            database_url,
            pool_size=self.pool_config.pool_size,
            max_overflow=self.pool_config.max_overflow,
            pool_pre_ping=self.pool_config.pool_pre_ping,
            pool_recycle=self.pool_config.pool_recycle,
            pool_timeout=self.pool_config.pool_timeout,
            echo=self.pool_config.echo,
            echo_pool=self.pool_config.echo_pool,
            poolclass=QueuePool,
            connect_args=self.pool_config.connect_args,
        )

        # Create session factory
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Set up event listeners for the sync engine
        self._setup_event_listeners()

    def _setup_event_listeners(self) -> None:
        """Set up SQLAlchemy event listeners for query monitoring."""
        sync_engine = self._engine.sync_engine

        @event.listens_for(sync_engine, "before_cursor_execute")
        def receive_before_cursor_execute(
            conn: Any,  # noqa: ARG001
            cursor: Any,  # noqa: ARG001
            statement: str,  # noqa: ARG001
            parameters: Any,  # noqa: ARG001
            context: Any,
            executemany: bool,  # noqa: ARG001
        ) -> None:
            if context is not None:
                context._query_start_time = time.perf_counter()

        @event.listens_for(sync_engine, "after_cursor_execute")
        def receive_after_cursor_execute(
            conn: Any,  # noqa: ARG001
            cursor: Any,
            statement: str,
            parameters: Any,  # noqa: ARG001
            context: Any,
            executemany: bool,  # noqa: ARG001
        ) -> None:
            if context is not None and hasattr(context, "_query_start_time"):
                duration_ms = (time.perf_counter() - context._query_start_time) * 1000

                # Extract operation and table from statement
                operation = "unknown"
                table_name = "unknown"
                statement_upper = statement.strip().upper()

                if statement_upper.startswith("SELECT"):
                    operation = "SELECT"
                elif statement_upper.startswith("INSERT"):
                    operation = "INSERT"
                elif statement_upper.startswith("UPDATE"):
                    operation = "UPDATE"
                elif statement_upper.startswith("DELETE"):
                    operation = "DELETE"

                # Try to extract table name
                try:
                    if "FROM" in statement_upper:
                        from_idx = statement_upper.index("FROM")
                        table_part = statement[from_idx + 5 :].strip().split()[0]
                        table_name = table_part.strip('"').split(".")[  # noqa: B005
                            -1
                        ]  # Handle schema.table
                    elif "INTO" in statement_upper:
                        into_idx = statement_upper.index("INTO")
                        table_part = statement[into_idx + 5 :].strip().split()[0]
                        table_name = table_part.strip('"').split(".")[-1]  # noqa: B005
                    elif "UPDATE" in statement_upper:
                        update_idx = statement_upper.index("UPDATE")
                        table_part = statement[update_idx + 7 :].strip().split()[0]
                        table_name = table_part.strip('"').split(".")[-1]  # noqa: B005
                except (ValueError, IndexError):
                    pass

                # Record query stats
                rows_affected = cursor.rowcount if cursor.rowcount >= 0 else 0
                self.slow_query_logger.record_query(
                    query_text=statement,
                    duration_ms=duration_ms,
                    rows_affected=rows_affected,
                    table_name=table_name,
                    operation=operation,
                )

                # Record metrics if observability is available
                try:
                    from elile.observability.metrics import record_db_query

                    record_db_query(
                        operation=operation.lower(),
                        table=table_name,
                        duration_seconds=duration_ms / 1000,
                    )
                except ImportError:
                    pass  # Observability module not available

    @property
    def engine(self) -> AsyncEngine:
        """Get the underlying async engine."""
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the session factory."""
        return self._session_factory

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session.

        Yields:
            AsyncSession for database operations.
        """
        async with self._session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    async def verify_connection(self) -> bool:
        """Verify database connectivity.

        Returns:
            True if connection is successful.
        """
        try:
            async with self._engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error("Database connection verification failed", exc_info=e)
            return False

    async def get_pool_statistics(self) -> dict[str, Any]:
        """Get connection pool statistics.

        Returns:
            Dictionary with pool statistics.
        """
        pool = self._engine.pool
        return {
            "pool_size": pool.size(),  # type: ignore[attr-defined]
            "checked_out": pool.checkedout(),  # type: ignore[attr-defined]
            "checked_in": pool.checkedin(),  # type: ignore[attr-defined]
            "overflow": pool.overflow(),  # type: ignore[attr-defined]
            "invalid": pool.invalidatedcount() if hasattr(pool, "invalidatedcount") else 0,
        }

    async def close(self) -> None:
        """Close the database engine and all connections."""
        await self._engine.dispose()


def create_optimized_engine(
    database_url: str,
    environment: str = "development",
    pool_config: OptimizedPoolConfig | None = None,
    slow_query_config: SlowQueryConfig | None = None,
) -> OptimizedEngine:
    """Factory function to create an optimized database engine.

    Args:
        database_url: Database connection URL.
        environment: Environment name (development, production, test).
        pool_config: Optional custom pool configuration.
        slow_query_config: Optional slow query configuration.

    Returns:
        Configured OptimizedEngine instance.
    """
    if pool_config is None:
        if environment == "production":
            pool_config = OptimizedPoolConfig.for_production()
        elif environment == "test":
            pool_config = OptimizedPoolConfig.for_testing()
        else:
            pool_config = OptimizedPoolConfig.for_development()

    if slow_query_config is None:
        slow_query_config = SlowQueryConfig(
            threshold_ms=100.0 if environment == "production" else 200.0,
            log_query_plan=environment != "production",
            log_parameters=environment == "development",
        )

    return OptimizedEngine(
        database_url=database_url,
        pool_config=pool_config,
        slow_query_config=slow_query_config,
    )


async def get_pool_statistics(engine: OptimizedEngine) -> dict[str, Any]:
    """Get pool statistics and update Prometheus metrics.

    Args:
        engine: The optimized engine to get statistics from.

    Returns:
        Dictionary with pool statistics.
    """
    stats = await engine.get_pool_statistics()

    # Update Prometheus metrics if available
    try:
        from elile.observability.metrics import set_active_connections, set_connection_pool_size

        set_connection_pool_size(stats["pool_size"])
        set_active_connections(stats["checked_out"])
    except ImportError:
        pass  # Observability module not available

    return stats


@asynccontextmanager
async def observe_query(
    operation: str,
    table: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Context manager for observing query performance.

    Args:
        operation: Query operation type (select, insert, update, delete).
        table: Target table name.

    Yields:
        Context dictionary for storing results.
    """
    context: dict[str, Any] = {}
    start_time = time.perf_counter()

    try:
        yield context
    finally:
        duration_seconds = time.perf_counter() - start_time

        # Record metrics if observability is available
        try:
            from elile.observability.metrics import record_db_query

            record_db_query(
                operation=operation,
                table=table,
                duration_seconds=duration_seconds,
            )
        except ImportError:
            pass


# Global slow query logger for use with the default engine
_global_slow_query_logger: SlowQueryLogger | None = None


def get_slow_query_logger() -> SlowQueryLogger:
    """Get the global slow query logger instance."""
    global _global_slow_query_logger
    if _global_slow_query_logger is None:
        _global_slow_query_logger = SlowQueryLogger()
    return _global_slow_query_logger
