"""Compliance type definitions for locale-aware background checks.

This module defines the core enums and models for the compliance framework:
- Locale: Geographic jurisdictions with specific compliance requirements
- CheckType: Types of background checks that can be performed
- RoleCategory: Job role categories that affect check requirements
- CheckRestriction: Outcome of compliance evaluation
"""

from datetime import timedelta
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Locale(str, Enum):
    """Geographic jurisdictions with specific compliance requirements.

    Each locale has distinct regulations governing what background checks
    are permitted, lookback periods, consent requirements, and disclosure rules.
    """

    # United States
    US = "US"  # Federal FCRA + state variations
    US_CA = "US_CA"  # California ICRAA
    US_NY = "US_NY"  # New York Fair Chance Act
    US_MA = "US_MA"  # Massachusetts CORI
    US_IL = "US_IL"  # Illinois BIPA

    # European Union / UK
    EU = "EU"  # GDPR baseline
    UK = "UK"  # UK DBS + post-Brexit GDPR
    DE = "DE"  # Germany (strict)
    FR = "FR"  # France
    NL = "NL"  # Netherlands

    # Canada
    CA = "CA"  # PIPEDA federal
    CA_BC = "CA_BC"  # British Columbia PIPA
    CA_AB = "CA_AB"  # Alberta PIPA
    CA_QC = "CA_QC"  # Quebec Bill 64

    # Asia-Pacific
    AU = "AU"  # Australia Privacy Act
    SG = "SG"  # Singapore PDPA
    HK = "HK"  # Hong Kong PDPO
    JP = "JP"  # Japan APPI
    IN = "IN"  # India (limited framework)

    # Latin America
    BR = "BR"  # Brazil LGPD
    MX = "MX"  # Mexico LFPDPPP
    AR = "AR"  # Argentina (strict)
    CO = "CO"  # Colombia

    # Middle East / Africa
    AE = "AE"  # UAE
    ZA = "ZA"  # South Africa POPIA


class CheckType(str, Enum):
    """Types of background checks that can be performed.

    These represent the categories of information that can be searched
    during a background investigation. Availability varies by locale
    and service tier.
    """

    # Identity Verification
    IDENTITY_BASIC = "identity_basic"  # Name, DOB, address verification
    IDENTITY_BIOMETRIC = "identity_biometric"  # Enhanced tier only
    SSN_TRACE = "ssn_trace"  # US only

    # Criminal Records
    CRIMINAL_NATIONAL = "criminal_national"
    CRIMINAL_STATE = "criminal_state"
    CRIMINAL_COUNTY = "criminal_county"
    CRIMINAL_FEDERAL = "criminal_federal"
    CRIMINAL_INTERNATIONAL = "criminal_international"
    SEX_OFFENDER = "sex_offender"

    # Civil Records
    CIVIL_LITIGATION = "civil_litigation"
    CIVIL_JUDGMENTS = "civil_judgments"
    BANKRUPTCY = "bankruptcy"
    LIENS = "liens"

    # Financial
    CREDIT_REPORT = "credit_report"
    CREDIT_SCORE = "credit_score"

    # Employment
    EMPLOYMENT_VERIFICATION = "employment_verification"
    EMPLOYMENT_REFERENCE = "employment_reference"

    # Education
    EDUCATION_VERIFICATION = "education_verification"
    EDUCATION_DEGREE = "education_degree"

    # Professional
    LICENSE_VERIFICATION = "license_verification"
    PROFESSIONAL_SANCTIONS = "professional_sanctions"
    REGULATORY_ENFORCEMENT = "regulatory_enforcement"

    # Sanctions / Watchlists
    SANCTIONS_OFAC = "sanctions_ofac"
    SANCTIONS_UN = "sanctions_un"
    SANCTIONS_EU = "sanctions_eu"
    SANCTIONS_PEP = "sanctions_pep"  # Politically Exposed Persons
    WATCHLIST_INTERPOL = "watchlist_interpol"
    WATCHLIST_FBI = "watchlist_fbi"

    # Media / Intelligence
    ADVERSE_MEDIA = "adverse_media"
    ADVERSE_MEDIA_AI = "adverse_media_ai"  # Enhanced tier only

    # Digital / OSINT (Enhanced tier only)
    DIGITAL_FOOTPRINT = "digital_footprint"
    SOCIAL_MEDIA = "social_media"

    # Network Analysis
    BUSINESS_AFFILIATIONS = "business_affiliations"
    NETWORK_D2 = "network_d2"  # Direct connections
    NETWORK_D3 = "network_d3"  # Extended network (Enhanced only)

    # Location / Behavioral (Enhanced + explicit consent)
    LOCATION_HISTORY = "location_history"
    BEHAVIORAL_DATA = "behavioral_data"

    # Dark Web (Enhanced, security use only)
    DARK_WEB_MONITORING = "dark_web_monitoring"

    # Drug / Health
    DRUG_TEST = "drug_test"
    MOTOR_VEHICLE = "motor_vehicle"


