"""Type definitions for LLM Synthesis Provider.

This module defines the core types for synthesizing verification data from
public sources using LLM models for extraction and cross-validation.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid7

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Source type for synthesized data."""

    LLM_SYNTHESIS = "llm_synthesis"
    OFFICIAL_PROVIDER = "official_provider"
    PUBLIC_RECORD = "public_record"


class AttestationType(str, Enum):
    """Types of peer attestation."""

    LINKEDIN_RECOMMENDATION = "linkedin_recommendation"
    LINKEDIN_SKILL_ENDORSEMENT = "linkedin_skill_endorsement"
    LINKEDIN_COWORKER_CONNECTION = "linkedin_coworker"
    COAUTHORED_PAPER = "coauthored_paper"
    COAUTHORED_PATENT = "coauthored_patent"
    CONFERENCE_SPEAKER = "conference_speaker"
    PRESS_RELEASE = "press_release"
    NEWS_QUOTE = "news_quote"
    SEC_FILING = "sec_filing"
    COMPANY_BLOG = "company_blog"
    GITHUB_ORG_MEMBER = "github_org_member"
    ALUMNI_DIRECTORY = "alumni_directory"
    PUBLICATION_AUTHOR = "publication_author"
    AWARD_RECIPIENT = "award_recipient"


class RelationshipType(str, Enum):
    """Relationship between attester and subject."""

    MANAGER = "manager"
    DIRECT_REPORT = "direct_report"
    COLLEAGUE = "colleague"
    TEAMMATE = "teammate"
    CLIENT = "client"
    VENDOR = "vendor"
    PARTNER = "partner"
    CLASSMATE = "classmate"
    PROFESSOR = "professor"
    MENTOR = "mentor"
    UNKNOWN = "unknown"


class ConfidenceFactor(str, Enum):
    """Factors contributing to attestation confidence."""

    ATTESTER_VERIFIED_AT_EMPLOYER = "attester_verified_at_employer"
    ATTESTER_EXTERNAL = "attester_external"
    RELATIONSHIP_MANAGER = "relationship_manager"
    RELATIONSHIP_COLLEAGUE = "relationship_colleague"
    RELATIONSHIP_UNKNOWN = "relationship_unknown"
    MENTIONS_PROJECTS = "mentions_projects"
    MENTIONS_TIMEFRAME = "mentions_timeframe"
    MENTIONS_TITLE = "mentions_title"
    ATTESTER_ESTABLISHED_NETWORK = "attester_established_network"
    ATTESTER_VERIFIED_ACCOUNT = "attester_verified_account"
    RECENT_ATTESTATION = "recent_attestation"
    MODERATELY_RECENT = "moderately_recent"
    SEC_FILING_SOURCE = "sec_filing_source"
    NEWS_SOURCE = "news_source"
    OFFICIAL_UNIVERSITY_SOURCE = "official_university_source"


class PublicSourceType(str, Enum):
    """Types of public sources for data gathering."""

    LINKEDIN_PROFILE = "linkedin_profile"
    LINKEDIN_RECOMMENDATION = "linkedin_recommendation"
    LINKEDIN_ENDORSEMENT = "linkedin_endorsement"
    NEWS_ARTICLE = "news_article"
    PRESS_RELEASE = "press_release"
    SEC_FILING = "sec_filing"
    COMPANY_WEBSITE = "company_website"
    UNIVERSITY_WEBSITE = "university_website"
    PROFESSIONAL_DIRECTORY = "professional_directory"
    GITHUB_PROFILE = "github_profile"
    TWITTER_PROFILE = "twitter_profile"
    PATENT_DATABASE = "patent_database"
    ACADEMIC_PUBLICATION = "academic_publication"
    ALUMNI_NETWORK = "alumni_network"
    STATE_LICENSE_BOARD = "state_license_board"
    COURT_RECORDS = "court_records"


