"""Type definitions for OSINT aggregation.

This module defines the core types for open-source intelligence gathering
including social media profiles, news mentions, and public records.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class OSINTSource(str, Enum):
    """Sources of OSINT data."""

    # Social Media
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    REDDIT = "reddit"
    GITHUB = "github"

    # Professional Networks
    CRUNCHBASE = "crunchbase"
    ANGEL_LIST = "angel_list"
    GLASSDOOR = "glassdoor"
    INDEED = "indeed"

    # News Sources
    NEWS_WIRE = "news_wire"
    LOCAL_NEWS = "local_news"
    BUSINESS_NEWS = "business_news"
    TECH_NEWS = "tech_news"
    TRADE_PUBLICATIONS = "trade_publications"

    # Public Records
    COURT_RECORDS = "court_records"
    PROPERTY_RECORDS = "property_records"
    BUSINESS_FILINGS = "business_filings"
    BANKRUPTCY_RECORDS = "bankruptcy_records"
    UCC_FILINGS = "ucc_filings"

    # Government Sources
    SEC_FILINGS = "sec_filings"
    POLITICAL_CONTRIBUTIONS = "political_contributions"
    LOBBYING_DISCLOSURES = "lobbying_disclosures"
    GOVERNMENT_CONTRACTS = "government_contracts"

    # Academic
    GOOGLE_SCHOLAR = "google_scholar"
    RESEARCHGATE = "researchgate"
    ACADEMIA_EDU = "academia_edu"
    ORCID = "orcid"

    # Other
    PERSONAL_WEBSITE = "personal_website"
    BLOG = "blog"
    PODCAST = "podcast"
    VIDEO_PLATFORM = "video_platform"
    UNKNOWN = "unknown"


class SourceReliability(str, Enum):
    """Reliability rating of an OSINT source."""

    AUTHORITATIVE = "authoritative"  # Official government/corporate sources
    HIGHLY_RELIABLE = "highly_reliable"  # Major news outlets, verified profiles
    GENERALLY_RELIABLE = "generally_reliable"  # Established platforms
    SOMEWHAT_RELIABLE = "somewhat_reliable"  # User-generated content
    LOW_RELIABILITY = "low_reliability"  # Unverified sources
    UNKNOWN = "unknown"  # Unknown reliability


class DataFreshness(str, Enum):
    """Freshness of the data."""

    REAL_TIME = "real_time"  # Updated in real-time
    DAILY = "daily"  # Updated daily
    WEEKLY = "weekly"  # Updated weekly
    MONTHLY = "monthly"  # Updated monthly
    ARCHIVED = "archived"  # Historical data
    UNKNOWN = "unknown"  # Unknown freshness


class SentimentType(str, Enum):
    """Sentiment classification."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class EntityType(str, Enum):
    """Types of entities that can be extracted."""

    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    DATE = "date"
    MONEY = "money"
    PERCENT = "percent"
    EVENT = "event"
    PRODUCT = "product"
    TITLE = "title"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    SOCIAL_HANDLE = "social_handle"


class RelationshipType(str, Enum):
    """Types of relationships between entities."""

    WORKS_FOR = "works_for"
    WORKED_FOR = "worked_for"
    FOUNDED = "founded"
    CO_FOUNDED = "co_founded"
    INVESTED_IN = "invested_in"
    BOARD_MEMBER = "board_member"
    ADVISOR = "advisor"
    PARTNER = "partner"
    SPOUSE = "spouse"
    FAMILY = "family"
    COLLEAGUE = "colleague"
    ASSOCIATED_WITH = "associated_with"
    MENTIONED_WITH = "mentioned_with"
    LOCATED_IN = "located_in"
    EDUCATED_AT = "educated_at"
    UNKNOWN = "unknown"


class RelevanceScore(str, Enum):
    """Relevance scoring levels."""

    HIGH = "high"  # Directly relevant to subject
    MEDIUM = "medium"  # Possibly relevant
    LOW = "low"  # Tangentially relevant
    NONE = "none"  # Not relevant