class RoleCategory(str, Enum):
    """Job role categories that affect compliance requirements.

    Different role types have different permitted checks based on
    regulatory requirements and job duties.
    """

    STANDARD = "standard"  # General employment
    FINANCIAL = "financial"  # FINRA, banking, fiduciary
    GOVERNMENT = "government"  # Public sector, security clearance
    HEALTHCARE = "healthcare"  # HIPAA, medical licensing
    EDUCATION = "education"  # Working with minors
    TRANSPORTATION = "transportation"  # DOT, CDL
    EXECUTIVE = "executive"  # C-suite, board members
    SECURITY = "security"  # Physical/cyber security roles
    CONTRACTOR = "contractor"  # Third-party contractors


class RestrictionType(str, Enum):
    """Types of restrictions on background checks."""

    BLOCKED = "blocked"  # Check not permitted
    LOOKBACK_LIMITED = "lookback_limited"  # Time limit on records
    CONSENT_REQUIRED = "consent_required"  # Explicit consent needed
    DISCLOSURE_REQUIRED = "disclosure_required"  # Must notify subject
    ROLE_RESTRICTED = "role_restricted"  # Only for specific roles
    TIER_RESTRICTED = "tier_restricted"  # Only for Enhanced tier
    CONDITIONAL = "conditional"  # Permitted with conditions


class CheckRestriction(BaseModel):
    """Outcome of compliance rule evaluation for a specific check.

    Represents whether a check is permitted and any restrictions
    that apply based on locale, role, and tier.
    """

    check_type: CheckType
    permitted: bool = True
    restriction_type: RestrictionType | None = None

    # Lookback period (None = unlimited)
    lookback_days: int | None = None

    # Conditions for permission
    requires_consent: bool = False
    requires_disclosure: bool = False
    requires_enhanced_tier: bool = False

    # Additional restrictions
    role_categories: list[RoleCategory] = Field(default_factory=list)
    notes: str | None = None

    @property
    def lookback_period(self) -> timedelta | None:
        """Get lookback period as timedelta."""
        if self.lookback_days is None:
            return None
        return timedelta(days=self.lookback_days)

    def is_permitted_for_role(self, role: RoleCategory) -> bool:
        """Check if permitted for a specific role category."""
        if not self.permitted:
            return False
        if not self.role_categories:
            return True  # No role restriction
        return role in self.role_categories


class CheckResult(BaseModel):
    """Result of evaluating whether a check can be performed.

    This is the output of the compliance engine's evaluate_check method.
    """

    check_type: CheckType
    locale: Locale
    permitted: bool
    restrictions: list[CheckRestriction] = Field(default_factory=list)

    # Combined requirements from all restrictions
    requires_consent: bool = False
    requires_disclosure: bool = False
    requires_enhanced_tier: bool = False
    lookback_days: int | None = None

    # Reason for blocking (if not permitted)
    block_reason: str | None = None

    @property
    def lookback_period(self) -> timedelta | None:
        """Get the most restrictive lookback period."""
        if self.lookback_days is None:
            return None
        return timedelta(days=self.lookback_days)


class LocaleConfig(BaseModel):
    """Configuration for a specific locale.

    Defines the base compliance framework and default restrictions
    for a geographic jurisdiction.
    """

    locale: Locale
    name: str
    framework: str  # e.g., "FCRA", "GDPR", "PIPEDA"
    parent_locale: Locale | None = None  # For inheritance

    # Default settings
    default_lookback_days: int | None = None  # None = unlimited
    consent_always_required: bool = True
    disclosure_always_required: bool = False

    # Adverse action requirements
    adverse_action_required: bool = False
    adverse_action_waiting_days: int = 0

    # Data retention
    max_retention_days: int | None = None

    # Blocked check types (absolute blocks for this locale)
    blocked_checks: list[CheckType] = Field(default_factory=list)

    # Enhanced tier only checks
    enhanced_only_checks: list[CheckType] = Field(default_factory=list)


# Tier restrictions: checks only available in Enhanced tier
ENHANCED_TIER_CHECKS: set[CheckType] = {
    CheckType.IDENTITY_BIOMETRIC,
    CheckType.ADVERSE_MEDIA_AI,
    CheckType.DIGITAL_FOOTPRINT,
    CheckType.SOCIAL_MEDIA,
    CheckType.NETWORK_D3,
    CheckType.LOCATION_HISTORY,
    CheckType.BEHAVIORAL_DATA,
    CheckType.DARK_WEB_MONITORING,
}

# Checks requiring explicit consent beyond standard background check consent
EXPLICIT_CONSENT_CHECKS: set[CheckType] = {
    CheckType.CREDIT_REPORT,
    CheckType.CREDIT_SCORE,
    CheckType.DRUG_TEST,
    CheckType.LOCATION_HISTORY,
    CheckType.BEHAVIORAL_DATA,
    CheckType.SOCIAL_MEDIA,
}

# Checks that are generally not permitted for hiring decisions
HIRING_RESTRICTED_CHECKS: set[CheckType] = {
    CheckType.DARK_WEB_MONITORING,  # Security use only
    CheckType.BEHAVIORAL_DATA,  # Sensitive, limited use
}


# Type aliases for clarity
PermissionStatus = Literal["permitted", "blocked", "conditional"]
