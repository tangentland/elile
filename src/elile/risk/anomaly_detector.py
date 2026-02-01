"""Anomaly Detector for identifying unusual patterns and deception indicators.

This module provides the AnomalyDetector that:
1. Detects statistical anomalies in subject data
2. Identifies systematic inconsistency patterns
3. Calculates deception likelihood scores
4. Flags timeline impossibilities
5. Detects credential inflation
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import InconsistencyType
from elile.core.logging import get_logger
from elile.investigation.finding_extractor import Severity
from elile.investigation.result_assessor import DetectedInconsistency, Fact

logger = get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class AnomalyType(str, Enum):
    """Types of anomalies that can be detected."""

    # Statistical anomalies
    STATISTICAL_OUTLIER = "statistical_outlier"
    UNUSUAL_FREQUENCY = "unusual_frequency"
    IMPROBABLE_VALUE = "improbable_value"

    # Inconsistency patterns
    SYSTEMATIC_INCONSISTENCIES = "systematic_inconsistencies"
    CROSS_FIELD_PATTERN = "cross_field_pattern"
    DIRECTIONAL_BIAS = "directional_bias"

    # Timeline anomalies
    TIMELINE_IMPOSSIBLE = "timeline_impossible"
    CHRONOLOGICAL_GAP = "chronological_gap"
    OVERLAPPING_PERIODS = "overlapping_periods"

    # Credential anomalies
    CREDENTIAL_INFLATION = "credential_inflation"
    EXPERIENCE_INFLATION = "experience_inflation"
    QUALIFICATION_GAP = "qualification_gap"

    # Deception indicators
    DECEPTION_PATTERN = "deception_pattern"
    CONCEALMENT_ATTEMPT = "concealment_attempt"
    FABRICATION_INDICATOR = "fabrication_indicator"

    # Behavioral anomalies
    UNUSUAL_PATTERN = "unusual_pattern"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


# Severity mapping for anomaly types
ANOMALY_TYPE_SEVERITY: dict[AnomalyType, Severity] = {
    # Statistical (generally lower severity)
    AnomalyType.STATISTICAL_OUTLIER: Severity.LOW,
    AnomalyType.UNUSUAL_FREQUENCY: Severity.LOW,
    AnomalyType.IMPROBABLE_VALUE: Severity.MEDIUM,
    # Inconsistency patterns
    AnomalyType.SYSTEMATIC_INCONSISTENCIES: Severity.HIGH,
    AnomalyType.CROSS_FIELD_PATTERN: Severity.MEDIUM,
    AnomalyType.DIRECTIONAL_BIAS: Severity.HIGH,
    # Timeline
    AnomalyType.TIMELINE_IMPOSSIBLE: Severity.CRITICAL,
    AnomalyType.CHRONOLOGICAL_GAP: Severity.MEDIUM,
    AnomalyType.OVERLAPPING_PERIODS: Severity.MEDIUM,
    # Credential
    AnomalyType.CREDENTIAL_INFLATION: Severity.HIGH,
    AnomalyType.EXPERIENCE_INFLATION: Severity.MEDIUM,
    AnomalyType.QUALIFICATION_GAP: Severity.LOW,
    # Deception
    AnomalyType.DECEPTION_PATTERN: Severity.CRITICAL,
    AnomalyType.CONCEALMENT_ATTEMPT: Severity.HIGH,
    AnomalyType.FABRICATION_INDICATOR: Severity.CRITICAL,
    # Behavioral
    AnomalyType.UNUSUAL_PATTERN: Severity.LOW,
    AnomalyType.SUSPICIOUS_ACTIVITY: Severity.MEDIUM,
}

# Deception likelihood by inconsistency type
DECEPTION_LIKELIHOOD: dict[InconsistencyType, float] = {
    # Low likelihood - common data issues
    InconsistencyType.DATE_MINOR: 0.1,
    InconsistencyType.SPELLING_VARIANT: 0.05,
    InconsistencyType.ADDRESS_FORMAT: 0.05,
    # Medium likelihood - could be innocent
    InconsistencyType.DATE_SIGNIFICANT: 0.3,
    InconsistencyType.TITLE_MISMATCH: 0.4,
    InconsistencyType.EMPLOYER_DISCREPANCY: 0.3,
    InconsistencyType.DEGREE_MISMATCH: 0.5,
    # High likelihood - likely intentional
    InconsistencyType.EMPLOYMENT_GAP_HIDDEN: 0.7,
    InconsistencyType.EDUCATION_INFLATED: 0.8,
    InconsistencyType.TIMELINE_IMPOSSIBLE: 0.85,
    InconsistencyType.IDENTITY_MISMATCH: 0.7,
    # Very high likelihood - strong deception signals
    InconsistencyType.EMPLOYER_FABRICATED: 0.9,
    InconsistencyType.MULTIPLE_IDENTITIES: 0.95,
    InconsistencyType.SYSTEMATIC_PATTERN: 0.9,
}


# =============================================================================
# Models
# =============================================================================


@dataclass
class Anomaly:
    """A detected anomaly in subject data.

    Anomalies represent unusual patterns, statistical outliers, or
    potential deception indicators that require attention.
    """

    anomaly_id: UUID = field(default_factory=uuid7)
    anomaly_type: AnomalyType = AnomalyType.UNUSUAL_PATTERN
    severity: Severity = Severity.MEDIUM
    confidence: float = 0.5  # 0.0-1.0
    description: str = ""
    evidence: list[str] = field(default_factory=list)
    affected_fields: list[str] = field(default_factory=list)
    related_facts: list[UUID] = field(default_factory=list)
    related_inconsistencies: list[UUID] = field(default_factory=list)
    deception_score: float = 0.0  # 0.0-1.0
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "anomaly_id": str(self.anomaly_id),
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "description": self.description,
            "evidence": self.evidence,
            "affected_fields": self.affected_fields,
            "related_facts": [str(f) for f in self.related_facts],
            "related_inconsistencies": [str(i) for i in self.related_inconsistencies],
            "deception_score": self.deception_score,
            "detected_at": self.detected_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class DeceptionAssessment:
    """Assessment of overall deception likelihood.

    Combines multiple signals to produce a comprehensive deception score.
    """

    assessment_id: UUID = field(default_factory=uuid7)
    overall_score: float = 0.0  # 0.0-1.0
    risk_level: Literal["none", "low", "moderate", "high", "critical"] = "none"
    contributing_factors: list[str] = field(default_factory=list)
    pattern_modifiers: list[str] = field(default_factory=list)
    anomaly_count: int = 0
    inconsistency_count: int = 0
    assessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "assessment_id": str(self.assessment_id),
            "overall_score": self.overall_score,
            "risk_level": self.risk_level,
            "contributing_factors": self.contributing_factors,
            "pattern_modifiers": self.pattern_modifiers,
            "anomaly_count": self.anomaly_count,
            "inconsistency_count": self.inconsistency_count,
            "assessed_at": self.assessed_at.isoformat(),
        }


class DetectorConfig(BaseModel):
    """Configuration for anomaly detector."""

    # Thresholds
    systematic_threshold: int = Field(
        default=4, ge=2, description="Inconsistencies needed for systematic pattern"
    )
    deception_warning_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Deception score for warning"
    )
    deception_critical_threshold: float = Field(
        default=0.75, ge=0.0, le=1.0, description="Deception score for critical"
    )

    # Feature flags
    detect_statistical: bool = Field(default=True, description="Detect statistical anomalies")
    detect_timeline: bool = Field(default=True, description="Detect timeline anomalies")
    detect_credential: bool = Field(default=True, description="Detect credential inflation")
    detect_deception: bool = Field(default=True, description="Calculate deception scores")

    # Sensitivity
    statistical_sensitivity: float = Field(
        default=2.0, ge=1.0, le=4.0, description="Standard deviations for outlier detection"
    )
    min_confidence: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Minimum confidence for anomaly"
    )


# =============================================================================
# Anomaly Detector
# =============================================================================


class AnomalyDetector:
    """Detects anomalies and deception patterns in subject data.

    The AnomalyDetector analyzes facts and inconsistencies to identify:
    - Statistical outliers and improbable values
    - Systematic inconsistency patterns
    - Timeline impossibilities
    - Credential inflation
    - Deception indicators

    Example:
        ```python
        detector = AnomalyDetector()

        anomalies = detector.detect_anomalies(
            facts=extracted_facts,
            inconsistencies=detected_inconsistencies,
        )

        assessment = detector.assess_deception(
            anomalies=anomalies,
            inconsistencies=inconsistencies,
        )

        print(f"Deception risk: {assessment.risk_level}")
        ```
    """

    def __init__(self, config: DetectorConfig | None = None):
        """Initialize the anomaly detector.

        Args:
            config: Detector configuration.
        """
        self.config = config or DetectorConfig()

    def detect_anomalies(
        self,
        facts: list[Fact],
        inconsistencies: list[DetectedInconsistency],
    ) -> list[Anomaly]:
        """Detect all anomalies in subject data.

        Args:
            facts: Extracted facts from investigation.
            inconsistencies: Detected inconsistencies between sources.

        Returns:
            List of detected anomalies.
        """
        anomalies: list[Anomaly] = []

        # Statistical anomalies
        if self.config.detect_statistical:
            anomalies.extend(self._detect_statistical_anomalies(facts))

        # Inconsistency patterns
        anomalies.extend(self._detect_inconsistency_patterns(inconsistencies))

        # Timeline anomalies
        if self.config.detect_timeline:
            anomalies.extend(self._detect_timeline_anomalies(facts, inconsistencies))

        # Credential anomalies
        if self.config.detect_credential:
            anomalies.extend(self._detect_credential_anomalies(facts, inconsistencies))

        # Deception indicators
        if self.config.detect_deception:
            anomalies.extend(self._detect_deception_indicators(facts, inconsistencies))

        # Filter by minimum confidence
        anomalies = [a for a in anomalies if a.confidence >= self.config.min_confidence]

        logger.info(
            "Anomalies detected",
            total=len(anomalies),
            by_type={t.value: sum(1 for a in anomalies if a.anomaly_type == t) for t in AnomalyType},
        )

        return anomalies

    def assess_deception(
        self,
        anomalies: list[Anomaly],
        inconsistencies: list[DetectedInconsistency],
    ) -> DeceptionAssessment:
        """Calculate overall deception likelihood.

        Args:
            anomalies: Detected anomalies.
            inconsistencies: Detected inconsistencies.

        Returns:
            Comprehensive deception assessment.
        """
        factors: list[str] = []
        modifiers: list[str] = []

        # Base score from inconsistencies
        inc_score = self._calculate_inconsistency_deception_score(inconsistencies)
        if inc_score > 0:
            factors.append(f"Inconsistency patterns (score: {inc_score:.2f})")

        # Score from high-severity anomalies
        anomaly_score = 0.0
        critical_anomalies = [a for a in anomalies if a.severity == Severity.CRITICAL]
        high_anomalies = [a for a in anomalies if a.severity == Severity.HIGH]

        if critical_anomalies:
            anomaly_score = max(anomaly_score, 0.8)
            factors.append(f"{len(critical_anomalies)} critical anomalies")
        if high_anomalies:
            anomaly_score = max(anomaly_score, 0.5 + len(high_anomalies) * 0.1)
            factors.append(f"{len(high_anomalies)} high-severity anomalies")

        # Deception-specific anomalies
        deception_anomalies = [
            a
            for a in anomalies
            if a.anomaly_type
            in (
                AnomalyType.DECEPTION_PATTERN,
                AnomalyType.FABRICATION_INDICATOR,
                AnomalyType.CONCEALMENT_ATTEMPT,
            )
        ]
        if deception_anomalies:
            avg_deception = sum(a.deception_score for a in deception_anomalies) / len(
                deception_anomalies
            )
            anomaly_score = max(anomaly_score, avg_deception)
            factors.append(f"{len(deception_anomalies)} deception indicators")

        # Pattern modifiers
        if self._has_directional_bias(inconsistencies):
            modifiers.append("Directional bias detected (all errors favor subject)")
            anomaly_score *= 1.2

        if self._has_cross_domain_pattern(inconsistencies):
            modifiers.append("Cross-domain inconsistencies")
            anomaly_score *= 1.15

        if len(inconsistencies) >= self.config.systematic_threshold:
            modifiers.append("Systematic pattern threshold exceeded")
            anomaly_score *= 1.25

        # Combine scores
        combined_score = max(inc_score, anomaly_score)
        combined_score = min(1.0, combined_score)

        # Determine risk level
        risk_level = self._score_to_risk_level(combined_score)

        return DeceptionAssessment(
            overall_score=combined_score,
            risk_level=risk_level,
            contributing_factors=factors,
            pattern_modifiers=modifiers,
            anomaly_count=len(anomalies),
            inconsistency_count=len(inconsistencies),
        )

    def _detect_statistical_anomalies(self, facts: list[Fact]) -> list[Anomaly]:
        """Detect statistical outliers and anomalies.

        Args:
            facts: List of facts to analyze.

        Returns:
            List of statistical anomalies.
        """
        anomalies: list[Anomaly] = []

        # Group facts by type
        by_type: dict[str, list[Fact]] = defaultdict(list)
        for fact in facts:
            by_type[fact.fact_type].append(fact)

        # Detect unusual frequency
        for fact_type, type_facts in by_type.items():
            # Very high frequency of a specific fact type could be unusual
            if len(type_facts) > 10:
                anomalies.append(
                    Anomaly(
                        anomaly_type=AnomalyType.UNUSUAL_FREQUENCY,
                        severity=Severity.LOW,
                        confidence=min(0.7, len(type_facts) / 20),
                        description=f"Unusually high frequency of {fact_type} facts ({len(type_facts)} occurrences)",
                        evidence=[f"{len(type_facts)} {fact_type} facts found"],
                        affected_fields=[fact_type],
                        related_facts=[f.fact_id for f in type_facts[:5]],
                        metadata={"count": len(type_facts), "fact_type": fact_type},
                    )
                )

        # Detect improbable values
        for fact in facts:
            improbability = self._assess_value_improbability(fact)
            if improbability > 0.5:
                anomalies.append(
                    Anomaly(
                        anomaly_type=AnomalyType.IMPROBABLE_VALUE,
                        severity=Severity.MEDIUM if improbability > 0.7 else Severity.LOW,
                        confidence=improbability,
                        description=f"Improbable value detected for {fact.fact_type}: {fact.value}",
                        evidence=[f"Value '{fact.value}' has low probability for {fact.fact_type}"],
                        affected_fields=[fact.fact_type],
                        related_facts=[fact.fact_id],
                        metadata={"value": str(fact.value), "improbability": improbability},
                    )
                )

        return anomalies

    def _detect_inconsistency_patterns(
        self, inconsistencies: list[DetectedInconsistency]
    ) -> list[Anomaly]:
        """Detect patterns in inconsistencies.

        Args:
            inconsistencies: List of detected inconsistencies.

        Returns:
            List of pattern-based anomalies.
        """
        anomalies: list[Anomaly] = []

        if not inconsistencies:
            return anomalies

        # Systematic pattern (4+ inconsistencies)
        if len(inconsistencies) >= self.config.systematic_threshold:
            fields_affected = list(set(inc.field for inc in inconsistencies))
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.SYSTEMATIC_INCONSISTENCIES,
                    severity=Severity.HIGH,
                    confidence=min(0.9, 0.5 + len(inconsistencies) * 0.05),
                    description=f"Systematic pattern of {len(inconsistencies)} inconsistencies detected",
                    evidence=[
                        f"{len(inconsistencies)} inconsistencies across {len(fields_affected)} fields"
                    ],
                    affected_fields=fields_affected,
                    related_inconsistencies=[inc.inconsistency_id for inc in inconsistencies],
                    deception_score=0.7,
                    metadata={
                        "inconsistency_count": len(inconsistencies),
                        "fields": fields_affected,
                    },
                )
            )

        # Cross-field pattern (inconsistencies in 3+ different fields)
        fields = defaultdict(int)
        for inc in inconsistencies:
            fields[inc.field] += 1

        if len(fields) >= 3:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.CROSS_FIELD_PATTERN,
                    severity=Severity.MEDIUM,
                    confidence=min(0.85, 0.4 + len(fields) * 0.1),
                    description=f"Inconsistencies span {len(fields)} different data fields",
                    evidence=[f"{field}: {count} issues" for field, count in fields.items()],
                    affected_fields=list(fields.keys()),
                    related_inconsistencies=[inc.inconsistency_id for inc in inconsistencies],
                    deception_score=0.5,
                    metadata={"field_counts": dict(fields)},
                )
            )

        # Directional bias (all errors favor subject)
        if self._has_directional_bias(inconsistencies):
            inflation_types = [
                inc
                for inc in inconsistencies
                if inc.inconsistency_type
                in (
                    InconsistencyType.EDUCATION_INFLATED,
                    InconsistencyType.TITLE_MISMATCH,
                    InconsistencyType.EMPLOYMENT_GAP_HIDDEN,
                )
            ]
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.DIRECTIONAL_BIAS,
                    severity=Severity.HIGH,
                    confidence=0.8,
                    description="All inconsistencies favor the subject (inflation/concealment pattern)",
                    evidence=[
                        f"{len(inflation_types)}/{len(inconsistencies)} inconsistencies inflate credentials or hide negatives"
                    ],
                    affected_fields=list(set(inc.field for inc in inflation_types)),
                    related_inconsistencies=[inc.inconsistency_id for inc in inflation_types],
                    deception_score=0.75,
                    metadata={
                        "bias_direction": "inflate",
                        "inflation_count": len(inflation_types),
                    },
                )
            )

        return anomalies

    def _detect_timeline_anomalies(
        self, facts: list[Fact], inconsistencies: list[DetectedInconsistency]
    ) -> list[Anomaly]:
        """Detect timeline-related anomalies.

        Args:
            facts: List of facts.
            inconsistencies: List of inconsistencies.

        Returns:
            List of timeline anomalies.
        """
        anomalies: list[Anomaly] = []

        # Check for timeline impossible inconsistencies
        timeline_issues = [
            inc
            for inc in inconsistencies
            if inc.inconsistency_type == InconsistencyType.TIMELINE_IMPOSSIBLE
        ]

        for issue in timeline_issues:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.TIMELINE_IMPOSSIBLE,
                    severity=Severity.CRITICAL,
                    confidence=0.9,
                    description=f"Timeline impossibility in {issue.field}: claimed '{issue.claimed_value}' vs found '{issue.found_value}'",
                    evidence=[
                        f"Source {issue.source_a}: {issue.claimed_value}",
                        f"Source {issue.source_b}: {issue.found_value}",
                    ],
                    affected_fields=[issue.field],
                    related_inconsistencies=[issue.inconsistency_id],
                    deception_score=0.85,
                    metadata={
                        "claimed": str(issue.claimed_value),
                        "found": str(issue.found_value),
                    },
                )
            )

        # Check for overlapping periods in employment/education facts
        date_facts = [f for f in facts if "date" in f.fact_type.lower() or "period" in f.fact_type.lower()]
        if date_facts:
            overlap_issues = self._find_date_overlaps(date_facts)
            for overlap in overlap_issues:
                anomalies.append(
                    Anomaly(
                        anomaly_type=AnomalyType.OVERLAPPING_PERIODS,
                        severity=Severity.MEDIUM,
                        confidence=overlap["confidence"],
                        description=overlap["description"],
                        evidence=overlap["evidence"],
                        affected_fields=["employment_dates", "education_dates"],
                        related_facts=overlap["fact_ids"],
                        deception_score=0.4,
                        metadata=overlap.get("metadata", {}),
                    )
                )

        return anomalies

    def _detect_credential_anomalies(
        self, facts: list[Fact], inconsistencies: list[DetectedInconsistency]
    ) -> list[Anomaly]:
        """Detect credential inflation anomalies.

        Args:
            facts: List of facts.
            inconsistencies: List of inconsistencies.

        Returns:
            List of credential anomalies.
        """
        anomalies: list[Anomaly] = []

        # Check for education inflation
        edu_inflation = [
            inc
            for inc in inconsistencies
            if inc.inconsistency_type == InconsistencyType.EDUCATION_INFLATED
        ]
        for inc in edu_inflation:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.CREDENTIAL_INFLATION,
                    severity=Severity.HIGH,
                    confidence=0.85,
                    description=f"Credential inflation detected: claimed '{inc.claimed_value}' but found '{inc.found_value}'",
                    evidence=[
                        f"Claimed credential: {inc.claimed_value}",
                        f"Verified credential: {inc.found_value}",
                    ],
                    affected_fields=[inc.field],
                    related_inconsistencies=[inc.inconsistency_id],
                    deception_score=0.8,
                    metadata={
                        "claimed": str(inc.claimed_value),
                        "verified": str(inc.found_value),
                    },
                )
            )

        # Check for title/experience inflation
        title_issues = [
            inc
            for inc in inconsistencies
            if inc.inconsistency_type == InconsistencyType.TITLE_MISMATCH
        ]
        for inc in title_issues:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.EXPERIENCE_INFLATION,
                    severity=Severity.MEDIUM,
                    confidence=0.7,
                    description=f"Title inflation detected: claimed '{inc.claimed_value}' vs verified '{inc.found_value}'",
                    evidence=[
                        f"Claimed title: {inc.claimed_value}",
                        f"Verified title: {inc.found_value}",
                    ],
                    affected_fields=[inc.field],
                    related_inconsistencies=[inc.inconsistency_id],
                    deception_score=0.5,
                    metadata={
                        "claimed": str(inc.claimed_value),
                        "verified": str(inc.found_value),
                    },
                )
            )

        return anomalies

    def _detect_deception_indicators(
        self, facts: list[Fact], inconsistencies: list[DetectedInconsistency]
    ) -> list[Anomaly]:
        """Detect strong deception indicators.

        Args:
            facts: List of facts.
            inconsistencies: List of inconsistencies.

        Returns:
            List of deception anomalies.
        """
        anomalies: list[Anomaly] = []

        # Employer fabrication
        fabrications = [
            inc
            for inc in inconsistencies
            if inc.inconsistency_type == InconsistencyType.EMPLOYER_FABRICATED
        ]
        for inc in fabrications:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.FABRICATION_INDICATOR,
                    severity=Severity.CRITICAL,
                    confidence=0.9,
                    description=f"Potential employer fabrication: '{inc.claimed_value}' could not be verified",
                    evidence=[
                        f"Claimed employer: {inc.claimed_value}",
                        f"Verification result: {inc.found_value}",
                    ],
                    affected_fields=[inc.field],
                    related_inconsistencies=[inc.inconsistency_id],
                    deception_score=0.9,
                    metadata={
                        "claimed_employer": str(inc.claimed_value),
                        "verification": str(inc.found_value),
                    },
                )
            )

        # Hidden employment gaps
        hidden_gaps = [
            inc
            for inc in inconsistencies
            if inc.inconsistency_type == InconsistencyType.EMPLOYMENT_GAP_HIDDEN
        ]
        for inc in hidden_gaps:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.CONCEALMENT_ATTEMPT,
                    severity=Severity.HIGH,
                    confidence=0.8,
                    description=f"Hidden employment gap detected in {inc.field}",
                    evidence=[
                        f"Claimed: {inc.claimed_value}",
                        f"Actual: {inc.found_value}",
                    ],
                    affected_fields=[inc.field],
                    related_inconsistencies=[inc.inconsistency_id],
                    deception_score=0.7,
                    metadata={
                        "claimed": str(inc.claimed_value),
                        "actual": str(inc.found_value),
                    },
                )
            )

        # Multiple identities (critical)
        multi_id = [
            inc
            for inc in inconsistencies
            if inc.inconsistency_type == InconsistencyType.MULTIPLE_IDENTITIES
        ]
        for inc in multi_id:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.DECEPTION_PATTERN,
                    severity=Severity.CRITICAL,
                    confidence=0.95,
                    description=f"Multiple identity indicators: '{inc.claimed_value}' vs '{inc.found_value}'",
                    evidence=[
                        f"Identity A: {inc.claimed_value}",
                        f"Identity B: {inc.found_value}",
                    ],
                    affected_fields=[inc.field],
                    related_inconsistencies=[inc.inconsistency_id],
                    deception_score=0.95,
                    metadata={
                        "identity_a": str(inc.claimed_value),
                        "identity_b": str(inc.found_value),
                    },
                )
            )

        return anomalies

    def _assess_value_improbability(self, fact: Fact) -> float:
        """Assess how improbable a fact value is.

        Args:
            fact: Fact to assess.

        Returns:
            Improbability score (0.0-1.0).
        """
        # Simple heuristics for improbable values
        value_str = str(fact.value).lower()

        improbability = 0.0

        # Check for very short employment tenure claimed as "senior" roles
        if fact.fact_type in ("title", "job_title", "position"):
            senior_terms = ["ceo", "cto", "cfo", "president", "vice president", "chief"]
            if any(term in value_str for term in senior_terms):
                # Would need more context to validate, but flag for review
                improbability = max(improbability, 0.3)

        # Check for suspiciously round numbers
        if fact.fact_type in ("salary", "years_experience", "duration"):
            try:
                num_val = float(fact.value)
                if num_val % 10 == 0 and num_val > 0:
                    improbability = max(improbability, 0.2)
                if num_val > 50 and fact.fact_type == "years_experience":
                    improbability = max(improbability, 0.7)
            except (ValueError, TypeError):
                pass

        # Very low confidence from source
        if fact.confidence < 0.3:
            improbability = max(improbability, 0.5)

        return improbability

    def _find_date_overlaps(self, date_facts: list[Fact]) -> list[dict[str, Any]]:
        """Find overlapping date periods.

        Args:
            date_facts: Facts containing date information.

        Returns:
            List of overlap descriptions.
        """
        # Simplified implementation - in practice would parse dates properly
        overlaps: list[dict[str, Any]] = []

        # Group by fact type (e.g., employment_start, employment_end)
        # This is a placeholder for more sophisticated date range analysis
        if len(date_facts) < 2:
            return overlaps

        # For now, just flag if we have multiple concurrent facts
        # Real implementation would parse and compare date ranges
        return overlaps

    def _has_directional_bias(self, inconsistencies: list[DetectedInconsistency]) -> bool:
        """Check if inconsistencies have directional bias (all favor subject).

        Args:
            inconsistencies: List of inconsistencies.

        Returns:
            True if directional bias detected.
        """
        if len(inconsistencies) < 2:
            return False

        inflation_types = {
            InconsistencyType.EDUCATION_INFLATED,
            InconsistencyType.TITLE_MISMATCH,
            InconsistencyType.EMPLOYMENT_GAP_HIDDEN,
        }

        inflation_count = sum(
            1 for inc in inconsistencies if inc.inconsistency_type in inflation_types
        )

        return inflation_count >= len(inconsistencies) * 0.7

    def _has_cross_domain_pattern(self, inconsistencies: list[DetectedInconsistency]) -> bool:
        """Check for cross-domain inconsistency pattern.

        Args:
            inconsistencies: List of inconsistencies.

        Returns:
            True if cross-domain pattern detected.
        """
        domains = set()
        for inc in inconsistencies:
            field_lower = inc.field.lower()
            if "education" in field_lower or "degree" in field_lower:
                domains.add("education")
            elif "employ" in field_lower or "title" in field_lower or "job" in field_lower:
                domains.add("employment")
            elif "address" in field_lower or "location" in field_lower:
                domains.add("address")
            elif "name" in field_lower or "identity" in field_lower:
                domains.add("identity")
            else:
                domains.add("other")

        return len(domains) >= 3

    def _calculate_inconsistency_deception_score(
        self, inconsistencies: list[DetectedInconsistency]
    ) -> float:
        """Calculate deception score from inconsistencies.

        Args:
            inconsistencies: List of inconsistencies.

        Returns:
            Deception score (0.0-1.0).
        """
        if not inconsistencies:
            return 0.0

        # Sum up deception likelihood for each inconsistency
        total_score = 0.0
        for inc in inconsistencies:
            base = DECEPTION_LIKELIHOOD.get(inc.inconsistency_type, 0.3)
            # Use existing deception_score if available
            total_score += max(base, inc.deception_score)

        # Average and apply count modifier
        avg_score = total_score / len(inconsistencies)

        # Boost for multiple inconsistencies
        count_modifier = 1.0
        if len(inconsistencies) >= self.config.systematic_threshold:
            count_modifier = 1.3
        elif len(inconsistencies) >= 2:
            count_modifier = 1.1

        return min(1.0, avg_score * count_modifier)

    def _score_to_risk_level(
        self, score: float
    ) -> Literal["none", "low", "moderate", "high", "critical"]:
        """Convert deception score to risk level.

        Args:
            score: Deception score (0.0-1.0).

        Returns:
            Risk level string.
        """
        if score >= self.config.deception_critical_threshold:
            return "critical"
        elif score >= self.config.deception_warning_threshold:
            return "high"
        elif score >= 0.3:
            return "moderate"
        elif score >= 0.1:
            return "low"
        else:
            return "none"


def create_anomaly_detector(config: DetectorConfig | None = None) -> AnomalyDetector:
    """Create an anomaly detector.

    Args:
        config: Optional detector configuration.

    Returns:
        Configured AnomalyDetector.
    """
    return AnomalyDetector(config=config)
