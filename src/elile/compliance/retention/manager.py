"""Data retention manager for enforcing retention policies.

This module provides the RetentionManager class that:
- Tracks retention lifecycle for data items
- Enforces retention policies
- Handles archival and deletion workflows
- Processes erasure requests
- Generates compliance reports
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid7

from elile.compliance.retention.policies import (
    get_default_policies,
    get_policy_for_data_type,
)
from elile.compliance.retention.types import (
    DataType,
    DeletionMethod,
    ErasureRequest,
    RetentionAction,
    RetentionPolicy,
    RetentionRecord,
    RetentionReport,
    RetentionStatus,
)
from elile.compliance.types import Locale

logger = logging.getLogger(__name__)


# Type alias for deletion callbacks
DeletionCallback = Callable[[UUID, DataType], Coroutine[Any, Any, bool]]
ArchiveCallback = Callable[[UUID, DataType, dict[str, Any]], Coroutine[Any, Any, bool]]
AnonymizeCallback = Callable[[UUID, DataType], Coroutine[Any, Any, bool]]


@dataclass
class RetentionManagerConfig:
    """Configuration for the RetentionManager."""

    # Processing intervals
    check_interval_seconds: int = 3600  # 1 hour
    """How often to check for expired data."""

    batch_size: int = 100
    """Number of items to process per batch."""

    # Warning thresholds
    warning_days: int = 30
    """Days before expiry to start warning."""

    # Behavior
    auto_delete: bool = False
    """Whether to automatically delete expired data."""

    auto_archive: bool = True
    """Whether to automatically archive data."""

    require_confirmation: bool = True
    """Whether deletion requires explicit confirmation."""

    # Erasure request handling
    erasure_verification_required: bool = True
    """Whether erasure requests require identity verification."""

    erasure_response_days: int = 30
    """Days to respond to erasure requests (GDPR: 30 days)."""


class RetentionManager:
    """Manages data retention lifecycle.

    Tracks retention status, enforces policies, and handles
    archival/deletion workflows.
    """

    def __init__(
        self,
        config: RetentionManagerConfig | None = None,
        delete_callback: DeletionCallback | None = None,
        archive_callback: ArchiveCallback | None = None,
        anonymize_callback: AnonymizeCallback | None = None,
    ):
        """Initialize the retention manager.

        Args:
            config: Manager configuration
            delete_callback: Async function to delete data
            archive_callback: Async function to archive data
            anonymize_callback: Async function to anonymize data
        """
        self.config = config or RetentionManagerConfig()
        self._delete_callback = delete_callback
        self._archive_callback = archive_callback
        self._anonymize_callback = anonymize_callback

        # In-memory storage for records (would be database in production)
        self._records: dict[UUID, RetentionRecord] = {}
        self._policies: dict[UUID, RetentionPolicy] = {}
        self._erasure_requests: dict[UUID, ErasureRequest] = {}

        # Background task
        self._check_task: asyncio.Task[None] | None = None
        self._running = False

        # Load default policies
        for policy in get_default_policies():
            self._policies[policy.policy_id] = policy

        logger.info("RetentionManager initialized")

    # =========================================================================
    # Policy Management
    # =========================================================================

    def register_policy(self, policy: RetentionPolicy) -> None:
        """Register a custom retention policy.

        Args:
            policy: The policy to register
        """
        self._policies[policy.policy_id] = policy
        logger.info(f"Registered retention policy: {policy.name}")

    def get_policy(self, policy_id: UUID) -> RetentionPolicy | None:
        """Get a policy by ID.

        Args:
            policy_id: The policy ID

        Returns:
            The policy, or None if not found
        """
        return self._policies.get(policy_id)

    def get_applicable_policy(
        self,
        data_type: DataType,
        locale: Locale | None = None,
    ) -> RetentionPolicy | None:
        """Get the applicable policy for a data type and locale.

        Args:
            data_type: Type of data
            locale: Optional locale

        Returns:
            The applicable policy, or None if no match
        """
        return get_policy_for_data_type(data_type, locale)

    # =========================================================================
    # Record Management
    # =========================================================================

    def track_data(
        self,
        data_id: UUID,
        data_type: DataType,
        tenant_id: UUID,
        locale: Locale | None = None,
        created_at: datetime | None = None,
    ) -> RetentionRecord:
        """Start tracking retention for a data item.

        Args:
            data_id: ID of the data item
            data_type: Type of data
            tenant_id: Tenant that owns the data
            locale: Optional locale for policy selection
            created_at: When the data was created (defaults to now)

        Returns:
            The created retention record
        """
        if created_at is None:
            created_at = datetime.utcnow()

        # Find applicable policy
        policy = self.get_applicable_policy(data_type, locale)
        if policy is None:
            logger.warning(f"No retention policy found for {data_type}, using defaults")
            # Create a default policy
            policy = RetentionPolicy(
                policy_id=uuid7(),
                name=f"default_{data_type.value}",
                description="Auto-generated default policy",
                data_type=data_type,
                retention_days=7 * 365,  # 7 years default
                deletion_method=DeletionMethod.SOFT_DELETE,
            )
            self._policies[policy.policy_id] = policy

        # Calculate dates
        expires_at = policy.calculate_expiry(created_at)
        archive_at = policy.calculate_archive_date(created_at)

        # Create record
        record = RetentionRecord(
            record_id=uuid7(),
            data_type=data_type,
            data_id=data_id,
            tenant_id=tenant_id,
            policy_id=policy.policy_id,
            status=RetentionStatus.ACTIVE,
            created_at=created_at,
            expires_at=expires_at,
            archive_at=archive_at,
        )

        record.add_event(
            RetentionAction.CREATED,
            {
                "policy_name": policy.name,
                "retention_days": policy.retention_days,
            },
        )

        self._records[record.record_id] = record
        logger.debug(f"Tracking retention for {data_type} {data_id}, expires {expires_at}")

        return record

    def get_record(self, record_id: UUID) -> RetentionRecord | None:
        """Get a retention record by ID.

        Args:
            record_id: The record ID

        Returns:
            The record, or None if not found
        """
        return self._records.get(record_id)

    def get_record_by_data_id(self, data_id: UUID) -> RetentionRecord | None:
        """Get a retention record by data ID.

        Args:
            data_id: The data item ID

        Returns:
            The record, or None if not found
        """
        for record in self._records.values():
            if record.data_id == data_id:
                return record
        return None

    def get_records_by_status(self, status: RetentionStatus) -> list[RetentionRecord]:
        """Get all records with a specific status.

        Args:
            status: The status to filter by

        Returns:
            List of matching records
        """
        return [r for r in self._records.values() if r.status == status]

    def get_records_by_tenant(self, tenant_id: UUID) -> list[RetentionRecord]:
        """Get all records for a tenant.

        Args:
            tenant_id: The tenant ID

        Returns:
            List of tenant's records
        """
        return [r for r in self._records.values() if r.tenant_id == tenant_id]

    # =========================================================================
    # Legal Hold Management
    # =========================================================================

    def place_legal_hold(
        self,
        data_id: UUID,
        reason: str,
    ) -> bool:
        """Place a legal hold on data.

        Args:
            data_id: The data item ID
            reason: Reason for the hold

        Returns:
            True if hold was placed successfully
        """
        record = self.get_record_by_data_id(data_id)
        if record is None:
            logger.error(f"Cannot place legal hold: no record for {data_id}")
            return False

        record.place_legal_hold(reason)
        logger.info(f"Legal hold placed on {data_id}: {reason}")
        return True

    def release_legal_hold(self, data_id: UUID) -> bool:
        """Release a legal hold on data.

        Args:
            data_id: The data item ID

        Returns:
            True if hold was released successfully
        """
        record = self.get_record_by_data_id(data_id)
        if record is None:
            logger.error(f"Cannot release legal hold: no record for {data_id}")
            return False

        if not record.legal_hold:
            logger.warning(f"No legal hold on {data_id}")
            return False

        record.release_legal_hold()
        logger.info(f"Legal hold released on {data_id}")
        return True

    # =========================================================================
    # Lifecycle Processing
    # =========================================================================

    async def check_expiring_data(self) -> list[RetentionRecord]:
        """Find data that is expiring soon.

        Returns:
            List of records approaching expiry
        """
        warning_threshold = datetime.utcnow() + timedelta(days=self.config.warning_days)
        expiring = []

        for record in self._records.values():
            if record.legal_hold:
                continue
            if record.status in (RetentionStatus.DELETED, RetentionStatus.ARCHIVED):
                continue
            if record.expires_at <= warning_threshold:
                if record.status != RetentionStatus.EXPIRY_WARNING:
                    record.status = RetentionStatus.EXPIRY_WARNING
                expiring.append(record)

        return expiring

    async def check_expired_data(self) -> list[RetentionRecord]:
        """Find data that has expired.

        Returns:
            List of expired records
        """
        now = datetime.utcnow()
        expired = []

        for record in self._records.values():
            if record.legal_hold:
                continue
            if record.status in (RetentionStatus.DELETED, RetentionStatus.ARCHIVED):
                continue
            if record.expires_at <= now:
                record.status = RetentionStatus.DELETION_PENDING
                expired.append(record)

        return expired

    async def check_archive_pending(self) -> list[RetentionRecord]:
        """Find data that should be archived.

        Returns:
            List of records pending archival
        """
        now = datetime.utcnow()
        pending = []

        for record in self._records.values():
            if record.legal_hold:
                continue
            if record.status != RetentionStatus.ACTIVE:
                continue
            if record.archive_at and record.archive_at <= now:
                record.status = RetentionStatus.ARCHIVE_PENDING
                pending.append(record)

        return pending

    async def process_archival(self, record: RetentionRecord) -> bool:
        """Archive a data item.

        Args:
            record: The retention record

        Returns:
            True if archival was successful
        """
        if record.legal_hold:
            logger.warning(f"Cannot archive {record.data_id}: under legal hold")
            return False

        policy = self._policies.get(record.policy_id)
        if policy is None:
            logger.error(f"No policy found for record {record.record_id}")
            return False

        if self._archive_callback:
            try:
                success = await self._archive_callback(
                    record.data_id,
                    record.data_type,
                    {"policy": policy.name, "expires_at": record.expires_at.isoformat()},
                )
                if success:
                    record.status = RetentionStatus.ARCHIVED
                    record.add_event(RetentionAction.ARCHIVED)
                    logger.info(f"Archived {record.data_type} {record.data_id}")
                    return True
            except Exception as e:
                logger.error(f"Archive failed for {record.data_id}: {e}")
                return False
        else:
            # No callback, just mark as archived
            record.status = RetentionStatus.ARCHIVED
            record.add_event(RetentionAction.ARCHIVED)
            return True

        return False

    async def process_deletion(self, record: RetentionRecord) -> bool:
        """Delete a data item.

        Args:
            record: The retention record

        Returns:
            True if deletion was successful
        """
        if record.legal_hold:
            logger.warning(f"Cannot delete {record.data_id}: under legal hold")
            return False

        policy = self._policies.get(record.policy_id)
        if policy is None:
            logger.error(f"No policy found for record {record.record_id}")
            return False

        # Archive first if required
        if policy.archive_before_delete and record.status != RetentionStatus.ARCHIVED:
            await self.process_archival(record)

        # Execute deletion based on method
        success = False

        if policy.deletion_method == DeletionMethod.SOFT_DELETE:
            success = await self._soft_delete(record)
        elif policy.deletion_method == DeletionMethod.HARD_DELETE:
            success = await self._hard_delete(record)
        elif policy.deletion_method == DeletionMethod.ANONYMIZE:
            success = await self._anonymize(record)
        elif policy.deletion_method == DeletionMethod.CRYPTO_SHRED:
            success = await self._hard_delete(record)  # Same as hard delete for now
        elif policy.deletion_method == DeletionMethod.ARCHIVE:
            # Archive-only, don't actually delete
            success = await self.process_archival(record)

        if success:
            record.status = RetentionStatus.DELETED
            record.deleted_at = datetime.utcnow()
            record.add_event(RetentionAction.DELETED, {"method": policy.deletion_method.value})
            logger.info(f"Deleted {record.data_type} {record.data_id} ({policy.deletion_method})")

        return success

    async def _soft_delete(self, record: RetentionRecord) -> bool:  # noqa: ARG002
        """Perform soft delete (mark as deleted)."""
        # In production, this would mark the database record as deleted
        return True

    async def _hard_delete(self, record: RetentionRecord) -> bool:
        """Perform hard delete (remove from database)."""
        if self._delete_callback:
            try:
                return await self._delete_callback(record.data_id, record.data_type)
            except Exception as e:
                logger.error(f"Hard delete failed for {record.data_id}: {e}")
                return False
        return True

    async def _anonymize(self, record: RetentionRecord) -> bool:
        """Anonymize the data (remove PII, keep structure)."""
        if self._anonymize_callback:
            try:
                return await self._anonymize_callback(record.data_id, record.data_type)
            except Exception as e:
                logger.error(f"Anonymization failed for {record.data_id}: {e}")
                return False
        return True

    # =========================================================================
    # Erasure Requests (GDPR)
    # =========================================================================

    async def submit_erasure_request(
        self,
        subject_id: UUID,
        tenant_id: UUID,
        locale: Locale,
        data_types: list[DataType] | None = None,
        reason: str | None = None,
    ) -> ErasureRequest:
        """Submit a data erasure request (GDPR right to be forgotten).

        Args:
            subject_id: ID of the subject requesting erasure
            tenant_id: Tenant that owns the data
            locale: Locale for compliance requirements
            data_types: Specific data types to erase (None = all)
            reason: Reason for the request

        Returns:
            The created erasure request
        """
        request = ErasureRequest(
            request_id=uuid7(),
            subject_id=subject_id,
            tenant_id=tenant_id,
            locale=locale,
            requested_data_types=data_types or [],
            reason=reason,
        )

        self._erasure_requests[request.request_id] = request
        logger.info(f"Erasure request submitted: {request.request_id}")

        return request

    async def verify_erasure_request(
        self,
        request_id: UUID,
        verification_method: str,
    ) -> bool:
        """Verify the identity of an erasure requestor.

        Args:
            request_id: The request ID
            verification_method: Method used to verify identity

        Returns:
            True if verification was successful
        """
        request = self._erasure_requests.get(request_id)
        if request is None:
            return False

        request.verified = True
        request.verified_at = datetime.utcnow()
        request.verification_method = verification_method

        logger.info(f"Erasure request verified: {request_id}")
        return True

    async def process_erasure_request(self, request_id: UUID) -> ErasureRequest:
        """Process a verified erasure request.

        Args:
            request_id: The request ID

        Returns:
            The updated request with results

        Raises:
            ValueError: If request is not verified
        """
        request = self._erasure_requests.get(request_id)
        if request is None:
            raise ValueError(f"Erasure request not found: {request_id}")

        if self.config.erasure_verification_required and not request.verified:
            raise ValueError("Erasure request not verified")

        request.status = "processing"

        # Find all records for this subject
        subject_records = [
            r
            for r in self._records.values()
            if r.tenant_id == request.tenant_id
            # In production, would also filter by subject_id
        ]

        # Filter by data type if specified
        if request.requested_data_types:
            subject_records = [
                r for r in subject_records if r.data_type in request.requested_data_types
            ]

        # Process each record
        for record in subject_records:
            policy = self._policies.get(record.policy_id)
            if policy is None:
                continue

            # Check if erasure is allowed
            if not policy.subject_request_override:
                request.items_retained += 1
                request.retention_reasons.append(
                    f"{record.data_type.value}: {policy.regulatory_basis or 'Policy override not allowed'}"
                )
                continue

            if record.legal_hold:
                request.items_retained += 1
                request.retention_reasons.append(f"{record.data_type.value}: Under legal hold")
                continue

            # Process deletion
            success = await self.process_deletion(record)
            if success:
                request.items_deleted += 1
            else:
                request.items_retained += 1
                request.retention_reasons.append(f"{record.data_type.value}: Deletion failed")

        request.status = "completed"
        request.completed_at = datetime.utcnow()

        logger.info(
            f"Erasure request {request_id} completed: "
            f"{request.items_deleted} deleted, {request.items_retained} retained"
        )

        return request

    # =========================================================================
    # Reporting
    # =========================================================================

    def generate_report(self, tenant_id: UUID | None = None) -> RetentionReport:
        """Generate a retention status report.

        Args:
            tenant_id: Optional tenant to filter by

        Returns:
            RetentionReport with current status
        """
        report = RetentionReport(
            report_id=uuid7(),
            tenant_id=tenant_id,
        )

        records = (
            self.get_records_by_tenant(tenant_id) if tenant_id else list(self._records.values())
        )

        now = datetime.utcnow()

        for record in records:
            # Count by status
            if record.status == RetentionStatus.ACTIVE:
                report.active_count += 1
            elif record.status == RetentionStatus.ARCHIVED:
                report.archived_count += 1
            elif record.status == RetentionStatus.EXPIRY_WARNING:
                report.expiry_warning_count += 1
            elif record.status == RetentionStatus.DELETION_PENDING:
                report.deletion_pending_count += 1
            elif record.status == RetentionStatus.LEGAL_HOLD:
                report.legal_hold_count += 1

            # Count by data type
            type_key = record.data_type.value
            report.counts_by_type[type_key] = report.counts_by_type.get(type_key, 0) + 1

            # Expiration windows
            if record.status not in (RetentionStatus.DELETED, RetentionStatus.ARCHIVED):
                days_to_expiry = (record.expires_at - now).days
                if 0 <= days_to_expiry <= 7:
                    report.expiring_next_7_days += 1
                if 0 <= days_to_expiry <= 30:
                    report.expiring_next_30_days += 1
                if 0 <= days_to_expiry <= 90:
                    report.expiring_next_90_days += 1

            # Compliance check
            if record.policy_id in self._policies:
                report.compliant_count += 1
            else:
                report.non_compliant_count += 1

        return report

    # =========================================================================
    # Background Processing
    # =========================================================================

    async def start(self) -> None:
        """Start background retention processing."""
        if self._running:
            return

        self._running = True
        self._check_task = asyncio.create_task(self._background_loop())
        logger.info("Retention manager started")

    async def stop(self) -> None:
        """Stop background retention processing."""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._check_task
            self._check_task = None
        logger.info("Retention manager stopped")

    async def _background_loop(self) -> None:
        """Background loop for checking retention status."""
        while self._running:
            try:
                await asyncio.sleep(self.config.check_interval_seconds)

                # Check for expiring data
                expiring = await self.check_expiring_data()
                if expiring:
                    logger.info(f"Found {len(expiring)} items approaching expiry")

                # Check for expired data
                expired = await self.check_expired_data()
                if expired and self.config.auto_delete:
                    for record in expired[: self.config.batch_size]:
                        await self.process_deletion(record)

                # Check for archive pending
                archive_pending = await self.check_archive_pending()
                if archive_pending and self.config.auto_archive:
                    for record in archive_pending[: self.config.batch_size]:
                        await self.process_archival(record)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in retention background loop: {e}")


# Module-level manager instance
_manager: RetentionManager | None = None


def get_retention_manager() -> RetentionManager:
    """Get the global retention manager instance.

    Returns:
        The RetentionManager instance
    """
    global _manager
    if _manager is None:
        _manager = RetentionManager()
    return _manager


def initialize_retention_manager(
    config: RetentionManagerConfig | None = None,
    delete_callback: DeletionCallback | None = None,
    archive_callback: ArchiveCallback | None = None,
    anonymize_callback: AnonymizeCallback | None = None,
) -> RetentionManager:
    """Initialize the global retention manager.

    Args:
        config: Manager configuration
        delete_callback: Async function to delete data
        archive_callback: Async function to archive data
        anonymize_callback: Async function to anonymize data

    Returns:
        The initialized RetentionManager
    """
    global _manager
    _manager = RetentionManager(
        config=config,
        delete_callback=delete_callback,
        archive_callback=archive_callback,
        anonymize_callback=anonymize_callback,
    )
    return _manager
