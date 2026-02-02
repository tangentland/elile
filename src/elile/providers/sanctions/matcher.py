"""Fuzzy name matching for sanctions screening.

This module provides algorithms for matching names against sanctions lists
using various techniques including Levenshtein distance, Jaro-Winkler,
phonetic encoding, and token-based matching.
"""

import re
import unicodedata
from datetime import date

from elile.core.logging import get_logger

from .types import (
    FuzzyMatchConfig,
    MatchType,
    SanctionedEntity,
)

logger = get_logger(__name__)


class NameMatcher:
    """Fuzzy name matcher for sanctions screening.

    Uses multiple matching algorithms to identify potential matches
    while minimizing false positives.

    Usage:
        matcher = NameMatcher()

        # Simple name matching
        score = matcher.match_names("John Smith", "Jon Smyth")

        # Full entity matching with additional context
        score, reasons = matcher.match_entity(
            query_name="John Smith",
            entity=sanctioned_entity,
            query_dob=date(1980, 1, 15),
        )
    """

    def __init__(self, config: FuzzyMatchConfig | None = None) -> None:
        """Initialize the name matcher.

        Args:
            config: Optional fuzzy match configuration.
        """
        self._config = config or FuzzyMatchConfig()

        # Common name prefixes and suffixes to normalize
        self._prefixes = {"mr", "mrs", "ms", "dr", "prof", "sir", "lord", "sheikh"}
        self._suffixes = {"jr", "sr", "ii", "iii", "iv", "esq", "phd", "md"}

        # Phonetic consonant groups for simplified Soundex
        self._phonetic_groups = {
            "b": "1",
            "f": "1",
            "p": "1",
            "v": "1",
            "c": "2",
            "g": "2",
            "j": "2",
            "k": "2",
            "q": "2",
            "s": "2",
            "x": "2",
            "z": "2",
            "d": "3",
            "t": "3",
            "l": "4",
            "m": "5",
            "n": "5",
            "r": "6",
        }

        logger.info("name_matcher_initialized", config=self._config.model_dump())

    @property
    def config(self) -> FuzzyMatchConfig:
        """Get the matcher configuration."""
        return self._config

    def match_names(self, name1: str, name2: str) -> float:
        """Calculate match score between two names.

        Uses a combination of algorithms and returns the best score.

        Args:
            name1: First name to compare.
            name2: Second name to compare.

        Returns:
            Match score between 0.0 and 1.0.
        """
        # Normalize names
        norm1 = self._normalize_name(name1)
        norm2 = self._normalize_name(name2)

        if not norm1 or not norm2:
            return 0.0

        # Exact match after normalization
        if norm1 == norm2:
            return 1.0

        scores = []

        # Jaro-Winkler similarity (good for typos and transpositions)
        jw_score = self._jaro_winkler(norm1, norm2)
        scores.append(jw_score)

        # Token-based matching (handles word reordering)
        token_score = self._token_match(norm1, norm2)
        scores.append(token_score)

        # Phonetic matching if enabled
        if self._config.use_phonetic:
            phonetic_score = self._phonetic_match(norm1, norm2)
            scores.append(phonetic_score)

        # Return the best score
        return max(scores)

    def match_entity(
        self,
        query_name: str,
        entity: SanctionedEntity,
        *,
        query_dob: date | None = None,
        query_country: str | None = None,
    ) -> tuple[float, list[str]]:
        """Match a query against a sanctioned entity.

        Checks the primary name and all aliases, factoring in
        additional identifiers like DOB and nationality.

        Args:
            query_name: Name to search for.
            entity: Sanctioned entity to match against.
            query_dob: Optional date of birth for additional matching.
            query_country: Optional country for additional matching.

        Returns:
            Tuple of (score, match_reasons).
        """
        reasons: list[str] = []
        base_score = 0.0

        # Match against primary name
        primary_score = self.match_names(query_name, entity.name)
        if primary_score > base_score:
            base_score = primary_score
            if primary_score >= self._config.strong_threshold:
                reasons.append(f"Primary name match: {entity.name}")

        # Match against aliases if enabled
        if self._config.use_aliases:
            for alias in entity.aliases:
                alias_score = self.match_names(query_name, alias.alias_name)
                if alias_score > base_score:
                    base_score = alias_score
                    reasons = [f"Alias match: {alias.alias_name}"]

        # No good name match, return early
        if base_score < self._config.min_threshold:
            return 0.0, []

        # Factor in DOB if available
        dob_boost = 0.0
        if query_dob and entity.date_of_birth:
            if query_dob == entity.date_of_birth:
                dob_boost = self._config.weight_dob
                reasons.append(f"DOB match: {entity.date_of_birth}")
            elif abs((query_dob - entity.date_of_birth).days) <= 365:
                # Within 1 year - partial credit
                dob_boost = self._config.weight_dob * 0.5
                reasons.append(f"DOB near match: {entity.date_of_birth}")

        # Factor in country/nationality if available
        country_boost = 0.0
        if query_country and entity.nationality:
            query_country_norm = query_country.upper().strip()
            for nat in entity.nationality:
                if nat.upper().strip() == query_country_norm:
                    country_boost = self._config.weight_country
                    reasons.append(f"Nationality match: {nat}")
                    break

        # Calculate final score
        # Name score is weighted most heavily
        name_weight = 1.0 - self._config.weight_dob - self._config.weight_country
        final_score = min(1.0, base_score * name_weight + dob_boost + country_boost)

        return final_score, reasons

    def get_match_type(self, score: float) -> MatchType:
        """Convert a score to a match type.

        Args:
            score: Match score between 0.0 and 1.0.

        Returns:
            Corresponding MatchType.
        """
        return self._config.score_to_match_type(score)

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for matching.

        Removes prefixes/suffixes, normalizes unicode, lowercase, etc.
        """
        if not name:
            return ""

        # Unicode normalization and lowercase
        normalized = unicodedata.normalize("NFKD", name)
        normalized = normalized.encode("ASCII", "ignore").decode("ASCII")
        normalized = normalized.lower().strip()

        # Remove punctuation and extra whitespace
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        # Tokenize
        tokens = normalized.split()

        # Remove prefixes and suffixes
        tokens = [t for t in tokens if t not in self._prefixes and t not in self._suffixes]

        return " ".join(tokens)

    def _jaro_winkler(self, s1: str, s2: str, prefix_weight: float = 0.1) -> float:
        """Calculate Jaro-Winkler similarity.

        Good for detecting typos and character transpositions.
        """
        jaro = self._jaro_similarity(s1, s2)

        # Calculate common prefix length (up to 4 chars)
        prefix_len = 0
        for i in range(min(len(s1), len(s2), 4)):
            if s1[i] == s2[i]:
                prefix_len += 1
            else:
                break

        return jaro + prefix_len * prefix_weight * (1 - jaro)

    def _jaro_similarity(self, s1: str, s2: str) -> float:
        """Calculate Jaro similarity between two strings."""
        if not s1 or not s2:
            return 0.0

        if s1 == s2:
            return 1.0

        len1, len2 = len(s1), len(s2)
        match_distance = max(len1, len2) // 2 - 1
        if match_distance < 0:
            match_distance = 0

        s1_matches = [False] * len1
        s2_matches = [False] * len2

        matches = 0
        transpositions = 0

        for i in range(len1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len2)

            for j in range(start, end):
                if s2_matches[j] or s1[i] != s2[j]:
                    continue
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

        if matches == 0:
            return 0.0

        # Count transpositions
        k = 0
        for i in range(len1):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

        return (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3

    def _token_match(self, s1: str, s2: str) -> float:
        """Token-based matching for handling word reordering."""
        tokens1 = set(s1.split())
        tokens2 = set(s2.split())

        if not tokens1 or not tokens2:
            return 0.0

        # Intersection over union (Jaccard similarity)
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        if union == 0:
            return 0.0

        jaccard = intersection / union

        # Also check for partial token matches (fuzzy)
        partial_matches: float = 0.0
        for t1 in tokens1:
            for t2 in tokens2:
                if t1 != t2:  # Not exact match
                    # Check if one is substring of other or Jaro > 0.85
                    if t1 in t2 or t2 in t1:
                        partial_matches += 0.5
                    elif self._jaro_similarity(t1, t2) > 0.85:
                        partial_matches += 0.3

        max_partials = max(len(tokens1), len(tokens2))
        partial_bonus = min(0.2, partial_matches / max_partials * 0.2) if max_partials > 0 else 0.0

        return min(1.0, jaccard + partial_bonus)

    def _phonetic_match(self, s1: str, s2: str) -> float:
        """Phonetic matching using simplified Soundex."""
        # Encode both strings
        code1 = self._soundex(s1)
        code2 = self._soundex(s2)

        if code1 == code2:
            return 0.85  # Phonetic match is strong but not perfect

        # Check token-level phonetic similarity
        tokens1 = s1.split()
        tokens2 = s2.split()

        phonetic_matches = 0
        for t1 in tokens1:
            for t2 in tokens2:
                if self._soundex(t1) == self._soundex(t2):
                    phonetic_matches += 1
                    break

        if tokens1 and tokens2:
            return 0.7 * phonetic_matches / max(len(tokens1), len(tokens2))

        return 0.0

    def _soundex(self, s: str) -> str:
        """Generate simplified Soundex code for a string."""
        if not s:
            return ""

        # Keep first letter, encode rest
        s = s.lower()
        code = s[0].upper()
        prev = self._phonetic_groups.get(s[0], "0")

        for char in s[1:]:
            curr = self._phonetic_groups.get(char, "0")
            if curr != "0" and curr != prev:
                code += curr
                if len(code) >= 4:
                    break
            prev = curr

        # Pad with zeros
        return code.ljust(4, "0")[:4]


# Factory function
def create_name_matcher(config: FuzzyMatchConfig | None = None) -> NameMatcher:
    """Create a new name matcher instance.

    Args:
        config: Optional configuration.

    Returns:
        A new NameMatcher instance.
    """
    return NameMatcher(config)
