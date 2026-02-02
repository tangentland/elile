"""Education verification provider module.

This module provides education credential verification through:
- National Student Clearinghouse (US)
- Direct registrar queries
- International verification services

Key Features:
- Institution name fuzzy matching
- Diploma mill detection
- Accreditation verification
- Enrollment and graduation date verification

Usage:
    from elile.providers.education import (
        EducationProvider,
        create_education_provider,
        get_education_provider,
    )

    # Create a provider
    provider = create_education_provider()

    # Verify education
    result = await provider.verify_education(
        subject_name="John Smith",
        claimed_education=ClaimedEducation(
            institution_name="MIT",
            degree_type=DegreeType.BACHELOR,
            major="Computer Science",
            graduation_date=date(2020, 5, 15),
        ),
    )

    if result.status == VerificationStatus.VERIFIED:
        print("Education verified!")
"""

from .diploma_mill import (
    DiplomaMilDetector,
    create_diploma_mill_detector,
    is_diploma_mill,
)
from .matcher import (
    DegreeTypeMatcher,
    InstitutionMatcher,
    create_institution_matcher,
)
from .provider import (
    EducationProvider,
    create_education_provider,
    get_education_provider,
)
from .types import (
    AccreditationType,
    ClaimedEducation,
    DegreeType,
    DiplomaMilDetectedError,
    EducationDiscrepancy,
    EducationProviderConfig,
    EducationProviderError,
    EducationVerificationResult,
    Institution,
    InstitutionMatchResult,
    InstitutionNotFoundError,
    InstitutionType,
    MatchConfidence,
    VerificationFailedError,
    VerificationStatus,
    VerifiedEducation,
)

__all__ = [
    # Provider
    "EducationProvider",
    "create_education_provider",
    "get_education_provider",
    # Types
    "AccreditationType",
    "ClaimedEducation",
    "DegreeType",
    "EducationDiscrepancy",
    "EducationProviderConfig",
    "EducationVerificationResult",
    "Institution",
    "InstitutionMatchResult",
    "InstitutionType",
    "MatchConfidence",
    "VerificationStatus",
    "VerifiedEducation",
    # Matcher
    "InstitutionMatcher",
    "DegreeTypeMatcher",
    "create_institution_matcher",
    # Diploma Mill Detection
    "DiplomaMilDetector",
    "create_diploma_mill_detector",
    "is_diploma_mill",
    # Exceptions
    "EducationProviderError",
    "InstitutionNotFoundError",
    "VerificationFailedError",
    "DiplomaMilDetectedError",
]
