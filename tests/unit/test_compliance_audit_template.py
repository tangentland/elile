"""Tests for Compliance Officer Audit Report template builder.

Tests the ComplianceAuditBuilder which transforms compiled screening results
into comprehensive audit documentation for compliance officers.
"""

from uuid import uuid7

import pytest

from elile.agent.state import InformationType
from elile.compliance.consent import ConsentScope, ConsentVerificationMethod
from elile.compliance.types import CheckType, Locale, RestrictionType
from elile.db.models.audit import AuditEventType, AuditSeverity
from elile.reporting.templates.compliance_audit import (
    AppliedRule,
    AuditTrailEvent,
    ComplianceAuditBuilder,
    ComplianceAuditConfig,
    ComplianceAuditContent,
    ComplianceStatus,
    ConsentRecord,
    DataHandlingStatus,
    DataSourceAccess,
    DisclosureRecord,
    create_compliance_audit_builder,
)
from elile.screening.result_compiler import (
    CompiledResult,
    ConnectionSummary,
    FindingsSummary,
    InvestigationSummary,
    SARSummary,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_compiled_result() -> CompiledResult:
    """Create a minimal compiled result."""
    return CompiledResult(
        screening_id=uuid7(),
        entity_id=uuid7(),
        tenant_id=uuid7(),
        findings_summary=FindingsSummary(total_findings=0),
        investigation_summary=InvestigationSummary(
            types_processed=3,
            types_completed=3,
            by_type={
                InformationType.IDENTITY: SARSummary(
                    info_type=InformationType.IDENTITY,
                    iterations_completed=2,
                    final_confidence=0.95,
                    queries_executed=5,
                    facts_extracted=10,
                ),
                InformationType.CRIMINAL: SARSummary(
                    info_type=InformationType.CRIMINAL,
                    iterations_completed=2,
                    final_confidence=0.92,
                    queries_executed=3,
                    facts_extracted=5,
                ),
            },
        ),
        connection_summary=ConnectionSummary(),
        risk_score=20,
        risk_level="low",
        recommendation="proceed",
    )


@pytest.fixture
def comprehensive_compiled_result() -> CompiledResult:
    """Create a comprehensive compiled result with multiple types."""
    return CompiledResult(
        screening_id=uuid7(),
        entity_id=uuid7(),
        tenant_id=uuid7(),
        findings_summary=FindingsSummary(total_findings=5),
        investigation_summary=InvestigationSummary(
            types_processed=6,
            types_completed=6,
            by_type={
                InformationType.IDENTITY: SARSummary(
                    info_type=InformationType.IDENTITY,
                    iterations_completed=2,
                    final_confidence=0.95,
                    queries_executed=5,
                    facts_extracted=10,
                    duration_ms=150.0,
                ),
                InformationType.CRIMINAL: SARSummary(
                    info_type=InformationType.CRIMINAL,
                    iterations_completed=3,
                    final_confidence=0.90,
                    queries_executed=8,
                    facts_extracted=3,
                    duration_ms=250.0,
                ),
                InformationType.EMPLOYMENT: SARSummary(
                    info_type=InformationType.EMPLOYMENT,
                    iterations_completed=2,
                    final_confidence=0.88,
                    queries_executed=4,
                    facts_extracted=8,
                    duration_ms=200.0,
                ),
                InformationType.EDUCATION: SARSummary(
                    info_type=InformationType.EDUCATION,
                    iterations_completed=2,
                    final_confidence=0.92,
                    queries_executed=3,
                    facts_extracted=4,
                    duration_ms=180.0,
                ),
                InformationType.SANCTIONS: SARSummary(
                    info_type=InformationType.SANCTIONS,
                    iterations_completed=1,
                    final_confidence=0.98,
                    queries_executed=2,
                    facts_extracted=0,
                    duration_ms=100.0,
                ),
                InformationType.FINANCIAL: SARSummary(
                    info_type=InformationType.FINANCIAL,
                    iterations_completed=2,
                    final_confidence=0.85,
                    queries_executed=5,
                    facts_extracted=6,
                    duration_ms=220.0,
                ),
            },
            total_queries=27,
            total_facts=31,
        ),
        connection_summary=ConnectionSummary(entities_discovered=5),
        risk_score=35,
        risk_level="moderate",
        recommendation="proceed_with_caution",
    )


@pytest.fixture
def consent_records() -> list[ConsentRecord]:
    """Create sample consent records."""
    return [
        ConsentRecord(
            scope=ConsentScope.BACKGROUND_CHECK,
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            verified=True,
            notes="Electronic signature verified",
        ),
        ConsentRecord(
            scope=ConsentScope.CRIMINAL_RECORDS,
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            verified=True,
        ),
        ConsentRecord(
            scope=ConsentScope.CREDIT_CHECK,
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            verified=True,
        ),
    ]


@pytest.fixture
def disclosure_records() -> list[DisclosureRecord]:
    """Create sample disclosure records."""
    return [
        DisclosureRecord(
            disclosure_type="FCRA",
            method="email",
            acknowledged=True,
            document_reference="FCRA_DISCLOSURE_v1.0",
        ),
        DisclosureRecord(
            disclosure_type="SUMMARY_OF_RIGHTS",
            method="email",
            acknowledged=True,
            document_reference="CFPB_SUMMARY_v2023",
        ),
        DisclosureRecord(
            disclosure_type="CA_ICRAA",
            method="email",
            acknowledged=True,
            document_reference="CA_ICRAA_v2.0",
        ),
    ]


@pytest.fixture
def applied_rules() -> list[AppliedRule]:
    """Create sample applied rules."""
    return [
        AppliedRule(
            rule_id="US_FCRA_CRIMINAL",
            rule_name="FCRA Criminal Background Check",
            rule_type="FCRA",
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
            restriction_type=None,
            result="permitted",
            notes="7-year lookback applied",
        ),
        AppliedRule(
            rule_id="US_FCRA_CREDIT",
            rule_name="FCRA Credit Report",
            rule_type="FCRA",
            locale=Locale.US,
            check_type=CheckType.CREDIT_REPORT,
            restriction_type=RestrictionType.CONDITIONAL,
            result="permitted",
            notes="Requires explicit consent",
        ),
    ]


@pytest.fixture
def data_source_accesses() -> list[DataSourceAccess]:
    """Create sample data source accesses."""
    return [
        DataSourceAccess(
            provider_id="sterling",
            provider_name="Sterling Background Check",
            data_type="criminal",
            response_time_ms=250.0,
            cost=15.00,
            records_returned=3,
            success=True,
        ),
        DataSourceAccess(
            provider_id="equifax",
            provider_name="Equifax Credit",
            data_type="credit",
            response_time_ms=180.0,
            cost=8.50,
            records_returned=1,
            success=True,
        ),
        DataSourceAccess(
            provider_id="work_number",
            provider_name="The Work Number",
            data_type="employment",
            response_time_ms=200.0,
            cost=12.00,
            records_returned=5,
            success=True,
        ),
    ]


@pytest.fixture
def audit_events() -> list[AuditTrailEvent]:
    """Create sample audit events."""
    return [
        AuditTrailEvent(
            event_type=AuditEventType.SCREENING_INITIATED,
            actor_type="user",
            actor_id="user-123",
            severity=AuditSeverity.INFO,
            description="Background screening initiated",
            resource_type="screening",
        ),
        AuditTrailEvent(
            event_type=AuditEventType.CONSENT_GRANTED,
            actor_type="subject",
            severity=AuditSeverity.INFO,
            description="Subject granted consent for background check",
        ),
        AuditTrailEvent(
            event_type=AuditEventType.DATA_ACCESSED,
            actor_type="system",
            severity=AuditSeverity.INFO,
            description="Accessed criminal records database",
            details={"provider": "sterling", "records": 3},
        ),
        AuditTrailEvent(
            event_type=AuditEventType.COMPLIANCE_CHECK,
            actor_type="system",
            severity=AuditSeverity.INFO,
            description="FCRA compliance rules evaluated",
        ),
        AuditTrailEvent(
            event_type=AuditEventType.SCREENING_COMPLETED,
            actor_type="system",
            severity=AuditSeverity.INFO,
            description="Background screening completed",
            details={"risk_score": 35},
        ),
    ]


@pytest.fixture
def builder() -> ComplianceAuditBuilder:
    """Create a default Compliance Audit builder."""
    return create_compliance_audit_builder()


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_compliance_audit_builder factory."""

    def test_create_default_builder(self):
        """Test creating builder with default config."""
        builder = create_compliance_audit_builder()

        assert isinstance(builder, ComplianceAuditBuilder)
        assert isinstance(builder.config, ComplianceAuditConfig)
        assert builder.config.max_audit_events == 100

    def test_create_builder_with_custom_config(self):
        """Test creating builder with custom config."""
        config = ComplianceAuditConfig(
            max_audit_events=50,
            max_data_sources=20,
            include_detailed_costs=False,
        )
        builder = create_compliance_audit_builder(config=config)

        assert builder.config.max_audit_events == 50
        assert builder.config.max_data_sources == 20
        assert builder.config.include_detailed_costs is False


# =============================================================================
# Builder Tests - Basic Build
# =============================================================================


class TestBasicBuild:
    """Tests for basic build functionality."""

    def test_build_with_minimal_result(self, builder, minimal_compiled_result):
        """Test building with minimal compiled result."""
        content = builder.build(minimal_compiled_result)

        assert isinstance(content, ComplianceAuditContent)
        assert content.screening_id == minimal_compiled_result.screening_id
        assert content.entity_id == minimal_compiled_result.entity_id
        assert content.tenant_id == minimal_compiled_result.tenant_id

    def test_build_with_comprehensive_result(self, builder, comprehensive_compiled_result):
        """Test building with comprehensive compiled result."""
        content = builder.build(comprehensive_compiled_result)

        assert isinstance(content, ComplianceAuditContent)
        assert content.data_sources.total_sources > 0
        assert len(content.audit_trail.events) > 0

    def test_default_consent_generated(self, builder, minimal_compiled_result):
        """Test default consent is generated when none provided."""
        content = builder.build(minimal_compiled_result)

        assert len(content.consent_verification.consents) > 0
        assert content.consent_verification.consents[0].scope == ConsentScope.BACKGROUND_CHECK

    def test_default_disclosures_generated(self, builder, minimal_compiled_result):
        """Test default disclosures are generated when none provided."""
        content = builder.build(minimal_compiled_result)

        assert len(content.consent_verification.disclosures) > 0
        # Should have FCRA and SUMMARY_OF_RIGHTS
        types = [d.disclosure_type for d in content.consent_verification.disclosures]
        assert "FCRA" in types
        assert "SUMMARY_OF_RIGHTS" in types


# =============================================================================
# Consent Verification Tests
# =============================================================================


class TestConsentVerification:
    """Tests for consent verification section."""

    def test_consent_section_with_provided_consents(
        self, builder, minimal_compiled_result, consent_records, disclosure_records
    ):
        """Test consent section with provided records."""
        content = builder.build(
            minimal_compiled_result,
            consent_records=consent_records,
            disclosure_records=disclosure_records,
        )

        assert len(content.consent_verification.consents) == 3
        assert len(content.consent_verification.disclosures) == 3
        assert content.consent_verification.all_required_consents_obtained is True
        assert content.consent_verification.all_disclosures_provided is True

    def test_consent_verification_complete(self, builder, minimal_compiled_result, consent_records):
        """Test consent verification complete flag."""
        content = builder.build(minimal_compiled_result, consent_records=consent_records)

        assert content.consent_verification.consent_verification_complete is True

    def test_consent_verification_incomplete(self, builder, minimal_compiled_result):
        """Test consent verification incomplete with unverified consent."""
        unverified = [
            ConsentRecord(
                scope=ConsentScope.BACKGROUND_CHECK,
                verified=False,
                notes="Consent not verified",
            )
        ]
        content = builder.build(minimal_compiled_result, consent_records=unverified)

        assert content.consent_verification.all_required_consents_obtained is False
        assert content.consent_verification.consent_verification_complete is False

    def test_consent_record_to_dict(self, consent_records):
        """Test ConsentRecord.to_dict()."""
        record = consent_records[0]
        data = record.to_dict()

        assert "consent_id" in data
        assert "scope" in data
        assert "granted_at" in data
        assert "verification_method" in data
        assert data["verified"] is True

    def test_disclosure_record_to_dict(self, disclosure_records):
        """Test DisclosureRecord.to_dict()."""
        record = disclosure_records[0]
        data = record.to_dict()

        assert "disclosure_id" in data
        assert data["disclosure_type"] == "FCRA"
        assert data["acknowledged"] is True


# =============================================================================
# Compliance Rules Tests
# =============================================================================


class TestComplianceRules:
    """Tests for compliance rules section."""

    def test_rules_section_with_provided_rules(
        self, builder, minimal_compiled_result, applied_rules
    ):
        """Test rules section with provided rules."""
        content = builder.build(minimal_compiled_result, applied_rules=applied_rules)

        assert len(content.compliance_rules.rules_applied) == 2
        assert content.compliance_rules.checks_permitted == 2
        assert content.compliance_rules.checks_blocked == 0

    def test_default_rules_generated(self, builder, comprehensive_compiled_result):
        """Test default rules are generated from investigation summary."""
        content = builder.build(comprehensive_compiled_result)

        # Should generate rules for each info type
        assert len(content.compliance_rules.rules_applied) > 0

    def test_rules_locale(self, builder, minimal_compiled_result, applied_rules):
        """Test rules respect locale parameter."""
        content = builder.build(
            minimal_compiled_result,
            applied_rules=applied_rules,
            locale=Locale.US,
        )

        assert content.compliance_rules.locale == Locale.US

    def test_blocked_rules_affect_status(self, builder, minimal_compiled_result):
        """Test blocked rules affect compliance status."""
        blocked_rule = [
            AppliedRule(
                rule_id="TEST_BLOCK",
                rule_name="Blocked Check",
                rule_type="FCRA",
                locale=Locale.US,
                restriction_type=RestrictionType.BLOCKED,
                result="blocked",
                notes="Check not permitted",
            )
        ]
        content = builder.build(minimal_compiled_result, applied_rules=blocked_rule)

        assert content.compliance_rules.checks_blocked == 1
        assert content.compliance_rules.overall_compliance == ComplianceStatus.PARTIALLY_COMPLIANT

    def test_applied_rule_to_dict(self, applied_rules):
        """Test AppliedRule.to_dict()."""
        rule = applied_rules[0]
        data = rule.to_dict()

        assert data["rule_id"] == "US_FCRA_CRIMINAL"
        assert data["rule_type"] == "FCRA"
        assert data["result"] == "permitted"


# =============================================================================
# Data Sources Tests
# =============================================================================


class TestDataSources:
    """Tests for data sources section."""

    def test_sources_section_with_provided_accesses(
        self, builder, minimal_compiled_result, data_source_accesses
    ):
        """Test sources section with provided accesses."""
        content = builder.build(minimal_compiled_result, data_source_accesses=data_source_accesses)

        assert content.data_sources.total_sources == 3
        assert content.data_sources.successful_queries == 3
        assert content.data_sources.failed_queries == 0

    def test_sources_cost_calculation(self, builder, minimal_compiled_result, data_source_accesses):
        """Test total cost is calculated correctly."""
        content = builder.build(minimal_compiled_result, data_source_accesses=data_source_accesses)

        expected_cost = 15.00 + 8.50 + 12.00
        assert content.data_sources.total_cost == expected_cost

    def test_sources_records_count(self, builder, minimal_compiled_result, data_source_accesses):
        """Test total records is calculated correctly."""
        content = builder.build(minimal_compiled_result, data_source_accesses=data_source_accesses)

        expected_records = 3 + 1 + 5
        assert content.data_sources.total_records == expected_records

    def test_sources_average_response_time(
        self, builder, minimal_compiled_result, data_source_accesses
    ):
        """Test average response time is calculated correctly."""
        content = builder.build(minimal_compiled_result, data_source_accesses=data_source_accesses)

        expected_avg = (250.0 + 180.0 + 200.0) / 3
        assert content.data_sources.average_response_time_ms == expected_avg

    def test_default_sources_generated(self, builder, comprehensive_compiled_result):
        """Test default sources are generated from investigation summary."""
        content = builder.build(comprehensive_compiled_result)

        # Should generate sources for each info type
        assert content.data_sources.total_sources > 0

    def test_failed_source_counted(self, builder, minimal_compiled_result):
        """Test failed sources are counted correctly."""
        sources = [
            DataSourceAccess(provider_id="test", success=True),
            DataSourceAccess(provider_id="failed", success=False, error_message="Timeout"),
        ]
        content = builder.build(minimal_compiled_result, data_source_accesses=sources)

        assert content.data_sources.successful_queries == 1
        assert content.data_sources.failed_queries == 1

    def test_data_source_access_to_dict(self, data_source_accesses):
        """Test DataSourceAccess.to_dict()."""
        access = data_source_accesses[0]
        data = access.to_dict()

        assert data["provider_id"] == "sterling"
        assert data["cost"] == 15.00
        assert data["success"] is True


# =============================================================================
# Audit Trail Tests
# =============================================================================


class TestAuditTrail:
    """Tests for audit trail section."""

    def test_audit_section_with_provided_events(
        self, builder, minimal_compiled_result, audit_events
    ):
        """Test audit section with provided events."""
        content = builder.build(minimal_compiled_result, audit_events=audit_events)

        assert content.audit_trail.total_events == 5
        assert content.audit_trail.info_events == 5
        assert content.audit_trail.warning_events == 0
        assert content.audit_trail.error_events == 0

    def test_default_events_generated(self, builder, comprehensive_compiled_result):
        """Test default events are generated from compiled result."""
        content = builder.build(comprehensive_compiled_result)

        # Should generate at least initiated and completed events
        event_types = [e.event_type for e in content.audit_trail.events]
        assert AuditEventType.SCREENING_INITIATED in event_types
        assert AuditEventType.SCREENING_COMPLETED in event_types

    def test_warning_events_counted(self, builder, minimal_compiled_result):
        """Test warning events are counted."""
        events = [
            AuditTrailEvent(severity=AuditSeverity.INFO),
            AuditTrailEvent(severity=AuditSeverity.WARNING),
            AuditTrailEvent(severity=AuditSeverity.WARNING),
        ]
        content = builder.build(minimal_compiled_result, audit_events=events)

        assert content.audit_trail.info_events == 1
        assert content.audit_trail.warning_events == 2

    def test_error_events_counted(self, builder, minimal_compiled_result):
        """Test error events are counted."""
        events = [
            AuditTrailEvent(severity=AuditSeverity.INFO),
            AuditTrailEvent(severity=AuditSeverity.ERROR),
            AuditTrailEvent(severity=AuditSeverity.CRITICAL),
        ]
        content = builder.build(minimal_compiled_result, audit_events=events)

        assert content.audit_trail.error_events == 2

    def test_audit_trail_event_to_dict(self, audit_events):
        """Test AuditTrailEvent.to_dict()."""
        event = audit_events[0]
        data = event.to_dict()

        assert "event_id" in data
        assert data["event_type"] == "screening.initiated"
        assert data["severity"] == "info"


# =============================================================================
# Data Handling Tests
# =============================================================================


class TestDataHandling:
    """Tests for data handling compliance section."""

    def test_data_handling_verified(self, builder, minimal_compiled_result):
        """Test data handling is verified by default."""
        content = builder.build(minimal_compiled_result)

        assert content.data_handling.attestation.status == DataHandlingStatus.VERIFIED
        assert content.data_handling.encryption_verified is True
        assert content.data_handling.access_controls_verified is True

    def test_data_handling_requirements(self, builder, minimal_compiled_result):
        """Test data handling requirements are listed."""
        content = builder.build(minimal_compiled_result)

        assert len(content.data_handling.attestation.requirements_met) > 0
        assert "Data encrypted at rest" in content.data_handling.attestation.requirements_met

    def test_retention_period(self, builder, minimal_compiled_result):
        """Test retention period is set correctly."""
        content = builder.build(minimal_compiled_result)

        # Default is 7 years (2555 days)
        assert content.data_handling.retention_period_days == 2555

    def test_custom_retention_period(self, minimal_compiled_result):
        """Test custom retention period from config."""
        config = ComplianceAuditConfig(default_retention_days=365)
        builder = ComplianceAuditBuilder(config=config)
        content = builder.build(minimal_compiled_result)

        assert content.data_handling.retention_period_days == 365

    def test_data_handling_attestation_to_dict(self, builder, minimal_compiled_result):
        """Test DataHandlingAttestation.to_dict()."""
        content = builder.build(minimal_compiled_result)
        data = content.data_handling.attestation.to_dict()

        assert "attestation_id" in data
        assert data["status"] == "verified"
        assert "requirements_met" in data


# =============================================================================
# Overall Status Tests
# =============================================================================


class TestOverallStatus:
    """Tests for overall compliance status determination."""

    def test_compliant_status(self, builder, minimal_compiled_result, consent_records):
        """Test compliant status when all checks pass."""
        content = builder.build(minimal_compiled_result, consent_records=consent_records)

        assert content.overall_status == ComplianceStatus.COMPLIANT

    def test_partially_compliant_consent(self, builder, minimal_compiled_result):
        """Test partially compliant when consent issues."""
        unverified = [ConsentRecord(scope=ConsentScope.BACKGROUND_CHECK, verified=False)]
        content = builder.build(minimal_compiled_result, consent_records=unverified)

        assert content.overall_status == ComplianceStatus.PARTIALLY_COMPLIANT

    def test_partially_compliant_rules(self, builder, minimal_compiled_result):
        """Test partially compliant when rules blocked checks."""
        blocked = [
            AppliedRule(
                rule_id="BLOCKED",
                rule_type="FCRA",
                locale=Locale.US,
                restriction_type=RestrictionType.BLOCKED,
                result="blocked",
            )
        ]
        content = builder.build(minimal_compiled_result, applied_rules=blocked)

        assert content.overall_status == ComplianceStatus.PARTIALLY_COMPLIANT


# =============================================================================
# Summary Tests
# =============================================================================


class TestSummary:
    """Tests for summary generation."""

    def test_summary_generated(self, builder, comprehensive_compiled_result):
        """Test summary is generated."""
        content = builder.build(comprehensive_compiled_result)

        assert len(content.summary) > 0

    def test_summary_mentions_compliance(self, builder, minimal_compiled_result, consent_records):
        """Test summary mentions compliance status."""
        content = builder.build(minimal_compiled_result, consent_records=consent_records)

        assert "compliance" in content.summary.lower()

    def test_summary_mentions_consent(self, builder, minimal_compiled_result, consent_records):
        """Test summary mentions consent."""
        content = builder.build(minimal_compiled_result, consent_records=consent_records)

        assert "consent" in content.summary.lower()

    def test_summary_mentions_sources(self, builder, minimal_compiled_result, data_source_accesses):
        """Test summary mentions data sources."""
        content = builder.build(minimal_compiled_result, data_source_accesses=data_source_accesses)

        assert "source" in content.summary.lower()


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Tests for configuration options."""

    def test_max_audit_events_limit(self, comprehensive_compiled_result):
        """Test max audit events limit is respected."""
        events = [AuditTrailEvent() for _ in range(150)]
        config = ComplianceAuditConfig(max_audit_events=50)
        builder = ComplianceAuditBuilder(config=config)

        content = builder.build(comprehensive_compiled_result, audit_events=events)

        assert len(content.audit_trail.events) <= 50

    def test_max_data_sources_limit(self, minimal_compiled_result):
        """Test max data sources limit is respected."""
        sources = [DataSourceAccess(provider_id=f"provider_{i}") for i in range(100)]
        config = ComplianceAuditConfig(max_data_sources=20)
        builder = ComplianceAuditBuilder(config=config)

        content = builder.build(minimal_compiled_result, data_source_accesses=sources)

        assert len(content.data_sources.sources_accessed) <= 20

    def test_max_rules_limit(self, minimal_compiled_result):
        """Test max rules limit is respected."""
        rules = [
            AppliedRule(rule_id=f"rule_{i}", rule_type="TEST", locale=Locale.US) for i in range(100)
        ]
        config = ComplianceAuditConfig(max_rules=25)
        builder = ComplianceAuditBuilder(config=config)

        content = builder.build(minimal_compiled_result, applied_rules=rules)

        assert len(content.compliance_rules.rules_applied) <= 25


# =============================================================================
# Data Model Tests
# =============================================================================


class TestDataModels:
    """Tests for data model serialization."""

    def test_compliance_audit_content_to_dict(self, builder, comprehensive_compiled_result):
        """Test ComplianceAuditContent.to_dict()."""
        content = builder.build(comprehensive_compiled_result)
        data = content.to_dict()

        assert "content_id" in data
        assert "screening_id" in data
        assert "consent_verification" in data
        assert "compliance_rules" in data
        assert "data_sources" in data
        assert "audit_trail" in data
        assert "data_handling" in data
        assert "overall_status" in data
        assert "summary" in data

    def test_consent_verification_section_to_dict(self, builder, minimal_compiled_result):
        """Test ConsentVerificationSection.to_dict()."""
        content = builder.build(minimal_compiled_result)
        data = content.consent_verification.to_dict()

        assert "section_id" in data
        assert "consents" in data
        assert "disclosures" in data
        assert "consent_verification_complete" in data

    def test_compliance_rules_section_to_dict(
        self, builder, minimal_compiled_result, applied_rules
    ):
        """Test ComplianceRulesSection.to_dict()."""
        content = builder.build(minimal_compiled_result, applied_rules=applied_rules)
        data = content.compliance_rules.to_dict()

        assert "section_id" in data
        assert "rules_applied" in data
        assert "overall_compliance" in data

    def test_data_sources_section_to_dict(
        self, builder, minimal_compiled_result, data_source_accesses
    ):
        """Test DataSourcesSection.to_dict()."""
        content = builder.build(minimal_compiled_result, data_source_accesses=data_source_accesses)
        data = content.data_sources.to_dict()

        assert "sources_accessed" in data
        assert "total_cost" in data
        assert "average_response_time_ms" in data

    def test_audit_trail_section_to_dict(self, builder, minimal_compiled_result, audit_events):
        """Test AuditTrailSection.to_dict()."""
        content = builder.build(minimal_compiled_result, audit_events=audit_events)
        data = content.audit_trail.to_dict()

        assert "events" in data
        assert "total_events" in data
        assert "info_events" in data

    def test_data_handling_section_to_dict(self, builder, minimal_compiled_result):
        """Test DataHandlingSection.to_dict()."""
        content = builder.build(minimal_compiled_result)
        data = content.data_handling.to_dict()

        assert "attestation" in data
        assert "encryption_verified" in data
        assert "retention_period_days" in data


# =============================================================================
# Locale Tests
# =============================================================================


class TestLocale:
    """Tests for locale-specific behavior."""

    def test_us_locale_fcra_rules(self, builder, comprehensive_compiled_result):
        """Test US locale generates FCRA rules."""
        content = builder.build(comprehensive_compiled_result, locale=Locale.US)

        rule_types = [r.rule_type for r in content.compliance_rules.rules_applied]
        assert "FCRA" in rule_types

    def test_eu_locale_gdpr_rules(self, builder, comprehensive_compiled_result):
        """Test EU locale generates GDPR rules."""
        content = builder.build(comprehensive_compiled_result, locale=Locale.EU)

        rule_types = [r.rule_type for r in content.compliance_rules.rules_applied]
        assert "GDPR" in rule_types

    def test_ca_locale_pipeda_rules(self, builder, comprehensive_compiled_result):
        """Test CA locale generates PIPEDA rules."""
        content = builder.build(comprehensive_compiled_result, locale=Locale.CA)

        rule_types = [r.rule_type for r in content.compliance_rules.rules_applied]
        assert "PIPEDA" in rule_types


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_investigation_summary(self, builder):
        """Test with empty investigation summary."""
        result = CompiledResult(
            screening_id=uuid7(),
            risk_score=0,
            risk_level="low",
            recommendation="proceed",
            findings_summary=FindingsSummary(),
            investigation_summary=InvestigationSummary(types_processed=0, by_type={}),
            connection_summary=ConnectionSummary(),
        )
        content = builder.build(result)

        assert content is not None
        assert content.data_sources.total_sources == 0

    def test_all_failed_sources(self, builder, minimal_compiled_result):
        """Test with all failed data sources."""
        sources = [
            DataSourceAccess(provider_id="failed1", success=False),
            DataSourceAccess(provider_id="failed2", success=False),
        ]
        content = builder.build(minimal_compiled_result, data_source_accesses=sources)

        assert content.data_sources.successful_queries == 0
        assert content.data_sources.failed_queries == 2

    def test_unacknowledged_disclosure(self, builder, minimal_compiled_result):
        """Test with unacknowledged disclosure."""
        disclosures = [
            DisclosureRecord(
                disclosure_type="FCRA",
                acknowledged=False,
            )
        ]
        content = builder.build(minimal_compiled_result, disclosure_records=disclosures)

        assert content.consent_verification.all_disclosures_provided is False
