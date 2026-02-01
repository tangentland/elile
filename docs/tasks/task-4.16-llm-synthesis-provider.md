# Task 4.16: LLM Synthesis Provider

## Overview

Create a fallback data provider that uses LLM models to synthesize verification information from publicly available sources when paid providers are unavailable or as a cost-effective supplement. This provider aggregates data from LinkedIn, news sources, SEC filings, and other public records, using multiple LLMs for cross-validation.

**Priority**: P1 | **Effort**: 5 days | **Status**: Not Started

## Dependencies

- Task 4.1: Provider Gateway
- Task 4.4: Response Normalizer
- Task 4.6: Request Routing (for fallback logic)
- Task 5.10: Finding Extractor (for structured extraction)

## Use Cases

1. **Cost Optimization**: Use synthesis for initial screening, escalate to paid providers only when needed
2. **Fallback**: When paid providers are unavailable or rate-limited
3. **Supplementary Data**: Enrich paid provider data with additional public source context
4. **Gap Filling**: Fill information gaps when paid providers return partial data

## Supported Check Types

| Check Type | Synthesis Approach | Max Confidence |
|------------|-------------------|----------------|
| `EMPLOYMENT_VERIFICATION` | LinkedIn + news + press releases | 0.85 |
| `EDUCATION_VERIFICATION` | LinkedIn + university news + alumni | 0.80 |
| `ADVERSE_MEDIA` | Web search + news APIs + social | 0.75 |
| `PROFESSIONAL_LICENSE` | State board websites + LinkedIn | 0.70 |
| `SOCIAL_MEDIA` | Public profile aggregation | 0.80 |
| `CORPORATE_AFFILIATIONS` | SEC + OpenCorporates + news | 0.75 |

### NOT Supported (compliance/accuracy concerns)

- `CREDIT_REPORT` - Legally protected, no public source
- `CRIMINAL_RECORD` - Accuracy critical, hallucination risk too high
- `IDENTITY_VERIFICATION` - Requires authoritative sources
- `SANCTIONS_CHECK` - Use free OFAC/UN APIs directly instead

## Implementation Checklist

- [ ] Create LLMSynthesisProvider base class
- [ ] Implement public source fetchers (LinkedIn, news, SEC)
- [ ] Build attestation models and scoring
- [ ] Implement multi-LLM synthesis with consensus
- [ ] Create confidence scoring system
- [ ] Add FCRA compliance flags and safeguards
- [ ] Build employment attestation aggregator
- [ ] Build education attestation aggregator
- [ ] Implement adverse media synthesizer
- [ ] Create provenance tracking
- [ ] Write comprehensive tests
- [ ] Add integration with RequestRouter as fallback

## Key Data Models

```python
# src/elile/providers/synthesis/models.py
from enum import Enum
from pydantic import BaseModel, Field
from datetime import date
from uuid import UUID


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


class RelationshipType(str, Enum):
    """Relationship between attester and subject."""
    MANAGER = "manager"
    DIRECT_REPORT = "direct_report"
    COLLEAGUE = "colleague"
    TEAMMATE = "teammate"
    CLIENT = "client"
    VENDOR = "vendor"
    PARTNER = "partner"
    UNKNOWN = "unknown"


class EmploymentAttestation(BaseModel):
    """Evidence of employment from peer attestations."""

    id: UUID
    employer: str
    attestation_type: AttestationType

    # The attester
    attester_name: str
    attester_linkedin_url: str | None = None
    attester_title_at_time: str | None = None
    attester_employer_verified: bool = False  # Did they also work there?

    # The attestation content
    attestation_text: str
    relationship_type: RelationshipType = RelationshipType.UNKNOWN
    date_of_attestation: date | None = None

    # What this attestation proves
    proves_employment: bool = True
    proves_dates: bool = False
    proves_title: bool = False
    proves_performance: bool = False

    # Extracted details (if mentioned)
    mentioned_title: str | None = None
    mentioned_timeframe: str | None = None
    mentioned_projects: list[str] = Field(default_factory=list)

    # Confidence for this single attestation
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_factors: list[str] = Field(default_factory=list)


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

    # Confidence
    confidence: float = Field(ge=0.0, le=0.85)  # Hard cap at 0.85
    verification_method: str = "peer_attestation"

    # Compliance
    source_type: SourceType = SourceType.LLM_SYNTHESIS
    fcra_usable: bool = False  # Cannot be sole basis for adverse action
    flags: list[str] = Field(default_factory=list)


class SynthesisProvenance(BaseModel):
    """Tracks how synthesized data was derived."""

    # Sources used
    public_sources: list[str]  # URLs
    source_types: list[str]  # linkedin, news, sec, etc.

    # LLM processing
    models_used: list[str]  # ["claude-3-opus", "gpt-4"]
    consensus_score: float  # Agreement between models

    # Audit trail
    synthesis_timestamp: date
    extraction_prompts: dict[str, str]  # check_type -> prompt used
    raw_model_responses: dict[str, str] | None = None  # For audit


class SynthesizedFinding(BaseModel):
    """A finding derived from LLM synthesis."""

    finding_id: UUID
    category: str
    description: str

    # Source tracking
    source_type: SourceType = SourceType.LLM_SYNTHESIS
    provenance: SynthesisProvenance

    # Confidence (capped)
    confidence: float = Field(ge=0.0, le=0.85)

    # Compliance flags
    fcra_usable: bool = False
    verification_required: bool = True
    not_for_adverse_action: bool = True

    # Display flags
    display_flags: list[str] = Field(default_factory=lambda: [
        "SYNTHESIZED_DATA",
        "NOT_FOR_ADVERSE_ACTION",
        "REQUIRES_VERIFICATION",
    ])
```

