"""Type definitions for sanctions and watchlist screening.

This module defines the core types for sanctions screening including
match results, list types, and screening configurations.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SanctionsList(str, Enum):
    """Available sanctions and watchlist databases."""

    # US Lists
    OFAC_SDN = "ofac_sdn"  # OFAC Specially Designated Nationals
    OFAC_CONSOLIDATED = "ofac_consolidated"  # OFAC Consolidated Sanctions List
    FBI_MOST_WANTED = "fbi_most_wanted"  # FBI Most Wanted
    BIS_DENIED = "bis_denied"  # Bureau of Industry and Security Denied Persons
    BIS_ENTITY = "bis_entity"  # Bureau of Industry and Security Entity List

    # International Lists
    UN_CONSOLIDATED = "un_consolidated"  # UN Security Council Consolidated List
    EU_CONSOLIDATED = "eu_consolidated"  # EU Consolidated Financial Sanctions List
    INTERPOL_RED = "interpol_red"  # Interpol Red Notices
    INTERPOL_YELLOW = "interpol_yellow"  # Interpol Yellow Notices

    # PEP Lists
    WORLD_PEP = "world_pep"  # World PEP Database
    WORLD_RCA = "world_rca"  # Relatives and Close Associates

    # Adverse Media
    ADVERSE_MEDIA = "adverse_media"  # Adverse media screening


class MatchType(str, Enum):
    """Type of match found in screening."""

    EXACT = "exact"  # Exact name match
    STRONG = "strong"  # High confidence fuzzy match
    MEDIUM = "medium"  # Medium confidence fuzzy match
    WEAK = "weak"  # Low confidence fuzzy match
    POTENTIAL = "potential"  # Possible match requiring review
    NO_MATCH = "no_match"  # No match found


class EntityType(str, Enum):
    """Type of sanctioned entity."""

    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"
    VESSEL = "vessel"
    AIRCRAFT = "aircraft"
    UNKNOWN = "unknown"


class SanctionsAlias(BaseModel):
    """An alias for a sanctioned entity.

    Attributes:
        alias_name: The alias or alternate name.
        alias_type: Type of alias (aka, fka, nee, etc.).
        quality: Quality/reliability of the alias.
    """

    alias_name: str
    alias_type: str = "aka"  # aka, fka, nee, spelling variation
    quality: str = "good"  # good, low


class SanctionsAddress(BaseModel):
    """Address associated with a sanctioned entity.

    Attributes:
        street: Street address.
        city: City name.
        state_province: State or province.
        postal_code: Postal/ZIP code.
        country: Country code (ISO 3166-1 alpha-2).
        address_type: Type of address (primary, mailing, etc.).
    """

    street: str | None = None
    city: str | None = None
    state_province: str | None = None
    postal_code: str | None = None
    country: str | None = None
    address_type: str = "primary"


class SanctionsIdentifier(BaseModel):
    """Identifier for a sanctioned entity.

    Attributes:
        id_type: Type of identifier (passport, national_id, etc.).
        id_number: The identifier value.
        country: Issuing country.
        notes: Additional notes about the identifier.
    """

    id_type: str
    id_number: str
    country: str | None = None
    notes: str | None = None


class SanctionedEntity(BaseModel):
    """A sanctioned entity from a watchlist.

    Attributes:
        entity_id: Unique identifier for the entity within the list.
        list_source: Which sanctions list this entity is from.
        entity_type: Type of entity (individual, organization, etc.).
        name: Primary name of the entity.
        aliases: Alternate names and aliases.
        date_of_birth: Date of birth (for individuals).
        nationality: Nationality or citizenship.
        addresses: Known addresses.
        identifiers: Identifying documents.
        programs: Sanctions programs the entity is listed under.
        remarks: Additional information or remarks.
        listed_date: When the entity was added to the list.
        last_updated: When the entry was last updated.
    """

    entity_id: str
    list_source: SanctionsList
    entity_type: EntityType
    name: str
    aliases: list[SanctionsAlias] = Field(default_factory=list)
    date_of_birth: date | None = None
    place_of_birth: str | None = None
    nationality: list[str] = Field(default_factory=list)
    addresses: list[SanctionsAddress] = Field(default_factory=list)
    identifiers: list[SanctionsIdentifier] = Field(default_factory=list)
    programs: list[str] = Field(default_factory=list)
    remarks: str | None = None
    listed_date: date | None = None
    last_updated: datetime | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)


class SanctionsMatch(BaseModel):
    """A match result from sanctions screening.

    Attributes:
        match_id: Unique identifier for this match.
        entity: The matched sanctioned entity.
        match_type: Type/quality of the match.
        match_score: Confidence score 0.0-1.0.
        matched_fields: Fields that contributed to the match.
        match_reasons: Explanation of why this is a match.
        screening_id: ID of the screening operation.
        screened_at: When the screening occurred.
    """

    match_id: UUID
    entity: SanctionedEntity
    match_type: MatchType
    match_score: float = Field(ge=0.0, le=1.0)
    matched_fields: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    screening_id: UUID | None = None
    screened_at: datetime = Field(default_factory=lambda: datetime.now())


class SanctionsScreeningResult(BaseModel):
    """Complete result of a sanctions screening.

    Attributes:
        screening_id: Unique identifier for this screening.
        subject_name: Name that was screened.
        subject_dob: Date of birth if provided.
        subject_country: Country if provided.
        lists_screened: Which lists were searched.
        matches: All matches found.
        total_matches: Total number of matches.
        highest_match_score: Best match score across all matches.
        has_hit: Whether any matches were found.
        screened_at: When the screening completed.
        screening_time_ms: How long the screening took.
        cached: Whether result was from cache.
    """

    screening_id: UUID
    subject_name: str
    subject_dob: date | None = None
    subject_country: str | None = None
    lists_screened: list[SanctionsList] = Field(default_factory=list)
    matches: list[SanctionsMatch] = Field(default_factory=list)
    total_matches: int = 0
    highest_match_score: float = 0.0
    has_hit: bool = False
    screened_at: datetime = Field(default_factory=lambda: datetime.now())
    screening_time_ms: float = 0.0
    cached: bool = False

    def get_strong_matches(self) -> list[SanctionsMatch]:
        """Get matches with strong or exact match type."""
        return [m for m in self.matches if m.match_type in (MatchType.EXACT, MatchType.STRONG)]

    def get_matches_by_list(self, list_source: SanctionsList) -> list[SanctionsMatch]:
        """Get matches from a specific list."""
        return [m for m in self.matches if m.entity.list_source == list_source]


class FuzzyMatchConfig(BaseModel):
    """Configuration for fuzzy name matching.

    Attributes:
        exact_threshold: Score threshold for exact match (default 0.99).
        strong_threshold: Score threshold for strong match (default 0.90).
        medium_threshold: Score threshold for medium match (default 0.80).
        weak_threshold: Score threshold for weak match (default 0.70).
        min_threshold: Minimum score to report as potential match (default 0.60).
        use_phonetic: Whether to use phonetic matching (Soundex, Metaphone).
        use_aliases: Whether to check aliases in addition to primary name.
        weight_dob: Weight for DOB matching (0.0-1.0).
        weight_country: Weight for country matching (0.0-1.0).
    """

    exact_threshold: float = Field(ge=0.0, le=1.0, default=0.99)
    strong_threshold: float = Field(ge=0.0, le=1.0, default=0.90)
    medium_threshold: float = Field(ge=0.0, le=1.0, default=0.80)
    weak_threshold: float = Field(ge=0.0, le=1.0, default=0.70)
    min_threshold: float = Field(ge=0.0, le=1.0, default=0.60)
    use_phonetic: bool = True
    use_aliases: bool = True
    weight_dob: float = Field(ge=0.0, le=1.0, default=0.2)
    weight_country: float = Field(ge=0.0, le=1.0, default=0.1)

    def score_to_match_type(self, score: float) -> MatchType:
        """Convert a match score to a match type."""
        if score >= self.exact_threshold:
            return MatchType.EXACT
        elif score >= self.strong_threshold:
            return MatchType.STRONG
        elif score >= self.medium_threshold:
            return MatchType.MEDIUM
        elif score >= self.weak_threshold:
            return MatchType.WEAK
        elif score >= self.min_threshold:
            return MatchType.POTENTIAL
        return MatchType.NO_MATCH


# =============================================================================
# Exceptions
# =============================================================================


class SanctionsProviderError(Exception):
    """Base exception for sanctions provider errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SanctionsListUnavailableError(SanctionsProviderError):
    """Raised when a sanctions list is unavailable."""

    def __init__(self, list_source: SanctionsList, reason: str) -> None:
        super().__init__(
            f"Sanctions list {list_source.value} unavailable: {reason}",
            details={"list_source": list_source.value, "reason": reason},
        )
        self.list_source = list_source
        self.reason = reason


class SanctionsScreeningError(SanctionsProviderError):
    """Raised when screening fails."""

    def __init__(self, screening_id: UUID, reason: str) -> None:
        super().__init__(
            f"Sanctions screening {screening_id} failed: {reason}",
            details={"screening_id": str(screening_id), "reason": reason},
        )
        self.screening_id = screening_id
        self.reason = reason
