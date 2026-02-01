"""Screening Orchestrator for end-to-end screening workflow.

This module provides the main ScreeningOrchestrator class that coordinates
all phases of a background screening from request validation through report
generation.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, Field
from uuid_utils import uuid7

from elile.agent.state import KnowledgeBase, ServiceTier
from elile.compliance import (
    CheckType,
    ComplianceEngine,
    ConsentManager,
    get_compliance_engine,
)
from elile.core.context import RequestContext, get_current_context_or_none
from elile.investigation import (
    InvestigationResult,
    SARLoopOrchestrator,
    create_sar_orchestrator,
)
from elile.investigation.finding_extractor import Finding, Severity
from elile.risk import (
    ComprehensiveRiskAssessment,
    RiskAggregator,
    create_risk_aggregator,
)
from elile.screening.types import (
    GeneratedReport,
    ReportType,
    ScreeningComplianceError,
    ScreeningError,
    ScreeningExecutionError,
    ScreeningPhaseResult,
    ScreeningRequest,
    ScreeningResult,
    ScreeningStatus,
    ScreeningValidationError,
)

logger = structlog.get_logger()


# =============================================================================
# Configuration
# =============================================================================


class OrchestratorConfig(BaseModel):
    """Configuration for the screening orchestrator."""

    # Validation settings
    validate_consent: bool = Field(default=True, description="Validate consent token")
    validate_compliance: bool = Field(default=True, description="Run compliance checks")

    # Execution settings
    parallel_investigation: bool = Field(
        default=True, description="Run investigation types in parallel where possible"
    )
    max_investigation_time_seconds: int = Field(
        default=600, ge=60, le=3600, description="Maximum time for investigation phase"
    )

    # Report settings
    generate_reports_on_complete: bool = Field(
        default=True, description="Auto-generate reports on completion"
    )

    # Error handling
    fail_on_compliance_warning: bool = Field(
        default=False, description="Fail if compliance warnings (not just errors)"
    )
    continue_on_partial_failure: bool = Field(
        default=True, description="Continue if some data sources fail"
    )


# =============================================================================
# Screening Orchestrator
# =============================================================================


class ScreeningOrchestrator:
    """Orchestrates the complete screening workflow.

    The orchestrator coordinates all phases of a background screening:
    1. Request validation
    2. Compliance checking
    3. Consent verification
    4. Data source resolution
    5. Investigation (SAR loop)
    6. Risk analysis
    7. Report generation

    Example:
        orchestrator = ScreeningOrchestrator()
        result = await orchestrator.execute_screening(request)

        if result.status == ScreeningStatus.COMPLETE:
            print(f"Risk score: {result.risk_score}")
            for report in result.reports:
                print(f"Generated: {report.report_type.value}")
    """

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
        compliance_engine: ComplianceEngine | None = None,
        consent_manager: ConsentManager | None = None,
        sar_orchestrator: SARLoopOrchestrator | None = None,
        risk_aggregator: RiskAggregator | None = None,
    ) -> None:
        """Initialize the screening orchestrator.

        Args:
            config: Orchestrator configuration.
            compliance_engine: Optional compliance engine instance.
            consent_manager: Optional consent manager instance.
            sar_orchestrator: Optional SAR orchestrator instance.
            risk_aggregator: Optional risk aggregator instance.
        """
        self.config = config or OrchestratorConfig()
        self._compliance_engine = compliance_engine
        self._consent_manager = consent_manager
        self._sar_orchestrator = sar_orchestrator
        self._risk_aggregator = risk_aggregator

    @property
    def compliance_engine(self) -> ComplianceEngine:
        """Get or create compliance engine."""
        if self._compliance_engine is None:
            self._compliance_engine = get_compliance_engine()
        return self._compliance_engine

    @property
    def consent_manager(self) -> ConsentManager:
        """Get or create consent manager."""
        if self._consent_manager is None:
            self._consent_manager = ConsentManager()
        return self._consent_manager

    @property
    def sar_orchestrator(self) -> SARLoopOrchestrator:
        """Get or create SAR orchestrator."""
        if self._sar_orchestrator is None:
            self._sar_orchestrator = create_sar_orchestrator()
        return self._sar_orchestrator

    @property
    def risk_aggregator(self) -> RiskAggregator:
        """Get or create risk aggregator."""
        if self._risk_aggregator is None:
            self._risk_aggregator = create_risk_aggregator()
        return self._risk_aggregator

    async def execute_screening(
        self,
        request: ScreeningRequest,
        ctx: RequestContext | None = None,
    ) -> ScreeningResult:
        """Execute a complete screening workflow.

        This is the main entry point for screening execution. It coordinates
        all phases and handles errors appropriately.

        Args:
            request: The screening request to execute.
            ctx: Optional request context for audit logging.

        Returns:
            ScreeningResult with status, risk assessment, and reports.

        Raises:
            ScreeningValidationError: If request validation fails.
            ScreeningComplianceError: If compliance checks fail.
            ScreeningExecutionError: If execution fails.
        """
        ctx = ctx or get_current_context_or_none()

        result = ScreeningResult(
            screening_id=request.screening_id,
            tenant_id=request.tenant_id,
            started_at=datetime.now(UTC),
        )

        logger.info(
            "Starting screening",
            screening_id=str(request.screening_id),
            tenant_id=str(request.tenant_id),
            locale=request.locale.value,
            tier=request.service_tier.value,
            degree=request.search_degree.value,
        )

        try:
            # Phase 1: Validate request
            result.status = ScreeningStatus.VALIDATING
            await self._validate_request(request, result)

            # Phase 2: Check compliance
            await self._check_compliance(request, result)

            # Phase 3: Verify consent
            await self._verify_consent(request, result)

            # Phase 4: Execute investigation
            result.status = ScreeningStatus.IN_PROGRESS
            investigation_result = await self._execute_investigation(request, result)

            # Phase 5: Analyze risk
            result.status = ScreeningStatus.ANALYZING
            risk_assessment = await self._analyze_risk(request, investigation_result, result)

            # Phase 6: Generate reports
            result.status = ScreeningStatus.GENERATING_REPORT
            await self._generate_reports(request, investigation_result, risk_assessment, result)

            # Complete
            result.status = ScreeningStatus.COMPLETE
            result.completed_at = datetime.now(UTC)

            logger.info(
                "Screening complete",
                screening_id=str(request.screening_id),
                risk_score=result.risk_score,
                duration_seconds=result.duration_seconds,
            )

        except ScreeningValidationError as e:
            result.status = ScreeningStatus.FAILED
            result.error_message = e.message
            result.error_code = e.code
            result.completed_at = datetime.now(UTC)
            logger.warning(
                "Screening validation failed",
                screening_id=str(request.screening_id),
                error=e.message,
            )

        except ScreeningComplianceError as e:
            result.status = ScreeningStatus.COMPLIANCE_BLOCKED
            result.error_message = e.message
            result.error_code = e.code
            result.completed_at = datetime.now(UTC)
            logger.warning(
                "Screening blocked by compliance",
                screening_id=str(request.screening_id),
                error=e.message,
            )

        except ScreeningExecutionError as e:
            result.status = ScreeningStatus.FAILED
            result.error_message = e.message
            result.error_code = e.code
            result.completed_at = datetime.now(UTC)
            logger.error(
                "Screening execution failed",
                screening_id=str(request.screening_id),
                error=e.message,
            )

        except Exception as e:
            result.status = ScreeningStatus.FAILED
            result.error_message = str(e)
            result.error_code = "UNEXPECTED_ERROR"
            result.completed_at = datetime.now(UTC)
            logger.exception(
                "Unexpected error during screening",
                screening_id=str(request.screening_id),
            )

        return result

    async def _validate_request(
        self,
        request: ScreeningRequest,
        result: ScreeningResult,
    ) -> None:
        """Validate the screening request.

        Checks:
        - Required fields are present
        - Tier/degree combination is valid
        - Subject identifiers are sufficient
        """
        phase = result.add_phase("validation")

        try:
            # Check required subject identifiers
            if not request.subject.full_name:
                raise ScreeningValidationError(
                    "Subject name is required",
                    details={"field": "subject.name"},
                )

            # Validate tier/degree combination
            if request.search_degree.value == "d3" and request.service_tier != ServiceTier.ENHANCED:
                raise ScreeningValidationError(
                    "D3 search degree requires Enhanced service tier",
                    details={
                        "search_degree": request.search_degree.value,
                        "service_tier": request.service_tier.value,
                    },
                )

            # Validate report types
            for report_type in request.report_types:
                if report_type == ReportType.CASE_FILE and request.service_tier != ServiceTier.ENHANCED:
                    raise ScreeningValidationError(
                        "Case file report requires Enhanced service tier",
                        details={"report_type": report_type.value},
                    )

            phase.complete("complete")

        except ScreeningValidationError:
            phase.complete("failed", "Validation failed")
            raise

    async def _check_compliance(
        self,
        request: ScreeningRequest,
        result: ScreeningResult,
    ) -> None:
        """Check compliance rules for the screening.

        Verifies that the requested checks are permitted for the locale
        and role category.
        """
        if not self.config.validate_compliance:
            return

        phase = result.add_phase("compliance_check")

        try:
            # Get permitted checks for this locale/tier/role
            permitted = self.compliance_engine.get_permitted_checks(
                locale=request.locale,
                tier=request.service_tier,
                role_category=request.role_category,
            )

            # Get blocked checks
            blocked = self.compliance_engine.get_blocked_checks(
                locale=request.locale,
                tier=request.service_tier,
                role_category=request.role_category,
            )

            if not permitted:
                raise ScreeningComplianceError(
                    f"No checks permitted for locale {request.locale.value}",
                    details={
                        "locale": request.locale.value,
                        "tier": request.service_tier.value,
                        "role_category": request.role_category.value,
                    },
                )

            phase.details["permitted_checks"] = len(permitted)
            phase.details["blocked_checks"] = len(blocked)
            phase.complete("complete")

        except ScreeningComplianceError:
            phase.complete("failed", "Compliance check failed")
            raise

    async def _verify_consent(
        self,
        request: ScreeningRequest,
        result: ScreeningResult,
    ) -> None:
        """Verify subject consent for the screening.

        Validates the consent token and ensures consent covers
        all required scopes.
        """
        if not self.config.validate_consent:
            return

        phase = result.add_phase("consent_verification")

        try:
            # Validate consent token is present
            if not request.consent_token:
                raise ScreeningValidationError(
                    "Consent token is required",
                    details={"field": "consent_token"},
                )

            # In a real implementation, this would verify the consent token
            # against the consent management system
            # For now, we just check it's not empty
            phase.details["consent_token_present"] = True
            phase.complete("complete")

        except ScreeningValidationError:
            phase.complete("failed", "Consent verification failed")
            raise

    async def _execute_investigation(
        self,
        request: ScreeningRequest,
        result: ScreeningResult,
    ) -> InvestigationResult:
        """Execute the SAR loop investigation.

        Runs the Search-Assess-Refine loop for all applicable information
        types based on the screening configuration.
        """
        phase = result.add_phase("investigation")

        try:
            # Create knowledge base for investigation
            knowledge_base = KnowledgeBase()

            # Seed knowledge base with subject identifiers
            if request.subject.full_name:
                knowledge_base.confirmed_names.append(request.subject.full_name)
            if request.subject.date_of_birth:
                knowledge_base.confirmed_dob = str(request.subject.date_of_birth)
            if request.subject.ssn:
                # Store last 4 of SSN
                ssn = request.subject.ssn.replace("-", "")
                if len(ssn) >= 4:
                    knowledge_base.confirmed_ssn_last4 = ssn[-4:]

            # Execute investigation
            investigation_result = await self.sar_orchestrator.execute_investigation(
                knowledge_base=knowledge_base,
                locale=request.locale,
                tier=request.service_tier,
                role_category=request.role_category,
            )

            # Update result statistics
            # Get all findings from type results
            all_findings = self._collect_findings(investigation_result)
            result.findings_count = len(all_findings)
            result.critical_findings = sum(
                1 for f in all_findings
                if f.severity == Severity.CRITICAL
            )
            result.high_findings = sum(
                1 for f in all_findings
                if f.severity == Severity.HIGH
            )
            result.queries_executed = investigation_result.total_queries
            result.data_sources_queried = len(investigation_result.type_results)

            phase.details["types_investigated"] = len(investigation_result.type_results)
            phase.details["findings_count"] = result.findings_count
            phase.complete("complete")

            return investigation_result

        except Exception as e:
            phase.complete("failed", str(e))
            raise ScreeningExecutionError(
                f"Investigation failed: {e}",
                details={"error": str(e)},
            )

    def _collect_findings(self, investigation_result: InvestigationResult) -> list[Finding]:
        """Collect all findings from investigation result.

        Args:
            investigation_result: The investigation result.

        Returns:
            List of all findings from all type results.
        """
        all_findings: list[Finding] = []

        # Check if all_findings attribute exists (for mocking)
        if hasattr(investigation_result, 'all_findings'):
            return investigation_result.all_findings

        # Otherwise, collect from type results
        for type_result in investigation_result.type_results.values():
            if hasattr(type_result, 'findings') and type_result.findings:
                all_findings.extend(type_result.findings)

        return all_findings

    async def _analyze_risk(
        self,
        request: ScreeningRequest,
        investigation_result: InvestigationResult,
        result: ScreeningResult,
    ) -> ComprehensiveRiskAssessment:
        """Analyze risk from investigation findings.

        Aggregates findings, patterns, anomalies, and connections into
        a comprehensive risk assessment.
        """
        phase = result.add_phase("risk_analysis")

        try:
            # Extract components for risk analysis
            findings = self._collect_findings(investigation_result)
            patterns = investigation_result.patterns if hasattr(investigation_result, 'patterns') else []
            anomalies = investigation_result.anomalies if hasattr(investigation_result, 'anomalies') else []

            # Run risk aggregation
            risk_assessment = await self.risk_aggregator.aggregate_risk(
                findings=findings,
                patterns=patterns,
                anomalies=anomalies,
                connections=None,  # Connection analysis is separate
                role_category=request.role_category,
            )

            # Update result with risk info
            result.risk_assessment_id = risk_assessment.assessment_id
            result.risk_score = risk_assessment.final_score
            result.risk_level = risk_assessment.risk_level.value
            result.recommendation = risk_assessment.recommendation.value

            phase.details["risk_score"] = risk_assessment.final_score
            phase.details["risk_level"] = risk_assessment.risk_level.value
            phase.complete("complete")

            return risk_assessment

        except Exception as e:
            phase.complete("failed", str(e))
            raise ScreeningExecutionError(
                f"Risk analysis failed: {e}",
                details={"error": str(e)},
            )

    async def _generate_reports(
        self,
        request: ScreeningRequest,
        investigation_result: InvestigationResult,
        risk_assessment: ComprehensiveRiskAssessment,
        result: ScreeningResult,
    ) -> None:
        """Generate requested reports.

        Creates reports based on the report types specified in the request.
        """
        if not self.config.generate_reports_on_complete:
            return

        phase = result.add_phase("report_generation")

        try:
            for report_type in request.report_types:
                report = await self._generate_single_report(
                    report_type=report_type,
                    request=request,
                    investigation_result=investigation_result,
                    risk_assessment=risk_assessment,
                )
                result.reports.append(report)

            phase.details["reports_generated"] = len(result.reports)
            phase.complete("complete")

        except Exception as e:
            phase.complete("failed", str(e))
            # Don't fail the whole screening for report generation issues
            logger.warning(
                "Report generation failed",
                screening_id=str(request.screening_id),
                error=str(e),
            )

    async def _generate_single_report(
        self,
        report_type: ReportType,
        request: ScreeningRequest,
        investigation_result: InvestigationResult,
        risk_assessment: ComprehensiveRiskAssessment,
    ) -> GeneratedReport:
        """Generate a single report.

        This is a placeholder implementation. The actual report generation
        will be implemented in Task 7.5-7.7.
        """
        # For now, create a stub report
        # Real implementation will use report generators
        content = f"Report: {report_type.value}\n"
        content += f"Screening ID: {request.screening_id}\n"
        content += f"Risk Score: {risk_assessment.final_score}\n"
        content += f"Recommendation: {risk_assessment.recommendation.value}\n"

        content_bytes = content.encode("utf-8")

        return GeneratedReport(
            report_type=report_type,
            format="txt",  # Placeholder - real reports will be PDF
            content=content_bytes,
            size_bytes=len(content_bytes),
            checksum="",  # Would calculate actual checksum
        )


# =============================================================================
# Factory Functions
# =============================================================================


def create_screening_orchestrator(
    config: OrchestratorConfig | None = None,
) -> ScreeningOrchestrator:
    """Create a screening orchestrator with optional configuration.

    Args:
        config: Optional orchestrator configuration.

    Returns:
        Configured ScreeningOrchestrator instance.
    """
    return ScreeningOrchestrator(config=config)
