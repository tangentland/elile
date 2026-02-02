"""Environment-based secrets manager for development and testing.

This implementation reads secrets from environment variables,
suitable for development environments where a secrets backend
is not available.
"""

import contextlib
import json
import logging
import os
from typing import Any

from elile.secrets.cache import SecretCache, SecretCacheConfig, create_secret_from_data
from elile.secrets.config import EnvironmentSecretsConfig
from elile.secrets.protocol import (
    SecretNotFoundError,
    SecretPath,
    SecretValue,
)
from elile.secrets.types import (
    AIProviderSecrets,
    DatabaseCredentials,
    EncryptionKeys,
    ProviderApiKey,
    SecretType,
)

logger = logging.getLogger(__name__)


class EnvironmentSecretsManager:
    """Secrets manager that reads from environment variables.

    This implementation is suitable for development and testing
    environments where a full secrets backend is not available.

    Environment variable naming convention:
    - {prefix}{PATH_WITH_UNDERSCORES}
    - e.g., ELILE_SECRET_DATABASE_POSTGRES for elile/database/postgres

    For complex secrets, use JSON format:
    - ELILE_SECRET_DATABASE_POSTGRES='{"host": "localhost", "port": 5432, ...}'

    Example:
        manager = EnvironmentSecretsManager()
        db_creds = await manager.get_database_credentials()
    """

    def __init__(
        self,
        config: EnvironmentSecretsConfig | None = None,
        cache: SecretCache | None = None,
    ):
        """Initialize the environment secrets manager.

        Args:
            config: Configuration for environment secrets
            cache: Optional cache instance
        """
        self.config = config or EnvironmentSecretsConfig()
        self._cache = cache or SecretCache(SecretCacheConfig(enabled=True))
        self._secrets: dict[str, dict[str, Any]] = {}
        self._load_from_env()

    def _path_to_env_var(self, path: str) -> str:
        """Convert a secret path to environment variable name.

        Args:
            path: Secret path (e.g., "elile/database/postgres")

        Returns:
            Environment variable name (e.g., "ELILE_SECRET_DATABASE_POSTGRES")
        """
        # Remove leading "elile/" if present
        if path.startswith("elile/"):
            path = path[6:]

        # Convert slashes and dashes to underscores, uppercase
        env_name = path.replace("/", "_").replace("-", "_").upper()
        return f"{self.config.prefix}{env_name}"

    def _load_from_env(self) -> None:
        """Load secrets from environment variables."""
        prefix = self.config.prefix

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue

            # Convert env var name back to path
            path_part = key[len(prefix) :].lower().replace("_", "/")
            path = f"elile/{path_part}"

            # Try to parse as JSON, fall back to string
            try:
                data = json.loads(value)
                if not isinstance(data, dict):
                    data = {"value": data}
            except json.JSONDecodeError:
                data = {"value": value}

            self._secrets[path] = data
            logger.debug(f"Loaded secret from environment: {path}")

        # Load common secrets with standard env var names
        self._load_standard_secrets()

    def _load_standard_secrets(self) -> None:
        """Load secrets from standard environment variable names."""
        standard_mappings: dict[str, dict[str, Any]] = {
            "elile/database/postgres": {
                "env_vars": {
                    "host": "DATABASE_HOST",
                    "port": "DATABASE_PORT",
                    "database": "DATABASE_NAME",
                    "username": "DATABASE_USER",
                    "password": "DATABASE_PASSWORD",
                },
                "fallback": "DATABASE_URL",
            },
            "elile/ai/anthropic": {
                "env_vars": {"api_key": "ANTHROPIC_API_KEY"},
            },
            "elile/ai/openai": {
                "env_vars": {
                    "api_key": "OPENAI_API_KEY",
                    "organization_id": "OPENAI_ORG_ID",
                },
            },
            "elile/ai/google": {
                "env_vars": {
                    "api_key": "GOOGLE_API_KEY",
                    "project_id": "GOOGLE_PROJECT_ID",
                },
            },
            "elile/database/redis": {
                "env_vars": {
                    "host": "REDIS_HOST",
                    "port": "REDIS_PORT",
                    "password": "REDIS_PASSWORD",
                },
                "fallback": "REDIS_URL",
            },
            "elile/encryption/primary": {
                "env_vars": {"primary_key": "ENCRYPTION_KEY"},
            },
            "elile/app/api-secret": {
                "env_vars": {"value": "API_SECRET_KEY"},
            },
        }

        for path, mapping in standard_mappings.items():
            if path in self._secrets:
                continue  # Don't override explicit secrets

            data: dict[str, Any] = {}

            # Try individual env vars
            for field, env_var in mapping.get("env_vars", {}).items():
                value = os.environ.get(env_var)
                if value:
                    # Convert port to int if possible
                    if field == "port":
                        with contextlib.suppress(ValueError):
                            value = int(value)  # type: ignore[assignment]
                    data[field] = value

            # Try fallback URL
            if not data and "fallback" in mapping:
                url = os.environ.get(mapping["fallback"])
                if url:
                    data = self._parse_url(url, path)

            if data:
                self._secrets[path] = data
                logger.debug(f"Loaded standard secret: {path}")

    def _parse_url(self, url: str, path: str) -> dict[str, Any]:
        """Parse a URL into credential components.

        Args:
            url: URL to parse
            path: Secret path (for context)

        Returns:
            Dictionary of parsed components
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)

        if "database" in path:
            return {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 5432,
                "database": parsed.path.lstrip("/") or "elile",
                "username": parsed.username or "postgres",
                "password": parsed.password or "",
            }

        if "redis" in path:
            return {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 6379,
                "password": parsed.password,
                "database": int(parsed.path.lstrip("/") or "0"),
            }

        return {"url": url}

    async def get_secret(self, path: str | SecretPath) -> SecretValue:
        """Retrieve a secret.

        Args:
            path: Path to the secret

        Returns:
            SecretValue containing the secret data

        Raises:
            SecretNotFoundError: If secret not found
        """
        path_str = path.value if isinstance(path, SecretPath) else path

        # Check cache first
        cached = self._cache.get(path_str)
        if cached is not None:
            return cached

        # Check in-memory secrets
        if path_str not in self._secrets:
            if self.config.allow_missing:
                logger.warning(f"Secret not found (allowed): {path_str}")
                # Return empty secret
                return create_secret_from_data(path_str, {}, SecretType.GENERIC)
            raise SecretNotFoundError(path_str)

        data = self._secrets[path_str]
        value = create_secret_from_data(path_str, data, SecretType.GENERIC)

        # Cache the result
        self._cache.set(path_str, value)

        return value

    async def set_secret(
        self,
        path: str | SecretPath,
        data: dict[str, Any],
        secret_type: SecretType = SecretType.GENERIC,
        metadata: dict[str, str] | None = None,  # noqa: ARG002 - protocol compatibility
    ) -> SecretValue:
        """Store a secret (in-memory only for environment manager).

        Args:
            path: Path to store the secret
            data: Secret data
            secret_type: Type of secret
            metadata: Optional metadata

        Returns:
            SecretValue with the stored secret
        """
        path_str = path.value if isinstance(path, SecretPath) else path
        self._secrets[path_str] = data

        value = create_secret_from_data(path_str, data, secret_type)
        self._cache.set(path_str, value)

        logger.debug(f"Set secret: {path_str}")
        return value

    async def delete_secret(self, path: str | SecretPath) -> bool:
        """Delete a secret.

        Args:
            path: Path to delete

        Returns:
            True if deleted, False if not found
        """
        path_str = path.value if isinstance(path, SecretPath) else path

        if path_str in self._secrets:
            del self._secrets[path_str]
            self._cache.invalidate(path_str)
            return True
        return False

    async def list_secrets(self, prefix: str) -> list[str]:
        """List secret paths under a prefix.

        Args:
            prefix: Path prefix

        Returns:
            List of matching paths
        """
        return [path for path in self._secrets if path.startswith(prefix)]

    async def get_database_credentials(
        self, path: str | SecretPath = SecretPath.DATABASE
    ) -> DatabaseCredentials:
        """Get database credentials.

        Args:
            path: Path to the database secret

        Returns:
            DatabaseCredentials object
        """
        secret = await self.get_secret(path)
        data = secret.data

        return DatabaseCredentials(
            host=data.get("host", "localhost"),
            port=int(data.get("port", 5432)),
            database=data.get("database", "elile"),
            username=data.get("username", "postgres"),
            password=data.get("password", ""),
            ssl_mode=data.get("ssl_mode", "prefer"),
        )

    async def get_api_key(self, provider: str) -> ProviderApiKey:
        """Get API key for a data provider.

        Args:
            provider: Provider identifier

        Returns:
            ProviderApiKey object
        """
        path = f"elile/providers/{provider}"
        secret = await self.get_secret(path)
        data = secret.data

        return ProviderApiKey(
            provider_id=provider,
            api_key=data.get("api_key", data.get("value", "")),
            api_secret=data.get("api_secret"),
            base_url=data.get("base_url"),
            environment=data.get("environment", "production"),
            rate_limit_rpm=data.get("rate_limit_rpm"),
        )

    async def get_ai_provider_secrets(self, provider: str) -> AIProviderSecrets:
        """Get secrets for an AI provider.

        Args:
            provider: AI provider (anthropic, openai, google)

        Returns:
            AIProviderSecrets object
        """
        path = f"elile/ai/{provider}"
        secret = await self.get_secret(path)
        data = secret.data

        return AIProviderSecrets(
            provider=provider,
            api_key=data.get("api_key", data.get("value", "")),
            organization_id=data.get("organization_id"),
            project_id=data.get("project_id"),
            base_url=data.get("base_url"),
        )

    async def get_encryption_keys(
        self, path: str | SecretPath = SecretPath.ENCRYPTION_PRIMARY
    ) -> EncryptionKeys:
        """Get encryption keys.

        Args:
            path: Path to the encryption keys

        Returns:
            EncryptionKeys object
        """
        secret = await self.get_secret(path)
        data = secret.data

        return EncryptionKeys(
            primary_key=data.get("primary_key", data.get("value", "")),
            key_id=data.get("key_id", "env-default"),
            algorithm=data.get("algorithm", "AES-256-GCM"),
            previous_keys=data.get("previous_keys", []),
        )

    async def rotate_secret(
        self,
        path: str | SecretPath,
        new_data: dict[str, Any],
        keep_previous: bool = True,
    ) -> SecretValue:
        """Rotate a secret.

        For environment manager, this just updates the in-memory value.

        Args:
            path: Path to the secret
            new_data: New secret data
            keep_previous: Whether to keep previous version

        Returns:
            SecretValue with the new secret
        """
        path_str = path.value if isinstance(path, SecretPath) else path

        if keep_previous and path_str in self._secrets:
            old_data = self._secrets[path_str]
            if "previous" in new_data:
                new_data["previous"].append(old_data)
            else:
                new_data["previous"] = [old_data]

        return await self.set_secret(path_str, new_data)

    async def health_check(self) -> bool:
        """Check if the manager is healthy.

        Returns:
            Always True for environment manager
        """
        return True

    async def close(self) -> None:
        """Cleanup resources."""
        await self._cache.stop()
