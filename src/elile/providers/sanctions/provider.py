"""Sanctions and watchlist provider implementation.

This module provides the SanctionsProvider class for screening subjects
against multiple sanctions and watchlist databases including OFAC, UN, EU,
and Interpol.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid7

from elile.agent.state import SearchDegree, ServiceTier
from elile.compliance.types import CheckType, Locale
from elile.core.logging import get_logger
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

from .matcher import NameMatcher, create_name_matcher
from .types import (
    EntityType,
    FuzzyMatchConfig,
    MatchType,
    SanctionedEntity,
    SanctionsAlias,
    SanctionsList,
    SanctionsMatch,
    SanctionsScreeningResult,
)

logger = get_logger(__name__)


class SanctionsProviderConfig:
    """Configuration for the sanctions provider.

    Attributes:
        enabled_lists: Which sanctions lists to screen against.
        match_config: Fuzzy matching configuration.
        cache_ttl_seconds: How long to cache results (default 3600).
        timeout_ms: Request timeout in milliseconds.
        batch_size: Maximum subjects per batch request.
    """

    def __init__(
        self,
        enabled_lists: list[SanctionsList] | None = None,
        match_config: FuzzyMatchConfig | None = None,
        cache_ttl_seconds: int = 3600,
        timeout_ms: int = 30000,
        batch_size: int = 100,
    ) -> None:
        """Initialize the configuration.

        Args:
            enabled_lists: Lists to enable. Defaults to common lists.
            match_config: Matching configuration.
            cache_ttl_seconds: Cache TTL.
            timeout_ms: Timeout.
            batch_size: Batch size.
        """
        self.enabled_lists = enabled_lists or [
            SanctionsList.OFAC_SDN,
            SanctionsList.OFAC_CONSOLIDATED,
            SanctionsList.UN_CONSOLIDATED,
            SanctionsList.EU_CONSOLIDATED,
            SanctionsList.WORLD_PEP,
        ]
        self.match_config = match_config or FuzzyMatchConfig()
        self.cache_ttl_seconds = cache_ttl_seconds
        self.timeout_ms = timeout_ms
        self.batch_size = batch_size


class SanctionsProvider(BaseDataProvider):
    """Sanctions and watchlist screening provider.

    Screens subjects against multiple sanctions databases including:
    - OFAC SDN (US Treasury)
    - UN Security Council Consolidated List
    - EU Consolidated Financial Sanctions List
    - Interpol Notices
    - PEP Databases

    Usage:
        provider = SanctionsProvider()

        # Execute sanctions check
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(full_name="John Smith"),
            locale=Locale.US,
        )

        if result.success:
            screening = result.normalized_data["screening"]
            if screening["has_hit"]:
                print(f"Found {screening['total_matches']} matches")
    """

    def __init__(self, config: SanctionsProviderConfig | None = None) -> None:
        """Initialize the sanctions provider.

        Args:
            config: Optional provider configuration.
        """
        self._config = config or SanctionsProviderConfig()
        self._matcher = create_name_matcher(self._config.match_config)

        # In-memory sanctions database (simulated)
        # In production, this would be populated from actual OFAC/UN/EU feeds
        self._sanctions_db: dict[SanctionsList, list[SanctionedEntity]] = {}
        self._last_update: datetime | None = None

        # Initialize with sample data for testing
        self._load_sample_data()

        # Provider info
        provider_info = ProviderInfo(
            provider_id="sanctions_provider",
            name="Sanctions & Watchlist Provider",
            description="Multi-list sanctions and watchlist screening (OFAC, UN, EU, PEP)",
            category=DataSourceCategory.CORE,
            capabilities=[
                ProviderCapability(
                    check_type=CheckType.SANCTIONS_OFAC,
                    supported_locales=list(Locale),
                    cost_tier=CostTier.LOW,
                    average_latency_ms=500,
                    reliability_score=0.999,
                ),
                ProviderCapability(
                    check_type=CheckType.SANCTIONS_UN,
                    supported_locales=list(Locale),
                    cost_tier=CostTier.LOW,
                    average_latency_ms=500,
                    reliability_score=0.999,
                ),
                ProviderCapability(
                    check_type=CheckType.SANCTIONS_EU,
                    supported_locales=list(Locale),
                    cost_tier=CostTier.LOW,
                    average_latency_ms=500,
                    reliability_score=0.999,
                ),
                ProviderCapability(
                    check_type=CheckType.SANCTIONS_PEP,
                    supported_locales=list(Locale),
                    cost_tier=CostTier.MEDIUM,
                    average_latency_ms=1000,
                    reliability_score=0.995,
                ),
                ProviderCapability(
                    check_type=CheckType.WATCHLIST_INTERPOL,
                    supported_locales=list(Locale),
                    cost_tier=CostTier.LOW,
                    average_latency_ms=500,
                    reliability_score=0.999,
                ),
            ],
            base_url="https://api.sanctions-provider.example.com",
            rate_limit_per_minute=1000,
            rate_limit_per_day=100000,
            requires_api_key=True,
            supports_batch=True,
        )

        super().__init__(provider_info)

        logger.info(
            "sanctions_provider_initialized",
            enabled_lists=[lst.value for lst in self._config.enabled_lists],
        )

    @property
    def config(self) -> SanctionsProviderConfig:
        """Get the provider configuration."""
        return self._config

    @property
    def matcher(self) -> NameMatcher:
        """Get the name matcher."""
        return self._matcher

    async def execute_check(
        self,
        check_type: CheckType,
        subject: SubjectIdentifiers,
        locale: Locale,
        *,
        degree: SearchDegree = SearchDegree.D1,  # noqa: ARG002
        service_tier: ServiceTier = ServiceTier.STANDARD,  # noqa: ARG002
        timeout_ms: int = 30000,  # noqa: ARG002
    ) -> ProviderResult:
        """Execute a sanctions screening check.

        Args:
            check_type: Type of sanctions check (SANCTIONS_OFAC, SANCTIONS_UN, etc.).
            subject: Subject identifiers to screen.
            locale: Locale for compliance context.
            degree: Search degree (reserved for future use).
            service_tier: Service tier (reserved for future use).
            timeout_ms: Request timeout (reserved for future use).

        Returns:
            ProviderResult with screening results.
        """
        start_time = datetime.now(UTC)
        query_id = uuid7()

        try:
            # Determine which lists to screen based on check type
            lists_to_screen = self._get_lists_for_check_type(check_type)

            # Build search name
            search_name = self._build_search_name(subject)
            if not search_name:
                return ProviderResult(
                    provider_id=self.provider_id,
                    check_type=check_type,
                    locale=locale,
                    success=False,
                    error_code="INVALID_SUBJECT",
                    error_message="No name provided for sanctions screening",
                    query_id=query_id,
                )

            # Execute screening
            screening_result = await self._screen_subject(
                subject_name=search_name,
                subject_dob=subject.date_of_birth,
                subject_country=subject.country,
                lists_to_screen=lists_to_screen,
                query_id=query_id,
            )

            # Calculate latency
            latency_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            screening_result.screening_time_ms = latency_ms

            # Build normalized data
            normalized_data = self._normalize_screening_result(screening_result)

            logger.info(
                "sanctions_check_complete",
                query_id=str(query_id),
                check_type=check_type.value,
                subject_name=search_name,
                lists_screened=[lst.value for lst in lists_to_screen],
                total_matches=screening_result.total_matches,
                has_hit=screening_result.has_hit,
                latency_ms=latency_ms,
                locale=locale.value,
            )

            return ProviderResult(
                provider_id=self.provider_id,
                check_type=check_type,
                locale=locale,
                success=True,
                normalized_data=normalized_data,
                query_id=query_id,
                latency_ms=latency_ms,
                cost_incurred=self._calculate_cost(lists_to_screen),
            )

        except Exception as e:
            latency_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            logger.error(
                "sanctions_check_failed",
                query_id=str(query_id),
                check_type=check_type.value,
                error=str(e),
            )
            return ProviderResult(
                provider_id=self.provider_id,
                check_type=check_type,
                locale=locale,
                success=False,
                error_code="SCREENING_ERROR",
                error_message=str(e),
                retryable=True,
                query_id=query_id,
                latency_ms=latency_ms,
            )

    async def health_check(self) -> ProviderHealth:
        """Check provider health.

        Returns:
            ProviderHealth with current status.
        """
        # In production, would check actual API connectivity
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.HEALTHY,
            last_check=datetime.now(UTC),
            latency_ms=50,
            success_rate_24h=0.999,
        )

    async def screen_all_lists(
        self,
        subject: SubjectIdentifiers,
        *,
        locale: str = "US",  # noqa: ARG002
    ) -> SanctionsScreeningResult:
        """Screen a subject against all enabled lists.

        Convenience method for comprehensive screening.

        Args:
            subject: Subject to screen.
            locale: Locale for audit logging (reserved for future use).

        Returns:
            SanctionsScreeningResult with all matches.
        """
        search_name = self._build_search_name(subject)
        if not search_name:
            return SanctionsScreeningResult(
                screening_id=uuid7(),
                subject_name="",
            )

        return await self._screen_subject(
            subject_name=search_name,
            subject_dob=subject.date_of_birth,
            subject_country=subject.country,
            lists_to_screen=self._config.enabled_lists,
            query_id=uuid7(),
        )

    async def get_list_statistics(self) -> dict[str, Any]:
        """Get statistics about loaded sanctions lists.

        Returns:
            Dictionary with list counts and last update time.
        """
        return {
            "lists": {
                list_source.value: len(entities)
                for list_source, entities in self._sanctions_db.items()
            },
            "total_entities": sum(len(e) for e in self._sanctions_db.values()),
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }

    async def _screen_subject(
        self,
        subject_name: str,
        subject_dob: Any | None,
        subject_country: str | None,
        lists_to_screen: list[SanctionsList],
        query_id: UUID,
    ) -> SanctionsScreeningResult:
        """Screen a subject against specified lists.

        Args:
            subject_name: Name to screen.
            subject_dob: Optional date of birth.
            subject_country: Optional country.
            lists_to_screen: Lists to search.
            query_id: Query identifier.

        Returns:
            SanctionsScreeningResult with matches.
        """
        matches: list[SanctionsMatch] = []
        highest_score = 0.0

        for list_source in lists_to_screen:
            entities = self._sanctions_db.get(list_source, [])

            for entity in entities:
                score, reasons = self._matcher.match_entity(
                    query_name=subject_name,
                    entity=entity,
                    query_dob=subject_dob,
                    query_country=subject_country,
                )

                match_type = self._matcher.get_match_type(score)

                if match_type != MatchType.NO_MATCH:
                    matches.append(
                        SanctionsMatch(
                            match_id=uuid7(),
                            entity=entity,
                            match_type=match_type,
                            match_score=score,
                            matched_fields=["name"] + (["dob"] if subject_dob else []),
                            match_reasons=reasons,
                            screening_id=query_id,
                        )
                    )
                    highest_score = max(highest_score, score)

        # Sort matches by score (highest first)
        matches.sort(key=lambda m: m.match_score, reverse=True)

        return SanctionsScreeningResult(
            screening_id=query_id,
            subject_name=subject_name,
            subject_dob=subject_dob,
            subject_country=subject_country,
            lists_screened=lists_to_screen,
            matches=matches,
            total_matches=len(matches),
            highest_match_score=highest_score,
            has_hit=len(matches) > 0,
            screened_at=datetime.now(UTC),
        )

    def _get_lists_for_check_type(self, check_type: CheckType) -> list[SanctionsList]:
        """Map check type to relevant sanctions lists."""
        mapping = {
            CheckType.SANCTIONS_OFAC: [
                SanctionsList.OFAC_SDN,
                SanctionsList.OFAC_CONSOLIDATED,
            ],
            CheckType.SANCTIONS_UN: [SanctionsList.UN_CONSOLIDATED],
            CheckType.SANCTIONS_EU: [SanctionsList.EU_CONSOLIDATED],
            CheckType.SANCTIONS_PEP: [
                SanctionsList.WORLD_PEP,
                SanctionsList.WORLD_RCA,
            ],
            CheckType.WATCHLIST_INTERPOL: [
                SanctionsList.INTERPOL_RED,
                SanctionsList.INTERPOL_YELLOW,
            ],
            CheckType.WATCHLIST_FBI: [SanctionsList.FBI_MOST_WANTED],
        }

        # Get lists for the check type, filtering to enabled lists
        check_lists = mapping.get(check_type, [])
        return [lst for lst in check_lists if lst in self._config.enabled_lists]

    def _build_search_name(self, subject: SubjectIdentifiers) -> str:
        """Build search name from subject identifiers."""
        if subject.full_name:
            return subject.full_name

        parts = []
        if subject.first_name:
            parts.append(subject.first_name)
        if subject.middle_name:
            parts.append(subject.middle_name)
        if subject.last_name:
            parts.append(subject.last_name)

        return " ".join(parts)

    def _normalize_screening_result(
        self, result: SanctionsScreeningResult
    ) -> dict[str, Any]:
        """Normalize screening result to standard format."""
        return {
            "screening": {
                "screening_id": str(result.screening_id),
                "subject_name": result.subject_name,
                "subject_dob": result.subject_dob.isoformat() if result.subject_dob else None,
                "subject_country": result.subject_country,
                "lists_screened": [lst.value for lst in result.lists_screened],
                "total_matches": result.total_matches,
                "highest_match_score": result.highest_match_score,
                "has_hit": result.has_hit,
                "screened_at": result.screened_at.isoformat(),
                "screening_time_ms": result.screening_time_ms,
            },
            "matches": [
                {
                    "match_id": str(m.match_id),
                    "entity_id": m.entity.entity_id,
                    "entity_name": m.entity.name,
                    "entity_type": m.entity.entity_type.value,
                    "list_source": m.entity.list_source.value,
                    "match_type": m.match_type.value,
                    "match_score": m.match_score,
                    "matched_fields": m.matched_fields,
                    "match_reasons": m.match_reasons,
                    "programs": m.entity.programs,
                    "nationality": m.entity.nationality,
                    "listed_date": m.entity.listed_date.isoformat() if m.entity.listed_date else None,
                }
                for m in result.matches
            ],
        }

    def _calculate_cost(self, lists_screened: list[SanctionsList]) -> Decimal:
        """Calculate cost based on lists screened."""
        # Base cost per list
        cost_per_list = Decimal("0.01")  # $0.01 per list
        return cost_per_list * len(lists_screened)

    def _load_sample_data(self) -> None:
        """Load sample sanctions data for testing.

        In production, this would load from OFAC/UN/EU APIs or data feeds.
        """
        from datetime import date

        # Sample OFAC SDN entries
        self._sanctions_db[SanctionsList.OFAC_SDN] = [
            SanctionedEntity(
                entity_id="OFAC-12345",
                list_source=SanctionsList.OFAC_SDN,
                entity_type=EntityType.INDIVIDUAL,
                name="Kim Jong Un",
                aliases=[
                    SanctionsAlias(alias_name="Kim Jong-un"),
                    SanctionsAlias(alias_name="Kim Jongun"),
                ],
                date_of_birth=date(1984, 1, 8),
                nationality=["North Korea", "KP"],
                programs=["NORTH_KOREA", "NONPROLIFERATION"],
                listed_date=date(2011, 1, 1),
                last_updated=datetime.now(UTC),
            ),
            SanctionedEntity(
                entity_id="OFAC-23456",
                list_source=SanctionsList.OFAC_SDN,
                entity_type=EntityType.INDIVIDUAL,
                name="Vladimir Vladimirovich Putin",
                aliases=[
                    SanctionsAlias(alias_name="Vladimir Putin"),
                    SanctionsAlias(alias_name="Putin Vladimir"),
                ],
                date_of_birth=date(1952, 10, 7),
                nationality=["Russia", "RU"],
                programs=["RUSSIA", "UKRAINE"],
                listed_date=date(2022, 2, 25),
                last_updated=datetime.now(UTC),
            ),
            SanctionedEntity(
                entity_id="OFAC-34567",
                list_source=SanctionsList.OFAC_SDN,
                entity_type=EntityType.ORGANIZATION,
                name="Central Bank of Iran",
                aliases=[
                    SanctionsAlias(alias_name="Bank Markazi Jomhouri Islami Iran"),
                ],
                nationality=["Iran", "IR"],
                programs=["IRAN", "IFSR"],
                listed_date=date(2012, 2, 6),
                last_updated=datetime.now(UTC),
            ),
        ]

        # Sample UN entries
        self._sanctions_db[SanctionsList.UN_CONSOLIDATED] = [
            SanctionedEntity(
                entity_id="UN-67890",
                list_source=SanctionsList.UN_CONSOLIDATED,
                entity_type=EntityType.INDIVIDUAL,
                name="Osama bin Laden",
                aliases=[
                    SanctionsAlias(alias_name="Usama bin Muhammad bin Awad bin Ladin"),
                ],
                date_of_birth=date(1957, 3, 10),
                nationality=["Saudi Arabia"],
                programs=["AL-QAIDA"],
                listed_date=date(2001, 10, 8),
                last_updated=datetime.now(UTC),
            ),
        ]

        # Sample EU entries
        self._sanctions_db[SanctionsList.EU_CONSOLIDATED] = [
            SanctionedEntity(
                entity_id="EU-11111",
                list_source=SanctionsList.EU_CONSOLIDATED,
                entity_type=EntityType.INDIVIDUAL,
                name="Alexander Lukashenko",
                aliases=[
                    SanctionsAlias(alias_name="Aliaksandr Ryhoravich Lukashenka"),
                ],
                date_of_birth=date(1954, 8, 30),
                nationality=["Belarus", "BY"],
                programs=["BELARUS"],
                listed_date=date(2020, 10, 2),
                last_updated=datetime.now(UTC),
            ),
        ]

        # Sample PEP entries
        self._sanctions_db[SanctionsList.WORLD_PEP] = [
            SanctionedEntity(
                entity_id="PEP-22222",
                list_source=SanctionsList.WORLD_PEP,
                entity_type=EntityType.INDIVIDUAL,
                name="Hunter Biden",
                nationality=["United States", "US"],
                programs=["PEP_FAMILY"],
                remarks="Son of US President Joseph Biden",
                last_updated=datetime.now(UTC),
            ),
        ]

        self._last_update = datetime.now(UTC)

        logger.info(
            "sample_sanctions_data_loaded",
            total_entities=sum(len(e) for e in self._sanctions_db.values()),
        )


# =============================================================================
# Factory function
# =============================================================================

_provider_instance: SanctionsProvider | None = None


def get_sanctions_provider(
    config: SanctionsProviderConfig | None = None,
) -> SanctionsProvider:
    """Get the singleton sanctions provider instance.

    Args:
        config: Optional configuration for first initialization.

    Returns:
        The SanctionsProvider singleton.
    """
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = SanctionsProvider(config)
    return _provider_instance


def create_sanctions_provider(
    config: SanctionsProviderConfig | None = None,
) -> SanctionsProvider:
    """Create a new sanctions provider instance.

    Use this for testing or when you need a fresh provider.

    Args:
        config: Optional configuration.

    Returns:
        A new SanctionsProvider instance.
    """
    return SanctionsProvider(config)
