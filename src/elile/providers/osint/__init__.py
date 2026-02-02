"""OSINT Aggregator Provider module.

This module provides open-source intelligence gathering capabilities
including social media monitoring, news search, and public records lookup.

Example:
    from elile.providers.osint import (
        OSINTProvider,
        get_osint_provider,
        OSINTProviderConfig,
    )

    # Get the singleton provider
    provider = get_osint_provider()

    # Or create with custom config
    config = OSINTProviderConfig(
        enable_news_search=True,
        enable_public_records=True,
        news_lookback_days=180,
    )
    provider = OSINTProvider(config)

    # Gather intelligence
    result = await provider.gather_intelligence(
        subject_name="John Smith",
        identifiers=["john.smith@example.com"],
    )
"""

from .deduplicator import (
    DeduplicationResult,
    OSINTDeduplicator,
    create_deduplicator,
)
from .entity_extractor import (
    EntityExtractor,
    RelationshipExtractor,
    create_entity_extractor,
    create_relationship_extractor,
)
from .provider import (
    OSINTProvider,
    create_osint_provider,
    get_osint_provider,
)
from .types import (
    DataFreshness,
    DuplicateGroup,
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    NewsMention,
    OSINTProviderConfig,
    OSINTProviderError,
    OSINTRateLimitError,
    OSINTSearchError,
    OSINTSearchResult,
    OSINTSource,
    OSINTSourceUnavailableError,
    ProfessionalInfo,
    PublicRecord,
    RelationshipType,
    RelevanceScore,
    SentimentType,
    SocialMediaProfile,
    SourceReliability,
)

__all__ = [
    # Provider
    "OSINTProvider",
    "create_osint_provider",
    "get_osint_provider",
    # Types
    "OSINTSource",
    "SourceReliability",
    "DataFreshness",
    "SentimentType",
    "EntityType",
    "RelationshipType",
    "RelevanceScore",
    "SocialMediaProfile",
    "NewsMention",
    "PublicRecord",
    "ProfessionalInfo",
    "ExtractedEntity",
    "ExtractedRelationship",
    "DuplicateGroup",
    "OSINTSearchResult",
    "OSINTProviderConfig",
    # Deduplication
    "OSINTDeduplicator",
    "DeduplicationResult",
    "create_deduplicator",
    # Entity extraction
    "EntityExtractor",
    "RelationshipExtractor",
    "create_entity_extractor",
    "create_relationship_extractor",
    # Exceptions
    "OSINTProviderError",
    "OSINTSearchError",
    "OSINTRateLimitError",
    "OSINTSourceUnavailableError",
]
