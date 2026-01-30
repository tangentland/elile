"""Tests for risk scoring module."""

import pytest

from elile.agent.state import RiskFinding
from elile.risk.scoring import RiskLevel, RiskScore, calculate_risk_score


class TestCalculateRiskScore:
    """Tests for calculate_risk_score function."""

    def test_empty_findings_returns_zero_score(self) -> None:
        """Empty findings should return a zero risk score."""
        result = calculate_risk_score([])

        assert result.overall_score == 0.0
        assert result.level == RiskLevel.LOW
        assert result.finding_count == 0
        assert result.high_severity_count == 0

    def test_single_low_severity_finding(self) -> None:
        """Single low severity finding should produce medium risk score.

        Note: A low-severity finding at 100% confidence yields score 0.25,
        which is at the MEDIUM threshold (score >= 0.25 = MEDIUM).
        """
        findings = [
            RiskFinding(
                category="test",
                description="Test finding",
                severity="low",
                confidence=1.0,
                sources=["source1"],
            )
        ]

        result = calculate_risk_score(findings)

        # Low severity weight (0.25) * confidence (1.0) = 0.25, which is MEDIUM threshold
        assert result.level == RiskLevel.MEDIUM
        assert result.overall_score == 0.25
        assert result.finding_count == 1
        assert result.high_severity_count == 0

    def test_high_severity_findings_increase_score(self) -> None:
        """High severity findings should increase the risk score."""
        findings = [
            RiskFinding(
                category="test",
                description="Critical finding",
                severity="critical",
                confidence=1.0,
                sources=["source1"],
            )
        ]

        result = calculate_risk_score(findings)

        assert result.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert result.high_severity_count == 1

    def test_multiple_categories_averaged(self) -> None:
        """Multiple categories should be averaged in overall score."""
        findings = [
            RiskFinding(
                category="financial",
                description="Financial finding",
                severity="high",
                confidence=1.0,
                sources=["source1"],
            ),
            RiskFinding(
                category="legal",
                description="Legal finding",
                severity="low",
                confidence=1.0,
                sources=["source2"],
            ),
        ]

        result = calculate_risk_score(findings)

        assert "financial" in result.category_scores
        assert "legal" in result.category_scores
        assert result.finding_count == 2

    def test_confidence_affects_score(self) -> None:
        """Lower confidence should reduce the effective score."""
        high_conf = [
            RiskFinding(
                category="test",
                description="High confidence",
                severity="high",
                confidence=1.0,
                sources=["source1"],
            )
        ]

        low_conf = [
            RiskFinding(
                category="test",
                description="Low confidence",
                severity="high",
                confidence=0.5,
                sources=["source1"],
            )
        ]

        high_result = calculate_risk_score(high_conf)
        low_result = calculate_risk_score(low_conf)

        assert high_result.overall_score > low_result.overall_score
