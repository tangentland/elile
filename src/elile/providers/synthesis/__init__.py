"""LLM Synthesis Provider module.

This module provides a fallback data provider that uses LLM models to
synthesize verification information from publicly available sources.

Example:
    from elile.providers.synthesis import (
        LLMSynthesisProvider,
        get_synthesis_provider,
        LLMSynthesisProviderConfig,
    )

    # Get the singleton provider
    provider = get_synthesis_provider()

    # Or create with custom config
    config = LLMSynthesisProviderConfig(
        primary_model=SynthesisLLMModel.CLAUDE_SONNET,
        require_consensus=True,
    )
    provider = LLMSynthesisProvider(config)

    # Execute a check
    result = await provider.execute_check(
        check_type=CheckType.EMPLOYMENT_VERIFICATION,
        subject=SubjectIdentifiers(full_name="John Smith"),
        locale=Locale.US,
        options={"claimed_employers": [{"employer": "Acme Corp"}]},
    )
"""

from .provider import (
    SUPPORTED_CHECK_TYPES,
    AttestationScorer,
    ClaimedEducation,
    ClaimedEmployment,
    EducationAttestationAggregator,
    EmploymentAttestationAggregator,
    LLMSynthesisProvider,
    create_synthesis_provider,
    get_synthesis_provider,
)
from .types import (
    AttestationType,
    ConfidenceFactor,
    ConsensusFailedError,
    EducationAttestation,
    EmploymentAttestation,
    LinkedInEducation,
    LinkedInExperience,
    LinkedInProfile,
    LinkedInRecommendation,
    LLMExtractionError,
    LLMSynthesisProviderConfig,
    NewsArticle,
    PublicSource,
    PublicSourceType,
    RelationshipType,
    SECFiling,
    SourceFetchError,
    SourceType,
    SynthesisLLMModel,
    SynthesisProvenance,
    SynthesisProviderError,
    SynthesizedAdverseMedia,
    SynthesizedCorporateAffiliation,
    SynthesizedCorporateAffiliations,
    SynthesizedEducationVerification,
    SynthesizedEmploymentVerification,
    SynthesizedLicenseVerification,
    SynthesizedSocialMedia,
    UnsupportedCheckTypeError,
)

__all__ = [
    # Provider
    "LLMSynthesisProvider",
    "create_synthesis_provider",
    "get_synthesis_provider",
    "SUPPORTED_CHECK_TYPES",
    # Config
    "LLMSynthesisProviderConfig",
    "SynthesisLLMModel",
    # Enums
    "SourceType",
    "AttestationType",
    "RelationshipType",
    "ConfidenceFactor",
    "PublicSourceType",
    # Public Source Models
    "PublicSource",
    "LinkedInProfile",
    "LinkedInExperience",
    "LinkedInEducation",
    "LinkedInRecommendation",
    "NewsArticle",
    "SECFiling",
    # Attestation Models
    "EmploymentAttestation",
    "EducationAttestation",
    # Synthesized Results
    "SynthesisProvenance",
    "SynthesizedEmploymentVerification",
    "SynthesizedEducationVerification",
    "SynthesizedAdverseMedia",
    "SynthesizedLicenseVerification",
    "SynthesizedSocialMedia",
    "SynthesizedCorporateAffiliation",
    "SynthesizedCorporateAffiliations",
    # Scoring and Aggregation
    "AttestationScorer",
    "EmploymentAttestationAggregator",
    "EducationAttestationAggregator",
    "ClaimedEmployment",
    "ClaimedEducation",
    # Exceptions
    "SynthesisProviderError",
    "UnsupportedCheckTypeError",
    "SourceFetchError",
    "LLMExtractionError",
    "ConsensusFailedError",
]
