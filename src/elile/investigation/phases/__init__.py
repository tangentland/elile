"""Investigation phase handlers.

This package provides phase handlers for the investigation process:
- foundation: Foundation phase (identity, employment, education) - Task 5.11
- records: Records phase (criminal, civil, financial, licenses, regulatory, sanctions) - Task 5.12
- intelligence: Intelligence phase (adverse media, digital footprint) - Task 5.13
- network: Network phase (D2/D3 connections) - Task 5.14
- reconciliation: Reconciliation phase (cross-source conflict resolution) - Task 5.15
"""

from elile.investigation.phases.foundation import (
    BaselineProfile,
    EducationBaseline,
    EmploymentBaseline,
    FoundationConfig,
    FoundationPhaseHandler,
    FoundationPhaseResult,
    IdentityBaseline,
    VerificationStatus,
    create_foundation_phase_handler,
)
from elile.investigation.phases.records import (
    CivilRecord,
    CriminalRecord,
    FinancialRecord,
    LicenseRecord,
    RecordsConfig,
    RecordsPhaseHandler,
    RecordsPhaseResult,
    RecordsProfile,
    RecordSeverity,
    RecordType,
    RegulatoryRecord,
    SanctionsRecord,
    create_records_phase_handler,
)
from elile.investigation.phases.intelligence import (
    IntelligenceConfig,
    IntelligencePhaseHandler,
    IntelligencePhaseResult,
    IntelligenceProfile,
    MediaCategory,
    MediaMention,
    MediaSentiment,
    ProfessionalPresence,
    RiskIndicator,
    SocialPlatform,
    SocialProfile,
    create_intelligence_phase_handler,
)
from elile.investigation.phases.network import (
    ConnectionStrength,
    DiscoveredEntity,
    EntityRelation,
    EntityType,
    NetworkConfig,
    NetworkPhaseHandler,
    NetworkPhaseResult,
    NetworkProfile,
    RelationType,
    RiskConnection,
    RiskLevel,
    create_network_phase_handler,
)
from elile.investigation.phases.reconciliation import (
    ConflictResolution,
    DeceptionAnalysis,
    DeceptionRiskLevel,
    Inconsistency,
    InconsistencyType,
    ReconciliationConfig,
    ReconciliationPhaseHandler,
    ReconciliationPhaseResult,
    ReconciliationProfile,
    ResolutionStatus,
    create_reconciliation_phase_handler,
)

__all__ = [
    # Foundation phase (Task 5.11)
    "FoundationPhaseHandler",
    "create_foundation_phase_handler",
    "FoundationConfig",
    "FoundationPhaseResult",
    "BaselineProfile",
    "IdentityBaseline",
    "EmploymentBaseline",
    "EducationBaseline",
    "VerificationStatus",
    # Records phase (Task 5.12)
    "RecordsPhaseHandler",
    "create_records_phase_handler",
    "RecordsConfig",
    "RecordsPhaseResult",
    "RecordsProfile",
    "RecordType",
    "RecordSeverity",
    "CriminalRecord",
    "CivilRecord",
    "FinancialRecord",
    "LicenseRecord",
    "RegulatoryRecord",
    "SanctionsRecord",
    # Intelligence phase (Task 5.13)
    "IntelligencePhaseHandler",
    "create_intelligence_phase_handler",
    "IntelligenceConfig",
    "IntelligencePhaseResult",
    "IntelligenceProfile",
    "MediaMention",
    "MediaCategory",
    "MediaSentiment",
    "SocialProfile",
    "SocialPlatform",
    "ProfessionalPresence",
    "RiskIndicator",
    # Network phase (Task 5.14)
    "NetworkPhaseHandler",
    "create_network_phase_handler",
    "NetworkConfig",
    "NetworkPhaseResult",
    "NetworkProfile",
    "DiscoveredEntity",
    "EntityRelation",
    "RiskConnection",
    "EntityType",
    "RelationType",
    "RiskLevel",
    "ConnectionStrength",
    # Reconciliation phase (Task 5.15)
    "ReconciliationPhaseHandler",
    "create_reconciliation_phase_handler",
    "ReconciliationConfig",
    "ReconciliationPhaseResult",
    "ReconciliationProfile",
    "Inconsistency",
    "InconsistencyType",
    "ConflictResolution",
    "ResolutionStatus",
    "DeceptionAnalysis",
    "DeceptionRiskLevel",
]
