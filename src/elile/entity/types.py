"""Entity resolution type definitions.

This module defines the core types for entity resolution including
match results, resolution decisions, and identifier types.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MatchType(str, Enum):
    """Type of entity match found."""

    EXACT = "exact"  # Canonical identifier match (SSN, EIN, etc.)
    FUZZY = "fuzzy"  # Similarity-based match
    NEW = "new"  # No match found, new entity


class ResolutionDecision(str, Enum):
    """Decision from entity resolution."""

    MATCH_EXISTING = "match_existing"  # Use existing entity
    CREATE_NEW = "create_new"  # Create new entity
    PENDING_REVIEW = "pending_review"  # Queue for analyst review (Enhanced tier)


class IdentifierType(str, Enum):
    """Types of canonical identifiers."""

    SSN = "ssn"  # US Social Security Number
    EIN = "ein"  # US Employer Identification Number
    PASSPORT = "passport"  # Passport number
    DRIVERS_LICENSE = "drivers_license"  # Driver's license
    NATIONAL_ID = "national_id"  # National ID card
    TAX_ID = "tax_id"  # Generic tax ID
    EMAIL = "email"  # Email address
    PHONE = "phone"  # Phone number


class RelationType(str, Enum):
    """Types of entity relationships."""

    EMPLOYER = "employer"  # Employment relationship
    EMPLOYEE = "employee"  # Employment relationship (reverse)
    HOUSEHOLD = "household"  # Shared residence
    BUSINESS_PARTNER = "business_partner"  # Business partnership
    COLLEAGUE = "colleague"  # Workplace connection
    FAMILY = "family"  # Family relationship
    ASSOCIATE = "associate"  # General association
    DIRECTOR = "director"  # Company director
    OFFICER = "officer"  # Company officer
    OWNER = "owner"  # Business ownership


class MatchedField(BaseModel):
    """A field that matched during entity resolution."""

    field_name: str
    source_value: str
    matched_value: str
    similarity: float  # 0.0 - 1.0


class MatchResult(BaseModel):
    """Result of entity matching operation.

    Contains the matched entity (if any), match type, confidence score,
    and details about which fields matched.
    """

    entity_id: UUID | None = None  # Matched entity ID or None
    match_type: MatchType
    confidence: float = Field(ge=0.0, le=1.0)  # 0.0 - 1.0
    decision: ResolutionDecision
    requires_review: bool = False  # True if needs analyst review

    # Match details
    matched_fields: list[MatchedField] = Field(default_factory=list)
    matched_identifiers: list[IdentifierType] = Field(default_factory=list)

    # Metadata
    resolution_notes: str | None = None


class SubjectIdentifiers(BaseModel):
    """Identifiers for a subject being resolved.

    Contains all known identifiers for matching against existing entities.
    """

    # Name information
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    name_variants: list[str] = Field(default_factory=list)

    # Date of birth
    date_of_birth: date | None = None

    # Address
    street_address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str = "US"

    # Canonical identifiers
    ssn: str | None = None
    ein: str | None = None
    passport: str | None = None
    passport_country: str | None = None
    drivers_license: str | None = None
    drivers_license_state: str | None = None
    national_id: str | None = None
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None

    def has_canonical_identifiers(self) -> bool:
        """Check if any canonical identifiers are present."""
        return any([
            self.ssn,
            self.ein,
            self.passport,
            self.drivers_license,
            self.national_id,
            self.tax_id,
        ])

    def get_canonical_identifiers(self) -> dict[IdentifierType, str]:
        """Get dictionary of available canonical identifiers."""
        identifiers: dict[IdentifierType, str] = {}
        if self.ssn:
            identifiers[IdentifierType.SSN] = self.ssn
        if self.ein:
            identifiers[IdentifierType.EIN] = self.ein
        if self.passport:
            identifiers[IdentifierType.PASSPORT] = self.passport
        if self.drivers_license:
            identifiers[IdentifierType.DRIVERS_LICENSE] = self.drivers_license
        if self.national_id:
            identifiers[IdentifierType.NATIONAL_ID] = self.national_id
        if self.tax_id:
            identifiers[IdentifierType.TAX_ID] = self.tax_id
        if self.email:
            identifiers[IdentifierType.EMAIL] = self.email
        if self.phone:
            identifiers[IdentifierType.PHONE] = self.phone
        return identifiers


class IdentifierRecord(BaseModel):
    """Record of a discovered identifier.

    Tracks when and where an identifier was discovered,
    along with its confidence level.
    """

    identifier_type: IdentifierType
    value: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    discovered_at: datetime
    source: str  # Where this identifier was discovered
    country: str | None = None  # For passport, national ID
    state: str | None = None  # For driver's license

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        result = {
            "value": self.value,
            "confidence": self.confidence,
            "discovered_at": self.discovered_at.isoformat(),
            "source": self.source,
        }
        if self.country:
            result["country"] = self.country
        if self.state:
            result["state"] = self.state
        return result
