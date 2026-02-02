"""Secrets management module for secure credential handling.

This module provides:
- Abstract SecretsManager protocol for backend-agnostic secrets access
- VaultSecretsManager for HashiCorp Vault integration
- EnvironmentSecretsManager for development/testing without Vault
- CloudSecretsManager for AWS Secrets Manager / Azure Key Vault
- SecretCache for reducing backend calls
- Secret rotation support
- Audit logging for compliance

Example:
    from elile.secrets import get_secrets_manager, SecretPath

    # Get configured secrets manager
    manager = get_secrets_manager()

    # Retrieve secrets
    db_creds = await manager.get_secret(SecretPath.DATABASE)
    api_key = await manager.get_api_key("anthropic")

    # Rotate a secret
    await manager.rotate_secret(SecretPath.DATABASE, new_credentials)
"""

from elile.secrets.cache import SecretCache, SecretCacheConfig
from elile.secrets.config import SecretsConfig, create_secrets_config
from elile.secrets.environment import EnvironmentSecretsManager
from elile.secrets.manager import get_secrets_manager, initialize_secrets, shutdown_secrets
from elile.secrets.protocol import (
    SecretPath,
    SecretsManager,
    SecretValue,
)
from elile.secrets.rotation import (
    RotationConfig,
    RotationResult,
    RotationStatus,
    SecretRotator,
    create_secret_rotator,
)
from elile.secrets.types import (
    AIProviderSecrets,
    DatabaseCredentials,
    EncryptionKeys,
    ProviderApiKey,
    SecretMetadata,
    SecretType,
)
from elile.secrets.vault import VaultConfig, VaultSecretsManager

__all__ = [
    # Protocol
    "SecretsManager",
    "SecretPath",
    "SecretValue",
    # Types
    "SecretType",
    "SecretMetadata",
    "DatabaseCredentials",
    "ProviderApiKey",
    "AIProviderSecrets",
    "EncryptionKeys",
    # Configuration
    "SecretsConfig",
    "create_secrets_config",
    "VaultConfig",
    # Implementations
    "VaultSecretsManager",
    "EnvironmentSecretsManager",
    # Cache
    "SecretCache",
    "SecretCacheConfig",
    # Rotation
    "SecretRotator",
    "RotationConfig",
    "RotationResult",
    "RotationStatus",
    "create_secret_rotator",
    # Manager functions
    "get_secrets_manager",
    "initialize_secrets",
    "shutdown_secrets",
]