class SynthesisLLMModel(str, Enum):
    """LLM models available for synthesis."""

    CLAUDE_OPUS = "claude-3-opus"
    CLAUDE_SONNET = "claude-3-sonnet"
    GPT4 = "gpt-4"
    GPT4_TURBO = "gpt-4-turbo"
    GEMINI_PRO = "gemini-pro"


# ============================================================
# Public Source Models
# ============================================================


class PublicSource(BaseModel):
    """A public source used for data synthesis."""

    source_id: UUID = Field(default_factory=uuid7)
    source_type: PublicSourceType
    url: str | None = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    content: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)

    class Config:
        """Model configuration."""

        frozen = False


class LinkedInProfile(BaseModel):
    """LinkedIn profile data."""

    profile_url: str
    full_name: str
    headline: str | None = None
    location: str | None = None
    connections: int | None = None
    verified: bool = False
    experience: list["LinkedInExperience"] = Field(default_factory=list)
    education: list["LinkedInEducation"] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class LinkedInExperience(BaseModel):
    """LinkedIn experience entry."""

    company: str
    title: str
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None
    is_current: bool = False


class LinkedInEducation(BaseModel):
    """LinkedIn education entry."""

    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    activities: str | None = None


class LinkedInRecommendation(BaseModel):
    """LinkedIn recommendation."""

    author_name: str
    author_profile_url: str | None = None
    author_title: str | None = None
    text: str
    recommendation_date: date | None = None


class NewsArticle(BaseModel):
    """News article data."""

    url: str
    title: str
    source: str
    published_date: date | None = None
    content: str = ""
    author: str | None = None
    mentions_subject: bool = True


class SECFiling(BaseModel):
    """SEC filing data."""

    filing_type: str  # 10-K, 10-Q, 8-K, DEF 14A, etc.
    company_name: str
    filing_date: date
    url: str
    content_excerpt: str = ""
    mentions_subject: bool = True
    role_mentioned: str | None = None


# ============================================================
# Attestation Models
# ============================================================


class EmploymentAttestation(BaseModel):
    """Evidence of employment from peer attestations."""

    id: UUID = Field(default_factory=uuid7)
    employer: str
    attestation_type: AttestationType

    # The attester
    attester_name: str
    attester_linkedin_url: str | None = None
    attester_title_at_time: str | None = None
    attester_employer_verified: bool = False

    # The attestation content
    attestation_text: str
    relationship_type: RelationshipType = RelationshipType.UNKNOWN
    date_of_attestation: date | None = None

    # What this attestation proves
    proves_employment: bool = True
    proves_dates: bool = False
    proves_title: bool = False
    proves_performance: bool = False

    # Extracted details
    mentioned_title: str | None = None
    mentioned_timeframe: str | None = None
    mentioned_projects: list[str] = Field(default_factory=list)

    # Confidence for this single attestation
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_factors: list[ConfidenceFactor] = Field(default_factory=list)


class EducationAttestation(BaseModel):
    """Evidence of education from attestations."""

    id: UUID = Field(default_factory=uuid7)
    institution: str
    attestation_type: AttestationType

    # The attester
    attester_name: str
    attester_source: str | None = None
    attester_role: str | None = None

    # The attestation content
    attestation_text: str
    date_of_attestation: date | None = None

    # What this attestation proves
    proves_attendance: bool = True
    proves_degree: bool = False
    proves_graduation_date: bool = False
    proves_major: bool = False

    # Extracted details
    mentioned_degree: str | None = None
    mentioned_year: int | None = None
    mentioned_major: str | None = None

    # Confidence
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_factors: list[ConfidenceFactor] = Field(default_factory=list)


# ============================================================
# Synthesized Verification Models
# ============================================================


class SynthesisProvenance(BaseModel):
    """Tracks how synthesized data was derived."""

    public_sources: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)
    models_used: list[str] = Field(default_factory=list)
    consensus_score: float = 0.0
    synthesis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    extraction_prompts: dict[str, str] = Field(default_factory=dict)


