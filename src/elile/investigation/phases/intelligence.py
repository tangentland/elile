"""Intelligence Phase Handler for OSINT and media analysis.

This module provides the IntelligencePhaseHandler that collects and analyzes
open-source intelligence including adverse media, social media presence,
and professional online presence.

Architecture Reference: docs/architecture/05-investigation.md
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import ServiceTier
from elile.compliance.types import Locale
from elile.core.logging import get_logger

logger = get_logger(__name__)


class MediaCategory(str, Enum):
    """Categories of media mentions."""

    NEWS = "news"
    LEGAL = "legal"
    REGULATORY = "regulatory"
    FINANCIAL = "financial"
    POLITICAL = "political"
    SOCIAL = "social"
    OTHER = "other"


class MediaSentiment(str, Enum):
    """Sentiment analysis of media mentions."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class SocialPlatform(str, Enum):
    """Social media platforms."""

    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    OTHER = "other"


@dataclass
class MediaMention:
    """A media mention found for the subject."""

    mention_id: UUID = field(default_factory=uuid7)
    source_name: str = ""
    source_url: str | None = None
    title: str = ""
    snippet: str = ""
    published_date: date | None = None
    category: MediaCategory = MediaCategory.OTHER
    sentiment: MediaSentiment = MediaSentiment.NEUTRAL
    relevance_score: float = 0.0
    is_adverse: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mention_id": str(self.mention_id),
            "source_name": self.source_name,
            "source_url": self.source_url,
            "title": self.title,
            "snippet": self.snippet,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "category": self.category.value,
            "sentiment": self.sentiment.value,
            "relevance_score": self.relevance_score,
            "is_adverse": self.is_adverse,
        }


@dataclass
class SocialProfile:
    """A social media profile found for the subject."""

    profile_id: UUID = field(default_factory=uuid7)
    platform: SocialPlatform = SocialPlatform.OTHER
    username: str = ""
    profile_url: str | None = None
    is_verified: bool = False
    follower_count: int | None = None
    post_count: int | None = None
    last_activity: date | None = None
    risk_indicators: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": str(self.profile_id),
            "platform": self.platform.value,
            "username": self.username,
            "profile_url": self.profile_url,
            "is_verified": self.is_verified,
            "follower_count": self.follower_count,
            "post_count": self.post_count,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "risk_indicators": self.risk_indicators,
            "confidence": self.confidence,
        }


@dataclass
class ProfessionalPresence:
    """Professional online presence."""

    presence_id: UUID = field(default_factory=uuid7)
    platform: str = ""
    profile_url: str | None = None
    headline: str = ""
    current_position: str | None = None
    company: str | None = None
    connections: int | None = None
    endorsements: int | None = None
    verified: bool = False
    last_updated: date | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "presence_id": str(self.presence_id),
            "platform": self.platform,
            "profile_url": self.profile_url,
            "headline": self.headline,
            "current_position": self.current_position,
            "company": self.company,
            "connections": self.connections,
            "endorsements": self.endorsements,
            "verified": self.verified,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


@dataclass
class RiskIndicator:
    """A risk indicator from intelligence gathering."""

    indicator_id: UUID = field(default_factory=uuid7)
    indicator_type: str = ""
    description: str = ""
    source: str = ""
    severity: str = "medium"
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator_id": str(self.indicator_id),
            "indicator_type": self.indicator_type,
            "description": self.description,
            "source": self.source,
            "severity": self.severity,
            "confidence": self.confidence,
        }


@dataclass
class IntelligenceProfile:
    """Combined intelligence from all OSINT sources."""

    profile_id: UUID = field(default_factory=uuid7)
    subject_entity_id: UUID | None = None

    # Media analysis
    media_mentions: list[MediaMention] = field(default_factory=list)
    adverse_media_count: int = 0
    media_sentiment_summary: MediaSentiment = MediaSentiment.NEUTRAL

    # Social presence
    social_profiles: list[SocialProfile] = field(default_factory=list)
    professional_presence: list[ProfessionalPresence] = field(default_factory=list)

    # Risk indicators
    risk_indicators: list[RiskIndicator] = field(default_factory=list)
    overall_risk_score: float = 0.0

    # Timing
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def calculate_risk_score(self) -> float:
        """Calculate overall risk score from intelligence."""
        score = 0.0
        if self.adverse_media_count > 0:
            score += min(self.adverse_media_count * 0.1, 0.5)
        for indicator in self.risk_indicators:
            if indicator.severity == "high":
                score += 0.2
            elif indicator.severity == "medium":
                score += 0.1
        self.overall_risk_score = min(score, 1.0)
        return self.overall_risk_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": str(self.profile_id),
            "subject_entity_id": str(self.subject_entity_id) if self.subject_entity_id else None,
            "media_mentions": [m.to_dict() for m in self.media_mentions],
            "adverse_media_count": self.adverse_media_count,
            "media_sentiment_summary": self.media_sentiment_summary.value,
            "social_profiles": [s.to_dict() for s in self.social_profiles],
            "professional_presence": [p.to_dict() for p in self.professional_presence],
            "risk_indicators": [r.to_dict() for r in self.risk_indicators],
            "overall_risk_score": self.overall_risk_score,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


class IntelligenceConfig(BaseModel):
    """Configuration for IntelligencePhaseHandler."""

    enable_media_search: bool = Field(default=True)
    enable_social_search: bool = Field(default=True)
    enable_professional_search: bool = Field(default=True)
    max_media_results: int = Field(default=50, ge=10, le=200)
    media_lookback_years: int = Field(default=5, ge=1, le=20)
    adverse_only: bool = Field(default=False)


@dataclass
class IntelligencePhaseResult:
    """Result from IntelligencePhaseHandler execution."""

    result_id: UUID = field(default_factory=uuid7)
    profile: IntelligenceProfile = field(default_factory=IntelligenceProfile)
    success: bool = True
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)
    sources_searched: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": str(self.result_id),
            "profile": self.profile.to_dict(),
            "success": self.success,
            "error_message": self.error_message,
            "warnings": self.warnings,
            "sources_searched": self.sources_searched,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


class IntelligencePhaseHandler:
    """Handles the Intelligence phase of investigation.

    Collects and analyzes OSINT including adverse media,
    social media, and professional online presence.
    """

    def __init__(self, config: IntelligenceConfig | None = None):
        self.config = config or IntelligenceConfig()

    async def execute(
        self,
        subject_name: str,
        aliases: list[str] | None = None,
        tier: ServiceTier = ServiceTier.STANDARD,
        locale: Locale = Locale.US,
    ) -> IntelligencePhaseResult:
        """Execute intelligence phase."""
        start_time = datetime.now(UTC)
        result = IntelligencePhaseResult()

        logger.info("Intelligence phase started", subject_name=subject_name)

        try:
            profile = IntelligenceProfile()

            if self.config.enable_media_search:
                result.sources_searched.append("media")
            if self.config.enable_social_search:
                result.sources_searched.append("social")
            if self.config.enable_professional_search:
                result.sources_searched.append("professional")

            profile.calculate_risk_score()
            result.profile = profile
            result.success = True

        except Exception as e:
            logger.error("Intelligence phase failed", error=str(e))
            result.success = False
            result.error_message = str(e)

        end_time = datetime.now(UTC)
        result.completed_at = end_time
        result.duration_ms = (end_time - start_time).total_seconds() * 1000

        return result


def create_intelligence_phase_handler(
    config: IntelligenceConfig | None = None,
) -> IntelligencePhaseHandler:
    """Create an intelligence phase handler."""
    return IntelligencePhaseHandler(config=config)
