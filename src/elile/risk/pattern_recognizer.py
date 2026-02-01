"""Pattern Recognizer for identifying risk patterns in findings.

This module provides the PatternRecognizer that:
1. Detects escalation patterns (increasing severity over time)
2. Identifies frequency anomalies (clustering of findings)
3. Recognizes cross-domain patterns (issues spanning categories)
4. Performs temporal trend analysis
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.core.logging import get_logger
from elile.investigation.finding_extractor import Finding, FindingCategory, Severity

logger = get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class PatternType(str, Enum):
    """Types of patterns that can be recognized."""

    # Escalation patterns
    SEVERITY_ESCALATION = "severity_escalation"
    FREQUENCY_ESCALATION = "frequency_escalation"

    # Frequency patterns
    BURST_ACTIVITY = "burst_activity"
    RECURRING_ISSUES = "recurring_issues"
    PERIODIC_PATTERN = "periodic_pattern"

    # Cross-domain patterns
    MULTI_CATEGORY = "multi_category"
    SYSTEMIC_ISSUES = "systemic_issues"
    CORRELATED_FINDINGS = "correlated_findings"

    # Temporal patterns
    TIMELINE_CLUSTER = "timeline_cluster"
    DORMANT_PERIOD = "dormant_period"
    RECENT_CONCENTRATION = "recent_concentration"

    # Behavioral patterns
    REPEAT_OFFENDER = "repeat_offender"
    PROGRESSIVE_DEGRADATION = "progressive_degradation"
    IMPROVEMENT_TREND = "improvement_trend"


# Severity ranking for comparison
SEVERITY_RANK: dict[Severity, int] = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Default pattern severity
PATTERN_DEFAULT_SEVERITY: dict[PatternType, Severity] = {
    PatternType.SEVERITY_ESCALATION: Severity.HIGH,
    PatternType.FREQUENCY_ESCALATION: Severity.MEDIUM,
    PatternType.BURST_ACTIVITY: Severity.MEDIUM,
    PatternType.RECURRING_ISSUES: Severity.HIGH,
    PatternType.PERIODIC_PATTERN: Severity.MEDIUM,
    PatternType.MULTI_CATEGORY: Severity.MEDIUM,
    PatternType.SYSTEMIC_ISSUES: Severity.HIGH,
    PatternType.CORRELATED_FINDINGS: Severity.MEDIUM,
    PatternType.TIMELINE_CLUSTER: Severity.LOW,
    PatternType.DORMANT_PERIOD: Severity.LOW,
    PatternType.RECENT_CONCENTRATION: Severity.MEDIUM,
    PatternType.REPEAT_OFFENDER: Severity.HIGH,
    PatternType.PROGRESSIVE_DEGRADATION: Severity.HIGH,
    PatternType.IMPROVEMENT_TREND: Severity.LOW,
}


# =============================================================================
# Models
# =============================================================================


@dataclass
class Pattern:
    """A recognized pattern in subject data.

    Patterns represent identifiable trends, clusters, or behavioral
    signals that emerge from analyzing multiple findings.
    """

    pattern_id: UUID = field(default_factory=uuid7)
    pattern_type: PatternType = PatternType.MULTI_CATEGORY
    severity: Severity = Severity.MEDIUM
    confidence: float = 0.5  # 0.0-1.0
    description: str = ""
    evidence: list[str] = field(default_factory=list)
    affected_categories: list[FindingCategory] = field(default_factory=list)
    related_findings: list[UUID] = field(default_factory=list)
    time_span: timedelta | None = None
    start_date: date | None = None
    end_date: date | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    recognized_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern_id": str(self.pattern_id),
            "pattern_type": self.pattern_type.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "description": self.description,
            "evidence": self.evidence,
            "affected_categories": [c.value for c in self.affected_categories],
            "related_findings": [str(f) for f in self.related_findings],
            "time_span_days": self.time_span.days if self.time_span else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "metadata": self.metadata,
            "recognized_at": self.recognized_at.isoformat(),
        }


@dataclass
class PatternSummary:
    """Summary of all recognized patterns."""

    summary_id: UUID = field(default_factory=uuid7)
    total_patterns: int = 0
    patterns_by_type: dict[PatternType, int] = field(default_factory=dict)
    highest_severity: Severity | None = None
    risk_score: float = 0.0  # 0.0-1.0
    key_concerns: list[str] = field(default_factory=list)
    analyzed_findings: int = 0
    analysis_period: timedelta | None = None
    summarized_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary_id": str(self.summary_id),
            "total_patterns": self.total_patterns,
            "patterns_by_type": {k.value: v for k, v in self.patterns_by_type.items()},
            "highest_severity": self.highest_severity.value if self.highest_severity else None,
            "risk_score": self.risk_score,
            "key_concerns": self.key_concerns,
            "analyzed_findings": self.analyzed_findings,
            "analysis_period_days": self.analysis_period.days if self.analysis_period else None,
            "summarized_at": self.summarized_at.isoformat(),
        }


class RecognizerConfig(BaseModel):
    """Configuration for pattern recognizer."""

    # Escalation detection
    escalation_window_days: int = Field(
        default=365, ge=30, description="Window for escalation detection"
    )
    min_findings_for_escalation: int = Field(
        default=3, ge=2, description="Minimum findings for escalation pattern"
    )

    # Frequency detection
    burst_window_days: int = Field(default=90, ge=7, description="Window for burst detection")
    burst_threshold: int = Field(default=3, ge=2, description="Findings in window for burst")
    recurring_threshold: int = Field(
        default=2, ge=2, description="Same type findings for recurring"
    )

    # Cross-domain detection
    min_categories_for_multi: int = Field(
        default=3, ge=2, description="Categories for multi-category pattern"
    )
    systemic_threshold: int = Field(
        default=5, ge=3, description="Findings for systemic issues"
    )

    # Temporal detection
    recent_days: int = Field(default=180, ge=30, description="Days considered 'recent'")
    dormant_threshold_days: int = Field(
        default=730, ge=365, description="Days for dormant period"
    )

    # Behavioral detection
    repeat_threshold: int = Field(default=3, ge=2, description="Count for repeat offender")

    # General
    min_confidence: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Minimum pattern confidence"
    )


# =============================================================================
# Pattern Recognizer
# =============================================================================


class PatternRecognizer:
    """Recognizes behavioral patterns in findings.

    The PatternRecognizer analyzes findings to identify:
    - Escalation patterns (increasing severity/frequency)
    - Frequency patterns (bursts, recurring issues)
    - Cross-domain patterns (issues spanning categories)
    - Temporal patterns (clusters, recent concentration)
    - Behavioral patterns (repeat offender, degradation)

    Example:
        ```python
        recognizer = PatternRecognizer()

        patterns = recognizer.recognize_patterns(findings)

        for pattern in patterns:
            print(f"{pattern.pattern_type.value}: {pattern.description}")

        summary = recognizer.summarize_patterns(patterns, findings)
        print(f"Risk score: {summary.risk_score}")
        ```
    """

    def __init__(self, config: RecognizerConfig | None = None):
        """Initialize the pattern recognizer.

        Args:
            config: Recognizer configuration.
        """
        self.config = config or RecognizerConfig()

    def recognize_patterns(self, findings: list[Finding]) -> list[Pattern]:
        """Recognize all patterns in findings.

        Args:
            findings: List of findings to analyze.

        Returns:
            List of recognized patterns.
        """
        if not findings:
            return []

        patterns: list[Pattern] = []

        # Escalation patterns
        patterns.extend(self._detect_escalation_patterns(findings))

        # Frequency patterns
        patterns.extend(self._detect_frequency_patterns(findings))

        # Cross-domain patterns
        patterns.extend(self._detect_cross_domain_patterns(findings))

        # Temporal patterns
        patterns.extend(self._detect_temporal_patterns(findings))

        # Behavioral patterns
        patterns.extend(self._detect_behavioral_patterns(findings))

        # Filter by minimum confidence
        patterns = [p for p in patterns if p.confidence >= self.config.min_confidence]

        logger.info(
            "Patterns recognized",
            total=len(patterns),
            by_type={t.value: sum(1 for p in patterns if p.pattern_type == t) for t in PatternType},
        )

        return patterns

    def summarize_patterns(
        self,
        patterns: list[Pattern],
        findings: list[Finding],
    ) -> PatternSummary:
        """Create summary of recognized patterns.

        Args:
            patterns: Recognized patterns.
            findings: Analyzed findings.

        Returns:
            Pattern summary with risk assessment.
        """
        if not patterns:
            return PatternSummary(analyzed_findings=len(findings))

        # Count by type
        by_type: dict[PatternType, int] = defaultdict(int)
        for pattern in patterns:
            by_type[pattern.pattern_type] += 1

        # Find highest severity
        highest = max(patterns, key=lambda p: SEVERITY_RANK.get(p.severity, 0))

        # Calculate risk score
        risk_score = self._calculate_risk_score(patterns)

        # Identify key concerns
        concerns = self._identify_key_concerns(patterns)

        # Calculate analysis period
        dated = [f for f in findings if f.finding_date]
        period = None
        if dated:
            dates = [f.finding_date for f in dated]
            period = timedelta(days=(max(dates) - min(dates)).days)  # type: ignore

        return PatternSummary(
            total_patterns=len(patterns),
            patterns_by_type=dict(by_type),
            highest_severity=highest.severity,
            risk_score=risk_score,
            key_concerns=concerns,
            analyzed_findings=len(findings),
            analysis_period=period,
        )

    def _detect_escalation_patterns(self, findings: list[Finding]) -> list[Pattern]:
        """Detect escalation patterns (increasing severity/frequency).

        Args:
            findings: Findings to analyze.

        Returns:
            List of escalation patterns.
        """
        patterns: list[Pattern] = []

        # Need dated findings for escalation
        dated = [(f, f.finding_date) for f in findings if f.finding_date]
        if len(dated) < self.config.min_findings_for_escalation:
            return patterns

        # Sort by date
        dated.sort(key=lambda x: x[1])  # type: ignore

        # Check for severity escalation
        severity_pattern = self._check_severity_escalation(dated)
        if severity_pattern:
            patterns.append(severity_pattern)

        # Check for frequency escalation
        freq_pattern = self._check_frequency_escalation(dated)
        if freq_pattern:
            patterns.append(freq_pattern)

        return patterns

    def _check_severity_escalation(
        self, dated_findings: list[tuple[Finding, date]]
    ) -> Pattern | None:
        """Check for increasing severity over time.

        Args:
            dated_findings: Findings sorted by date.

        Returns:
            Pattern if escalation detected.
        """
        if len(dated_findings) < 3:
            return None

        # Compare first half to second half
        mid = len(dated_findings) // 2
        first_half = dated_findings[:mid]
        second_half = dated_findings[mid:]

        first_avg = sum(SEVERITY_RANK.get(f.severity, 2) for f, _ in first_half) / len(first_half)
        second_avg = sum(SEVERITY_RANK.get(f.severity, 2) for f, _ in second_half) / len(
            second_half
        )

        # Check if severity increased by at least 0.5 levels on average
        if second_avg - first_avg >= 0.5:
            span = dated_findings[-1][1] - dated_findings[0][1]
            return Pattern(
                pattern_type=PatternType.SEVERITY_ESCALATION,
                severity=Severity.HIGH,
                confidence=min(0.9, 0.5 + (second_avg - first_avg) * 0.2),
                description=f"Severity escalation detected over {span.days} days: average increased from {first_avg:.1f} to {second_avg:.1f}",
                evidence=[
                    f"First half avg severity: {first_avg:.2f}",
                    f"Second half avg severity: {second_avg:.2f}",
                    f"Increase: {(second_avg - first_avg):.2f}",
                ],
                related_findings=[f.finding_id for f, _ in dated_findings],
                time_span=span,
                start_date=dated_findings[0][1],
                end_date=dated_findings[-1][1],
                metadata={
                    "first_half_avg": first_avg,
                    "second_half_avg": second_avg,
                    "increase": second_avg - first_avg,
                },
            )

        return None

    def _check_frequency_escalation(
        self, dated_findings: list[tuple[Finding, date]]
    ) -> Pattern | None:
        """Check for increasing frequency over time.

        Args:
            dated_findings: Findings sorted by date.

        Returns:
            Pattern if escalation detected.
        """
        if len(dated_findings) < 4:
            return None

        # Divide into early and recent periods
        total_days = (dated_findings[-1][1] - dated_findings[0][1]).days
        if total_days < 60:  # Need at least 60 days of data
            return None

        mid_date = dated_findings[0][1] + timedelta(days=total_days // 2)
        early = [f for f in dated_findings if f[1] < mid_date]
        recent = [f for f in dated_findings if f[1] >= mid_date]

        if not early or not recent:
            return None

        early_days = max(1, (mid_date - dated_findings[0][1]).days)
        recent_days = max(1, (dated_findings[-1][1] - mid_date).days)

        early_rate = len(early) / early_days * 30  # Per month
        recent_rate = len(recent) / recent_days * 30

        # Check if frequency doubled
        if recent_rate > early_rate * 1.5 and recent_rate >= 1:
            span = dated_findings[-1][1] - dated_findings[0][1]
            return Pattern(
                pattern_type=PatternType.FREQUENCY_ESCALATION,
                severity=Severity.MEDIUM,
                confidence=min(0.85, 0.4 + (recent_rate / early_rate) * 0.1),
                description=f"Frequency escalation: {early_rate:.1f}/month → {recent_rate:.1f}/month",
                evidence=[
                    f"Early period: {len(early)} findings over {early_days} days",
                    f"Recent period: {len(recent)} findings over {recent_days} days",
                ],
                related_findings=[f.finding_id for f, _ in dated_findings],
                time_span=span,
                start_date=dated_findings[0][1],
                end_date=dated_findings[-1][1],
                metadata={
                    "early_rate_per_month": early_rate,
                    "recent_rate_per_month": recent_rate,
                    "increase_factor": recent_rate / early_rate if early_rate > 0 else 0,
                },
            )

        return None

    def _detect_frequency_patterns(self, findings: list[Finding]) -> list[Pattern]:
        """Detect frequency-based patterns.

        Args:
            findings: Findings to analyze.

        Returns:
            List of frequency patterns.
        """
        patterns: list[Pattern] = []

        # Burst activity
        burst = self._detect_burst_activity(findings)
        if burst:
            patterns.append(burst)

        # Recurring issues (same type)
        recurring = self._detect_recurring_issues(findings)
        patterns.extend(recurring)

        return patterns

    def _detect_burst_activity(self, findings: list[Finding]) -> Pattern | None:
        """Detect burst of findings in short period.

        Args:
            findings: Findings to analyze.

        Returns:
            Pattern if burst detected.
        """
        dated = [f for f in findings if f.finding_date]
        if len(dated) < self.config.burst_threshold:
            return None

        # Check if findings cluster within burst window
        today = date.today()
        window_start = today - timedelta(days=self.config.burst_window_days)

        recent = [f for f in dated if f.finding_date and f.finding_date >= window_start]

        if len(recent) >= self.config.burst_threshold:
            categories = set(f.category for f in recent if f.category)
            return Pattern(
                pattern_type=PatternType.BURST_ACTIVITY,
                severity=Severity.MEDIUM,
                confidence=min(0.85, 0.5 + len(recent) * 0.05),
                description=f"Burst of {len(recent)} findings in past {self.config.burst_window_days} days",
                evidence=[
                    f"{len(recent)} findings within {self.config.burst_window_days}-day window",
                    f"Affected categories: {', '.join(c.value for c in categories if c)}",
                ],
                affected_categories=list(categories),
                related_findings=[f.finding_id for f in recent],
                time_span=timedelta(days=self.config.burst_window_days),
                metadata={
                    "count": len(recent),
                    "window_days": self.config.burst_window_days,
                },
            )

        return None

    def _detect_recurring_issues(self, findings: list[Finding]) -> list[Pattern]:
        """Detect recurring issues of the same type.

        Args:
            findings: Findings to analyze.

        Returns:
            List of recurring issue patterns.
        """
        patterns: list[Pattern] = []

        # Group by finding_type
        by_type: dict[str, list[Finding]] = defaultdict(list)
        for finding in findings:
            if finding.finding_type:
                by_type[finding.finding_type].append(finding)

        for finding_type, type_findings in by_type.items():
            if len(type_findings) >= self.config.recurring_threshold:
                # Get date range
                dated = [f for f in type_findings if f.finding_date]
                span = None
                start = None
                end = None
                if len(dated) >= 2:
                    dates = sorted(f.finding_date for f in dated)  # type: ignore
                    start = dates[0]
                    end = dates[-1]
                    span = end - start

                patterns.append(
                    Pattern(
                        pattern_type=PatternType.RECURRING_ISSUES,
                        severity=Severity.HIGH,
                        confidence=min(0.9, 0.5 + len(type_findings) * 0.1),
                        description=f"Recurring {finding_type}: {len(type_findings)} occurrences",
                        evidence=[
                            f"{len(type_findings)} instances of '{finding_type}'",
                            f"Span: {span.days if span else 'unknown'} days",
                        ],
                        related_findings=[f.finding_id for f in type_findings],
                        time_span=span,
                        start_date=start,
                        end_date=end,
                        metadata={
                            "finding_type": finding_type,
                            "count": len(type_findings),
                        },
                    )
                )

        return patterns

    def _detect_cross_domain_patterns(self, findings: list[Finding]) -> list[Pattern]:
        """Detect patterns spanning multiple categories.

        Args:
            findings: Findings to analyze.

        Returns:
            List of cross-domain patterns.
        """
        patterns: list[Pattern] = []

        # Group by category
        by_category: dict[FindingCategory, list[Finding]] = defaultdict(list)
        for finding in findings:
            if finding.category:
                by_category[finding.category].append(finding)

        categories_with_findings = [c for c in by_category.keys()]

        # Multi-category pattern
        if len(categories_with_findings) >= self.config.min_categories_for_multi:
            all_ids = [f.finding_id for findings_list in by_category.values() for f in findings_list]
            patterns.append(
                Pattern(
                    pattern_type=PatternType.MULTI_CATEGORY,
                    severity=Severity.MEDIUM,
                    confidence=min(0.8, 0.4 + len(categories_with_findings) * 0.1),
                    description=f"Issues span {len(categories_with_findings)} categories",
                    evidence=[
                        f"{c.value}: {len(fl)} findings"
                        for c, fl in by_category.items()
                    ],
                    affected_categories=categories_with_findings,
                    related_findings=all_ids,
                    metadata={
                        "category_count": len(categories_with_findings),
                        "category_breakdown": {c.value: len(fl) for c, fl in by_category.items()},
                    },
                )
            )

        # Systemic issues (many findings across domains)
        if len(findings) >= self.config.systemic_threshold:
            high_severity = [f for f in findings if f.severity in (Severity.HIGH, Severity.CRITICAL)]
            if len(high_severity) >= 3:
                patterns.append(
                    Pattern(
                        pattern_type=PatternType.SYSTEMIC_ISSUES,
                        severity=Severity.HIGH,
                        confidence=min(0.9, 0.5 + len(high_severity) * 0.1),
                        description=f"Systemic issues: {len(high_severity)} high/critical findings",
                        evidence=[
                            f"{len(high_severity)} high/critical severity findings",
                            f"Total findings: {len(findings)}",
                        ],
                        affected_categories=categories_with_findings,
                        related_findings=[f.finding_id for f in high_severity],
                        metadata={
                            "high_severity_count": len(high_severity),
                            "total_findings": len(findings),
                        },
                    )
                )

        return patterns

    def _detect_temporal_patterns(self, findings: list[Finding]) -> list[Pattern]:
        """Detect temporal patterns.

        Args:
            findings: Findings to analyze.

        Returns:
            List of temporal patterns.
        """
        patterns: list[Pattern] = []

        dated = [f for f in findings if f.finding_date]
        if not dated:
            return patterns

        today = date.today()
        recent_cutoff = today - timedelta(days=self.config.recent_days)

        # Recent concentration
        recent = [f for f in dated if f.finding_date and f.finding_date >= recent_cutoff]
        older = [f for f in dated if f.finding_date and f.finding_date < recent_cutoff]

        if len(recent) > len(older) and len(recent) >= 2:
            patterns.append(
                Pattern(
                    pattern_type=PatternType.RECENT_CONCENTRATION,
                    severity=Severity.MEDIUM,
                    confidence=min(0.8, 0.5 + (len(recent) - len(older)) * 0.05),
                    description=f"Recent concentration: {len(recent)} recent vs {len(older)} older findings",
                    evidence=[
                        f"{len(recent)} findings in past {self.config.recent_days} days",
                        f"{len(older)} findings before that",
                    ],
                    related_findings=[f.finding_id for f in recent],
                    metadata={
                        "recent_count": len(recent),
                        "older_count": len(older),
                        "recent_days": self.config.recent_days,
                    },
                )
            )

        # Timeline cluster (findings bunched together)
        if len(dated) >= 3:
            dates = sorted(f.finding_date for f in dated if f.finding_date)  # type: ignore
            if dates:
                total_span = (dates[-1] - dates[0]).days
                if total_span > 0:
                    # Check if findings are clustered (not evenly distributed)
                    gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
                    avg_gap = sum(gaps) / len(gaps)
                    max_gap = max(gaps)

                    # If max gap is > 3x average, there's clustering
                    if max_gap > avg_gap * 3 and avg_gap < 60:
                        patterns.append(
                            Pattern(
                                pattern_type=PatternType.TIMELINE_CLUSTER,
                                severity=Severity.LOW,
                                confidence=0.6,
                                description=f"Findings cluster together with {avg_gap:.0f} day avg gap",
                                evidence=[
                                    f"Average gap: {avg_gap:.1f} days",
                                    f"Max gap: {max_gap} days",
                                ],
                                related_findings=[f.finding_id for f in dated],
                                time_span=timedelta(days=total_span),
                                start_date=dates[0],
                                end_date=dates[-1],
                                metadata={
                                    "avg_gap_days": avg_gap,
                                    "max_gap_days": max_gap,
                                },
                            )
                        )

        return patterns

    def _detect_behavioral_patterns(self, findings: list[Finding]) -> list[Pattern]:
        """Detect behavioral patterns.

        Args:
            findings: Findings to analyze.

        Returns:
            List of behavioral patterns.
        """
        patterns: list[Pattern] = []

        # Repeat offender (same category multiple times)
        by_category: dict[FindingCategory, list[Finding]] = defaultdict(list)
        for f in findings:
            if f.category:
                by_category[f.category].append(f)

        for category, cat_findings in by_category.items():
            if len(cat_findings) >= self.config.repeat_threshold:
                # Check if high severity
                high_sev = [f for f in cat_findings if f.severity in (Severity.HIGH, Severity.CRITICAL)]
                if len(high_sev) >= 2:
                    patterns.append(
                        Pattern(
                            pattern_type=PatternType.REPEAT_OFFENDER,
                            severity=Severity.HIGH,
                            confidence=min(0.9, 0.6 + len(high_sev) * 0.1),
                            description=f"Repeat {category.value} issues: {len(cat_findings)} total, {len(high_sev)} high severity",
                            evidence=[
                                f"{len(cat_findings)} {category.value} findings",
                                f"{len(high_sev)} high/critical severity",
                            ],
                            affected_categories=[category],
                            related_findings=[f.finding_id for f in cat_findings],
                            metadata={
                                "category": category.value,
                                "total": len(cat_findings),
                                "high_severity": len(high_sev),
                            },
                        )
                    )

        # Progressive degradation (check dated findings)
        dated = sorted(
            [(f, f.finding_date) for f in findings if f.finding_date],
            key=lambda x: x[1],  # type: ignore
        )

        if len(dated) >= 4:
            # Check if recent findings are worse
            recent_third = dated[-(len(dated) // 3) :]
            early_third = dated[: len(dated) // 3]

            recent_avg = sum(SEVERITY_RANK.get(f.severity, 2) for f, _ in recent_third) / len(
                recent_third
            )
            early_avg = sum(SEVERITY_RANK.get(f.severity, 2) for f, _ in early_third) / len(
                early_third
            )

            if recent_avg > early_avg + 0.5:
                patterns.append(
                    Pattern(
                        pattern_type=PatternType.PROGRESSIVE_DEGRADATION,
                        severity=Severity.HIGH,
                        confidence=min(0.85, 0.5 + (recent_avg - early_avg) * 0.15),
                        description=f"Progressive degradation: severity {early_avg:.1f} → {recent_avg:.1f}",
                        evidence=[
                            f"Early average severity: {early_avg:.2f}",
                            f"Recent average severity: {recent_avg:.2f}",
                        ],
                        related_findings=[f.finding_id for f, _ in dated],
                        start_date=dated[0][1],
                        end_date=dated[-1][1],
                        metadata={
                            "early_avg": early_avg,
                            "recent_avg": recent_avg,
                        },
                    )
                )
            elif early_avg > recent_avg + 0.5:
                patterns.append(
                    Pattern(
                        pattern_type=PatternType.IMPROVEMENT_TREND,
                        severity=Severity.LOW,
                        confidence=min(0.8, 0.5 + (early_avg - recent_avg) * 0.15),
                        description=f"Improvement trend: severity {early_avg:.1f} → {recent_avg:.1f}",
                        evidence=[
                            f"Early average severity: {early_avg:.2f}",
                            f"Recent average severity: {recent_avg:.2f}",
                        ],
                        related_findings=[f.finding_id for f, _ in dated],
                        start_date=dated[0][1],
                        end_date=dated[-1][1],
                        metadata={
                            "early_avg": early_avg,
                            "recent_avg": recent_avg,
                        },
                    )
                )

        return patterns

    def _calculate_risk_score(self, patterns: list[Pattern]) -> float:
        """Calculate overall risk score from patterns.

        Args:
            patterns: Recognized patterns.

        Returns:
            Risk score (0.0-1.0).
        """
        if not patterns:
            return 0.0

        # Weight patterns by severity and confidence
        weighted_sum = 0.0
        total_weight = 0.0

        for pattern in patterns:
            severity_weight = SEVERITY_RANK.get(pattern.severity, 2) / 4.0
            score = severity_weight * pattern.confidence
            weighted_sum += score
            total_weight += 1

        return min(1.0, weighted_sum / max(1, total_weight) * 1.5)

    def _identify_key_concerns(self, patterns: list[Pattern]) -> list[str]:
        """Identify key concerns from patterns.

        Args:
            patterns: Recognized patterns.

        Returns:
            List of key concern descriptions.
        """
        concerns: list[str] = []

        # High severity patterns
        high_sev = [p for p in patterns if p.severity in (Severity.HIGH, Severity.CRITICAL)]
        for pattern in high_sev[:3]:  # Top 3
            concerns.append(f"{pattern.pattern_type.value}: {pattern.description}")

        # Specific concerning patterns
        concerning_types = {
            PatternType.REPEAT_OFFENDER,
            PatternType.SEVERITY_ESCALATION,
            PatternType.PROGRESSIVE_DEGRADATION,
            PatternType.SYSTEMIC_ISSUES,
        }

        for pattern in patterns:
            if pattern.pattern_type in concerning_types and pattern.description not in concerns:
                concerns.append(pattern.description)
                if len(concerns) >= 5:
                    break

        return concerns[:5]


def create_pattern_recognizer(config: RecognizerConfig | None = None) -> PatternRecognizer:
    """Create a pattern recognizer.

    Args:
        config: Optional recognizer configuration.

    Returns:
        Configured PatternRecognizer.
    """
    return PatternRecognizer(config=config)
