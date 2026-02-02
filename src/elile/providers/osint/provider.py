"""OSINT Aggregator Provider implementation.

This module provides the main OSINT aggregator that combines
multiple open-source intelligence sources into a unified profile.
"""

import asyncio
import hashlib
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid7

from elile.compliance.types import CheckType, Locale
from elile.entity.types import SubjectIdentifiers
from elile.providers.protocol import BaseDataProvider
from elile.providers.types import (
    CostTier,
    DataSourceCategory,
    ProviderCapability,
    ProviderHealth,
    ProviderInfo,
    ProviderResult,
    ProviderStatus,
)

from .deduplicator import create_deduplicator
from .entity_extractor import (
    create_entity_extractor,
    create_relationship_extractor,
)
from .types import (
    NewsMention,
    OSINTProviderConfig,
    OSINTSearchResult,
    OSINTSource,
    ProfessionalInfo,
    PublicRecord,
    RelevanceScore,
    SentimentType,
    SocialMediaProfile,
    SourceReliability,
)

# Singleton instance
_osint_provider: "OSINTProvider | None" = None


class OSINTProvider(BaseDataProvider):
    """OSINT Aggregator Provider.

    Aggregates open-source intelligence from multiple sources including
    social media, news, public records, and professional networks.

    Attributes:
        config: Provider configuration.
    """

    def __init__(self, config: OSINTProviderConfig | None = None) -> None:
        """Initialize the OSINT provider.

        Args:
            config: Optional configuration.
        """
        self.config = config or OSINTProviderConfig()
        self._deduplicator = create_deduplicator(self.config.dedup_similarity_threshold)
        self._entity_extractor = create_entity_extractor()
        self._relationship_extractor = create_relationship_extractor()

        # Define provider info
        provider_info = ProviderInfo(
            provider_id="osint_provider",
            name="OSINT Aggregator Provider",
            description="Aggregates open-source intelligence from multiple sources",
            version="1.0.0",
            category=DataSourceCategory.PREMIUM,
            capabilities=[
                ProviderCapability(
                    check_type=CheckType.SOCIAL_MEDIA,
                    supported_locales=[Locale.US, Locale.UK, Locale.CA, Locale.AU],
                    cost_tier=CostTier.MEDIUM,
                    avg_latency_ms=3000,
                    description="Social media profile aggregation",
                ),
                ProviderCapability(
                    check_type=CheckType.ADVERSE_MEDIA,
                    supported_locales=[Locale.US, Locale.UK, Locale.CA, Locale.AU],
                    cost_tier=CostTier.MEDIUM,
                    avg_latency_ms=5000,
                    description="News and media monitoring",
                ),
                ProviderCapability(
                    check_type=CheckType.DIGITAL_FOOTPRINT,
                    supported_locales=[Locale.US],
                    cost_tier=CostTier.HIGH,
                    avg_latency_ms=8000,
                    description="Digital footprint and public records search",
                ),
            ],
        )
        super().__init__(provider_info)

    @property
    def supported_checks(self) -> set[CheckType]:
        """Get supported check types."""
        return {
            CheckType.SOCIAL_MEDIA,
            CheckType.ADVERSE_MEDIA,
            CheckType.DIGITAL_FOOTPRINT,
        }

    async def execute_check(
        self,
        check_type: CheckType,
        subject: SubjectIdentifiers,
        locale: Locale,
        *,
        options: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ProviderResult:
        """Execute an OSINT check.

        Args:
            check_type: Type of check to perform.
            subject: Subject identifiers.
            locale: Target locale.
            options: Additional options (reserved for future use).

        Returns:
            Provider result with OSINT data.
        """
        start_time = datetime.utcnow()
        query_id = uuid7()

        # Validate subject
        if not subject.full_name:
            return ProviderResult(
                provider_id=self.provider_id,
                query_id=query_id,
                check_type=check_type,
                locale=locale,
                success=False,
                error_code="INVALID_SUBJECT",
                error_message="Subject full_name is required for OSINT search",
                latency_ms=0,
            )

        # Build search identifiers
        identifiers = self._build_identifiers(subject)

        # Perform the search
        search_result = await self.gather_intelligence(
            subject_name=subject.full_name,
            identifiers=identifiers,
            check_type=check_type,
        )

        # Calculate latency
        latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Calculate cost
        cost = self._calculate_cost(search_result, check_type)

        # Normalize the result
        normalized_data = self._normalize_search_result(search_result)

        return ProviderResult(
            provider_id=self.provider_id,
            query_id=query_id,
            check_type=check_type,
            locale=locale,
            success=True,
            normalized_data=normalized_data,
            raw_data=search_result.model_dump(),
            latency_ms=latency_ms,
            cost_incurred=cost,
        )

    async def health_check(self) -> ProviderHealth:
        """Check provider health.

        Returns:
            Health status of the provider.
        """
        start_time = datetime.utcnow()

        # Simulate health check
        await asyncio.sleep(0.01)

        latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.HEALTHY,
            latency_ms=latency_ms,
            last_check=datetime.utcnow(),
        )

    async def gather_intelligence(
        self,
        subject_name: str,
        identifiers: list[str],
        check_type: CheckType | None = None,
    ) -> OSINTSearchResult:
        """Gather OSINT from all enabled sources.

        Args:
            subject_name: Name of the subject.
            identifiers: Additional identifiers to search.
            check_type: Type of check (filters sources).

        Returns:
            Aggregated OSINT search result.
        """
        search_id = uuid7()
        start_time = datetime.utcnow()
        errors: list[str] = []

        # Initialize result collections
        social_profiles: list[SocialMediaProfile] = []
        news_mentions: list[NewsMention] = []
        public_records: list[PublicRecord] = []
        professional_info: list[ProfessionalInfo] = []

        sources_searched = 0
        sources_with_results = 0

        # Gather from enabled sources based on check type
        if self.config.enable_social_media and (
            check_type is None or check_type == CheckType.SOCIAL_MEDIA
        ):
            try:
                profiles = await self._search_social_media(subject_name, identifiers)
                social_profiles.extend(profiles)
                sources_searched += 5  # Approximate social platforms
                if profiles:
                    sources_with_results += 1
            except Exception as e:
                errors.append(f"Social media search failed: {e}")

        if self.config.enable_news_search and (
            check_type is None or check_type == CheckType.ADVERSE_MEDIA
        ):
            try:
                mentions = await self._search_news(subject_name, identifiers)
                news_mentions.extend(mentions)
                sources_searched += 3  # Approximate news sources
                if mentions:
                    sources_with_results += 1
            except Exception as e:
                errors.append(f"News search failed: {e}")

        if self.config.enable_public_records and (
            check_type is None or check_type == CheckType.DIGITAL_FOOTPRINT
        ):
            try:
                records = await self._search_public_records(subject_name, identifiers)
                public_records.extend(records)
                sources_searched += 4  # Approximate record sources
                if records:
                    sources_with_results += 1
            except Exception as e:
                errors.append(f"Public records search failed: {e}")

        if self.config.enable_professional:
            try:
                infos = await self._search_professional(subject_name, identifiers)
                professional_info.extend(infos)
                sources_searched += 2  # LinkedIn, etc.
                if infos:
                    sources_with_results += 1
            except Exception as e:
                errors.append(f"Professional search failed: {e}")

        # Count totals before dedup
        total_items = (
            len(social_profiles) + len(news_mentions) + len(public_records) + len(professional_info)
        )

        # Deduplicate if enabled
        duplicate_groups = []
        if self.config.enable_deduplication:
            # Dedupe profiles
            profile_result = self._deduplicator.deduplicate_profiles(social_profiles)
            social_profiles = profile_result.items
            duplicate_groups.extend(profile_result.duplicate_groups)

            # Dedupe news
            news_result = self._deduplicator.deduplicate_news(news_mentions)
            news_mentions = news_result.items
            duplicate_groups.extend(news_result.duplicate_groups)

            # Dedupe records
            record_result = self._deduplicator.deduplicate_records(public_records)
            public_records = record_result.items
            duplicate_groups.extend(record_result.duplicate_groups)

            # Dedupe professional
            prof_result = self._deduplicator.deduplicate_professional(professional_info)
            professional_info = prof_result.items
            duplicate_groups.extend(prof_result.duplicate_groups)

        unique_items = (
            len(social_profiles) + len(news_mentions) + len(public_records) + len(professional_info)
        )

        # Extract entities if enabled
        extracted_entities = []
        if self.config.enable_entity_extraction:
            self._entity_extractor.clear_cache()
            extracted_entities.extend(self._entity_extractor.extract_from_profiles(social_profiles))
            extracted_entities.extend(self._entity_extractor.extract_from_news(news_mentions))
            extracted_entities.extend(self._entity_extractor.extract_from_records(public_records))
            extracted_entities.extend(
                self._entity_extractor.extract_from_professional(professional_info)
            )

        # Extract relationships if enabled
        extracted_relationships = []
        if self.config.enable_relationship_extraction:
            self._relationship_extractor.clear_cache()
            extracted_relationships.extend(
                self._relationship_extractor.extract_from_professional(
                    professional_info, subject_name
                )
            )
            extracted_relationships.extend(
                self._relationship_extractor.extract_from_news(news_mentions, subject_name)
            )
            extracted_relationships.extend(
                self._relationship_extractor.extract_from_profiles(social_profiles, subject_name)
            )

        # Calculate duration
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return OSINTSearchResult(
            search_id=search_id,
            subject_name=subject_name,
            search_identifiers=identifiers,
            social_profiles=social_profiles,
            news_mentions=news_mentions,
            public_records=public_records,
            professional_info=professional_info,
            extracted_entities=extracted_entities,
            extracted_relationships=extracted_relationships,
            duplicate_groups=duplicate_groups,
            total_sources_searched=sources_searched,
            sources_with_results=sources_with_results,
            total_items_found=total_items,
            unique_items_after_dedup=unique_items,
            dedup_removed_count=total_items - unique_items,
            searched_at=start_time,
            search_duration_ms=duration_ms,
            errors=errors,
        )

    async def search_social_media(
        self,
        subject_name: str,
        identifiers: list[str] | None = None,
    ) -> list[SocialMediaProfile]:
        """Search social media sources.

        Args:
            subject_name: Name to search.
            identifiers: Additional identifiers.

        Returns:
            List of social media profiles.
        """
        return await self._search_social_media(subject_name, identifiers or [])

    async def search_news(
        self,
        subject_name: str,
        lookback_days: int | None = None,
    ) -> list[NewsMention]:
        """Search news sources.

        Args:
            subject_name: Name to search.
            lookback_days: How far back to search.

        Returns:
            List of news mentions.
        """
        return await self._search_news(
            subject_name, [], lookback_days or self.config.news_lookback_days
        )

    async def _search_social_media(
        self,
        subject_name: str,
        identifiers: list[str],  # noqa: ARG002
    ) -> list[SocialMediaProfile]:
        """Search social media platforms.

        Args:
            subject_name: Name to search.
            identifiers: Additional identifiers (reserved for future use).

        Returns:
            List of profiles found.
        """
        # Simulate API calls
        await asyncio.sleep(0.05)

        profiles: list[SocialMediaProfile] = []

        # Generate deterministic results based on name
        name_hash = hashlib.md5(subject_name.lower().encode()).hexdigest()
        random.seed(int(name_hash[:8], 16))

        # LinkedIn profile (high probability)
        if random.random() < 0.8:
            username = subject_name.lower().replace(" ", "")
            profiles.append(
                SocialMediaProfile(
                    profile_id=uuid7(),
                    source=OSINTSource.LINKEDIN,
                    username=username,
                    display_name=subject_name,
                    profile_url=f"https://linkedin.com/in/{username}",
                    bio=f"Professional profile for {subject_name}",  # noqa: F541
                    follower_count=random.randint(100, 1000),
                    following_count=random.randint(50, 500),
                    verified=random.random() < 0.2,
                    location=random.choice(
                        [
                            "San Francisco, CA",
                            "New York, NY",
                            "Austin, TX",
                            "Seattle, WA",
                            "Boston, MA",
                        ]
                    ),
                    is_likely_match=True,
                    match_confidence=0.85,
                )
            )

        # Twitter profile (medium probability)
        if random.random() < 0.5:
            handle = subject_name.lower().replace(" ", "_")[:15]
            profiles.append(
                SocialMediaProfile(
                    profile_id=uuid7(),
                    source=OSINTSource.TWITTER,
                    username=handle,
                    display_name=subject_name,
                    profile_url=f"https://twitter.com/{handle}",
                    bio=f"Thoughts from {subject_name.split()[0]}",
                    follower_count=random.randint(50, 5000),
                    following_count=random.randint(100, 2000),
                    post_count=random.randint(50, 500),
                    verified=random.random() < 0.1,
                    is_likely_match=True,
                    match_confidence=0.75,
                )
            )

        # GitHub profile (for tech workers)
        if random.random() < 0.3:
            username = subject_name.lower().replace(" ", "-")
            profiles.append(
                SocialMediaProfile(
                    profile_id=uuid7(),
                    source=OSINTSource.GITHUB,
                    username=username,
                    display_name=subject_name,
                    profile_url=f"https://github.com/{username}",
                    bio="Software developer",
                    follower_count=random.randint(10, 500),
                    following_count=random.randint(20, 200),
                    is_likely_match=True,
                    match_confidence=0.70,
                )
            )

        return profiles

    async def _search_news(
        self,
        subject_name: str,
        identifiers: list[str],  # noqa: ARG002
        lookback_days: int | None = None,
    ) -> list[NewsMention]:
        """Search news sources.

        Args:
            subject_name: Name to search.
            identifiers: Additional identifiers (reserved for future use).
            lookback_days: How far back to search.

        Returns:
            List of news mentions.
        """
        # Simulate API calls
        await asyncio.sleep(0.05)

        mentions: list[NewsMention] = []

        # Generate deterministic results
        name_hash = hashlib.md5(subject_name.lower().encode()).hexdigest()
        random.seed(int(name_hash[:8], 16) + 1)

        # Number of mentions varies by name
        num_mentions = random.randint(0, 5)

        news_sources = [
            ("TechCrunch", OSINTSource.TECH_NEWS, SourceReliability.HIGHLY_RELIABLE),
            ("Reuters", OSINTSource.NEWS_WIRE, SourceReliability.AUTHORITATIVE),
            ("Local News", OSINTSource.LOCAL_NEWS, SourceReliability.GENERALLY_RELIABLE),
            ("Business Insider", OSINTSource.BUSINESS_NEWS, SourceReliability.HIGHLY_RELIABLE),
        ]

        topics = [
            "company expansion",
            "funding round",
            "industry panel",
            "conference speaker",
            "product launch",
            "leadership change",
        ]

        for _ in range(num_mentions):
            source_info = random.choice(news_sources)
            topic = random.choice(topics)
            days_ago = random.randint(1, lookback_days or 365)

            mentions.append(
                NewsMention(
                    mention_id=uuid7(),
                    source=source_info[1],
                    headline=f"{subject_name} involved in {topic}",
                    snippet=f"...{subject_name} was mentioned in connection with {topic}...",
                    url=f"https://example.com/news/{uuid7()}",
                    published_at=datetime.utcnow() - timedelta(days=days_ago),
                    author="Staff Writer",
                    publication=source_info[0],
                    sentiment=random.choice(list(SentimentType)),
                    relevance=random.choice(
                        [
                            RelevanceScore.HIGH,
                            RelevanceScore.MEDIUM,
                            RelevanceScore.LOW,
                        ]
                    ),
                    entities_mentioned=[subject_name],
                    is_subject_primary=random.random() < 0.3,
                    source_reliability=source_info[2],
                )
            )

        return mentions

    async def _search_public_records(
        self,
        subject_name: str,
        identifiers: list[str],  # noqa: ARG002
    ) -> list[PublicRecord]:
        """Search public records.

        Args:
            subject_name: Name to search.
            identifiers: Additional identifiers (reserved for future use).

        Returns:
            List of public records.
        """
        # Simulate API calls
        await asyncio.sleep(0.05)

        records: list[PublicRecord] = []

        # Generate deterministic results
        name_hash = hashlib.md5(subject_name.lower().encode()).hexdigest()
        random.seed(int(name_hash[:8], 16) + 2)

        # Number of records varies
        num_records = random.randint(0, 3)

        record_types = [
            ("Property Record", OSINTSource.PROPERTY_RECORDS),
            ("Business Filing", OSINTSource.BUSINESS_FILINGS),
            ("UCC Filing", OSINTSource.UCC_FILINGS),
            ("Court Record", OSINTSource.COURT_RECORDS),
        ]

        jurisdictions = [
            "California",
            "Delaware",
            "New York",
            "Texas",
            "Florida",
        ]

        for _ in range(num_records):
            record_info = random.choice(record_types)
            jurisdiction = random.choice(jurisdictions)
            days_ago = random.randint(30, 1000)

            records.append(
                PublicRecord(
                    record_id=uuid7(),
                    source=record_info[1],
                    record_type=record_info[0],
                    title=f"{record_info[0]} involving {subject_name}",
                    filing_date=datetime.utcnow() - timedelta(days=days_ago),
                    jurisdiction=jurisdiction,
                    case_number=f"{jurisdiction[:2].upper()}-{random.randint(1000, 9999)}-{random.randint(100, 999)}",
                    parties=[subject_name],
                    status="Filed" if random.random() < 0.7 else "Closed",
                    summary=f"Record related to {subject_name} in {jurisdiction}",
                    source_reliability=SourceReliability.AUTHORITATIVE,
                )
            )

        return records

    async def _search_professional(
        self,
        subject_name: str,
        identifiers: list[str],  # noqa: ARG002
    ) -> list[ProfessionalInfo]:
        """Search professional networks.

        Args:
            subject_name: Name to search.
            identifiers: Additional identifiers (reserved for future use).

        Returns:
            List of professional info.
        """
        # Simulate API calls
        await asyncio.sleep(0.05)

        infos: list[ProfessionalInfo] = []

        # Generate deterministic results
        name_hash = hashlib.md5(subject_name.lower().encode()).hexdigest()
        random.seed(int(name_hash[:8], 16) + 3)

        # Usually find one professional profile
        if random.random() < 0.8:
            titles = [
                "Software Engineer",
                "Product Manager",
                "Director of Engineering",
                "VP of Operations",
                "Chief Technology Officer",
                "Senior Consultant",
                "Managing Director",
            ]

            companies = [
                ("Tech Corp", "Technology", "1000-5000"),
                ("Finance Inc", "Financial Services", "5000-10000"),
                ("Startup Co", "Technology", "50-200"),
                ("Global Corp", "Consulting", "10000+"),
                ("Innovation Labs", "Research", "200-500"),
            ]

            company = random.choice(companies)
            title = random.choice(titles)

            skills = random.sample(
                [
                    "Leadership",
                    "Strategy",
                    "Python",
                    "Data Analysis",
                    "Project Management",
                    "Business Development",
                    "Machine Learning",
                    "Cloud Computing",
                ],
                k=random.randint(3, 6),
            )

            infos.append(
                ProfessionalInfo(
                    info_id=uuid7(),
                    source=OSINTSource.LINKEDIN,
                    current_title=title,
                    current_company=company[0],
                    company_industry=company[1],
                    company_size=company[2],
                    employment_history=[
                        {
                            "company": "Previous Corp",
                            "title": "Senior " + title.split()[-1],
                            "start_date": "2018",
                            "end_date": "2022",
                        },
                        {
                            "company": "First Job Inc",
                            "title": title.split()[-1],
                            "start_date": "2015",
                            "end_date": "2018",
                        },
                    ],
                    education=[
                        {
                            "school": random.choice(
                                [
                                    "Stanford University",
                                    "MIT",
                                    "UC Berkeley",
                                    "Harvard University",
                                    "Carnegie Mellon",
                                ]
                            ),
                            "degree": random.choice(
                                [
                                    "BS Computer Science",
                                    "MBA",
                                    "MS Engineering",
                                    "BA Economics",
                                ]
                            ),
                            "year": random.randint(2008, 2015),
                        }
                    ],
                    skills=skills,
                    certifications=random.sample(
                        [
                            "PMP",
                            "AWS Certified",
                            "CFA",
                            "Six Sigma",
                        ],
                        k=random.randint(0, 2),
                    ),
                )
            )

        return infos

    def _build_identifiers(self, subject: SubjectIdentifiers) -> list[str]:
        """Build list of search identifiers from subject.

        Args:
            subject: Subject identifiers.

        Returns:
            List of identifiers to search.
        """
        identifiers = []

        if subject.full_name:
            identifiers.append(subject.full_name)

        if subject.name_variants:
            identifiers.extend(subject.name_variants)

        if subject.email:
            identifiers.append(subject.email)

        if subject.phone:
            identifiers.append(subject.phone)

        return identifiers

    def _calculate_cost(
        self,
        result: OSINTSearchResult,
        check_type: CheckType,  # noqa: ARG002
    ) -> Decimal:
        """Calculate cost for the search.

        Args:
            result: Search result.
            check_type: Type of check (reserved for future pricing tiers).

        Returns:
            Cost in dollars.
        """
        base_cost = Decimal("5.00")

        # Add per-source costs
        source_cost = Decimal(str(result.sources_with_results)) * Decimal("2.00")

        # Add per-item costs (capped)
        item_cost = min(
            Decimal(str(result.unique_items_after_dedup)) * Decimal("0.50"),
            Decimal("20.00"),
        )

        # Entity extraction cost
        entity_cost = Decimal("0.00")
        if self.config.enable_entity_extraction:
            entity_cost = min(
                Decimal(str(len(result.extracted_entities))) * Decimal("0.10"),
                Decimal("5.00"),
            )

        return base_cost + source_cost + item_cost + entity_cost

    def _normalize_search_result(
        self,
        result: OSINTSearchResult,
    ) -> dict[str, Any]:
        """Normalize search result to standard format.

        Args:
            result: Search result to normalize.

        Returns:
            Normalized data dictionary.
        """
        return {
            "search": {
                "search_id": str(result.search_id),
                "subject_name": result.subject_name,
                "identifiers_searched": result.search_identifiers,
                "sources_searched": result.total_sources_searched,
                "sources_with_results": result.sources_with_results,
                "total_items_found": result.total_items_found,
                "unique_items": result.unique_items_after_dedup,
                "duplicates_removed": result.dedup_removed_count,
                "searched_at": result.searched_at.isoformat(),
                "duration_ms": result.search_duration_ms,
            },
            "social_profiles": [
                {
                    "profile_id": str(p.profile_id),
                    "source": p.source.value,
                    "username": p.username,
                    "display_name": p.display_name,
                    "profile_url": p.profile_url,
                    "location": p.location,
                    "follower_count": p.follower_count,
                    "verified": p.verified,
                    "match_confidence": p.match_confidence,
                }
                for p in result.social_profiles
            ],
            "news_mentions": [
                {
                    "mention_id": str(n.mention_id),
                    "source": n.source.value,
                    "headline": n.headline,
                    "publication": n.publication,
                    "published_at": n.published_at.isoformat() if n.published_at else None,
                    "sentiment": n.sentiment.value,
                    "relevance": n.relevance.value,
                    "is_subject_primary": n.is_subject_primary,
                }
                for n in result.news_mentions
            ],
            "public_records": [
                {
                    "record_id": str(r.record_id),
                    "source": r.source.value,
                    "record_type": r.record_type,
                    "title": r.title,
                    "jurisdiction": r.jurisdiction,
                    "case_number": r.case_number,
                    "filing_date": r.filing_date.isoformat() if r.filing_date else None,
                    "status": r.status,
                }
                for r in result.public_records
            ],
            "professional_info": [
                {
                    "info_id": str(p.info_id),
                    "source": p.source.value,
                    "current_title": p.current_title,
                    "current_company": p.current_company,
                    "company_industry": p.company_industry,
                    "skills": p.skills,
                    "education": p.education,
                }
                for p in result.professional_info
            ],
            "entities": [
                {
                    "entity_id": str(e.entity_id),
                    "type": e.entity_type.value,
                    "name": e.name,
                    "source_count": e.source_count,
                    "confidence": e.confidence,
                }
                for e in result.extracted_entities[:20]  # Limit for response size
            ],
            "relationships": [
                {
                    "relationship_id": str(r.relationship_id),
                    "type": r.relationship_type.value,
                    "source_entity": r.source_entity,
                    "target_entity": r.target_entity,
                    "is_current": r.is_current,
                    "confidence": r.confidence,
                }
                for r in result.extracted_relationships[:20]  # Limit for response size
            ],
            "errors": result.errors,
        }


def create_osint_provider(config: OSINTProviderConfig | None = None) -> OSINTProvider:
    """Create an OSINT provider.

    Args:
        config: Optional configuration.

    Returns:
        Configured OSINT provider.
    """
    return OSINTProvider(config)


def get_osint_provider() -> OSINTProvider:
    """Get the singleton OSINT provider.

    Returns:
        Singleton provider instance.
    """
    global _osint_provider
    if _osint_provider is None:
        _osint_provider = OSINTProvider()
    return _osint_provider