## Core Provider Implementation

```python
# src/elile/providers/synthesis/provider.py
from elile.providers.protocol import DataProvider
from elile.providers.types import (
    DataSourceCategory, CostTier, ProviderResult, ProviderHealth,
    CheckType, ProviderStatus
)


class LLMSynthesisProviderConfig(BaseModel):
    """Configuration for LLM synthesis provider."""

    # LLM settings
    primary_model: str = "claude-3-opus"
    secondary_model: str = "gpt-4"
    require_consensus: bool = True
    min_consensus_score: float = 0.7

    # Confidence caps per check type
    max_confidence: dict[CheckType, float] = Field(default_factory=lambda: {
        CheckType.EMPLOYMENT_VERIFICATION: 0.85,
        CheckType.EDUCATION_VERIFICATION: 0.80,
        CheckType.ADVERSE_MEDIA: 0.75,
        CheckType.PROFESSIONAL_LICENSE: 0.70,
        CheckType.SOCIAL_MEDIA: 0.80,
        CheckType.CORPORATE_AFFILIATIONS: 0.75,
    })

    # Source settings
    linkedin_enabled: bool = True
    news_search_enabled: bool = True
    sec_filings_enabled: bool = True

    # Rate limiting
    max_sources_per_check: int = 10
    max_llm_calls_per_check: int = 4


class LLMSynthesisProvider(DataProvider):
    """
    Fallback provider that synthesizes verification data from public sources.

    Uses multiple LLMs to extract and cross-validate information from:
    - LinkedIn profiles and recommendations
    - News articles and press releases
    - SEC filings and corporate records
    - Public professional databases

    All synthesized data is clearly marked and capped at lower confidence
    than official provider data.
    """

    provider_id = "llm_synthesis"
    provider_name = "LLM Synthesis Provider"
    tier_category = DataSourceCategory.CORE  # Available to all tiers
    cost_tier = CostTier.LOW  # Just LLM API costs

    supported_checks = [
        CheckType.EMPLOYMENT_VERIFICATION,
        CheckType.EDUCATION_VERIFICATION,
        CheckType.ADVERSE_MEDIA,
        CheckType.PROFESSIONAL_LICENSE,
        CheckType.SOCIAL_MEDIA,
        CheckType.CORPORATE_AFFILIATIONS,
    ]

    def __init__(
        self,
        config: LLMSynthesisProviderConfig,
        claude_client: ClaudeClient,
        openai_client: OpenAIClient,
        linkedin_fetcher: LinkedInFetcher,
        news_fetcher: NewsFetcher,
        sec_fetcher: SECFetcher,
    ):
        self.config = config
        self.claude = claude_client
        self.openai = openai_client
        self.linkedin = linkedin_fetcher
        self.news = news_fetcher
        self.sec = sec_fetcher

        self._synthesizers = {
            CheckType.EMPLOYMENT_VERIFICATION: EmploymentSynthesizer(self),
            CheckType.EDUCATION_VERIFICATION: EducationSynthesizer(self),
            CheckType.ADVERSE_MEDIA: AdverseMediaSynthesizer(self),
            CheckType.PROFESSIONAL_LICENSE: LicenseSynthesizer(self),
            CheckType.SOCIAL_MEDIA: SocialMediaSynthesizer(self),
            CheckType.CORPORATE_AFFILIATIONS: CorporateSynthesizer(self),
        }

    async def execute_check(
        self,
        check_type: CheckType,
        subject: SubjectInfo,
        locale: Locale,
        degree: SearchDegree,
    ) -> ProviderResult:
        """Execute synthesized check from public sources."""

        if check_type not in self.supported_checks:
            raise UnsupportedCheckTypeError(
                f"LLM synthesis does not support {check_type}. "
                f"Supported: {self.supported_checks}"
            )

        synthesizer = self._synthesizers[check_type]

        # 1. Gather public sources
        sources = await synthesizer.gather_sources(subject)

        # 2. Extract with primary LLM
        primary_result = await self._extract_with_model(
            self.config.primary_model,
            sources,
            check_type,
            subject,
        )

        # 3. Extract with secondary LLM for consensus
        secondary_result = await self._extract_with_model(
            self.config.secondary_model,
            sources,
            check_type,
            subject,
        )

        # 4. Calculate consensus and merge
        merged, consensus_score = self._merge_with_consensus(
            primary_result,
            secondary_result,
        )

        # 5. Apply confidence cap
        max_conf = self.config.max_confidence.get(check_type, 0.7)
        final_confidence = min(merged.confidence, max_conf)

        if self.config.require_consensus and consensus_score < self.config.min_consensus_score:
            final_confidence *= 0.7  # Reduce confidence if low consensus

        # 6. Build result with provenance
        return ProviderResult(
            provider_id=self.provider_id,
            check_type=check_type,
            data=merged.data,
            confidence=final_confidence,
            source_type=SourceType.LLM_SYNTHESIS,
            provenance=SynthesisProvenance(
                public_sources=[s.url for s in sources],
                source_types=[s.source_type for s in sources],
                models_used=[self.config.primary_model, self.config.secondary_model],
                consensus_score=consensus_score,
                synthesis_timestamp=date.today(),
            ),
            flags=[
                "SYNTHESIZED_DATA",
                "NOT_FOR_ADVERSE_ACTION",
                "REQUIRES_VERIFICATION",
            ],
            metadata={
                "synthesis_method": synthesizer.method_name,
                "source_count": len(sources),
                "consensus_score": consensus_score,
            },
        )

    async def health_check(self) -> ProviderHealth:
        """Check health of underlying services."""
        checks = await asyncio.gather(
            self.claude.health_check(),
            self.openai.health_check(),
            self.linkedin.health_check(),
            return_exceptions=True,
        )

        healthy = all(
            isinstance(c, HealthResult) and c.healthy
            for c in checks
        )

        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.HEALTHY if healthy else ProviderStatus.DEGRADED,
            last_check=datetime.utcnow(),
        )
```

