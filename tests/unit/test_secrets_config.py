"""Tests for secrets configuration."""

import pytest

from elile.secrets.config import (
    AuditConfig,
    AWSSecretsConfig,
    AzureKeyVaultConfig,
    CacheConfig,
    EnvironmentSecretsConfig,
    GCPSecretManagerConfig,
    SecretsBackend,
    SecretsConfig,
    VaultConfig,
    create_secrets_config,
)


class TestSecretsBackend:
    """Tests for SecretsBackend enum."""

    def test_all_backends(self) -> None:
        """Test all backend values."""
        assert SecretsBackend.VAULT == "vault"
        assert SecretsBackend.AWS == "aws"
        assert SecretsBackend.AZURE == "azure"
        assert SecretsBackend.GCP == "gcp"
        assert SecretsBackend.ENVIRONMENT == "environment"


class TestVaultConfig:
    """Tests for VaultConfig."""

    def test_default_config(self) -> None:
        """Test default Vault configuration."""
        config = VaultConfig()

        assert config.url == "https://vault.example.com:8200"
        assert config.token is None
        assert config.namespace is None
        assert config.mount_point == "secret"
        assert config.auth_method == "token"
        assert config.tls_verify is True
        assert config.timeout == 30
        assert config.max_retries == 3

    def test_custom_config(self) -> None:
        """Test custom Vault configuration."""
        config = VaultConfig(
            url="https://vault.internal:8200",
            token="s.xxxxxxx",
            namespace="elile",
            auth_method="approle",
            role_id="role-123",
            secret_id="secret-456",
        )

        assert config.url == "https://vault.internal:8200"
        assert config.token == "s.xxxxxxx"
        assert config.namespace == "elile"
        assert config.auth_method == "approle"
        assert config.role_id == "role-123"

    def test_kubernetes_auth(self) -> None:
        """Test Kubernetes auth configuration."""
        config = VaultConfig(
            auth_method="kubernetes",
            kubernetes_role="elile-app",
            kubernetes_mount="kubernetes",
        )

        assert config.auth_method == "kubernetes"
        assert config.kubernetes_role == "elile-app"


class TestAWSSecretsConfig:
    """Tests for AWSSecretsConfig."""

    def test_default_config(self) -> None:
        """Test default AWS configuration."""
        config = AWSSecretsConfig()

        assert config.region == "us-east-1"
        assert config.access_key_id is None
        assert config.prefix == "elile/"

    def test_custom_config(self) -> None:
        """Test custom AWS configuration."""
        config = AWSSecretsConfig(
            region="eu-west-1",
            access_key_id="AKIA...",
            secret_access_key="secret",
            prefix="myapp/",
        )

        assert config.region == "eu-west-1"
        assert config.access_key_id == "AKIA..."


class TestAzureKeyVaultConfig:
    """Tests for AzureKeyVaultConfig."""

    def test_default_config(self) -> None:
        """Test default Azure configuration."""
        config = AzureKeyVaultConfig()

        assert config.vault_url == ""
        assert config.use_managed_identity is False

    def test_managed_identity(self) -> None:
        """Test managed identity configuration."""
        config = AzureKeyVaultConfig(
            vault_url="https://myvault.vault.azure.net",
            use_managed_identity=True,
        )

        assert config.use_managed_identity is True


class TestGCPSecretManagerConfig:
    """Tests for GCPSecretManagerConfig."""

    def test_default_config(self) -> None:
        """Test default GCP configuration."""
        config = GCPSecretManagerConfig()

        assert config.project_id == ""
        assert config.use_default_credentials is True

    def test_with_credentials_file(self) -> None:
        """Test configuration with credentials file."""
        config = GCPSecretManagerConfig(
            project_id="my-project",
            credentials_file="/path/to/creds.json",
            use_default_credentials=False,
        )

        assert config.credentials_file == "/path/to/creds.json"
        assert config.use_default_credentials is False


