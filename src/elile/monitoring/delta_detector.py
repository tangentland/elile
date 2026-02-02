"""Delta Detector for monitoring profile changes.

This module provides delta detection between baseline and current profiles,
identifying new findings, resolved findings, changed findings, risk score
changes, and escalations.

Classes:
    DeltaType: Types of detected changes
    FindingChange: Details of a changed finding
    ConnectionChange: Details of a changed connection
    DeltaResult: Complete delta detection result
    DetectorConfig: Configuration for delta detection
    DeltaDetector: Main delta detection class
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.core.logging import get_logger
from elile.investigation.finding_extractor import Finding, Severity
from elile.monitoring.types import DeltaSeverity, ProfileDelta
from elile.risk.risk_scorer import RiskLevel, RiskScore

logger = get_logger(__name__)


# =============================================================================
# Enums
# =============================================================================


class DeltaType(str, Enum):
    """Types of detected changes."""

    NEW_FINDING = "new_finding"  # New finding detected
    RESOLVED_FINDING = "resolved_finding"  # Finding no longer present
    FINDING_SEVERITY_INCREASED = "finding_severity_increased"  # Severity got worse
    FINDING_SEVERITY_DECREASED = "finding_severity_decreased"  # Severity improved
    FINDING_DETAILS_CHANGED = "finding_details_changed"  # Details updated
    RISK_SCORE_INCREASED = "risk_score_increased"  # Overall risk increased
    RISK_SCORE_DECREASED = "risk_score_decreased"  # Overall risk decreased
    RISK_LEVEL_ESCALATED = "risk_level_escalated"  # Risk level category increased
    RISK_LEVEL_DEESCALATED = "risk_level_deescalated"  # Risk level category decreased
    NEW_CONNECTION = "new_connection"  # New entity connection
    LOST_CONNECTION = "lost_connection"  # Connection no longer present
    CONNECTION_RISK_CHANGED = "connection_risk_changed"  # Connection risk changed


# =============================================================================
# Change Details Models
# =============================================================================


@dataclass
class FindingChange:
    """Details of a changed finding.

    Attributes:
        finding_id: ID of the changed finding
        change_type: Type of change (severity increased/decreased/details changed)
        old_severity: Previous severity level
        new_severity: Current severity level
        old_value: Previous value (for details changes)
        new_value: Current value (for details changes)
        description: Human-readable description of the change
    """

    finding_id: UUID
    change_type: DeltaType
    old_severity: Severity | None = None
    new_severity: Severity | None = None
    old_value: str | None = None
    new_value: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "finding_id": str(self.finding_id),
            "change_type": self.change_type.value,
            "old_severity": self.old_severity.value if self.old_severity else None,
            "new_severity": self.new_severity.value if self.new_severity else None,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "description": self.description,
        }


@dataclass
class ConnectionChange:
    """Details of a changed connection.

    Attributes:
        entity_id: ID of the connected entity
        change_type: Type of change (new/lost/risk changed)
        entity_name: Name of the connected entity (if known)
        old_risk_level: Previous risk level
        new_risk_level: Current risk level
        description: Human-readable description of the change
    """

    entity_id: UUID
    change_type: DeltaType
    entity_name: str | None = None
    old_risk_level: str | None = None
    new_risk_level: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": str(self.entity_id),
            "change_type": self.change_type.value,
            "entity_name": self.entity_name,
            "old_risk_level": self.old_risk_level,
            "new_risk_level": self.new_risk_level,
            "description": self.description,
        }


@dataclass
class RiskScoreChange:
    """Details of risk score changes.

    Attributes:
        old_score: Previous overall risk score
        new_score: Current overall risk score
        score_change: Absolute change in score
        old_level: Previous risk level
        new_level: Current risk level
        level_changed: Whether risk level category changed
        category_changes: Per-category score changes
    """

    old_score: int
    new_score: int
    score_change: int
    old_level: RiskLevel
    new_level: RiskLevel
    level_changed: bool
    category_changes: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "old_score": self.old_score,
            "new_score": self.new_score,
            "score_change": self.score_change,
            "old_level": self.old_level.value,
            "new_level": self.new_level.value,
            "level_changed": self.level_changed,
            "category_changes": self.category_changes,
        }


# =============================================================================
# Delta Result
# =============================================================================


@dataclass
class DeltaResult:
    """Complete result of delta detection between two profiles.

    Attributes:
        result_id: Unique identifier for this result
        entity_id: Entity the comparison was for
        baseline_profile_id: ID of the baseline profile
        current_profile_id: ID of the current profile (if from stored profile)
        detected_at: When the detection was performed
        new_findings: List of new findings detected
        resolved_findings: List of findings that are no longer present
        changed_findings: List of findings with changes
        risk_score_change: Details of risk score changes (if any)
        connection_changes: List of connection changes
        deltas: Generated ProfileDelta objects for alerting
        has_escalation: Whether any escalation was detected
        requires_review: Whether human review is recommended
        summary: Human-readable summary of changes
    """

    result_id: UUID = field(default_factory=uuid7)
    entity_id: UUID | None = None
    baseline_profile_id: UUID | None = None
    current_profile_id: UUID | None = None
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Finding changes
    new_findings: list[Finding] = field(default_factory=list)
    resolved_findings: list[Finding] = field(default_factory=list)
    changed_findings: list[FindingChange] = field(default_factory=list)

    # Risk score changes
    risk_score_change: RiskScoreChange | None = None

    # Connection changes
    connection_changes: list[ConnectionChange] = field(default_factory=list)

    # Generated ProfileDeltas for alerting
    deltas: list[ProfileDelta] = field(default_factory=list)

    # Summary flags
    has_escalation: bool = False
    requires_review: bool = False
    summary: str = ""

    @property
    def has_changes(self) -> bool:
        """Check if any changes were detected."""
        return bool(
            self.new_findings
            or self.resolved_findings
            or self.changed_findings
            or self.risk_score_change
            or self.connection_changes
        )

    @property
    def total_changes(self) -> int:
        """Get total number of changes detected."""
        count = len(self.new_findings) + len(self.resolved_findings) + len(self.changed_findings)
        count += len(self.connection_changes)
        if self.risk_score_change:
            count += 1
        return count

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "baseline_profile_id": (
                str(self.baseline_profile_id) if self.baseline_profile_id else None
            ),
            "current_profile_id": (
                str(self.current_profile_id) if self.current_profile_id else None
            ),
            "detected_at": self.detected_at.isoformat(),
            "new_findings": [f.to_dict() for f in self.new_findings],
            "resolved_findings": [f.to_dict() for f in self.resolved_findings],
            "changed_findings": [c.to_dict() for c in self.changed_findings],
            "risk_score_change": (
                self.risk_score_change.to_dict() if self.risk_score_change else None
            ),
            "connection_changes": [c.to_dict() for c in self.connection_changes],
            "deltas": [d.to_dict() for d in self.deltas],
            "has_escalation": self.has_escalation,
            "requires_review": self.requires_review,
            "summary": self.summary,
            "has_changes": self.has_changes,
            "total_changes": self.total_changes,
        }


# =============================================================================
# Configuration
# =============================================================================


class DetectorConfig(BaseModel):
    """Configuration for the delta detector.

    Attributes:
        risk_score_threshold: Minimum score change to consider significant
        risk_level_change_is_escalation: Treat level changes as escalations
        new_critical_finding_is_escalation: Treat new critical findings as escalations
        new_high_finding_requires_review: Require review for new high findings
        track_detail_changes: Track finding detail changes (not just severity)
        compare_connections: Include connection comparison
        connection_risk_threshold: Minimum connection risk change to report
    """

    risk_score_threshold: int = Field(default=5, ge=1, le=50)
    risk_level_change_is_escalation: bool = True
    new_critical_finding_is_escalation: bool = True
    new_high_finding_requires_review: bool = True
    track_detail_changes: bool = False
    compare_connections: bool = True
    connection_risk_threshold: float = Field(default=0.2, ge=0.0, le=1.0)


# =============================================================================
# Severity Ordering
# =============================================================================

SEVERITY_ORDER = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
RISK_LEVEL_ORDER = [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL]


def severity_rank(severity: Severity) -> int:
    """Get numeric rank for severity (higher = more severe)."""
    return SEVERITY_ORDER.index(severity)


def risk_level_rank(level: RiskLevel) -> int:
    """Get numeric rank for risk level (higher = more severe)."""
    return RISK_LEVEL_ORDER.index(level)


def severity_to_delta_severity(severity: Severity) -> DeltaSeverity:
    """Convert finding Severity to DeltaSeverity."""
    mapping = {
        Severity.LOW: DeltaSeverity.LOW,
        Severity.MEDIUM: DeltaSeverity.MEDIUM,
        Severity.HIGH: DeltaSeverity.HIGH,
        Severity.CRITICAL: DeltaSeverity.CRITICAL,
    }
    return mapping.get(severity, DeltaSeverity.LOW)


# =============================================================================
# Delta Detector
# =============================================================================


class DeltaDetector:
    """Detects changes between baseline and current profiles.

    The DeltaDetector compares two profile snapshots and identifies:
    - New findings (in current but not baseline)
    - Resolved findings (in baseline but not current)
    - Changed findings (severity or details changed)
    - Risk score changes
    - Connection changes (D2/D3 investigations)

    It generates ProfileDelta objects suitable for alerting and assigns
    severity levels based on the nature of changes.

    Attributes:
        config: Detector configuration
    """

    def __init__(self, config: DetectorConfig | None = None) -> None:
        """Initialize the delta detector.

        Args:
            config: Optional detector configuration. Uses defaults if not provided.
        """
        self.config = config or DetectorConfig()

    def detect_deltas(
        self,
        baseline_findings: list[Finding],
        current_findings: list[Finding],
        baseline_risk_score: RiskScore | None = None,
        current_risk_score: RiskScore | None = None,
        baseline_connections: list[dict[str, Any]] | None = None,
        current_connections: list[dict[str, Any]] | None = None,
        entity_id: UUID | None = None,
        baseline_profile_id: UUID | None = None,
        current_profile_id: UUID | None = None,
    ) -> DeltaResult:
        """Detect all deltas between baseline and current state.

        Args:
            baseline_findings: Findings from baseline profile
            current_findings: Current findings to compare
            baseline_risk_score: Baseline risk score (optional)
            current_risk_score: Current risk score (optional)
            baseline_connections: Baseline connections (optional, for D2/D3)
            current_connections: Current connections (optional, for D2/D3)
            entity_id: Entity being compared
            baseline_profile_id: ID of baseline profile
            current_profile_id: ID of current profile

        Returns:
            DeltaResult with all detected changes and generated deltas
        """
        result = DeltaResult(
            entity_id=entity_id,
            baseline_profile_id=baseline_profile_id,
            current_profile_id=current_profile_id,
        )

        # Compare findings
        new, resolved, changed = self._compare_findings(baseline_findings, current_findings)
        result.new_findings = new
        result.resolved_findings = resolved
        result.changed_findings = changed

        # Compare risk scores
        if baseline_risk_score and current_risk_score:
            result.risk_score_change = self._compare_risk_scores(
                baseline_risk_score, current_risk_score
            )

        # Compare connections (handle case where one list is empty but provided)
        if self.config.compare_connections:
            baseline_conns = baseline_connections if baseline_connections is not None else []
            current_conns = current_connections if current_connections is not None else []
            if baseline_conns or current_conns:
                result.connection_changes = self._compare_connections(
                    baseline_conns, current_conns
                )

        # Check for escalations
        result.has_escalation = self._check_escalation(result)

        # Check if review required
        result.requires_review = self._check_requires_review(result)

        # Generate ProfileDelta objects for alerting
        result.deltas = self._generate_profile_deltas(result)

        # Generate summary
        result.summary = self._generate_summary(result)

        logger.info(
            "Delta detection complete",
            entity_id=str(entity_id) if entity_id else None,
            total_changes=result.total_changes,
            has_escalation=result.has_escalation,
            requires_review=result.requires_review,
        )

        return result

    def _compare_findings(
        self,
        baseline: list[Finding],
        current: list[Finding],
    ) -> tuple[list[Finding], list[Finding], list[FindingChange]]:
        """Compare findings between baseline and current.

        Args:
            baseline: Baseline findings
            current: Current findings

        Returns:
            Tuple of (new_findings, resolved_findings, changed_findings)
        """
        baseline_by_id = {f.finding_id: f for f in baseline}
        current_by_id = {f.finding_id: f for f in current}

        baseline_ids = set(baseline_by_id.keys())
        current_ids = set(current_by_id.keys())

        # New findings (in current but not baseline)
        new_findings = [current_by_id[fid] for fid in (current_ids - baseline_ids)]

        # Resolved findings (in baseline but not current)
        resolved_findings = [baseline_by_id[fid] for fid in (baseline_ids - current_ids)]

        # Changed findings (in both, check for changes)
        changed_findings: list[FindingChange] = []
        common_ids = baseline_ids & current_ids

        for fid in common_ids:
            old_finding = baseline_by_id[fid]
            new_finding = current_by_id[fid]

            # Check severity change
            if old_finding.severity != new_finding.severity:
                old_rank = severity_rank(old_finding.severity)
                new_rank = severity_rank(new_finding.severity)

                change_type = (
                    DeltaType.FINDING_SEVERITY_INCREASED
                    if new_rank > old_rank
                    else DeltaType.FINDING_SEVERITY_DECREASED
                )

                changed_findings.append(
                    FindingChange(
                        finding_id=fid,
                        change_type=change_type,
                        old_severity=old_finding.severity,
                        new_severity=new_finding.severity,
                        description=(
                            f"Severity changed from {old_finding.severity.value} "
                            f"to {new_finding.severity.value}"
                        ),
                    )
                )

            # Check details change (if configured)
            elif self.config.track_detail_changes:
                if old_finding.details != new_finding.details:
                    changed_findings.append(
                        FindingChange(
                            finding_id=fid,
                            change_type=DeltaType.FINDING_DETAILS_CHANGED,
                            old_value=old_finding.details[:100] if old_finding.details else None,
                            new_value=new_finding.details[:100] if new_finding.details else None,
                            description="Finding details updated",
                        )
                    )

        return new_findings, resolved_findings, changed_findings

    def _compare_risk_scores(
        self,
        baseline: RiskScore,
        current: RiskScore,
    ) -> RiskScoreChange | None:
        """Compare risk scores between baseline and current.

        Args:
            baseline: Baseline risk score
            current: Current risk score

        Returns:
            RiskScoreChange if significant change, None otherwise
        """
        score_change = current.overall_score - baseline.overall_score
        level_changed = baseline.risk_level != current.risk_level

        # Check if change meets threshold
        if abs(score_change) < self.config.risk_score_threshold and not level_changed:
            return None

        # Calculate category changes
        category_changes: dict[str, int] = {}
        all_categories = set(baseline.category_scores.keys()) | set(current.category_scores.keys())
        for category in all_categories:
            old_cat_score = baseline.category_scores.get(category, 0)
            new_cat_score = current.category_scores.get(category, 0)
            diff = new_cat_score - old_cat_score
            if diff != 0:
                category_changes[category.value if hasattr(category, "value") else str(category)] = (
                    diff
                )

        return RiskScoreChange(
            old_score=baseline.overall_score,
            new_score=current.overall_score,
            score_change=score_change,
            old_level=baseline.risk_level,
            new_level=current.risk_level,
            level_changed=level_changed,
            category_changes=category_changes,
        )

    def _compare_connections(
        self,
        baseline: list[dict[str, Any]],
        current: list[dict[str, Any]],
    ) -> list[ConnectionChange]:
        """Compare connections between baseline and current.

        Args:
            baseline: Baseline connection dicts (must have 'entity_id' key)
            current: Current connection dicts

        Returns:
            List of connection changes
        """
        changes: list[ConnectionChange] = []

        # Index by entity_id
        baseline_by_id = {UUID(c["entity_id"]): c for c in baseline if "entity_id" in c}
        current_by_id = {UUID(c["entity_id"]): c for c in current if "entity_id" in c}

        baseline_ids = set(baseline_by_id.keys())
        current_ids = set(current_by_id.keys())

        # New connections
        for eid in current_ids - baseline_ids:
            conn = current_by_id[eid]
            changes.append(
                ConnectionChange(
                    entity_id=eid,
                    change_type=DeltaType.NEW_CONNECTION,
                    entity_name=conn.get("name"),
                    new_risk_level=conn.get("risk_level"),
                    description=f"New connection: {conn.get('name', 'Unknown')}",
                )
            )

        # Lost connections
        for eid in baseline_ids - current_ids:
            conn = baseline_by_id[eid]
            changes.append(
                ConnectionChange(
                    entity_id=eid,
                    change_type=DeltaType.LOST_CONNECTION,
                    entity_name=conn.get("name"),
                    old_risk_level=conn.get("risk_level"),
                    description=f"Lost connection: {conn.get('name', 'Unknown')}",
                )
            )

        # Changed connection risk
        for eid in baseline_ids & current_ids:
            old_conn = baseline_by_id[eid]
            new_conn = current_by_id[eid]

            old_risk = old_conn.get("risk_score", 0)
            new_risk = new_conn.get("risk_score", 0)

            if abs(new_risk - old_risk) >= self.config.connection_risk_threshold:
                changes.append(
                    ConnectionChange(
                        entity_id=eid,
                        change_type=DeltaType.CONNECTION_RISK_CHANGED,
                        entity_name=new_conn.get("name"),
                        old_risk_level=str(old_risk),
                        new_risk_level=str(new_risk),
                        description=(
                            f"Connection risk changed: {old_conn.get('name', 'Unknown')} "
                            f"({old_risk:.2f} -> {new_risk:.2f})"
                        ),
                    )
                )

        return changes

    def _check_escalation(self, result: DeltaResult) -> bool:
        """Check if result contains any escalation.

        Args:
            result: Delta result to check

        Returns:
            True if escalation detected
        """
        # New critical finding
        if self.config.new_critical_finding_is_escalation and any(
            f.severity == Severity.CRITICAL for f in result.new_findings
        ):
            return True

        # Risk level increased
        if (
            self.config.risk_level_change_is_escalation
            and result.risk_score_change
            and result.risk_score_change.level_changed
        ):
                old_rank = risk_level_rank(result.risk_score_change.old_level)
                new_rank = risk_level_rank(result.risk_score_change.new_level)
                if new_rank > old_rank:
                    return True

        # Severity increased to critical
        for change in result.changed_findings:
            if (
                change.change_type == DeltaType.FINDING_SEVERITY_INCREASED
                and change.new_severity == Severity.CRITICAL
            ):
                return True

        return False

    def _check_requires_review(self, result: DeltaResult) -> bool:
        """Check if result requires human review.

        Args:
            result: Delta result to check

        Returns:
            True if review required
        """
        # Escalation always requires review
        if result.has_escalation:
            return True

        # New high findings
        if self.config.new_high_finding_requires_review and any(
            f.severity in (Severity.HIGH, Severity.CRITICAL) for f in result.new_findings
        ):
            return True

        # Significant risk score increase
        return bool(result.risk_score_change and result.risk_score_change.score_change >= 20)

    def _generate_profile_deltas(self, result: DeltaResult) -> list[ProfileDelta]:
        """Generate ProfileDelta objects from the result.

        Args:
            result: Delta result to convert

        Returns:
            List of ProfileDelta objects for alerting
        """
        deltas: list[ProfileDelta] = []

        # New findings
        for finding in result.new_findings:
            deltas.append(
                ProfileDelta(
                    delta_type=DeltaType.NEW_FINDING.value,
                    category=finding.category.value if finding.category else "unknown",
                    severity=severity_to_delta_severity(finding.severity),
                    description=f"New finding: {finding.summary}",
                    current_value=finding.summary,
                    source_provider=finding.sources[0].provider_id if finding.sources else None,
                    requires_review=finding.severity in (Severity.HIGH, Severity.CRITICAL),
                    metadata={
                        "finding_id": str(finding.finding_id),
                        "finding_type": finding.finding_type,
                    },
                )
            )

        # Resolved findings (positive change)
        for finding in result.resolved_findings:
            deltas.append(
                ProfileDelta(
                    delta_type=DeltaType.RESOLVED_FINDING.value,
                    category=finding.category.value if finding.category else "unknown",
                    severity=DeltaSeverity.POSITIVE,
                    description=f"Finding resolved: {finding.summary}",
                    previous_value=finding.summary,
                    requires_review=False,
                    metadata={
                        "finding_id": str(finding.finding_id),
                        "previous_severity": finding.severity.value,
                    },
                )
            )

        # Changed findings
        for change in result.changed_findings:
            severity = DeltaSeverity.MEDIUM
            if change.change_type == DeltaType.FINDING_SEVERITY_INCREASED:
                if change.new_severity == Severity.CRITICAL:
                    severity = DeltaSeverity.CRITICAL
                elif change.new_severity == Severity.HIGH:
                    severity = DeltaSeverity.HIGH
            elif change.change_type == DeltaType.FINDING_SEVERITY_DECREASED:
                severity = DeltaSeverity.POSITIVE

            deltas.append(
                ProfileDelta(
                    delta_type=change.change_type.value,
                    category="finding_change",
                    severity=severity,
                    description=change.description,
                    previous_value=(
                        change.old_severity.value if change.old_severity else change.old_value
                    ),
                    current_value=(
                        change.new_severity.value if change.new_severity else change.new_value
                    ),
                    requires_review=change.change_type == DeltaType.FINDING_SEVERITY_INCREASED,
                    metadata={"finding_id": str(change.finding_id)},
                )
            )

        # Risk score change
        if result.risk_score_change:
            rsc = result.risk_score_change
            if rsc.score_change > 0:
                severity = DeltaSeverity.MEDIUM
                if rsc.level_changed:
                    if rsc.new_level == RiskLevel.CRITICAL:
                        severity = DeltaSeverity.CRITICAL
                    elif rsc.new_level == RiskLevel.HIGH:
                        severity = DeltaSeverity.HIGH
                delta_type = (
                    DeltaType.RISK_LEVEL_ESCALATED.value
                    if rsc.level_changed
                    else DeltaType.RISK_SCORE_INCREASED.value
                )
            else:
                severity = DeltaSeverity.POSITIVE
                delta_type = (
                    DeltaType.RISK_LEVEL_DEESCALATED.value
                    if rsc.level_changed
                    else DeltaType.RISK_SCORE_DECREASED.value
                )

            deltas.append(
                ProfileDelta(
                    delta_type=delta_type,
                    category="risk_score",
                    severity=severity,
                    description=(
                        f"Risk score changed from {rsc.old_score} to {rsc.new_score} "
                        f"({rsc.old_level.value} -> {rsc.new_level.value})"
                    ),
                    previous_value=str(rsc.old_score),
                    current_value=str(rsc.new_score),
                    requires_review=rsc.level_changed and rsc.score_change > 0,
                    metadata={
                        "score_change": rsc.score_change,
                        "category_changes": rsc.category_changes,
                    },
                )
            )

        # Connection changes
        for conn_change in result.connection_changes:
            if conn_change.change_type == DeltaType.NEW_CONNECTION:
                severity = DeltaSeverity.MEDIUM
                if conn_change.new_risk_level in ("high", "critical"):
                    severity = DeltaSeverity.HIGH
            elif conn_change.change_type == DeltaType.LOST_CONNECTION:
                severity = DeltaSeverity.LOW
            else:
                severity = DeltaSeverity.MEDIUM

            deltas.append(
                ProfileDelta(
                    delta_type=conn_change.change_type.value,
                    category="connection",
                    severity=severity,
                    description=conn_change.description,
                    previous_value=conn_change.old_risk_level,
                    current_value=conn_change.new_risk_level,
                    requires_review=conn_change.change_type == DeltaType.NEW_CONNECTION,
                    metadata={
                        "entity_id": str(conn_change.entity_id),
                        "entity_name": conn_change.entity_name,
                    },
                )
            )

        return deltas

    def _generate_summary(self, result: DeltaResult) -> str:
        """Generate human-readable summary of changes.

        Args:
            result: Delta result to summarize

        Returns:
            Summary string
        """
        if not result.has_changes:
            return "No changes detected"

        parts: list[str] = []

        if result.new_findings:
            critical = sum(1 for f in result.new_findings if f.severity == Severity.CRITICAL)
            high = sum(1 for f in result.new_findings if f.severity == Severity.HIGH)
            total = len(result.new_findings)
            parts.append(f"{total} new finding(s)")
            if critical:
                parts[-1] += f" ({critical} critical)"
            elif high:
                parts[-1] += f" ({high} high)"

        if result.resolved_findings:
            parts.append(f"{len(result.resolved_findings)} resolved finding(s)")

        if result.changed_findings:
            increased = sum(
                1
                for c in result.changed_findings
                if c.change_type == DeltaType.FINDING_SEVERITY_INCREASED
            )
            decreased = sum(
                1
                for c in result.changed_findings
                if c.change_type == DeltaType.FINDING_SEVERITY_DECREASED
            )
            if increased:
                parts.append(f"{increased} severity increase(s)")
            if decreased:
                parts.append(f"{decreased} severity decrease(s)")

        if result.risk_score_change:
            rsc = result.risk_score_change
            direction = "increased" if rsc.score_change > 0 else "decreased"
            parts.append(f"risk score {direction} by {abs(rsc.score_change)}")
            if rsc.level_changed:
                parts[-1] += f" ({rsc.old_level.value} -> {rsc.new_level.value})"

        if result.connection_changes:
            new_conn = sum(
                1 for c in result.connection_changes if c.change_type == DeltaType.NEW_CONNECTION
            )
            lost_conn = sum(
                1 for c in result.connection_changes if c.change_type == DeltaType.LOST_CONNECTION
            )
            if new_conn:
                parts.append(f"{new_conn} new connection(s)")
            if lost_conn:
                parts.append(f"{lost_conn} lost connection(s)")

        summary = ", ".join(parts)
        if result.has_escalation:
            summary = "[ESCALATION] " + summary
        elif result.requires_review:
            summary = "[REVIEW REQUIRED] " + summary

        return summary


# =============================================================================
# Factory Function
# =============================================================================


def create_delta_detector(config: DetectorConfig | None = None) -> DeltaDetector:
    """Create a delta detector with default or provided configuration.

    Args:
        config: Optional detector configuration

    Returns:
        Configured DeltaDetector instance
    """
    return DeltaDetector(config=config)
