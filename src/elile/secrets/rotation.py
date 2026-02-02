"""Secret rotation support.

This module provides utilities for rotating secrets safely,
including key generation, rotation scheduling, and rollback support.
"""

import asyncio
import base64
import contextlib
import logging
import secrets
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid7

from elile.secrets.protocol import (
    SecretPath,
    SecretsAccessError,
    SecretsManager,
    SecretValue,
)

logger = logging.getLogger(__name__)


class RotationStatus(str, Enum):
    """Status of a secret rotation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class RotationConfig:
    """Configuration for secret rotation.

    Attributes:
        rotation_interval_days: How often to rotate the secret
        notification_days_before: Days before rotation to send notification
        max_rotation_age_days: Maximum age before forcing rotation
        keep_previous_versions: Number of previous versions to keep
        rollback_on_failure: Whether to rollback on rotation failure
        verify_after_rotation: Whether to verify the new secret works
    """

    rotation_interval_days: int = 90
    notification_days_before: int = 7
    max_rotation_age_days: int = 180
    keep_previous_versions: int = 2
    rollback_on_failure: bool = True
    verify_after_rotation: bool = True


@dataclass
class RotationResult:
    """Result of a secret rotation operation.

    Attributes:
        rotation_id: Unique ID for this rotation
        path: Secret path that was rotated
        status: Current status of the rotation
        started_at: When rotation started
        completed_at: When rotation completed
        old_version: Previous secret version
        new_version: New secret version
        error_message: Error message if failed
        verification_passed: Whether verification passed
    """

    rotation_id: str
    path: str
    status: RotationStatus
    started_at: datetime
    completed_at: datetime | None = None
    old_version: int | None = None
    new_version: int | None = None
    error_message: str | None = None
    verification_passed: bool | None = None


@dataclass
class RotationSchedule:
    """Schedule for automatic secret rotation.

    Attributes:
        path: Secret path
        config: Rotation configuration
        last_rotated: When last rotated
        next_rotation: When next rotation is due
        enabled: Whether automatic rotation is enabled
    """

    path: str
    config: RotationConfig
    last_rotated: datetime | None = None
    next_rotation: datetime | None = None
    enabled: bool = True


# Type alias for rotation verification function
RotationVerifier = Callable[[str, dict[str, Any]], Coroutine[Any, Any, bool]]


class SecretRotator:
    """Handles secret rotation with safety features.

    Features:
    - Safe rotation with verification
    - Automatic rollback on failure
    - Rotation scheduling
    - Key generation utilities
    - Previous version preservation

    Example:
        rotator = SecretRotator(secrets_manager)

        # Rotate with new generated key
        result = await rotator.rotate_encryption_key(
            SecretPath.ENCRYPTION_PRIMARY,
            verify_fn=verify_encryption_works,
        )

        # Schedule automatic rotation
        rotator.schedule_rotation(
            SecretPath.DATABASE,
            RotationConfig(rotation_interval_days=30),
        )
    """

    def __init__(
        self,
        secrets_manager: SecretsManager,
        default_config: RotationConfig | None = None,
    ):
        """Initialize the rotator.

        Args:
            secrets_manager: Secrets manager to use
            default_config: Default rotation configuration
        """
        self.secrets_manager = secrets_manager
        self.default_config = default_config or RotationConfig()
        self._schedules: dict[str, RotationSchedule] = {}
        self._rotation_history: list[RotationResult] = []
        self._scheduler_task: asyncio.Task[None] | None = None

    # ----------------------------------------------------------------
    # Key generation utilities
    # ----------------------------------------------------------------

    @staticmethod
    def generate_aes_key(bits: int = 256) -> str:
        """Generate a new AES encryption key.

        Args:
            bits: Key size in bits (128, 192, or 256)

        Returns:
            Base64-encoded key
        """
        if bits not in (128, 192, 256):
            raise ValueError("AES key must be 128, 192, or 256 bits")

        key_bytes = secrets.token_bytes(bits // 8)
        return base64.b64encode(key_bytes).decode("utf-8")

    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """Generate a new API key.

        Args:
            length: Length of the key in bytes

        Returns:
            URL-safe base64-encoded key
        """
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_password(
        length: int = 32,
        include_special: bool = True,
    ) -> str:
        """Generate a secure random password.

        Args:
            length: Password length
            include_special: Whether to include special characters

        Returns:
            Random password string
        """
        import string

        alphabet = string.ascii_letters + string.digits
        if include_special:
            alphabet += "!@#$%^&*()_+-=[]{}|;:,.<>?"

        # Ensure at least one of each required type
        password = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
        ]
        if include_special:
            password.append(secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?"))

        # Fill the rest
        password.extend(secrets.choice(alphabet) for _ in range(length - len(password)))

        # Shuffle
        result = list(password)
        secrets.SystemRandom().shuffle(result)
        return "".join(result)

    # ----------------------------------------------------------------
    # Rotation operations
    # ----------------------------------------------------------------

    async def rotate_secret(
        self,
        path: str | SecretPath,
        new_data: dict[str, Any],
        config: RotationConfig | None = None,
        verify_fn: RotationVerifier | None = None,
    ) -> RotationResult:
        """Rotate a secret to new values.

        Args:
            path: Path to the secret
            new_data: New secret data
            config: Optional rotation configuration
            verify_fn: Optional verification function

        Returns:
            RotationResult with status and details

        Raises:
            SecretsAccessError: If rotation fails and rollback is disabled
        """
        path_str = path.value if isinstance(path, SecretPath) else path
        config = config or self.default_config
        rotation_id = str(uuid7())

        result = RotationResult(
            rotation_id=rotation_id,
            path=path_str,
            status=RotationStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
        )

        try:
            # Get current secret for rollback
            old_secret: SecretValue | None = None
            try:
                old_secret = await self.secrets_manager.get_secret(path)
                result.old_version = old_secret.metadata.version
            except Exception:
                logger.debug(f"No existing secret at {path_str}")

            # Perform rotation
            new_secret = await self.secrets_manager.rotate_secret(
                path,
                new_data,
                keep_previous=config.keep_previous_versions > 0,
            )
            result.new_version = new_secret.metadata.version

            # Verify if requested
            if config.verify_after_rotation and verify_fn:
                try:
                    verification_passed = await verify_fn(path_str, new_data)
                    result.verification_passed = verification_passed

                    if not verification_passed:
                        raise SecretsAccessError(
                            f"Verification failed for rotated secret: {path_str}"
                        )
                except Exception as e:
                    logger.error(f"Verification failed for {path_str}: {e}")
                    result.verification_passed = False

                    # Rollback if configured
                    if config.rollback_on_failure and old_secret:
                        await self._rollback(path, old_secret.data, result)
                        return result

                    raise

            # Update schedule if exists
            if path_str in self._schedules:
                schedule = self._schedules[path_str]
                schedule.last_rotated = datetime.utcnow()
                schedule.next_rotation = datetime.utcnow() + timedelta(
                    days=schedule.config.rotation_interval_days
                )

            result.status = RotationStatus.COMPLETED
            result.completed_at = datetime.utcnow()
            logger.info(f"Successfully rotated secret: {path_str}")

        except Exception as e:
            result.status = RotationStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.utcnow()
            logger.error(f"Failed to rotate secret {path_str}: {e}")

            if not config.rollback_on_failure:
                raise

        finally:
            self._rotation_history.append(result)

        return result

    async def _rollback(
        self,
        path: str | SecretPath,
        old_data: dict[str, Any],
        result: RotationResult,
    ) -> None:
        """Rollback a failed rotation.

        Args:
            path: Secret path
            old_data: Previous secret data
            result: RotationResult to update
        """
        path_str = path.value if isinstance(path, SecretPath) else path

        try:
            await self.secrets_manager.set_secret(path, old_data)
            result.status = RotationStatus.ROLLED_BACK
            logger.info(f"Rolled back secret rotation: {path_str}")
        except Exception as rollback_error:
            logger.error(f"Rollback failed for {path_str}: {rollback_error}")
            result.error_message = f"{result.error_message}; Rollback also failed: {rollback_error}"

    async def rotate_encryption_key(
        self,
        path: str | SecretPath = SecretPath.ENCRYPTION_PRIMARY,
        key_bits: int = 256,
        verify_fn: RotationVerifier | None = None,
    ) -> RotationResult:
        """Rotate an encryption key with a new generated key.

        Args:
            path: Path to the encryption key secret
            key_bits: Key size in bits
            verify_fn: Optional verification function

        Returns:
            RotationResult
        """
        new_key = self.generate_aes_key(key_bits)
        new_data = {
            "primary_key": new_key,
            "key_id": str(uuid7()),
            "algorithm": "AES-256-GCM",
            "created_at": datetime.utcnow().isoformat(),
        }

        return await self.rotate_secret(path, new_data, verify_fn=verify_fn)

    async def rotate_api_key(
        self,
        provider: str,
        new_api_key: str | None = None,
        verify_fn: RotationVerifier | None = None,
    ) -> RotationResult:
        """Rotate an API key for a provider.

        Args:
            provider: Provider identifier
            new_api_key: New API key (generated if not provided)
            verify_fn: Optional verification function

        Returns:
            RotationResult
        """
        path = f"elile/providers/{provider}"

        # Get current secret to preserve other fields
        try:
            current = await self.secrets_manager.get_secret(path)
            new_data = dict(current.data)
        except Exception:
            new_data = {"provider_id": provider}

        new_data["api_key"] = new_api_key or self.generate_api_key()

        return await self.rotate_secret(path, new_data, verify_fn=verify_fn)

    async def rotate_database_password(
        self,
        path: str | SecretPath = SecretPath.DATABASE,
        new_password: str | None = None,
        verify_fn: RotationVerifier | None = None,
    ) -> RotationResult:
        """Rotate database password.

        Note: This only updates the stored password. You must separately
        update the actual database user password.

        Args:
            path: Path to database credentials
            new_password: New password (generated if not provided)
            verify_fn: Verification function to test connection

        Returns:
            RotationResult
        """
        # Get current credentials
        current = await self.secrets_manager.get_secret(path)
        new_data = dict(current.data)
        new_data["password"] = new_password or self.generate_password()

        return await self.rotate_secret(path, new_data, verify_fn=verify_fn)

    # ----------------------------------------------------------------
    # Scheduling
    # ----------------------------------------------------------------

    def schedule_rotation(
        self,
        path: str | SecretPath,
        config: RotationConfig | None = None,
    ) -> RotationSchedule:
        """Schedule automatic rotation for a secret.

        Args:
            path: Secret path
            config: Rotation configuration

        Returns:
            RotationSchedule
        """
        path_str = path.value if isinstance(path, SecretPath) else path
        config = config or self.default_config

        schedule = RotationSchedule(
            path=path_str,
            config=config,
            next_rotation=datetime.utcnow() + timedelta(days=config.rotation_interval_days),
        )
        self._schedules[path_str] = schedule

        logger.info(f"Scheduled rotation for {path_str} every {config.rotation_interval_days} days")
        return schedule

    def cancel_scheduled_rotation(self, path: str | SecretPath) -> bool:
        """Cancel scheduled rotation for a secret.

        Args:
            path: Secret path

        Returns:
            True if cancelled, False if not found
        """
        path_str = path.value if isinstance(path, SecretPath) else path

        if path_str in self._schedules:
            del self._schedules[path_str]
            return True
        return False

    async def check_due_rotations(self) -> list[RotationSchedule]:
        """Check for secrets that are due for rotation.

        Returns:
            List of schedules that are due
        """
        now = datetime.utcnow()
        due = []

        for schedule in self._schedules.values():
            if not schedule.enabled:
                continue
            if schedule.next_rotation and schedule.next_rotation <= now:
                due.append(schedule)

        return due

    async def start_scheduler(self, check_interval_hours: int = 24) -> None:
        """Start the automatic rotation scheduler.

        Args:
            check_interval_hours: How often to check for due rotations
        """
        if self._scheduler_task is not None:
            return

        async def scheduler_loop() -> None:
            while True:
                try:
                    await asyncio.sleep(check_interval_hours * 3600)
                    due = await self.check_due_rotations()
                    for schedule in due:
                        logger.info(f"Auto-rotating due secret: {schedule.path}")
                        # Note: Auto-rotation requires pre-configured rotation logic
                        # For now, just log - actual rotation needs custom logic per secret type
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")

        self._scheduler_task = asyncio.create_task(scheduler_loop())
        logger.info("Started rotation scheduler")

    async def stop_scheduler(self) -> None:
        """Stop the automatic rotation scheduler."""
        if self._scheduler_task:
            self._scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler_task
            self._scheduler_task = None
            logger.info("Stopped rotation scheduler")

    # ----------------------------------------------------------------
    # History and status
    # ----------------------------------------------------------------

    def get_rotation_history(
        self,
        path: str | SecretPath | None = None,
        limit: int = 100,
    ) -> list[RotationResult]:
        """Get rotation history.

        Args:
            path: Optional path to filter by
            limit: Maximum results to return

        Returns:
            List of RotationResult
        """
        history = self._rotation_history

        if path:
            path_str = path.value if isinstance(path, SecretPath) else path
            history = [r for r in history if r.path == path_str]

        return history[-limit:]

    def get_schedule(self, path: str | SecretPath) -> RotationSchedule | None:
        """Get rotation schedule for a secret.

        Args:
            path: Secret path

        Returns:
            RotationSchedule or None
        """
        path_str = path.value if isinstance(path, SecretPath) else path
        return self._schedules.get(path_str)

    def list_schedules(self) -> list[RotationSchedule]:
        """List all rotation schedules.

        Returns:
            List of all schedules
        """
        return list(self._schedules.values())


def create_secret_rotator(
    secrets_manager: SecretsManager,
    config: RotationConfig | None = None,
) -> SecretRotator:
    """Create a SecretRotator instance.

    Args:
        secrets_manager: Secrets manager to use
        config: Optional default configuration

    Returns:
        SecretRotator instance
    """
    return SecretRotator(secrets_manager, config)
