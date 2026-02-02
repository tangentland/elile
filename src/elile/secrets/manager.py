"""Secrets manager factory and global instance management.

This module provides factory functions for creating secrets managers
and manages the global secrets manager instance for the application.
"""

import asyncio
import logging
import os
from typing import Any

from elile.secrets.cache import SecretCache, SecretCacheConfig
from elile.secrets.config import (
    SecretsBackend,
    SecretsConfig,
    create_secrets_config,
)
from elile.secrets.environment import EnvironmentSecretsManager
from elile.secrets.protocol import (
    SecretPath,
    SecretsConnectionError,
    SecretsManager,
)

logger = logging.getLogger(__name__)

# Global secrets manager instance
_secrets_manager: SecretsManager | None = None
_initialized = False
_init_lock = asyncio.Lock()


async def initialize_secrets(
    config: SecretsConfig | None = None,
    *,
    environment: str | None = None,
) -> SecretsManager:
    """Initialize the global secrets manager.

    This function should be called once during application startup.
    It creates and configures the appropriate secrets manager based
    on the environment and configuration.

    Args:
        config: Optional explicit configuration
        environment: Environment name (uses ELILE_ENVIRONMENT env var if not provided)

    Returns:
        Initialized SecretsManager instance

    Raises:
        SecretsConnectionError: If connection to backend fails

    Example:
        # In application startup
        @app.on_event("startup")
        async def startup():
            await initialize_secrets()

        # Or with explicit config
        config = create_secrets_config("production", vault_url="...")
        await initialize_secrets(config)
    """
    global _secrets_manager, _initialized

    async with _init_lock:
        if _initialized and _secrets_manager is not None:
            logger.debug("Secrets manager already initialized")
            return _secrets_manager

        # Determine environment
        if environment is None:
            environment = os.environ.get("ELILE_ENVIRONMENT", "development")

        # Create config if not provided
        if config is None:
            vault_url = os.environ.get("VAULT_ADDR")
            vault_token = os.environ.get("VAULT_TOKEN")
            config = create_secrets_config(
                environment,  # type: ignore
                vault_url=vault_url,
                vault_token=vault_token,
            )

        logger.info(f"Initializing secrets manager with backend: {config.backend.value}")

        # Create cache
        cache = SecretCache(
            SecretCacheConfig(
                enabled=config.cache.enabled,
                default_ttl_seconds=config.cache.default_ttl_seconds,
                max_entries=config.cache.max_entries,
                refresh_before_expiry_seconds=config.cache.refresh_before_expiry_seconds,
            )
        )

        # Create appropriate backend
        if config.backend == SecretsBackend.VAULT:
            _secrets_manager = await _create_vault_manager(config, cache)
        elif config.backend == SecretsBackend.AWS:
            _secrets_manager = await _create_aws_manager(config, cache)
        elif config.backend == SecretsBackend.AZURE:
            _secrets_manager = await _create_azure_manager(config, cache)
        elif config.backend == SecretsBackend.GCP:
            _secrets_manager = await _create_gcp_manager(config, cache)
        else:
            # Default to environment
            _secrets_manager = EnvironmentSecretsManager(config.environment, cache)
            await cache.start()

        _initialized = True
        logger.info("Secrets manager initialized successfully")

        return _secrets_manager


async def _create_vault_manager(
    config: SecretsConfig,
    cache: SecretCache,
) -> SecretsManager:
    """Create and connect a Vault secrets manager."""
    from elile.secrets.vault import VaultSecretsManager

    manager = VaultSecretsManager(config.vault, cache)
    await manager.connect()
    return manager


async def _create_aws_manager(
    config: SecretsConfig,
    cache: SecretCache,
) -> SecretsManager:
    """Create AWS Secrets Manager backend.

    Note: AWS Secrets Manager support is planned for a future release.
    Currently falls back to environment secrets.
    """
    logger.warning("AWS Secrets Manager not yet implemented, using environment fallback")

    if config.fallback_to_environment:
        return EnvironmentSecretsManager(config.environment, cache)

    raise SecretsConnectionError(
        "AWS",
        Exception("AWS Secrets Manager not implemented"),
    )


