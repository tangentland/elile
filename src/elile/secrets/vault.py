"""HashiCorp Vault secrets manager implementation.

This module provides integration with HashiCorp Vault for
production-grade secrets management.
"""

import asyncio
import contextlib
import logging
from datetime import datetime
from functools import cached_property
from typing import Any

from elile.secrets.cache import SecretCache, SecretCacheConfig
from elile.secrets.config import VaultConfig
from elile.secrets.protocol import (
    SecretNotFoundError,
    SecretPath,
    SecretsAccessError,
    SecretsConnectionError,
    SecretValue,
)
from elile.secrets.types import (
    AIProviderSecrets,
    DatabaseCredentials,
    EncryptionKeys,
    ProviderApiKey,
    SecretMetadata,
    SecretType,
)

logger = logging.getLogger(__name__)

__all__ = ["VaultConfig", "VaultSecretsManager"]


class VaultSecretsManager:
    """Secrets manager using HashiCorp Vault.

    This implementation uses the hvac library to interact with
    HashiCorp Vault's KV v2 secrets engine.

    Features:
    - Token, AppRole, and Kubernetes authentication
    - KV v2 secrets engine support
    - Secret versioning
    - Automatic token renewal
    - Caching with TTL

    Example:
        config = VaultConfig(
            url="https://vault.example.com:8200",
            token="s.xxxxxxx",
        )
        manager = VaultSecretsManager(config)
        await manager.connect()

        db_creds = await manager.get_database_credentials()
    """

    def __init__(
        self,
        config: VaultConfig,
        cache: SecretCache | None = None,
    ):
        """Initialize the Vault secrets manager.

        Args:
            config: Vault configuration
            cache: Optional cache instance
        """
        self.config = config
        self._cache = cache or SecretCache(SecretCacheConfig(enabled=True))
        self._client: Any | None = None
        self._connected = False
        self._token_renewal_task: asyncio.Task[None] | None = None

    @cached_property
    def _hvac(self) -> Any:
        """Lazy import of hvac module."""
        try:
            import hvac  # type: ignore[import-untyped]

            return hvac
        except ImportError as e:
            raise ImportError(
                "hvac package is required for Vault integration. "
                "Install it with: pip install hvac"
            ) from e

    async def connect(self) -> None:
        """Connect to Vault and authenticate.

        Raises:
            SecretsConnectionError: If connection fails
        """
        try:
            # Create the client
            self._client = self._hvac.Client(
                url=self.config.url,
                token=self.config.token if self.config.auth_method == "token" else None,
                namespace=self.config.namespace,
                verify=self.config.tls_verify,
                cert=(
                    (self.config.client_cert, self.config.client_key)
                    if self.config.client_cert
                    else None
                ),
                timeout=self.config.timeout,
            )

            # Authenticate based on method
            if self.config.auth_method == "approle":
                await self._auth_approle()
            elif self.config.auth_method == "kubernetes":
                await self._auth_kubernetes()
            elif self.config.auth_method == "aws":
                await self._auth_aws()
            elif self.config.auth_method == "gcp":
                await self._auth_gcp()

            # Verify connection
            if not await self._verify_connection():
                raise SecretsConnectionError("Vault", Exception("Failed to verify connection"))

            self._connected = True
            logger.info(f"Connected to Vault at {self.config.url}")

            # Start cache cleanup and token renewal
            await self._cache.start()
            self._start_token_renewal()

        except Exception as e:
            logger.error(f"Failed to connect to Vault: {e}")
            raise SecretsConnectionError("Vault", e) from e

    async def _auth_approle(self) -> None:
        """Authenticate using AppRole."""
        if not self.config.role_id or not self.config.secret_id:
            raise SecretsAccessError("AppRole requires role_id and secret_id")

        # Run synchronous hvac call in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.auth.approle.login(  # type: ignore[union-attr]
                role_id=self.config.role_id,
                secret_id=self.config.secret_id,
            ),
        )
        logger.debug("Authenticated with AppRole")

    async def _auth_kubernetes(self) -> None:
        """Authenticate using Kubernetes service account."""
        if not self.config.kubernetes_role:
            raise SecretsAccessError("Kubernetes auth requires kubernetes_role")

        # Read service account token
        try:
            with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
                jwt = f.read()
        except FileNotFoundError as e:
            raise SecretsAccessError("Kubernetes service account token not found") from e

        # Run synchronous hvac call in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.auth.kubernetes.login(  # type: ignore[union-attr]
                role=self.config.kubernetes_role,
                jwt=jwt,
                mount_point=self.config.kubernetes_mount,
            ),
        )
        logger.debug("Authenticated with Kubernetes")

    async def _auth_aws(self) -> None:
        """Authenticate using AWS IAM."""
        # AWS auth requires boto3 for signing
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.auth.aws.iam_login(),  # type: ignore[union-attr]
        )
        logger.debug("Authenticated with AWS IAM")

    async def _auth_gcp(self) -> None:
        """Authenticate using GCP."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.auth.gcp.login(),  # type: ignore[union-attr]
        )
        logger.debug("Authenticated with GCP")

    async def _verify_connection(self) -> bool:
        """Verify the Vault connection is working."""
        try:
            loop = asyncio.get_event_loop()
            is_authenticated: bool = await loop.run_in_executor(
                None,
                lambda: self._client.is_authenticated(),  # type: ignore[union-attr]
            )
            return is_authenticated
        except Exception:
            return False

    def _start_token_renewal(self) -> None:
        """Start background token renewal task."""
        if self._token_renewal_task is None:
            self._token_renewal_task = asyncio.create_task(self._token_renewal_loop())

    async def _token_renewal_loop(self) -> None:
        """Periodically renew the Vault token."""
        while True:
            try:
                # Renew every 30 minutes (half the default 1-hour TTL)
                await asyncio.sleep(1800)

                if self._client and self._connected:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: self._client.auth.token.renew_self(),  # type: ignore[union-attr]
                    )
                    logger.debug("Renewed Vault token")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Token renewal failed: {e}")

    def _normalize_path(self, path: str | SecretPath) -> str:
        """Normalize a secret path for Vault.

        Args:
            path: Secret path

        Returns:
            Normalized path without leading "elile/"
        """
        path_str = path.value if isinstance(path, SecretPath) else path

        # Remove leading "elile/" if present - Vault paths don't need it
        if path_str.startswith("elile/"):
            path_str = path_str[6:]

        return path_str

    async def get_secret(self, path: str | SecretPath) -> SecretValue:
        """Retrieve a secret from Vault.

        Args:
            path: Path to the secret

        Returns:
            SecretValue containing the secret data

        Raises:
            SecretNotFoundError: If secret not found
            SecretsAccessError: If access denied
        """
        if not self._connected:
            await self.connect()

        path_str = path.value if isinstance(path, SecretPath) else path
        vault_path = self._normalize_path(path)

        # Check cache first
        cached = self._cache.get(path_str)
        if cached is not None:
            return cached

        try:
            # Read from Vault KV v2
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.secrets.kv.v2.read_secret_version(  # type: ignore[union-attr]
                    path=vault_path,
                    mount_point=self.config.mount_point,
                ),
            )

            if response is None:
                raise SecretNotFoundError(path_str)

            data = response["data"]["data"]
            metadata_raw = response["data"]["metadata"]

            # Build metadata
            metadata = SecretMetadata(
                secret_type=SecretType.GENERIC,
                created_at=(
                    datetime.fromisoformat(
                        metadata_raw.get("created_time", "").replace("Z", "+00:00")
                    )
                    if metadata_raw.get("created_time")
                    else datetime.utcnow()
                ),
                updated_at=datetime.utcnow(),
                version=metadata_raw.get("version", 1),
            )

            value = SecretValue(
                path=path_str,
                data=data,
                metadata=metadata,
                cached=False,
                retrieved_at=datetime.utcnow(),
            )

            # Cache the result
            self._cache.set(path_str, value)

            return value

        except self._hvac.exceptions.InvalidPath as e:
            raise SecretNotFoundError(path_str) from e
        except self._hvac.exceptions.Forbidden as e:
            raise SecretsAccessError(f"Access denied to secret: {path_str}", e) from e
        except Exception as e:
            raise SecretsAccessError(f"Failed to read secret: {path_str}", e) from e

    async def set_secret(
        self,
        path: str | SecretPath,
        data: dict[str, Any],
        secret_type: SecretType = SecretType.GENERIC,  # noqa: ARG002
        metadata: dict[str, str] | None = None,  # noqa: ARG002
    ) -> SecretValue:
        """Store a secret in Vault.

        Args:
            path: Path to store the secret
            data: Secret data
            secret_type: Type of secret
            metadata: Optional custom metadata

        Returns:
            SecretValue with the stored secret
        """
        if not self._connected:
            await self.connect()

        path_str = path.value if isinstance(path, SecretPath) else path
        vault_path = self._normalize_path(path)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.secrets.kv.v2.create_or_update_secret(  # type: ignore[union-attr]
                    path=vault_path,
                    secret=data,
                    mount_point=self.config.mount_point,
                ),
            )

            # Invalidate cache
            self._cache.invalidate(path_str)

            # Read back the secret to get version info
            return await self.get_secret(path)

        except self._hvac.exceptions.Forbidden as e:
            raise SecretsAccessError(f"Access denied to write secret: {path_str}", e) from e
        except Exception as e:
            raise SecretsAccessError(f"Failed to write secret: {path_str}", e) from e

    async def delete_secret(self, path: str | SecretPath) -> bool:
        """Delete a secret from Vault.

        Args:
            path: Path to delete

        Returns:
            True if deleted
        """
        if not self._connected:
            await self.connect()

        path_str = path.value if isinstance(path, SecretPath) else path
        vault_path = self._normalize_path(path)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.secrets.kv.v2.delete_metadata_and_all_versions(  # type: ignore[union-attr]
                    path=vault_path,
                    mount_point=self.config.mount_point,
                ),
            )

            self._cache.invalidate(path_str)
            return True

        except self._hvac.exceptions.InvalidPath:
            return False
        except Exception as e:
            raise SecretsAccessError(f"Failed to delete secret: {path_str}", e) from e

    async def list_secrets(self, prefix: str) -> list[str]:
        """List secret paths under a prefix.

        Args:
            prefix: Path prefix

        Returns:
            List of secret paths
        """
        if not self._connected:
            await self.connect()

        vault_prefix = self._normalize_path(prefix)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.secrets.kv.v2.list_secrets(  # type: ignore[union-attr]
                    path=vault_prefix,
                    mount_point=self.config.mount_point,
                ),
            )

            keys = response.get("data", {}).get("keys", [])
            return [f"elile/{vault_prefix}/{k}".rstrip("/") for k in keys]

        except self._hvac.exceptions.InvalidPath:
            return []
        except Exception as e:
            raise SecretsAccessError(f"Failed to list secrets: {prefix}", e) from e

    async def get_database_credentials(
        self, path: str | SecretPath = SecretPath.DATABASE
    ) -> DatabaseCredentials:
        """Get database credentials from Vault.

        Args:
            path: Path to the database secret

        Returns:
            DatabaseCredentials object
        """
        secret = await self.get_secret(path)
        data = secret.data

        return DatabaseCredentials(
            host=data["host"],
            port=int(data.get("port", 5432)),
            database=data["database"],
            username=data["username"],
            password=data["password"],
            ssl_mode=data.get("ssl_mode", "prefer"),
            ssl_ca=data.get("ssl_ca"),
            ssl_cert=data.get("ssl_cert"),
            ssl_key=data.get("ssl_key"),
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
            api_key=data["api_key"],
            api_secret=data.get("api_secret"),
            base_url=data.get("base_url"),
            environment=data.get("environment", "production"),
            rate_limit_rpm=data.get("rate_limit_rpm"),
            metadata=data.get("metadata", {}),
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
            api_key=data["api_key"],
            organization_id=data.get("organization_id"),
            project_id=data.get("project_id"),
            base_url=data.get("base_url"),
            model_overrides=data.get("model_overrides", {}),
        )

    async def get_encryption_keys(
        self, path: str | SecretPath = SecretPath.ENCRYPTION_PRIMARY
    ) -> EncryptionKeys:
        """Get encryption keys from Vault.

        Args:
            path: Path to the encryption keys

        Returns:
            EncryptionKeys object
        """
        secret = await self.get_secret(path)
        data = secret.data

        return EncryptionKeys(
            primary_key=data["primary_key"],
            key_id=data.get("key_id", "vault-managed"),
            algorithm=data.get("algorithm", "AES-256-GCM"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.utcnow()
            ),
            previous_keys=data.get("previous_keys", []),
        )

    async def rotate_secret(
        self,
        path: str | SecretPath,
        new_data: dict[str, Any],
        keep_previous: bool = True,
    ) -> SecretValue:
        """Rotate a secret to a new value.

        For Vault KV v2, this creates a new version automatically.

        Args:
            path: Path to the secret
            new_data: New secret data
            keep_previous: Whether to preserve previous version (KV v2 does this automatically)

        Returns:
            SecretValue with the new secret
        """
        # If keeping previous, include the old key in the new data for encryption keys
        if keep_previous and "primary_key" in new_data:
            try:
                old_secret = await self.get_secret(path)
                old_key = old_secret.data.get("primary_key")
                if old_key:
                    previous_keys = new_data.get("previous_keys", [])
                    previous_keys.append(old_key)
                    new_data["previous_keys"] = previous_keys
            except SecretNotFoundError:
                pass

        return await self.set_secret(path, new_data)

    async def health_check(self) -> bool:
        """Check if Vault is healthy.

        Returns:
            True if healthy
        """
        if not self._client:
            return False

        try:
            return await self._verify_connection()
        except Exception:
            return False

    async def close(self) -> None:
        """Close connections and cleanup."""
        if self._token_renewal_task:
            self._token_renewal_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._token_renewal_task
            self._token_renewal_task = None

        await self._cache.stop()
        self._connected = False
        self._client = None
        logger.info("Disconnected from Vault")
