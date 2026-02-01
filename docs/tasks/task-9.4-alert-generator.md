# Task 9.4: Alert Generator

## Overview

Implement alert generator that evaluates deltas against severity thresholds, generates alerts with priority routing, and sends notifications via multiple channels.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 9.3: Delta Detector

## Implementation

```python
# src/elile/monitoring/alert_generator.py
class AlertGenerator:
    """Generates and routes monitoring alerts."""

    ALERT_THRESHOLDS = {
        VigilanceLevel.V1: Severity.CRITICAL,  # Only critical
        VigilanceLevel.V2: Severity.HIGH,      # High and above
        VigilanceLevel.V3: Severity.MEDIUM     # Medium and above
    }

    async def evaluate_and_alert(
        self,
        deltas: list[ProfileDelta],
        vigilance_level: VigilanceLevel,
        recipients: list[str]
    ) -> list[Alert]:
        """Evaluate deltas and generate alerts."""

        threshold = self.ALERT_THRESHOLDS[vigilance_level]
        alerts = []

        for delta in deltas:
            if self._should_alert(delta, threshold):
                alert = Alert(
                    alert_id=uuid4(),
                    severity=self._determine_severity(delta),
                    summary=self._generate_summary(delta),
                    delta=delta,
                    generated_at=datetime.now(timezone.utc)
                )
                alerts.append(alert)

                # Send notifications
                await self._send_notifications(alert, recipients)

        return alerts

    def _should_alert(self, delta: ProfileDelta, threshold: Severity) -> bool:
        """Check if delta meets alert threshold."""
        pass

    async def _send_notifications(
        self,
        alert: Alert,
        recipients: list[str]
    ) -> None:
        """Send alert via email/webhook/SMS."""
        pass
```

## Acceptance Criteria

- [ ] Evaluates deltas against thresholds
- [ ] V1: alerts on CRITICAL only
- [ ] V2: alerts on HIGH+
- [ ] V3: alerts on MEDIUM+
- [ ] Sends email/webhook/SMS notifications

## Deliverables

- `src/elile/monitoring/alert_generator.py`
- `tests/unit/test_alert_generator.py`

## References

- Architecture: [04-monitoring.md](../../docs/architecture/04-monitoring.md) - Alert Management

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
