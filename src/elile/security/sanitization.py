"""Input sanitization utilities.

Provides comprehensive input sanitization including:
- HTML sanitization (XSS prevention)
- String sanitization (control character removal)
- Filename sanitization (path traversal prevention)
- URL validation
- Email validation
- SQL safety checking (detection of dangerous patterns)
"""

import html
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

# Regex patterns compiled once for performance
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

_PATH_TRAVERSAL_PATTERN = re.compile(r"(\.\.[\\/]|[\\/]\.\.)")

_FILENAME_UNSAFE_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# SQL injection patterns (common attack vectors)
_SQL_DANGEROUS_PATTERNS = [
    re.compile(r";\s*--", re.IGNORECASE),  # Comment after statement
    re.compile(r"'\s*OR\s+'[^']*'\s*=\s*'", re.IGNORECASE),  # ' OR '1'='1
    re.compile(r"'\s*OR\s+\d+\s*=\s*\d+", re.IGNORECASE),  # ' OR 1=1
    re.compile(r"UNION\s+(ALL\s+)?SELECT", re.IGNORECASE),  # UNION SELECT
    re.compile(r"INSERT\s+INTO", re.IGNORECASE),  # INSERT INTO
    re.compile(r"UPDATE\s+\w+\s+SET", re.IGNORECASE),  # UPDATE SET
    re.compile(r"DELETE\s+FROM", re.IGNORECASE),  # DELETE FROM
    re.compile(r"DROP\s+(TABLE|DATABASE|INDEX)", re.IGNORECASE),  # DROP
    re.compile(r"EXEC(UTE)?\s*\(", re.IGNORECASE),  # EXEC/EXECUTE
    re.compile(r"xp_\w+", re.IGNORECASE),  # SQL Server xp_ procedures
    re.compile(r";\s*WAITFOR\s+DELAY", re.IGNORECASE),  # Time-based SQLi
    re.compile(r"SLEEP\s*\(\s*\d+\s*\)", re.IGNORECASE),  # MySQL SLEEP
    re.compile(r"BENCHMARK\s*\(", re.IGNORECASE),  # MySQL BENCHMARK
    re.compile(r"LOAD_FILE\s*\(", re.IGNORECASE),  # MySQL LOAD_FILE
    re.compile(r"INTO\s+(OUT|DUMP)FILE", re.IGNORECASE),  # File operations
]

# HTML tags that are generally safe (allow list)
_SAFE_HTML_TAGS = frozenset(
    {
        "p",
        "br",
        "b",
        "i",
        "u",
        "em",
        "strong",
        "span",
        "ul",
        "ol",
        "li",
        "a",
        "blockquote",
        "pre",
        "code",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    }
)

# Safe attributes for HTML tags
_SAFE_HTML_ATTRS = frozenset(
    {
        "href",
        "title",
        "class",
        "id",
        "colspan",
        "rowspan",
    }
)


def sanitize_string(
    value: str,
    max_length: int | None = None,
    strip: bool = True,
    normalize_unicode: bool = True,
    remove_control_chars: bool = True,
) -> str:
    """Sanitize a string input.

    Performs the following sanitization:
    - Strips leading/trailing whitespace
    - Normalizes Unicode to NFC form
    - Removes control characters
    - Truncates to max length

    Args:
        value: The string to sanitize
        max_length: Maximum allowed length (truncates if exceeded)
        strip: Whether to strip whitespace
        normalize_unicode: Whether to normalize Unicode
        remove_control_chars: Whether to remove control characters

    Returns:
        Sanitized string

    Example:
        >>> sanitize_string("  Hello\\x00World  ", max_length=10)
        'HelloWorld'
    """
    if not value:
        return ""

    result = value

    # Strip whitespace
    if strip:
        result = result.strip()

    # Normalize Unicode
    if normalize_unicode:
        result = unicodedata.normalize("NFC", result)

    # Remove control characters
    if remove_control_chars:
        result = _CONTROL_CHARS_PATTERN.sub("", result)

    # Truncate to max length
    if max_length is not None and len(result) > max_length:
        result = result[:max_length]

    return result


