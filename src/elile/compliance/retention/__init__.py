"""Data retention framework for compliance.

This package provides automated data retention management:
- Locale-aware retention policies
- Archival and deletion workflows
- GDPR erasure request processing
- Compliance reporting

Usage:
    from elile.compliance.retention import (
        RetentionManager,
        RetentionPolicy,
        DataType,
        get_retention_manager,
    )

    manager = get_retention_manager()

    # Track data retention
    record = manager.track_data(
        data_id=some_uuid,
        data_type=DataType.SCREENING_RESULT,
        tenant_id=tenant_uuid,
        locale=Locale.US,
    )

    # Place legal hold
    manager.place_legal_hold(some_uuid, "Litigation hold - Case #123")

    # Submit erasure request
    request = await manager.submit_erasure_request(
        subject_id=subject_uuid,
        tenant_id=tenant_uuid,
        locale=Locale.EU,
        reason="GDPR Article 17 request",
    )

    # Generate compliance report
    report = manager.generate_report(tenant_id=tenant_uuid)
"""

from elile.compliance.retention.manager import (
    RetentionManager,
    RetentionManagerConfig,
    get_retention_manager,
    initialize_retention_manager,
)
from elile.compliance.retention.policies import (
    get_default_policies,
    get_policies_for_locale,
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

__all__ = [
    # Types
    "DataType",
    "DeletionMethod",
    "RetentionAction",
    "RetentionStatus",
    # Models
    "RetentionPolicy",
    "RetentionRecord",
    "RetentionReport",
    "ErasureRequest",
    # Manager
    "RetentionManager",
    "RetentionManagerConfig",
    "get_retention_manager",
    "initialize_retention_manager",
    # Policy utilities
    "get_default_policies",
    "get_policies_for_locale",
    "get_policy_for_data_type",
]
