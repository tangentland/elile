"""Unit tests for configuration validation."""

import pytest
from pydantic import SecretStr

from elile.config.settings import Settings
from elile.config.validation import (
    ConfigurationError,
    ValidationResult,
    ValidationSeverity,
    get_configuration_summary,
    validate_configuration,
    validate_or_raise,
)


class TestValidationResult:
    """Tests for ValidationResult class."""

    def test_validation_result_str_error(self):
        """Test string representation for error."""
        result = ValidationResult(
            field="TEST_FIELD",
            severity=ValidationSeverity.ERROR,
            message="Test error message",
        )
        text = str(result)
        assert "[ERROR]" in text
        assert "TEST_FIELD" in text
        assert "Test error message" in text

    def test_validation_result_str_warning(self):
        """Test string representation for warning."""
        result = ValidationResult(
            field="TEST_FIELD",
            severity=ValidationSeverity.WARNING,
            message="Test warning message",
        )
        text = str(result)
        assert "[WARNING]" in text
        assert "TEST_FIELD" in text

    def test_validation_result_with_suggestion(self):
        """Test string representation with suggestion."""
        result = ValidationResult(
            field="TEST_FIELD",
            severity=ValidationSeverity.ERROR,
            message="Test message",
            suggestion="Fix this by doing X",
        )
        text = str(result)
        assert "Suggestion:" in text
        assert "Fix this by doing X" in text


