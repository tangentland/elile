"""API schemas for request/response validation."""

from .dashboard import (
    AlertSummary,
    HRAlertsListResponse,
    HRPortfolioResponse,
    HRScreeningsListResponse,
    PortfolioMetrics,
    RiskDistribution,
    RiskDistributionItem,
    RiskDistributionResponse,
    ScreeningSummary,
)
from .errors import APIError, ErrorCode
from .health import HealthDetailResponse, HealthResponse, HealthStatus
from .screening import (
    AddressInput,
    CostSummaryResponse,
    PhaseResultResponse,
    ReportResponse,
    ScreeningCancelResponse,
    ScreeningCreateRequest,
    ScreeningListResponse,
    ScreeningResponse,
    SubjectInput,
    screening_response_from_result,
)

__all__ = [
    # Error schemas
    "APIError",
    "ErrorCode",
    # Health schemas
    "HealthStatus",
    "HealthResponse",
    "HealthDetailResponse",
    # Screening schemas
    "AddressInput",
    "SubjectInput",
    "ScreeningCreateRequest",
    "ScreeningResponse",
    "ScreeningListResponse",
    "ScreeningCancelResponse",
    "PhaseResultResponse",
    "CostSummaryResponse",
    "ReportResponse",
    "screening_response_from_result",
    # Dashboard schemas
    "AlertSummary",
    "HRAlertsListResponse",
    "HRPortfolioResponse",
    "HRScreeningsListResponse",
    "PortfolioMetrics",
    "RiskDistribution",
    "RiskDistributionItem",
    "RiskDistributionResponse",
    "ScreeningSummary",
]
