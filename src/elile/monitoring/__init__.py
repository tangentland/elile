"""Monitoring module for ongoing employee vigilance.

This module provides scheduling and execution of periodic monitoring checks
based on vigilance levels (V1/V2/V3) for ongoing employee surveillance.
"""

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
