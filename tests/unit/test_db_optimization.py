"""Tests for database optimization module."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from elile.db.optimization import (
    OptimizedPoolConfig,
    QueryOptimizer,
    QueryStats,
    SlowQueryConfig,
    SlowQueryLogger,
    get_slow_query_logger,
    observe_query,
)


class TestOptimizedPoolConfig:
    """Tests for OptimizedPoolConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = OptimizedPoolConfig()

        assert config.pool_size == 20
        assert config.max_overflow == 10
        assert config.pool_pre_ping is True
        assert config.pool_recycle == 3600
        assert config.pool_timeout == 30
        assert config.echo_pool is False
        assert config.echo is False

    def test_for_production(self) -> None:
        """Test production configuration preset."""
        config = OptimizedPoolConfig.for_production()

        assert config.pool_size == 20
        assert config.max_overflow == 10
        assert config.pool_pre_ping is True
        assert config.pool_recycle == 3600
        assert config.echo is False
        assert config.echo_pool is False
        assert "statement_timeout" in config.connect_args.get("server_settings", {})
        assert "lock_timeout" in config.connect_args.get("server_settings", {})

    def test_for_development(self) -> None:
        """Test development configuration preset."""
        config = OptimizedPoolConfig.for_development()

        assert config.pool_size == 5
        assert config.max_overflow == 5
        assert config.echo is True
        assert config.echo_pool is True

    def test_for_testing(self) -> None:
        """Test testing configuration preset."""
        config = OptimizedPoolConfig.for_testing()

        assert config.pool_size == 1
        assert config.max_overflow == 0
        assert config.pool_pre_ping is False
        assert config.echo is False


