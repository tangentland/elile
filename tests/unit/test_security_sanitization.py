"""Tests for input sanitization utilities."""

import pytest

from elile.security.sanitization import (
    HTMLSanitizer,
    InputSanitizer,
    SQLSafetyChecker,
    sanitize_filename,
    sanitize_html,
    sanitize_string,
    validate_email,
    validate_url,
)


class TestSanitizeString:
    """Tests for sanitize_string function."""

    def test_strips_whitespace(self) -> None:
        """Test stripping whitespace."""
        assert sanitize_string("  hello  ") == "hello"
        assert sanitize_string("\n\ttest\n\t") == "test"

    def test_removes_control_characters(self) -> None:
        """Test removing control characters."""
        assert sanitize_string("hello\x00world") == "helloworld"
        assert sanitize_string("test\x1f\x7fvalue") == "testvalue"

    def test_normalizes_unicode(self) -> None:
        """Test Unicode normalization."""
        # Combining characters should be normalized
        # é as e + combining acute vs precomposed é
        result = sanitize_string("cafe\u0301")  # e + combining acute
        assert result == "café"

    def test_truncates_to_max_length(self) -> None:
        """Test truncation to max length."""
        assert sanitize_string("hello world", max_length=5) == "hello"

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert sanitize_string("") == ""
        assert sanitize_string("   ") == ""

    def test_preserves_valid_content(self) -> None:
        """Test that valid content is preserved."""
        assert sanitize_string("Hello, World!") == "Hello, World!"
        assert sanitize_string("Test 123") == "Test 123"

    def test_optional_flags(self) -> None:
        """Test optional sanitization flags."""
        # Without stripping
        result = sanitize_string("  test  ", strip=False)
        assert result == "  test  "

        # Without Unicode normalization
        result = sanitize_string("cafe", normalize_unicode=False)
        assert result == "cafe"


class TestSanitizeHTML:
    """Tests for sanitize_html function."""

    def test_strips_all_tags(self) -> None:
        """Test stripping all HTML tags."""
        assert sanitize_html("<p>Hello</p>") == "Hello"
        assert sanitize_html("<div><span>Test</span></div>") == "Test"

    def test_strips_script_tags(self) -> None:
        """Test stripping script tags."""
        result = sanitize_html("<script>alert('xss')</script>Hello")
        assert "script" not in result.lower()
        assert "alert" not in result
        assert "Hello" in result

    def test_strips_event_handlers(self) -> None:
        """Test stripping event handlers."""
        result = sanitize_html('<p onclick="alert()">Test</p>')
        assert "onclick" not in result
        assert "Test" in result

    def test_preserves_safe_tags(self) -> None:
        """Test preserving safe tags when strip_tags=False."""
        result = sanitize_html("<p>Hello</p>", strip_tags=False)
        assert "<p>" in result
        assert "Hello" in result

    def test_removes_unsafe_tags(self) -> None:
        """Test removing unsafe tags when strip_tags=False."""
        result = sanitize_html("<script>bad</script><p>good</p>", strip_tags=False)
        assert "script" not in result.lower()
        assert "<p>" in result
        assert "good" in result

    def test_sanitizes_attributes(self) -> None:
        """Test sanitizing dangerous attributes."""
        result = sanitize_html(
            '<a href="https://example.com" onclick="alert()">Link</a>',
            strip_tags=False,
        )
        assert "onclick" not in result
        assert 'href="https://example.com"' in result

    def test_blocks_javascript_urls(self) -> None:
        """Test blocking javascript: URLs."""
        result = sanitize_html(
            '<a href="javascript:alert()">Click</a>',
            strip_tags=False,
        )
        assert "javascript:" not in result

    def test_unescapes_entities(self) -> None:
        """Test unescaping HTML entities when stripping tags."""
        assert sanitize_html("&lt;test&gt;") == "<test>"
        assert sanitize_html("&amp;") == "&"

    def test_custom_allowed_tags(self) -> None:
        """Test custom allowed tags."""
        result = sanitize_html(
            "<div><strong>Bold</strong> <em>Italic</em></div>",
            allowed_tags=frozenset({"strong"}),
            strip_tags=False,
        )
        assert "<strong>" in result
        assert "<em>" not in result
        assert "<div>" not in result

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert sanitize_html("") == ""


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_removes_path_traversal(self) -> None:
        """Test removing path traversal sequences."""
        assert sanitize_filename("../../../etc/passwd") == "etc_passwd"
        assert sanitize_filename("..\\..\\windows\\system32") == "windows_system32"

    def test_removes_unsafe_characters(self) -> None:
        """Test removing unsafe characters."""
        assert sanitize_filename("file<name>.txt") == "file_name_.txt"
        assert sanitize_filename("test:file.txt") == "test_file.txt"
        assert sanitize_filename("file|name.txt") == "file_name.txt"

    def test_removes_directory_separators(self) -> None:
        """Test removing directory separators."""
        assert "_" in sanitize_filename("path/to/file.txt")
        assert "_" in sanitize_filename("path\\to\\file.txt")

    def test_truncates_long_filenames(self) -> None:
        """Test truncating long filenames."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name, max_length=255)
        assert len(result) <= 255
        assert result.endswith(".txt")

    def test_preserves_extension(self) -> None:
        """Test extension is preserved when truncating."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name, max_length=50)
        assert result.endswith(".txt")

    def test_handles_empty_filename(self) -> None:
        """Test empty filename handling."""
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename("...") == "unnamed"

    def test_removes_leading_trailing_dots(self) -> None:
        """Test removing leading/trailing dots."""
        assert sanitize_filename(".hidden") == "hidden"
        assert sanitize_filename("file.") == "file"

    def test_collapses_replacement_chars(self) -> None:
        """Test collapsing multiple replacement characters."""
        result = sanitize_filename("file<<<name>>>test")
        assert "___" not in result


