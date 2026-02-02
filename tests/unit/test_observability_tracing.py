"""Unit tests for OpenTelemetry tracing module."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import pytest

from elile.observability.tracing import (
    SpanKindType,
    TracingConfig,
    TracingManager,
    _serialize_arg,
    create_tracing_manager,
    get_current_span,
    get_tracer,
    get_tracing_manager,
    trace_provider_query,
    trace_sar_loop,
    trace_screening,
    traced,
    traced_async,
)


class TestTracingConfig:
    """Tests for TracingConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = TracingConfig()

        assert config.service_name == "elile"
        assert config.service_version == "0.1.0"
        assert config.environment == "development"
        assert config.enabled is True
        assert config.sample_rate == 1.0
        assert config.batch_export is True

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = TracingConfig(
            service_name="custom-service",
            service_version="2.0.0",
            environment="production",
            otlp_endpoint="http://localhost:4317",
            enabled=False,
            sample_rate=0.5,
        )

        assert config.service_name == "custom-service"
        assert config.service_version == "2.0.0"
        assert config.environment == "production"
        assert config.otlp_endpoint == "http://localhost:4317"
        assert config.enabled is False
        assert config.sample_rate == 0.5

    def test_from_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env with default environment."""
        # Clear any existing env vars
        monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        config = TracingConfig.from_env()

        assert config.service_name == "elile"
        assert config.otlp_endpoint is None

    def test_from_env_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env with custom environment variables."""
        monkeypatch.setenv("OTEL_SERVICE_NAME", "custom-service")
        monkeypatch.setenv("ELILE_VERSION", "3.0.0")
        monkeypatch.setenv("ELILE_ENVIRONMENT", "staging")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel:4317")
        monkeypatch.setenv("OTEL_TRACING_ENABLED", "false")
        monkeypatch.setenv("OTEL_SAMPLE_RATE", "0.25")

        config = TracingConfig.from_env()

        assert config.service_name == "custom-service"
        assert config.service_version == "3.0.0"
        assert config.environment == "staging"
        assert config.otlp_endpoint == "http://otel:4317"
        assert config.enabled is False
        assert config.sample_rate == 0.25

    def test_extra_resource_attributes(self) -> None:
        """Test extra resource attributes."""
        config = TracingConfig(
            extra_resource_attributes={"custom.key": "custom_value"},
        )

        assert config.extra_resource_attributes == {"custom.key": "custom_value"}


class TestTracingManager:
    """Tests for TracingManager."""

    def test_create_manager(self) -> None:
        """Test creating tracing manager."""
        config = TracingConfig(
            service_name="elile-test",
            service_version="0.1.0-test",
            environment="testing",
            enabled=True,
        )
        manager = TracingManager(config)

        assert manager.config == config
        assert manager._initialized is False

    def test_initialize_disabled(self) -> None:
        """Test initialization when tracing is disabled."""
        config = TracingConfig(enabled=False)
        manager = TracingManager(config)

        manager.initialize()

        assert manager._initialized is False

    def test_get_tracer(self) -> None:
        """Test getting tracer instance."""
        config = TracingConfig(
            service_name="test-service",
            service_version="1.0.0",
        )
        manager = TracingManager(config)

        tracer = manager.tracer

        assert tracer is not None
        assert manager._tracer == tracer

    def test_shutdown_not_initialized(self) -> None:
        """Test shutdown when not initialized."""
        config = TracingConfig(enabled=False)
        manager = TracingManager(config)

        # Should not raise
        manager.shutdown()
        assert manager._initialized is False


class TestSpanKindType:
    """Tests for SpanKindType enum."""

    def test_span_kind_values(self) -> None:
        """Test span kind enum values."""
        assert SpanKindType.INTERNAL.value == "internal"
        assert SpanKindType.SERVER.value == "server"
        assert SpanKindType.CLIENT.value == "client"
        assert SpanKindType.PRODUCER.value == "producer"
        assert SpanKindType.CONSUMER.value == "consumer"


class TestSerializeArg:
    """Tests for _serialize_arg helper function."""

    def test_serialize_string(self) -> None:
        """Test serializing string."""
        assert _serialize_arg("test") == "test"

    def test_serialize_int(self) -> None:
        """Test serializing integer."""
        assert _serialize_arg(42) == 42

    def test_serialize_float(self) -> None:
        """Test serializing float."""
        assert _serialize_arg(3.14) == 3.14

    def test_serialize_bool(self) -> None:
        """Test serializing boolean."""
        assert _serialize_arg(True) is True
        assert _serialize_arg(False) is False

    def test_serialize_none(self) -> None:
        """Test serializing None."""
        assert _serialize_arg(None) is None

    def test_serialize_uuid(self) -> None:
        """Test serializing UUID."""
        test_uuid = uuid4()
        assert _serialize_arg(test_uuid) == str(test_uuid)

    def test_serialize_datetime(self) -> None:
        """Test serializing datetime."""
        test_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert _serialize_arg(test_dt) == test_dt.isoformat()

    def test_serialize_enum(self) -> None:
        """Test serializing enum."""

        class TestEnum(Enum):
            VALUE = "test_value"

        assert _serialize_arg(TestEnum.VALUE) == "test_value"

    def test_serialize_complex_type(self) -> None:
        """Test serializing complex type as string."""

        class CustomClass:
            def __str__(self) -> str:
                return "custom_string"

        result = _serialize_arg(CustomClass())
        assert "custom_string" in result

    def test_serialize_complex_type_truncated(self) -> None:
        """Test that complex types are truncated when converted to string."""

        class LongClass:
            def __str__(self) -> str:
                return "x" * 1000

        result = _serialize_arg(LongClass())
        assert len(result) <= 500


