"""OpenTelemetry tracing instrumentation for Elile.

This module provides distributed tracing capabilities using OpenTelemetry:
- Automatic FastAPI instrumentation
- Custom span decorators for key operations
- Context propagation across async boundaries
- Integration with OTLP exporters for trace collection
"""

from __future__ import annotations

import functools
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar
from uuid import UUID

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.trace import Span, SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

__all__ = [
    "TracingConfig",
    "TracingManager",
    "SpanKindType",
    "traced",
    "traced_async",
    "add_span_attributes",
    "add_span_event",
    "record_exception",
    "get_current_span",
    "get_tracer",
    "create_tracing_manager",
]

P = ParamSpec("P")
R = TypeVar("R")


class SpanKindType(str, Enum):
    """Span kinds for categorizing operations."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


@dataclass
class TracingConfig:
    """Configuration for OpenTelemetry tracing.

    Attributes:
        service_name: Name of the service for trace identification.
        service_version: Version of the service.
        environment: Deployment environment (development, staging, production).
        otlp_endpoint: OTLP exporter endpoint URL.
        enabled: Whether tracing is enabled.
        sample_rate: Sampling rate for traces (0.0 to 1.0).
        batch_export: Use batch span processor for better performance.
        max_queue_size: Maximum queue size for batch processor.
        max_export_batch_size: Maximum batch size for exports.
        export_timeout_millis: Export timeout in milliseconds.
    """

    service_name: str = "elile"
    service_version: str = "0.1.0"
    environment: str = "development"
    otlp_endpoint: str | None = None
    enabled: bool = True
    sample_rate: float = 1.0
    batch_export: bool = True
    max_queue_size: int = 2048
    max_export_batch_size: int = 512
    export_timeout_millis: int = 30000
    extra_resource_attributes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> TracingConfig:
        """Create configuration from environment variables."""
        return cls(
            service_name=os.getenv("OTEL_SERVICE_NAME", "elile"),
            service_version=os.getenv("ELILE_VERSION", "0.1.0"),
            environment=os.getenv("ELILE_ENVIRONMENT", "development"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            enabled=os.getenv("OTEL_TRACING_ENABLED", "true").lower() == "true",
            sample_rate=float(os.getenv("OTEL_SAMPLE_RATE", "1.0")),
            batch_export=os.getenv("OTEL_BATCH_EXPORT", "true").lower() == "true",
        )


class TracingManager:
    """Manages OpenTelemetry tracing setup and instrumentation.

    This class handles:
    - TracerProvider configuration with OTLP export
    - Automatic instrumentation for FastAPI, SQLAlchemy, and HTTPX
    - Custom tracer access for application spans
    """

    def __init__(self, config: TracingConfig | None = None) -> None:
        """Initialize the tracing manager.

        Args:
            config: Tracing configuration. Uses defaults if not provided.
        """
        self.config = config or TracingConfig()
        self._tracer_provider: TracerProvider | None = None
        self._tracer: trace.Tracer | None = None
        self._initialized: bool = False

    @property
    def tracer(self) -> trace.Tracer:
        """Get the tracer instance."""
        if self._tracer is None:
            self._tracer = trace.get_tracer(
                self.config.service_name,
                self.config.service_version,
            )
        return self._tracer

    def initialize(self) -> None:
        """Initialize the tracing system.

        Sets up the TracerProvider with OTLP exporter and configures
        automatic instrumentation for supported libraries.
        """
        if self._initialized or not self.config.enabled:
            return

        # Create resource with service attributes
        resource_attributes = {
            "service.name": self.config.service_name,
            "service.version": self.config.service_version,
            "deployment.environment": self.config.environment,
        }
        resource_attributes.update(self.config.extra_resource_attributes)
        resource = Resource.create(resource_attributes)

        # Create tracer provider
        self._tracer_provider = TracerProvider(resource=resource)

        # Configure exporter if endpoint is set
        if self.config.otlp_endpoint:
            exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint)

            if self.config.batch_export:
                processor = BatchSpanProcessor(
                    exporter,
                    max_queue_size=self.config.max_queue_size,
                    max_export_batch_size=self.config.max_export_batch_size,
                    export_timeout_millis=self.config.export_timeout_millis,
                )
            else:
                processor = SimpleSpanProcessor(exporter)

            self._tracer_provider.add_span_processor(processor)

        # Set global tracer provider
        trace.set_tracer_provider(self._tracer_provider)

        self._initialized = True

    def instrument_fastapi(self, app: FastAPI) -> None:
        """Instrument a FastAPI application.

        Args:
            app: The FastAPI application to instrument.
        """
        if not self.config.enabled:
            return

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="health,health/db,health/ready,metrics",
        )

    def instrument_sqlalchemy(self, engine: AsyncEngine) -> None:
        """Instrument SQLAlchemy for database tracing.

        Args:
            engine: The SQLAlchemy async engine to instrument.
        """
        if not self.config.enabled:
            return

        # Get sync engine for instrumentation
        SQLAlchemyInstrumentor().instrument(
            engine=engine.sync_engine,
            enable_commenter=True,
        )

    def instrument_httpx(self) -> None:
        """Instrument HTTPX client for outbound HTTP tracing."""
        if not self.config.enabled:
            return

        HTTPXClientInstrumentor().instrument()

    def shutdown(self) -> None:
        """Shutdown the tracing system and flush pending spans."""
        if self._tracer_provider is not None:
            self._tracer_provider.shutdown()
            self._initialized = False


# Global tracing manager instance
_tracing_manager: TracingManager | None = None


def get_tracing_manager() -> TracingManager:
    """Get the global tracing manager instance."""
    global _tracing_manager
    if _tracing_manager is None:
        _tracing_manager = TracingManager(TracingConfig.from_env())
    return _tracing_manager


def create_tracing_manager(config: TracingConfig | None = None) -> TracingManager:
    """Create and register a new tracing manager.

    Args:
        config: Optional tracing configuration.

    Returns:
        The configured TracingManager instance.
    """
    global _tracing_manager
    _tracing_manager = TracingManager(config)
    return _tracing_manager


def get_tracer(name: str | None = None) -> trace.Tracer:
    """Get a tracer instance.

    Args:
        name: Optional tracer name. Uses service name if not provided.

    Returns:
        OpenTelemetry Tracer instance.
    """
    manager = get_tracing_manager()
    if name:
        return trace.get_tracer(name, manager.config.service_version)
    return manager.tracer


def get_current_span() -> Span:
    """Get the current active span.

    Returns:
        The current span, or a non-recording span if none is active.
    """
    return trace.get_current_span()


def add_span_attributes(**attributes: Any) -> None:
    """Add attributes to the current span.

    Args:
        **attributes: Key-value pairs to add as span attributes.
    """
    span = get_current_span()
    for key, value in attributes.items():
        if value is not None:
            # Convert UUIDs and other types to strings
            if isinstance(value, UUID):
                value = str(value)
            elif isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, Enum):
                value = value.value
            span.set_attribute(key, value)


def add_span_event(
    name: str,
    attributes: dict[str, Any] | None = None,
    timestamp: datetime | None = None,
) -> None:
    """Add an event to the current span.

    Args:
        name: Event name.
        attributes: Optional event attributes.
        timestamp: Optional event timestamp.
    """
    span = get_current_span()
    event_attrs: dict[str, Any] = {}
    if attributes:
        for key, value in attributes.items():
            if isinstance(value, UUID):
                event_attrs[key] = str(value)
            elif isinstance(value, datetime):
                event_attrs[key] = value.isoformat()
            elif isinstance(value, Enum):
                event_attrs[key] = value.value
            else:
                event_attrs[key] = value

    ts = int(timestamp.timestamp() * 1e9) if timestamp else None
    span.add_event(name, event_attrs, ts)


def record_exception(
    exception: BaseException,
    attributes: dict[str, Any] | None = None,
    escaped: bool = True,
) -> None:
    """Record an exception on the current span.

    Args:
        exception: The exception to record.
        attributes: Optional additional attributes.
        escaped: Whether the exception escaped the span's scope.
    """
    span = get_current_span()
    span.record_exception(exception, attributes=attributes, escaped=escaped)
    span.set_status(Status(StatusCode.ERROR, str(exception)))


@contextmanager
def create_span(
    name: str,
    kind: SpanKindType = SpanKindType.INTERNAL,
    attributes: dict[str, Any] | None = None,
) -> Generator[Span, None, None]:
    """Create a new span as a context manager.

    Args:
        name: Span name.
        kind: Span kind (internal, server, client, etc.).
        attributes: Optional span attributes.

    Yields:
        The created span.
    """
    tracer = get_tracer()
    otel_kind = SpanKind.INTERNAL
    if kind == SpanKindType.SERVER:
        otel_kind = SpanKind.SERVER
    elif kind == SpanKindType.CLIENT:
        otel_kind = SpanKind.CLIENT
    elif kind == SpanKindType.PRODUCER:
        otel_kind = SpanKind.PRODUCER
    elif kind == SpanKindType.CONSUMER:
        otel_kind = SpanKind.CONSUMER

    with tracer.start_as_current_span(name, kind=otel_kind, attributes=attributes) as span:
        yield span


def traced(
    name: str | None = None,
    kind: SpanKindType = SpanKindType.INTERNAL,
    record_args: bool = False,
    record_result: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace a synchronous function.

    Args:
        name: Span name. Uses function name if not provided.
        kind: Span kind.
        record_args: Whether to record function arguments as attributes.
        record_result: Whether to record the return value as an attribute.

    Returns:
        Decorated function with tracing.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with create_span(span_name, kind) as span:
                if record_args:
                    _record_call_args(span, args, kwargs)
                try:
                    result = func(*args, **kwargs)
                    if record_result and result is not None:
                        span.set_attribute("result", str(result)[:1000])
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    record_exception(e)
                    raise

        return wrapper

    return decorator


def traced_async(
    name: str | None = None,
    kind: SpanKindType = SpanKindType.INTERNAL,
    record_args: bool = False,
    record_result: bool = False,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator to trace an asynchronous function.

    Args:
        name: Span name. Uses function name if not provided.
        kind: Span kind.
        record_args: Whether to record function arguments as attributes.
        record_result: Whether to record the return value as an attribute.

    Returns:
        Decorated async function with tracing.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with create_span(span_name, kind) as span:
                if record_args:
                    _record_call_args(span, args, kwargs)
                try:
                    result = await func(*args, **kwargs)
                    if record_result and result is not None:
                        span.set_attribute("result", str(result)[:1000])
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    record_exception(e)
                    raise

        return wrapper

    return decorator


def _record_call_args(span: Span, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    """Record function call arguments as span attributes.

    Args:
        span: The span to add attributes to.
        args: Positional arguments.
        kwargs: Keyword arguments.
    """
    # Record positional args (skip self/cls for methods)
    for i, arg in enumerate(args):
        if i == 0 and hasattr(arg, "__class__"):
            # Skip self/cls
            continue
        value = _serialize_arg(arg)
        if value is not None:
            span.set_attribute(f"arg.{i}", value)

    # Record keyword args
    for key, value in kwargs.items():
        serialized = _serialize_arg(value)
        if serialized is not None:
            span.set_attribute(f"arg.{key}", serialized)


def _serialize_arg(value: Any) -> str | int | float | bool | None:
    """Serialize an argument value for span attributes.

    Args:
        value: The value to serialize.

    Returns:
        Serialized value suitable for span attributes, or None if not serializable.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    # For complex types, return a truncated string representation
    try:
        return str(value)[:500]
    except Exception:
        return None