class TestValidateEmail:
    """Tests for validate_email function."""

    def test_valid_emails(self) -> None:
        """Test valid email addresses."""
        assert validate_email("user@example.com") is True
        assert validate_email("user.name@example.com") is True
        assert validate_email("user+tag@example.com") is True
        assert validate_email("user@subdomain.example.com") is True

    def test_invalid_emails(self) -> None:
        """Test invalid email addresses."""
        assert validate_email("invalid") is False
        assert validate_email("@example.com") is False
        assert validate_email("user@") is False
        assert validate_email("user@.com") is False
        assert validate_email("") is False

    def test_email_length_limit(self) -> None:
        """Test email length limit."""
        long_email = "a" * 250 + "@example.com"
        assert validate_email(long_email) is False


class TestValidateURL:
    """Tests for validate_url function."""

    def test_valid_urls(self) -> None:
        """Test valid URLs."""
        assert validate_url("https://example.com") is True
        assert validate_url("http://example.com/path") is True
        assert validate_url("https://sub.example.com/path?query=1") is True

    def test_invalid_urls(self) -> None:
        """Test invalid URLs."""
        assert validate_url("") is False
        assert validate_url("not-a-url") is False
        assert validate_url("ftp://example.com") is False  # Not in allowed schemes
        assert validate_url("javascript:alert()") is False

    def test_custom_allowed_schemes(self) -> None:
        """Test custom allowed schemes."""
        assert validate_url("ftp://example.com", allowed_schemes=frozenset({"ftp"})) is True

    def test_requires_tld(self) -> None:
        """Test TLD requirement."""
        assert validate_url("http://localhost") is True  # localhost is special
        assert validate_url("http://hostname", require_tld=True) is False
        assert validate_url("http://hostname", require_tld=False) is True


class TestHTMLSanitizer:
    """Tests for HTMLSanitizer class."""

    @pytest.fixture
    def sanitizer(self) -> HTMLSanitizer:
        """Create default sanitizer."""
        return HTMLSanitizer()

    def test_removes_comments(self, sanitizer: HTMLSanitizer) -> None:
        """Test removing HTML comments."""
        result = sanitizer.sanitize("Hello <!-- comment --> World")
        assert "comment" not in result
        assert "Hello" in result
        assert "World" in result

    def test_removes_script_tags(self, sanitizer: HTMLSanitizer) -> None:
        """Test removing script tags and content."""
        result = sanitizer.sanitize("<script>alert('xss')</script>Hello")
        assert "script" not in result.lower()
        assert "alert" not in result
        assert "Hello" in result

    def test_removes_style_tags(self, sanitizer: HTMLSanitizer) -> None:
        """Test removing style tags and content."""
        result = sanitizer.sanitize("<style>.evil { display: none; }</style>Hello")
        assert "style" not in result.lower()
        assert "evil" not in result
        assert "Hello" in result

    def test_custom_allowed_tags(self) -> None:
        """Test custom allowed tags."""
        sanitizer = HTMLSanitizer(
            allowed_tags=frozenset({"p", "br"}),
        )
        result = sanitizer.sanitize("<p>Hello</p><div>World</div>")
        assert "<p>" in result
        assert "<div>" not in result


