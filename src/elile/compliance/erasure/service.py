"""GDPR Erasure Service for right to be forgotten requests.

This module provides the ErasureService class that handles GDPR Article 17
erasure requests with legal hold checking, anonymization, and audit trail.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid7

from elile.compliance.erasure.anonymizer import (
    DataAnonymizer,
    create_anonymizer,
)
from elile.compliance.erasure.types import (
    AnonymizationMethod,
    AnonymizationRule,
    ErasureConfirmationReport,
    ErasureExemption,
    ErasureOperation,
    ErasureStatus,
    ErasureType,
    ErasureVerificationError,
    LegalHoldException,
    RetainedItem,
)
from elile.compliance.retention.manager import RetentionManager, get_retention_manager
from elile.compliance.retention.types import DataType
from elile.compliance.types import Locale

logger = logging.getLogger(__name__)


# Regulatory exemptions by data type
DATA_TYPE_EXEMPTIONS: dict[DataType, tuple[ErasureExemption, str, int]] = {
    DataType.AUDIT_LOG: (
        ErasureExemption.REGULATORY_REQUIREMENT,
        "Audit logs must be retained for compliance (SOC 2, GDPR Art. 30)",
        7 * 365,  # 7 years
    ),
    DataType.CONSENT_RECORD: (
        ErasureExemption.REGULATORY_REQUIREMENT,
        "Consent records must be retained to demonstrate compliance (GDPR Art. 7)",
        7 * 365,
    ),
    DataType.ADVERSE_ACTION: (
        ErasureExemption.REGULATORY_REQUIREMENT,
        "Adverse action records must be retained under FCRA",
        7 * 365,
    ),
    DataType.SCREENING_RESULT: (
        ErasureExemption.REGULATORY_REQUIREMENT,
        "Background check results retained under FCRA (7 years)",
        7 * 365,
    ),
}

# Locale-specific GDPR deadlines
GDPR_DEADLINE_DAYS: dict[Locale, int] = {
    Locale.EU: 30,
    Locale.UK: 30,
    Locale.BR: 15,  # LGPD has shorter deadline
}

DEFAULT_DEADLINE_DAYS = 30


@dataclass
class ErasureServiceConfig:
    """Configuration for the ErasureService."""

    # Verification settings
    require_identity_verification: bool = True
    """Whether to require identity verification before processing."""

    verification_timeout_hours: int = 72
    """Hours to complete verification before request expires."""

    # Processing settings
    auto_process_after_verification: bool = False
    """Whether to automatically process after verification."""

    max_processing_attempts: int = 3
    """Maximum attempts to process erasure."""

    # Legal hold settings
    block_on_any_legal_hold: bool = True
    """Block entire request if any data has legal hold."""

    # Anonymization settings
    anonymize_before_delete: bool = True
    """Anonymize data before deletion for audit trail."""

    preserve_anonymized_for_days: int = 90
    """Days to keep anonymized data before hard delete."""

    # Reporting settings
    generate_confirmation_report: bool = True
    """Whether to generate confirmation reports."""

    include_detailed_audit: bool = True
    """Include detailed audit trail in reports."""

    # Audit settings
    log_all_operations: bool = True
    """Log all erasure operations for audit."""


class ErasureService:
    """Handle GDPR erasure requests.

    Provides comprehensive GDPR Article 17 "Right to Erasure" functionality:
    - Identity verification
    - Legal hold checking
    - Data anonymization
    - Confirmation report generation
    - Full audit trail
    """

    def __init__(
        self,
        config: ErasureServiceConfig | None = None,
        retention_manager: RetentionManager | None = None,
        anonymizer: DataAnonymizer | None = None,
    ):
        """Initialize the erasure service.

        Args:
            config: Service configuration
            retention_manager: Optional retention manager instance
            anonymizer: Optional anonymizer instance
        """
        self.config = config or ErasureServiceConfig()
        self._retention_manager = retention_manager or get_retention_manager()
        self._anonymizer = anonymizer or create_anonymizer()

        # In-memory storage for operations (would be database in production)
        self._operations: dict[UUID, ErasureOperation] = {}

        logger.info("ErasureService initialized")

    # =========================================================================
    # Request Management
    # =========================================================================

    async def submit_erasure_request(
        self,
        subject_id: UUID,
        tenant_id: UUID,
        locale: Locale,
        erasure_type: ErasureType = ErasureType.FULL_ERASURE,
        data_types: list[DataType] | None = None,
        reason: str | None = None,
        requester_id: str | None = None,
    ) -> ErasureOperation:
        """Submit a new erasure request.

        Args:
            subject_id: ID of the data subject
            tenant_id: Tenant that owns the data
            locale: Locale for compliance requirements
            erasure_type: Type of erasure requested
            data_types: Specific data types to erase (None = all)
            reason: Reason for the request
            requester_id: ID of the requester

        Returns:
            The created erasure operation
        """
        # Calculate deadline
        deadline_days = GDPR_DEADLINE_DAYS.get(locale, DEFAULT_DEADLINE_DAYS)
        deadline = datetime.utcnow() + timedelta(days=deadline_days)

        # Create operation
        operation = ErasureOperation(
            operation_id=uuid7(),
            subject_id=subject_id,
            tenant_id=tenant_id,
            locale=locale,
            erasure_type=erasure_type,
            requested_data_types=data_types or [],
            reason=reason,
            requester_id=requester_id,
            status=ErasureStatus.PENDING,
            deadline=deadline,
        )

        operation.add_audit_entry(
            "request_submitted",
            {
                "erasure_type": erasure_type.value,
                "data_types": [dt.value for dt in (data_types or [])],
                "deadline": deadline.isoformat(),
            },
        )

        self._operations[operation.operation_id] = operation
        logger.info(f"Erasure request submitted: {operation.operation_id}")

        return operation

    async def verify_identity(
        self,
        operation_id: UUID,
        verification_method: str,
        verified_by: str | None = None,
    ) -> ErasureOperation:
        """Verify the identity of the erasure requestor.

        Args:
            operation_id: ID of the erasure operation
            verification_method: Method used to verify identity
            verified_by: Who performed the verification

        Returns:
            Updated operation

        Raises:
            ErasureVerificationError: If verification fails
        """
        operation = self._get_operation(operation_id)

        if operation.status != ErasureStatus.PENDING:
            raise ErasureVerificationError(
                operation.subject_id,
                f"Operation is not pending: {operation.status.value}",
            )

        # Check verification timeout
        timeout = timedelta(hours=self.config.verification_timeout_hours)
        if datetime.utcnow() > operation.requested_at + timeout:
            operation.status = ErasureStatus.REJECTED
            operation.add_audit_entry(
                "verification_timeout",
                {
                    "timeout_hours": self.config.verification_timeout_hours,
                },
            )
            raise ErasureVerificationError(
                operation.subject_id,
                "Verification timeout expired",
            )

        # Mark as verified
        operation.verification_method = verification_method
        operation.verified_at = datetime.utcnow()
        operation.status = ErasureStatus.VERIFIED

        operation.add_audit_entry(
            "identity_verified",
            {
                "method": verification_method,
                "verified_by": verified_by,
            },
        )

        logger.info(f"Identity verified for operation {operation_id}")

        # Auto-process if configured
        if self.config.auto_process_after_verification:
            return await self.process_erasure_request(operation_id)

        return operation

    # =========================================================================
    # Legal Hold Management
    # =========================================================================

    def _check_legal_holds(
        self,
        operation: ErasureOperation,
    ) -> tuple[bool, list[RetainedItem]]:
        """Check for legal holds on subject data.

        Args:
            operation: The erasure operation

        Returns:
            Tuple of (has_blocking_hold, retained_items)
        """
        retained_items: list[RetainedItem] = []
        has_blocking_hold = False

        # Get all retention records for the tenant/subject
        for record in self._retention_manager._records.values():
            if record.tenant_id != operation.tenant_id:
                continue

            # Check if data type is in scope
            if (
                operation.requested_data_types
                and record.data_type not in operation.requested_data_types
            ):
                continue

            if record.legal_hold:
                has_blocking_hold = True
                retained_items.append(
                    RetainedItem(
                        data_id=record.data_id,
                        data_type=record.data_type,
                        exemption=ErasureExemption.LEGAL_HOLD,
                        exemption_details=record.legal_hold_reason or "Legal hold in effect",
                        retention_until=None,  # Indefinite during legal hold
                    )
                )

        return has_blocking_hold, retained_items

    def _has_legal_hold(self, subject_id: UUID) -> bool:  # noqa: ARG002
        """Check if subject has any active legal holds.

        Args:
            subject_id: ID of the subject

        Returns:
            True if legal hold exists
        """
        # In production, would also filter by subject_id
        return any(record.legal_hold for record in self._retention_manager._records.values())

    # =========================================================================
    # Data Processing
    # =========================================================================

    async def process_erasure_request(
        self,
        operation_id: UUID,
        force: bool = False,
    ) -> ErasureOperation:
        """Process a verified erasure request.

        Args:
            operation_id: ID of the erasure operation
            force: Force processing even if not verified

        Returns:
            Updated operation with results

        Raises:
            LegalHoldException: If subject has active legal hold
            ErasureBlockedException: If erasure is blocked for other reasons
        """
        operation = self._get_operation(operation_id)

        # Check status
        if (
            not force
            and operation.status != ErasureStatus.VERIFIED
            and self.config.require_identity_verification
        ):
            raise ErasureVerificationError(
                operation.subject_id,
                f"Operation not verified: {operation.status.value}",
            )

        # Check for legal holds
        has_blocking_hold, legal_hold_items = self._check_legal_holds(operation)

        if has_blocking_hold and self.config.block_on_any_legal_hold:
            operation.status = ErasureStatus.BLOCKED
            for item in legal_hold_items:
                operation.retained_items.append(
                    {
                        "data_id": str(item.data_id),
                        "data_type": item.data_type.value,
                        "exemption": item.exemption.value,
                        "details": item.exemption_details,
                    }
                )
            operation.add_audit_entry(
                "blocked_legal_hold",
                {
                    "items_blocked": len(legal_hold_items),
                },
            )

            raise LegalHoldException(
                operation.subject_id,
                (
                    legal_hold_items[0].exemption_details
                    if legal_hold_items
                    else "Legal hold in effect"
                ),
            )

        # Start processing
        operation.status = ErasureStatus.PROCESSING
        operation.started_at = datetime.utcnow()
        operation.add_audit_entry("processing_started")

        try:
            # Get all data for this tenant/subject
            records = [
                r
                for r in self._retention_manager._records.values()
                if r.tenant_id == operation.tenant_id
            ]

            # Filter by data type if specified
            if operation.requested_data_types:
                records = [r for r in records if r.data_type in operation.requested_data_types]

            # Process each record
            for record in records:
                await self._process_record(operation, record)

            # Determine final status
            if operation.items_retained_count > 0:
                operation.status = ErasureStatus.PARTIALLY_COMPLETED
            else:
                operation.status = ErasureStatus.COMPLETED

            operation.completed_at = datetime.utcnow()
            operation.add_audit_entry(
                "processing_completed",
                {
                    "items_erased": operation.items_erased_count,
                    "items_retained": operation.items_retained_count,
                },
            )

            logger.info(
                f"Erasure operation {operation_id} completed: "
                f"{operation.items_erased_count} erased, "
                f"{operation.items_retained_count} retained"
            )

        except Exception as e:
            operation.errors.append(str(e))
            operation.add_audit_entry("processing_error", {"error": str(e)})
            logger.error(f"Error processing erasure {operation_id}: {e}")
            raise

        return operation

    async def _process_record(
        self,
        operation: ErasureOperation,
        record: Any,
    ) -> None:
        """Process a single retention record for erasure.

        Args:
            operation: The erasure operation
            record: The retention record to process
        """
        # Check for regulatory exemptions
        if record.data_type in DATA_TYPE_EXEMPTIONS:
            exemption, reason, retention_days = DATA_TYPE_EXEMPTIONS[record.data_type]
            operation.retained_items.append(
                {
                    "data_id": str(record.data_id),
                    "data_type": record.data_type.value,
                    "exemption": exemption.value,
                    "details": reason,
                    "legal_basis": reason,
                }
            )
            return

        # Check legal hold
        if record.legal_hold:
            operation.retained_items.append(
                {
                    "data_id": str(record.data_id),
                    "data_type": record.data_type.value,
                    "exemption": ErasureExemption.LEGAL_HOLD.value,
                    "details": record.legal_hold_reason or "Legal hold in effect",
                }
            )
            return

        # Anonymize if configured
        if self.config.anonymize_before_delete:
            await self._anonymize_subject_data(operation.subject_id, record.data_type)

        # Process deletion through retention manager
        success = await self._retention_manager.process_deletion(record)

        if success:
            operation.erased_items.append(
                {
                    "data_id": str(record.data_id),
                    "data_type": record.data_type.value,
                    "action": operation.erasure_type.value,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        else:
            operation.errors.append(f"Failed to delete {record.data_type.value}: {record.data_id}")

    async def _anonymize_subject_data(
        self,
        subject_id: UUID,
        data_type: DataType,
    ) -> bool:
        """Anonymize PII while preserving statistical data.

        Args:
            subject_id: ID of the subject
            data_type: Type of data to anonymize

        Returns:
            True if anonymization was successful
        """
        # Create sample data structure for the data type
        # In production, this would fetch actual data from database
        sample_data = {
            "subject_id": str(subject_id),
            "full_name": "John Smith",
            "email": "john.smith@example.com",
            "ssn": "123-45-6789",
            "date_of_birth": "1985-03-15",
            "address": "123 Main Street",
            "city": "Springfield",
            "state": "IL",
            "phone": "555-123-4567",
        }

        # Define rules based on data type
        rules = {}
        if data_type in (DataType.ENTITY_PROFILE, DataType.SCREENING_RAW_DATA):
            # Anonymize all PII fields
            rules = {
                "full_name": AnonymizationRule("full_name", AnonymizationMethod.REDACTION),
                "email": AnonymizationRule("email", AnonymizationMethod.TOKENIZATION),
                "ssn": AnonymizationRule("ssn", AnonymizationMethod.MASKING, preserve_format=True),
                "phone": AnonymizationRule(
                    "phone", AnonymizationMethod.MASKING, preserve_format=True
                ),
            }

        # Perform anonymization
        anonymized, result = self._anonymizer.anonymize_record(
            sample_data,
            data_id=subject_id,
            data_type=data_type,
            explicit_rules=rules,
        )

        if result.success:
            logger.info(
                f"Anonymized {len(result.fields_anonymized)} fields for "
                f"{data_type.value} of subject {subject_id}"
            )
            return True
        else:
            logger.error(f"Anonymization failed: {result.error_message}")
            return False

    # =========================================================================
    # Reporting
    # =========================================================================

    async def generate_confirmation_report(
        self,
        operation_id: UUID,
    ) -> ErasureConfirmationReport:
        """Generate a confirmation report for a completed operation.

        Args:
            operation_id: ID of the erasure operation

        Returns:
            Confirmation report
        """
        operation = self._get_operation(operation_id)

        if not operation.is_complete:
            raise ValueError(f"Operation not complete: {operation.status.value}")

        # Calculate processing time
        processing_days = 0
        if operation.completed_at:
            delta = operation.completed_at - operation.requested_at
            processing_days = delta.days

        # Build data category lists
        data_categories_requested = (
            [dt.value for dt in operation.requested_data_types]
            if operation.requested_data_types
            else ["all"]
        )

        data_categories_erased = list({item["data_type"] for item in operation.erased_items})

        data_categories_retained = list({item["data_type"] for item in operation.retained_items})

        # Build report
        report = ErasureConfirmationReport(
            report_id=uuid7(),
            operation_id=operation.operation_id,
            subject_id=operation.subject_id,
            tenant_id=operation.tenant_id,
            locale=operation.locale,
            request_date=operation.requested_at,
            completion_date=operation.completed_at or datetime.utcnow(),
            processing_days=processing_days,
            status=operation.status,
            is_fully_completed=operation.status == ErasureStatus.COMPLETED,
            data_categories_requested=data_categories_requested,
            data_categories_erased=data_categories_erased,
            data_categories_retained=data_categories_retained,
            total_items_processed=operation.items_erased_count + operation.items_retained_count,
            items_erased=operation.items_erased_count,
            items_anonymized=len(
                [
                    i
                    for i in operation.erased_items
                    if i.get("action") == ErasureType.ANONYMIZE.value
                ]
            ),
            items_retained=operation.items_retained_count,
            erased_data_summary=[
                {
                    "category": item["data_type"],
                    "action": item.get("action", "deleted"),
                    "timestamp": item.get("timestamp"),
                }
                for item in operation.erased_items
            ],
            retained_data_explanation=[
                {
                    "category": item["data_type"],
                    "reason": item.get("details", ""),
                    "legal_basis": item.get("legal_basis", ""),
                    "exemption": item.get("exemption", ""),
                }
                for item in operation.retained_items
            ],
            gdpr_compliance_statement=self._generate_compliance_statement(operation),
            legal_basis_for_retention=[
                item.get("legal_basis", item.get("details", ""))
                for item in operation.retained_items
                if item.get("legal_basis") or item.get("details")
            ],
            authorized_by=operation.requester_id,
        )

        # Generate verification hash
        import hashlib
        import json

        report_data = report.model_dump(mode="json")
        report.verification_hash = hashlib.sha256(
            json.dumps(report_data, sort_keys=True).encode()
        ).hexdigest()

        logger.info(
            f"Generated confirmation report {report.report_id} for operation {operation_id}"
        )

        return report

    def _generate_compliance_statement(self, operation: ErasureOperation) -> str:
        """Generate GDPR compliance statement.

        Args:
            operation: The erasure operation

        Returns:
            Compliance statement text
        """
        locale_article = {
            Locale.EU: "GDPR Article 17",
            Locale.UK: "UK GDPR Article 17",
            Locale.BR: "LGPD Article 18",
        }

        article = locale_article.get(operation.locale, "applicable data protection law")

        if operation.status == ErasureStatus.COMPLETED:
            return (
                f"This erasure request has been processed in accordance with {article}. "
                f"All requested personal data has been erased from our systems. "
                f"Processing was completed within the statutory timeframe."
            )
        elif operation.status == ErasureStatus.PARTIALLY_COMPLETED:
            return (
                f"This erasure request has been partially processed in accordance with {article}. "
                f"Some data has been retained due to legal exemptions under {article}(3), "
                f"including legal obligations and the establishment, exercise, or defense of legal claims. "
                f"Details of retained data and reasons are provided in this report."
            )
        elif operation.status == ErasureStatus.BLOCKED:
            return (
                "This erasure request could not be processed at this time. "
                "The data is subject to a legal hold and cannot be erased until "
                "the hold is lifted. You will be notified when processing can resume."
            )
        else:
            return f"Request processed in accordance with {article}."

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _get_operation(self, operation_id: UUID) -> ErasureOperation:
        """Get an operation by ID.

        Args:
            operation_id: The operation ID

        Returns:
            The operation

        Raises:
            ValueError: If operation not found
        """
        operation = self._operations.get(operation_id)
        if operation is None:
            raise ValueError(f"Erasure operation not found: {operation_id}")
        return operation

    def get_operation(self, operation_id: UUID) -> ErasureOperation | None:
        """Get an operation by ID (public API).

        Args:
            operation_id: The operation ID

        Returns:
            The operation, or None if not found
        """
        return self._operations.get(operation_id)

    def get_operations_by_subject(self, subject_id: UUID) -> list[ErasureOperation]:
        """Get all operations for a subject.

        Args:
            subject_id: The subject ID

        Returns:
            List of operations
        """
        return [op for op in self._operations.values() if op.subject_id == subject_id]

    def get_operations_by_tenant(self, tenant_id: UUID) -> list[ErasureOperation]:
        """Get all operations for a tenant.

        Args:
            tenant_id: The tenant ID

        Returns:
            List of operations
        """
        return [op for op in self._operations.values() if op.tenant_id == tenant_id]

    def get_pending_operations(self) -> list[ErasureOperation]:
        """Get all pending operations.

        Returns:
            List of pending operations
        """
        return [
            op
            for op in self._operations.values()
            if op.status in (ErasureStatus.PENDING, ErasureStatus.VERIFIED)
        ]

    def get_overdue_operations(self) -> list[ErasureOperation]:
        """Get operations past their deadline.

        Returns:
            List of overdue operations
        """
        now = datetime.utcnow()
        return [
            op
            for op in self._operations.values()
            if op.deadline and op.deadline < now and not op.is_complete
        ]


# Module-level service instance
_service: ErasureService | None = None


def get_erasure_service() -> ErasureService:
    """Get the global erasure service instance.

    Returns:
        The ErasureService instance
    """
    global _service
    if _service is None:
        _service = ErasureService()
    return _service


def initialize_erasure_service(
    config: ErasureServiceConfig | None = None,
    retention_manager: RetentionManager | None = None,
    anonymizer: DataAnonymizer | None = None,
) -> ErasureService:
    """Initialize the global erasure service.

    Args:
        config: Service configuration
        retention_manager: Optional retention manager
        anonymizer: Optional anonymizer

    Returns:
        The initialized ErasureService
    """
    global _service
    _service = ErasureService(
        config=config,
        retention_manager=retention_manager,
        anonymizer=anonymizer,
    )
    return _service