class TestTracedDecorators:
    """Tests for traced decorators."""

    def test_traced_sync_function(self) -> None:
        """Test tracing synchronous function."""

        @traced("sync_operation")
        def sync_func(x: int, y: int) -> int:
            return x + y

        result = sync_func(1, 2)

        assert result == 3

    def test_traced_sync_with_exception(self) -> None:
        """Test tracing sync function that raises exception."""

        @traced("failing_operation")
        def failing_func() -> None:
            raise RuntimeError("Test error")

        with pytest.raises(RuntimeError, match="Test error"):
            failing_func()

    @pytest.mark.asyncio
    async def test_traced_async_function(self) -> None:
        """Test tracing asynchronous function."""

        @traced_async("async_operation")
        async def async_func(x: int) -> int:
            await asyncio.sleep(0.001)
            return x * 2

        result = await async_func(5)

        assert result == 10

    @pytest.mark.asyncio
    async def test_traced_async_with_exception(self) -> None:
        """Test tracing async function that raises exception."""

        @traced_async("failing_async")
        async def failing_async_func() -> None:
            raise ValueError("Async error")

        with pytest.raises(ValueError, match="Async error"):
            await failing_async_func()

    def test_traced_preserves_function_metadata(self) -> None:
        """Test that traced decorator preserves function metadata."""

        @traced("test_op")
        def documented_func() -> None:
            """This is a docstring."""
            pass

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a docstring."

    @pytest.mark.asyncio
    async def test_traced_async_preserves_function_metadata(self) -> None:
        """Test that traced_async decorator preserves function metadata."""

        @traced_async("test_op")
        async def documented_async_func() -> None:
            """This is an async docstring."""
            pass

        assert documented_async_func.__name__ == "documented_async_func"
        assert documented_async_func.__doc__ == "This is an async docstring."


class TestSpecializedTracers:
    """Tests for specialized tracing decorators."""

    @pytest.mark.asyncio
    async def test_trace_sar_loop(self) -> None:
        """Test SAR loop tracing decorator."""

        @trace_sar_loop(info_type="criminal", iteration=1)
        async def sar_operation() -> dict[str, Any]:
            return {"confidence_score": 0.85, "facts_discovered": 5}

        result = await sar_operation()

        assert result["confidence_score"] == 0.85
        assert result["facts_discovered"] == 5

    @pytest.mark.asyncio
    async def test_trace_sar_loop_with_exception(self) -> None:
        """Test SAR loop tracing with exception."""

        @trace_sar_loop(info_type="criminal", iteration=1)
        async def failing_sar_operation() -> dict[str, Any]:
            raise RuntimeError("SAR error")

        with pytest.raises(RuntimeError, match="SAR error"):
            await failing_sar_operation()

    @pytest.mark.asyncio
    async def test_trace_screening(self) -> None:
        """Test screening tracing decorator."""
        screening_id = uuid4()

        @trace_screening(screening_id=screening_id, tier="standard", degree="d1")
        async def screening_operation() -> dict[str, Any]:
            return {"risk_score": 25, "status": "complete"}

        result = await screening_operation()

        assert result["risk_score"] == 25
        assert result["status"] == "complete"

    @pytest.mark.asyncio
    async def test_trace_screening_with_exception(self) -> None:
        """Test screening tracing with exception."""
        screening_id = uuid4()

        @trace_screening(screening_id=screening_id, tier="enhanced", degree="d3")
        async def failing_screening_operation() -> dict[str, Any]:
            raise ValueError("Screening error")

        with pytest.raises(ValueError, match="Screening error"):
            await failing_screening_operation()

    @pytest.mark.asyncio
    async def test_trace_provider_query(self) -> None:
        """Test provider query tracing decorator."""

        @trace_provider_query(provider_id="sterling", check_type="criminal_national")
        async def provider_operation() -> dict[str, Any]:
            return {"success": True, "cache_hit": False}

        result = await provider_operation()

        assert result["success"] is True
        assert result["cache_hit"] is False

    @pytest.mark.asyncio
    async def test_trace_provider_query_with_exception(self) -> None:
        """Test provider query tracing with exception."""

        @trace_provider_query(provider_id="checkr", check_type="credit")
        async def failing_provider_operation() -> dict[str, Any]:
            raise RuntimeError("Provider error")

        with pytest.raises(RuntimeError, match="Provider error"):
            await failing_provider_operation()


class TestGetCurrentSpan:
    """Tests for get_current_span function."""

    def test_get_current_span_returns_span(self) -> None:
        """Test getting current span."""
        span = get_current_span()

        # Should return a span (may be non-recording if no active span)
        assert span is not None


class TestGetTracer:
    """Tests for get_tracer function."""

    def test_get_default_tracer(self) -> None:
        """Test getting default tracer."""
        tracer = get_tracer()
        assert tracer is not None

    def test_get_named_tracer(self) -> None:
        """Test getting named tracer."""
        tracer = get_tracer("custom-tracer")
        assert tracer is not None


class TestTracingManagerSingleton:
    """Tests for tracing manager singleton functions."""

    def test_get_tracing_manager_returns_same_instance(self) -> None:
        """Test that get_tracing_manager returns singleton."""
        manager1 = get_tracing_manager()
        manager2 = get_tracing_manager()

        assert manager1 is manager2

    def test_create_tracing_manager_replaces_singleton(self) -> None:
        """Test that create_tracing_manager replaces singleton."""
        config = TracingConfig(service_name="new-service")
        manager = create_tracing_manager(config)

        assert manager.config.service_name == "new-service"
        assert get_tracing_manager() is manager