## Employment Attestation Synthesizer

```python
# src/elile/providers/synthesis/employment.py

class EmploymentSynthesizer:
    """Synthesizes employment verification from LinkedIn and public sources."""

    method_name = "peer_attestation"

    def __init__(self, provider: LLMSynthesisProvider):
        self.provider = provider
        self.scorer = AttestationScorer()
        self.aggregator = AttestationAggregator()

    async def gather_sources(self, subject: SubjectInfo) -> list[PublicSource]:
        """Gather all relevant public sources for employment verification."""
        sources = []

        # LinkedIn profile and recommendations
        if self.provider.config.linkedin_enabled:
            linkedin_data = await self.provider.linkedin.fetch_profile(
                name=subject.full_name,
                email=subject.email,
            )
            if linkedin_data:
                sources.append(PublicSource(
                    source_type="linkedin_profile",
                    url=linkedin_data.profile_url,
                    content=linkedin_data,
                ))

                # Fetch recommendations
                recommendations = await self.provider.linkedin.fetch_recommendations(
                    profile_url=linkedin_data.profile_url
                )
                for rec in recommendations:
                    sources.append(PublicSource(
                        source_type="linkedin_recommendation",
                        url=rec.url,
                        content=rec,
                    ))

        # News mentions
        if self.provider.config.news_search_enabled:
            for employer in subject.claimed_employers or []:
                news = await self.provider.news.search(
                    query=f'"{subject.full_name}" "{employer}"',
                    max_results=5,
                )
                for article in news:
                    sources.append(PublicSource(
                        source_type="news_article",
                        url=article.url,
                        content=article,
                    ))

        # SEC filings (for executives)
        if self.provider.config.sec_filings_enabled:
            sec_mentions = await self.provider.sec.search_person(
                name=subject.full_name
            )
            for filing in sec_mentions:
                sources.append(PublicSource(
                    source_type="sec_filing",
                    url=filing.url,
                    content=filing,
                ))

        return sources[:self.provider.config.max_sources_per_check]

    async def synthesize(
        self,
        sources: list[PublicSource],
        subject: SubjectInfo,
        claimed_employment: list[ClaimedEmployment],
    ) -> SynthesizedEmploymentVerification:
        """Synthesize employment verification from gathered sources."""

        all_attestations = []

        # Process LinkedIn recommendations
        recommendations = [s for s in sources if s.source_type == "linkedin_recommendation"]
        for rec_source in recommendations:
            rec = rec_source.content

            # Fetch attester's profile to verify they worked at same company
            attester_profile = await self.provider.linkedin.fetch_profile(
                profile_url=rec.author_profile_url
            )

            for claimed in claimed_employment:
                attestation = self.scorer.score_linkedin_recommendation(
                    recommendation=rec,
                    attester_profile=attester_profile,
                    target_claimed_employer=claimed.employer,
                )
                if attestation.confidence > 0.2:  # Minimum relevance threshold
                    all_attestations.append(attestation)

        # Process news mentions
        news_articles = [s for s in sources if s.source_type == "news_article"]
        for article_source in news_articles:
            article = article_source.content

            for claimed in claimed_employment:
                attestation = self.scorer.score_news_mention(
                    article=article,
                    subject_name=subject.full_name,
                    target_employer=claimed.employer,
                )
                if attestation and attestation.confidence > 0.2:
                    all_attestations.append(attestation)

        # Process SEC filings
        sec_filings = [s for s in sources if s.source_type == "sec_filing"]
        for filing_source in sec_filings:
            filing = filing_source.content

            for claimed in claimed_employment:
                attestation = self.scorer.score_sec_filing(
                    filing=filing,
                    subject_name=subject.full_name,
                    target_employer=claimed.employer,
                )
                if attestation and attestation.confidence > 0.3:
                    all_attestations.append(attestation)

        # Aggregate attestations per employer
        results = []
        for claimed in claimed_employment:
            verification = self.aggregator.aggregate_attestations(
                claimed_employment=claimed,
                attestations=all_attestations,
            )
            results.append(verification)

        return results


class AttestationScorer:
    """Scores individual attestations for confidence."""

    def score_linkedin_recommendation(
        self,
        recommendation: LinkedInRecommendation,
        attester_profile: LinkedInProfile | None,
        target_claimed_employer: str,
    ) -> EmploymentAttestation:
        """Score a LinkedIn recommendation as employment attestation."""

        confidence = 0.0
        factors = []

        # Factor 1: Attester worked at same company (0.0 - 0.30)
        attester_employer_verified = False
        if attester_profile:
            attester_employers = [
                exp.company for exp in attester_profile.experience
            ]
            if self._fuzzy_match_employer(target_claimed_employer, attester_employers):
                confidence += 0.30
                factors.append("attester_verified_at_employer")
                attester_employer_verified = True
            else:
                confidence += 0.10  # External recommendation
                factors.append("attester_external")

        # Factor 2: Relationship type (0.0 - 0.20)
        relationship = self._extract_relationship(recommendation.text)
        relationship_scores = {
            RelationshipType.MANAGER: 0.20,
            RelationshipType.DIRECT_REPORT: 0.18,
            RelationshipType.COLLEAGUE: 0.15,
            RelationshipType.TEAMMATE: 0.15,
            RelationshipType.CLIENT: 0.10,
            RelationshipType.VENDOR: 0.10,
            RelationshipType.PARTNER: 0.10,
            RelationshipType.UNKNOWN: 0.05,
        }
        confidence += relationship_scores.get(relationship, 0.05)
        factors.append(f"relationship_{relationship.value}")

        # Factor 3: Specificity of content (0.0 - 0.15)
        mentioned_projects = self._extract_projects(recommendation.text)
        if mentioned_projects:
            confidence += 0.05
            factors.append("mentions_projects")

        mentioned_timeframe = self._extract_timeframe(recommendation.text)
        if mentioned_timeframe:
            confidence += 0.05
            factors.append("mentions_timeframe")

        mentioned_title = self._extract_title(recommendation.text, target_claimed_employer)
        if mentioned_title:
            confidence += 0.05
            factors.append("mentions_title")

        # Factor 4: Attester credibility (0.0 - 0.10)
        if attester_profile:
            if attester_profile.connections and attester_profile.connections > 500:
                confidence += 0.05
                factors.append("attester_established_network")

            if attester_profile.verified:
                confidence += 0.05
                factors.append("attester_verified_account")

        # Factor 5: Recency (0.0 - 0.05)
        if recommendation.date:
            years_old = (date.today() - recommendation.date).days / 365
            if years_old < 2:
                confidence += 0.05
                factors.append("recent_recommendation")
            elif years_old < 5:
                confidence += 0.02
                factors.append("moderately_recent")

        # Cap single attestation at 0.70
        confidence = min(0.70, confidence)

        return EmploymentAttestation(
            id=uuid7(),
            employer=target_claimed_employer,
            attestation_type=AttestationType.LINKEDIN_RECOMMENDATION,
            attester_name=recommendation.author_name,
            attester_linkedin_url=recommendation.author_profile_url,
            attester_title_at_time=recommendation.author_title,
            attester_employer_verified=attester_employer_verified,
            attestation_text=recommendation.text,
            relationship_type=relationship,
            date_of_attestation=recommendation.date,
            proves_employment=True,
            proves_dates=bool(mentioned_timeframe),
            proves_title=bool(mentioned_title),
            proves_performance=True,  # Recommendations usually speak to quality
            mentioned_title=mentioned_title,
            mentioned_timeframe=mentioned_timeframe,
            mentioned_projects=mentioned_projects,
            confidence=confidence,
            confidence_factors=factors,
        )

    def _extract_relationship(self, text: str) -> RelationshipType:
        """Extract relationship type from recommendation text."""
        text_lower = text.lower()

        manager_patterns = [
            "i managed", "reported to me", "on my team", "i supervised",
            "worked under my", "i hired", "i mentored"
        ]
        if any(p in text_lower for p in manager_patterns):
            return RelationshipType.MANAGER

        report_patterns = [
            "my manager", "i reported to", "my supervisor", "my boss",
            "managed me", "i worked for"
        ]
        if any(p in text_lower for p in report_patterns):
            return RelationshipType.DIRECT_REPORT

        colleague_patterns = [
            "worked with", "colleague", "worked alongside", "peer",
            "co-worker", "worked together", "teammate"
        ]
        if any(p in text_lower for p in colleague_patterns):
            return RelationshipType.COLLEAGUE

        client_patterns = ["client", "customer", "hired them", "contracted"]
        if any(p in text_lower for p in client_patterns):
            return RelationshipType.CLIENT

        return RelationshipType.UNKNOWN

    def _fuzzy_match_employer(
        self,
        target: str,
        employers: list[str],
        threshold: float = 0.85,
    ) -> bool:
        """Fuzzy match employer name."""
        target_normalized = self._normalize_company_name(target)
        for emp in employers:
            emp_normalized = self._normalize_company_name(emp)
            if target_normalized == emp_normalized:
                return True
            # Use Jaro-Winkler for fuzzy match
            similarity = jaro_winkler_similarity(target_normalized, emp_normalized)
            if similarity >= threshold:
                return True
        return False

    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name for matching."""
        name = name.lower().strip()
        # Remove common suffixes
        suffixes = [
            " inc", " inc.", " llc", " ltd", " ltd.", " corp", " corp.",
            " corporation", " company", " co", " co.", " plc", " lp",
        ]
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        return name.strip()


class AttestationAggregator:
    """Aggregates multiple attestations into overall verification."""

    def aggregate_attestations(
        self,
        claimed_employment: ClaimedEmployment,
        attestations: list[EmploymentAttestation],
    ) -> SynthesizedEmploymentVerification:
        """Combine multiple attestations for overall confidence."""

        # Filter to attestations for this employer
        relevant = [
            a for a in attestations
            if self._matches_employer(a.employer, claimed_employment.employer)
        ]

        if not relevant:
            return SynthesizedEmploymentVerification(
                employer=claimed_employment.employer,
                claimed_title=claimed_employment.title,
                claimed_start_date=claimed_employment.start_date,
                claimed_end_date=claimed_employment.end_date,
                employment_confirmed=False,
                confidence=0.0,
                attestation_count=0,
                flags=["NO_ATTESTATIONS_FOUND"],
            )

        # Start with highest single attestation confidence
        base_confidence = max(a.confidence for a in relevant)

        # Multiple independent attesters increase confidence (diminishing returns)
        unique_attesters = {a.attester_name for a in relevant}
        for i, _ in enumerate(list(unique_attesters)[1:], 1):
            boost = 0.10 / (i + 1)  # 0.05, 0.033, 0.025...
            base_confidence += boost

        # Bonus for diverse attestation types
        attestation_types = {a.attestation_type for a in relevant}
        if len(attestation_types) >= 2:
            base_confidence += 0.05  # Multiple source types

        # Bonus for diverse relationship types
        relationship_types = {
            a.relationship_type for a in relevant
            if a.relationship_type != RelationshipType.UNKNOWN
        }
        if len(relationship_types) >= 2:
            base_confidence += 0.05  # Manager AND colleague

        # Bonus if any attester was manager
        if any(a.relationship_type == RelationshipType.MANAGER for a in relevant):
            base_confidence += 0.05

        # Check what we can confirm
        title_confirmed = any(a.proves_title and a.mentioned_title for a in relevant)
        dates_confirmed = any(a.proves_dates for a in relevant)

        # Bonus for confirming title/dates
        if title_confirmed:
            base_confidence += 0.03
        if dates_confirmed:
            base_confidence += 0.03

        # Hard cap at 0.85
        final_confidence = min(0.85, base_confidence)

        return SynthesizedEmploymentVerification(
            employer=claimed_employment.employer,
            claimed_title=claimed_employment.title,
            claimed_start_date=claimed_employment.start_date,
            claimed_end_date=claimed_employment.end_date,
            employment_confirmed=True,
            title_confirmed=title_confirmed,
            dates_confirmed=dates_confirmed,
            attestation_count=len(relevant),
            unique_attesters=len(unique_attesters),
            attestations=relevant,
            confidence=final_confidence,
            verification_method="peer_attestation",
            source_type=SourceType.LLM_SYNTHESIS,
            fcra_usable=False,
            flags=[
                "SYNTHESIZED_FROM_PUBLIC_SOURCES",
                "PEER_ATTESTATION_BASED",
                "NOT_FOR_ADVERSE_ACTION",
            ] + (["DATES_NOT_VERIFIED"] if not dates_confirmed else [])
              + (["TITLE_NOT_VERIFIED"] if not title_confirmed else []),
        )
```

