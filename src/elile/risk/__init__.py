"""Risk assessment module for analyzing findings and scoring risks."""

from elile.risk.analyzer import RiskAnalyzer
from elile.risk.anomaly_detector import (
    ANOMALY_TYPE_SEVERITY,
    Anomaly,
    AnomalyDetector,
    AnomalyType,
    create_anomaly_detector,
    DeceptionAssessment,
    DECEPTION_LIKELIHOOD,
    DetectorConfig,
)
from elile.risk.connection_analyzer import (
    AnalyzerConfig,
    ConnectionAnalysisResult,
    ConnectionAnalyzer,
    ConnectionEdge,
    ConnectionGraph,
    ConnectionNode,
    ConnectionRiskType,
    RELATION_RISK_FACTOR,
    RISK_DECAY_PER_HOP,
    RiskPropagationPath,
    STRENGTH_MULTIPLIER,
    create_connection_analyzer,
)
from elile.risk.finding_classifier import (
    CATEGORY_KEYWORDS,
    ClassificationResult,
    ClassifierConfig,
    FindingClassifier,
    ROLE_RELEVANCE_MATRIX,
    SubCategory,
    SUBCATEGORY_KEYWORDS,
    create_finding_classifier,
)
from elile.risk.inconsistency import InconsistencyAnalyzer
from elile.risk.pattern_recognizer import (
    create_pattern_recognizer,
    Pattern,
    PatternRecognizer,
    PatternSummary,
    PatternType,
    RecognizerConfig,
)
from elile.risk.risk_aggregator import (
    AggregatorConfig,
    AssessmentConfidence,
    ANOMALY_SEVERITY_WEIGHT,
    CONNECTION_RISK_WEIGHT,
    ComprehensiveRiskAssessment,
    PATTERN_SEVERITY_WEIGHT,
    RiskAdjustment,
    RiskAggregator,
    create_risk_aggregator,
)
from elile.risk.risk_scorer import (
    Recommendation,
    RiskLevel,
    RiskScore,
    RiskScorer,
    ScorerConfig,
    create_risk_scorer,
)
from elile.risk.scoring import calculate_risk_score
from elile.risk.severity_calculator import (
    CalculatorConfig,
    ROLE_SEVERITY_ADJUSTMENTS,
    SEVERITY_RULES,
    SUBCATEGORY_SEVERITY,
    SeverityCalculator,
    SeverityDecision,
    create_severity_calculator,
)
from elile.risk.temporal_risk_tracker import (
    CategoryDelta,
    create_temporal_risk_tracker,
    EvolutionSignal,
    EvolutionSignalType,
    RiskDelta,
    RiskSnapshot,
    RiskTrend,
    TemporalRiskTracker,
    TrackerConfig,
    TrendDirection,
)

__all__ = [
    # Analyzer
    "RiskAnalyzer",
    "InconsistencyAnalyzer",
    # Anomaly Detector
    "AnomalyDetector",
    "create_anomaly_detector",
    "DetectorConfig",
    "Anomaly",
    "AnomalyType",
    "DeceptionAssessment",
    "ANOMALY_TYPE_SEVERITY",
    "DECEPTION_LIKELIHOOD",
    # Pattern Recognizer
    "PatternRecognizer",
    "create_pattern_recognizer",
    "RecognizerConfig",
    "Pattern",
    "PatternSummary",
    "PatternType",
    # Risk Scorer
    "RiskScorer",
    "create_risk_scorer",
    "ScorerConfig",
    "RiskScore",
    "RiskLevel",
    "Recommendation",
    # Risk Aggregator
    "RiskAggregator",
    "create_risk_aggregator",
    "AggregatorConfig",
    "ComprehensiveRiskAssessment",
    "RiskAdjustment",
    "AssessmentConfidence",
    "PATTERN_SEVERITY_WEIGHT",
    "ANOMALY_SEVERITY_WEIGHT",
    "CONNECTION_RISK_WEIGHT",
    # Severity Calculator
    "SeverityCalculator",
    "create_severity_calculator",
    "CalculatorConfig",
    "SeverityDecision",
    "SEVERITY_RULES",
    "SUBCATEGORY_SEVERITY",
    "ROLE_SEVERITY_ADJUSTMENTS",
    # Legacy scoring function
    "calculate_risk_score",
    # Finding Classifier
    "FindingClassifier",
    "create_finding_classifier",
    "ClassifierConfig",
    "ClassificationResult",
    "SubCategory",
    "CATEGORY_KEYWORDS",
    "SUBCATEGORY_KEYWORDS",
    "ROLE_RELEVANCE_MATRIX",
    # Connection Analyzer
    "ConnectionAnalyzer",
    "create_connection_analyzer",
    "AnalyzerConfig",
    "ConnectionAnalysisResult",
    "ConnectionGraph",
    "ConnectionNode",
    "ConnectionEdge",
    "ConnectionRiskType",
    "RiskPropagationPath",
    "RISK_DECAY_PER_HOP",
    "STRENGTH_MULTIPLIER",
    "RELATION_RISK_FACTOR",
    # Temporal Risk Tracker
    "TemporalRiskTracker",
    "create_temporal_risk_tracker",
    "TrackerConfig",
    "RiskSnapshot",
    "RiskDelta",
    "RiskTrend",
    "EvolutionSignal",
    "EvolutionSignalType",
    "TrendDirection",
    "CategoryDelta",
]
