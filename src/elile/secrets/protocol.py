"""Secrets manager protocol and abstract interface.

This module defines the abstract protocol that all secrets manager
implementations must follow.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from elile.secrets.types import (
    AIProviderSecrets,
    DatabaseCredentials,
    EncryptionKeys,
    ProviderApiKey,
    SecretMetadata,
    SecretType,
)


class SecretPath(str, Enum):
    """Standard paths for secrets in the vault.

    These paths follow a hierarchical structure:
    elile/{environment}/{category}/{name}
    """

    # Database credentials
    DATABASE = "elile/database/postgres"
    DATABASE_READ_REPLICA = "elile/database/postgres-readonly"
    REDIS = "elile/database/redis"

    # AI provider keys
    AI_ANTHROPIC = "elile/ai/anthropic"
    AI_OPENAI = "elile/ai/openai"
    AI_GOOGLE = "elile/ai/google"

    # Data provider keys
    PROVIDER_STERLING = "elile/providers/sterling"
    PROVIDER_CHECKR = "elile/providers/checkr"
    PROVIDER_WORLD_CHECK = "elile/providers/world_check"
    PROVIDER_HIRERIGHT = "elile/providers/hireright"
    PROVIDER_NCSC = "elile/providers/ncsc"
    PROVIDER_FINRA = "elile/providers/finra"

    # Encryption keys
    ENCRYPTION_PRIMARY = "elile/encryption/primary"
    ENCRYPTION_DATA = "elile/encryption/data"
    ENCRYPTION_PII = "elile/encryption/pii"

    # JWT signing
    JWT_SIGNING = "elile/auth/jwt"

    # Application secrets
    API_SECRET = "elile/app/api-secret"
    WEBHOOK_SECRET = "elile/app/webhook-secret"

    # HRIS credentials (template - actual path includes tenant_id)
    HRIS_WORKDAY = "elile/hris/workday"
    HRIS_SUCCESSFACTORS = "elile/hris/successfactors"
    HRIS_ORACLE = "elile/hris/oracle"
    HRIS_ADP = "elile/hris/adp"
    HRIS_BAMBOOHR = "elile/hris/bamboohr"


@dataclass(frozen=True, slots=True)
class SecretValue:
    """A retrieved secret value with metadata.

    Attributes:
        path: The path where the secret is stored
        data: The secret data (type depends on secret type)
        metadata: Metadata about the secret
        cached: Whether this value was retrieved from cache
        retrieved_at: When the value was retrieved
    """

    path: str
    data: dict[str, Any]
    metadata: SecretMetadata
    cached: bool = False
    retrieved_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SecretAccessLog:
    """Log entry for secret access.

    Attributes:
        path: Secret path that was accessed
        operation: Operation performed (get, set, delete, rotate)
        actor_id: ID of the actor accessing the secret
        tenant_id: Tenant ID if applicable
        timestamp: When the access occurred
        success: Whether the operation succeeded
        error_message: Error message if failed
        source_ip: Source IP address if available
    """

    path: str
    operation: str
    actor_id: str | None
    tenant_id: str | None
    timestamp: datetime
    success: bool
    error_message: str | None = None
    source_ip: str | None = None


@runtime_checkable
class SecretsManager(Protocol):
    """Protocol for secrets manager implementations.

    All secrets managers must implement this protocol to ensure
    consistent behavior across different backends (Vault, AWS, Azure, etc.).
    """

    async def get_secret(self, path: str | SecretPath) -> SecretValue:
        """Retrieve a secret from the secrets store.

        Args:
            path: Path to the secret (string or SecretPath enum)

        Returns:
            SecretValue containing the secret data and metadata

        Raises:
            SecretNotFoundError: If the secret does not exist
            SecretsAccessError: If access is denied or connection fails
        """
        ...

    async def set_secret(
        self,
        path: str | SecretPath,
        data: dict[str, Any],
        secret_type: SecretType = SecretType.GENERIC,
        metadata: dict[str, str] | None = None,
    ) -> SecretValue:
        """Store or update a secret.

        Args:
            path: Path to store the secret
            data: Secret data to store
            secret_type: Type of the secret
            metadata: Optional tags/metadata

        Returns:
            SecretValue with the stored secret

        Raises:
            SecretsAccessError: If write access is denied
        """
        ...

    async def delete_secret(self, path: str | SecretPath) -> bool:
        """Delete a secret.

        Args:
            path: Path to the secret to delete

        Returns:
            True if deleted, False if not found

        Raises:
            SecretsAccessError: If delete access is denied
        """
        ...

    async def list_secrets(self, prefix: str) -> list[str]:
        """List secret paths under a prefix.

        Args:
            prefix: Path prefix to list

        Returns:
            List of secret paths

        Raises:
            SecretsAccessError: If list access is denied
        """
        ...

    async def get_database_credentials(
        self, path: str | SecretPath = SecretPath.DATABASE
    ) -> DatabaseCredentials:
        """Get database credentials.

        Args:
            path: Path to the database secret

        Returns:
            DatabaseCredentials object

        Raises:
            SecretNotFoundError: If credentials not found
        """
        ...

    async def get_api_key(self, provider: str) -> ProviderApiKey:
        """Get API key for a data provider.

        Args:
            provider: Provider identifier (sterling, checkr, etc.)

        Returns:
            ProviderApiKey object

        Raises:
            SecretNotFoundError: If provider key not found
        """
        ...

    async def get_ai_provider_secrets(self, provider: str) -> AIProviderSecrets:
        """Get secrets for an AI provider.

        Args:
            provider: AI provider (anthropic, openai, google)

        Returns:
            AIProviderSecrets object

        Raises:
            SecretNotFoundError: If provider secrets not found
        """
        ...

    async def get_encryption_keys(
        self, path: str | SecretPath = SecretPath.ENCRYPTION_PRIMARY
    ) -> EncryptionKeys:
        """Get encryption keys.

        Args:
            path: Path to the encryption keys

        Returns:
            EncryptionKeys object

        Raises:
            SecretNotFoundError: If keys not found
        """
        ...

    async def rotate_secret(
        self,
        path: str | SecretPath,
        new_data: dict[str, Any],
        keep_previous: bool = True,
    ) -> SecretValue:
        """Rotate a secret to a new value.

        Args:
            path: Path to the secret
            new_data: New secret data
            keep_previous: Whether to preserve previous version

        Returns:
            SecretValue with the new secret

        Raises:
            SecretNotFoundError: If secret doesn't exist
            SecretsAccessError: If rotation fails
        """
        ...

    async def health_check(self) -> bool:
        """Check if the secrets backend is healthy.

        Returns:
            True if healthy, False otherwise
        """
        ...

    async def close(self) -> None:
        """Close connections and cleanup resources."""
        ...


class SecretsError(Exception):
    """Base exception for secrets-related errors."""

    pass


class SecretNotFoundError(SecretsError):
    """Raised when a secret is not found."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Secret not found: {path}")


class SecretsAccessError(SecretsError):
    """Raised when access to secrets is denied or fails."""

    def __init__(self, message: str, cause: Exception | None = None):
        self.cause = cause
        super().__init__(message)


class SecretValidationError(SecretsError):
    """Raised when secret data fails validation."""

    def __init__(self, path: str, message: str):
        self.path = path
        super().__init__(f"Invalid secret at {path}: {message}")


class SecretsConnectionError(SecretsError):
    """Raised when connection to secrets backend fails."""

    def __init__(self, backend: str, cause: Exception | None = None):
        self.backend = backend
        self.cause = cause
        super().__init__(f"Failed to connect to secrets backend: {backend}")
