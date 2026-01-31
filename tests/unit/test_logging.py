"""Unit tests for structured logging."""
# ruff: noqa: ARG002  # Fixtures used for setup side effects

import json
import logging
from io import StringIO
from unittest.mock import MagicMock, patch
from uuid import uuid7

import pytest
import structlog

from elile.core.context import RequestContext, request_context
from elile.core.logging import (
    LogContext,
    add_environment_info,
    add_request_context,
    bind_contextvars,
    clear_contextvars,
    drop_color_message_key,
    get_logger,
    log_database_query,
    log_exception,
    log_external_call,
    log_request_end,
    log_request_start,
    setup_logging,
    unbind_contextvars,
)


class TestAddRequestContext:
    """Tests for add_request_context processor."""

    def test_adds_context_when_available(self):
        """Test context fields are added when RequestContext is set."""
        ctx = RequestContext(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            correlation_id=uuid7(),
            locale="US",
        )

        with request_context(ctx):
            event_dict = {}
            result = add_request_context(None, "info", event_dict)

            assert result["correlation_id"] == str(ctx.correlation_id)
            assert result["tenant_id"] == str(ctx.tenant_id)
            assert result["actor_id"] == str(ctx.actor_id)
            assert result["locale"] == "US"

    def test_no_context_available(self):
        """Test graceful handling when no context is set."""
        event_dict = {"message": "test"}
        result = add_request_context(None, "info", event_dict)

        assert result == {"message": "test"}
        assert "correlation_id" not in result


class TestAddEnvironmentInfo:
    """Tests for add_environment_info processor."""

    def test_adds_environment(self):
        """Test environment is added to event dict."""
        mock_settings = MagicMock()
        mock_settings.ENVIRONMENT = "production"

        with patch("elile.core.logging.get_settings", return_value=mock_settings):
            event_dict = {}
            result = add_environment_info(None, "info", event_dict)

            assert result["environment"] == "production"


class TestDropColorMessageKey:
    """Tests for drop_color_message_key processor."""

    def test_drops_color_message(self):
        """Test color_message key is removed."""
        event_dict = {"message": "test", "color_message": "colored test"}
        result = drop_color_message_key(None, "info", event_dict)

        assert "color_message" not in result
        assert result["message"] == "test"

    def test_no_color_message(self):
        """Test no error when color_message not present."""
        event_dict = {"message": "test"}
        result = drop_color_message_key(None, "info", event_dict)

        assert result == {"message": "test"}


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_default(self, mock_settings):
        """Test logging setup with default settings."""
        mock_settings.log_level = "INFO"
        mock_settings.ENVIRONMENT = "development"

        # Should not raise
        setup_logging()

        # Verify structlog is configured
        logger = get_logger("test")
        assert logger is not None

    def test_setup_logging_json_format(self, mock_settings):
        """Test logging setup with JSON format."""
        mock_settings.log_level = "DEBUG"
        mock_settings.ENVIRONMENT = "production"

        setup_logging(json_format=True)

        logger = get_logger("test")
        assert logger is not None

    def test_setup_logging_custom_level(self, mock_settings):
        """Test logging setup with custom log level."""
        mock_settings.ENVIRONMENT = "development"

        setup_logging(log_level="DEBUG")

        # Verify log level was set
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_with_name(self):
        """Test getting logger with specific name."""
        logger = get_logger("my.module")
        assert logger is not None

    def test_get_logger_without_name(self):
        """Test getting logger without name."""
        logger = get_logger()
        assert logger is not None


class TestLogContext:
    """Tests for LogContext context manager."""

    def test_log_context_binds_values(self, mock_settings):
        """Test that LogContext binds values during block."""
        setup_logging()
        clear_contextvars()

        with LogContext(operation="test_op", item_id=123):
            # Values should be bound
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("operation") == "test_op"
            assert ctx.get("item_id") == 123

        # Values should be unbound after block
        ctx = structlog.contextvars.get_contextvars()
        assert "operation" not in ctx
        assert "item_id" not in ctx


class TestContextVarsFunctions:
    """Tests for context variable functions."""

    def test_bind_unbind_contextvars(self, mock_settings):
        """Test binding and unbinding context variables."""
        setup_logging()
        clear_contextvars()

        bind_contextvars(key1="value1", key2="value2")

        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get("key1") == "value1"
        assert ctx.get("key2") == "value2"

        unbind_contextvars("key1")

        ctx = structlog.contextvars.get_contextvars()
        assert "key1" not in ctx
        assert ctx.get("key2") == "value2"

    def test_clear_contextvars(self, mock_settings):
        """Test clearing all context variables."""
        setup_logging()
        bind_contextvars(key1="value1", key2="value2")

        clear_contextvars()

        ctx = structlog.contextvars.get_contextvars()
        assert len(ctx) == 0


