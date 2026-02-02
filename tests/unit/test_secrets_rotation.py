"""Tests for secret rotation."""

import base64
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from elile.secrets.cache import create_secret_from_data
from elile.secrets.protocol import SecretNotFoundError, SecretPath, SecretsManager
from elile.secrets.rotation import (
    RotationConfig,
    RotationResult,
    RotationSchedule,
    RotationStatus,
    SecretRotator,
    create_secret_rotator,
)
from elile.secrets.types import SecretType


@pytest.fixture
def mock_secrets_manager() -> MagicMock:
    """Create a mock secrets manager."""
    manager = MagicMock(spec=SecretsManager)
    manager.get_secret = AsyncMock()
    manager.set_secret = AsyncMock()
    manager.rotate_secret = AsyncMock()
    return manager


@pytest.fixture
def rotator(mock_secrets_manager: MagicMock) -> SecretRotator:
    """Create a rotator with mock manager."""
    return SecretRotator(mock_secrets_manager)


class TestRotationConfig:
    """Tests for RotationConfig."""

    def test_default_config(self) -> None:
        """Test default rotation configuration."""
        config = RotationConfig()

        assert config.rotation_interval_days == 90
        assert config.notification_days_before == 7
        assert config.max_rotation_age_days == 180
        assert config.keep_previous_versions == 2
        assert config.rollback_on_failure is True
        assert config.verify_after_rotation is True

    def test_custom_config(self) -> None:
        """Test custom rotation configuration."""
        config = RotationConfig(
            rotation_interval_days=30,
            keep_previous_versions=5,
            verify_after_rotation=False,
        )

        assert config.rotation_interval_days == 30
        assert config.keep_previous_versions == 5
        assert config.verify_after_rotation is False