class SynthesizedEmploymentVerification(BaseModel):
    """Aggregated employment verification from synthesis."""

    employer: str
    claimed_title: str | None = None
    claimed_start_date: date | None = None
    claimed_end_date: date | None = None

    # Verification status
    employment_confirmed: bool = False
    title_confirmed: bool = False
    dates_confirmed: bool = False

    # Attestation evidence
    attestation_count: int = 0
    unique_attesters: int = 0
    attestations: list[EmploymentAttestation] = Field(default_factory=list)

    # Additional evidence
    press_mentions: list[str] = Field(default_factory=list)
    sec_filings: list[str] = Field(default_factory=list)

    # Confidence (hard capped at 0.85)
    confidence: float = Field(ge=0.0, le=0.85, default=0.0)
    verification_method: str = "peer_attestation"

    # Compliance
    source_type: SourceType = SourceType.LLM_SYNTHESIS
    fcra_usable: bool = False
    flags: list[str] = Field(default_factory=list)


class SynthesizedEducationVerification(BaseModel):
    """Aggregated education verification from synthesis."""

    institution: str
    claimed_degree: str | None = None
    claimed_major: str | None = None
    claimed_graduation_year: int | None = None

    # Verification status
    attendance_confirmed: bool = False
    degree_confirmed: bool = False
    graduation_confirmed: bool = False

    # Attestation evidence
    attestation_count: int = 0
    unique_sources: int = 0
    attestations: list[EducationAttestation] = Field(default_factory=list)

    # Additional evidence
    alumni_mentions: list[str] = Field(default_factory=list)
    publications_at_institution: list[str] = Field(default_factory=list)

    # Confidence (hard capped at 0.80)
    confidence: float = Field(ge=0.0, le=0.80, default=0.0)
    verification_method: str = "public_source_aggregation"

    # Compliance
    source_type: SourceType = SourceType.LLM_SYNTHESIS
    fcra_usable: bool = False
    flags: list[str] = Field(default_factory=list)


class SynthesizedAdverseMedia(BaseModel):
    """Synthesized adverse media findings."""

    search_id: UUID = Field(default_factory=uuid7)
    subject_name: str
    search_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Findings
    total_articles_found: int = 0
    adverse_articles_count: int = 0
    articles: list[NewsArticle] = Field(default_factory=list)

    # Categorization
    categories_found: list[str] = Field(default_factory=list)
    severity_max: str = "none"  # none, low, medium, high
    sentiment_summary: str = "neutral"

    # Confidence (hard capped at 0.75)
    confidence: float = Field(ge=0.0, le=0.75, default=0.0)

    # Compliance
    source_type: SourceType = SourceType.LLM_SYNTHESIS
    fcra_usable: bool = False
    flags: list[str] = Field(
        default_factory=lambda: [
            "SYNTHESIZED_DATA",
            "REQUIRES_VERIFICATION",
            "NOT_FOR_ADVERSE_ACTION",
        ]
    )


class SynthesizedLicenseVerification(BaseModel):
    """Synthesized professional license verification."""

    license_type: str
    claimed_state: str | None = None
    claimed_license_number: str | None = None

    # Verification status
    license_found: bool = False
    status_confirmed: bool = False
    status: str | None = None  # active, inactive, expired, revoked

    # Evidence
    source_url: str | None = None
    last_verified: datetime | None = None
    expiration_date: date | None = None

    # Confidence (hard capped at 0.70)
    confidence: float = Field(ge=0.0, le=0.70, default=0.0)

    # Compliance
    source_type: SourceType = SourceType.LLM_SYNTHESIS
    fcra_usable: bool = False
    flags: list[str] = Field(default_factory=list)


class SynthesizedSocialMedia(BaseModel):
    """Synthesized social media profile."""

    subject_name: str
    profiles_found: int = 0
    profiles: list[dict[str, str]] = Field(default_factory=list)  # platform -> url

    # Analysis
    professional_presence_score: float = 0.0
    red_flags_found: int = 0
    red_flag_details: list[str] = Field(default_factory=list)

    # Confidence (hard capped at 0.80)
    confidence: float = Field(ge=0.0, le=0.80, default=0.0)

    # Compliance
    source_type: SourceType = SourceType.LLM_SYNTHESIS
    fcra_usable: bool = False
    flags: list[str] = Field(default_factory=list)


