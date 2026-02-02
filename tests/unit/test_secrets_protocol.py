"""Tests for secrets protocol and exceptions."""

from datetime import datetime

import pytest

from elile.secrets.protocol import (
    SecretAccessLog,
    SecretNotFoundError,
    SecretPath,
    SecretValidationError,
    SecretValue,
    SecretsAccessError,
    SecretsConnectionError,
    SecretsError,
)
from elile.secrets.types import SecretMetadata, SecretType


class TestSecretPath:
    """Tests for SecretPath enum."""

    def test_database_paths(self) -> None:
        """Test database secret paths."""
        assert SecretPath.DATABASE.value == "elile/database/postgres"
        assert SecretPath.DATABASE_READ_REPLICA.value == "elile/database/postgres-readonly"
        assert SecretPath.REDIS.value == "elile/database/redis"

    def test_ai_provider_paths(self) -> None:
        """Test AI provider secret paths."""
        assert SecretPath.AI_ANTHROPIC.value == "elile/ai/anthropic"
        assert SecretPath.AI_OPENAI.value == "elile/ai/openai"
        assert SecretPath.AI_GOOGLE.value == "elile/ai/google"

    def test_data_provider_paths(self) -> None:
        """Test data provider secret paths."""
        assert SecretPath.PROVIDER_STERLING.value == "elile/providers/sterling"
        assert SecretPath.PROVIDER_CHECKR.value == "elile/providers/checkr"
        assert SecretPath.PROVIDER_WORLD_CHECK.value == "elile/providers/world_check"

    def test_encryption_paths(self) -> None:
        """Test encryption key paths."""
        assert SecretPath.ENCRYPTION_PRIMARY.value == "elile/encryption/primary"
        assert SecretPath.ENCRYPTION_DATA.value == "elile/encryption/data"
        assert SecretPath.ENCRYPTION_PII.value == "elile/encryption/pii"

    def test_auth_paths(self) -> None:
        """Test authentication paths."""
        assert SecretPath.JWT_SIGNING.value == "elile/auth/jwt"
        assert SecretPath.API_SECRET.value == "elile/app/api-secret"
        assert SecretPath.WEBHOOK_SECRET.value == "elile/app/webhook-secret"

    def test_hris_paths(self) -> None:
        """Test HRIS credential paths."""
        assert SecretPath.HRIS_WORKDAY.value == "elile/hris/workday"
        assert SecretPath.HRIS_SUCCESSFACTORS.value == "elile/hris/successfactors"


class TestSecretValue:
    """Tests for SecretValue dataclass."""

    def test_create_secret_value(self) -> None:
        """Test creating a secret value."""
        now = datetime.utcnow()
        metadata = SecretMetadata(
            secret_type=SecretType.API_KEY,
            created_at=now,
            updated_at=now,
            version=1,
        )

        value = SecretValue(
            path="elile/test/secret",
            data={"key": "value"},
            metadata=metadata,
        )

        assert value.path == "elile/test/secret"
        assert value.data == {"key": "value"}
        assert value.metadata.secret_type == SecretType.API_KEY
        assert value.cached is False

    def test_cached_secret_value(self) -> None:
        """Test cached secret value."""
        now = datetime.utcnow()
        metadata = SecretMetadata(
            secret_type=SecretType.GENERIC,
            created_at=now,
            updated_at=now,
        )

        value = SecretValue(
            path="elile/test/cached",
            data={"cached": True},
            metadata=metadata,
            cached=True,
        )

        assert value.cached is True


class TestSecretAccessLog:
    """Tests for SecretAccessLog dataclass."""

    def test_create_access_log(self) -> None:
        """Test creating an access log entry."""
        log = SecretAccessLog(
            path="elile/test/secret",
            operation="get",
            actor_id="user-123",
            tenant_id="tenant-456",
            timestamp=datetime.utcnow(),
            success=True,
        )

        assert log.path == "elile/test/secret"
        assert log.operation == "get"
        assert log.actor_id == "user-123"
        assert log.success is True
        assert log.error_message is None

    def test_access_log_with_error(self) -> None:
        """Test access log with error."""
        log = SecretAccessLog(
            path="elile/test/secret",
            operation="get",
            actor_id=None,
            tenant_id=None,
            timestamp=datetime.utcnow(),
            success=False,
            error_message="Access denied",
        )

        assert log.success is False
        assert log.error_message == "Access denied"


class TestSecretsError:
    """Tests for secrets exception classes."""

    def test_secrets_error_base(self) -> None:
        """Test base SecretsError."""
        error = SecretsError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert isinstance(error, Exception)

    def test_secret_not_found_error(self) -> None:
        """Test SecretNotFoundError."""
        error = SecretNotFoundError("elile/missing/secret")

        assert error.path == "elile/missing/secret"
        assert "elile/missing/secret" in str(error)
        assert isinstance(error, SecretsError)

    def test_secrets_access_error(self) -> None:
        """Test SecretsAccessError."""
        cause = PermissionError("Access denied")
        error = SecretsAccessError("Failed to read secret", cause)

        assert error.cause == cause
        assert "Failed to read secret" in str(error)
        assert isinstance(error, SecretsError)

    def test_secrets_access_error_without_cause(self) -> None:
        """Test SecretsAccessError without cause."""
        error = SecretsAccessError("Generic access error")

        assert error.cause is None
        assert "Generic access error" in str(error)

    def test_secret_validation_error(self) -> None:
        """Test SecretValidationError."""
        error = SecretValidationError(
            "elile/test/invalid",
            "Missing required field: api_key",
        )

        assert error.path == "elile/test/invalid"
        assert "elile/test/invalid" in str(error)
        assert "Missing required field" in str(error)
        assert isinstance(error, SecretsError)

    def test_secrets_connection_error(self) -> None:
        """Test SecretsConnectionError."""
        cause = ConnectionRefusedError("Connection refused")
        error = SecretsConnectionError("Vault", cause)

        assert error.backend == "Vault"
        assert error.cause == cause
        assert "Vault" in str(error)
        assert isinstance(error, SecretsError)

    def test_secrets_connection_error_without_cause(self) -> None:
        """Test SecretsConnectionError without cause."""
        error = SecretsConnectionError("AWS")

        assert error.backend == "AWS"
        assert error.cause is None


class TestExceptionHierarchy:
    """Tests for exception hierarchy."""

    def test_all_errors_inherit_from_base(self) -> None:
        """Test all errors inherit from SecretsError."""
        errors = [
            SecretNotFoundError("path"),
            SecretsAccessError("message"),
            SecretValidationError("path", "message"),
            SecretsConnectionError("backend"),
        ]

        for error in errors:
            assert isinstance(error, SecretsError)
            assert isinstance(error, Exception)

    def test_exceptions_are_catchable(self) -> None:
        """Test that exceptions can be caught by base class."""
        try:
            raise SecretNotFoundError("elile/test/missing")
        except SecretsError as e:
            assert "missing" in str(e)

        try:
            raise SecretsConnectionError("Vault")
        except SecretsError as e:
            assert "Vault" in str(e)