## Report Output Format

```python
# src/elile/providers/synthesis/report.py

class SynthesisReportFormatter:
    """Formats synthesized verification for reports."""

    def format_employment_verification(
        self,
        verification: SynthesizedEmploymentVerification,
    ) -> str:
        """Format employment verification for report output."""

        status = "PARTIALLY VERIFIED" if verification.employment_confirmed else "UNVERIFIED"
        confidence_pct = f"{verification.confidence:.0%}"

        output = f"""
EMPLOYMENT VERIFICATION (Synthesized)
=====================================

Employer: {verification.employer}
Claimed Title: {verification.claimed_title or "Not specified"}
Claimed Period: {self._format_period(verification)}

VERIFICATION STATUS: {status}
Confidence: {confidence_pct}
Method: {verification.verification_method.replace("_", " ").title()}

"""

        if verification.attestations:
            output += "ATTESTATIONS FOUND:\n"
            output += self._format_attestation_table(verification.attestations)

        output += f"""
WHAT THIS CONFIRMS:
  {"[x]" if verification.employment_confirmed else "[ ]"} Employment at {verification.employer}
  {"[x]" if verification.title_confirmed else "[ ]"} Title: {verification.claimed_title or "N/A"}
  {"[x]" if verification.dates_confirmed else "[ ]"} Employment dates

{self._format_disclaimer()}
"""
        return output

    def _format_attestation_table(
        self,
        attestations: list[EmploymentAttestation],
    ) -> str:
        """Format attestations as a table."""
        lines = []
        for i, att in enumerate(attestations, 1):
            attester_info = att.attester_name
            if att.attester_employer_verified:
                attester_info += f" (verified at {att.employer})"

            relationship = att.relationship_type.value.replace("_", " ").title()

            lines.append(f"""
+{'─' * 60}+
│ {i}. {attester_info}
│    Type: {att.attestation_type.value.replace("_", " ").title()}
│    Relationship: {relationship}
│    Confidence: {att.confidence:.0%}
│    {"✓ Attester verified at same employer" if att.attester_employer_verified else "○ External attester"}
{self._format_factors(att.confidence_factors)}
""")

        lines.append(f"+{'─' * 60}+")
        return "".join(lines)

    def _format_disclaimer(self) -> str:
        """Standard disclaimer for synthesized data."""
        return """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  IMPORTANT NOTICE

This verification is based on peer attestations and publicly
available sources. It has NOT been verified through official
employment records (e.g., The Work Number, direct employer
verification).

Under FCRA guidelines, this information should not be used as
the sole basis for adverse employment decisions. Official
verification is recommended before making hiring decisions.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
```