# Pre-configured span decorators for common operations
def trace_sar_loop(
    info_type: str | None = None,
    iteration: int | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator for tracing SAR loop operations.

    Args:
        info_type: Information type being processed.
        iteration: Current iteration number.

    Returns:
        Decorated function with SAR-specific tracing.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with create_span("sar_loop.execute") as span:
                if info_type:
                    span.set_attribute("sar.info_type", info_type)
                if iteration is not None:
                    span.set_attribute("sar.iteration", iteration)

                try:
                    result = await func(*args, **kwargs)

                    # Extract metrics from result if available
                    if hasattr(result, "confidence_score"):
                        span.set_attribute("sar.confidence_score", result.confidence_score)
                    if hasattr(result, "facts_discovered"):
                        span.set_attribute("sar.facts_discovered", result.facts_discovered)

                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    record_exception(e)
                    raise

        return wrapper

    return decorator


def trace_screening(
    screening_id: UUID | None = None,
    tier: str | None = None,
    degree: str | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator for tracing screening operations.

    Args:
        screening_id: Screening identifier.
        tier: Service tier (Standard/Enhanced).
        degree: Search degree (D1/D2/D3).

    Returns:
        Decorated function with screening-specific tracing.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with create_span("screening.execute", kind=SpanKindType.INTERNAL) as span:
                if screening_id:
                    span.set_attribute("screening.id", str(screening_id))
                if tier:
                    span.set_attribute("screening.tier", tier)
                if degree:
                    span.set_attribute("screening.degree", degree)

                add_span_event("screening_started")

                try:
                    result = await func(*args, **kwargs)

                    # Extract metrics from result if available
                    if hasattr(result, "risk_score"):
                        span.set_attribute("screening.risk_score", result.risk_score)
                    if hasattr(result, "status"):
                        span.set_attribute("screening.status", str(result.status))

                    add_span_event("screening_completed")
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    add_span_event("screening_failed", {"error": str(e)})
                    record_exception(e)
                    raise

        return wrapper

    return decorator


def trace_provider_query(
    provider_id: str | None = None,
    check_type: str | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator for tracing data provider queries.

    Args:
        provider_id: Provider identifier.
        check_type: Type of check being performed.

    Returns:
        Decorated function with provider query tracing.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with create_span("provider.query", kind=SpanKindType.CLIENT) as span:
                if provider_id:
                    span.set_attribute("provider.id", provider_id)
                if check_type:
                    span.set_attribute("provider.check_type", check_type)

                start_time = datetime.now(UTC)

                try:
                    result = await func(*args, **kwargs)

                    duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
                    span.set_attribute("provider.duration_ms", duration_ms)

                    if hasattr(result, "success"):
                        span.set_attribute("provider.success", result.success)
                    if hasattr(result, "cache_hit"):
                        span.set_attribute("provider.cache_hit", result.cache_hit)

                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
                    span.set_attribute("provider.duration_ms", duration_ms)
                    record_exception(e)
                    raise

        return wrapper

    return decorator


# Context propagation helper
propagator = TraceContextTextMapPropagator()


def inject_trace_context(carrier: dict[str, str]) -> None:
    """Inject trace context into a carrier dict for propagation.

    Args:
        carrier: Dictionary to inject trace context into.
    """
    propagator.inject(carrier)


def extract_trace_context(carrier: dict[str, str]) -> trace.Context:
    """Extract trace context from a carrier dict.

    Args:
        carrier: Dictionary containing trace context.

    Returns:
        Extracted trace context.
    """
    return propagator.extract(carrier)