class TestSlowQueryConfig:
    """Tests for SlowQueryConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = SlowQueryConfig()

        assert config.threshold_ms == 100.0
        assert config.log_query_plan is True
        assert config.sample_rate == 0.1
        assert config.enable_query_logging is True
        assert config.log_parameters is False

    def test_custom_threshold(self) -> None:
        """Test custom threshold configuration."""
        config = SlowQueryConfig(threshold_ms=50.0)
        assert config.threshold_ms == 50.0


class TestQueryStats:
    """Tests for QueryStats dataclass."""

    def test_creation(self) -> None:
        """Test QueryStats creation."""
        stats = QueryStats(
            query_text="SELECT * FROM entities",
            duration_ms=50.0,
            rows_affected=10,
            table_name="entities",
            operation="SELECT",
            is_slow=False,
        )

        assert stats.query_text == "SELECT * FROM entities"
        assert stats.duration_ms == 50.0
        assert stats.rows_affected == 10
        assert stats.table_name == "entities"
        assert stats.operation == "SELECT"
        assert stats.is_slow is False
        assert stats.timestamp is not None

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        stats = QueryStats(
            query_text="SELECT * FROM entities",
            duration_ms=50.0,
            rows_affected=10,
            table_name="entities",
            operation="SELECT",
        )

        result = stats.to_dict()

        assert result["query_text"] == "SELECT * FROM entities"
        assert result["duration_ms"] == 50.0
        assert result["rows_affected"] == 10
        assert result["table_name"] == "entities"
        assert result["operation"] == "SELECT"
        assert "timestamp" in result

    def test_long_query_truncation(self) -> None:
        """Test that long queries are truncated in to_dict."""
        long_query = "SELECT " + "a" * 1000
        stats = QueryStats(query_text=long_query, duration_ms=10.0)

        result = stats.to_dict()
        assert len(result["query_text"]) == 500


class TestSlowQueryLogger:
    """Tests for SlowQueryLogger."""

    def test_initialization(self) -> None:
        """Test logger initialization."""
        logger = SlowQueryLogger()
        assert logger.config.threshold_ms == 100.0

    def test_custom_config(self) -> None:
        """Test logger with custom config."""
        config = SlowQueryConfig(threshold_ms=50.0)
        logger = SlowQueryLogger(config)
        assert logger.config.threshold_ms == 50.0

    def test_record_fast_query(self) -> None:
        """Test recording a fast query (not slow)."""
        logger = SlowQueryLogger(SlowQueryConfig(threshold_ms=100.0))

        stats = logger.record_query(
            query_text="SELECT 1",
            duration_ms=10.0,
            table_name="test",
            operation="SELECT",
        )

        assert stats.is_slow is False
        assert len(logger.get_query_stats()) == 1
        assert len(logger.get_slow_queries()) == 0

    def test_record_slow_query(self) -> None:
        """Test recording a slow query."""
        logger = SlowQueryLogger(SlowQueryConfig(threshold_ms=100.0, enable_query_logging=False))

        stats = logger.record_query(
            query_text="SELECT * FROM large_table",
            duration_ms=200.0,
            table_name="large_table",
            operation="SELECT",
        )

        assert stats.is_slow is True
        assert len(logger.get_query_stats()) == 1
        assert len(logger.get_slow_queries()) == 1

    def test_query_at_threshold_is_slow(self) -> None:
        """Test that query at exactly threshold is considered slow."""
        logger = SlowQueryLogger(SlowQueryConfig(threshold_ms=100.0, enable_query_logging=False))

        stats = logger.record_query(
            query_text="SELECT 1",
            duration_ms=100.0,
        )

        assert stats.is_slow is True

    def test_get_summary_empty(self) -> None:
        """Test summary with no queries."""
        logger = SlowQueryLogger()
        summary = logger.get_summary()

        assert summary["total_queries"] == 0
        assert summary["slow_queries"] == 0
        assert summary["slow_query_rate"] == 0.0

    def test_get_summary_with_queries(self) -> None:
        """Test summary with recorded queries."""
        logger = SlowQueryLogger(SlowQueryConfig(threshold_ms=100.0, enable_query_logging=False))

        # Record 8 fast queries and 2 slow queries
        for i in range(8):
            logger.record_query(f"SELECT {i}", duration_ms=50.0)
        for i in range(2):
            logger.record_query(f"SLOW SELECT {i}", duration_ms=150.0)

        summary = logger.get_summary()

        assert summary["total_queries"] == 10
        assert summary["slow_queries"] == 2
        assert summary["slow_query_rate"] == 0.2
        assert summary["avg_duration_ms"] == 70.0  # (8*50 + 2*150) / 10
        assert summary["max_duration_ms"] == 150.0

    def test_rolling_window(self) -> None:
        """Test that query stats have a rolling window."""
        logger = SlowQueryLogger()
        logger._max_stored_stats = 10  # Reduce for testing

        # Record more queries than max
        for i in range(15):
            logger.record_query(f"SELECT {i}", duration_ms=10.0)

        assert len(logger.get_query_stats()) == 10

    def test_clear(self) -> None:
        """Test clearing query statistics."""
        logger = SlowQueryLogger(SlowQueryConfig(enable_query_logging=False))

        logger.record_query("SELECT 1", duration_ms=10.0)
        logger.record_query("SELECT 2", duration_ms=200.0)

        logger.clear()

        assert len(logger.get_query_stats()) == 0
        assert len(logger.get_slow_queries()) == 0


class TestQueryOptimizer:
    """Tests for QueryOptimizer."""

    def test_with_selectinload_creates_loader(self) -> None:
        """Test that with_selectinload creates a valid loader option."""
        # Use a mock attribute to test the factory method
        mock_attr = MagicMock()
        with patch("elile.db.optimization.selectinload") as mock_selectinload:
            mock_selectinload.return_value = MagicMock()
            QueryOptimizer.with_selectinload(mock_attr)
            mock_selectinload.assert_called_once_with(mock_attr)

    def test_with_joinedload_creates_loader(self) -> None:
        """Test that with_joinedload creates a valid loader option."""
        # Use a mock attribute to test the factory method
        mock_attr = MagicMock()
        with patch("elile.db.optimization.joinedload") as mock_joinedload:
            mock_joinedload.return_value = MagicMock()
            QueryOptimizer.with_joinedload(mock_attr)
            mock_joinedload.assert_called_once_with(mock_attr)


class TestObserveQuery:
    """Tests for observe_query context manager."""

    @pytest.mark.asyncio
    async def test_observe_query_records_metrics(self) -> None:
        """Test that observe_query records metrics."""
        with patch(
            "elile.observability.metrics.record_db_query"
        ) as mock_record:
            async with observe_query("select", "entities"):
                await asyncio.sleep(0.01)  # Simulate some work

            # Verify metrics were recorded
            mock_record.assert_called_once()
            call_args = mock_record.call_args
            assert call_args.kwargs["operation"] == "select"
            assert call_args.kwargs["table"] == "entities"
            assert call_args.kwargs["duration_seconds"] > 0

    @pytest.mark.asyncio
    async def test_observe_query_without_metrics(self) -> None:
        """Test observe_query works without metrics module."""
        # The function catches ImportError internally, so we need to simulate that
        with patch.dict("sys.modules", {"elile.observability.metrics": None}):
            # Should not raise even if module is not available
            async with observe_query("select", "entities"):
                pass


class TestGetSlowQueryLogger:
    """Tests for get_slow_query_logger function."""

    def test_returns_singleton(self) -> None:
        """Test that get_slow_query_logger returns a singleton."""
        # Clear any existing global logger
        import elile.db.optimization as opt_module

        opt_module._global_slow_query_logger = None

        logger1 = get_slow_query_logger()
        logger2 = get_slow_query_logger()

        assert logger1 is logger2

    def test_creates_logger_if_none_exists(self) -> None:
        """Test that a logger is created if none exists."""
        import elile.db.optimization as opt_module

        opt_module._global_slow_query_logger = None

        logger = get_slow_query_logger()

        assert logger is not None
        assert isinstance(logger, SlowQueryLogger)


class TestSlowQueryLoggerIntegration:
    """Integration tests for slow query logging behavior."""

    def test_multiple_operations_tracked(self) -> None:
        """Test tracking multiple different operations."""
        logger = SlowQueryLogger(SlowQueryConfig(threshold_ms=100.0, enable_query_logging=False))

        # Record various operations
        logger.record_query(
            "SELECT * FROM entities", duration_ms=50.0, operation="SELECT", table_name="entities"
        )
        logger.record_query(
            "INSERT INTO entities VALUES(...)",
            duration_ms=30.0,
            operation="INSERT",
            table_name="entities",
        )
        logger.record_query(
            "UPDATE entities SET...", duration_ms=150.0, operation="UPDATE", table_name="entities"
        )
        logger.record_query(
            "DELETE FROM entities WHERE...",
            duration_ms=20.0,
            operation="DELETE",
            table_name="entities",
        )

        stats = logger.get_query_stats()
        assert len(stats) == 4

        slow_queries = logger.get_slow_queries()
        assert len(slow_queries) == 1
        assert slow_queries[0].operation == "UPDATE"

    def test_p95_calculation(self) -> None:
        """Test P95 duration calculation in summary."""
        logger = SlowQueryLogger(SlowQueryConfig(enable_query_logging=False))

        # Record 100 queries with predictable durations (1-100ms)
        for i in range(1, 101):
            logger.record_query(f"SELECT {i}", duration_ms=float(i))

        summary = logger.get_summary()

        # P95 index for 100 items is int(100 * 0.95) = 95, which gives value 96
        # (0-indexed, so sorted[95] = 96th value = 96ms)
        assert summary["p95_duration_ms"] == 96.0
        assert summary["max_duration_ms"] == 100.0
        assert summary["avg_duration_ms"] == 50.5  # Mean of 1-100


class TestOptimizedPoolConfigPresets:
    """Test configuration presets work correctly."""

    def test_production_has_query_timeouts(self) -> None:
        """Test that production config has appropriate timeouts."""
        config = OptimizedPoolConfig.for_production()

        assert "server_settings" in config.connect_args
        settings = config.connect_args["server_settings"]
        assert "statement_timeout" in settings
        assert "lock_timeout" in settings

    def test_development_enables_debugging(self) -> None:
        """Test that development config enables debugging features."""
        config = OptimizedPoolConfig.for_development()

        assert config.echo is True
        assert config.echo_pool is True

    def test_testing_minimizes_resources(self) -> None:
        """Test that testing config minimizes resources."""
        config = OptimizedPoolConfig.for_testing()

        assert config.pool_size == 1
        assert config.max_overflow == 0
        assert config.pool_pre_ping is False


class TestSlowQueryLoggerEdgeCases:
    """Test edge cases for SlowQueryLogger."""

    def test_empty_query_text(self) -> None:
        """Test handling of empty query text."""
        logger = SlowQueryLogger(SlowQueryConfig(enable_query_logging=False))

        stats = logger.record_query("", duration_ms=10.0)

        assert stats.query_text == ""
        assert len(logger.get_query_stats()) == 1

    def test_very_fast_query(self) -> None:
        """Test handling of very fast queries."""
        logger = SlowQueryLogger(SlowQueryConfig(enable_query_logging=False))

        stats = logger.record_query("SELECT 1", duration_ms=0.001)

        assert stats.is_slow is False
        assert stats.duration_ms == 0.001

    def test_negative_rows_affected_handled(self) -> None:
        """Test handling of negative rows affected (some drivers return -1)."""
        logger = SlowQueryLogger(SlowQueryConfig(enable_query_logging=False))

        stats = logger.record_query("SELECT 1", duration_ms=10.0, rows_affected=-1)

        assert stats.rows_affected == -1

    def test_limit_parameter_respected(self) -> None:
        """Test that limit parameter works for get_query_stats."""
        logger = SlowQueryLogger(SlowQueryConfig(enable_query_logging=False))

        for i in range(20):
            logger.record_query(f"SELECT {i}", duration_ms=10.0)

        stats = logger.get_query_stats(limit=5)
        assert len(stats) == 5

        # Should return the most recent 5
        assert stats[0].query_text == "SELECT 15"

    def test_limit_parameter_slow_queries(self) -> None:
        """Test that limit parameter works for get_slow_queries."""
        logger = SlowQueryLogger(SlowQueryConfig(threshold_ms=100.0, enable_query_logging=False))

        for i in range(20):
            logger.record_query(f"SLOW SELECT {i}", duration_ms=200.0)

        slow = logger.get_slow_queries(limit=5)
        assert len(slow) == 5
