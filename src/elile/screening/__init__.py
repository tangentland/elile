"""Screening service for end-to-end background screening workflow.

This package provides the screening orchestration layer that coordinates
all phases of a background screening investigation:

1. Request validation
2. Compliance checking
3. Consent verification
4. Investigation (SAR loop)
5. Risk analysis
6. Report generation

Usage:
    from elile.screening import (
        ScreeningOrchestrator,
        ScreeningRequest,
        ScreeningResult,
        ScreeningStatus,
    )

    # Create request
    request = ScreeningRequest(
        tenant_id=tenant_id,
        subject=SubjectIdentifiers(name="John Smith"),
        locale=Locale.US,
        consent_token="consent-abc123",
    )

    # Execute screening
    orchestrator = ScreeningOrchestrator()
    result = await orchestrator.execute_screening(request)

    if result.status == ScreeningStatus.COMPLETE:
        print(f"Risk score: {result.risk_score}")
"""

from elile.screening.types import (
    GeneratedReport,
    ReportType,
    ScreeningComplianceError,
    ScreeningCostSummary,
    ScreeningError,
    ScreeningExecutionError,
    ScreeningPhaseResult,
    ScreeningPriority,
    ScreeningRequest,
    ScreeningRequestCreate,
    ScreeningResult,
    ScreeningStatus,
    ScreeningValidationError,
)
from elile.screening.orchestrator import (
    OrchestratorConfig,
    ScreeningOrchestrator,
    create_screening_orchestrator,
)
from elile.screening.degree_handlers import (
    D1Handler,
    D1Result,
    D2Handler,
    D2Result,
    D3Handler,
    D3Result,
    DegreeHandlerConfig,
    create_d1_handler,
    create_d2_handler,
    create_d3_handler,
)
from elile.screening.tier_router import (
    DataSourceSpec,
    DataSourceTier,
    TierCapabilities,
    TierRouter,
    TierRouterConfig,
    RoutingResult,
    create_tier_router,
    create_default_data_sources,
)

__all__ = [
    # Orchestrator
    "ScreeningOrchestrator",
    "create_screening_orchestrator",
    "OrchestratorConfig",
    # Degree Handlers
    "D1Handler",
    "D1Result",
    "D2Handler",
    "D2Result",
    "D3Handler",
    "D3Result",
    "DegreeHandlerConfig",
    "create_d1_handler",
    "create_d2_handler",
    "create_d3_handler",
    # Tier Router
    "TierRouter",
    "TierRouterConfig",
    "TierCapabilities",
    "DataSourceSpec",
    "DataSourceTier",
    "RoutingResult",
    "create_tier_router",
    "create_default_data_sources",
    # Request/Response models
    "ScreeningRequest",
    "ScreeningRequestCreate",
    "ScreeningResult",
    "ScreeningPhaseResult",
    "ScreeningCostSummary",
    "GeneratedReport",
    # Enums
    "ScreeningStatus",
    "ReportType",
    "ScreeningPriority",
    # Errors
    "ScreeningError",
    "ScreeningValidationError",
    "ScreeningComplianceError",
    "ScreeningExecutionError",
]
