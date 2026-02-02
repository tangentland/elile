"""Unit tests for GDPR data anonymization."""

from datetime import datetime
from uuid import uuid7

import pytest

from elile.compliance.erasure.anonymizer import (
    AnonymizationConfig,
    DataAnonymizer,
    PII_FIELD_PATTERNS,
    create_anonymizer,
)
from elile.compliance.erasure.types import (
    AnonymizationMethod,
    AnonymizationRule,
)
from elile.compliance.retention.types import DataType


class TestAnonymizationConfig:
    """Tests for AnonymizationConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AnonymizationConfig()
        assert config.preserve_data_structure is True
        assert config.preserve_null_values is True
        assert config.mask_character == "*"
        assert config.mask_preserve_last == 4
        assert config.hash_algorithm == "sha256"
        assert config.date_generalization_level == "year"

    def test_custom_config(self):
        """Test custom configuration."""
        config = AnonymizationConfig(
            mask_character="#",
            mask_preserve_last=6,
            hash_algorithm="sha512",
            date_generalization_level="decade",
        )
        assert config.mask_character == "#"
        assert config.mask_preserve_last == 6
        assert config.hash_algorithm == "sha512"
        assert config.date_generalization_level == "decade"


class TestDataAnonymizer:
    """Tests for DataAnonymizer class."""

    def test_create_anonymizer(self):
        """Test creating an anonymizer."""
        anonymizer = create_anonymizer()
        assert isinstance(anonymizer, DataAnonymizer)

    def test_create_anonymizer_with_config(self):
        """Test creating an anonymizer with config."""
        config = AnonymizationConfig(mask_preserve_last=6)
        anonymizer = create_anonymizer(config)
        assert anonymizer.config.mask_preserve_last == 6

    def test_anonymize_empty_record(self):
        """Test anonymizing an empty record."""
        anonymizer = DataAnonymizer()
        result, report = anonymizer.anonymize_record({})
        assert result == {}
        assert report.success is True
        assert len(report.fields_anonymized) == 0

    def test_anonymize_non_pii_data(self):
        """Test that non-PII data is preserved."""
        anonymizer = DataAnonymizer()
        data = {
            "status": "active",
            "count": 42,
            "is_valid": True,
        }
        result, report = anonymizer.anonymize_record(data)
        assert result["status"] == "active"
        assert result["count"] == 42
        assert result["is_valid"] is True
        assert len(report.fields_anonymized) == 0

    def test_anonymize_null_values_preserved(self):
        """Test that null values are preserved by default."""
        anonymizer = DataAnonymizer()
        data = {"full_name": None, "email": None}
        result, report = anonymizer.anonymize_record(data)
        assert result["full_name"] is None
        assert result["email"] is None

    def test_redaction(self):
        """Test redaction method."""
        anonymizer = DataAnonymizer()
        data = {"full_name": "John Smith"}
        rules = {
            "full_name": AnonymizationRule("full_name", AnonymizationMethod.REDACTION),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert result["full_name"] == "[REDACTED]"
        assert "full_name" in report.fields_anonymized

    def test_redaction_with_custom_value(self):
        """Test redaction with custom replacement value."""
        anonymizer = DataAnonymizer()
        data = {"full_name": "John Smith"}
        rules = {
            "full_name": AnonymizationRule(
                "full_name",
                AnonymizationMethod.REDACTION,
                custom_value="[REMOVED]",
            ),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert result["full_name"] == "[REMOVED]"

    def test_masking_ssn(self):
        """Test masking SSN with format preservation."""
        anonymizer = DataAnonymizer()
        data = {"ssn": "123-45-6789"}
        rules = {
            "ssn": AnonymizationRule(
                "ssn",
                AnonymizationMethod.MASKING,
                preserve_format=True,
            ),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert result["ssn"] == "***-**-6789"
        assert "ssn" in report.fields_anonymized

    def test_masking_phone(self):
        """Test masking phone number."""
        anonymizer = DataAnonymizer()
        data = {"phone": "(555) 123-4567"}
        rules = {
            "phone": AnonymizationRule(
                "phone",
                AnonymizationMethod.MASKING,
                preserve_format=True,
            ),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert result["phone"] == "(***) ***-4567"

    def test_masking_credit_card(self):
        """Test masking credit card number."""
        anonymizer = DataAnonymizer()
        data = {"card": "1234 5678 9012 3456"}
        rules = {
            "card": AnonymizationRule(
                "card",
                AnonymizationMethod.MASKING,
                preserve_format=True,
            ),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert result["card"] == "**** **** **** 3456"

    def test_masking_default_last_4(self):
        """Test masking preserves last 4 characters by default."""
        anonymizer = DataAnonymizer()
        data = {"account": "12345678"}
        rules = {
            "account": AnonymizationRule("account", AnonymizationMethod.MASKING),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert result["account"].endswith("5678")
        assert result["account"].startswith("****")

    def test_generalization_date(self):
        """Test date generalization."""
        anonymizer = DataAnonymizer()
        data = {"date_of_birth": "1985-03-15"}
        rules = {
            "date_of_birth": AnonymizationRule(
                "date_of_birth",
                AnonymizationMethod.GENERALIZATION,
            ),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert result["date_of_birth"] == "1985"

    def test_generalization_date_decade(self):
        """Test date generalization to decade."""
        config = AnonymizationConfig(date_generalization_level="decade")
        anonymizer = DataAnonymizer(config)
        data = {"date_of_birth": "1985-03-15"}
        rules = {
            "date_of_birth": AnonymizationRule(
                "date_of_birth",
                AnonymizationMethod.GENERALIZATION,
            ),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert result["date_of_birth"] == "1980s"

    def test_generalization_zip_code(self):
        """Test zip code generalization."""
        anonymizer = DataAnonymizer()
        data = {"zip_code": "12345"}
        rules = {
            "zip_code": AnonymizationRule("zip_code", AnonymizationMethod.GENERALIZATION),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert result["zip_code"] == "123XX"

    def test_tokenization(self):
        """Test tokenization method."""
        anonymizer = DataAnonymizer()
        data = {"email": "john@example.com"}
        rules = {
            "email": AnonymizationRule("email", AnonymizationMethod.TOKENIZATION),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert result["email"].startswith("tok_")
        assert len(result["email"]) == 16  # "tok_" + 12 hex chars

    def test_tokenization_consistency(self):
        """Test that tokenization produces consistent tokens."""
        anonymizer = DataAnonymizer()
        data = {"email": "john@example.com"}
        rules = {
            "email": AnonymizationRule("email", AnonymizationMethod.TOKENIZATION),
        }
        result1, _ = anonymizer.anonymize_record(data.copy(), explicit_rules=rules)
        result2, _ = anonymizer.anonymize_record(data.copy(), explicit_rules=rules)
        assert result1["email"] == result2["email"]

    def test_hashing(self):
        """Test hashing method."""
        anonymizer = DataAnonymizer()
        data = {"ip_address": "192.168.1.100"}
        rules = {
            "ip_address": AnonymizationRule("ip_address", AnonymizationMethod.HASHING),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert len(result["ip_address"]) == 64  # SHA-256 hex length
        assert "ip_address" in report.fields_anonymized

    def test_pseudonymization(self):
        """Test pseudonymization method."""
        anonymizer = DataAnonymizer()
        data = {"full_name": "John Smith"}
        rules = {
            "full_name": AnonymizationRule("full_name", AnonymizationMethod.PSEUDONYMIZATION),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        # Should generate a pseudo-name
        assert " " in result["full_name"]  # Contains first and last name
        assert result["full_name"] != "John Smith"

    def test_automatic_pii_detection_name(self):
        """Test automatic PII detection for name fields."""
        anonymizer = DataAnonymizer()
        data = {"full_name": "John Smith", "first_name": "John", "last_name": "Smith"}
        result, report = anonymizer.anonymize_record(data)
        assert "full_name" in report.fields_anonymized
        assert "first_name" in report.fields_anonymized
        assert "last_name" in report.fields_anonymized

    def test_automatic_pii_detection_ssn(self):
        """Test automatic PII detection for SSN."""
        anonymizer = DataAnonymizer()
        data = {"ssn": "123-45-6789"}
        result, report = anonymizer.anonymize_record(data)
        assert "ssn" in report.fields_anonymized
        # Should be masked
        assert result["ssn"].endswith("6789")

    def test_automatic_pii_detection_email(self):
        """Test automatic PII detection for email."""
        anonymizer = DataAnonymizer()
        data = {"email": "john@example.com"}
        result, report = anonymizer.anonymize_record(data)
        assert "email" in report.fields_anonymized

    def test_automatic_pii_detection_phone(self):
        """Test automatic PII detection for phone."""
        anonymizer = DataAnonymizer()
        data = {"phone": "555-123-4567", "mobile": "555-987-6543"}
        result, report = anonymizer.anonymize_record(data)
        assert "phone" in report.fields_anonymized
        assert "mobile" in report.fields_anonymized

    def test_nested_dict_anonymization(self):
        """Test anonymization of nested dictionaries."""
        anonymizer = DataAnonymizer()
        data = {
            "id": "abc123",
            "subject": {
                "full_name": "John Smith",
                "email": "john@example.com",
            },
        }
        result, report = anonymizer.anonymize_record(data)
        assert result["id"] == "abc123"
        assert "full_name" in result["subject"]
        assert result["subject"]["full_name"] != "John Smith"

    def test_list_of_dicts_anonymization(self):
        """Test anonymization of list of dictionaries."""
        anonymizer = DataAnonymizer()
        data = {
            "contacts": [
                {"full_name": "John Smith", "email": "john@example.com"},
                {"full_name": "Jane Doe", "email": "jane@example.com"},
            ]
        }
        result, report = anonymizer.anonymize_record(data)
        assert len(result["contacts"]) == 2
        for contact in result["contacts"]:
            assert "full_name" in contact

    def test_result_has_original_hash(self):
        """Test that result includes original data hash."""
        anonymizer = DataAnonymizer()
        data = {"full_name": "John Smith"}
        _, report = anonymizer.anonymize_record(data)
        assert report.original_hash != ""
        assert len(report.original_hash) == 64  # SHA-256

    def test_result_has_anonymized_hash(self):
        """Test that result includes anonymized data hash."""
        anonymizer = DataAnonymizer()
        data = {"full_name": "John Smith"}
        _, report = anonymizer.anonymize_record(data)
        assert report.anonymized_hash != ""
        assert report.anonymized_hash != report.original_hash

    def test_result_tracks_methods_used(self):
        """Test that result tracks which methods were used."""
        anonymizer = DataAnonymizer()
        data = {"full_name": "John Smith", "ssn": "123-45-6789"}
        _, report = anonymizer.anonymize_record(data)
        assert "full_name" in report.methods_used
        assert "ssn" in report.methods_used

    def test_custom_rules_override_detection(self):
        """Test that custom rules override automatic detection."""
        anonymizer = DataAnonymizer()
        data = {"email": "john@example.com"}
        rules = {
            "email": AnonymizationRule("email", AnonymizationMethod.REDACTION),
        }
        result, report = anonymizer.anonymize_record(data, explicit_rules=rules)
        assert result["email"] == "[REDACTED]"
        assert report.methods_used["email"] == "redaction"


class TestPIIFieldPatterns:
    """Tests for PII field pattern detection."""

    def test_name_patterns(self):
        """Test name field patterns are detected."""
        anonymizer = DataAnonymizer()
        name_fields = [
            "full_name", "fullName", "first_name", "firstName",
            "last_name", "lastName", "middle_name", "middleName",
            "maiden_name", "name"
        ]
        for field in name_fields:
            method = anonymizer._detect_pii_field(field)
            assert method is not None, f"Field '{field}' not detected as PII"

    def test_id_patterns(self):
        """Test ID field patterns are detected."""
        anonymizer = DataAnonymizer()
        id_fields = ["ssn", "social_security", "passport", "driver_license", "ein"]
        for field in id_fields:
            method = anonymizer._detect_pii_field(field)
            assert method is not None, f"Field '{field}' not detected as PII"

    def test_contact_patterns(self):
        """Test contact field patterns are detected."""
        anonymizer = DataAnonymizer()
        contact_fields = ["email", "email_address", "phone", "telephone", "mobile"]
        for field in contact_fields:
            method = anonymizer._detect_pii_field(field)
            assert method is not None, f"Field '{field}' not detected as PII"

    def test_non_pii_not_detected(self):
        """Test non-PII fields are not detected."""
        anonymizer = DataAnonymizer()
        non_pii_fields = ["status", "count", "created_at", "id", "uuid", "type"]
        for field in non_pii_fields:
            method = anonymizer._detect_pii_field(field)
            assert method is None, f"Field '{field}' wrongly detected as PII"


class TestAnonymizationWithDataIds:
    """Tests for anonymization with data IDs and types."""

    def test_anonymize_with_data_id(self):
        """Test anonymization with data ID."""
        anonymizer = DataAnonymizer()
        data_id = uuid7()
        data = {"full_name": "John Smith"}
        _, report = anonymizer.anonymize_record(data, data_id=data_id)
        assert report.data_id == data_id

    def test_anonymize_with_data_type(self):
        """Test anonymization with data type."""
        anonymizer = DataAnonymizer()
        data = {"full_name": "John Smith"}
        _, report = anonymizer.anonymize_record(
            data,
            data_type=DataType.ENTITY_PROFILE,
        )
        assert report.data_type == DataType.ENTITY_PROFILE

    def test_result_timestamp(self):
        """Test that result has timestamp."""
        anonymizer = DataAnonymizer()
        data = {"full_name": "John Smith"}
        _, report = anonymizer.anonymize_record(data)
        assert isinstance(report.timestamp, datetime)


class TestRandomReplacement:
    """Tests for random replacement generation."""

    def test_generate_random_uppercase(self):
        """Test generating uppercase random string."""
        anonymizer = DataAnonymizer()
        result = anonymizer.generate_random_replacement("ABC", preserve_format=True)
        assert result.isupper()
        assert len(result) == 3

    def test_generate_random_lowercase(self):
        """Test generating lowercase random string."""
        anonymizer = DataAnonymizer()
        result = anonymizer.generate_random_replacement("abc", preserve_format=True)
        assert result.islower()
        assert len(result) == 3

    def test_generate_random_digits(self):
        """Test generating numeric random string."""
        anonymizer = DataAnonymizer()
        result = anonymizer.generate_random_replacement("123", preserve_format=True)
        assert result.isdigit()
        assert len(result) == 3

    def test_generate_random_default_length(self):
        """Test generating random string with default length."""
        anonymizer = DataAnonymizer()
        result = anonymizer.generate_random_replacement("test", preserve_format=False)
        # Default is 10 chars, but generate_random_replacement uses hex which gives length/2
        assert len(result) >= 5