class SynthesizedCorporateAffiliation(BaseModel):
    """Synthesized corporate affiliation."""

    company_name: str
    role: str | None = None
    role_type: str | None = None  # officer, director, shareholder, etc.
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False

    # Evidence
    source_type_found: str | None = None  # sec, opencorporates, news
    source_url: str | None = None
    filing_references: list[str] = Field(default_factory=list)

    # Confidence (hard capped at 0.75)
    confidence: float = Field(ge=0.0, le=0.75, default=0.0)


class SynthesizedCorporateAffiliations(BaseModel):
    """Collection of corporate affiliations."""

    subject_name: str
    affiliations: list[SynthesizedCorporateAffiliation] = Field(default_factory=list)
    total_companies: int = 0
    active_affiliations: int = 0

    # Aggregate confidence
    confidence: float = Field(ge=0.0, le=0.75, default=0.0)

    # Compliance
    source_type: SourceType = SourceType.LLM_SYNTHESIS
    fcra_usable: bool = False
    flags: list[str] = Field(default_factory=list)


# ============================================================
# Provider Configuration
# ============================================================


class LLMSynthesisProviderConfig(BaseModel):
    """Configuration for LLM synthesis provider."""

    # LLM settings
    primary_model: SynthesisLLMModel = SynthesisLLMModel.CLAUDE_SONNET
    secondary_model: SynthesisLLMModel = SynthesisLLMModel.GPT4
    require_consensus: bool = True
    min_consensus_score: float = Field(default=0.7, ge=0.0, le=1.0)

    # Confidence caps per check type (by check type string)
    max_confidence: dict[str, float] = Field(
        default_factory=lambda: {
            "employment_verification": 0.85,
            "education_verification": 0.80,
            "adverse_media": 0.75,
            "license_verification": 0.70,
            "social_media": 0.80,
            "business_affiliations": 0.75,
        }
    )

    # Source settings
    linkedin_enabled: bool = True
    news_search_enabled: bool = True
    sec_filings_enabled: bool = True
    github_enabled: bool = True

    # Rate limiting
    max_sources_per_check: int = Field(default=10, ge=1, le=50)
    max_llm_calls_per_check: int = Field(default=4, ge=1, le=10)

    # Timeouts (seconds)
    source_fetch_timeout: float = Field(default=30.0, ge=5.0)
    llm_call_timeout: float = Field(default=60.0, ge=10.0)


# ============================================================
# Exceptions
# ============================================================


class SynthesisProviderError(Exception):
    """Base exception for synthesis provider errors."""

    pass


class UnsupportedCheckTypeError(SynthesisProviderError):
    """Raised when a check type is not supported by synthesis."""

    def __init__(self, check_type: str, supported: list[str]):
        super().__init__(f"LLM synthesis does not support {check_type}. Supported: {supported}")
        self.check_type = check_type
        self.supported = supported


class SourceFetchError(SynthesisProviderError):
    """Raised when source fetching fails."""

    def __init__(self, source_type: str, reason: str):
        super().__init__(f"Failed to fetch {source_type}: {reason}")
        self.source_type = source_type
        self.reason = reason


class LLMExtractionError(SynthesisProviderError):
    """Raised when LLM extraction fails."""

    def __init__(self, model: str, reason: str):
        super().__init__(f"LLM extraction failed for {model}: {reason}")
        self.model = model
        self.reason = reason


class ConsensusFailedError(SynthesisProviderError):
    """Raised when LLM consensus is too low."""

    def __init__(self, consensus_score: float, min_required: float):
        super().__init__(f"Consensus score {consensus_score:.2f} below minimum {min_required:.2f}")
        self.consensus_score = consensus_score
        self.min_required = min_required
