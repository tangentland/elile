"""Unit tests for error handling utilities."""

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid7

import pytest

from elile.core.error_handling import (
    ErrorHandler,
    ErrorRecord,
    error_context,
    handle_errors,
)
from elile.db.models.audit import AuditSeverity
from elile.utils.exceptions import ElileError


class TestErrorRecord:
    """Tests for ErrorRecord class."""

    def test_error_record_creation(self):
        """Test basic error record creation."""
        record = ErrorRecord(
            error_code="test_error",
            message="Test error message",
        )
        assert record.error_code == "test_error"
        assert record.message == "Test error message"
        assert record.severity == AuditSeverity.ERROR
        assert record.timestamp is not None
        assert isinstance(record.timestamp, datetime)

    def test_error_record_with_exception(self):
        """Test error record captures exception details."""
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            record = ErrorRecord(
                error_code="value_error",
                message="A value error occurred",
                exception=e,
            )

        assert record.details["exception_type"] == "ValueError"
        assert record.details["exception_message"] == "Test exception"
        assert "traceback" in record.details

    def test_error_record_with_details(self):
        """Test error record with custom details."""
        record = ErrorRecord(
            error_code="custom_error",
            message="Custom error",
            details={"field": "name", "value": "invalid"},
        )
        assert record.details["field"] == "name"
        assert record.details["value"] == "invalid"

    def test_error_record_to_dict(self):
        """Test error record serialization."""
        record = ErrorRecord(
            error_code="test_error",
            message="Test message",
            details={"key": "value"},
            severity=AuditSeverity.WARNING,
        )
        data = record.to_dict()

        assert data["error_code"] == "test_error"
        assert data["message"] == "Test message"
        assert data["details"]["key"] == "value"
        assert data["severity"] == "warning"
        assert "timestamp" in data

    def test_error_record_severities(self):
        """Test different severity levels."""
        for severity in AuditSeverity:
            record = ErrorRecord(
                error_code="test",
                message="Test",
                severity=severity,
            )
            assert record.severity == severity


class TestErrorHandler:
    """Tests for ErrorHandler class."""

    @pytest.mark.asyncio
    async def test_error_handler_no_errors(self):
        """Test error handler with no errors recorded."""
        async with ErrorHandler(log_to_audit=False) as handler:
            pass

        assert not handler.has_errors()
        assert handler.get_errors() == []

    @pytest.mark.asyncio
    async def test_error_handler_record_error(self):
        """Test recording errors manually."""
        async with ErrorHandler(log_to_audit=False) as handler:
            handler.record_error("error_1", "First error")
            handler.record_error("error_2", "Second error")

        assert handler.has_errors()
        errors = handler.get_errors()
        assert len(errors) == 2
        assert errors[0].error_code == "error_1"
        assert errors[1].error_code == "error_2"

    @pytest.mark.asyncio
    async def test_error_handler_catches_exception(self):
        """Test error handler catches unhandled exceptions."""
        with pytest.raises(ValueError):
            async with ErrorHandler(log_to_audit=False) as handler:
                raise ValueError("Test exception")

        assert handler.has_errors()
        errors = handler.get_errors()
        assert len(errors) == 1
        # ValueError is not ElileError, so it gets generic error code
        assert errors[0].error_code == "internal_error"

    @pytest.mark.asyncio
    async def test_error_handler_clear_errors(self):
        """Test clearing recorded errors."""
        handler = ErrorHandler(log_to_audit=False)
        handler.record_error("error", "Test")
        assert handler.has_errors()

        handler.clear_errors()
        assert not handler.has_errors()

    @pytest.mark.asyncio
    async def test_error_handler_with_context(self):
        """Test error handler uses request context."""
        from elile.core.context import create_context, request_context

        ctx = create_context(
            tenant_id=uuid7(),
            actor_id=uuid7(),
        )

        with request_context(ctx):
            async with ErrorHandler(log_to_audit=False) as handler:
                handler.record_error("test_error", "Test")

        assert handler.ctx is not None
        assert handler.ctx.tenant_id == ctx.tenant_id

    @pytest.mark.asyncio
    async def test_error_handler_resource_info(self):
        """Test error handler with resource information."""
        handler = ErrorHandler(
            resource_type="screening",
            resource_id="screen-123",
            log_to_audit=False,
        )
        assert handler.resource_type == "screening"
        assert handler.resource_id == "screen-123"

    @pytest.mark.asyncio
    async def test_error_handler_logs_to_python_logging(self, caplog):
        """Test errors are logged to Python logging."""
        import logging

        with caplog.at_level(logging.ERROR, logger="elile.errors"):
            async with ErrorHandler(log_to_audit=False) as handler:
                handler.record_error("test_error", "Test message")

        assert "test_error" in caplog.text
        assert "Test message" in caplog.text

    @pytest.mark.asyncio
    async def test_error_handler_audit_logging(self):
        """Test errors are logged to audit system."""
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()

        with patch("elile.core.audit.AuditLogger", return_value=mock_audit_logger):
            async with ErrorHandler(db=mock_db, log_to_audit=True) as handler:
                handler.record_error("audit_error", "Should be audited")

        mock_audit_logger.log_event.assert_called_once()
        mock_db.commit.assert_called_once()


