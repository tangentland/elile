"""Tests for secrets types and data structures."""

from datetime import datetime

import pytest

from elile.secrets.types import (
    AIProviderSecrets,
    DatabaseCredentials,
    EncryptionKeys,
    HRISCredentials,
    JWTSigningKeys,
    ProviderApiKey,
    RedisCredentials,
    SecretMetadata,
    SecretType,
    WebhookSecret,
)
from uuid import uuid4


class TestSecretMetadata:
    """Tests for SecretMetadata."""

    def test_create_metadata(self) -> None:
        """Test creating secret metadata."""
        now = datetime.utcnow()
        metadata = SecretMetadata(
            secret_type=SecretType.DATABASE,
            created_at=now,
            updated_at=now,
            version=1,
        )

        assert metadata.secret_type == SecretType.DATABASE
        assert metadata.created_at == now
        assert metadata.version == 1
        assert metadata.expires_at is None
        assert metadata.rotation_enabled is False

    def test_metadata_with_expiration(self) -> None:
        """Test metadata with expiration."""
        now = datetime.utcnow()
        metadata = SecretMetadata(
            secret_type=SecretType.API_KEY,
            created_at=now,
            updated_at=now,
            expires_at=datetime(2025, 12, 31),
            rotation_enabled=True,
        )

        assert metadata.expires_at is not None
        assert metadata.rotation_enabled is True


class TestDatabaseCredentials:
    """Tests for DatabaseCredentials."""

    def test_create_credentials(self) -> None:
        """Test creating database credentials."""
        creds = DatabaseCredentials(
            host="localhost",
            port=5432,
            database="elile",
            username="postgres",
            password="secret",
        )

        assert creds.host == "localhost"
        assert creds.port == 5432
        assert creds.database == "elile"
        assert creds.username == "postgres"
        assert creds.password == "secret"
        assert creds.ssl_mode == "prefer"

    def test_to_url_basic(self) -> None:
        """Test converting credentials to URL."""
        creds = DatabaseCredentials(
            host="localhost",
            port=5432,
            database="elile",
            username="postgres",
            password="secret",
        )

        url = creds.to_url()
        assert url == "postgresql+asyncpg://postgres:secret@localhost:5432/elile"

    def test_to_url_with_special_characters(self) -> None:
        """Test URL encoding of special characters in password."""
        creds = DatabaseCredentials(
            host="localhost",
            port=5432,
            database="elile",
            username="user",
            password="p@ss:word/test",
        )

        url = creds.to_url()
        # Password should be URL-encoded
        assert "p%40ss%3Aword%2Ftest" in url

    def test_to_url_with_ssl(self) -> None:
        """Test URL with SSL mode."""
        creds = DatabaseCredentials(
            host="localhost",
            port=5432,
            database="elile",
            username="postgres",
            password="secret",
            ssl_mode="require",
        )

        url = creds.to_url()
        assert "?sslmode=require" in url

    def test_to_url_custom_driver(self) -> None:
        """Test URL with custom driver."""
        creds = DatabaseCredentials(
            host="localhost",
            port=5432,
            database="elile",
            username="postgres",
            password="secret",
        )

        url = creds.to_url(driver="postgresql+psycopg2")
        assert url.startswith("postgresql+psycopg2://")


class TestProviderApiKey:
    """Tests for ProviderApiKey."""

    def test_create_api_key(self) -> None:
        """Test creating provider API key."""
        key = ProviderApiKey(
            provider_id="sterling",
            api_key="sk_test_123",
        )

        assert key.provider_id == "sterling"
        assert key.api_key == "sk_test_123"
        assert key.environment == "production"

    def test_api_key_with_secret(self) -> None:
        """Test API key with secret."""
        key = ProviderApiKey(
            provider_id="checkr",
            api_key="pk_123",
            api_secret="sk_secret",
            base_url="https://api.checkr.com",
            rate_limit_rpm=100,
        )

        assert key.api_secret == "sk_secret"
        assert key.base_url == "https://api.checkr.com"
        assert key.rate_limit_rpm == 100


class TestAIProviderSecrets:
    """Tests for AIProviderSecrets."""

    def test_create_anthropic_secrets(self) -> None:
        """Test creating Anthropic secrets."""
        secrets = AIProviderSecrets(
            provider="anthropic",
            api_key="sk-ant-123",
        )

        assert secrets.provider == "anthropic"
        assert secrets.api_key == "sk-ant-123"

    def test_openai_secrets_with_org(self) -> None:
        """Test OpenAI secrets with organization."""
        secrets = AIProviderSecrets(
            provider="openai",
            api_key="sk-123",
            organization_id="org-456",
        )

        assert secrets.organization_id == "org-456"

    def test_google_secrets_with_project(self) -> None:
        """Test Google secrets with project."""
        secrets = AIProviderSecrets(
            provider="google",
            api_key="AIza123",
            project_id="my-project",
        )

        assert secrets.project_id == "my-project"