async def _create_azure_manager(
    config: SecretsConfig,
    cache: SecretCache,
) -> SecretsManager:
    """Create Azure Key Vault backend.

    Note: Azure Key Vault support is planned for a future release.
    Currently falls back to environment secrets.
    """
    logger.warning("Azure Key Vault not yet implemented, using environment fallback")

    if config.fallback_to_environment:
        return EnvironmentSecretsManager(config.environment, cache)

    raise SecretsConnectionError(
        "Azure",
        Exception("Azure Key Vault not implemented"),
    )


async def _create_gcp_manager(
    config: SecretsConfig,
    cache: SecretCache,
) -> SecretsManager:
    """Create GCP Secret Manager backend.

    Note: GCP Secret Manager support is planned for a future release.
    Currently falls back to environment secrets.
    """
    logger.warning("GCP Secret Manager not yet implemented, using environment fallback")

    if config.fallback_to_environment:
        return EnvironmentSecretsManager(config.environment, cache)

    raise SecretsConnectionError(
        "GCP",
        Exception("GCP Secret Manager not implemented"),
    )


def get_secrets_manager() -> SecretsManager:
    """Get the global secrets manager instance.

    Returns:
        SecretsManager instance

    Raises:
        RuntimeError: If secrets manager not initialized

    Example:
        manager = get_secrets_manager()
        db_creds = await manager.get_database_credentials()
    """
    if _secrets_manager is None:
        raise RuntimeError("Secrets manager not initialized. Call initialize_secrets() first.")
    return _secrets_manager


async def shutdown_secrets() -> None:
    """Shutdown the global secrets manager.

    Should be called during application shutdown to close
    connections and cleanup resources.

    Example:
        @app.on_event("shutdown")
        async def shutdown():
            await shutdown_secrets()
    """
    global _secrets_manager, _initialized

    async with _init_lock:
        if _secrets_manager is not None:
            try:
                await _secrets_manager.close()
                logger.info("Secrets manager shut down")
            except Exception as e:
                logger.warning(f"Error shutting down secrets manager: {e}")
            finally:
                _secrets_manager = None
                _initialized = False


async def get_or_initialize_secrets(
    config: SecretsConfig | None = None,
) -> SecretsManager:
    """Get the secrets manager, initializing if needed.

    Convenience function that combines get_secrets_manager and
    initialize_secrets. Safe to call multiple times.

    Args:
        config: Optional configuration for initialization

    Returns:
        SecretsManager instance
    """
    global _secrets_manager

    if _secrets_manager is None:
        await initialize_secrets(config)

    return _secrets_manager  # type: ignore


# ----------------------------------------------------------------
# Convenience functions for common operations
# ----------------------------------------------------------------


async def get_secret(path: str | SecretPath) -> dict[str, Any]:
    """Get a secret value.

    Convenience function that gets the secrets manager and retrieves a secret.

    Args:
        path: Secret path

    Returns:
        Secret data dictionary
    """
    manager = get_secrets_manager()
    secret = await manager.get_secret(path)
    return secret.data


async def get_database_url(path: str | SecretPath = SecretPath.DATABASE) -> str:
    """Get database URL from secrets.

    Convenience function for getting database connection URL.

    Args:
        path: Path to database credentials

    Returns:
        Database connection URL
    """
    manager = get_secrets_manager()
    creds = await manager.get_database_credentials(path)
    return creds.to_url()


async def get_ai_api_key(provider: str) -> str:
    """Get AI provider API key.

    Convenience function for getting AI provider API keys.

    Args:
        provider: AI provider (anthropic, openai, google)

    Returns:
        API key string
    """
    manager = get_secrets_manager()
    secrets = await manager.get_ai_provider_secrets(provider)
    return secrets.api_key


async def get_provider_api_key(provider: str) -> str:
    """Get data provider API key.

    Convenience function for getting data provider API keys.

    Args:
        provider: Provider identifier (sterling, checkr, etc.)

    Returns:
        API key string
    """
    manager = get_secrets_manager()
    key = await manager.get_api_key(provider)
    return key.api_key