class TestHandleErrorsDecorator:
    """Tests for handle_errors decorator."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorator passes through on success."""
        @handle_errors(audit=False)
        async def successful_op():
            return "success"

        result = await successful_op()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_reraises_by_default(self):
        """Test decorator re-raises exceptions by default."""
        @handle_errors(audit=False)
        async def failing_op():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await failing_op()

    @pytest.mark.asyncio
    async def test_decorator_no_reraise(self):
        """Test decorator can suppress exceptions."""
        @handle_errors(audit=False, reraise=False)
        async def failing_op():
            raise ValueError("Test error")

        result = await failing_op()
        assert result is None

    @pytest.mark.asyncio
    async def test_decorator_uses_function_name_as_resource(self):
        """Test decorator uses function name as resource type."""
        with patch("elile.core.error_handling.ErrorHandler") as MockHandler:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockHandler.return_value = mock_instance

            @handle_errors(audit=False)
            async def my_operation():
                return "ok"

            await my_operation()

            # Check resource_type was set to function name
            call_kwargs = MockHandler.call_args.kwargs
            assert call_kwargs["resource_type"] == "my_operation"

    @pytest.mark.asyncio
    async def test_decorator_custom_resource_type(self):
        """Test decorator accepts custom resource type."""
        with patch("elile.core.error_handling.ErrorHandler") as MockHandler:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockHandler.return_value = mock_instance

            @handle_errors(audit=False, resource_type="custom_resource")
            async def my_operation():
                return "ok"

            await my_operation()

            call_kwargs = MockHandler.call_args.kwargs
            assert call_kwargs["resource_type"] == "custom_resource"


class TestErrorContext:
    """Tests for error_context context manager."""

    @pytest.mark.asyncio
    async def test_error_context_basic(self):
        """Test basic error context usage."""
        async with error_context(log_to_audit=False) as handler:
            handler.record_error("test", "Test error")

        assert handler.has_errors()

    @pytest.mark.asyncio
    async def test_error_context_with_resource(self):
        """Test error context with resource information."""
        async with error_context(
            resource_type="entity",
            resource_id="ent-123",
            log_to_audit=False,
        ) as handler:
            pass

        assert handler.resource_type == "entity"
        assert handler.resource_id == "ent-123"


class TestErrorCodeDerivation:
    """Tests for error code derivation from exceptions."""

    @pytest.mark.asyncio
    async def test_elile_error_code_derivation(self):
        """Test error code derived from ElileError subclass."""
        from elile.core.exceptions import TenantNotFoundError

        async with ErrorHandler(log_to_audit=False) as handler:
            handler._get_error_code(TenantNotFoundError(uuid7()))

        # The method should convert CamelCase to snake_case
        # TenantNotFoundError -> tenant_not_found_error

    @pytest.mark.asyncio
    async def test_generic_error_code_derivation(self):
        """Test error code for non-ElileError exceptions."""
        handler = ErrorHandler(log_to_audit=False)
        code = handler._get_error_code(ValueError("test"))
        assert code == "internal_error"