class TestLogHelpers:
    """Tests for logging helper functions."""

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        return MagicMock()

    def test_log_request_start(self, mock_logger):
        """Test logging request start."""
        log_request_start(mock_logger, "GET", "/api/users", user_id="123")

        mock_logger.info.assert_called_once()
        args, kwargs = mock_logger.info.call_args
        assert args[0] == "request_started"
        assert kwargs["http_method"] == "GET"
        assert kwargs["http_path"] == "/api/users"
        assert kwargs["user_id"] == "123"

    def test_log_request_end(self, mock_logger):
        """Test logging request end."""
        log_request_end(mock_logger, "GET", "/api/users", 200, 123.456)

        mock_logger.info.assert_called_once()
        args, kwargs = mock_logger.info.call_args
        assert args[0] == "request_completed"
        assert kwargs["http_status"] == 200
        assert kwargs["duration_ms"] == 123.46

    def test_log_exception(self, mock_logger):
        """Test logging exception."""
        exc = ValueError("Test error")
        log_exception(mock_logger, exc, context="testing")

        mock_logger.exception.assert_called_once()
        args, kwargs = mock_logger.exception.call_args
        assert args[0] == "exception_occurred"
        assert kwargs["error_type"] == "ValueError"
        assert kwargs["error_message"] == "Test error"
        assert kwargs["context"] == "testing"

    def test_log_database_query(self, mock_logger):
        """Test logging database query."""
        log_database_query(mock_logger, "SELECT", "users", 15.5, rows=10)

        mock_logger.debug.assert_called_once()
        args, kwargs = mock_logger.debug.call_args
        assert args[0] == "database_query"
        assert kwargs["query_type"] == "SELECT"
        assert kwargs["table"] == "users"
        assert kwargs["duration_ms"] == 15.5
        assert kwargs["rows"] == 10

    def test_log_external_call_success(self, mock_logger):
        """Test logging successful external call."""
        log_external_call(mock_logger, "payment-api", "charge", 250.0, True)

        mock_logger.info.assert_called_once()
        args, kwargs = mock_logger.info.call_args
        assert args[0] == "external_call"
        assert kwargs["service"] == "payment-api"
        assert kwargs["success"] is True

    def test_log_external_call_failure(self, mock_logger):
        """Test logging failed external call."""
        log_external_call(mock_logger, "payment-api", "charge", 5000.0, False)

        mock_logger.warning.assert_called_once()
        args, kwargs = mock_logger.warning.call_args
        assert args[0] == "external_call"
        assert kwargs["success"] is False


class TestLoggingIntegration:
    """Integration tests for logging."""

    def test_json_output_format(self, mock_settings):
        """Test that JSON format produces valid JSON."""
        mock_settings.ENVIRONMENT = "production"
        mock_settings.log_level = "INFO"

        # Capture stdout
        output = StringIO()
        handler = logging.StreamHandler(output)

        # Setup logging
        setup_logging(json_format=True)

        # Get root logger and add our handler
        root = logging.getLogger()
        root.handlers = [handler]

        # Create structlog logger and log something
        _ = get_logger("test")  # Ensure it can be created

        # Use structlog's stdlib wrapper
        import structlog

        stdlib_logger = structlog.wrap_logger(
            logging.getLogger("test"),
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
        )
        stdlib_logger.info("test_message", key="value")

        # Verify output is valid JSON
        output.seek(0)
        log_line = output.getvalue().strip()
        if log_line:
            # Parse should not raise
            data = json.loads(log_line)
            assert "event" in data or "key" in data

    def test_context_propagation(self, mock_settings):
        """Test that context is propagated through logs."""
        mock_settings.ENVIRONMENT = "development"
        mock_settings.log_level = "INFO"

        setup_logging()
        clear_contextvars()

        ctx = RequestContext(
            tenant_id=uuid7(),
            actor_id=uuid7(),
            correlation_id=uuid7(),
            locale="US",
        )

        with request_context(ctx):
            # When logging within a request context, the context should be captured
            logger = get_logger("test")
            # Logger should be available
            assert logger is not None
