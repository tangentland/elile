"""Monitoring module for ongoing employee vigilance.

This module provides scheduling and execution of periodic monitoring checks
based on vigilance levels (V1/V2/V3) for ongoing employee surveillance.
"""

from elile.monitoring.alert_generator import (
    AUTO_ALERT_THRESHOLDS,
    AlertConfig,
    AlertGenerator,
    AlertStatus,
    EscalationTrigger,
    GeneratedAlert,
    MockEmailChannel,
    MockSMSChannel,
    MockWebhookChannel,
    NotificationChannel,
    NotificationChannelType,
    NotificationResult,
    create_alert_generator,
)
from elile.monitoring.delta_detector import (
    ConnectionChange,
    DeltaDetector,
    DeltaResult,
    DeltaType,
    DetectorConfig,
    FindingChange,
    RiskScoreChange,
    create_delta_detector,
)
from elile.monitoring.scheduler import (
    MonitoringScheduler,
    SchedulerConfig,
    create_monitoring_scheduler,
)
from elile.monitoring.types import (
    CheckType,
    LifecycleEvent,
    LifecycleEventType,
    MonitoringCheck,
    MonitoringConfig,
    MonitoringError,
    MonitoringStatus,
    ProfileDelta,
    ScheduleResult,
)
from elile.monitoring.vigilance_manager import (
    RISK_THRESHOLD_V2,
    RISK_THRESHOLD_V3,
    ROLE_DEFAULT_VIGILANCE,
    EscalationAction,
    ManagerConfig,
    RoleVigilanceMapping,
    VigilanceChangeReason,
    VigilanceDecision,
    VigilanceManager,
    VigilanceUpdate,
    create_vigilance_manager,
)

__all__ = [
    # Alert Generator
    "AlertGenerator",
    "AlertConfig",
    "AlertStatus",
    "GeneratedAlert",
    "EscalationTrigger",
    "NotificationChannel",
    "NotificationChannelType",
    "NotificationResult",
    "MockEmailChannel",
    "MockWebhookChannel",
    "MockSMSChannel",
    "AUTO_ALERT_THRESHOLDS",
    "create_alert_generator",
    # Delta Detector
    "DeltaDetector",
    "DetectorConfig",
    "DeltaResult",
    "DeltaType",
    "FindingChange",
    "ConnectionChange",
    "RiskScoreChange",
    "create_delta_detector",
    # Scheduler
    "MonitoringScheduler",
    "SchedulerConfig",
    "create_monitoring_scheduler",
    # Vigilance Manager
    "VigilanceManager",
    "ManagerConfig",
    "VigilanceDecision",
    "VigilanceUpdate",
    "VigilanceChangeReason",
    "EscalationAction",
    "RoleVigilanceMapping",
    "create_vigilance_manager",
    "ROLE_DEFAULT_VIGILANCE",
    "RISK_THRESHOLD_V2",
    "RISK_THRESHOLD_V3",
    # Types
    "CheckType",
    "LifecycleEvent",
    "LifecycleEventType",
    "MonitoringCheck",
    "MonitoringConfig",
    "MonitoringError",
    "MonitoringStatus",
    "ProfileDelta",
    "ScheduleResult",
]