class SocialMediaProfile(BaseModel):
    """A social media profile.

    Attributes:
        profile_id: Unique identifier for this profile.
        source: Source platform.
        username: Username or handle.
        display_name: Display name.
        profile_url: URL to the profile.
        bio: Profile bio/description.
        follower_count: Number of followers.
        following_count: Number followed.
        post_count: Number of posts.
        verified: Whether the profile is verified.
        created_at: Profile creation date.
        last_active: Last activity date.
        location: Listed location.
        profile_image_url: URL to profile image.
        is_likely_match: Whether this likely matches the subject.
        match_confidence: Confidence score for the match.
        raw_data: Raw profile data.
    """

    profile_id: UUID
    source: OSINTSource
    username: str | None = None
    display_name: str | None = None
    profile_url: str | None = None
    bio: str | None = None
    follower_count: int | None = None
    following_count: int | None = None
    post_count: int | None = None
    verified: bool = False
    created_at: datetime | None = None
    last_active: datetime | None = None
    location: str | None = None
    profile_image_url: str | None = None
    is_likely_match: bool = False
    match_confidence: float = 0.0
    raw_data: dict[str, Any] = Field(default_factory=dict)


class NewsMention(BaseModel):
    """A news article or media mention.

    Attributes:
        mention_id: Unique identifier for this mention.
        source: Source of the news.
        headline: Article headline.
        snippet: Text snippet with the mention.
        full_text: Full article text if available.
        url: URL to the article.
        published_at: Publication date.
        author: Author name.
        publication: Publication name.
        sentiment: Sentiment of the mention.
        relevance: Relevance to the subject.
        entities_mentioned: Entities mentioned in context.
        is_subject_primary: Whether subject is primary focus.
        source_reliability: Reliability of the source.
        raw_data: Raw article data.
    """

    mention_id: UUID
    source: OSINTSource = OSINTSource.NEWS_WIRE
    headline: str | None = None
    snippet: str | None = None
    full_text: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    publication: str | None = None
    sentiment: SentimentType = SentimentType.NEUTRAL
    relevance: RelevanceScore = RelevanceScore.MEDIUM
    entities_mentioned: list[str] = Field(default_factory=list)
    is_subject_primary: bool = False
    source_reliability: SourceReliability = SourceReliability.GENERALLY_RELIABLE
    raw_data: dict[str, Any] = Field(default_factory=dict)


class PublicRecord(BaseModel):
    """A public record.

    Attributes:
        record_id: Unique identifier for this record.
        source: Source of the record.
        record_type: Type of public record.
        title: Record title or description.
        filing_date: Date of filing.
        jurisdiction: Jurisdiction (state, federal, etc.).
        case_number: Case or filing number.
        parties: Parties involved.
        status: Current status.
        summary: Brief summary.
        amount: Dollar amount if applicable.
        url: URL to the record.
        source_reliability: Reliability of the source.
        raw_data: Raw record data.
    """

    record_id: UUID
    source: OSINTSource = OSINTSource.COURT_RECORDS
    record_type: str | None = None
    title: str | None = None
    filing_date: datetime | None = None
    jurisdiction: str | None = None
    case_number: str | None = None
    parties: list[str] = Field(default_factory=list)
    status: str | None = None
    summary: str | None = None
    amount: float | None = None
    url: str | None = None
    source_reliability: SourceReliability = SourceReliability.AUTHORITATIVE
    raw_data: dict[str, Any] = Field(default_factory=dict)


class ProfessionalInfo(BaseModel):
    """Professional information about the subject.

    Attributes:
        info_id: Unique identifier.
        source: Source of the information.
        current_title: Current job title.
        current_company: Current employer.
        company_url: Company website.
        company_industry: Company industry.
        company_size: Company size range.
        employment_history: Past positions.
        education: Education history.
        skills: Listed skills.
        certifications: Professional certifications.
        patents: Patents held.
        publications: Publications authored.
        speaking_engagements: Speaking engagements.
        board_positions: Board positions.
        advisory_roles: Advisory roles.
        raw_data: Raw data.
    """

    info_id: UUID
    source: OSINTSource = OSINTSource.LINKEDIN
    current_title: str | None = None
    current_company: str | None = None
    company_url: str | None = None
    company_industry: str | None = None
    company_size: str | None = None
    employment_history: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    patents: list[dict[str, Any]] = Field(default_factory=list)
    publications: list[dict[str, Any]] = Field(default_factory=list)
    speaking_engagements: list[dict[str, Any]] = Field(default_factory=list)
    board_positions: list[str] = Field(default_factory=list)
    advisory_roles: list[str] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)


