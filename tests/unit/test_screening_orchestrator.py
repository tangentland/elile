"""Tests for the Screening Orchestrator.

Tests cover:
- Screening request validation
- Compliance checking
- Consent verification
- Investigation execution
- Risk analysis
- Report generation
- Error handling
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid7

import pytest

from elile.agent.state import SearchDegree, ServiceTier, VigilanceLevel
from elile.compliance.types import Locale, RoleCategory
from elile.entity.types import SubjectIdentifiers
from elile.investigation import InvestigationResult, TypeCycleResult
from elile.investigation.finding_extractor import Finding, FindingCategory, Severity
from elile.risk import ComprehensiveRiskAssessment, RiskLevel
from elile.risk.risk_scorer import Recommendation
from elile.screening import (
    GeneratedReport,
    OrchestratorConfig,
    ReportType,
    ScreeningComplianceError,
    ScreeningCostSummary,
    ScreeningExecutionError,
    ScreeningOrchestrator,
    ScreeningPhaseResult,
    ScreeningPriority,
    ScreeningRequest,
    ScreeningRequestCreate,
    ScreeningResult,
    ScreeningStatus,
    ScreeningValidationError,
    create_screening_orchestrator,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_subject() -> SubjectIdentifiers:
    """Create sample subject identifiers."""
    return SubjectIdentifiers(
        full_name="John Smith",
        date_of_birth="1985-06-15",
        ssn="123-45-6789",
    )


@pytest.fixture
def sample_request(sample_subject: SubjectIdentifiers) -> ScreeningRequest:
    """Create sample screening request."""
    return ScreeningRequest(
        tenant_id=uuid7(),
        subject=sample_subject,
        locale=Locale.US,
        service_tier=ServiceTier.STANDARD,
        search_degree=SearchDegree.D1,
        consent_token="valid-consent-token-123",
        report_types=[ReportType.SUMMARY],
    )


@pytest.fixture
def enhanced_request(sample_subject: SubjectIdentifiers) -> ScreeningRequest:
    """Create enhanced tier screening request."""
    return ScreeningRequest(
        tenant_id=uuid7(),
        subject=sample_subject,
        locale=Locale.US,
        service_tier=ServiceTier.ENHANCED,
        search_degree=SearchDegree.D3,
        consent_token="valid-consent-token-123",
        report_types=[ReportType.SUMMARY, ReportType.CASE_FILE],
    )


@pytest.fixture
def mock_investigation_result() -> InvestigationResult:
    """Create mock investigation result."""
    findings = [
        Finding(
            summary="Employment verified",
            details="Employment at ABC Corp verified for 2020-2023",
            category=FindingCategory.VERIFICATION,
            severity=Severity.LOW,
        ),
        Finding(
            summary="Education verified",
            details="Bachelor's degree from State University verified",
            category=FindingCategory.VERIFICATION,
            severity=Severity.LOW,
        ),
    ]

    result = InvestigationResult(
        investigation_id=uuid7(),
        total_queries=15,
    )
    # Set findings as attribute (mock)
    result.all_findings = findings
    result.type_results = {}

    return result


@pytest.fixture
def mock_risk_assessment() -> ComprehensiveRiskAssessment:
    """Create mock risk assessment."""
    return ComprehensiveRiskAssessment(
        final_score=25,
        base_score=20,
        risk_level=RiskLevel.LOW,
        recommendation=Recommendation.PROCEED,
        recommendation_reasons=["No significant findings"],
    )


@pytest.fixture
def mock_orchestrator() -> ScreeningOrchestrator:
    """Create orchestrator with mocked dependencies."""
    orchestrator = ScreeningOrchestrator()

    # Mock compliance engine
    mock_compliance = MagicMock()
    mock_compliance.get_permitted_checks.return_value = ["CRIMINAL_NATIONAL", "EMPLOYMENT"]
    mock_compliance.get_blocked_checks.return_value = []
    orchestrator._compliance_engine = mock_compliance

    # Mock consent manager
    mock_consent = MagicMock()
    orchestrator._consent_manager = mock_consent

    return orchestrator


# =============================================================================
# Screening Request Tests
# =============================================================================


class TestScreeningRequest:
    """Tests for ScreeningRequest model."""

    def test_create_basic_request(self, sample_subject: SubjectIdentifiers) -> None:
        """Test creating a basic screening request."""
        request = ScreeningRequest(
            tenant_id=uuid7(),
            subject=sample_subject,
            locale=Locale.US,
            consent_token="test-token",
        )

        assert request.screening_id is not None
        assert request.service_tier == ServiceTier.STANDARD
        assert request.search_degree == SearchDegree.D1
        assert request.vigilance_level == VigilanceLevel.V0
        assert request.priority == ScreeningPriority.NORMAL

    def test_d3_requires_enhanced_tier(self, sample_subject: SubjectIdentifiers) -> None:
        """Test that D3 degree requires Enhanced tier."""
        with pytest.raises(ValueError, match="D3 search degree requires Enhanced"):
            ScreeningRequest(
                tenant_id=uuid7(),
                subject=sample_subject,
                locale=Locale.US,
                service_tier=ServiceTier.STANDARD,
                search_degree=SearchDegree.D3,
                consent_token="test-token",
            )

    def test_d3_with_enhanced_tier_valid(self, sample_subject: SubjectIdentifiers) -> None:
        """Test that D3 with Enhanced tier is valid."""
        request = ScreeningRequest(
            tenant_id=uuid7(),
            subject=sample_subject,
            locale=Locale.US,
            service_tier=ServiceTier.ENHANCED,
            search_degree=SearchDegree.D3,
            consent_token="test-token",
        )

        assert request.search_degree == SearchDegree.D3
        assert request.service_tier == ServiceTier.ENHANCED

    def test_request_create_to_request(self, sample_subject: SubjectIdentifiers) -> None:
        """Test converting ScreeningRequestCreate to ScreeningRequest."""
        create = ScreeningRequestCreate(
            tenant_id=uuid7(),
            subject=sample_subject,
            locale=Locale.US,
            consent_token="test-token",
        )

        request = create.to_screening_request()

        assert request.tenant_id == create.tenant_id
        assert request.subject == create.subject
        assert request.screening_id is not None


class TestScreeningResult:
    """Tests for ScreeningResult model."""

    def test_create_result(self) -> None:
        """Test creating a screening result."""
        result = ScreeningResult(
            screening_id=uuid7(),
            tenant_id=uuid7(),
        )

        assert result.status == ScreeningStatus.PENDING
        assert result.risk_score == 0
        assert len(result.phases) == 0
        assert len(result.reports) == 0

    def test_add_phase(self) -> None:
        """Test adding phases to result."""
        result = ScreeningResult()
        phase = result.add_phase("validation")

        assert len(result.phases) == 1
        assert phase.phase_name == "validation"
        assert phase.status == "pending"

    def test_get_phase(self) -> None:
        """Test getting phase by name."""
        result = ScreeningResult()
        result.add_phase("validation")
        result.add_phase("investigation")

        phase = result.get_phase("investigation")
        assert phase is not None
        assert phase.phase_name == "investigation"

        missing = result.get_phase("nonexistent")
        assert missing is None

    def test_duration_calculation(self) -> None:
        """Test duration calculation."""
        result = ScreeningResult()
        result.started_at = datetime.now(UTC)

        # Not complete yet
        assert result.duration_seconds is None

        # Complete
        result.completed_at = datetime.now(UTC)
        assert result.duration_seconds is not None
        assert result.duration_seconds >= 0

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        result = ScreeningResult(
            screening_id=uuid7(),
            tenant_id=uuid7(),
            status=ScreeningStatus.COMPLETE,
            risk_score=45,
            risk_level="moderate",
        )

        d = result.to_dict()

        assert d["status"] == "complete"
        assert d["risk_score"] == 45
        assert d["risk_level"] == "moderate"


class TestScreeningPhaseResult:
    """Tests for ScreeningPhaseResult."""

    def test_create_phase(self) -> None:
        """Test creating a phase result."""
        phase = ScreeningPhaseResult(phase_name="test_phase")

        assert phase.phase_name == "test_phase"
        assert phase.status == "pending"
        assert phase.completed_at is None

    def test_complete_phase(self) -> None:
        """Test completing a phase."""
        phase = ScreeningPhaseResult(phase_name="test_phase")
        phase.complete("complete")

        assert phase.status == "complete"
        assert phase.completed_at is not None
        assert phase.duration_seconds is not None

    def test_complete_phase_with_error(self) -> None:
        """Test completing a phase with error."""
        phase = ScreeningPhaseResult(phase_name="test_phase")
        phase.complete("failed", "Something went wrong")

        assert phase.status == "failed"
        assert phase.error_message == "Something went wrong"


# =============================================================================
# Orchestrator Tests
# =============================================================================


class TestScreeningOrchestrator:
    """Tests for ScreeningOrchestrator."""

    def test_create_orchestrator(self) -> None:
        """Test creating orchestrator with defaults."""
        orchestrator = create_screening_orchestrator()

        assert orchestrator is not None
        assert orchestrator.config.validate_consent is True
        assert orchestrator.config.validate_compliance is True

    def test_create_orchestrator_with_config(self) -> None:
        """Test creating orchestrator with custom config."""
        config = OrchestratorConfig(
            validate_consent=False,
            parallel_investigation=False,
        )
        orchestrator = create_screening_orchestrator(config=config)

        assert orchestrator.config.validate_consent is False
        assert orchestrator.config.parallel_investigation is False


class TestRequestValidation:
    """Tests for request validation."""

    @pytest.mark.asyncio
    async def test_validate_missing_name(
        self, mock_orchestrator: ScreeningOrchestrator
    ) -> None:
        """Test validation fails when name is missing."""
        request = ScreeningRequest(
            tenant_id=uuid7(),
            subject=SubjectIdentifiers(full_name=""),  # Empty name
            locale=Locale.US,
            consent_token="test-token",
        )

        result = ScreeningResult()

        with pytest.raises(ScreeningValidationError, match="Subject name is required"):
            await mock_orchestrator._validate_request(request, result)

    @pytest.mark.asyncio
    async def test_validate_case_file_requires_enhanced(
        self, mock_orchestrator: ScreeningOrchestrator, sample_subject: SubjectIdentifiers
    ) -> None:
        """Test validation fails when case file requested without enhanced tier."""
        request = ScreeningRequest(
            tenant_id=uuid7(),
            subject=sample_subject,
            locale=Locale.US,
            service_tier=ServiceTier.STANDARD,
            consent_token="test-token",
            report_types=[ReportType.CASE_FILE],
        )

        result = ScreeningResult()

        with pytest.raises(ScreeningValidationError, match="Case file report requires Enhanced"):
            await mock_orchestrator._validate_request(request, result)

    @pytest.mark.asyncio
    async def test_validate_success(
        self, mock_orchestrator: ScreeningOrchestrator, sample_request: ScreeningRequest
    ) -> None:
        """Test successful validation."""
        result = ScreeningResult()

        await mock_orchestrator._validate_request(sample_request, result)

        assert len(result.phases) == 1
        assert result.phases[0].phase_name == "validation"
        assert result.phases[0].status == "complete"


class TestComplianceChecking:
    """Tests for compliance checking."""

    @pytest.mark.asyncio
    async def test_compliance_check_success(
        self, mock_orchestrator: ScreeningOrchestrator, sample_request: ScreeningRequest
    ) -> None:
        """Test successful compliance check."""
        result = ScreeningResult()

        await mock_orchestrator._check_compliance(sample_request, result)

        assert len(result.phases) == 1
        assert result.phases[0].status == "complete"

    @pytest.mark.asyncio
    async def test_compliance_check_no_permitted(
        self, sample_request: ScreeningRequest
    ) -> None:
        """Test compliance check fails when no checks permitted."""
        orchestrator = ScreeningOrchestrator()

        # Mock compliance engine to return no permitted checks
        mock_compliance = MagicMock()
        mock_compliance.get_permitted_checks.return_value = []
        mock_compliance.get_blocked_checks.return_value = []
        orchestrator._compliance_engine = mock_compliance

        result = ScreeningResult()

        with pytest.raises(ScreeningComplianceError, match="No checks permitted"):
            await orchestrator._check_compliance(sample_request, result)

    @pytest.mark.asyncio
    async def test_compliance_check_skipped_when_disabled(
        self, sample_request: ScreeningRequest
    ) -> None:
        """Test compliance check is skipped when disabled."""
        config = OrchestratorConfig(validate_compliance=False)
        orchestrator = ScreeningOrchestrator(config=config)

        result = ScreeningResult()

        await orchestrator._check_compliance(sample_request, result)

        # No phase added when skipped
        assert len(result.phases) == 0


class TestConsentVerification:
    """Tests for consent verification."""

    @pytest.mark.asyncio
    async def test_consent_verification_success(
        self, mock_orchestrator: ScreeningOrchestrator, sample_request: ScreeningRequest
    ) -> None:
        """Test successful consent verification."""
        result = ScreeningResult()

        await mock_orchestrator._verify_consent(sample_request, result)

        assert len(result.phases) == 1
        assert result.phases[0].status == "complete"

    @pytest.mark.asyncio
    async def test_consent_verification_missing_token(
        self, mock_orchestrator: ScreeningOrchestrator, sample_subject: SubjectIdentifiers
    ) -> None:
        """Test consent verification fails without token."""
        request = ScreeningRequest(
            tenant_id=uuid7(),
            subject=sample_subject,
            locale=Locale.US,
            consent_token="",  # Empty token
        )

        result = ScreeningResult()

        with pytest.raises(ScreeningValidationError, match="Consent token is required"):
            await mock_orchestrator._verify_consent(request, result)

    @pytest.mark.asyncio
    async def test_consent_verification_skipped_when_disabled(
        self, sample_request: ScreeningRequest
    ) -> None:
        """Test consent verification is skipped when disabled."""
        config = OrchestratorConfig(validate_consent=False)
        orchestrator = ScreeningOrchestrator(config=config)

        result = ScreeningResult()

        await orchestrator._verify_consent(sample_request, result)

        # No phase added when skipped
        assert len(result.phases) == 0


class TestInvestigationExecution:
    """Tests for investigation execution."""

    @pytest.mark.asyncio
    async def test_investigation_success(
        self,
        mock_orchestrator: ScreeningOrchestrator,
        sample_request: ScreeningRequest,
        mock_investigation_result: InvestigationResult,
    ) -> None:
        """Test successful investigation execution."""
        # Mock SAR orchestrator
        mock_sar = AsyncMock()
        mock_sar.execute_investigation.return_value = mock_investigation_result
        mock_orchestrator._sar_orchestrator = mock_sar

        result = ScreeningResult()

        investigation_result = await mock_orchestrator._execute_investigation(
            sample_request, result
        )

        assert investigation_result is not None
        assert result.findings_count == 2
        assert len(result.phases) == 1
        assert result.phases[0].status == "complete"

    @pytest.mark.asyncio
    async def test_investigation_failure(
        self, mock_orchestrator: ScreeningOrchestrator, sample_request: ScreeningRequest
    ) -> None:
        """Test investigation failure handling."""
        # Mock SAR orchestrator to raise exception
        mock_sar = AsyncMock()
        mock_sar.execute_investigation.side_effect = Exception("Investigation failed")
        mock_orchestrator._sar_orchestrator = mock_sar

        result = ScreeningResult()

        with pytest.raises(ScreeningExecutionError, match="Investigation failed"):
            await mock_orchestrator._execute_investigation(sample_request, result)


class TestRiskAnalysis:
    """Tests for risk analysis."""

    @pytest.mark.asyncio
    async def test_risk_analysis_success(
        self,
        mock_orchestrator: ScreeningOrchestrator,
        sample_request: ScreeningRequest,
        mock_investigation_result: InvestigationResult,
        mock_risk_assessment: ComprehensiveRiskAssessment,
    ) -> None:
        """Test successful risk analysis."""
        # Mock risk aggregator
        mock_risk = AsyncMock()
        mock_risk.aggregate_risk.return_value = mock_risk_assessment
        mock_orchestrator._risk_aggregator = mock_risk

        result = ScreeningResult()

        risk_assessment = await mock_orchestrator._analyze_risk(
            sample_request, mock_investigation_result, result
        )

        assert risk_assessment is not None
        assert result.risk_score == 25
        assert result.risk_level == "low"
        assert result.recommendation == "proceed"

    @pytest.mark.asyncio
    async def test_risk_analysis_failure(
        self,
        mock_orchestrator: ScreeningOrchestrator,
        sample_request: ScreeningRequest,
        mock_investigation_result: InvestigationResult,
    ) -> None:
        """Test risk analysis failure handling."""
        # Mock risk aggregator to raise exception
        mock_risk = AsyncMock()
        mock_risk.aggregate_risk.side_effect = Exception("Analysis failed")
        mock_orchestrator._risk_aggregator = mock_risk

        result = ScreeningResult()

        with pytest.raises(ScreeningExecutionError, match="Risk analysis failed"):
            await mock_orchestrator._analyze_risk(
                sample_request, mock_investigation_result, result
            )


class TestReportGeneration:
    """Tests for report generation."""

    @pytest.mark.asyncio
    async def test_report_generation_success(
        self,
        mock_orchestrator: ScreeningOrchestrator,
        sample_request: ScreeningRequest,
        mock_investigation_result: InvestigationResult,
        mock_risk_assessment: ComprehensiveRiskAssessment,
    ) -> None:
        """Test successful report generation."""
        result = ScreeningResult()

        await mock_orchestrator._generate_reports(
            sample_request, mock_investigation_result, mock_risk_assessment, result
        )

        assert len(result.reports) == 1
        assert result.reports[0].report_type == ReportType.SUMMARY

    @pytest.mark.asyncio
    async def test_report_generation_multiple(
        self,
        mock_orchestrator: ScreeningOrchestrator,
        sample_subject: SubjectIdentifiers,
        mock_investigation_result: InvestigationResult,
        mock_risk_assessment: ComprehensiveRiskAssessment,
    ) -> None:
        """Test generating multiple report types."""
        request = ScreeningRequest(
            tenant_id=uuid7(),
            subject=sample_subject,
            locale=Locale.US,
            consent_token="test-token",
            report_types=[ReportType.SUMMARY, ReportType.AUDIT],
        )

        result = ScreeningResult()

        await mock_orchestrator._generate_reports(
            request, mock_investigation_result, mock_risk_assessment, result
        )

        assert len(result.reports) == 2
        report_types = {r.report_type for r in result.reports}
        assert ReportType.SUMMARY in report_types
        assert ReportType.AUDIT in report_types

    @pytest.mark.asyncio
    async def test_report_generation_skipped_when_disabled(
        self,
        sample_request: ScreeningRequest,
        mock_investigation_result: InvestigationResult,
        mock_risk_assessment: ComprehensiveRiskAssessment,
    ) -> None:
        """Test report generation is skipped when disabled."""
        config = OrchestratorConfig(generate_reports_on_complete=False)
        orchestrator = ScreeningOrchestrator(config=config)

        result = ScreeningResult()

        await orchestrator._generate_reports(
            sample_request, mock_investigation_result, mock_risk_assessment, result
        )

        assert len(result.reports) == 0


class TestEndToEndScreening:
    """End-to-end screening tests."""

    @pytest.mark.asyncio
    async def test_complete_screening_success(
        self,
        sample_request: ScreeningRequest,
        mock_investigation_result: InvestigationResult,
        mock_risk_assessment: ComprehensiveRiskAssessment,
    ) -> None:
        """Test complete screening workflow success."""
        orchestrator = ScreeningOrchestrator()

        # Mock all dependencies
        mock_compliance = MagicMock()
        mock_compliance.get_permitted_checks.return_value = ["CRIMINAL_NATIONAL"]
        mock_compliance.get_blocked_checks.return_value = []
        orchestrator._compliance_engine = mock_compliance

        mock_sar = AsyncMock()
        mock_sar.execute_investigation.return_value = mock_investigation_result
        orchestrator._sar_orchestrator = mock_sar

        mock_risk = AsyncMock()
        mock_risk.aggregate_risk.return_value = mock_risk_assessment
        orchestrator._risk_aggregator = mock_risk

        result = await orchestrator.execute_screening(sample_request)

        assert result.status == ScreeningStatus.COMPLETE
        assert result.risk_score == 25
        assert result.completed_at is not None
        assert len(result.phases) >= 4  # validation, compliance, consent, investigation, risk, reports

    @pytest.mark.asyncio
    async def test_screening_validation_failure(
        self, sample_subject: SubjectIdentifiers
    ) -> None:
        """Test screening fails on validation error."""
        request = ScreeningRequest(
            tenant_id=uuid7(),
            subject=SubjectIdentifiers(full_name=""),  # Invalid
            locale=Locale.US,
            consent_token="test-token",
        )

        orchestrator = ScreeningOrchestrator()
        result = await orchestrator.execute_screening(request)

        assert result.status == ScreeningStatus.FAILED
        assert result.error_code == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_screening_compliance_blocked(
        self, sample_request: ScreeningRequest
    ) -> None:
        """Test screening blocked by compliance."""
        orchestrator = ScreeningOrchestrator()

        # Mock compliance to return no permitted checks
        mock_compliance = MagicMock()
        mock_compliance.get_permitted_checks.return_value = []
        mock_compliance.get_blocked_checks.return_value = []
        orchestrator._compliance_engine = mock_compliance

        result = await orchestrator.execute_screening(sample_request)

        assert result.status == ScreeningStatus.COMPLIANCE_BLOCKED
        assert result.error_code == "COMPLIANCE_ERROR"


# =============================================================================
# Cost Summary Tests
# =============================================================================


class TestScreeningCostSummary:
    """Tests for ScreeningCostSummary."""

    def test_create_cost_summary(self) -> None:
        """Test creating a cost summary."""
        summary = ScreeningCostSummary(
            total_cost=Decimal("125.50"),
            data_provider_cost=Decimal("100.00"),
            ai_model_cost=Decimal("25.50"),
        )

        assert summary.total_cost == Decimal("125.50")
        assert summary.currency == "USD"

    def test_cost_summary_to_dict(self) -> None:
        """Test cost summary serialization."""
        summary = ScreeningCostSummary(
            total_cost=Decimal("50.00"),
            cost_by_provider={"sterling": Decimal("30.00"), "checkr": Decimal("20.00")},
        )

        d = summary.to_dict()

        assert d["total_cost"] == "50.00"
        assert "sterling" in d["cost_by_provider"]


# =============================================================================
# Generated Report Tests
# =============================================================================


class TestGeneratedReport:
    """Tests for GeneratedReport."""

    def test_create_report(self) -> None:
        """Test creating a generated report."""
        report = GeneratedReport(
            report_type=ReportType.SUMMARY,
            format="pdf",
            content=b"PDF content here",
            size_bytes=100,
        )

        assert report.report_type == ReportType.SUMMARY
        assert report.format == "pdf"
        assert report.report_id is not None

    def test_report_to_dict(self) -> None:
        """Test report serialization (without content)."""
        report = GeneratedReport(
            report_type=ReportType.AUDIT,
            format="html",
            content=b"<html>...</html>",
            size_bytes=50,
        )

        d = report.to_dict()

        assert d["report_type"] == "audit"
        assert d["format"] == "html"
        assert d["size_bytes"] == 50
        # Content should not be in dict
        assert "content" not in d


# =============================================================================
# Error Tests
# =============================================================================


class TestScreeningErrors:
    """Tests for screening error classes."""

    def test_validation_error(self) -> None:
        """Test ScreeningValidationError."""
        error = ScreeningValidationError(
            "Invalid field",
            details={"field": "name"},
        )

        assert error.code == "VALIDATION_ERROR"
        assert error.details["field"] == "name"

    def test_compliance_error(self) -> None:
        """Test ScreeningComplianceError."""
        error = ScreeningComplianceError(
            "Check not permitted",
            details={"locale": "EU"},
        )

        assert error.code == "COMPLIANCE_ERROR"

    def test_execution_error(self) -> None:
        """Test ScreeningExecutionError."""
        error = ScreeningExecutionError("Processing failed")

        assert error.code == "EXECUTION_ERROR"
