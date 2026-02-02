"""Data anonymization logic for GDPR compliance.

This module provides the DataAnonymizer class for anonymizing personal
identifiable information (PII) while preserving data utility for analytics.
"""

import hashlib
import logging
import re
import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid7

from elile.compliance.erasure.types import (
    AnonymizationMethod,
    AnonymizationRule,
)
from elile.compliance.retention.types import DataType

logger = logging.getLogger(__name__)


# Field patterns for automatic PII detection
PII_FIELD_PATTERNS = {
    # Names
    r"(?i)^(full_?name|first_?name|last_?name|middle_?name|maiden_?name|"
    r"given_?name|family_?name|name)$": AnonymizationMethod.REDACTION,
    # Government IDs
    r"(?i)^(ssn|social_?security|tax_?id|ein|passport|driver_?license|"
    r"national_?id|sin|nin|itin)$": AnonymizationMethod.MASKING,
    # Contact Info
    r"(?i)^(email|e_?mail|email_?address)$": AnonymizationMethod.TOKENIZATION,
    r"(?i)^(phone|telephone|mobile|cell|fax)": AnonymizationMethod.MASKING,
    # Address
    r"(?i)^(address|street|street_?address|address_?line)": AnonymizationMethod.GENERALIZATION,
    r"(?i)^(city|town|municipality)$": AnonymizationMethod.GENERALIZATION,
    r"(?i)^(state|province|region)$": AnonymizationMethod.GENERALIZATION,
    r"(?i)^(zip|postal_?code|zip_?code|postcode)$": AnonymizationMethod.MASKING,
    # Financial
    r"(?i)^(account_?number|bank_?account|iban|routing_?number)$": AnonymizationMethod.MASKING,
    r"(?i)^(credit_?card|card_?number|cvv|cvc)$": AnonymizationMethod.MASKING,
    # Dates
    r"(?i)^(date_?of_?birth|dob|birth_?date|birthday)$": AnonymizationMethod.GENERALIZATION,
    # Other PII
    r"(?i)^(ip_?address|mac_?address)$": AnonymizationMethod.HASHING,
    r"(?i)^(photo|image|picture|avatar)$": AnonymizationMethod.REDACTION,
    r"(?i)^(signature|biometric)$": AnonymizationMethod.REDACTION,
}


@dataclass
class AnonymizationConfig:
    """Configuration for data anonymization."""

    # General settings
    preserve_data_structure: bool = True
    """Keep original data structure, just anonymize values."""

    preserve_null_values: bool = True
    """Keep null values as null instead of anonymizing."""

    preserve_data_types: bool = True
    """Try to maintain original data types (string stays string, etc.)."""

    # Masking settings
    mask_character: str = "*"
    """Character to use for masking."""

    mask_preserve_last: int = 4
    """Number of characters to preserve at end when masking."""

    # Hashing settings
    hash_algorithm: str = "sha256"
    """Hash algorithm for hashing method."""

    hash_salt: str = ""
    """Salt for hashing (generated if empty)."""

    # Generalization settings
    date_generalization_level: str = "year"
    """How to generalize dates: year, month, decade."""

    address_generalization_level: str = "city"
    """How to generalize addresses: city, state, country."""

    # Custom rules
    custom_rules: dict[str, AnonymizationRule] = field(default_factory=dict)
    """Custom anonymization rules by field name."""

    # Logging
    log_anonymized_fields: bool = True
    """Log which fields were anonymized."""