## Integration with Request Router

```python
# Update to src/elile/providers/router.py

class RequestRouter:
    """Routes requests with LLM synthesis as fallback."""

    async def route_with_fallback(
        self,
        request: RoutedRequest,
    ) -> RoutedResult:
        """Route request, falling back to synthesis if needed."""

        # Try official providers first
        try:
            result = await self.route(request)
            if result.success:
                return result
        except (ProviderUnavailableError, RateLimitExceededError):
            pass

        # Check if synthesis is available for this check type
        if request.check_type in self.synthesis_provider.supported_checks:
            logger.info(
                "Falling back to LLM synthesis",
                check_type=request.check_type,
                reason="official_provider_unavailable",
            )

            synthesis_result = await self.synthesis_provider.execute_check(
                check_type=request.check_type,
                subject=request.subject,
                locale=request.locale,
                degree=request.degree,
            )

            return RoutedResult(
                success=True,
                result=synthesis_result,
                provider_used="llm_synthesis",
                is_fallback=True,
                fallback_reason="official_provider_unavailable",
            )

        # No fallback available
        return RoutedResult(
            success=False,
            error="No provider available and synthesis not supported",
        )
```

## Testing Requirements

### Unit Tests
- Attestation scoring for all factors
- Employer name normalization and matching
- Relationship extraction from text
- Confidence aggregation with multiple attesters
- Confidence caps enforced
- FCRA flags always set

