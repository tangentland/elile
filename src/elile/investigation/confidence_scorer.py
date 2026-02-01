"""Confidence Scorer for SAR loop assessment.

This module provides standalone confidence scoring for information types.
It evaluates completeness, corroboration, query success, and fact quality
to produce a weighted confidence score.

The scorer is configurable, allowing customization of:
- Expected fact counts per information type
- Factor weights for scoring
- Foundation type adjustments
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from elile.agent.state import InformationType
from elile.core.logging import get_logger
from elile.investigation.query_executor import QueryResult, QueryStatus
from elile.investigation.result_assessor import Fact

logger = get_logger(__name__)


class ScorerConfig(BaseModel):
    """Configuration for confidence scoring."""

    # Factor weights (must sum to 1.0)
    completeness_weight: float = Field(default=0.30, ge=0.0, le=1.0)
    corroboration_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    query_success_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    fact_confidence_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    source_diversity_weight: float = Field(default=0.10, ge=0.0, le=1.0)

    # Foundation type bonus (higher confidence requirement for foundation types)
    foundation_type_threshold_boost: float = Field(default=0.05, ge=0.0, le=0.2)

    # Minimum sources for full corroboration score
    min_sources_for_full_corroboration: int = Field(default=2, ge=1)

    # Minimum sources for full diversity score
    min_sources_for_full_diversity: int = Field(default=3, ge=1)

    def get_weights(self) -> dict[str, float]:
        """Get all factor weights as a dictionary."""
        return {
            "completeness": self.completeness_weight,
            "corroboration": self.corroboration_weight,
            "query_success": self.query_success_weight,
            "fact_confidence": self.fact_confidence_weight,
            "source_diversity": self.source_diversity_weight,
        }


# Default expected fact counts per information type
DEFAULT_EXPECTED_FACTS: dict[InformationType, int] = {
    InformationType.IDENTITY: 5,  # name, dob, ssn_last4, address, phone
    InformationType.EMPLOYMENT: 3,  # employer, title, dates
    InformationType.EDUCATION: 3,  # school, degree, dates
    InformationType.LICENSES: 2,  # license, status
    InformationType.CRIMINAL: 1,  # records check completed
    InformationType.CIVIL: 1,  # litigation check completed
    InformationType.FINANCIAL: 2,  # credit, bankruptcy
    InformationType.REGULATORY: 1,  # regulatory actions
    InformationType.SANCTIONS: 1,  # sanctions status
    InformationType.ADVERSE_MEDIA: 1,  # media mentions
    InformationType.DIGITAL_FOOTPRINT: 2,  # social, digital presence
    InformationType.NETWORK_D2: 2,  # direct associates
    InformationType.NETWORK_D3: 3,  # extended network
    InformationType.RECONCILIATION: 5,  # all verified facts
}

# Foundation types that get stricter scoring
FOUNDATION_TYPES: set[InformationType] = {
    InformationType.IDENTITY,
    InformationType.EMPLOYMENT,
    InformationType.EDUCATION,
}


@dataclass
class FactorBreakdown:
    """Detailed breakdown of a single confidence factor."""

    name: str
    raw_value: float  # 0.0 - 1.0
    weight: float
    weighted_value: float  # raw_value * weight
    description: str = ""


@dataclass
class ConfidenceScore:
    """Complete confidence score with contributing factors.

    Provides the overall score, individual factor values, and
    threshold comparison for SAR loop decision-making.
    """

    info_type: InformationType
    overall_score: float  # 0.0 - 1.0

    # Individual factors
    completeness: float = 0.0
    corroboration: float = 0.0
    query_success: float = 0.0
    fact_confidence: float = 0.0
    source_diversity: float = 0.0

    # Threshold comparison
    threshold: float = 0.85
    meets_threshold: bool = False
    is_foundation_type: bool = False

    # Statistics
    fact_count: int = 0
    expected_fact_count: int = 0
    source_count: int = 0
    query_count: int = 0
    successful_query_count: int = 0

    # Detailed breakdown
    factor_breakdown: list[FactorBreakdown] = field(default_factory=list)

    @property
    def gap_to_threshold(self) -> float:
        """How far below threshold (0 if meets threshold)."""
        return max(0.0, self.threshold - self.overall_score)

    @property
    def factors_dict(self) -> dict[str, float]:
        """Get factors as a dictionary."""
        return {
            "completeness": self.completeness,
            "corroboration": self.corroboration,
            "query_success": self.query_success,
            "fact_confidence": self.fact_confidence,
            "source_diversity": self.source_diversity,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "info_type": self.info_type.value,
            "overall_score": self.overall_score,
            "factors": self.factors_dict,
            "threshold": self.threshold,
            "meets_threshold": self.meets_threshold,
            "is_foundation_type": self.is_foundation_type,
            "gap_to_threshold": self.gap_to_threshold,
            "statistics": {
                "fact_count": self.fact_count,
                "expected_fact_count": self.expected_fact_count,
                "source_count": self.source_count,
                "query_count": self.query_count,
                "successful_query_count": self.successful_query_count,
            },
        }


class ConfidenceScorer:
    """Calculates confidence scores for information types.

    The ConfidenceScorer evaluates gathered information using five factors:
    1. Completeness: Did we find the expected facts for this type?
    2. Corroboration: Are facts verified by multiple sources?
    3. Query Success: What percentage of queries succeeded?
    4. Fact Confidence: What is the average confidence of extracted facts?
    5. Source Diversity: How many different providers contributed?

    Each factor is weighted and combined for an overall score.

    Example:
        ```python
        scorer = ConfidenceScorer()

        score = scorer.calculate_confidence(
            info_type=InformationType.IDENTITY,
            facts=extracted_facts,
            query_results=results,
            threshold=0.85,
        )

        if score.meets_threshold:
            print("Confidence threshold met!")
        else:
            print(f"Gap to threshold: {score.gap_to_threshold:.2f}")
        ```
    """

    def __init__(
        self,
        config: ScorerConfig | None = None,
        expected_facts: dict[InformationType, int] | None = None,
    ):
        """Initialize the confidence scorer.

        Args:
            config: Scoring configuration. Uses defaults if not provided.
            expected_facts: Expected fact counts per type. Uses defaults if not provided.
        """
        self.config = config or ScorerConfig()
        self.expected_facts = expected_facts or DEFAULT_EXPECTED_FACTS.copy()

    def calculate_confidence(
        self,
        info_type: InformationType,
        facts: list[Fact],
        query_results: list[QueryResult],
        threshold: float = 0.85,
    ) -> ConfidenceScore:
        """Calculate overall confidence score for an information type.

        Args:
            info_type: The information type being scored.
            facts: List of extracted facts.
            query_results: List of query execution results.
            threshold: Confidence threshold for this type.

        Returns:
            ConfidenceScore with overall score and factor breakdown.
        """
        weights = self.config.get_weights()
        is_foundation = info_type in FOUNDATION_TYPES

        # Apply foundation type boost to threshold
        effective_threshold = threshold
        if is_foundation:
            effective_threshold = min(threshold + self.config.foundation_type_threshold_boost, 1.0)

        # Calculate individual factors
        completeness = self._calculate_completeness(info_type, facts)
        corroboration = self._calculate_corroboration(facts)
        query_success = self._calculate_query_success(query_results)
        fact_confidence = self._calculate_fact_confidence(facts)
        source_diversity = self._calculate_source_diversity(facts)

        # Calculate weighted score
        overall = (
            completeness * weights["completeness"]
            + corroboration * weights["corroboration"]
            + query_success * weights["query_success"]
            + fact_confidence * weights["fact_confidence"]
            + source_diversity * weights["source_diversity"]
        )

        # Build factor breakdown
        factor_breakdown = [
            FactorBreakdown(
                name="completeness",
                raw_value=completeness,
                weight=weights["completeness"],
                weighted_value=completeness * weights["completeness"],
                description=f"{len(facts)}/{self.expected_facts.get(info_type, 1)} expected facts",
            ),
            FactorBreakdown(
                name="corroboration",
                raw_value=corroboration,
                weight=weights["corroboration"],
                weighted_value=corroboration * weights["corroboration"],
                description="Multi-source verification",
            ),
            FactorBreakdown(
                name="query_success",
                raw_value=query_success,
                weight=weights["query_success"],
                weighted_value=query_success * weights["query_success"],
                description=f"{sum(1 for r in query_results if r.status == QueryStatus.SUCCESS)}/{len(query_results)} queries succeeded",
            ),
            FactorBreakdown(
                name="fact_confidence",
                raw_value=fact_confidence,
                weight=weights["fact_confidence"],
                weighted_value=fact_confidence * weights["fact_confidence"],
                description="Average fact confidence",
            ),
            FactorBreakdown(
                name="source_diversity",
                raw_value=source_diversity,
                weight=weights["source_diversity"],
                weighted_value=source_diversity * weights["source_diversity"],
                description=f"{len({f.source_provider for f in facts})} unique sources",
            ),
        ]

        # Gather statistics
        unique_sources = {f.source_provider for f in facts}
        successful_queries = sum(1 for r in query_results if r.status == QueryStatus.SUCCESS)

        score = ConfidenceScore(
            info_type=info_type,
            overall_score=overall,
            completeness=completeness,
            corroboration=corroboration,
            query_success=query_success,
            fact_confidence=fact_confidence,
            source_diversity=source_diversity,
            threshold=effective_threshold,
            meets_threshold=overall >= effective_threshold,
            is_foundation_type=is_foundation,
            fact_count=len(facts),
            expected_fact_count=self.expected_facts.get(info_type, 1),
            source_count=len(unique_sources),
            query_count=len(query_results),
            successful_query_count=successful_queries,
            factor_breakdown=factor_breakdown,
        )

        logger.debug(
            "Confidence calculated",
            info_type=info_type.value,
            overall_score=overall,
            meets_threshold=score.meets_threshold,
            threshold=effective_threshold,
        )

        return score

    def calculate_aggregate_confidence(
        self,
        scores: list[ConfidenceScore],
    ) -> float:
        """Calculate aggregate confidence across multiple types.

        Foundation types are weighted more heavily in the aggregate.

        Args:
            scores: List of individual type scores.

        Returns:
            Aggregate confidence score (0.0 - 1.0).
        """
        if not scores:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0

        for score in scores:
            # Foundation types get 1.5x weight
            weight = 1.5 if score.is_foundation_type else 1.0
            weighted_sum += score.overall_score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def get_expected_facts(self, info_type: InformationType) -> int:
        """Get expected fact count for an information type.

        Args:
            info_type: Information type to check.

        Returns:
            Expected fact count.
        """
        return self.expected_facts.get(info_type, 1)

    def set_expected_facts(self, info_type: InformationType, count: int) -> None:
        """Set expected fact count for an information type.

        Args:
            info_type: Information type to configure.
            count: Expected fact count.
        """
        self.expected_facts[info_type] = count

    def _calculate_completeness(
        self,
        info_type: InformationType,
        facts: list[Fact],
    ) -> float:
        """Calculate data completeness factor.

        Completeness is the ratio of actual facts to expected facts,
        capped at 1.0 (having more facts than expected doesn't increase score).

        Args:
            info_type: Information type.
            facts: Extracted facts.

        Returns:
            Completeness score (0.0 - 1.0).
        """
        expected = self.expected_facts.get(info_type, 1)
        if expected <= 0:
            return 1.0 if facts else 0.0

        actual = len(facts)
        return min(actual / expected, 1.0)

    def _calculate_corroboration(self, facts: list[Fact]) -> float:
        """Calculate multi-source corroboration factor.

        Corroboration measures how many fact types have been verified
        by multiple independent sources.

        Args:
            facts: Extracted facts.

        Returns:
            Corroboration score (0.0 - 1.0).
        """
        if not facts:
            return 0.0

        # Group facts by type
        fact_groups: dict[str, list[Fact]] = defaultdict(list)
        for fact in facts:
            fact_groups[fact.fact_type].append(fact)

        if not fact_groups:
            return 0.0

        # Count groups with multiple sources
        min_sources = self.config.min_sources_for_full_corroboration
        corroborated = 0

        for group_facts in fact_groups.values():
            unique_sources = {f.source_provider for f in group_facts}
            if len(unique_sources) >= min_sources:
                corroborated += 1

        return corroborated / len(fact_groups)

    def _calculate_query_success(self, results: list[QueryResult]) -> float:
        """Calculate query success rate factor.

        Args:
            results: Query execution results.

        Returns:
            Query success rate (0.0 - 1.0).
        """
        if not results:
            return 0.0

        successful = sum(1 for r in results if r.status == QueryStatus.SUCCESS)
        return successful / len(results)

    def _calculate_fact_confidence(self, facts: list[Fact]) -> float:
        """Calculate average fact confidence factor.

        Args:
            facts: Extracted facts.

        Returns:
            Average fact confidence (0.0 - 1.0).
        """
        if not facts:
            return 0.0

        total_confidence = sum(f.confidence for f in facts)
        return total_confidence / len(facts)

    def _calculate_source_diversity(self, facts: list[Fact]) -> float:
        """Calculate source diversity factor.

        Source diversity rewards having information from multiple
        independent data providers.

        Args:
            facts: Extracted facts.

        Returns:
            Source diversity score (0.0 - 1.0).
        """
        if not facts:
            return 0.0

        unique_sources = {f.source_provider for f in facts}
        min_sources = self.config.min_sources_for_full_diversity

        # Scale: 1 source = 0.33, 2 sources = 0.67, 3+ sources = 1.0
        return min(len(unique_sources) / min_sources, 1.0)


def create_confidence_scorer(
    config: ScorerConfig | None = None,
    expected_facts: dict[InformationType, int] | None = None,
) -> ConfidenceScorer:
    """Factory function to create a ConfidenceScorer.

    Args:
        config: Optional scoring configuration.
        expected_facts: Optional expected facts per type.

    Returns:
        Configured ConfidenceScorer instance.
    """
    return ConfidenceScorer(config=config, expected_facts=expected_facts)
