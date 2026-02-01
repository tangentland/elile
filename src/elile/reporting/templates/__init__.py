"""Report template content builders.

This package contains specialized content builders for each persona's
report type. Each builder transforms compiled screening results into
persona-appropriate structured content.

Available Builders:
- HRSummaryBuilder: HR Manager summary report with risk overview and recommendations

This package also re-exports core template classes from template_definitions
for convenience.
"""

from elile.reporting.template_definitions import (
    ReportTemplate,
    TemplateRegistry,
    create_template_registry,
)
from elile.reporting.templates.hr_summary import (
    CategoryScore,
    CategoryStatus,
    FindingIndicator,
    HRSummaryBuilder,
    HRSummaryConfig,
    HRSummaryContent,
    RecommendedAction,
    RiskAssessmentDisplay,
    create_hr_summary_builder,
)

__all__ = [
    # Core template classes (re-exported from template_definitions)
    "ReportTemplate",
    "TemplateRegistry",
    "create_template_registry",
    # HR Summary Builder
    "HRSummaryBuilder",
    "HRSummaryConfig",
    "create_hr_summary_builder",
    # HR Summary data models
    "HRSummaryContent",
    "RiskAssessmentDisplay",
    "FindingIndicator",
    "CategoryScore",
    "CategoryStatus",
    "RecommendedAction",
]
