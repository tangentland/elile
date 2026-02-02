"""Secrets management configuration.

This module provides configuration for the secrets management system,
including backend selection and environment-specific settings.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class SecretsBackend(str, Enum):
    """Supported secrets backends."""

    VAULT = "vault"
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    ENVIRONMENT = "environment"


@dataclass(frozen=True, slots=True)
class VaultConfig:
    """Configuration for HashiCorp Vault backend.

    Attributes:
        url: Vault server URL
        token: Vault token (optional if using other auth methods)
        namespace: Vault namespace (enterprise feature)
        mount_point: KV secrets engine mount point
        auth_method: Authentication method
        role_id: AppRole role ID
        secret_id: AppRole secret ID
        kubernetes_role: Kubernetes auth role
        kubernetes_mount: Kubernetes auth mount point
        tls_verify: Whether to verify TLS certificates
        ca_cert: Path to CA certificate
        client_cert: Path to client certificate
        client_key: Path to client key
        timeout: Connection timeout in seconds
        max_retries: Maximum number of retries
    """

    url: str = "https://vault.example.com:8200"
    token: str | None = None
    namespace: str | None = None
    mount_point: str = "secret"
    auth_method: Literal["token", "approle", "kubernetes", "aws", "gcp"] = "token"
    role_id: str | None = None
    secret_id: str | None = None
    kubernetes_role: str | None = None
    kubernetes_mount: str = "kubernetes"
    tls_verify: bool = True
    ca_cert: str | None = None
    client_cert: str | None = None
    client_key: str | None = None
    timeout: int = 30
    max_retries: int = 3


@dataclass(frozen=True, slots=True)
class AWSSecretsConfig:
    """Configuration for AWS Secrets Manager backend.

    Attributes:
        region: AWS region
        access_key_id: AWS access key ID (optional if using IAM roles)
        secret_access_key: AWS secret access key
        session_token: AWS session token (for temporary credentials)
        endpoint_url: Custom endpoint URL (for LocalStack, etc.)
        prefix: Prefix for secret names
    """

    region: str = "us-east-1"
    access_key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None
    endpoint_url: str | None = None
    prefix: str = "elile/"


@dataclass(frozen=True, slots=True)
class AzureKeyVaultConfig:
    """Configuration for Azure Key Vault backend.

    Attributes:
        vault_url: Azure Key Vault URL
        tenant_id: Azure tenant ID
        client_id: Azure client ID
        client_secret: Azure client secret
        use_managed_identity: Whether to use managed identity
    """

    vault_url: str = ""
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    use_managed_identity: bool = False


@dataclass(frozen=True, slots=True)
class GCPSecretManagerConfig:
    """Configuration for GCP Secret Manager backend.

    Attributes:
        project_id: GCP project ID
        credentials_file: Path to service account credentials JSON
        use_default_credentials: Whether to use default credentials
    """

    project_id: str = ""
    credentials_file: str | None = None
    use_default_credentials: bool = True


@dataclass(frozen=True, slots=True)
class EnvironmentSecretsConfig:
    """Configuration for environment-based secrets (development/testing).

    Attributes:
        prefix: Environment variable prefix
        env_file: Path to .env file
        allow_missing: Whether to allow missing secrets
    """

    prefix: str = "ELILE_SECRET_"
    env_file: str = ".env"
    allow_missing: bool = True


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Configuration for secrets caching.

    Attributes:
        enabled: Whether caching is enabled
        default_ttl_seconds: Default TTL for cached secrets
        max_entries: Maximum number of cached entries
        refresh_before_expiry_seconds: Refresh secrets this many seconds before expiry
    """

    enabled: bool = True
    default_ttl_seconds: int = 300  # 5 minutes
    max_entries: int = 1000
    refresh_before_expiry_seconds: int = 60


@dataclass(frozen=True, slots=True)
class AuditConfig:
    """Configuration for secrets access auditing.

    Attributes:
        enabled: Whether audit logging is enabled
        log_reads: Whether to log read operations
        log_writes: Whether to log write operations
        log_deletes: Whether to log delete operations
        include_actor: Whether to include actor information
        include_source_ip: Whether to include source IP
    """

    enabled: bool = True
    log_reads: bool = True
    log_writes: bool = True
    log_deletes: bool = True
    include_actor: bool = True
    include_source_ip: bool = False