class ExtractedEntity(BaseModel):
    """An entity extracted from OSINT data.

    Attributes:
        entity_id: Unique identifier.
        entity_type: Type of entity.
        name: Entity name or value.
        normalized_name: Normalized form of the name.
        source_count: Number of sources mentioning this entity.
        sources: Sources that mention this entity.
        first_seen: First occurrence date.
        last_seen: Last occurrence date.
        confidence: Confidence in the extraction.
        context_snippets: Context where entity was found.
    """

    entity_id: UUID
    entity_type: EntityType
    name: str
    normalized_name: str | None = None
    source_count: int = 1
    sources: list[OSINTSource] = Field(default_factory=list)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    confidence: float = 0.8
    context_snippets: list[str] = Field(default_factory=list)


class ExtractedRelationship(BaseModel):
    """A relationship extracted from OSINT data.

    Attributes:
        relationship_id: Unique identifier.
        relationship_type: Type of relationship.
        source_entity: Source entity name.
        source_entity_type: Type of source entity.
        target_entity: Target entity name.
        target_entity_type: Type of target entity.
        source_count: Number of sources with this relationship.
        sources: Sources that mention this relationship.
        start_date: When relationship started.
        end_date: When relationship ended (if applicable).
        is_current: Whether relationship is current.
        confidence: Confidence in the extraction.
        context_snippets: Context where relationship was found.
    """

    relationship_id: UUID
    relationship_type: RelationshipType
    source_entity: str
    source_entity_type: EntityType
    target_entity: str
    target_entity_type: EntityType
    source_count: int = 1
    sources: list[OSINTSource] = Field(default_factory=list)
    start_date: datetime | None = None
    end_date: datetime | None = None
    is_current: bool = True
    confidence: float = 0.7
    context_snippets: list[str] = Field(default_factory=list)


class DuplicateGroup(BaseModel):
    """A group of duplicate/similar items.

    Attributes:
        group_id: Unique identifier for this group.
        item_type: Type of items in the group.
        canonical_item_id: ID of the canonical (best) item.
        duplicate_item_ids: IDs of duplicate items.
        similarity_scores: Similarity scores for each duplicate.
        merged_data: Merged data from all duplicates.
    """

    group_id: UUID
    item_type: str
    canonical_item_id: UUID
    duplicate_item_ids: list[UUID] = Field(default_factory=list)
    similarity_scores: dict[str, float] = Field(default_factory=dict)
    merged_data: dict[str, Any] = Field(default_factory=dict)


class OSINTSearchResult(BaseModel):
    """Result of an OSINT search.

    Attributes:
        search_id: Unique identifier for the search.
        subject_name: Name of the subject searched.
        search_identifiers: Identifiers used in search.
        social_profiles: Social media profiles found.
        news_mentions: News mentions found.
        public_records: Public records found.
        professional_info: Professional information.
        extracted_entities: Entities extracted from data.
        extracted_relationships: Relationships extracted.
        duplicate_groups: Detected duplicate groups.
        total_sources_searched: Total sources queried.
        sources_with_results: Sources that returned results.
        total_items_found: Total items found before dedup.
        unique_items_after_dedup: Items after deduplication.
        dedup_removed_count: Number of duplicates removed.
        searched_at: When search was performed.
        search_duration_ms: How long the search took.
        errors: Any errors during search.
    """

    search_id: UUID
    subject_name: str
    search_identifiers: list[str] = Field(default_factory=list)
    social_profiles: list[SocialMediaProfile] = Field(default_factory=list)
    news_mentions: list[NewsMention] = Field(default_factory=list)
    public_records: list[PublicRecord] = Field(default_factory=list)
    professional_info: list[ProfessionalInfo] = Field(default_factory=list)
    extracted_entities: list[ExtractedEntity] = Field(default_factory=list)
    extracted_relationships: list[ExtractedRelationship] = Field(default_factory=list)
    duplicate_groups: list[DuplicateGroup] = Field(default_factory=list)
    total_sources_searched: int = 0
    sources_with_results: int = 0
    total_items_found: int = 0
    unique_items_after_dedup: int = 0
    dedup_removed_count: int = 0
    searched_at: datetime = Field(default_factory=datetime.utcnow)
    search_duration_ms: int = 0
    errors: list[str] = Field(default_factory=list)

    def has_results(self) -> bool:
        """Check if any results were found."""
        return (
            len(self.social_profiles) > 0
            or len(self.news_mentions) > 0
            or len(self.public_records) > 0
            or len(self.professional_info) > 0
        )

    def get_high_relevance_count(self) -> int:
        """Get count of high-relevance items."""
        high_relevance = 0
        high_relevance += sum(1 for p in self.social_profiles if p.match_confidence >= 0.8)
        high_relevance += sum(1 for n in self.news_mentions if n.relevance == RelevanceScore.HIGH)
        return high_relevance

    def get_source_breakdown(self) -> dict[str, int]:
        """Get breakdown of results by source."""
        breakdown: dict[str, int] = {}
        for profile in self.social_profiles:
            source = profile.source.value
            breakdown[source] = breakdown.get(source, 0) + 1
        for mention in self.news_mentions:
            source = mention.source.value
            breakdown[source] = breakdown.get(source, 0) + 1
        for record in self.public_records:
            source = record.source.value
            breakdown[source] = breakdown.get(source, 0) + 1
        for info in self.professional_info:
            source = info.source.value
            breakdown[source] = breakdown.get(source, 0) + 1
        return breakdown


