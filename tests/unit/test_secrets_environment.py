"""Tests for environment-based secrets manager."""

import os
from unittest.mock import patch

import pytest

from elile.secrets.config import EnvironmentSecretsConfig
from elile.secrets.environment import EnvironmentSecretsManager
from elile.secrets.protocol import SecretNotFoundError, SecretPath
from elile.secrets.types import SecretType


@pytest.fixture
def env_config() -> EnvironmentSecretsConfig:
    """Create test environment config."""
    return EnvironmentSecretsConfig(
        prefix="ELILE_TEST_SECRET_",
        allow_missing=False,
    )


@pytest.fixture
def env_manager(env_config: EnvironmentSecretsConfig) -> EnvironmentSecretsManager:
    """Create test environment manager."""
    return EnvironmentSecretsManager(env_config)


class TestEnvironmentSecretsManager:
    """Tests for EnvironmentSecretsManager."""

    @pytest.mark.asyncio
    async def test_get_secret_not_found_strict(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test getting nonexistent secret in strict mode."""
        with pytest.raises(SecretNotFoundError):
            await env_manager.get_secret("elile/nonexistent/path")

    @pytest.mark.asyncio
    async def test_get_secret_not_found_lenient(self) -> None:
        """Test getting nonexistent secret in lenient mode."""
        config = EnvironmentSecretsConfig(allow_missing=True)
        manager = EnvironmentSecretsManager(config)

        secret = await manager.get_secret("elile/nonexistent/path")
        assert secret.data == {}

    @pytest.mark.asyncio
    async def test_set_and_get_secret(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test setting and getting a secret."""
        data = {"api_key": "test_key_123"}
        await env_manager.set_secret("elile/test/api", data)

        secret = await env_manager.get_secret("elile/test/api")
        assert secret.data == data

    @pytest.mark.asyncio
    async def test_delete_secret(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test deleting a secret."""
        await env_manager.set_secret("elile/test/delete", {"value": "test"})

        # Delete
        result = await env_manager.delete_secret("elile/test/delete")
        assert result is True

        # Should raise now
        with pytest.raises(SecretNotFoundError):
            await env_manager.get_secret("elile/test/delete")

    @pytest.mark.asyncio
    async def test_delete_nonexistent(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test deleting nonexistent secret."""
        result = await env_manager.delete_secret("elile/nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_secrets(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test listing secrets by prefix."""
        await env_manager.set_secret("elile/test/a", {"value": "a"})
        await env_manager.set_secret("elile/test/b", {"value": "b"})
        await env_manager.set_secret("elile/other/c", {"value": "c"})

        secrets = await env_manager.list_secrets("elile/test")
        assert len(secrets) == 2
        assert "elile/test/a" in secrets
        assert "elile/test/b" in secrets

    @pytest.mark.asyncio
    async def test_get_database_credentials(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test getting database credentials."""
        await env_manager.set_secret(
            SecretPath.DATABASE,
            {
                "host": "db.example.com",
                "port": 5432,
                "database": "elile_test",
                "username": "testuser",
                "password": "testpass",
            },
        )

        creds = await env_manager.get_database_credentials()
        assert creds.host == "db.example.com"
        assert creds.port == 5432
        assert creds.database == "elile_test"
        assert creds.username == "testuser"
        assert creds.password == "testpass"

    @pytest.mark.asyncio
    async def test_get_api_key(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test getting provider API key."""
        await env_manager.set_secret(
            "elile/providers/sterling",
            {
                "api_key": "sk_sterling_123",
                "base_url": "https://api.sterling.com",
            },
        )

        key = await env_manager.get_api_key("sterling")
        assert key.provider_id == "sterling"
        assert key.api_key == "sk_sterling_123"
        assert key.base_url == "https://api.sterling.com"

    @pytest.mark.asyncio
    async def test_get_ai_provider_secrets(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test getting AI provider secrets."""
        await env_manager.set_secret(
            "elile/ai/anthropic",
            {"api_key": "sk-ant-test"},
        )

        secrets = await env_manager.get_ai_provider_secrets("anthropic")
        assert secrets.provider == "anthropic"
        assert secrets.api_key == "sk-ant-test"

    @pytest.mark.asyncio
    async def test_get_encryption_keys(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test getting encryption keys."""
        await env_manager.set_secret(
            SecretPath.ENCRYPTION_PRIMARY,
            {
                "primary_key": "base64encodedkey==",
                "key_id": "key-001",
            },
        )

        keys = await env_manager.get_encryption_keys()
        assert keys.primary_key == "base64encodedkey=="
        assert keys.key_id == "key-001"

    @pytest.mark.asyncio
    async def test_rotate_secret(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test rotating a secret."""
        # Set initial
        await env_manager.set_secret(
            "elile/test/rotate",
            {"value": "old"},
        )

        # Rotate
        new_secret = await env_manager.rotate_secret(
            "elile/test/rotate",
            {"value": "new"},
            keep_previous=True,
        )

        assert new_secret.data["value"] == "new"
        assert "previous" in new_secret.data

    @pytest.mark.asyncio
    async def test_health_check(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test health check always returns true."""
        assert await env_manager.health_check() is True

    @pytest.mark.asyncio
    async def test_close(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test closing the manager."""
        # Should not raise
        await env_manager.close()


class TestEnvironmentLoading:
    """Tests for loading secrets from environment variables."""

    @pytest.mark.asyncio
    async def test_load_from_standard_env_vars(self) -> None:
        """Test loading from standard environment variable names."""
        env_vars = {
            "ANTHROPIC_API_KEY": "sk-ant-env",
            "DATABASE_HOST": "localhost",
            "DATABASE_PORT": "5432",
            "DATABASE_NAME": "elile",
            "DATABASE_USER": "postgres",
            "DATABASE_PASSWORD": "secret",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = EnvironmentSecretsConfig(allow_missing=True)
            manager = EnvironmentSecretsManager(config)

            # Check AI key loaded
            secrets = await manager.get_ai_provider_secrets("anthropic")
            assert secrets.api_key == "sk-ant-env"

            # Check database creds loaded
            creds = await manager.get_database_credentials()
            assert creds.host == "localhost"
            assert creds.port == 5432

    @pytest.mark.asyncio
    async def test_load_from_prefixed_env_vars(self) -> None:
        """Test loading from prefixed environment variables."""
        env_vars = {
            "ELILE_SECRET_TEST_API": '{"api_key": "test_key"}',
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = EnvironmentSecretsConfig(prefix="ELILE_SECRET_")
            manager = EnvironmentSecretsManager(config)

            secret = await manager.get_secret("elile/test/api")
            assert secret.data["api_key"] == "test_key"

    @pytest.mark.asyncio
    async def test_load_from_database_url(self) -> None:
        """Test loading database credentials from URL."""
        env_vars = {
            "DATABASE_URL": "postgresql://user:pass@db.example.com:5432/mydb",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = EnvironmentSecretsConfig(allow_missing=True)
            manager = EnvironmentSecretsManager(config)

            creds = await manager.get_database_credentials()
            assert creds.host == "db.example.com"
            assert creds.port == 5432
            assert creds.database == "mydb"
            assert creds.username == "user"
            assert creds.password == "pass"

    @pytest.mark.asyncio
    async def test_load_from_redis_url(self) -> None:
        """Test loading Redis credentials from URL."""
        env_vars = {
            "REDIS_URL": "redis://:mypassword@redis.example.com:6380/1",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = EnvironmentSecretsConfig(allow_missing=True)
            manager = EnvironmentSecretsManager(config)

            secret = await manager.get_secret("elile/database/redis")
            assert secret.data["host"] == "redis.example.com"
            assert secret.data["port"] == 6380
            assert secret.data["password"] == "mypassword"
            # Database can be either int or str depending on parsing
            assert int(secret.data["database"]) == 1


class TestEnvironmentPathConversion:
    """Tests for path to env var conversion."""

    def test_path_to_env_var(self) -> None:
        """Test converting paths to environment variable names."""
        config = EnvironmentSecretsConfig(prefix="ELILE_SECRET_")
        manager = EnvironmentSecretsManager(config)

        # Test basic path
        assert (
            manager._path_to_env_var("elile/database/postgres") == "ELILE_SECRET_DATABASE_POSTGRES"
        )

        # Test with dashes
        assert manager._path_to_env_var("elile/ai/api-key") == "ELILE_SECRET_AI_API_KEY"

        # Test without elile prefix
        assert manager._path_to_env_var("database/postgres") == "ELILE_SECRET_DATABASE_POSTGRES"


class TestCaching:
    """Tests for caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test that cache is used on second access."""
        # Clear cache first
        env_manager._cache.clear()

        # Set secret directly to in-memory store (bypassing cache)
        env_manager._secrets["elile/test/cache"] = {"value": "cached"}

        # First access - should come from in-memory secrets, then be cached
        secret1 = await env_manager.get_secret("elile/test/cache")
        assert secret1.cached is False

        # Second access should be cached
        secret2 = await env_manager.get_secret("elile/test/cache")
        assert secret2.cached is True

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_set(
        self,
        env_manager: EnvironmentSecretsManager,
    ) -> None:
        """Test that cache is invalidated on set."""
        await env_manager.set_secret("elile/test/inv", {"value": "old"})

        # Cache it
        await env_manager.get_secret("elile/test/inv")

        # Update
        await env_manager.set_secret("elile/test/inv", {"value": "new"})

        # Should get new value
        secret = await env_manager.get_secret("elile/test/inv")
        assert secret.data["value"] == "new"
