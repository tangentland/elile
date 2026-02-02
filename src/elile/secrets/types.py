"""Secret types and data structures.

This module defines the typed data structures for different secret types
used throughout the application.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class SecretType(str, Enum):
    """Types of secrets stored in the secrets manager."""

    DATABASE = "database"
    API_KEY = "api_key"
    ENCRYPTION_KEY = "encryption_key"
    AI_PROVIDER = "ai_provider"
    DATA_PROVIDER = "data_provider"
    HRIS_CREDENTIAL = "hris_credential"
    WEBHOOK_SECRET = "webhook_secret"
    JWT_SIGNING = "jwt_signing"
    REDIS = "redis"
    GENERIC = "generic"


@dataclass(frozen=True, slots=True)
class SecretMetadata:
    """Metadata about a secret.

    Attributes:
        secret_type: Type of the secret
        created_at: When the secret was created
        updated_at: When the secret was last updated
        version: Version number of the secret
        expires_at: Optional expiration time
        rotation_enabled: Whether automatic rotation is enabled
        last_rotated_at: When the secret was last rotated
        accessed_count: Number of times the secret has been accessed
        tags: Optional tags for categorization
    """

    secret_type: SecretType
    created_at: datetime
    updated_at: datetime
    version: int = 1
    expires_at: datetime | None = None
    rotation_enabled: bool = False
    last_rotated_at: datetime | None = None
    accessed_count: int = 0
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DatabaseCredentials:
    """Database connection credentials.

    Attributes:
        host: Database host
        port: Database port
        database: Database name
        username: Database username
        password: Database password
        ssl_mode: SSL connection mode
        ssl_ca: Optional SSL CA certificate
        ssl_cert: Optional SSL client certificate
        ssl_key: Optional SSL client key
    """

    host: str
    port: int
    database: str
    username: str
    password: str
    ssl_mode: str = "prefer"
    ssl_ca: str | None = None
    ssl_cert: str | None = None
    ssl_key: str | None = None

    def to_url(self, driver: str = "postgresql+asyncpg") -> str:
        """Convert credentials to database URL.

        Args:
            driver: Database driver (default: postgresql+asyncpg)

        Returns:
            Database connection URL
        """
        from urllib.parse import quote_plus

        # URL-encode password in case it contains special characters
        encoded_password = quote_plus(self.password)
        url = (
            f"{driver}://{self.username}:{encoded_password}@{self.host}:{self.port}/{self.database}"
        )

        # Add SSL mode if not default
        if self.ssl_mode and self.ssl_mode != "prefer":
            url += f"?sslmode={self.ssl_mode}"

        return url


@dataclass(frozen=True, slots=True)
class ProviderApiKey:
    """API key for a data provider.

    Attributes:
        provider_id: Unique identifier for the provider
        api_key: The API key
        api_secret: Optional API secret (for OAuth-style APIs)
        base_url: Optional base URL override
        environment: Environment (production, sandbox, etc.)
        rate_limit_rpm: Requests per minute limit
        metadata: Additional provider-specific metadata
    """

    provider_id: str
    api_key: str
    api_secret: str | None = None
    base_url: str | None = None
    environment: str = "production"
    rate_limit_rpm: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIProviderSecrets:
    """Secrets for AI model providers.

    Attributes:
        provider: Provider name (anthropic, openai, google)
        api_key: Primary API key
        organization_id: Optional organization ID (OpenAI)
        project_id: Optional project ID (Google)
        base_url: Optional base URL override
        model_overrides: Optional model name overrides
    """

    provider: str
    api_key: str
    organization_id: str | None = None
    project_id: str | None = None
    base_url: str | None = None
    model_overrides: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EncryptionKeys:
    """Encryption keys for data protection.

    Attributes:
        primary_key: Current primary encryption key (base64 encoded)
        previous_keys: Previous keys for decryption of old data
        key_id: Identifier for the current key
        algorithm: Encryption algorithm (default: AES-256-GCM)
        created_at: When the current key was created
    """

    primary_key: str
    key_id: str
    algorithm: str = "AES-256-GCM"
    created_at: datetime = field(default_factory=datetime.utcnow)
    previous_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class HRISCredentials:
    """Credentials for HRIS platform integration.

    Attributes:
        platform: HRIS platform (workday, successfactors, etc.)
        tenant_id: Tenant ID this credential belongs to
        client_id: OAuth client ID
        client_secret: OAuth client secret
        token_url: OAuth token endpoint
        api_base_url: HRIS API base URL
        scopes: OAuth scopes
        webhook_secret: Webhook validation secret
    """

    platform: str
    tenant_id: UUID
    client_id: str
    client_secret: str
    token_url: str
    api_base_url: str
    scopes: list[str] = field(default_factory=list)
    webhook_secret: str | None = None


@dataclass(frozen=True, slots=True)
class RedisCredentials:
    """Redis connection credentials.

    Attributes:
        host: Redis host
        port: Redis port
        password: Redis password
        database: Redis database number
        ssl: Whether to use SSL
        cluster_mode: Whether cluster mode is enabled
    """

    host: str
    port: int = 6379
    password: str | None = None
    database: int = 0
    ssl: bool = False
    cluster_mode: bool = False

    def to_url(self) -> str:
        """Convert credentials to Redis URL.

        Returns:
            Redis connection URL
        """
        scheme = "rediss" if self.ssl else "redis"
        if self.password:
            from urllib.parse import quote_plus

            encoded_password = quote_plus(self.password)
            return f"{scheme}://:{encoded_password}@{self.host}:{self.port}/{self.database}"
        return f"{scheme}://{self.host}:{self.port}/{self.database}"


@dataclass(frozen=True, slots=True)
class JWTSigningKeys:
    """Keys for JWT token signing.

    Attributes:
        algorithm: Signing algorithm (RS256, HS256, etc.)
        private_key: Private key for signing (PEM format for RSA)
        public_key: Public key for verification (PEM format for RSA)
        secret: Shared secret (for HS256)
        key_id: Key identifier for key rotation
        issuer: JWT issuer claim
    """

    algorithm: str
    key_id: str
    issuer: str
    private_key: str | None = None
    public_key: str | None = None
    secret: str | None = None


@dataclass(frozen=True, slots=True)
class WebhookSecret:
    """Secret for webhook signature validation.

    Attributes:
        secret: The webhook secret
        algorithm: Hashing algorithm (sha256, sha512)
        header_name: Name of the signature header
        encoding: Signature encoding (hex, base64)
    """

    secret: str
    algorithm: str = "sha256"
    header_name: str = "X-Signature"
    encoding: str = "hex"
