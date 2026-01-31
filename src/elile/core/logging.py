"""Structured logging configuration for Elile.

Provides structured JSON logging with correlation ID tracking,
context propagation, and log level management using structlog.
"""
# ruff: noqa: ARG001  # Processor signatures required by structlog API

import logging
import sys
from typing import Any, Literal

import structlog
from structlog.types import Processor

from elile.config.settings import get_settings
from elile.core.context import get_current_context_or_none

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def add_request_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add request context to log entries.

    Extracts correlation_id, tenant_id, and actor_id from the current
    RequestContext if available.
    """
    ctx = get_current_context_or_none()
    if ctx is not None:
        event_dict["correlation_id"] = str(ctx.correlation_id)
        event_dict["tenant_id"] = str(ctx.tenant_id)
        event_dict["actor_id"] = str(ctx.actor_id)
        event_dict["locale"] = ctx.locale

    return event_dict


def add_environment_info(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add environment information to log entries."""
    settings = get_settings()
    event_dict["environment"] = settings.ENVIRONMENT
    return event_dict


def drop_color_message_key(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Drop the color_message key if present.

    This key is added by uvicorn and we don't need it in structured logs.
    """
    event_dict.pop("color_message", None)
    return event_dict


def setup_logging(
    log_level: LogLevel | None = None,
    json_format: bool | None = None,
    add_timestamp: bool = True,
) -> None:
    """Configure structured logging for the application.

    Args:
        log_level: Override log level (default from settings)
        json_format: Use JSON output (default: True in production, False in dev)
        add_timestamp: Include timestamp in log entries
    """
    settings = get_settings()

    # Determine effective settings
    effective_level = log_level or settings.log_level
    effective_json = (
        json_format if json_format is not None else settings.ENVIRONMENT == "production"
    )

    # Convert string level to numeric
    numeric_level = getattr(logging, effective_level.upper(), logging.INFO)

    # Build processor chain
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_request_context,
        add_environment_info,
        drop_color_message_key,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if add_timestamp:
        shared_processors.insert(0, structlog.processors.TimeStamper(fmt="iso"))

    if effective_json:
        # JSON logging for production
        shared_processors.append(structlog.processors.format_exc_info)

        structlog.configure(
            processors=shared_processors
            + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    else:
        # Console logging for development
        structlog.configure(
            processors=shared_processors
            + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
        )

    # Configure standard library logging to use structlog
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(numeric_level)

    # Configure specific loggers
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "sqlalchemy"]:
        logger = logging.getLogger(logger_name)
        logger.handlers = [handler]
        logger.propagate = False

    # Set SQLAlchemy logging level (quieter by default)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (uses caller module if None)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class LogContext:
    """Context manager for adding temporary log context.

    Example:
        with LogContext(operation="process_order", order_id=123):
            logger.info("Processing started")
            # All logs in this block will include operation and order_id
    """

    def __init__(self, **kwargs: Any):
        """Initialize with context values to add."""
        self.context = kwargs
        self._token = None

    def __enter__(self) -> "LogContext":
        """Enter context and bind values."""
        structlog.contextvars.bind_contextvars(**self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and unbind values."""
        structlog.contextvars.unbind_contextvars(*self.context.keys())


def bind_contextvars(**kwargs: Any) -> None:
    """Bind values to the structlog context variables.

    These values will be included in all subsequent log entries
    until explicitly unbound.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_contextvars(*keys: str) -> None:
    """Unbind values from the structlog context variables."""
    structlog.contextvars.unbind_contextvars(*keys)


def clear_contextvars() -> None:
    """Clear all structlog context variables."""
    structlog.contextvars.clear_contextvars()


# Convenience functions for common log patterns
def log_request_start(
    logger: structlog.stdlib.BoundLogger,
    method: str,
    path: str,
    **kwargs: Any,
) -> None:
    """Log the start of an HTTP request."""
    logger.info(
        "request_started",
        http_method=method,
        http_path=path,
        **kwargs,
    )


def log_request_end(
    logger: structlog.stdlib.BoundLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **kwargs: Any,
) -> None:
    """Log the end of an HTTP request."""
    logger.info(
        "request_completed",
        http_method=method,
        http_path=path,
        http_status=status_code,
        duration_ms=round(duration_ms, 2),
        **kwargs,
    )


def log_exception(
    logger: structlog.stdlib.BoundLogger,
    exc: Exception,
    **kwargs: Any,
) -> None:
    """Log an exception with full context."""
    logger.exception(
        "exception_occurred",
        error_type=type(exc).__name__,
        error_message=str(exc),
        **kwargs,
    )


def log_database_query(
    logger: structlog.stdlib.BoundLogger,
    query_type: str,
    table: str,
    duration_ms: float,
    **kwargs: Any,
) -> None:
    """Log a database query execution."""
    logger.debug(
        "database_query",
        query_type=query_type,
        table=table,
        duration_ms=round(duration_ms, 2),
        **kwargs,
    )


def log_external_call(
    logger: structlog.stdlib.BoundLogger,
    service: str,
    operation: str,
    duration_ms: float,
    success: bool,
    **kwargs: Any,
) -> None:
    """Log an external service call."""
    level = "info" if success else "warning"
    getattr(logger, level)(
        "external_call",
        service=service,
        operation=operation,
        duration_ms=round(duration_ms, 2),
        success=success,
        **kwargs,
    )
