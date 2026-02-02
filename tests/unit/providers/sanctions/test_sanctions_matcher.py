"""Unit tests for Sanctions Name Matcher.

Tests the fuzzy name matching algorithms including Jaro-Winkler,
phonetic matching, and token-based matching.
"""

from datetime import date

from elile.providers.sanctions import (
    EntityType,
    FuzzyMatchConfig,
    MatchType,
    NameMatcher,
    SanctionedEntity,
    SanctionsAlias,
    SanctionsList,
    create_name_matcher,
)

# =============================================================================
# Initialization Tests
# =============================================================================


class TestNameMatcherInit:
    """Tests for NameMatcher initialization."""

    def test_create_with_defaults(self):
        """Test creating matcher with default config."""
        matcher = NameMatcher()
        assert matcher.config.exact_threshold == 0.99
        assert matcher.config.use_phonetic is True

    def test_create_with_custom_config(self):
        """Test creating matcher with custom config."""
        config = FuzzyMatchConfig(
            exact_threshold=0.98,
            use_phonetic=False,
        )
        matcher = NameMatcher(config)
        assert matcher.config.exact_threshold == 0.98
        assert matcher.config.use_phonetic is False

    def test_factory_function(self):
        """Test create_name_matcher factory."""
        matcher = create_name_matcher()
        assert isinstance(matcher, NameMatcher)

    def test_factory_with_config(self):
        """Test create_name_matcher with config."""
        config = FuzzyMatchConfig(use_aliases=False)
        matcher = create_name_matcher(config)
        assert matcher.config.use_aliases is False


# =============================================================================
# Name Normalization Tests
# =============================================================================


class TestNameNormalization:
    """Tests for name normalization."""

    def test_normalize_basic(self):
        """Test basic name normalization."""
        matcher = NameMatcher()
        # Access private method for testing
        result = matcher._normalize_name("John Smith")
        assert result == "john smith"

    def test_normalize_unicode(self):
        """Test Unicode normalization."""
        matcher = NameMatcher()
        # Accented characters should be converted to ASCII
        result = matcher._normalize_name("José García")
        assert "jose" in result
        assert "garcia" in result

    def test_normalize_removes_prefixes(self):
        """Test prefix removal."""
        matcher = NameMatcher()
        result = matcher._normalize_name("Mr. John Smith")
        assert "mr" not in result
        assert "john" in result
        assert "smith" in result

    def test_normalize_removes_suffixes(self):
        """Test suffix removal."""
        matcher = NameMatcher()
        result = matcher._normalize_name("John Smith Jr.")
        assert "jr" not in result
        assert "john" in result
        assert "smith" in result

    def test_normalize_removes_punctuation(self):
        """Test punctuation removal."""
        matcher = NameMatcher()
        result = matcher._normalize_name("O'Brien-Smith, John")
        # Should have spaces, not punctuation
        assert "," not in result
        assert "'" not in result

    def test_normalize_empty_string(self):
        """Test normalizing empty string."""
        matcher = NameMatcher()
        result = matcher._normalize_name("")
        assert result == ""

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        matcher = NameMatcher()
        result = matcher._normalize_name("  John    Smith  ")
        assert result == "john smith"


# =============================================================================
# Exact and Near-Exact Matching Tests
# =============================================================================


class TestExactMatching:
    """Tests for exact and near-exact matching."""

    def test_exact_match(self):
        """Test identical names return 1.0."""
        matcher = NameMatcher()
        score = matcher.match_names("John Smith", "John Smith")
        assert score == 1.0

    def test_case_insensitive_match(self):
        """Test case-insensitive matching."""
        matcher = NameMatcher()
        score = matcher.match_names("JOHN SMITH", "john smith")
        assert score == 1.0

    def test_near_exact_with_prefix(self):
        """Test matching with title prefix difference."""
        matcher = NameMatcher()
        score = matcher.match_names("Mr. John Smith", "John Smith")
        assert score == 1.0

    def test_near_exact_with_suffix(self):
        """Test matching with suffix difference."""
        matcher = NameMatcher()
        score = matcher.match_names("John Smith Jr", "John Smith")
        assert score == 1.0


# =============================================================================
# Jaro-Winkler Tests
# =============================================================================


class TestJaroWinkler:
    """Tests for Jaro-Winkler similarity."""

    def test_single_character_typo(self):
        """Test single character typo detection."""
        matcher = NameMatcher()
        score = matcher.match_names("John Smith", "Jon Smith")
        # Should be high score for single typo
        assert score >= 0.90

    def test_transposition(self):
        """Test character transposition detection."""
        matcher = NameMatcher()
        score = matcher.match_names("John Smith", "Jhon Smith")
        # Jaro-Winkler handles transpositions well
        assert score >= 0.90

    def test_common_misspelling(self):
        """Test common misspelling detection."""
        matcher = NameMatcher()
        score = matcher.match_names("Michael", "Micheal")
        # Common transposition
        assert score >= 0.90

    def test_completely_different_names(self):
        """Test completely different names."""
        matcher = NameMatcher()
        score = matcher.match_names("John Smith", "Mary Johnson")
        # Should be low score - phonetic/token matching may give some similarity
        assert score < 0.70