@dataclass
class SecretsConfig:
    """Main configuration for secrets management.

    Attributes:
        backend: Which secrets backend to use
        vault: Vault-specific configuration
        aws: AWS Secrets Manager configuration
        azure: Azure Key Vault configuration
        gcp: GCP Secret Manager configuration
        environment: Environment secrets configuration
        cache: Caching configuration
        audit: Audit logging configuration
        environment_name: Current environment (development, staging, production)
        fallback_to_environment: Whether to fall back to environment variables
    """

    backend: SecretsBackend = SecretsBackend.ENVIRONMENT
    vault: VaultConfig = field(default_factory=VaultConfig)
    aws: AWSSecretsConfig = field(default_factory=AWSSecretsConfig)
    azure: AzureKeyVaultConfig = field(default_factory=AzureKeyVaultConfig)
    gcp: GCPSecretManagerConfig = field(default_factory=GCPSecretManagerConfig)
    environment: EnvironmentSecretsConfig = field(default_factory=EnvironmentSecretsConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    environment_name: Literal["development", "staging", "production", "test"] = "development"
    fallback_to_environment: bool = True


def create_secrets_config(
    environment: Literal["development", "staging", "production", "test"] = "development",
    *,
    vault_url: str | None = None,
    vault_token: str | None = None,
    aws_region: str | None = None,  # noqa: ARG001 - reserved for AWS backend
    azure_vault_url: str | None = None,  # noqa: ARG001 - reserved for Azure backend
    gcp_project: str | None = None,  # noqa: ARG001 - reserved for GCP backend
) -> SecretsConfig:
    """Create secrets configuration based on environment.

    Factory function that creates appropriate secrets configuration
    based on the deployment environment.

    Args:
        environment: Deployment environment
        vault_url: Override Vault URL
        vault_token: Override Vault token
        aws_region: Override AWS region
        azure_vault_url: Override Azure Key Vault URL
        gcp_project: Override GCP project ID

    Returns:
        SecretsConfig configured for the environment

    Example:
        # Development (uses environment variables)
        config = create_secrets_config("development")

        # Production with Vault
        config = create_secrets_config(
            "production",
            vault_url="https://vault.internal:8200",
        )
    """
    if environment == "test":
        # Test environment: always use environment-based secrets
        return SecretsConfig(
            backend=SecretsBackend.ENVIRONMENT,
            environment=EnvironmentSecretsConfig(allow_missing=True),
            cache=CacheConfig(enabled=False),
            audit=AuditConfig(enabled=False),
            environment_name=environment,
            fallback_to_environment=True,
        )

    if environment == "development":
        # Development: environment variables with caching
        return SecretsConfig(
            backend=SecretsBackend.ENVIRONMENT,
            environment=EnvironmentSecretsConfig(allow_missing=True),
            cache=CacheConfig(enabled=True, default_ttl_seconds=600),
            audit=AuditConfig(enabled=True, log_reads=False),
            environment_name=environment,
            fallback_to_environment=True,
        )

    if environment == "staging":
        # Staging: Vault with development-like settings
        vault_config = VaultConfig(
            url=vault_url or "https://vault.staging.internal:8200",
            token=vault_token,
            auth_method="kubernetes" if not vault_token else "token",
            tls_verify=True,
        )
        return SecretsConfig(
            backend=SecretsBackend.VAULT,
            vault=vault_config,
            cache=CacheConfig(enabled=True, default_ttl_seconds=300),
            audit=AuditConfig(enabled=True),
            environment_name=environment,
            fallback_to_environment=True,
        )

    # Production: full security
    vault_config = VaultConfig(
        url=vault_url or "https://vault.internal:8200",
        token=vault_token,
        auth_method="kubernetes" if not vault_token else "token",
        tls_verify=True,
        max_retries=5,
    )
    return SecretsConfig(
        backend=SecretsBackend.VAULT,
        vault=vault_config,
        cache=CacheConfig(
            enabled=True,
            default_ttl_seconds=300,
            refresh_before_expiry_seconds=60,
        ),
        audit=AuditConfig(enabled=True),
        environment_name=environment,
        fallback_to_environment=False,  # Production: no fallback
    )