### Integration Tests
- End-to-end synthesis flow
- Multi-LLM consensus calculation
- Fallback routing from official to synthesis
- Source gathering from LinkedIn, news, SEC

### Edge Cases
- No attestations found
- Single attestation (no corroboration)
- Conflicting attestations
- Attester not verified at employer
- Very old recommendations
- Non-English content

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] LLMSynthesisProvider implements DataProvider interface
- [ ] Employment attestation scoring implemented with all factors
- [ ] Multi-LLM consensus validation working
- [ ] Confidence caps enforced (max 0.85 for employment)
- [ ] FCRA flags always present on synthesized data
- [ ] Provenance tracking captures all sources and prompts
- [ ] Integration with RequestRouter as fallback
- [ ] Clear report formatting with disclaimers
- [ ] Unit tests pass with 90%+ coverage
- [ ] Integration tests demonstrate fallback behavior

## Deliverables

- `src/elile/providers/synthesis/__init__.py`
- `src/elile/providers/synthesis/models.py`
- `src/elile/providers/synthesis/provider.py`
- `src/elile/providers/synthesis/employment.py`
- `src/elile/providers/synthesis/education.py`
- `src/elile/providers/synthesis/adverse_media.py`
- `src/elile/providers/synthesis/report.py`
- `src/elile/providers/synthesis/fetchers/linkedin.py`
- `src/elile/providers/synthesis/fetchers/news.py`
- `src/elile/providers/synthesis/fetchers/sec.py`
- `tests/unit/test_synthesis_provider.py`
- `tests/unit/test_attestation_scoring.py`
- `tests/unit/test_attestation_aggregation.py`
- `tests/integration/test_synthesis_fallback.py`

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md)
- Provider Interface: Task 4.1
- Finding Extractor: Task 5.10
- FCRA Compliance: [07-compliance.md](../architecture/07-compliance.md)

---

*Task Owner: [TBD]* | *Created: 2026-02-01*
