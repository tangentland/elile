"""Institution and degree name matching for education verification.

This module provides fuzzy matching algorithms for institution names,
handling abbreviations, alternative names, and common variations.
"""

import re
from difflib import SequenceMatcher

from .types import (
    Institution,
    InstitutionMatchResult,
    MatchConfidence,
)


class InstitutionMatcher:
    """Fuzzy matcher for educational institution names.

    Uses multiple matching strategies:
    - Exact matching
    - Normalized matching (case-insensitive, punctuation removed)
    - Token-based matching
    - Abbreviation expansion
    - Alias matching

    Usage:
        matcher = InstitutionMatcher()
        results = matcher.find_matches("MIT", institutions)
        best_match = results[0] if results else None
    """

    # Common abbreviations and their expansions
    ABBREVIATIONS: dict[str, list[str]] = {
        "U": ["University"],
        "Univ": ["University"],
        "Univ.": ["University"],
        "Col": ["College"],
        "Col.": ["College"],
        "Inst": ["Institute"],
        "Inst.": ["Institute"],
        "Tech": ["Technology", "Technical"],
        "Tech.": ["Technology", "Technical"],
        "Poly": ["Polytechnic"],
        "St": ["State", "Saint"],
        "St.": ["State", "Saint"],
        "N": ["North", "Northern"],
        "S": ["South", "Southern"],
        "E": ["East", "Eastern"],
        "W": ["West", "Western"],
        "CC": ["Community College"],
        "JC": ["Junior College"],
        "&": ["and"],
    }

    # Common suffixes to normalize
    SUFFIXES_TO_REMOVE = [
        "inc",
        "inc.",
        "llc",
        "llc.",
        "corp",
        "corp.",
        "corporation",
    ]

    def __init__(
        self,
        exact_threshold: float = 0.99,
        high_threshold: float = 0.85,
        medium_threshold: float = 0.70,
        low_threshold: float = 0.55,
    ) -> None:
        """Initialize the matcher with configurable thresholds.

        Args:
            exact_threshold: Score for exact match confidence.
            high_threshold: Score for high confidence.
            medium_threshold: Score for medium confidence.
            low_threshold: Score for low confidence (minimum to report).
        """
        self.exact_threshold = exact_threshold
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self.low_threshold = low_threshold

    def normalize_name(self, name: str) -> str:
        """Normalize an institution name for comparison.

        - Convert to lowercase
        - Remove punctuation
        - Remove common suffixes
        - Normalize whitespace

        Args:
            name: Raw institution name.

        Returns:
            Normalized name string.
        """
        # Convert to lowercase
        normalized = name.lower()

        # Remove common suffixes
        for suffix in self.SUFFIXES_TO_REMOVE:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)].strip()

        # Remove punctuation except apostrophes (for names like "St. John's")
        normalized = re.sub(r"[^\w\s']", " ", normalized)

        # Normalize whitespace
        normalized = " ".join(normalized.split())

        return normalized

    def expand_abbreviations(self, name: str) -> list[str]:
        """Expand known abbreviations to generate variants.

        Args:
            name: Institution name potentially containing abbreviations.

        Returns:
            List of name variants with abbreviations expanded.
        """
        variants = [name]
        tokens = name.split()

        for abbrev, expansions in self.ABBREVIATIONS.items():
            for i, token in enumerate(tokens):
                if token.lower() == abbrev.lower():
                    for expansion in expansions:
                        new_tokens = tokens.copy()
                        new_tokens[i] = expansion
                        variants.append(" ".join(new_tokens))

        return variants

    def calculate_score(self, query: str, target: str) -> tuple[float, list[str]]:
        """Calculate match score between query and target names.

        Uses multiple matching strategies and returns the best score.

        Args:
            query: The search query (claimed institution name).
            target: The target to match against.

        Returns:
            Tuple of (score, list of reasons for the match).
        """
        reasons: list[str] = []

        # Normalize both names
        query_norm = self.normalize_name(query)
        target_norm = self.normalize_name(target)

        # Exact match after normalization
        if query_norm == target_norm:
            return 1.0, ["Exact normalized match"]

        # Sequence matching score
        sequence_score = SequenceMatcher(None, query_norm, target_norm).ratio()

        # Token-based matching
        query_tokens = set(query_norm.split())
        target_tokens = set(target_norm.split())
        if query_tokens and target_tokens:
            common = query_tokens & target_tokens
            token_score = len(common) / max(len(query_tokens), len(target_tokens))
        else:
            token_score = 0.0

        # Check abbreviation expansions
        abbreviation_bonus = 0.0
        query_variants = self.expand_abbreviations(query)
        for variant in query_variants:
            variant_norm = self.normalize_name(variant)
            if variant_norm == target_norm:
                abbreviation_bonus = 0.15
                reasons.append("Abbreviation expansion match")
                break
            variant_score = SequenceMatcher(None, variant_norm, target_norm).ratio()
            if variant_score > sequence_score:
                abbreviation_bonus = 0.1
                reasons.append("Abbreviation expansion partial match")

        # Combine scores
        base_score = max(sequence_score, token_score)
        final_score = min(1.0, base_score + abbreviation_bonus)

        # Build reasons
        if sequence_score > 0.8:
            reasons.append(f"High sequence similarity ({sequence_score:.2f})")
        if token_score > 0.6:
            reasons.append(f"Common tokens ({token_score:.2f})")

        return final_score, reasons

    def score_to_confidence(self, score: float) -> MatchConfidence:
        """Convert a match score to confidence level.

        Args:
            score: Match score between 0.0 and 1.0.

        Returns:
            MatchConfidence level.
        """
        if score >= self.exact_threshold:
            return MatchConfidence.EXACT
        elif score >= self.high_threshold:
            return MatchConfidence.HIGH
        elif score >= self.medium_threshold:
            return MatchConfidence.MEDIUM
        elif score >= self.low_threshold:
            return MatchConfidence.LOW
        return MatchConfidence.NO_MATCH

    def find_matches(
        self,
        query: str,
        institutions: list[Institution],
        *,
        max_results: int = 5,
    ) -> list[InstitutionMatchResult]:
        """Find institutions matching a query name.

        Args:
            query: The institution name to search for.
            institutions: List of institutions to search.
            max_results: Maximum number of results to return.

        Returns:
            List of InstitutionMatchResult sorted by score (highest first).
        """
        results: list[InstitutionMatchResult] = []

        for institution in institutions:
            # Check primary name
            best_score, best_reasons = self.calculate_score(query, institution.name)

            # Check aliases
            for alias in institution.aliases:
                alias_score, alias_reasons = self.calculate_score(query, alias)
                if alias_score > best_score:
                    best_score = alias_score
                    best_reasons = alias_reasons + [f"Matched alias: {alias}"]

            # Only include if meets minimum threshold
            confidence = self.score_to_confidence(best_score)
            if confidence != MatchConfidence.NO_MATCH:
                results.append(
                    InstitutionMatchResult(
                        institution=institution,
                        confidence=confidence,
                        score=best_score,
                        match_reasons=best_reasons,
                    )
                )

        # Sort by score (highest first) and limit results
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]

    def match_single(
        self,
        query: str,
        institutions: list[Institution],
    ) -> InstitutionMatchResult | None:
        """Find the best matching institution for a query.

        Args:
            query: The institution name to search for.
            institutions: List of institutions to search.

        Returns:
            Best matching InstitutionMatchResult or None if no match.
        """
        matches = self.find_matches(query, institutions, max_results=1)
        return matches[0] if matches else None


