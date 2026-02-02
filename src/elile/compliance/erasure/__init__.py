"""GDPR Erasure module for right to be forgotten requests.

This module provides comprehensive GDPR Article 17 "Right to Erasure"
functionality including:
- Erasure request management
- Identity verification
- Legal hold checking
- Data anonymization
- Confirmation report generation
- Full audit trail

Example Usage:
    ```python
    from elile.compliance.erasure import (
        ErasureService,
        ErasureType,
        LegalHoldException,
        get_erasure_service,
    )
    from elile.compliance.types import Locale

    # Get service instance
    service = get_erasure_service()

    # Submit erasure request
    operation = await service.submit_erasure_request(
        subject_id=subject_uuid,
        tenant_id=tenant_uuid,
        locale=Locale.EU,
        erasure_type=ErasureType.FULL_ERASURE,
        reason="GDPR Article 17 request",
    )

    # Verify identity
    operation = await service.verify_identity(
        operation.operation_id,
        verification_method="email_confirmation",
    )

    # Process erasure
    try:
        operation = await service.process_erasure_request(operation.operation_id)
    except LegalHoldException as e:
        print(f"Blocked by legal hold: {e.hold_reason}")

    # Generate confirmation report
    report = await service.generate_confirmation_report(operation.operation_id)
    ```
"""

from elile.compliance.erasure.anonymizer import (
    PII_FIELD_PATTERNS,
    AnonymizationConfig,
    AnonymizationResult,
    DataAnonymizer,
    create_anonymizer,
)
from elile.compliance.erasure.service import (
    DATA_TYPE_EXEMPTIONS,
    DEFAULT_DEADLINE_DAYS,
    GDPR_DEADLINE_DAYS,
    ErasureService,
    ErasureServiceConfig,
    get_erasure_service,
    initialize_erasure_service,
)
from elile.compliance.erasure.types import (
    AnonymizationMethod,
    AnonymizationRule,
    ErasedItem,
    ErasureBlockedException,
    ErasureConfirmationReport,
    ErasureExemption,
    ErasureOperation,
    ErasureStatus,
    ErasureType,
    ErasureVerificationError,
    LegalHoldException,
    RetainedItem,
)

__all__ = [
    # Service
    "ErasureService",
    "ErasureServiceConfig",
    "get_erasure_service",
    "initialize_erasure_service",
    # Types
    "ErasureType",
    "ErasureStatus",
    "ErasureExemption",
    "AnonymizationMethod",
    "AnonymizationRule",
    "ErasedItem",
    "RetainedItem",
    "ErasureOperation",
    "ErasureConfirmationReport",
    # Exceptions
    "LegalHoldException",
    "ErasureBlockedException",
    "ErasureVerificationError",
    # Anonymizer
    "DataAnonymizer",
    "AnonymizationConfig",
    "AnonymizationResult",
    "create_anonymizer",
    "PII_FIELD_PATTERNS",
    # Constants
    "DATA_TYPE_EXEMPTIONS",
    "GDPR_DEADLINE_DAYS",
    "DEFAULT_DEADLINE_DAYS",
]