@dataclass
class AnonymizationResult:
    """Result of an anonymization operation."""

    result_id: UUID = field(default_factory=uuid7)
    """Unique identifier for this result."""

    data_id: UUID | None = None
    """ID of the data that was anonymized."""

    data_type: DataType | None = None
    """Type of data that was anonymized."""

    original_hash: str = ""
    """SHA-256 hash of original data for verification."""

    anonymized_hash: str = ""
    """SHA-256 hash of anonymized data."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    """When anonymization was performed."""

    fields_anonymized: list[str] = field(default_factory=list)
    """List of fields that were anonymized."""

    methods_used: dict[str, str] = field(default_factory=dict)
    """Anonymization method used for each field."""

    success: bool = True
    """Whether anonymization was successful."""

    error_message: str | None = None
    """Error message if anonymization failed."""


class DataAnonymizer:
    """Handles anonymization of personal data.

    Provides multiple anonymization methods and automatic PII detection.
    """

    def __init__(self, config: AnonymizationConfig | None = None):
        """Initialize the anonymizer.

        Args:
            config: Anonymization configuration
        """
        self.config = config or AnonymizationConfig()
        self._salt = config.hash_salt if config else ""
        if not self._salt:
            self._salt = secrets.token_hex(16)

        logger.info("DataAnonymizer initialized")

    def anonymize_record(
        self,
        data: dict[str, Any],
        data_id: UUID | None = None,
        data_type: DataType | None = None,
        explicit_rules: dict[str, AnonymizationRule] | None = None,
    ) -> tuple[dict[str, Any], AnonymizationResult]:
        """Anonymize a data record.

        Args:
            data: The data record to anonymize
            data_id: ID of the data item
            data_type: Type of data
            explicit_rules: Optional explicit anonymization rules

        Returns:
            Tuple of (anonymized data, anonymization result)
        """
        result = AnonymizationResult(
            data_id=data_id,
            data_type=data_type,
        )

        try:
            # Hash original data for audit
            result.original_hash = self._hash_data(data)

            # Get rules for each field
            rules = explicit_rules or {}
            rules.update(self.config.custom_rules)

            # Anonymize each field
            anonymized: dict[str, Any] = {}
            for key, value in data.items():
                if self.config.preserve_null_values and value is None:
                    anonymized[key] = None
                    continue

                # Check for explicit rule
                if key in rules:
                    rule = rules[key]
                    anonymized[key] = self._apply_rule(value, rule)
                    result.fields_anonymized.append(key)
                    result.methods_used[key] = rule.method.value
                else:
                    # Check for PII pattern
                    pii_method = self._detect_pii_field(key)
                    if pii_method:
                        rule = AnonymizationRule(field_name=key, method=pii_method)
                        anonymized[key] = self._apply_rule(value, rule)
                        result.fields_anonymized.append(key)
                        result.methods_used[key] = pii_method.value
                    elif isinstance(value, dict):
                        # Recursively anonymize nested dicts
                        nested, _ = self.anonymize_record(value, explicit_rules=rules)
                        anonymized[key] = nested
                    elif isinstance(value, list):
                        # Handle list of dicts
                        anonymized[key] = self._anonymize_list(value, rules)
                    else:
                        # Keep non-PII data as-is
                        anonymized[key] = value

            result.anonymized_hash = self._hash_data(anonymized)
            result.success = True

            if self.config.log_anonymized_fields and result.fields_anonymized:
                logger.info(
                    f"Anonymized {len(result.fields_anonymized)} fields: "
                    f"{', '.join(result.fields_anonymized)}"
                )

            return anonymized, result

        except Exception as e:
            result.success = False
            result.error_message = str(e)
            logger.error(f"Anonymization failed: {e}")
            return data, result

    def _detect_pii_field(self, field_name: str) -> AnonymizationMethod | None:
        """Detect if a field name indicates PII.

        Args:
            field_name: The field name to check

        Returns:
            Anonymization method if PII detected, None otherwise
        """
        for pattern, method in PII_FIELD_PATTERNS.items():
            if re.match(pattern, field_name):
                return method
        return None

    def _apply_rule(self, value: Any, rule: AnonymizationRule) -> Any:
        """Apply an anonymization rule to a value.

        Args:
            value: The value to anonymize
            rule: The anonymization rule

        Returns:
            Anonymized value
        """
        if value is None:
            return None

        method = rule.method

        if method == AnonymizationMethod.REDACTION:
            return self._redact(value, rule)
        elif method == AnonymizationMethod.MASKING:
            return self._mask(value, rule)
        elif method == AnonymizationMethod.GENERALIZATION:
            return self._generalize(value, rule)
        elif method == AnonymizationMethod.TOKENIZATION:
            return self._tokenize(value, rule)
        elif method == AnonymizationMethod.PSEUDONYMIZATION:
            return self._pseudonymize(value, rule)
        elif method == AnonymizationMethod.HASHING:
            return self._hash_value(value, rule)
        else:
            return self._redact(value, rule)

    def _redact(self, value: Any, rule: AnonymizationRule) -> str:
        """Redact a value completely.

        Args:
            value: Value to redact
            rule: Anonymization rule

        Returns:
            Redacted value
        """
        if rule.custom_value:
            return rule.custom_value

        if rule.preserve_length and isinstance(value, str):
            return self.config.mask_character * len(value)

        return "[REDACTED]"

    def _mask(self, value: Any, rule: AnonymizationRule) -> str:
        """Mask a value, preserving some characters.

        Args:
            value: Value to mask
            rule: Anonymization rule

        Returns:
            Masked value
        """
        str_value = str(value)
        length = len(str_value)

        if length <= self.config.mask_preserve_last:
            return self.config.mask_character * length

        mask_count = length - self.config.mask_preserve_last
        masked = (
            self.config.mask_character * mask_count + str_value[-self.config.mask_preserve_last :]
        )

        if rule.preserve_format:
            # Try to preserve format (e.g., SSN: XXX-XX-6789)
            masked = self._preserve_format(str_value, masked)

        return masked

    def _preserve_format(self, original: str, masked: str) -> str:
        """Preserve the format of the original value in masked version.

        Args:
            original: Original value
            masked: Masked value

        Returns:
            Masked value with preserved format
        """
        # Detect common formats
        # SSN: XXX-XX-XXXX
        if re.match(r"^\d{3}-\d{2}-\d{4}$", original):
            return f"***-**-{original[-4:]}"

        # Phone: (XXX) XXX-XXXX or XXX-XXX-XXXX
        if re.match(r"^\(\d{3}\) \d{3}-\d{4}$", original):
            return f"(***) ***-{original[-4:]}"
        if re.match(r"^\d{3}-\d{3}-\d{4}$", original):
            return f"***-***-{original[-4:]}"

        # Credit card: XXXX XXXX XXXX XXXX
        if re.match(r"^\d{4} \d{4} \d{4} \d{4}$", original):
            return f"**** **** **** {original[-4:]}"

        return masked

    def _generalize(self, value: Any, rule: AnonymizationRule) -> Any:
        """Generalize a value to a broader category.

        Args:
            value: Value to generalize
            rule: Anonymization rule

        Returns:
            Generalized value
        """
        # Handle dates
        if isinstance(value, datetime):
            if self.config.date_generalization_level == "year":
                return f"{value.year}"
            elif self.config.date_generalization_level == "month":
                return f"{value.year}-{value.month:02d}"
            elif self.config.date_generalization_level == "decade":
                decade = (value.year // 10) * 10
                return f"{decade}s"
            return str(value.year)

        # Handle date strings
        str_value = str(value)
        date_patterns = [
            (r"^\d{4}-\d{2}-\d{2}$", "year"),  # YYYY-MM-DD
            (r"^\d{2}/\d{2}/\d{4}$", "year"),  # MM/DD/YYYY
            (r"^\d{2}-\d{2}-\d{4}$", "year"),  # DD-MM-YYYY
        ]

        for pattern, _level in date_patterns:
            if re.match(pattern, str_value):
                # Extract year and generalize
                year_match = re.search(r"\d{4}", str_value)
                if year_match:
                    year = int(year_match.group())
                    if self.config.date_generalization_level == "decade":
                        return f"{(year // 10) * 10}s"
                    return str(year)

        # Handle addresses - keep only city/state level
        if rule.field_name and "address" in rule.field_name.lower():
            return "[ADDRESS REMOVED]"

        if rule.field_name and "city" in rule.field_name.lower():
            return "[CITY]"

        if rule.field_name and "state" in rule.field_name.lower():
            return value  # Keep state as-is (not highly identifying)

        # Handle zip codes - generalize to 3-digit prefix
        if re.match(r"^\d{5}(-\d{4})?$", str_value):
            return str_value[:3] + "XX"

        # Default: truncate to first character
        if isinstance(value, str) and len(value) > 0:
            return value[0] + "..."

        return "[GENERALIZED]"

    def _tokenize(self, value: Any, rule: AnonymizationRule) -> str:  # noqa: ARG002
        """Replace value with a random token.

        Args:
            value: Value to tokenize
            rule: Anonymization rule

        Returns:
            Random token
        """
        # Generate deterministic token based on value (for consistency)
        token_hash = hashlib.sha256(f"{self._salt}:{value}".encode()).hexdigest()[:12]
        return f"tok_{token_hash}"

    def _pseudonymize(self, value: Any, rule: AnonymizationRule) -> str:
        """Replace value with a pseudonym.

        Args:
            value: Value to pseudonymize
            rule: Anonymization rule

        Returns:
            Pseudonymized value
        """
        # Generate deterministic pseudonym
        pseudo_hash = hashlib.sha256(f"{self._salt}:{value}".encode()).hexdigest()

        # Generate name-like pseudonym for name fields
        if rule.field_name and "name" in rule.field_name.lower():
            # Use hash to generate consistent pseudo-name
            first_names = ["Alex", "Blake", "Casey", "Dana", "Ellis", "Finley"]
            last_names = ["Smith", "Jones", "Brown", "Davis", "Miller", "Wilson"]
            first_idx = int(pseudo_hash[:2], 16) % len(first_names)
            last_idx = int(pseudo_hash[2:4], 16) % len(last_names)
            return f"{first_names[first_idx]} {last_names[last_idx]}"

        return f"pseudo_{pseudo_hash[:8]}"

    def _hash_value(self, value: Any, rule: AnonymizationRule) -> str:  # noqa: ARG002
        """Hash a value (one-way, irreversible).

        Args:
            value: Value to hash
            rule: Anonymization rule

        Returns:
            Hashed value
        """
        hash_input = f"{self._salt}:{value}".encode()

        if self.config.hash_algorithm == "sha256":
            return hashlib.sha256(hash_input).hexdigest()
        elif self.config.hash_algorithm == "sha512":
            return hashlib.sha512(hash_input).hexdigest()
        elif self.config.hash_algorithm == "md5":
            return hashlib.md5(hash_input).hexdigest()  # noqa: S324
        else:
            return hashlib.sha256(hash_input).hexdigest()

    def _hash_data(self, data: dict[str, Any]) -> str:
        """Generate a hash of the entire data record.

        Args:
            data: Data to hash

        Returns:
            SHA-256 hash of the data
        """
        import json

        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _anonymize_list(
        self,
        items: list[Any],
        rules: dict[str, AnonymizationRule],
    ) -> list[Any]:
        """Anonymize a list of items.

        Args:
            items: List to anonymize
            rules: Anonymization rules

        Returns:
            Anonymized list
        """
        result = []
        for item in items:
            if isinstance(item, dict):
                anonymized, _ = self.anonymize_record(item, explicit_rules=rules)
                result.append(anonymized)
            else:
                result.append(item)
        return result

    def generate_random_replacement(
        self,
        original: str,
        preserve_format: bool = False,
    ) -> str:
        """Generate a random replacement string.

        Args:
            original: Original value for format reference
            preserve_format: Whether to preserve the format

        Returns:
            Random replacement string
        """
        length = len(original) if preserve_format else 10

        # Detect and preserve format
        if preserve_format:
            if re.match(r"^[A-Z]+$", original):
                return "".join(secrets.choice(string.ascii_uppercase) for _ in range(length))
            elif re.match(r"^[a-z]+$", original):
                return "".join(secrets.choice(string.ascii_lowercase) for _ in range(length))
            elif re.match(r"^\d+$", original):
                return "".join(secrets.choice(string.digits) for _ in range(length))

        return secrets.token_hex(length // 2)


def create_anonymizer(config: AnonymizationConfig | None = None) -> DataAnonymizer:
    """Create a configured DataAnonymizer.

    Args:
        config: Optional configuration

    Returns:
        Configured DataAnonymizer instance
    """
    return DataAnonymizer(config)