class OSINTProviderConfig(BaseModel):
    """Configuration for OSINT aggregator.

    Attributes:
        api_key: API key for external services.
        enable_social_media: Enable social media searches.
        enable_news_search: Enable news searches.
        enable_public_records: Enable public records searches.
        enable_professional: Enable professional network searches.
        enable_entity_extraction: Enable entity extraction.
        enable_relationship_extraction: Enable relationship extraction.
        enable_deduplication: Enable deduplication.
        max_results_per_source: Maximum results per source.
        search_timeout_ms: Timeout for each search.
        cache_ttl_seconds: Cache TTL for results.
        dedup_similarity_threshold: Similarity threshold for dedup.
        min_match_confidence: Minimum confidence for matches.
        news_lookback_days: How far back to search news.
        sources_to_include: Specific sources to include.
        sources_to_exclude: Specific sources to exclude.
    """

    api_key: str | None = None
    enable_social_media: bool = True
    enable_news_search: bool = True
    enable_public_records: bool = True
    enable_professional: bool = True
    enable_entity_extraction: bool = True
    enable_relationship_extraction: bool = True
    enable_deduplication: bool = True
    max_results_per_source: int = 100
    search_timeout_ms: int = 30000
    cache_ttl_seconds: int = 3600
    dedup_similarity_threshold: float = 0.85
    min_match_confidence: float = 0.6
    news_lookback_days: int = 365
    sources_to_include: list[OSINTSource] | None = None
    sources_to_exclude: list[OSINTSource] | None = None


# Exceptions


class OSINTProviderError(Exception):
    """Base exception for OSINT provider errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize the exception.

        Args:
            message: Error message.
            details: Additional error details.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class OSINTSearchError(OSINTProviderError):
    """Error during OSINT search."""

    def __init__(
        self,
        search_id: UUID,
        reason: str,
        failed_sources: list[str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            search_id: ID of the search that failed.
            reason: Reason for failure.
            failed_sources: Sources that failed.
        """
        message = f"OSINT search {search_id} failed: {reason}"
        super().__init__(message, {"failed_sources": failed_sources or []})
        self.search_id = search_id
        self.reason = reason
        self.failed_sources = failed_sources or []


class OSINTRateLimitError(OSINTProviderError):
    """Rate limit exceeded for OSINT source."""

    def __init__(
        self,
        source: OSINTSource,
        retry_after_seconds: int = 60,
    ) -> None:
        """Initialize the exception.

        Args:
            source: Source that rate limited.
            retry_after_seconds: Seconds to wait.
        """
        message = f"Rate limited by {source.value}, retry after {retry_after_seconds}s"
        super().__init__(message, {"retry_after_seconds": retry_after_seconds})
        self.source = source
        self.retry_after_seconds = retry_after_seconds


class OSINTSourceUnavailableError(OSINTProviderError):
    """OSINT source is unavailable."""

    def __init__(self, source: OSINTSource, reason: str) -> None:
        """Initialize the exception.

        Args:
            source: Source that is unavailable.
            reason: Reason for unavailability.
        """
        message = f"OSINT source {source.value} unavailable: {reason}"
        super().__init__(message)
        self.source = source
        self.reason = reason