class TestEnvironmentSecretsConfig:
    """Tests for EnvironmentSecretsConfig."""

    def test_default_config(self) -> None:
        """Test default environment configuration."""
        config = EnvironmentSecretsConfig()

        assert config.prefix == "ELILE_SECRET_"
        assert config.env_file == ".env"
        assert config.allow_missing is True

    def test_strict_mode(self) -> None:
        """Test strict mode configuration."""
        config = EnvironmentSecretsConfig(allow_missing=False)
        assert config.allow_missing is False


class TestCacheConfig:
    """Tests for CacheConfig."""

    def test_default_config(self) -> None:
        """Test default cache configuration."""
        config = CacheConfig()

        assert config.enabled is True
        assert config.default_ttl_seconds == 300
        assert config.max_entries == 1000
        assert config.refresh_before_expiry_seconds == 60

    def test_disabled_cache(self) -> None:
        """Test disabled cache configuration."""
        config = CacheConfig(enabled=False)
        assert config.enabled is False


class TestAuditConfig:
    """Tests for AuditConfig."""

    def test_default_config(self) -> None:
        """Test default audit configuration."""
        config = AuditConfig()

        assert config.enabled is True
        assert config.log_reads is True
        assert config.log_writes is True
        assert config.log_deletes is True
        assert config.include_actor is True
        assert config.include_source_ip is False

    def test_minimal_logging(self) -> None:
        """Test minimal audit logging configuration."""
        config = AuditConfig(
            log_reads=False,
            log_writes=True,
            log_deletes=True,
        )

        assert config.log_reads is False


class TestSecretsConfig:
    """Tests for SecretsConfig."""

    def test_default_config(self) -> None:
        """Test default secrets configuration."""
        config = SecretsConfig()

        assert config.backend == SecretsBackend.ENVIRONMENT
        assert config.environment_name == "development"
        assert config.fallback_to_environment is True

    def test_vault_backend(self) -> None:
        """Test Vault backend configuration."""
        config = SecretsConfig(
            backend=SecretsBackend.VAULT,
            vault=VaultConfig(url="https://vault.test:8200"),
        )

        assert config.backend == SecretsBackend.VAULT
        assert config.vault.url == "https://vault.test:8200"


class TestCreateSecretsConfig:
    """Tests for create_secrets_config factory."""

    def test_test_environment(self) -> None:
        """Test configuration for test environment."""
        config = create_secrets_config("test")

        assert config.backend == SecretsBackend.ENVIRONMENT
        assert config.cache.enabled is False
        assert config.audit.enabled is False
        assert config.environment.allow_missing is True

    def test_development_environment(self) -> None:
        """Test configuration for development environment."""
        config = create_secrets_config("development")

        assert config.backend == SecretsBackend.ENVIRONMENT
        assert config.cache.enabled is True
        assert config.cache.default_ttl_seconds == 600
        assert config.audit.log_reads is False  # Don't log reads in dev

    def test_staging_environment(self) -> None:
        """Test configuration for staging environment."""
        config = create_secrets_config("staging")

        assert config.backend == SecretsBackend.VAULT
        assert config.cache.enabled is True
        assert config.fallback_to_environment is True

    def test_staging_with_custom_vault(self) -> None:
        """Test staging with custom Vault URL."""
        config = create_secrets_config(
            "staging",
            vault_url="https://custom-vault:8200",
            vault_token="s.token",
        )

        assert config.vault.url == "https://custom-vault:8200"
        assert config.vault.token == "s.token"
        assert config.vault.auth_method == "token"

    def test_staging_without_token(self) -> None:
        """Test staging defaults to Kubernetes auth without token."""
        config = create_secrets_config("staging", vault_url="https://vault:8200")

        assert config.vault.auth_method == "kubernetes"

    def test_production_environment(self) -> None:
        """Test configuration for production environment."""
        config = create_secrets_config("production")

        assert config.backend == SecretsBackend.VAULT
        assert config.cache.enabled is True
        assert config.audit.enabled is True
        assert config.fallback_to_environment is False  # No fallback in prod
        assert config.vault.max_retries == 5

    def test_production_with_vault_url(self) -> None:
        """Test production with custom Vault URL."""
        config = create_secrets_config(
            "production",
            vault_url="https://prod-vault.internal:8200",
        )

        assert config.vault.url == "https://prod-vault.internal:8200"
        assert config.vault.tls_verify is True