class TestEncryptionKeys:
    """Tests for EncryptionKeys."""

    def test_create_encryption_keys(self) -> None:
        """Test creating encryption keys."""
        keys = EncryptionKeys(
            primary_key="base64encodedkey==",
            key_id="key-001",
        )

        assert keys.primary_key == "base64encodedkey=="
        assert keys.key_id == "key-001"
        assert keys.algorithm == "AES-256-GCM"
        assert keys.previous_keys == []

    def test_keys_with_previous(self) -> None:
        """Test keys with previous versions."""
        keys = EncryptionKeys(
            primary_key="newkey==",
            key_id="key-002",
            previous_keys=["oldkey1==", "oldkey2=="],
        )

        assert len(keys.previous_keys) == 2


class TestRedisCredentials:
    """Tests for RedisCredentials."""

    def test_create_redis_credentials(self) -> None:
        """Test creating Redis credentials."""
        creds = RedisCredentials(
            host="localhost",
            port=6379,
        )

        assert creds.host == "localhost"
        assert creds.port == 6379
        assert creds.database == 0

    def test_to_url_no_password(self) -> None:
        """Test Redis URL without password."""
        creds = RedisCredentials(host="localhost", port=6379)
        url = creds.to_url()
        assert url == "redis://localhost:6379/0"

    def test_to_url_with_password(self) -> None:
        """Test Redis URL with password."""
        creds = RedisCredentials(
            host="localhost",
            port=6379,
            password="secret",
            database=1,
        )
        url = creds.to_url()
        assert url == "redis://:secret@localhost:6379/1"

    def test_to_url_with_ssl(self) -> None:
        """Test Redis URL with SSL."""
        creds = RedisCredentials(
            host="redis.example.com",
            port=6380,
            password="secret",
            ssl=True,
        )
        url = creds.to_url()
        assert url.startswith("rediss://")


class TestHRISCredentials:
    """Tests for HRISCredentials."""

    def test_create_hris_credentials(self) -> None:
        """Test creating HRIS credentials."""
        tenant_id = uuid4()
        creds = HRISCredentials(
            platform="workday",
            tenant_id=tenant_id,
            client_id="client_123",
            client_secret="secret_456",
            token_url="https://workday.com/oauth/token",
            api_base_url="https://api.workday.com",
            scopes=["read", "write"],
        )

        assert creds.platform == "workday"
        assert creds.tenant_id == tenant_id
        assert creds.client_id == "client_123"
        assert len(creds.scopes) == 2


class TestJWTSigningKeys:
    """Tests for JWTSigningKeys."""

    def test_create_jwt_keys_symmetric(self) -> None:
        """Test creating JWT keys with symmetric algorithm."""
        keys = JWTSigningKeys(
            algorithm="HS256",
            key_id="jwt-001",
            issuer="elile",
            secret="my_secret_key",
        )

        assert keys.algorithm == "HS256"
        assert keys.secret == "my_secret_key"

    def test_create_jwt_keys_asymmetric(self) -> None:
        """Test creating JWT keys with asymmetric algorithm."""
        keys = JWTSigningKeys(
            algorithm="RS256",
            key_id="jwt-002",
            issuer="elile",
            private_key="-----BEGIN PRIVATE KEY-----...",
            public_key="-----BEGIN PUBLIC KEY-----...",
        )

        assert keys.algorithm == "RS256"
        assert keys.private_key is not None
        assert keys.public_key is not None


class TestWebhookSecret:
    """Tests for WebhookSecret."""

    def test_create_webhook_secret(self) -> None:
        """Test creating webhook secret."""
        secret = WebhookSecret(secret="whsec_123")

        assert secret.secret == "whsec_123"
        assert secret.algorithm == "sha256"
        assert secret.header_name == "X-Signature"
        assert secret.encoding == "hex"

    def test_webhook_secret_custom(self) -> None:
        """Test webhook secret with custom settings."""
        secret = WebhookSecret(
            secret="whsec_456",
            algorithm="sha512",
            header_name="X-Hub-Signature-256",
            encoding="base64",
        )

        assert secret.algorithm == "sha512"
        assert secret.header_name == "X-Hub-Signature-256"


class TestSecretType:
    """Tests for SecretType enum."""

    def test_all_secret_types(self) -> None:
        """Test all secret types exist."""
        assert SecretType.DATABASE == "database"
        assert SecretType.API_KEY == "api_key"
        assert SecretType.ENCRYPTION_KEY == "encryption_key"
        assert SecretType.AI_PROVIDER == "ai_provider"
        assert SecretType.DATA_PROVIDER == "data_provider"
        assert SecretType.HRIS_CREDENTIAL == "hris_credential"
        assert SecretType.WEBHOOK_SECRET == "webhook_secret"
        assert SecretType.JWT_SIGNING == "jwt_signing"
        assert SecretType.REDIS == "redis"
        assert SecretType.GENERIC == "generic"