class DegreeTypeMatcher:
    """Matcher for degree types and titles."""

    # Common degree title patterns
    BACHELOR_PATTERNS = [
        r"\bb\.?s\.?\b",  # B.S., BS
        r"\bb\.?a\.?\b",  # B.A., BA
        r"\bb\.?f\.?a\.?\b",  # B.F.A., BFA
        r"\bbachelor",
        r"\bbs\b",
        r"\bba\b",
    ]

    MASTER_PATTERNS = [
        r"\bm\.?s\.?\b",  # M.S., MS
        r"\bm\.?a\.?\b",  # M.A., MA
        r"\bm\.?b\.?a\.?\b",  # M.B.A., MBA
        r"\bm\.?f\.?a\.?\b",  # M.F.A., MFA
        r"\bmaster",
    ]

    DOCTORATE_PATTERNS = [
        r"\bph\.?d\.?\b",  # Ph.D., PhD
        r"\bed\.?d\.?\b",  # Ed.D., EdD
        r"\bdoctor",
        r"\bdoctorate",
    ]

    PROFESSIONAL_PATTERNS = [
        r"\bm\.?d\.?\b",  # M.D., MD (medical)
        r"\bj\.?d\.?\b",  # J.D., JD (law)
        r"\bd\.?d\.?s\.?\b",  # D.D.S., DDS (dental)
        r"\bd\.?o\.?\b",  # D.O., DO (osteopathic)
    ]

    ASSOCIATE_PATTERNS = [
        r"\ba\.?s\.?\b",  # A.S., AS
        r"\ba\.?a\.?\b",  # A.A., AA
        r"\bassociate",
    ]

    @classmethod
    def infer_degree_type(cls, degree_title: str) -> str:
        """Infer degree type from a degree title string.

        Args:
            degree_title: The degree title (e.g., "Bachelor of Science").

        Returns:
            Inferred degree type string.
        """
        title_lower = degree_title.lower()

        # Check patterns in order of specificity
        for pattern in cls.PROFESSIONAL_PATTERNS:
            if re.search(pattern, title_lower, re.IGNORECASE):
                return "professional"

        for pattern in cls.DOCTORATE_PATTERNS:
            if re.search(pattern, title_lower, re.IGNORECASE):
                return "doctorate"

        for pattern in cls.MASTER_PATTERNS:
            if re.search(pattern, title_lower, re.IGNORECASE):
                return "master"

        for pattern in cls.BACHELOR_PATTERNS:
            if re.search(pattern, title_lower, re.IGNORECASE):
                return "bachelor"

        for pattern in cls.ASSOCIATE_PATTERNS:
            if re.search(pattern, title_lower, re.IGNORECASE):
                return "associate"

        # Check for certificate/diploma
        if "certificate" in title_lower:
            return "certificate"
        if "diploma" in title_lower:
            return "diploma"

        return "unknown"


def create_institution_matcher(
    exact_threshold: float = 0.99,
    high_threshold: float = 0.85,
    medium_threshold: float = 0.70,
    low_threshold: float = 0.55,
) -> InstitutionMatcher:
    """Factory function to create an InstitutionMatcher.

    Args:
        exact_threshold: Score for exact match confidence.
        high_threshold: Score for high confidence.
        medium_threshold: Score for medium confidence.
        low_threshold: Minimum score to report.

    Returns:
        Configured InstitutionMatcher instance.
    """
    return InstitutionMatcher(
        exact_threshold=exact_threshold,
        high_threshold=high_threshold,
        medium_threshold=medium_threshold,
        low_threshold=low_threshold,
    )
