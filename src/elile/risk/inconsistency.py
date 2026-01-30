"""Inconsistency analysis and risk assessment.

Inconsistencies between information sources are not just data quality issues -
they are potential indicators of manipulation, falsification, or identity fraud.
This module analyzes inconsistency patterns and generates appropriate risk findings.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal
from uuid import uuid7

import structlog

from elile.agent.state import (
    Inconsistency,
    InconsistencyType,
    InformationType,
    RiskFinding,
)

logger = structlog.get_logger()


# Base risk scores by inconsistency type
INCONSISTENCY_BASE_SCORES: dict[InconsistencyType, float] = {
    # Lower risk - common data entry issues
    InconsistencyType.DATE_MINOR: 0.1,
    InconsistencyType.SPELLING_VARIANT: 0.1,
    InconsistencyType.ADDRESS_FORMAT: 0.1,
    # Medium risk - requires explanation
    InconsistencyType.DATE_SIGNIFICANT: 0.3,
    InconsistencyType.TITLE_MISMATCH: 0.3,
    InconsistencyType.DEGREE_MISMATCH: 0.5,
    InconsistencyType.EMPLOYER_DISCREPANCY: 0.4,
    # Higher risk - potential deception indicators
    InconsistencyType.EMPLOYMENT_GAP_HIDDEN: 0.6,
    InconsistencyType.EDUCATION_INFLATED: 0.7,
    InconsistencyType.EMPLOYER_FABRICATED: 0.8,
    InconsistencyType.TIMELINE_IMPOSSIBLE: 0.7,
    InconsistencyType.IDENTITY_MISMATCH: 0.8,
    # Critical - strong deception signals
    InconsistencyType.MULTIPLE_IDENTITIES: 0.9,
    InconsistencyType.SYSTEMATIC_PATTERN: 0.95,
}


# Map base score to severity level
def _score_to_severity(score: float) -> Literal["low", "medium", "high", "critical"]:
    """Convert a risk score to severity level.

    Args:
        score: Risk score from 0.0 to 1.0.

    Returns:
        Severity level string.
    """
    if score >= 0.75:
        return "critical"
    elif score >= 0.5:
        return "high"
    elif score >= 0.25:
        return "medium"
    else:
        return "low"


class InconsistencyAnalyzer:
    """Analyzes inconsistency patterns and generates risk findings.

    This class implements the risk scoring logic for inconsistencies,
    detecting patterns that indicate potential deception or fraud.
    """

    def __init__(
        self,
        systematic_threshold: int = 4,
        cross_type_threshold: int = 3,
    ) -> None:
        """Initialize the inconsistency analyzer.

        Args:
            systematic_threshold: Number of inconsistencies to trigger
                systematic pattern detection.
            cross_type_threshold: Number of information types with
                inconsistencies to trigger cross-type pattern.
        """
        self._systematic_threshold = systematic_threshold
        self._cross_type_threshold = cross_type_threshold

    def analyze_patterns(
        self,
        inconsistencies: list[Inconsistency],
    ) -> list[RiskFinding]:
        """Analyze inconsistency patterns and generate risk findings.

        Args:
            inconsistencies: List of detected inconsistencies.

        Returns:
            List of risk findings derived from inconsistency patterns.
        """
        if not inconsistencies:
            return []

        findings: list[RiskFinding] = []

        # Calculate pattern modifiers
        pattern_modifier = self._calculate_pattern_modifier(inconsistencies)
        direction = self._detect_direction(inconsistencies)

        # Check for systematic patterns
        if len(inconsistencies) >= self._systematic_threshold:
            findings.append(self._systematic_pattern_finding(inconsistencies))

        # Check for directional bias (all inflate/all deflate)
        if direction:
            findings.append(self._directional_bias_finding(inconsistencies, direction))

        # Check for cross-type patterns
        cross_type_finding = self._check_cross_type_pattern(inconsistencies)
        if cross_type_finding:
            findings.append(cross_type_finding)

        # Generate findings for high-severity individual inconsistencies
        for inc in inconsistencies:
            if inc.risk_severity in ("high", "critical"):
                findings.append(self._individual_finding(inc, pattern_modifier))

        logger.info(
            "Analyzed inconsistencies",
            total_inconsistencies=len(inconsistencies),
            findings_generated=len(findings),
            pattern_modifier=pattern_modifier,
            direction=direction,
        )

        return findings

    def _calculate_pattern_modifier(
        self,
        inconsistencies: list[Inconsistency],
    ) -> float:
        """Calculate pattern-based modifier for risk scoring.

        Args:
            inconsistencies: List of inconsistencies.

        Returns:
            Multiplicative modifier for risk scores.
        """
        modifier = 1.0

        # Count inconsistencies by field
        by_field: dict[str, int] = defaultdict(int)
        for inc in inconsistencies:
            by_field[inc.field] += 1

        # Count unique information types involved
        types_involved = set()
        for inc in inconsistencies:
            types_involved.add(inc.type_a)
            types_involved.add(inc.type_b)

        # 2-3 inconsistencies in same field
        for count in by_field.values():
            if 2 <= count <= 3:
                modifier = max(modifier, 1.3)
            elif count >= 4:
                modifier = max(modifier, 1.5)

        # Inconsistencies span 3+ types
        if len(types_involved) >= self._cross_type_threshold:
            modifier *= 1.5

        # 4+ total inconsistencies
        if len(inconsistencies) >= self._systematic_threshold:
            modifier = max(modifier, 2.0)

        return modifier

    def _detect_direction(
        self,
        inconsistencies: list[Inconsistency],
    ) -> str | None:
        """Detect if inconsistencies have a directional bias.

        Looks for patterns where inconsistencies consistently favor
        the subject (inflation) or consistently understate (deflation).

        Args:
            inconsistencies: List of inconsistencies.

        Returns:
            "inflate", "deflate", or None if no clear direction.
        """
        if len(inconsistencies) < 2:
            return None

        # Track inflation vs deflation signals
        inflate_types = {
            InconsistencyType.EDUCATION_INFLATED,
            InconsistencyType.TITLE_MISMATCH,
            InconsistencyType.EMPLOYMENT_GAP_HIDDEN,
        }

        inflate_count = 0
        deflate_count = 0

        for inc in inconsistencies:
            if inc.inconsistency_type in inflate_types:
                inflate_count += 1
            # Other types that could indicate deflation would go here

        total = len(inconsistencies)
        if inflate_count >= total * 0.7:  # 70% threshold
            return "inflate"
        elif deflate_count >= total * 0.7:
            return "deflate"

        return None

    def _systematic_pattern_finding(
        self,
        inconsistencies: list[Inconsistency],
    ) -> RiskFinding:
        """Generate finding for systematic pattern of inconsistencies.

        Args:
            inconsistencies: List of inconsistencies forming the pattern.

        Returns:
            RiskFinding for the systematic pattern.
        """
        # Collect all sources
        all_sources = []
        for inc in inconsistencies:
            all_sources.extend(inc.sources)

        # Get unique fields affected
        fields = set(inc.field for inc in inconsistencies)

        return RiskFinding(
            category="integrity",
            description=(
                f"Systematic pattern of {len(inconsistencies)} inconsistencies detected "
                f"across provided information. Affected fields: {', '.join(fields)}. "
                "This pattern may indicate intentional misrepresentation."
            ),
            severity="critical",
            confidence=0.85,
            sources=list(set(all_sources)),
            metadata={
                "inconsistency_count": str(len(inconsistencies)),
                "fields_affected": ", ".join(fields),
                "pattern_type": "systematic",
            },
        )

    def _directional_bias_finding(
        self,
        inconsistencies: list[Inconsistency],
        direction: str,
    ) -> RiskFinding:
        """Generate finding for directional bias in inconsistencies.

        Args:
            inconsistencies: List of inconsistencies.
            direction: "inflate" or "deflate".

        Returns:
            RiskFinding for the directional bias.
        """
        all_sources = []
        for inc in inconsistencies:
            all_sources.extend(inc.sources)

        if direction == "inflate":
            description = (
                f"Pattern of {len(inconsistencies)} inconsistencies all favor "
                "inflating credentials or concealing negative information. "
                "This directional bias suggests intentional misrepresentation."
            )
        else:
            description = (
                f"Pattern of {len(inconsistencies)} inconsistencies detected "
                f"with consistent {direction} bias."
            )

        return RiskFinding(
            category="integrity",
            description=description,
            severity="high",
            confidence=0.80,
            sources=list(set(all_sources)),
            metadata={
                "direction": direction,
                "inconsistency_count": str(len(inconsistencies)),
                "pattern_type": "directional_bias",
            },
        )

    def _check_cross_type_pattern(
        self,
        inconsistencies: list[Inconsistency],
    ) -> RiskFinding | None:
        """Check for inconsistencies spanning multiple information types.

        Args:
            inconsistencies: List of inconsistencies.

        Returns:
            RiskFinding if cross-type pattern detected, None otherwise.
        """
        types_involved: set[InformationType] = set()
        for inc in inconsistencies:
            types_involved.add(inc.type_a)
            types_involved.add(inc.type_b)

        if len(types_involved) < self._cross_type_threshold:
            return None

        all_sources = []
        for inc in inconsistencies:
            all_sources.extend(inc.sources)

        type_names = [t.value for t in types_involved]

        return RiskFinding(
            category="integrity",
            description=(
                f"Inconsistencies detected spanning {len(types_involved)} different "
                f"information categories: {', '.join(type_names)}. "
                "Cross-category discrepancies may indicate coordinated misrepresentation."
            ),
            severity="high",
            confidence=0.75,
            sources=list(set(all_sources)),
            metadata={
                "types_involved": ", ".join(type_names),
                "type_count": str(len(types_involved)),
                "pattern_type": "cross_type",
            },
        )

    def _individual_finding(
        self,
        inconsistency: Inconsistency,
        pattern_modifier: float,
    ) -> RiskFinding:
        """Generate finding for a single high-severity inconsistency.

        Args:
            inconsistency: The inconsistency to report.
            pattern_modifier: Pattern-based score modifier.

        Returns:
            RiskFinding for the individual inconsistency.
        """
        # Calculate adjusted score
        base_score = INCONSISTENCY_BASE_SCORES.get(inconsistency.inconsistency_type, 0.5)
        adjusted_score = min(1.0, base_score * pattern_modifier)
        severity = _score_to_severity(adjusted_score)

        return RiskFinding(
            category="integrity",
            description=(
                f"{inconsistency.inconsistency_type.value}: {inconsistency.risk_rationale}. "
                f"Found '{inconsistency.value_a}' vs '{inconsistency.value_b}' "
                f"for field '{inconsistency.field}'."
            ),
            severity=severity,
            confidence=adjusted_score,
            sources=inconsistency.sources,
            metadata={
                "inconsistency_id": str(inconsistency.inconsistency_id),
                "inconsistency_type": inconsistency.inconsistency_type.value,
                "field": inconsistency.field,
                "type_a": inconsistency.type_a.value,
                "type_b": inconsistency.type_b.value,
            },
        )

    def classify_inconsistency(
        self,
        field: str,
        value_a: str,
        value_b: str,
        type_a: InformationType,
        type_b: InformationType,
    ) -> tuple[InconsistencyType, str]:
        """Classify an inconsistency and determine its type.

        Args:
            field: Field where inconsistency was detected.
            value_a: Value from source A.
            value_b: Value from source B.
            type_a: Information type of source A.
            type_b: Information type of source B.

        Returns:
            Tuple of (InconsistencyType, risk_rationale).
        """
        field_lower = field.lower()
        value_a_lower = value_a.lower()
        value_b_lower = value_b.lower()

        # Date-related inconsistencies
        if "date" in field_lower:
            return self._classify_date_inconsistency(value_a, value_b)

        # Name/spelling inconsistencies
        if "name" in field_lower:
            return self._classify_name_inconsistency(value_a, value_b)

        # Education-related
        if "degree" in field_lower or "education" in field_lower:
            return self._classify_education_inconsistency(value_a, value_b)

        # Employment-related
        if "employer" in field_lower or "title" in field_lower or "job" in field_lower:
            return self._classify_employment_inconsistency(field, value_a, value_b)

        # Address-related
        if "address" in field_lower:
            return self._classify_address_inconsistency(value_a, value_b)

        # Default: general discrepancy
        return (
            InconsistencyType.EMPLOYER_DISCREPANCY,
            f"Discrepancy in {field} between sources",
        )

    def _classify_date_inconsistency(
        self,
        value_a: str,
        value_b: str,
    ) -> tuple[InconsistencyType, str]:
        """Classify date-related inconsistencies.

        Args:
            value_a: First date value.
            value_b: Second date value.

        Returns:
            Tuple of (InconsistencyType, risk_rationale).
        """
        # Try to parse and compare dates
        # For now, use simple heuristics based on string differences
        try:
            # Check if dates differ by more than 30 days (significant)
            # This is simplified - real implementation would parse dates
            if len(value_a) != len(value_b):
                return (
                    InconsistencyType.DATE_SIGNIFICANT,
                    "Date formats differ significantly, may indicate gap concealment",
                )

            # Check for completely different dates
            if value_a[:4] != value_b[:4]:  # Different year
                return (
                    InconsistencyType.TIMELINE_IMPOSSIBLE,
                    "Dates differ by years, suggesting timeline manipulation",
                )
            elif value_a[:7] != value_b[:7]:  # Different month
                return (
                    InconsistencyType.DATE_SIGNIFICANT,
                    "Dates differ by months, possible gap concealment",
                )
            else:
                return (
                    InconsistencyType.DATE_MINOR,
                    "Minor date discrepancy, likely data entry variance",
                )
        except Exception:
            return (
                InconsistencyType.DATE_SIGNIFICANT,
                "Unable to parse dates for comparison",
            )

    def _classify_name_inconsistency(
        self,
        value_a: str,
        value_b: str,
    ) -> tuple[InconsistencyType, str]:
        """Classify name-related inconsistencies.

        Args:
            value_a: First name value.
            value_b: Second name value.

        Returns:
            Tuple of (InconsistencyType, risk_rationale).
        """
        # Check similarity
        a_parts = set(value_a.lower().split())
        b_parts = set(value_b.lower().split())

        common = a_parts & b_parts

        if len(common) >= len(a_parts) - 1 or len(common) >= len(b_parts) - 1:
            return (
                InconsistencyType.SPELLING_VARIANT,
                "Minor name spelling variation, likely legitimate variant",
            )
        elif len(common) > 0:
            return (
                InconsistencyType.IDENTITY_MISMATCH,
                "Significant name difference may indicate identity confusion",
            )
        else:
            return (
                InconsistencyType.MULTIPLE_IDENTITIES,
                "Completely different names suggest potential identity fraud",
            )

    def _classify_education_inconsistency(
        self,
        value_a: str,
        value_b: str,
    ) -> tuple[InconsistencyType, str]:
        """Classify education-related inconsistencies.

        Args:
            value_a: First education value.
            value_b: Second education value.

        Returns:
            Tuple of (InconsistencyType, risk_rationale).
        """
        # Check for degree inflation patterns
        degree_hierarchy = ["high school", "associate", "bachelor", "master", "doctor", "phd"]

        a_level = -1
        b_level = -1

        for i, level in enumerate(degree_hierarchy):
            if level in value_a.lower():
                a_level = i
            if level in value_b.lower():
                b_level = i

        if a_level > b_level and b_level >= 0:
            return (
                InconsistencyType.EDUCATION_INFLATED,
                "Claimed degree exceeds verified credential",
            )
        elif a_level != b_level:
            return (
                InconsistencyType.DEGREE_MISMATCH,
                "Degree type differs between sources",
            )
        else:
            return (
                InconsistencyType.SPELLING_VARIANT,
                "Minor variation in education description",
            )

    def _classify_employment_inconsistency(
        self,
        field: str,
        value_a: str,
        value_b: str,
    ) -> tuple[InconsistencyType, str]:
        """Classify employment-related inconsistencies.

        Args:
            field: Field name.
            value_a: First value.
            value_b: Second value.

        Returns:
            Tuple of (InconsistencyType, risk_rationale).
        """
        if "title" in field.lower():
            # Check for title inflation
            seniority_terms = ["senior", "director", "vp", "chief", "head", "lead", "manager"]
            a_seniority = sum(1 for term in seniority_terms if term in value_a.lower())
            b_seniority = sum(1 for term in seniority_terms if term in value_b.lower())

            if a_seniority > b_seniority:
                return (
                    InconsistencyType.TITLE_MISMATCH,
                    "Claimed title appears inflated compared to verified records",
                )
            else:
                return (
                    InconsistencyType.TITLE_MISMATCH,
                    "Job title differs between sources",
                )
        else:
            # Employer name check
            a_parts = set(value_a.lower().split())
            b_parts = set(value_b.lower().split())

            if not a_parts & b_parts:
                return (
                    InconsistencyType.EMPLOYER_FABRICATED,
                    "Employer names have no overlap, possible fabrication",
                )
            else:
                return (
                    InconsistencyType.EMPLOYER_DISCREPANCY,
                    "Employer name differs between sources",
                )

    def _classify_address_inconsistency(
        self,
        value_a: str,
        value_b: str,
    ) -> tuple[InconsistencyType, str]:
        """Classify address-related inconsistencies.

        Args:
            value_a: First address value.
            value_b: Second address value.

        Returns:
            Tuple of (InconsistencyType, risk_rationale).
        """
        # Check for format vs substantive differences
        a_parts = set(value_a.lower().replace(",", " ").split())
        b_parts = set(value_b.lower().replace(",", " ").split())

        common = a_parts & b_parts

        if len(common) >= min(len(a_parts), len(b_parts)) * 0.7:
            return (
                InconsistencyType.ADDRESS_FORMAT,
                "Same address with formatting differences",
            )
        else:
            return (
                InconsistencyType.IDENTITY_MISMATCH,
                "Significantly different addresses reported",
            )

    def create_inconsistency(
        self,
        type_a: InformationType,
        type_b: InformationType,
        field: str,
        value_a: str,
        value_b: str,
        sources: list[str],
    ) -> Inconsistency:
        """Create a fully classified inconsistency.

        Args:
            type_a: First information type.
            type_b: Second information type.
            field: Field where inconsistency was found.
            value_a: Value from first source.
            value_b: Value from second source.
            sources: List of source identifiers.

        Returns:
            Fully classified Inconsistency object.
        """
        inc_type, rationale = self.classify_inconsistency(field, value_a, value_b, type_a, type_b)

        base_score = INCONSISTENCY_BASE_SCORES.get(inc_type, 0.5)
        severity = _score_to_severity(base_score)

        return Inconsistency(
            inconsistency_id=uuid7(),
            type_a=type_a,
            type_b=type_b,
            field=field,
            value_a=value_a,
            value_b=value_b,
            sources=sources,
            inconsistency_type=inc_type,
            risk_severity=severity,
            risk_rationale=rationale,
        )
