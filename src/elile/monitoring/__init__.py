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

__all__ = [
    # Scheduler
    "MonitoringScheduler",
    "SchedulerConfig",
    "create_monitoring_scheduler",
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