# =============================================================================
# Token-Based Matching Tests
# =============================================================================


class TestTokenMatching:
    """Tests for token-based matching."""

    def test_word_order_reversal(self):
        """Test matching with reversed word order."""
        matcher = NameMatcher()
        score = matcher.match_names("John Smith", "Smith John")
        # Token matching should catch this
        assert score >= 0.80

    def test_missing_middle_name(self):
        """Test matching with missing middle name."""
        matcher = NameMatcher()
        score = matcher.match_names("John Michael Smith", "John Smith")
        # Should still match reasonably well
        assert score >= 0.65

    def test_partial_name_match(self):
        """Test partial name matching."""
        matcher = NameMatcher()
        score = matcher.match_names("John Smith", "John")
        # Partial match should have moderate score
        # Phonetic matching can boost this higher
        assert 0.40 <= score <= 0.95


# =============================================================================
# Phonetic Matching Tests
# =============================================================================


class TestPhoneticMatching:
    """Tests for phonetic matching."""

    def test_soundex_similar_names(self):
        """Test phonetically similar names."""
        matcher = NameMatcher()
        score = matcher.match_names("Smith", "Smyth")
        # Phonetically identical
        assert score >= 0.80

    def test_phonetic_spelling_variation(self):
        """Test phonetic spelling variations."""
        matcher = NameMatcher()
        score = matcher.match_names("Catherine", "Katherine")
        # Both should have similar phonetics
        assert score >= 0.70

    def test_phonetic_disabled(self):
        """Test with phonetic matching disabled."""
        config = FuzzyMatchConfig(use_phonetic=False)
        matcher = NameMatcher(config)
        score = matcher.match_names("Smith", "Smyth")
        # Should still match via other algorithms but potentially lower
        assert score >= 0.70


# =============================================================================
# Entity Matching Tests
# =============================================================================


class TestEntityMatching:
    """Tests for full entity matching."""

    def test_match_entity_name_only(self):
        """Test matching entity with name only."""
        matcher = NameMatcher()
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="John Smith",
        )
        score, reasons = matcher.match_entity(
            query_name="John Smith",
            entity=entity,
        )
        # Note: match_entity applies weights (name_weight = 0.7 by default)
        # So a perfect name match (1.0) becomes 0.7 without DOB/country
        assert score >= 0.60
        assert len(reasons) >= 1

    def test_match_entity_with_alias(self):
        """Test matching entity via alias."""
        matcher = NameMatcher()
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="Vladimir Putin",
            aliases=[
                SanctionsAlias(alias_name="Putin Vladimir"),
                SanctionsAlias(alias_name="V. Putin"),
            ],
        )
        score, reasons = matcher.match_entity(
            query_name="Putin Vladimir",
            entity=entity,
        )
        # Note: match_entity applies weights (name_weight = 0.7 by default)
        assert score >= 0.60
        # Either alias or primary name may match
        assert len(reasons) >= 1

    def test_match_entity_with_dob_match(self):
        """Test matching entity with DOB boost."""
        matcher = NameMatcher()
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="John Smith",
            date_of_birth=date(1980, 5, 15),
        )
        score_without_dob, _ = matcher.match_entity(
            query_name="John Smith",
            entity=entity,
        )
        score_with_dob, reasons = matcher.match_entity(
            query_name="John Smith",
            entity=entity,
            query_dob=date(1980, 5, 15),
        )
        # DOB match should boost score
        assert score_with_dob >= score_without_dob
        assert any("DOB" in r for r in reasons)

    def test_match_entity_with_dob_near_match(self):
        """Test matching entity with near DOB match."""
        matcher = NameMatcher()
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="John Smith",
            date_of_birth=date(1980, 5, 15),
        )
        score, reasons = matcher.match_entity(
            query_name="John Smith",
            entity=entity,
            query_dob=date(1980, 6, 20),  # Within 1 year
        )
        assert any("near match" in r.lower() for r in reasons)

    def test_match_entity_with_country(self):
        """Test matching entity with country boost."""
        matcher = NameMatcher()
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="John Smith",
            nationality=["US", "United States"],
        )
        score_without_country, _ = matcher.match_entity(
            query_name="John Smith",
            entity=entity,
        )
        score_with_country, reasons = matcher.match_entity(
            query_name="John Smith",
            entity=entity,
            query_country="US",
        )
        assert score_with_country >= score_without_country
        assert any("Nationality" in r for r in reasons)

    def test_no_match_returns_zero(self):
        """Test no match returns zero score and empty reasons."""
        matcher = NameMatcher()
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="John Smith",
        )
        score, reasons = matcher.match_entity(
            query_name="Completely Different Person",
            entity=entity,
        )
        assert score == 0.0
        assert len(reasons) == 0

    def test_alias_matching_disabled(self):
        """Test entity matching with aliases disabled."""
        config = FuzzyMatchConfig(use_aliases=False)
        matcher = NameMatcher(config)
        entity = SanctionedEntity(
            entity_id="TEST-001",
            list_source=SanctionsList.OFAC_SDN,
            entity_type=EntityType.INDIVIDUAL,
            name="Vladimir Putin",
            aliases=[SanctionsAlias(alias_name="V. V. Putin")],
        )
        # Try to match against an alias that wouldn't match primary name
        score, _ = matcher.match_entity(
            query_name="V. V. Putin",
            entity=entity,
        )
        # Without aliases, should match less well
        # The primary name "Vladimir Putin" doesn't match "V. V. Putin" as closely
        assert score < 0.90


