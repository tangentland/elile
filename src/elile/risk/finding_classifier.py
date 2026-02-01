"""Finding Classifier for categorizing findings into risk categories.

This module provides the FindingClassifier that:
1. Categorizes findings into risk categories (criminal, financial, regulatory, etc.)
2. Validates AI-assigned categories
3. Calculates role-specific relevance
4. Assigns sub-categories for granular analysis
5. Tracks classification confidence
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.compliance.types import RoleCategory
from elile.core.logging import get_logger
from elile.investigation.finding_extractor import Finding, FindingCategory, Severity

logger = get_logger(__name__)


class SubCategory(str, Enum):
    """Sub-categories for detailed classification."""

    # Criminal sub-categories
    CRIMINAL_FELONY = "criminal_felony"
    CRIMINAL_MISDEMEANOR = "criminal_misdemeanor"
    CRIMINAL_TRAFFIC = "criminal_traffic"
    CRIMINAL_DUI = "criminal_dui"
    CRIMINAL_VIOLENT = "criminal_violent"
    CRIMINAL_FINANCIAL = "criminal_financial"
    CRIMINAL_DRUG = "criminal_drug"
    CRIMINAL_SEX = "criminal_sex"

    # Financial sub-categories
    FINANCIAL_BANKRUPTCY = "financial_bankruptcy"
    FINANCIAL_LIEN = "financial_lien"
    FINANCIAL_JUDGMENT = "financial_judgment"
    FINANCIAL_FORECLOSURE = "financial_foreclosure"
    FINANCIAL_COLLECTION = "financial_collection"
    FINANCIAL_CREDIT = "financial_credit"

    # Regulatory sub-categories
    REGULATORY_LICENSE = "regulatory_license"
    REGULATORY_SANCTION = "regulatory_sanction"
    REGULATORY_ENFORCEMENT = "regulatory_enforcement"
    REGULATORY_BAR = "regulatory_bar"
    REGULATORY_PEP = "regulatory_pep"

    # Reputation sub-categories
    REPUTATION_LITIGATION = "reputation_litigation"
    REPUTATION_MEDIA = "reputation_media"
    REPUTATION_COMPLAINT = "reputation_complaint"
    REPUTATION_SOCIAL = "reputation_social"

    # Verification sub-categories
    VERIFICATION_IDENTITY = "verification_identity"
    VERIFICATION_EMPLOYMENT = "verification_employment"
    VERIFICATION_EDUCATION = "verification_education"
    VERIFICATION_DISCREPANCY = "verification_discrepancy"
    VERIFICATION_GAP = "verification_gap"

    # Behavioral sub-categories
    BEHAVIORAL_PATTERN = "behavioral_pattern"
    BEHAVIORAL_DECEPTION = "behavioral_deception"

    # Network sub-categories
    NETWORK_ASSOCIATION = "network_association"
    NETWORK_SHELL = "network_shell"
    NETWORK_PEP = "network_pep"

    # Default
    UNCLASSIFIED = "unclassified"


# Category keyword mappings for classification
CATEGORY_KEYWORDS: dict[FindingCategory, list[str]] = {
    FindingCategory.CRIMINAL: [
        "arrest",
        "conviction",
        "felony",
        "misdemeanor",
        "charge",
        "criminal",
        "offense",
        "violation",
        "incarceration",
        "probation",
        "parole",
        "indictment",
        "plea",
        "sentence",
        "dui",
        "dwi",
        "assault",
        "theft",
        "fraud",
        "burglary",
        "drug",
    ],
    FindingCategory.FINANCIAL: [
        "bankruptcy",
        "lien",
        "judgment",
        "debt",
        "foreclosure",
        "garnishment",
        "default",
        "collection",
        "delinquent",
        "credit",
        "insolvency",
        "chapter 7",
        "chapter 11",
        "chapter 13",
        "tax lien",
        "civil judgment",
    ],
    FindingCategory.REGULATORY: [
        "license",
        "sanction",
        "enforcement",
        "suspension",
        "revocation",
        "bar",
        "restriction",
        "debarment",
        "watchlist",
        "ofac",
        "pep",
        "politically exposed",
        "compliance violation",
        "sec action",
        "finra",
    ],
    FindingCategory.REPUTATION: [
        "litigation",
        "lawsuit",
        "complaint",
        "allegation",
        "adverse media",
        "controversy",
        "scandal",
        "news",
        "article",
        "investigation",
        "civil suit",
        "defendant",
        "plaintiff",
    ],
    FindingCategory.VERIFICATION: [
        "discrepancy",
        "gap",
        "inconsistency",
        "mismatch",
        "unverified",
        "false",
        "misleading",
        "fabricated",
        "inflated",
        "cannot verify",
        "employment gap",
        "education discrepancy",
    ],
    FindingCategory.BEHAVIORAL: [
        "pattern",
        "trend",
        "recurring",
        "systematic",
        "deception",
        "fabrication",
        "misrepresentation",
    ],
    FindingCategory.NETWORK: [
        "associate",
        "connection",
        "relationship",
        "shell company",
        "affiliated",
        "linked",
        "related entity",
        "beneficial owner",
    ],
}

# Sub-category keyword mappings
SUBCATEGORY_KEYWORDS: dict[SubCategory, list[str]] = {
    # Criminal
    SubCategory.CRIMINAL_FELONY: ["felony", "felonious"],
    SubCategory.CRIMINAL_MISDEMEANOR: ["misdemeanor"],
    SubCategory.CRIMINAL_TRAFFIC: ["traffic", "speeding", "reckless driving"],
    SubCategory.CRIMINAL_DUI: ["dui", "dwi", "driving under", "intoxicated"],
    SubCategory.CRIMINAL_VIOLENT: ["assault", "battery", "violence", "murder", "manslaughter"],
    SubCategory.CRIMINAL_FINANCIAL: ["fraud", "embezzlement", "forgery", "money laundering"],
    SubCategory.CRIMINAL_DRUG: ["drug", "narcotic", "controlled substance", "possession"],
    SubCategory.CRIMINAL_SEX: ["sexual", "sex offense", "indecent"],
    # Financial
    SubCategory.FINANCIAL_BANKRUPTCY: ["bankruptcy", "chapter 7", "chapter 11", "chapter 13"],
    SubCategory.FINANCIAL_LIEN: ["lien", "tax lien"],
    SubCategory.FINANCIAL_JUDGMENT: ["judgment", "civil judgment"],
    SubCategory.FINANCIAL_FORECLOSURE: ["foreclosure", "foreclosed"],
    SubCategory.FINANCIAL_COLLECTION: ["collection", "collections"],
    SubCategory.FINANCIAL_CREDIT: ["credit", "credit score", "credit report"],
    # Regulatory
    SubCategory.REGULATORY_LICENSE: ["license", "licensing", "licensure"],
    SubCategory.REGULATORY_SANCTION: ["sanction", "sanctioned", "watchlist", "ofac"],
    SubCategory.REGULATORY_ENFORCEMENT: ["enforcement", "sec action", "finra"],
    SubCategory.REGULATORY_BAR: ["bar", "barred", "debarment", "debarred"],
    SubCategory.REGULATORY_PEP: ["pep", "politically exposed", "public official"],
    # Reputation
    SubCategory.REPUTATION_LITIGATION: ["litigation", "lawsuit", "civil suit"],
    SubCategory.REPUTATION_MEDIA: ["media", "news", "article", "press"],
    SubCategory.REPUTATION_COMPLAINT: ["complaint", "allegation", "accusation"],
    SubCategory.REPUTATION_SOCIAL: ["social media", "online", "post"],
    # Verification
    SubCategory.VERIFICATION_IDENTITY: ["identity", "ssn", "name mismatch"],
    SubCategory.VERIFICATION_EMPLOYMENT: ["employment", "employer", "job title"],
    SubCategory.VERIFICATION_EDUCATION: ["education", "degree", "school", "university"],
    SubCategory.VERIFICATION_DISCREPANCY: ["discrepancy", "inconsistency", "mismatch"],
    SubCategory.VERIFICATION_GAP: ["gap", "unexplained period"],
    # Behavioral
    SubCategory.BEHAVIORAL_PATTERN: ["pattern", "trend", "recurring"],
    SubCategory.BEHAVIORAL_DECEPTION: ["deception", "fabrication", "misrepresentation"],
    # Network
    SubCategory.NETWORK_ASSOCIATION: ["associate", "connection", "relationship"],
    SubCategory.NETWORK_SHELL: ["shell company", "shell corporation", "nominee"],
    SubCategory.NETWORK_PEP: ["pep connection", "political connection"],
}

# Role-category relevance matrix (category, role) -> relevance score
ROLE_RELEVANCE_MATRIX: dict[tuple[FindingCategory, RoleCategory], float] = {
    # Criminal findings relevance
    (FindingCategory.CRIMINAL, RoleCategory.GOVERNMENT): 1.0,
    (FindingCategory.CRIMINAL, RoleCategory.SECURITY): 1.0,
    (FindingCategory.CRIMINAL, RoleCategory.FINANCIAL): 0.9,
    (FindingCategory.CRIMINAL, RoleCategory.HEALTHCARE): 0.85,
    (FindingCategory.CRIMINAL, RoleCategory.EXECUTIVE): 0.85,
    (FindingCategory.CRIMINAL, RoleCategory.EDUCATION): 0.9,
    (FindingCategory.CRIMINAL, RoleCategory.TRANSPORTATION): 0.85,
    (FindingCategory.CRIMINAL, RoleCategory.STANDARD): 0.7,
    (FindingCategory.CRIMINAL, RoleCategory.CONTRACTOR): 0.75,
    # Financial findings relevance
    (FindingCategory.FINANCIAL, RoleCategory.FINANCIAL): 1.0,
    (FindingCategory.FINANCIAL, RoleCategory.EXECUTIVE): 0.9,
    (FindingCategory.FINANCIAL, RoleCategory.GOVERNMENT): 0.8,
    (FindingCategory.FINANCIAL, RoleCategory.SECURITY): 0.75,
    (FindingCategory.FINANCIAL, RoleCategory.HEALTHCARE): 0.65,
    (FindingCategory.FINANCIAL, RoleCategory.EDUCATION): 0.6,
    (FindingCategory.FINANCIAL, RoleCategory.TRANSPORTATION): 0.6,
    (FindingCategory.FINANCIAL, RoleCategory.STANDARD): 0.5,
    (FindingCategory.FINANCIAL, RoleCategory.CONTRACTOR): 0.6,
    # Regulatory findings relevance
    (FindingCategory.REGULATORY, RoleCategory.FINANCIAL): 1.0,
    (FindingCategory.REGULATORY, RoleCategory.HEALTHCARE): 1.0,
    (FindingCategory.REGULATORY, RoleCategory.GOVERNMENT): 0.95,
    (FindingCategory.REGULATORY, RoleCategory.SECURITY): 0.9,
    (FindingCategory.REGULATORY, RoleCategory.EXECUTIVE): 0.85,
    (FindingCategory.REGULATORY, RoleCategory.TRANSPORTATION): 0.9,
    (FindingCategory.REGULATORY, RoleCategory.EDUCATION): 0.8,
    (FindingCategory.REGULATORY, RoleCategory.STANDARD): 0.5,
    (FindingCategory.REGULATORY, RoleCategory.CONTRACTOR): 0.7,
    # Reputation findings relevance
    (FindingCategory.REPUTATION, RoleCategory.EXECUTIVE): 1.0,
    (FindingCategory.REPUTATION, RoleCategory.GOVERNMENT): 0.9,
    (FindingCategory.REPUTATION, RoleCategory.FINANCIAL): 0.85,
    (FindingCategory.REPUTATION, RoleCategory.SECURITY): 0.8,
    (FindingCategory.REPUTATION, RoleCategory.HEALTHCARE): 0.75,
    (FindingCategory.REPUTATION, RoleCategory.EDUCATION): 0.7,
    (FindingCategory.REPUTATION, RoleCategory.TRANSPORTATION): 0.6,
    (FindingCategory.REPUTATION, RoleCategory.STANDARD): 0.5,
    (FindingCategory.REPUTATION, RoleCategory.CONTRACTOR): 0.4,
    # Verification findings relevance (high for all roles)
    (FindingCategory.VERIFICATION, RoleCategory.GOVERNMENT): 1.0,
    (FindingCategory.VERIFICATION, RoleCategory.SECURITY): 1.0,
    (FindingCategory.VERIFICATION, RoleCategory.FINANCIAL): 1.0,
    (FindingCategory.VERIFICATION, RoleCategory.EXECUTIVE): 1.0,
    (FindingCategory.VERIFICATION, RoleCategory.HEALTHCARE): 0.95,
    (FindingCategory.VERIFICATION, RoleCategory.EDUCATION): 0.95,
    (FindingCategory.VERIFICATION, RoleCategory.TRANSPORTATION): 0.9,
    (FindingCategory.VERIFICATION, RoleCategory.STANDARD): 0.8,
    (FindingCategory.VERIFICATION, RoleCategory.CONTRACTOR): 0.85,
    # Behavioral findings relevance
    (FindingCategory.BEHAVIORAL, RoleCategory.GOVERNMENT): 1.0,
    (FindingCategory.BEHAVIORAL, RoleCategory.SECURITY): 1.0,
    (FindingCategory.BEHAVIORAL, RoleCategory.FINANCIAL): 0.9,
    (FindingCategory.BEHAVIORAL, RoleCategory.EXECUTIVE): 0.9,
    (FindingCategory.BEHAVIORAL, RoleCategory.HEALTHCARE): 0.85,
    (FindingCategory.BEHAVIORAL, RoleCategory.EDUCATION): 0.85,
    (FindingCategory.BEHAVIORAL, RoleCategory.TRANSPORTATION): 0.8,
    (FindingCategory.BEHAVIORAL, RoleCategory.STANDARD): 0.7,
    (FindingCategory.BEHAVIORAL, RoleCategory.CONTRACTOR): 0.75,
    # Network findings relevance
    (FindingCategory.NETWORK, RoleCategory.GOVERNMENT): 1.0,
    (FindingCategory.NETWORK, RoleCategory.SECURITY): 1.0,
    (FindingCategory.NETWORK, RoleCategory.FINANCIAL): 0.95,
    (FindingCategory.NETWORK, RoleCategory.EXECUTIVE): 0.9,
    (FindingCategory.NETWORK, RoleCategory.HEALTHCARE): 0.75,
    (FindingCategory.NETWORK, RoleCategory.EDUCATION): 0.65,
    (FindingCategory.NETWORK, RoleCategory.TRANSPORTATION): 0.6,
    (FindingCategory.NETWORK, RoleCategory.STANDARD): 0.5,
    (FindingCategory.NETWORK, RoleCategory.CONTRACTOR): 0.6,
}


@dataclass
class ClassificationResult:
    """Result of classifying a finding."""

    classification_id: UUID = field(default_factory=uuid7)
    finding_id: UUID | None = None
    original_category: FindingCategory | None = None
    assigned_category: FindingCategory = FindingCategory.VERIFICATION
    sub_category: SubCategory = SubCategory.UNCLASSIFIED
    category_confidence: float = 0.0
    relevance_to_role: float = 0.0
    keyword_matches: list[str] = field(default_factory=list)
    was_reclassified: bool = False
    classified_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "classification_id": str(self.classification_id),
            "finding_id": str(self.finding_id) if self.finding_id else None,
            "original_category": self.original_category.value
            if self.original_category
            else None,
            "assigned_category": self.assigned_category.value,
            "sub_category": self.sub_category.value,
            "category_confidence": self.category_confidence,
            "relevance_to_role": self.relevance_to_role,
            "keyword_matches": self.keyword_matches,
            "was_reclassified": self.was_reclassified,
            "classified_at": self.classified_at.isoformat(),
        }


class ClassifierConfig(BaseModel):
    """Configuration for finding classifier."""

    # Validation thresholds
    min_validation_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Min confidence to keep AI-assigned category",
    )
    min_keyword_matches: int = Field(
        default=1, ge=1, description="Min keyword matches for category assignment"
    )

    # Confidence calculation
    confidence_per_match: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Confidence boost per keyword match",
    )
    max_keyword_confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Maximum confidence from keywords alone",
    )

    # Sub-category settings
    enable_subcategory: bool = Field(
        default=True, description="Enable sub-category classification"
    )

    # Default relevance
    default_relevance: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Default role relevance"
    )


class FindingClassifier:
    """Classifies findings into risk categories with role-based relevance.

    The FindingClassifier:
    1. Validates AI-assigned categories against keyword rules
    2. Reclassifies findings when AI confidence is low
    3. Assigns sub-categories for granular analysis
    4. Calculates role-specific relevance scores

    Example:
        ```python
        classifier = FindingClassifier()

        # Classify a single finding
        result = classifier.classify_finding(
            finding=finding,
            role_category=RoleCategory.FINANCIAL,
        )
        print(f"Category: {result.assigned_category}")
        print(f"Relevance: {result.relevance_to_role}")

        # Classify multiple findings
        results = classifier.classify_findings(
            findings=findings,
            role_category=RoleCategory.EXECUTIVE,
        )
        ```
    """

    def __init__(self, config: ClassifierConfig | None = None):
        """Initialize the finding classifier.

        Args:
            config: Classifier configuration.
        """
        self.config = config or ClassifierConfig()

    def classify_finding(
        self,
        finding: Finding,
        role_category: RoleCategory,
        update_finding: bool = True,
    ) -> ClassificationResult:
        """Classify a single finding.

        Args:
            finding: Finding to classify.
            role_category: Role for relevance calculation.
            update_finding: Whether to update the finding object.

        Returns:
            ClassificationResult with category and relevance.
        """
        result = ClassificationResult(
            finding_id=finding.finding_id,
            original_category=finding.category,
        )

        # Get text for classification
        text = self._get_finding_text(finding)

        # If already classified by AI, validate
        if finding.category:
            validation_confidence = self._validate_category(finding.category, text)
            result.category_confidence = validation_confidence

            if validation_confidence >= self.config.min_validation_confidence:
                # Keep AI-assigned category
                result.assigned_category = finding.category
                result.keyword_matches = self._get_keyword_matches(
                    finding.category, text
                )
            else:
                # Reclassify
                category, confidence, matches = self._determine_category(text)
                result.assigned_category = category
                result.category_confidence = confidence
                result.keyword_matches = matches
                result.was_reclassified = True
        else:
            # Classify from scratch
            category, confidence, matches = self._determine_category(text)
            result.assigned_category = category
            result.category_confidence = confidence
            result.keyword_matches = matches

        # Assign sub-category
        if self.config.enable_subcategory:
            result.sub_category = self._determine_subcategory(
                result.assigned_category, text
            )

        # Calculate role relevance
        result.relevance_to_role = self._calculate_relevance(
            result.assigned_category, role_category
        )

        # Update finding if requested
        if update_finding:
            finding.category = result.assigned_category
            finding.relevance_to_role = result.relevance_to_role

        logger.debug(
            "Finding classified",
            finding_id=str(finding.finding_id),
            category=result.assigned_category.value,
            sub_category=result.sub_category.value,
            confidence=result.category_confidence,
            relevance=result.relevance_to_role,
            reclassified=result.was_reclassified,
        )

        return result

    def classify_findings(
        self,
        findings: list[Finding],
        role_category: RoleCategory,
        update_findings: bool = True,
    ) -> list[ClassificationResult]:
        """Classify multiple findings.

        Args:
            findings: Findings to classify.
            role_category: Role for relevance calculation.
            update_findings: Whether to update finding objects.

        Returns:
            List of ClassificationResult.
        """
        results = []
        for finding in findings:
            result = self.classify_finding(
                finding=finding,
                role_category=role_category,
                update_finding=update_findings,
            )
            results.append(result)

        logger.info(
            "Findings classified",
            total=len(findings),
            reclassified=sum(1 for r in results if r.was_reclassified),
        )

        return results

    def get_category_distribution(
        self, results: list[ClassificationResult]
    ) -> dict[FindingCategory, int]:
        """Get distribution of findings by category.

        Args:
            results: Classification results.

        Returns:
            Count per category.
        """
        distribution: dict[FindingCategory, int] = {}
        for result in results:
            category = result.assigned_category
            distribution[category] = distribution.get(category, 0) + 1
        return distribution

    def get_subcategory_distribution(
        self, results: list[ClassificationResult]
    ) -> dict[SubCategory, int]:
        """Get distribution of findings by sub-category.

        Args:
            results: Classification results.

        Returns:
            Count per sub-category.
        """
        distribution: dict[SubCategory, int] = {}
        for result in results:
            sub = result.sub_category
            distribution[sub] = distribution.get(sub, 0) + 1
        return distribution

    def _get_finding_text(self, finding: Finding) -> str:
        """Get text content from finding for classification."""
        parts = [finding.summary or "", finding.details or "", finding.finding_type or ""]
        return " ".join(parts).lower()

    def _validate_category(self, category: FindingCategory, text: str) -> float:
        """Validate AI-assigned category against keywords.

        Args:
            category: Category to validate.
            text: Finding text content.

        Returns:
            Validation confidence (0.0-1.0).
        """
        keywords = CATEGORY_KEYWORDS.get(category, [])
        if not keywords:
            return 0.5  # No keywords to validate against

        matches = sum(1 for kw in keywords if kw.lower() in text)

        # Calculate confidence: 3+ matches = high confidence
        confidence = min(
            matches * self.config.confidence_per_match,
            self.config.max_keyword_confidence,
        )
        return confidence

    def _determine_category(
        self, text: str
    ) -> tuple[FindingCategory, float, list[str]]:
        """Determine category from text content.

        Args:
            text: Finding text content.

        Returns:
            Tuple of (category, confidence, matched keywords).
        """
        scores: dict[FindingCategory, tuple[float, list[str]]] = {}

        for category, keywords in CATEGORY_KEYWORDS.items():
            matches = [kw for kw in keywords if kw.lower() in text]
            if matches:
                confidence = min(
                    len(matches) * self.config.confidence_per_match,
                    self.config.max_keyword_confidence,
                )
                scores[category] = (confidence, matches)

        if not scores:
            # Default to VERIFICATION with low confidence
            return FindingCategory.VERIFICATION, 0.3, []

        # Get highest scoring category
        best_category = max(scores, key=lambda c: scores[c][0])
        confidence, matches = scores[best_category]

        return best_category, confidence, matches

    def _determine_subcategory(
        self, category: FindingCategory, text: str
    ) -> SubCategory:
        """Determine sub-category based on category and text.

        Args:
            category: Parent category.
            text: Finding text content.

        Returns:
            Sub-category.
        """
        # Filter sub-categories by parent category prefix
        category_prefix = category.value.lower()

        best_subcategory = SubCategory.UNCLASSIFIED
        best_matches = 0

        for subcategory, keywords in SUBCATEGORY_KEYWORDS.items():
            # Check if sub-category belongs to this category
            if not subcategory.value.startswith(category_prefix):
                continue

            matches = sum(1 for kw in keywords if kw.lower() in text)
            if matches > best_matches:
                best_matches = matches
                best_subcategory = subcategory

        return best_subcategory

    def _calculate_relevance(
        self, category: FindingCategory, role: RoleCategory
    ) -> float:
        """Calculate role-specific relevance for a category.

        Args:
            category: Finding category.
            role: Role category.

        Returns:
            Relevance score (0.0-1.0).
        """
        return ROLE_RELEVANCE_MATRIX.get(
            (category, role), self.config.default_relevance
        )

    def _get_keyword_matches(
        self, category: FindingCategory, text: str
    ) -> list[str]:
        """Get list of matched keywords for a category.

        Args:
            category: Category to check.
            text: Text to search.

        Returns:
            List of matched keywords.
        """
        keywords = CATEGORY_KEYWORDS.get(category, [])
        return [kw for kw in keywords if kw.lower() in text]


def create_finding_classifier(
    config: ClassifierConfig | None = None,
) -> FindingClassifier:
    """Create a finding classifier.

    Args:
        config: Optional classifier configuration.

    Returns:
        Configured FindingClassifier.
    """
    return FindingClassifier(config=config)
