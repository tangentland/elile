# Task 3.5: Profile Delta Computation

## Overview

Compute delta between two profile versions identifying new/resolved/changed findings, risk score changes, and connection changes. Critical for ongoing monitoring (Phase 9).

**Priority**: P0 | **Effort**: 2-3 days | **Status**: Not Started

## Dependencies

- Task 3.4: Profile Version Manager

## Implementation Checklist

- [ ] Create ProfileDelta model
- [ ] Implement finding comparison logic
- [ ] Build connection diff algorithm
- [ ] Add risk score change calculation
- [ ] Create delta visualization helpers
- [ ] Write delta computation tests

## Key Implementation

```python
# src/elile/services/profile_delta.py
from dataclasses import dataclass

@dataclass
class FindingChange:
    """Represents a change in a finding."""
    finding_id: UUID
    change_type: Literal["severity_increased", "severity_decreased", "details_changed"]
    old_value: Any
    new_value: Any

@dataclass
class ProfileDelta:
    """Delta between two profile versions."""
    entity_id: UUID
    old_version: int
    new_version: int

    # Finding changes
    new_findings: list[Finding]
    resolved_findings: list[Finding]  # Findings that disappeared
    changed_findings: list[FindingChange]

    # Risk changes
    risk_score_change: float
    risk_score_old: float
    risk_score_new: float

    # Connection changes
    connection_count_change: int
    new_connections: list[EntityConnection]
    lost_connections: list[EntityConnection]

    # Evolution signals
    evolution_signals: list[dict]  # Detected patterns

class ProfileDeltaComputer:
    """Compute delta between profile versions."""

    async def compute_delta(
        self,
        old_profile: EntityProfile,
        new_profile: EntityProfile
    ) -> ProfileDelta:
        """Compute delta between two profiles."""
        assert old_profile.entity_id == new_profile.entity_id
        assert old_profile.version < new_profile.version

        # Load findings for both profiles
        old_findings = await self._load_findings(old_profile.profile_id)
        new_findings = await self._load_findings(new_profile.profile_id)

        # Compute finding deltas
        new, resolved, changed = self._compare_findings(old_findings, new_findings)

        # Compute connection deltas
        old_connections = old_profile.entity_graph.get("connections", [])
        new_connections = new_profile.entity_graph.get("connections", [])
        new_conn, lost_conn = self._compare_connections(old_connections, new_connections)

        # Calculate risk score change
        risk_change = new_profile.risk_score - old_profile.risk_score

        # Detect evolution patterns
        signals = self._detect_evolution_signals(
            new_findings=new,
            resolved_findings=resolved,
            risk_change=risk_change,
            connection_change=len(new_conn) - len(lost_conn)
        )

        return ProfileDelta(
            entity_id=old_profile.entity_id,
            old_version=old_profile.version,
            new_version=new_profile.version,
            new_findings=new,
            resolved_findings=resolved,
            changed_findings=changed,
            risk_score_change=risk_change,
            risk_score_old=old_profile.risk_score,
            risk_score_new=new_profile.risk_score,
            connection_count_change=len(new_conn) - len(lost_conn),
            new_connections=new_conn,
            lost_connections=lost_conn,
            evolution_signals=signals
        )

    def _compare_findings(
        self,
        old: list[Finding],
        new: list[Finding]
    ) -> tuple[list[Finding], list[Finding], list[FindingChange]]:
        """Compare findings and return (new, resolved, changed)."""
        old_by_id = {f.finding_id: f for f in old}
        new_by_id = {f.finding_id: f for f in new}

        new_findings = [f for f in new if f.finding_id not in old_by_id]
        resolved_findings = [f for f in old if f.finding_id not in new_by_id]
        changed_findings = []

        # Check for changes in existing findings
        for finding_id in set(old_by_id.keys()) & set(new_by_id.keys()):
            old_f = old_by_id[finding_id]
            new_f = new_by_id[finding_id]

            if old_f.severity != new_f.severity:
                changed_findings.append(FindingChange(
                    finding_id=finding_id,
                    change_type="severity_increased" if new_f.severity > old_f.severity else "severity_decreased",
                    old_value=old_f.severity,
                    new_value=new_f.severity
                ))

        return new_findings, resolved_findings, changed_findings

    def _compare_connections(
        self,
        old: list[dict],
        new: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """Compare connections and return (new, lost)."""
        old_ids = {c["entity_id"] for c in old}
        new_ids = {c["entity_id"] for c in new}

        new_connections = [c for c in new if c["entity_id"] not in old_ids]
        lost_connections = [c for c in old if c["entity_id"] not in new_ids]

        return new_connections, lost_connections

    def _detect_evolution_signals(
        self,
        new_findings: list[Finding],
        resolved_findings: list[Finding],
        risk_change: float,
        connection_change: int
    ) -> list[dict]:
        """Detect evolution patterns (basic rule-based)."""
        signals = []

        # Significant risk increase
        if risk_change > 0.3:
            signals.append({
                "type": "risk_escalation",
                "severity": "high",
                "description": f"Risk score increased by {risk_change:.2f}"
            })

        # Rapid network expansion
        if connection_change > 10:
            signals.append({
                "type": "network_expansion",
                "severity": "medium",
                "description": f"Network grew by {connection_change} connections"
            })

        # Many new critical findings
        critical_new = sum(1 for f in new_findings if f.severity == "critical")
        if critical_new >= 3:
            signals.append({
                "type": "critical_findings_surge",
                "severity": "high",
                "description": f"{critical_new} new critical findings"
            })

        return signals
```

## Testing Requirements

### Unit Tests
- Finding comparison (new/resolved/changed)
- Connection comparison
- Risk score change calculation
- Evolution signal detection

### Integration Tests
- Delta between two real profiles
- Empty delta (no changes)
- Large delta (100+ findings)

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] ProfileDelta includes all change types
- [ ] Finding comparison detects new/resolved/changed
- [ ] Connection diff works correctly
- [ ] Risk score change calculated
- [ ] Evolution signals detected
- [ ] Performance acceptable for large profiles

## Deliverables

- `src/elile/services/profile_delta.py`
- `tests/unit/test_profile_delta.py`

## References

- Architecture: [04-monitoring.md](../architecture/04-monitoring.md) - Delta detection
- Dependencies: Task 3.4 (profile versioning)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