class TestDatabaseValidation:
    """Tests for database configuration validation."""

    def test_valid_postgresql_url(self):
        """Test valid PostgreSQL URL passes."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            ENVIRONMENT="development",
        )
        results = validate_configuration(settings)
        db_errors = [r for r in results if r.field == "DATABASE_URL" and r.severity == ValidationSeverity.ERROR]
        assert len(db_errors) == 0

    def test_valid_sqlite_url(self):
        """Test valid SQLite URL passes."""
        settings = Settings(
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            ENVIRONMENT="development",
        )
        results = validate_configuration(settings)
        db_errors = [r for r in results if r.field == "DATABASE_URL" and r.severity == ValidationSeverity.ERROR]
        assert len(db_errors) == 0

    def test_small_pool_size_warning(self):
        """Test warning for small pool size."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            DATABASE_POOL_SIZE=2,
            ENVIRONMENT="development",
        )
        results = validate_configuration(settings)
        pool_warnings = [r for r in results if r.field == "DATABASE_POOL_SIZE"]
        assert len(pool_warnings) > 0
        assert pool_warnings[0].severity == ValidationSeverity.WARNING

    def test_large_pool_size_warning(self):
        """Test warning for large pool size."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            DATABASE_POOL_SIZE=150,
            ENVIRONMENT="development",
        )
        results = validate_configuration(settings)
        pool_warnings = [r for r in results if r.field == "DATABASE_POOL_SIZE"]
        assert len(pool_warnings) > 0


class TestSecurityValidation:
    """Tests for security configuration validation."""

    def test_production_requires_encryption_key(self):
        """Test encryption key required in production."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            ENVIRONMENT="production",
            DEBUG=False,
            ENCRYPTION_KEY=None,
            API_SECRET_KEY=SecretStr("a" * 64),
        )
        results = validate_configuration(settings)
        encryption_errors = [
            r for r in results
            if r.field == "ENCRYPTION_KEY" and r.severity == ValidationSeverity.ERROR
        ]
        assert len(encryption_errors) > 0

    def test_production_requires_api_key(self):
        """Test API key required in production."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            ENVIRONMENT="production",
            DEBUG=False,
            ENCRYPTION_KEY=SecretStr("a" * 44),
            API_SECRET_KEY=None,
        )
        results = validate_configuration(settings)
        api_key_errors = [
            r for r in results
            if r.field == "API_SECRET_KEY" and r.severity == ValidationSeverity.ERROR
        ]
        assert len(api_key_errors) > 0

    def test_short_api_key_warning(self):
        """Test warning for short API key."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            ENVIRONMENT="development",
            API_SECRET_KEY=SecretStr("short"),
        )
        results = validate_configuration(settings)
        key_warnings = [
            r for r in results
            if r.field == "API_SECRET_KEY" and r.severity == ValidationSeverity.WARNING
        ]
        assert len(key_warnings) > 0

    def test_development_encryption_warning(self):
        """Test warning for missing encryption in development."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            ENVIRONMENT="development",
            ENCRYPTION_KEY=None,
        )
        results = validate_configuration(settings)
        encryption_warnings = [
            r for r in results
            if r.field == "ENCRYPTION_KEY" and r.severity == ValidationSeverity.WARNING
        ]
        assert len(encryption_warnings) > 0


class TestAPIValidation:
    """Tests for API configuration validation."""

    def test_invalid_port(self):
        """Test error for invalid port number."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            API_PORT=0,
            ENVIRONMENT="development",
        )
        results = validate_configuration(settings)
        port_errors = [
            r for r in results
            if r.field == "API_PORT" and r.severity == ValidationSeverity.ERROR
        ]
        assert len(port_errors) > 0

    def test_production_wildcard_cors_error(self):
        """Test error for wildcard CORS in production."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            ENVIRONMENT="production",
            DEBUG=False,
            ENCRYPTION_KEY=SecretStr("a" * 44),
            API_SECRET_KEY=SecretStr("a" * 64),
            CORS_ORIGINS=["*"],
        )
        results = validate_configuration(settings)
        cors_errors = [
            r for r in results
            if r.field == "CORS_ORIGINS" and r.severity == ValidationSeverity.ERROR
        ]
        assert len(cors_errors) > 0


class TestEnvironmentValidation:
    """Tests for environment-specific validation."""

    def test_production_debug_error(self):
        """Test error for debug mode in production."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            ENVIRONMENT="production",
            DEBUG=True,
            ENCRYPTION_KEY=SecretStr("a" * 44),
            API_SECRET_KEY=SecretStr("a" * 64),
        )
        results = validate_configuration(settings)
        debug_errors = [
            r for r in results
            if r.field == "DEBUG" and r.severity == ValidationSeverity.ERROR
        ]
        assert len(debug_errors) > 0

    def test_production_debug_log_warning(self):
        """Test warning for DEBUG log level in production."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            ENVIRONMENT="production",
            DEBUG=False,
            log_level="DEBUG",
            ENCRYPTION_KEY=SecretStr("a" * 44),
            API_SECRET_KEY=SecretStr("a" * 64),
        )
        results = validate_configuration(settings)
        log_warnings = [
            r for r in results
            if r.field == "log_level" and r.severity == ValidationSeverity.WARNING
        ]
        assert len(log_warnings) > 0


class TestValidateOrRaise:
    """Tests for validate_or_raise function."""

    def test_raises_on_errors(self):
        """Test function raises ConfigurationError on validation errors."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            ENVIRONMENT="production",
            DEBUG=True,  # Error: debug in production
        )
        with pytest.raises(ConfigurationError) as exc_info:
            validate_or_raise(settings)

        assert "DEBUG" in str(exc_info.value)

    def test_does_not_raise_on_warnings(self):
        """Test function does not raise for warnings only."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            ENVIRONMENT="development",
            DATABASE_POOL_SIZE=2,  # Warning only
        )
        # Should not raise
        validate_or_raise(settings)


class TestConfigurationSummary:
    """Tests for get_configuration_summary function."""

    def test_summary_excludes_secrets(self):
        """Test summary does not include sensitive values."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:secret@localhost/db",
            ENCRYPTION_KEY=SecretStr("supersecretkey123"),
            API_SECRET_KEY=SecretStr("anothersecret456"),
            ENVIRONMENT="development",
        )
        summary = get_configuration_summary(settings)

        # Should not contain actual secret values
        summary_str = str(summary)
        assert "supersecretkey123" not in summary_str
        assert "anothersecret456" not in summary_str
        assert "secret@" not in summary_str

    def test_summary_includes_relevant_fields(self):
        """Test summary includes expected fields."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            ENVIRONMENT="development",
            DEBUG=True,
        )
        summary = get_configuration_summary(settings)

        assert "environment" in summary
        assert "debug" in summary
        assert "api_port" in summary
        assert "encryption_configured" in summary
        assert "api_key_configured" in summary

    def test_summary_shows_configured_status(self):
        """Test summary correctly shows configuration status."""
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            ENCRYPTION_KEY=SecretStr("test"),
            API_SECRET_KEY=None,
            ENVIRONMENT="development",
        )
        summary = get_configuration_summary(settings)

        assert summary["encryption_configured"] is True
        assert summary["api_key_configured"] is False
