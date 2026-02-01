"""Unit tests for SeverityCalculator."""

from datetime import date, timedelta
from uuid import UUID, uuid7

import pytest

from elile.compliance.types import RoleCategory
from elile.investigation.finding_extractor import Finding, FindingCategory, Severity
from elile.risk.finding_classifier import SubCategory
from elile.risk.severity_calculator import (
    CalculatorConfig,
    ROLE_SEVERITY_ADJUSTMENTS,
    SEVERITY_RULES,
    SUBCATEGORY_SEVERITY,
    SeverityCalculator,
    SeverityDecision,
    create_severity_calculator,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def calculator() -> SeverityCalculator:
    """Create default calculator."""
    return SeverityCalculator()


@pytest.fixture
def custom_config() -> CalculatorConfig:
    """Create custom calculator config."""
    return CalculatorConfig(
        enable_role_adjustment=False,
        enable_recency_adjustment=False,
        default_severity=Severity.LOW,
    )


@pytest.fixture
def custom_calculator(custom_config: CalculatorConfig) -> SeverityCalculator:
    """Create calculator with custom config."""
    return SeverityCalculator(config=custom_config)


def create_finding(
    summary: str = "Test finding",
    details: str = "",
    finding_type: str = "",
    category: FindingCategory | None = FindingCategory.CRIMINAL,
    finding_date: date | None = None,
) -> Finding:
    """Helper to create a Finding for testing."""
    return Finding(
        summary=summary,
        details=details,
        finding_type=finding_type,
        category=category,
        finding_date=finding_date,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestSeverityCalculatorInit:
    """Tests for SeverityCalculator initialization."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        calculator = SeverityCalculator()
        assert calculator.config is not None
        assert calculator.config.use_rule_matching is True
        assert calculator.config.use_subcategory_defaults is True
        assert calculator.config.enable_role_adjustment is True
        assert calculator.config.enable_recency_adjustment is True
        assert calculator.config.default_severity == Severity.MEDIUM

    def test_init_custom_config(self, custom_config: CalculatorConfig) -> None:
        """Test initialization with custom config."""
        calculator = SeverityCalculator(config=custom_config)
        assert calculator.config.enable_role_adjustment is False
        assert calculator.config.enable_recency_adjustment is False
        assert calculator.config.default_severity == Severity.LOW

    def test_factory_function(self) -> None:
        """Test create_severity_calculator factory function."""
        calculator = create_severity_calculator()
        assert isinstance(calculator, SeverityCalculator)

    def test_factory_function_with_config(self, custom_config: CalculatorConfig) -> None:
        """Test factory function with custom config."""
        calculator = create_severity_calculator(config=custom_config)
        assert calculator.config.default_severity == Severity.LOW


# =============================================================================
# CalculatorConfig Tests
# =============================================================================


class TestCalculatorConfig:
    """Tests for CalculatorConfig validation."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = CalculatorConfig()
        assert config.use_rule_matching is True
        assert config.use_subcategory_defaults is True
        assert config.use_ai_fallback is False
        assert config.enable_role_adjustment is True
        assert config.enable_recency_adjustment is True
        assert config.recent_boost_days == 365
        assert config.recency_boost_amount == 1
        assert config.default_severity == Severity.MEDIUM

    def test_validation_bounds(self) -> None:
        """Test config validation bounds."""
        # Valid values
        config = CalculatorConfig(recent_boost_days=0, recency_boost_amount=0)
        assert config.recent_boost_days == 0
        assert config.recency_boost_amount == 0

        # Invalid recency boost
        with pytest.raises(ValueError):
            CalculatorConfig(recency_boost_amount=-1)
        with pytest.raises(ValueError):
            CalculatorConfig(recency_boost_amount=3)


# =============================================================================
# Rule Matching Tests
# =============================================================================


class TestRuleMatching:
    """Tests for rule-based severity matching."""

    def test_critical_felony_conviction(self, calculator: SeverityCalculator) -> None:
        """Test CRITICAL severity for felony conviction."""
        finding = create_finding(summary="Felony conviction for assault")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.CRITICAL
        assert decision.determination_method == "rule"
        assert "felony conviction" in decision.matched_rules

    def test_critical_active_warrant(self, calculator: SeverityCalculator) -> None:
        """Test CRITICAL severity for active warrant."""
        finding = create_finding(summary="Active warrant for subject")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.CRITICAL
        assert "active warrant" in decision.matched_rules

    def test_critical_sex_offense(self, calculator: SeverityCalculator) -> None:
        """Test CRITICAL severity for sex offense."""
        finding = create_finding(summary="Registered sex offense conviction")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.CRITICAL
        assert "sex offense" in decision.matched_rules

    def test_critical_ofac_sanction(self, calculator: SeverityCalculator) -> None:
        """Test CRITICAL severity for OFAC sanction."""
        finding = create_finding(summary="Subject on OFAC sanction list")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.CRITICAL
        assert "ofac sanction" in decision.matched_rules

    def test_high_recent_bankruptcy(self, calculator: SeverityCalculator) -> None:
        """Test HIGH severity for recent bankruptcy."""
        finding = create_finding(summary="Recent bankruptcy filed in 2025")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.HIGH
        assert "recent bankruptcy" in decision.matched_rules

    def test_high_license_revocation(self, calculator: SeverityCalculator) -> None:
        """Test HIGH severity for license revocation."""
        finding = create_finding(summary="Medical license revocation")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.HIGH
        assert "license revocation" in decision.matched_rules

    def test_high_dui_conviction(self, calculator: SeverityCalculator) -> None:
        """Test HIGH severity for DUI conviction."""
        finding = create_finding(summary="DUI conviction in California")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.HIGH
        assert "dui conviction" in decision.matched_rules

    def test_medium_misdemeanor(self, calculator: SeverityCalculator) -> None:
        """Test MEDIUM severity for misdemeanor."""
        finding = create_finding(summary="Misdemeanor conviction for trespass")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.MEDIUM
        assert "misdemeanor conviction" in decision.matched_rules

    def test_medium_civil_judgment(self, calculator: SeverityCalculator) -> None:
        """Test MEDIUM severity for civil judgment."""
        finding = create_finding(summary="Civil judgment filed against subject")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.MEDIUM
        assert "civil judgment" in decision.matched_rules

    def test_low_employment_gap(self, calculator: SeverityCalculator) -> None:
        """Test LOW severity for employment gap."""
        finding = create_finding(summary="Employment gap detected in 2020")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.LOW
        assert "employment gap" in decision.matched_rules

    def test_low_address_discrepancy(self, calculator: SeverityCalculator) -> None:
        """Test LOW severity for address discrepancy."""
        finding = create_finding(summary="Minor address discrepancy found")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.LOW
        assert "address discrepancy" in decision.matched_rules

    def test_highest_severity_wins(self, calculator: SeverityCalculator) -> None:
        """Test highest severity is used when multiple rules match."""
        # Finding matches both critical (felony) and medium (misdemeanor)
        finding = create_finding(
            summary="Felony conviction, prior misdemeanor conviction history"
        )
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.CRITICAL
        assert "felony conviction" in decision.matched_rules
        assert "misdemeanor conviction" in decision.matched_rules

    def test_case_insensitive_matching(self, calculator: SeverityCalculator) -> None:
        """Test rule matching is case-insensitive."""
        finding = create_finding(summary="FELONY CONVICTION for theft")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.CRITICAL


# =============================================================================
# Subcategory Default Tests
# =============================================================================


class TestSubcategoryDefaults:
    """Tests for subcategory-based severity defaults."""

    def test_criminal_felony_subcategory(self, calculator: SeverityCalculator) -> None:
        """Test CRITICAL from CRIMINAL_FELONY subcategory."""
        finding = create_finding(summary="Generic criminal finding")
        severity, decision = calculator.calculate_severity(
            finding, subcategory=SubCategory.CRIMINAL_FELONY
        )

        assert severity == Severity.CRITICAL
        assert decision.determination_method == "subcategory"

    def test_financial_bankruptcy_subcategory(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test HIGH from FINANCIAL_BANKRUPTCY subcategory."""
        finding = create_finding(summary="Generic financial finding")
        severity, decision = calculator.calculate_severity(
            finding, subcategory=SubCategory.FINANCIAL_BANKRUPTCY
        )

        assert severity == Severity.HIGH
        assert decision.determination_method == "subcategory"

    def test_verification_gap_subcategory(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test LOW from VERIFICATION_GAP subcategory."""
        finding = create_finding(summary="Generic verification finding")
        severity, decision = calculator.calculate_severity(
            finding, subcategory=SubCategory.VERIFICATION_GAP
        )

        assert severity == Severity.LOW
        assert decision.determination_method == "subcategory"

    def test_rule_takes_precedence_over_subcategory(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test rules are checked before subcategory defaults."""
        finding = create_finding(summary="Felony conviction for theft")
        # Even with a LOW subcategory, rule should match CRITICAL
        severity, decision = calculator.calculate_severity(
            finding, subcategory=SubCategory.VERIFICATION_GAP
        )

        assert severity == Severity.CRITICAL
        assert decision.determination_method == "rule"


# =============================================================================
# Default Severity Tests
# =============================================================================


class TestDefaultSeverity:
    """Tests for default severity when no rules match."""

    def test_default_severity_when_no_match(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test MEDIUM default when no rules match."""
        finding = create_finding(summary="Some generic finding with no keywords")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.MEDIUM
        assert decision.determination_method == "default"

    def test_custom_default_severity(
        self, custom_calculator: SeverityCalculator
    ) -> None:
        """Test custom default severity from config."""
        finding = create_finding(summary="Some generic finding")
        severity, decision = custom_calculator.calculate_severity(finding)

        assert severity == Severity.LOW  # Custom default


# =============================================================================
# Role Adjustment Tests
# =============================================================================


class TestRoleAdjustment:
    """Tests for role-based severity adjustment."""

    def test_criminal_government_role_boost(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test criminal findings boosted for government role."""
        finding = create_finding(
            summary="Some generic criminal issue",
            category=FindingCategory.CRIMINAL,
        )
        # Default is MEDIUM, with +1 adjustment should be HIGH
        severity, decision = calculator.calculate_severity(
            finding, role_category=RoleCategory.GOVERNMENT
        )

        assert decision.role_adjustment == 1
        assert severity == Severity.HIGH

    def test_criminal_security_role_boost(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test criminal findings boosted for security role."""
        finding = create_finding(
            summary="Some generic criminal issue",
            category=FindingCategory.CRIMINAL,
        )
        severity, decision = calculator.calculate_severity(
            finding, role_category=RoleCategory.SECURITY
        )

        assert decision.role_adjustment == 1

    def test_financial_financial_role_boost(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test financial findings boosted for financial role."""
        finding = create_finding(
            summary="Some generic financial issue",
            category=FindingCategory.FINANCIAL,
        )
        severity, decision = calculator.calculate_severity(
            finding, role_category=RoleCategory.FINANCIAL
        )

        assert decision.role_adjustment == 1

    def test_no_adjustment_for_standard_role(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test no adjustment for standard role."""
        finding = create_finding(
            summary="Some generic criminal issue",
            category=FindingCategory.CRIMINAL,
        )
        severity, decision = calculator.calculate_severity(
            finding, role_category=RoleCategory.STANDARD
        )

        assert decision.role_adjustment == 0

    def test_role_adjustment_disabled(
        self, custom_calculator: SeverityCalculator
    ) -> None:
        """Test role adjustment disabled in config."""
        finding = create_finding(
            summary="Some generic criminal issue",
            category=FindingCategory.CRIMINAL,
        )
        severity, decision = custom_calculator.calculate_severity(
            finding, role_category=RoleCategory.GOVERNMENT
        )

        # Should have no adjustment even though rule would normally apply
        assert decision.role_adjustment == 0

    def test_severity_capped_at_critical(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test severity doesn't exceed CRITICAL after adjustment."""
        # Felony conviction = CRITICAL, +1 adjustment should still be CRITICAL
        finding = create_finding(
            summary="Felony conviction for assault",
            category=FindingCategory.CRIMINAL,
        )
        severity, decision = calculator.calculate_severity(
            finding, role_category=RoleCategory.GOVERNMENT
        )

        assert severity == Severity.CRITICAL
        assert decision.role_adjustment == 1


# =============================================================================
# Recency Adjustment Tests
# =============================================================================


class TestRecencyAdjustment:
    """Tests for recency-based severity adjustment."""

    def test_recent_finding_gets_boost(self, calculator: SeverityCalculator) -> None:
        """Test recent finding (within 365 days) gets severity boost."""
        finding = create_finding(
            summary="Some generic finding",
            finding_date=date.today() - timedelta(days=100),
        )
        severity, decision = calculator.calculate_severity(finding)

        assert decision.recency_adjustment == 1
        # MEDIUM (default) + 1 = HIGH
        assert severity == Severity.HIGH

    def test_old_finding_no_boost(self, calculator: SeverityCalculator) -> None:
        """Test old finding (>365 days) gets no boost."""
        finding = create_finding(
            summary="Some generic finding",
            finding_date=date.today() - timedelta(days=500),
        )
        severity, decision = calculator.calculate_severity(finding)

        assert decision.recency_adjustment == 0

    def test_no_date_no_boost(self, calculator: SeverityCalculator) -> None:
        """Test finding with no date gets no boost."""
        finding = create_finding(summary="Some generic finding", finding_date=None)
        severity, decision = calculator.calculate_severity(finding)

        assert decision.recency_adjustment == 0

    def test_recency_adjustment_disabled(
        self, custom_calculator: SeverityCalculator
    ) -> None:
        """Test recency adjustment disabled in config."""
        finding = create_finding(
            summary="Some generic finding",
            finding_date=date.today() - timedelta(days=100),
        )
        severity, decision = custom_calculator.calculate_severity(finding)

        assert decision.recency_adjustment == 0


# =============================================================================
# Combined Adjustments Tests
# =============================================================================


class TestCombinedAdjustments:
    """Tests for combined role and recency adjustments."""

    def test_both_adjustments_applied(self, calculator: SeverityCalculator) -> None:
        """Test both role and recency adjustments are applied."""
        finding = create_finding(
            summary="Some generic criminal issue",
            category=FindingCategory.CRIMINAL,
            finding_date=date.today() - timedelta(days=100),
        )
        severity, decision = calculator.calculate_severity(
            finding, role_category=RoleCategory.GOVERNMENT
        )

        # MEDIUM + 1 (role) + 1 (recency) = CRITICAL
        assert decision.role_adjustment == 1
        assert decision.recency_adjustment == 1
        assert severity == Severity.CRITICAL

    def test_severity_capped_at_critical_combined(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test severity capped at CRITICAL with combined adjustments."""
        # High severity + 2 adjustments should cap at CRITICAL
        finding = create_finding(
            summary="DUI conviction",  # HIGH
            category=FindingCategory.CRIMINAL,
            finding_date=date.today() - timedelta(days=100),
        )
        severity, decision = calculator.calculate_severity(
            finding, role_category=RoleCategory.GOVERNMENT
        )

        assert severity == Severity.CRITICAL


# =============================================================================
# Batch Processing Tests
# =============================================================================


class TestBatchProcessing:
    """Tests for batch severity calculation."""

    def test_calculate_severities_batch(self, calculator: SeverityCalculator) -> None:
        """Test batch severity calculation."""
        findings = [
            create_finding(summary="Felony conviction"),
            create_finding(summary="Employment gap"),
            create_finding(summary="Generic finding"),
        ]
        results = calculator.calculate_severities(findings)

        assert len(results) == 3
        assert results[0][0] == Severity.CRITICAL  # Felony
        assert results[1][0] == Severity.LOW  # Employment gap
        assert results[2][0] == Severity.MEDIUM  # Default

    def test_batch_updates_findings(self, calculator: SeverityCalculator) -> None:
        """Test batch calculation updates finding.severity."""
        findings = [create_finding(summary="Felony conviction")]
        calculator.calculate_severities(findings, update_findings=True)

        assert findings[0].severity == Severity.CRITICAL

    def test_batch_no_update_when_disabled(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test batch calculation doesn't update when disabled."""
        findings = [create_finding(summary="Felony conviction")]
        original_severity = findings[0].severity
        calculator.calculate_severities(findings, update_findings=False)

        assert findings[0].severity == original_severity

    def test_batch_with_subcategories(self, calculator: SeverityCalculator) -> None:
        """Test batch calculation with subcategory mapping."""
        findings = [
            create_finding(summary="Generic finding 1"),
            create_finding(summary="Generic finding 2"),
        ]
        subcategories = {
            findings[0].finding_id: SubCategory.CRIMINAL_FELONY,
            findings[1].finding_id: SubCategory.VERIFICATION_GAP,
        }
        results = calculator.calculate_severities(
            findings, subcategories=subcategories
        )

        assert results[0][0] == Severity.CRITICAL
        assert results[1][0] == Severity.LOW


# =============================================================================
# SeverityDecision Tests
# =============================================================================


class TestSeverityDecision:
    """Tests for SeverityDecision dataclass."""

    def test_default_values(self) -> None:
        """Test default SeverityDecision values."""
        decision = SeverityDecision()

        assert isinstance(decision.decision_id, UUID)
        assert decision.finding_id is None
        assert decision.initial_severity == Severity.MEDIUM
        assert decision.final_severity == Severity.MEDIUM
        assert decision.determination_method == "rule"
        assert decision.matched_rules == []
        assert decision.role_adjustment == 0
        assert decision.recency_adjustment == 0
        assert decision.context_notes == []
        assert decision.decided_at is not None

    def test_to_dict(self) -> None:
        """Test SeverityDecision to_dict method."""
        finding_id = uuid7()
        decision = SeverityDecision(
            finding_id=finding_id,
            initial_severity=Severity.MEDIUM,
            final_severity=Severity.HIGH,
            determination_method="rule",
            matched_rules=["dui conviction"],
            role_adjustment=1,
            context_notes=["Role boost for government"],
        )
        d = decision.to_dict()

        assert "decision_id" in d
        assert d["finding_id"] == str(finding_id)
        assert d["initial_severity"] == "medium"
        assert d["final_severity"] == "high"
        assert d["determination_method"] == "rule"
        assert d["matched_rules"] == ["dui conviction"]
        assert d["role_adjustment"] == 1


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for severity rule constants."""

    def test_severity_rules_exist(self) -> None:
        """Test SEVERITY_RULES has entries."""
        assert len(SEVERITY_RULES) > 0

        # Check some critical patterns
        assert SEVERITY_RULES["felony conviction"] == Severity.CRITICAL
        assert SEVERITY_RULES["active warrant"] == Severity.CRITICAL

        # Check some high patterns
        assert SEVERITY_RULES["recent bankruptcy"] == Severity.HIGH
        assert SEVERITY_RULES["dui conviction"] == Severity.HIGH

        # Check some low patterns
        assert SEVERITY_RULES["employment gap"] == Severity.LOW

    def test_subcategory_severity_mapping(self) -> None:
        """Test SUBCATEGORY_SEVERITY has all subcategories."""
        for subcategory in SubCategory:
            assert subcategory in SUBCATEGORY_SEVERITY

    def test_role_severity_adjustments(self) -> None:
        """Test ROLE_SEVERITY_ADJUSTMENTS has expected entries."""
        # Check government criminal boost
        assert (FindingCategory.CRIMINAL, RoleCategory.GOVERNMENT) in ROLE_SEVERITY_ADJUSTMENTS
        assert (
            ROLE_SEVERITY_ADJUSTMENTS[(FindingCategory.CRIMINAL, RoleCategory.GOVERNMENT)]
            == 1
        )


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_finding_text(self, calculator: SeverityCalculator) -> None:
        """Test handling of empty finding text."""
        finding = create_finding(summary="", details="", finding_type="")
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.MEDIUM
        assert decision.determination_method == "default"

    def test_finding_without_category(self, calculator: SeverityCalculator) -> None:
        """Test handling of finding without category."""
        finding = create_finding(summary="Generic finding", category=None)
        severity, decision = calculator.calculate_severity(
            finding, role_category=RoleCategory.GOVERNMENT
        )

        # No category means no role adjustment
        assert decision.role_adjustment == 0

    def test_text_in_details_matches(self, calculator: SeverityCalculator) -> None:
        """Test rules match text in finding details."""
        finding = create_finding(
            summary="Criminal record found",
            details="Subject has felony conviction for fraud",
        )
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.CRITICAL
        assert "felony conviction" in decision.matched_rules

    def test_text_in_finding_type_matches(
        self, calculator: SeverityCalculator
    ) -> None:
        """Test rules match text in finding_type."""
        finding = create_finding(
            summary="Record found",
            finding_type="felony conviction assault",
        )
        severity, decision = calculator.calculate_severity(finding)

        assert severity == Severity.CRITICAL
        assert "felony conviction" in decision.matched_rules

    def test_rule_matching_disabled(self) -> None:
        """Test behavior when rule matching is disabled."""
        config = CalculatorConfig(
            use_rule_matching=False,
            use_subcategory_defaults=False,
        )
        calculator = SeverityCalculator(config=config)

        finding = create_finding(summary="Felony conviction")
        severity, decision = calculator.calculate_severity(finding)

        # Should use default, not match rule
        assert decision.determination_method == "default"
        assert severity == Severity.MEDIUM

    def test_subcategory_defaults_disabled(self) -> None:
        """Test behavior when subcategory defaults are disabled."""
        config = CalculatorConfig(
            use_rule_matching=False,
            use_subcategory_defaults=False,
        )
        calculator = SeverityCalculator(config=config)

        finding = create_finding(summary="Generic finding")
        severity, decision = calculator.calculate_severity(
            finding, subcategory=SubCategory.CRIMINAL_FELONY
        )

        # Should use default, not subcategory
        assert decision.determination_method == "default"
        assert severity == Severity.MEDIUM