class TestRotationResult:
    """Tests for RotationResult."""

    def test_create_result(self) -> None:
        """Test creating a rotation result."""
        result = RotationResult(
            rotation_id="rot-123",
            path="elile/test/secret",
            status=RotationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        assert result.rotation_id == "rot-123"
        assert result.status == RotationStatus.COMPLETED

    def test_result_with_versions(self) -> None:
        """Test result with version tracking."""
        result = RotationResult(
            rotation_id="rot-456",
            path="elile/test/secret",
            status=RotationStatus.COMPLETED,
            started_at=datetime.utcnow(),
            old_version=1,
            new_version=2,
        )

        assert result.old_version == 1
        assert result.new_version == 2


class TestRotationSchedule:
    """Tests for RotationSchedule."""

    def test_create_schedule(self) -> None:
        """Test creating a rotation schedule."""
        config = RotationConfig(rotation_interval_days=30)
        schedule = RotationSchedule(
            path="elile/test/secret",
            config=config,
            next_rotation=datetime.utcnow() + timedelta(days=30),
        )

        assert schedule.path == "elile/test/secret"
        assert schedule.enabled is True
        assert schedule.last_rotated is None


class TestSecretRotatorKeyGeneration:
    """Tests for key generation utilities."""

    def test_generate_aes_key_256(self, rotator: SecretRotator) -> None:
        """Test generating 256-bit AES key."""
        key = rotator.generate_aes_key(256)

        # Should be base64 encoded
        decoded = base64.b64decode(key)
        assert len(decoded) == 32  # 256 bits = 32 bytes

    def test_generate_aes_key_128(self, rotator: SecretRotator) -> None:
        """Test generating 128-bit AES key."""
        key = rotator.generate_aes_key(128)

        decoded = base64.b64decode(key)
        assert len(decoded) == 16

    def test_generate_aes_key_invalid_size(self, rotator: SecretRotator) -> None:
        """Test invalid AES key size."""
        with pytest.raises(ValueError, match="must be 128, 192, or 256"):
            rotator.generate_aes_key(512)

    def test_generate_api_key(self, rotator: SecretRotator) -> None:
        """Test generating API key."""
        key = rotator.generate_api_key(32)

        # URL-safe base64 encoding expands size
        assert len(key) > 32
        # URL-safe base64 uses only alphanumeric, underscore, and hyphen
        assert all(c.isalnum() or c in "_-" for c in key)

    def test_generate_api_key_uniqueness(self, rotator: SecretRotator) -> None:
        """Test API keys are unique."""
        keys = [rotator.generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100

    def test_generate_password(self, rotator: SecretRotator) -> None:
        """Test generating password."""
        password = rotator.generate_password(32)

        assert len(password) == 32
        # Should contain various character types
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)

        assert has_upper
        assert has_lower
        assert has_digit

    def test_generate_password_no_special(self, rotator: SecretRotator) -> None:
        """Test password without special characters."""
        password = rotator.generate_password(32, include_special=False)

        # Should only be alphanumeric
        assert password.isalnum()


class TestSecretRotatorRotation:
    """Tests for secret rotation operations."""

    @pytest.mark.asyncio
    async def test_rotate_secret_success(
        self,
        mock_secrets_manager: MagicMock,
        rotator: SecretRotator,
    ) -> None:
        """Test successful secret rotation."""
        # Setup mocks
        old_secret = create_secret_from_data(
            "elile/test/secret",
            {"value": "old"},
            version=1,
        )
        new_secret = create_secret_from_data(
            "elile/test/secret",
            {"value": "new"},
            version=2,
        )

        mock_secrets_manager.get_secret.return_value = old_secret
        mock_secrets_manager.rotate_secret.return_value = new_secret

        # Rotate
        result = await rotator.rotate_secret(
            "elile/test/secret",
            {"value": "new"},
        )

        assert result.status == RotationStatus.COMPLETED
        assert result.old_version == 1
        assert result.new_version == 2
        mock_secrets_manager.rotate_secret.assert_called_once()

    @pytest.mark.asyncio
    async def test_rotate_secret_with_verification(
        self,
        mock_secrets_manager: MagicMock,
        rotator: SecretRotator,
    ) -> None:
        """Test rotation with verification."""
        new_secret = create_secret_from_data(
            "elile/test/secret",
            {"value": "new"},
            version=2,
        )
        mock_secrets_manager.get_secret.side_effect = SecretNotFoundError("not found")
        mock_secrets_manager.rotate_secret.return_value = new_secret

        # Verify function
        async def verify_fn(path: str, data: dict) -> bool:
            return data.get("value") == "new"

        result = await rotator.rotate_secret(
            "elile/test/secret",
            {"value": "new"},
            verify_fn=verify_fn,
        )

        assert result.status == RotationStatus.COMPLETED
        assert result.verification_passed is True

    @pytest.mark.asyncio
    async def test_rotate_secret_verification_failed_with_rollback(
        self,
        mock_secrets_manager: MagicMock,
        rotator: SecretRotator,
    ) -> None:
        """Test rotation rollback on verification failure."""
        old_secret = create_secret_from_data(
            "elile/test/secret",
            {"value": "old"},
            version=1,
        )
        new_secret = create_secret_from_data(
            "elile/test/secret",
            {"value": "new"},
            version=2,
        )

        mock_secrets_manager.get_secret.return_value = old_secret
        mock_secrets_manager.rotate_secret.return_value = new_secret

        # Failing verification
        async def verify_fn(path: str, data: dict) -> bool:
            return False

        result = await rotator.rotate_secret(
            "elile/test/secret",
            {"value": "new"},
            config=RotationConfig(rollback_on_failure=True),
            verify_fn=verify_fn,
        )

        assert result.status == RotationStatus.ROLLED_BACK
        assert result.verification_passed is False
        mock_secrets_manager.set_secret.assert_called_once()  # Rollback call

    @pytest.mark.asyncio
    async def test_rotate_encryption_key(
        self,
        mock_secrets_manager: MagicMock,
        rotator: SecretRotator,
    ) -> None:
        """Test rotating encryption key."""
        new_secret = create_secret_from_data(
            SecretPath.ENCRYPTION_PRIMARY.value,
            {"primary_key": "newkey=="},
            version=2,
        )
        mock_secrets_manager.get_secret.side_effect = SecretNotFoundError("not found")
        mock_secrets_manager.rotate_secret.return_value = new_secret

        result = await rotator.rotate_encryption_key()

        assert result.status == RotationStatus.COMPLETED
        # Verify rotate_secret was called with generated key
        call_args = mock_secrets_manager.rotate_secret.call_args
        assert "primary_key" in call_args[0][1]
        assert "key_id" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_rotate_api_key(
        self,
        mock_secrets_manager: MagicMock,
        rotator: SecretRotator,
    ) -> None:
        """Test rotating provider API key."""
        old_secret = create_secret_from_data(
            "elile/providers/sterling",
            {"api_key": "old_key", "base_url": "https://api.sterling.com"},
            version=1,
        )
        new_secret = create_secret_from_data(
            "elile/providers/sterling",
            {"api_key": "new_key", "base_url": "https://api.sterling.com"},
            version=2,
        )

        mock_secrets_manager.get_secret.return_value = old_secret
        mock_secrets_manager.rotate_secret.return_value = new_secret

        result = await rotator.rotate_api_key("sterling", new_api_key="new_key")

        assert result.status == RotationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_rotate_database_password(
        self,
        mock_secrets_manager: MagicMock,
        rotator: SecretRotator,
    ) -> None:
        """Test rotating database password."""
        old_secret = create_secret_from_data(
            SecretPath.DATABASE.value,
            {
                "host": "localhost",
                "port": 5432,
                "database": "elile",
                "username": "postgres",
                "password": "old_pass",
            },
            version=1,
        )
        new_secret = create_secret_from_data(
            SecretPath.DATABASE.value,
            {
                "host": "localhost",
                "port": 5432,
                "database": "elile",
                "username": "postgres",
                "password": "new_pass",
            },
            version=2,
        )

        mock_secrets_manager.get_secret.return_value = old_secret
        mock_secrets_manager.rotate_secret.return_value = new_secret

        result = await rotator.rotate_database_password(new_password="new_pass")

        assert result.status == RotationStatus.COMPLETED


class TestSecretRotatorScheduling:
    """Tests for rotation scheduling."""

    def test_schedule_rotation(self, rotator: SecretRotator) -> None:
        """Test scheduling a rotation."""
        config = RotationConfig(rotation_interval_days=30)
        schedule = rotator.schedule_rotation("elile/test/secret", config)

        assert schedule.path == "elile/test/secret"
        assert schedule.next_rotation is not None
        assert "elile/test/secret" in rotator._schedules

    def test_cancel_scheduled_rotation(self, rotator: SecretRotator) -> None:
        """Test canceling a scheduled rotation."""
        rotator.schedule_rotation("elile/test/secret")

        result = rotator.cancel_scheduled_rotation("elile/test/secret")
        assert result is True
        assert "elile/test/secret" not in rotator._schedules

    def test_cancel_nonexistent_schedule(self, rotator: SecretRotator) -> None:
        """Test canceling nonexistent schedule."""
        result = rotator.cancel_scheduled_rotation("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_due_rotations(self, rotator: SecretRotator) -> None:
        """Test checking for due rotations."""
        # Schedule with past due date
        schedule = RotationSchedule(
            path="elile/test/due",
            config=RotationConfig(),
            next_rotation=datetime.utcnow() - timedelta(days=1),
            enabled=True,
        )
        rotator._schedules["elile/test/due"] = schedule

        # Schedule with future date
        future_schedule = RotationSchedule(
            path="elile/test/future",
            config=RotationConfig(),
            next_rotation=datetime.utcnow() + timedelta(days=30),
            enabled=True,
        )
        rotator._schedules["elile/test/future"] = future_schedule

        due = await rotator.check_due_rotations()

        assert len(due) == 1
        assert due[0].path == "elile/test/due"

    def test_list_schedules(self, rotator: SecretRotator) -> None:
        """Test listing all schedules."""
        rotator.schedule_rotation("elile/test/a")
        rotator.schedule_rotation("elile/test/b")

        schedules = rotator.list_schedules()
        assert len(schedules) == 2

    def test_get_schedule(self, rotator: SecretRotator) -> None:
        """Test getting a specific schedule."""
        rotator.schedule_rotation("elile/test/secret")

        schedule = rotator.get_schedule("elile/test/secret")
        assert schedule is not None
        assert schedule.path == "elile/test/secret"

    def test_get_schedule_not_found(self, rotator: SecretRotator) -> None:
        """Test getting nonexistent schedule."""
        schedule = rotator.get_schedule("nonexistent")
        assert schedule is None


class TestSecretRotatorHistory:
    """Tests for rotation history."""

    @pytest.mark.asyncio
    async def test_rotation_history(
        self,
        mock_secrets_manager: MagicMock,
        rotator: SecretRotator,
    ) -> None:
        """Test rotation history is tracked."""
        new_secret = create_secret_from_data("elile/test/secret", {"value": "new"}, version=2)
        mock_secrets_manager.get_secret.side_effect = SecretNotFoundError("not found")
        mock_secrets_manager.rotate_secret.return_value = new_secret

        await rotator.rotate_secret("elile/test/secret", {"value": "new"})

        history = rotator.get_rotation_history()
        assert len(history) == 1
        assert history[0].path == "elile/test/secret"

    @pytest.mark.asyncio
    async def test_rotation_history_filtered(
        self,
        mock_secrets_manager: MagicMock,
        rotator: SecretRotator,
    ) -> None:
        """Test filtered rotation history."""
        secret_a = create_secret_from_data("elile/test/a", {"v": "a"}, version=1)
        secret_b = create_secret_from_data("elile/test/b", {"v": "b"}, version=1)

        mock_secrets_manager.get_secret.side_effect = SecretNotFoundError("not found")
        mock_secrets_manager.rotate_secret.side_effect = [secret_a, secret_b]

        await rotator.rotate_secret("elile/test/a", {"v": "a"})
        await rotator.rotate_secret("elile/test/b", {"v": "b"})

        history_a = rotator.get_rotation_history("elile/test/a")
        assert len(history_a) == 1
        assert history_a[0].path == "elile/test/a"


class TestCreateSecretRotator:
    """Tests for factory function."""

    def test_create_rotator(self, mock_secrets_manager: MagicMock) -> None:
        """Test creating rotator with factory."""
        rotator = create_secret_rotator(mock_secrets_manager)

        assert rotator.secrets_manager == mock_secrets_manager
        assert rotator.default_config is not None

    def test_create_rotator_with_config(self, mock_secrets_manager: MagicMock) -> None:
        """Test creating rotator with custom config."""
        config = RotationConfig(rotation_interval_days=14)
        rotator = create_secret_rotator(mock_secrets_manager, config)

        assert rotator.default_config.rotation_interval_days == 14