class TestSQLSafetyChecker:
    """Tests for SQLSafetyChecker class."""

    @pytest.fixture
    def checker(self) -> SQLSafetyChecker:
        """Create default checker."""
        return SQLSafetyChecker(log_detections=False)

    def test_safe_input(self, checker: SQLSafetyChecker) -> None:
        """Test safe inputs pass."""
        assert checker.is_safe("John Smith") is True
        assert checker.is_safe("Hello World") is True
        assert checker.is_safe("test@example.com") is True
        assert checker.is_safe("123 Main Street") is True

    def test_sql_injection_patterns(self, checker: SQLSafetyChecker) -> None:
        """Test SQL injection patterns are detected."""
        # Classic SQL injection
        assert checker.is_safe("'; DROP TABLE users; --") is False
        assert checker.is_safe("' OR '1'='1") is False
        assert checker.is_safe("' OR 1=1 --") is False

        # UNION-based injection
        assert checker.is_safe("' UNION SELECT * FROM users --") is False
        assert checker.is_safe("1 UNION ALL SELECT username, password FROM users") is False

        # Time-based injection
        assert checker.is_safe("'; WAITFOR DELAY '0:0:5' --") is False
        assert checker.is_safe("' OR SLEEP(5) --") is False

        # Dangerous statements
        assert checker.is_safe("'; DELETE FROM users; --") is False
        assert checker.is_safe("'; UPDATE users SET role='admin'; --") is False
        assert checker.is_safe("'; INSERT INTO users VALUES (1,'hacker'); --") is False

    def test_check_or_raise(self, checker: SQLSafetyChecker) -> None:
        """Test check_or_raise method."""
        # Safe input should return value
        result = checker.check_or_raise("safe value", "field")
        assert result == "safe value"

        # Unsafe input should raise
        with pytest.raises(ValueError):
            checker.check_or_raise("'; DROP TABLE users; --", "field")

    def test_get_matching_pattern(self, checker: SQLSafetyChecker) -> None:
        """Test getting matching pattern."""
        pattern = checker.get_matching_pattern("' OR '1'='1")
        assert pattern is not None

        pattern = checker.get_matching_pattern("safe value")
        assert pattern is None

    def test_empty_and_none(self, checker: SQLSafetyChecker) -> None:
        """Test empty string handling."""
        assert checker.is_safe("") is True
        assert checker.get_matching_pattern("") is None


class TestInputSanitizer:
    """Tests for InputSanitizer class."""

    @pytest.fixture
    def sanitizer(self) -> InputSanitizer:
        """Create default sanitizer."""
        return InputSanitizer()

    def test_sanitize_name(self, sanitizer: InputSanitizer) -> None:
        """Test name sanitization."""
        assert sanitizer.sanitize_name("John Smith") == "John Smith"
        assert sanitizer.sanitize_name("  John  Smith  ") == "John  Smith"
        assert sanitizer.sanitize_name("John<script>alert()</script>Smith") == "JohnSmith"

    def test_sanitize_name_sql_injection(self, sanitizer: InputSanitizer) -> None:
        """Test name sanitization blocks SQL injection."""
        with pytest.raises(ValueError):
            sanitizer.sanitize_name("'; DROP TABLE users; --")

    def test_sanitize_email(self, sanitizer: InputSanitizer) -> None:
        """Test email sanitization."""
        assert sanitizer.sanitize_email("USER@EXAMPLE.COM") == "user@example.com"
        assert sanitizer.sanitize_email("  user@example.com  ") == "user@example.com"

    def test_sanitize_email_invalid(self, sanitizer: InputSanitizer) -> None:
        """Test invalid email raises."""
        with pytest.raises(ValueError):
            sanitizer.sanitize_email("invalid-email")

    def test_sanitize_url(self, sanitizer: InputSanitizer) -> None:
        """Test URL sanitization."""
        assert sanitizer.sanitize_url("https://example.com") == "https://example.com"

    def test_sanitize_url_invalid(self, sanitizer: InputSanitizer) -> None:
        """Test invalid URL raises."""
        with pytest.raises(ValueError):
            sanitizer.sanitize_url("javascript:alert()")

    def test_sanitize_text(self, sanitizer: InputSanitizer) -> None:
        """Test text sanitization."""
        result = sanitizer.sanitize_text("Hello <script>alert()</script> World")
        assert "script" not in result
        assert "Hello" in result
        assert "World" in result

    def test_sanitize_text_with_html(self, sanitizer: InputSanitizer) -> None:
        """Test text sanitization with HTML allowed."""
        result = sanitizer.sanitize_text("<p>Hello</p>", allow_html=True)
        assert "<p>" in result

    def test_sanitize_identifier(self, sanitizer: InputSanitizer) -> None:
        """Test identifier sanitization."""
        assert sanitizer.sanitize_identifier("valid_id") == "valid_id"
        assert sanitizer.sanitize_identifier("valid-id-123") == "valid-id-123"

    def test_sanitize_identifier_invalid(self, sanitizer: InputSanitizer) -> None:
        """Test invalid identifier raises."""
        with pytest.raises(ValueError):
            sanitizer.sanitize_identifier("invalid id")
        with pytest.raises(ValueError):
            sanitizer.sanitize_identifier("invalid@id")

    def test_sanitize_dict(self, sanitizer: InputSanitizer) -> None:
        """Test dictionary sanitization."""
        data = {
            "name": "John<script>alert()</script>",
            "count": 42,
            "nested": {"value": "<b>test</b>"},
        }
        result = sanitizer.sanitize_dict(data)

        assert "script" not in result["name"]
        assert result["count"] == 42
        assert "b" not in result["nested"]["value"]

    def test_sanitize_list(self, sanitizer: InputSanitizer) -> None:
        """Test list sanitization."""
        data = ["Hello<script>alert()</script>", 42, {"key": "<b>value</b>"}]
        result = sanitizer.sanitize_list(data)

        assert "script" not in result[0]
        assert result[1] == 42
        assert "b" not in result[2]["key"]