def sanitize_html(
    value: str,
    allowed_tags: frozenset[str] | None = None,
    allowed_attrs: frozenset[str] | None = None,
    strip_tags: bool = True,
) -> str:
    """Sanitize HTML content to prevent XSS.

    If strip_tags is True, all HTML tags are removed.
    Otherwise, only allowed tags and attributes are preserved.

    Args:
        value: HTML content to sanitize
        allowed_tags: Set of allowed HTML tags (lowercase)
        allowed_attrs: Set of allowed HTML attributes (lowercase)
        strip_tags: If True, remove all HTML tags

    Returns:
        Sanitized HTML content

    Example:
        >>> sanitize_html("<script>alert('xss')</script><p>Hello</p>")
        'Hello'
        >>> sanitize_html("<p onclick='alert()'>Hello</p>", strip_tags=False)
        '<p>Hello</p>'
    """
    if not value:
        return ""

    result = value

    if strip_tags:
        # First, remove dangerous tags and their content (script, style, etc.)
        result = re.sub(
            r"<script\b[^>]*>.*?</script>",
            "",
            result,
            flags=re.DOTALL | re.IGNORECASE,
        )
        result = re.sub(
            r"<style\b[^>]*>.*?</style>",
            "",
            result,
            flags=re.DOTALL | re.IGNORECASE,
        )
        result = re.sub(
            r"<noscript\b[^>]*>.*?</noscript>",
            "",
            result,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Remove HTML comments
        result = re.sub(r"<!--.*?-->", "", result, flags=re.DOTALL)
        # Remove all remaining HTML tags (but keep their content)
        result = re.sub(r"<[^>]+>", "", result)
        # Unescape HTML entities
        result = html.unescape(result)
        return sanitize_string(result)

    # Use allow list approach for tags and attributes
    tags = allowed_tags or _SAFE_HTML_TAGS
    attrs = allowed_attrs or _SAFE_HTML_ATTRS

    # Simple tag-by-tag sanitization
    # For production, consider using a library like bleach or lxml
    def replace_tag(match: re.Match[str]) -> str:
        tag_content = match.group(1)
        if not tag_content:
            return ""

        # Parse tag name and attributes
        parts = tag_content.split(None, 1)
        tag_name = parts[0].lower().strip("/")

        # Check if closing tag
        is_closing = tag_content.startswith("/")

        if tag_name not in tags:
            return ""

        if is_closing:
            return f"</{tag_name}>"

        # Filter attributes
        if len(parts) > 1:
            attr_str = parts[1]
            safe_attrs = []
            for attr_match in re.finditer(r'(\w+)\s*=\s*["\']([^"\']*)["\']', attr_str):
                attr_name = attr_match.group(1).lower()
                attr_value = attr_match.group(2)
                if attr_name in attrs:
                    # Additional safety: check href for javascript:
                    if attr_name == "href" and attr_value.lower().startswith("javascript:"):
                        continue
                    safe_attrs.append(f'{attr_name}="{html.escape(attr_value)}"')

            if safe_attrs:
                return f"<{tag_name} {' '.join(safe_attrs)}>"
            return f"<{tag_name}>"

        return f"<{tag_name}>"

    result = re.sub(r"<([^>]*)>", replace_tag, value)
    return result


def sanitize_filename(
    filename: str,
    max_length: int = 255,
    replacement: str = "_",
) -> str:
    """Sanitize a filename to prevent path traversal and invalid characters.

    Args:
        filename: The filename to sanitize
        max_length: Maximum filename length
        replacement: Character to replace invalid characters with

    Returns:
        Safe filename

    Example:
        >>> sanitize_filename("../../../etc/passwd")
        'etc_passwd'
        >>> sanitize_filename("file<name>.txt")
        'file_name_.txt'
    """
    if not filename:
        return "unnamed"

    # Remove path traversal sequences
    result = _PATH_TRAVERSAL_PATTERN.sub("", filename)

    # Remove directory separators
    result = result.replace("/", replacement)
    result = result.replace("\\", replacement)

    # Remove unsafe characters
    result = _FILENAME_UNSAFE_PATTERN.sub(replacement, result)

    # Remove leading/trailing dots and spaces (problematic on some systems)
    result = result.strip(". ")

    # Collapse multiple replacement characters
    while replacement + replacement in result:
        result = result.replace(replacement + replacement, replacement)

    # Ensure we have something
    if not result:
        return "unnamed"

    # Truncate if needed
    if len(result) > max_length:
        # Preserve extension if present
        if "." in result:
            name, ext = result.rsplit(".", 1)
            max_name_len = max_length - len(ext) - 1
            if max_name_len > 0:
                result = f"{name[:max_name_len]}.{ext}"
            else:
                result = result[:max_length]
        else:
            result = result[:max_length]

    return result


def validate_email(email: str) -> bool:
    """Validate an email address format.

    Args:
        email: Email address to validate

    Returns:
        True if the email format is valid

    Example:
        >>> validate_email("user@example.com")
        True
        >>> validate_email("invalid-email")
        False
    """
    if not email or len(email) > 254:
        return False

    return bool(_EMAIL_PATTERN.match(email))


def validate_url(
    url: str,
    allowed_schemes: frozenset[str] | None = None,
    require_tld: bool = True,
) -> bool:
    """Validate a URL.

    Args:
        url: URL to validate
        allowed_schemes: Set of allowed URL schemes
        require_tld: Whether to require a TLD in the domain

    Returns:
        True if the URL is valid

    Example:
        >>> validate_url("https://example.com/path")
        True
        >>> validate_url("javascript:alert('xss')")
        False
    """
    if not url:
        return False

    schemes = allowed_schemes or frozenset({"http", "https"})

    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme.lower() not in schemes:
            return False

        # Check netloc exists
        if not parsed.netloc:
            return False

        # Check for TLD if required
        if require_tld:
            domain = parsed.netloc.split(":")[0]  # Remove port
            if "." not in domain and domain.lower() != "localhost":
                return False

        return True
    except Exception:
        return False


@dataclass
class HTMLSanitizer:
    """Configurable HTML sanitizer.

    Provides a more flexible interface for HTML sanitization with
    customizable tag and attribute allow lists.

    Example:
        sanitizer = HTMLSanitizer(
            allowed_tags={"p", "br", "a"},
            allowed_attrs={"href", "class"},
        )
        safe_html = sanitizer.sanitize("<script>bad</script><p>good</p>")
    """

    allowed_tags: frozenset[str] = field(default_factory=lambda: _SAFE_HTML_TAGS)
    allowed_attrs: frozenset[str] = field(default_factory=lambda: _SAFE_HTML_ATTRS)
    strip_comments: bool = True
    strip_scripts: bool = True
    strip_styles: bool = True

    def sanitize(self, content: str) -> str:
        """Sanitize HTML content.

        Args:
            content: HTML to sanitize

        Returns:
            Sanitized HTML
        """
        if not content:
            return ""

        result = content

        # Remove comments
        if self.strip_comments:
            result = re.sub(r"<!--.*?-->", "", result, flags=re.DOTALL)

        # Remove script tags and content
        if self.strip_scripts:
            result = re.sub(
                r"<script\b[^>]*>.*?</script>",
                "",
                result,
                flags=re.DOTALL | re.IGNORECASE,
            )

        # Remove style tags and content
        if self.strip_styles:
            result = re.sub(
                r"<style\b[^>]*>.*?</style>",
                "",
                result,
                flags=re.DOTALL | re.IGNORECASE,
            )

        # Sanitize remaining HTML
        return sanitize_html(
            result,
            allowed_tags=self.allowed_tags,
            allowed_attrs=self.allowed_attrs,
            strip_tags=False,
        )


@dataclass
class SQLSafetyChecker:
    """SQL injection pattern detector.

    Detects common SQL injection patterns in user input.
    Note: This is a defense-in-depth measure. Always use parameterized
    queries (SQLAlchemy ORM) as the primary defense.

    Example:
        checker = SQLSafetyChecker()
        if not checker.is_safe("'; DROP TABLE users; --"):
            raise ValueError("Potential SQL injection detected")
    """

    patterns: list[re.Pattern[str]] = field(default_factory=lambda: list(_SQL_DANGEROUS_PATTERNS))
    log_detections: bool = True

    def is_safe(self, value: str) -> bool:
        """Check if a value appears safe from SQL injection.

        Args:
            value: Value to check

        Returns:
            True if no SQL injection patterns detected
        """
        if not value:
            return True

        for pattern in self.patterns:
            if pattern.search(value):
                if self.log_detections:
                    import logging

                    logger = logging.getLogger("elile.security")
                    logger.warning(
                        "Potential SQL injection detected",
                        extra={"pattern": pattern.pattern, "value_length": len(value)},
                    )
                return False

        return True

    def check_or_raise(self, value: str, field_name: str = "input") -> str:
        """Check value and raise if unsafe.

        Args:
            value: Value to check
            field_name: Name of the field for error message

        Returns:
            The original value if safe

        Raises:
            ValueError: If SQL injection pattern detected
        """
        if not self.is_safe(value):
            raise ValueError(f"Invalid characters in {field_name}")
        return value

    def get_matching_pattern(self, value: str) -> str | None:
        """Get the pattern that matched, if any.

        Args:
            value: Value to check

        Returns:
            The matching pattern string, or None
        """
        if not value:
            return None

        for pattern in self.patterns:
            if pattern.search(value):
                return pattern.pattern

        return None


@dataclass
class InputSanitizer:
    """Comprehensive input sanitizer for API requests.

    Combines multiple sanitization techniques for various input types.

    Example:
        sanitizer = InputSanitizer()
        safe_name = sanitizer.sanitize_name("John<script>Doe")  # "JohnDoe"
        safe_email = sanitizer.sanitize_email("USER@EXAMPLE.COM")  # "user@example.com"
    """

    max_string_length: int = 10000
    max_name_length: int = 200
    max_email_length: int = 254
    sql_checker: SQLSafetyChecker = field(default_factory=SQLSafetyChecker)

    def sanitize_name(self, name: str) -> str:
        """Sanitize a person or entity name.

        Args:
            name: Name to sanitize

        Returns:
            Sanitized name
        """
        # Basic string sanitization
        result = sanitize_string(
            name,
            max_length=self.max_name_length,
            normalize_unicode=True,
        )

        # Remove HTML tags
        result = sanitize_html(result, strip_tags=True)

        # Check for SQL patterns
        self.sql_checker.check_or_raise(result, "name")

        return result

    def sanitize_email(self, email: str) -> str:
        """Sanitize and validate an email address.

        Args:
            email: Email to sanitize

        Returns:
            Sanitized email (lowercase)

        Raises:
            ValueError: If email format is invalid
        """
        result = sanitize_string(
            email,
            max_length=self.max_email_length,
        ).lower()

        if not validate_email(result):
            raise ValueError("Invalid email format")

        return result

    def sanitize_url(self, url: str) -> str:
        """Sanitize and validate a URL.

        Args:
            url: URL to sanitize

        Returns:
            Sanitized URL

        Raises:
            ValueError: If URL format is invalid
        """
        result = sanitize_string(url, max_length=2048)

        if not validate_url(result):
            raise ValueError("Invalid URL format")

        return result

    def sanitize_text(self, text: str, allow_html: bool = False) -> str:
        """Sanitize free-form text input.

        Args:
            text: Text to sanitize
            allow_html: Whether to preserve safe HTML tags

        Returns:
            Sanitized text
        """
        result = sanitize_string(
            text,
            max_length=self.max_string_length,
        )

        if allow_html:
            result = sanitize_html(result, strip_tags=False)
        else:
            result = sanitize_html(result, strip_tags=True)

        # Check for SQL patterns
        self.sql_checker.check_or_raise(result, "text")

        return result

    def sanitize_identifier(self, identifier: str) -> str:
        """Sanitize an identifier (alphanumeric with hyphens/underscores).

        Args:
            identifier: Identifier to sanitize

        Returns:
            Sanitized identifier

        Raises:
            ValueError: If identifier contains invalid characters
        """
        result = sanitize_string(identifier, max_length=100)

        # Allow only alphanumeric, hyphen, underscore
        if not re.match(r"^[a-zA-Z0-9_-]+$", result):
            raise ValueError("Identifier contains invalid characters")

        return result

    def sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively sanitize string values in a dictionary.

        Args:
            data: Dictionary to sanitize

        Returns:
            Dictionary with sanitized string values
        """
        result: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.sanitize_text(value)
            elif isinstance(value, dict):
                result[key] = self.sanitize_dict(value)
            elif isinstance(value, list):
                result[key] = self.sanitize_list(value)
            else:
                result[key] = value
        return result

    def sanitize_list(self, data: list[Any]) -> list[Any]:
        """Recursively sanitize string values in a list.

        Args:
            data: List to sanitize

        Returns:
            List with sanitized string values
        """
        result: list[Any] = []
        for item in data:
            if isinstance(item, str):
                result.append(self.sanitize_text(item))
            elif isinstance(item, dict):
                result.append(self.sanitize_dict(item))
            elif isinstance(item, list):
                result.append(self.sanitize_list(item))
            else:
                result.append(item)
        return result