# =============================================================================
# Match Type Conversion Tests
# =============================================================================


class TestMatchTypeConversion:
    """Tests for score to match type conversion."""

    def test_get_match_type_exact(self):
        """Test getting EXACT match type."""
        matcher = NameMatcher()
        match_type = matcher.get_match_type(0.99)
        assert match_type == MatchType.EXACT

    def test_get_match_type_strong(self):
        """Test getting STRONG match type."""
        matcher = NameMatcher()
        match_type = matcher.get_match_type(0.92)
        assert match_type == MatchType.STRONG

    def test_get_match_type_medium(self):
        """Test getting MEDIUM match type."""
        matcher = NameMatcher()
        match_type = matcher.get_match_type(0.82)
        assert match_type == MatchType.MEDIUM

    def test_get_match_type_weak(self):
        """Test getting WEAK match type."""
        matcher = NameMatcher()
        match_type = matcher.get_match_type(0.72)
        assert match_type == MatchType.WEAK

    def test_get_match_type_potential(self):
        """Test getting POTENTIAL match type."""
        matcher = NameMatcher()
        match_type = matcher.get_match_type(0.62)
        assert match_type == MatchType.POTENTIAL

    def test_get_match_type_no_match(self):
        """Test getting NO_MATCH type."""
        matcher = NameMatcher()
        match_type = matcher.get_match_type(0.50)
        assert match_type == MatchType.NO_MATCH


# =============================================================================
# Edge Cases and Special Characters
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and special characters."""

    def test_empty_name(self):
        """Test matching empty names."""
        matcher = NameMatcher()
        score = matcher.match_names("", "John Smith")
        assert score == 0.0

    def test_both_empty(self):
        """Test matching two empty names."""
        matcher = NameMatcher()
        score = matcher.match_names("", "")
        assert score == 0.0

    def test_single_word_name(self):
        """Test single word names."""
        matcher = NameMatcher()
        score = matcher.match_names("Madonna", "Madonna")
        assert score == 1.0

    def test_hyphenated_names(self):
        """Test hyphenated names."""
        matcher = NameMatcher()
        score = matcher.match_names("Mary-Jane Watson", "Mary Jane Watson")
        assert score >= 0.90

    def test_apostrophe_names(self):
        """Test names with apostrophes."""
        matcher = NameMatcher()
        score = matcher.match_names("O'Brien", "OBrien")
        assert score >= 0.90

    def test_very_long_names(self):
        """Test very long names."""
        matcher = NameMatcher()
        long_name = "John Michael David William Smith Johnson Anderson"
        score = matcher.match_names(long_name, long_name)
        assert score == 1.0

    def test_numeric_in_name(self):
        """Test names with numbers."""
        matcher = NameMatcher()
        score = matcher.match_names("John Smith 3rd", "John Smith")
        # 3rd might be treated as a suffix
        assert score >= 0.90


# =============================================================================
# Real-World Sanctions Name Tests
# =============================================================================


class TestRealWorldNames:
    """Tests with real-world style names from sanctions lists."""

    def test_russian_name_transliteration(self):
        """Test Russian name transliteration variations."""
        matcher = NameMatcher()
        # Common variations of Russian names
        score = matcher.match_names(
            "Vladimir Vladimirovich Putin",
            "Vladimir Putin",
        )
        assert score >= 0.70

    def test_korean_name_order(self):
        """Test Korean name order variations."""
        matcher = NameMatcher()
        score = matcher.match_names("Kim Jong Un", "Jong Un Kim")
        assert score >= 0.80

    def test_arabic_name_variations(self):
        """Test Arabic name transliteration variations."""
        matcher = NameMatcher()
        # Common transliteration differences
        score = matcher.match_names(
            "Muhammad bin Salman",
            "Mohammed bin Salman",
        )
        # Phonetically similar
        assert score >= 0.80

    def test_organization_names(self):
        """Test organization name matching."""
        matcher = NameMatcher()
        score = matcher.match_names(
            "Central Bank of Iran",
            "Bank Markazi Iran",
        )
        # Different language but similar structure
        assert score >= 0.30  # Lower threshold for translations
