"""Unit tests for core exceptions."""

from datetime import datetime, timedelta, timezone
from uuid import uuid7

import pytest

from elile.core.exceptions import (
    BudgetExceededError,
    ComplianceError,
    ConsentExpiredError,
    ConsentScopeError,
    ContextNotSetError,
)
from elile.utils.exceptions import ElileError


class TestExceptionHierarchy:
    """Tests for exception inheritance."""

    def test_context_not_set_error_is_elile_error(self):
        """Test ContextNotSetError inherits from ElileError."""
        error = ContextNotSetError()
        assert isinstance(error, ElileError)
        assert isinstance(error, Exception)

    def test_compliance_error_is_elile_error(self):
        """Test ComplianceError inherits from ElileError."""
        error = ComplianceError("test", check_type="identity", locale="US")
        assert isinstance(error, ElileError)

    def test_budget_exceeded_error_is_elile_error(self):
        """Test BudgetExceededError inherits from ElileError."""
        error = BudgetExceededError("test", cost=10.0, budget_limit=100.0, accumulated=95.0)
        assert isinstance(error, ElileError)

    def test_consent_expired_error_is_elile_error(self):
        """Test ConsentExpiredError inherits from ElileError."""
        error = ConsentExpiredError(
            "test", consent_token=uuid7(), expiry=datetime.now(timezone.utc)
        )
        assert isinstance(error, ElileError)

    def test_consent_scope_error_is_elile_error(self):
        """Test ConsentScopeError inherits from ElileError."""
        error = ConsentScopeError("test", required_scope="criminal", granted_scope={"identity"})
        assert isinstance(error, ElileError)


class TestContextNotSetError:
    """Tests for ContextNotSetError."""

    def test_default_message(self):
        """Test default error message."""
        error = ContextNotSetError()
        assert "Request context is not set" in str(error)

    def test_custom_message(self):
        """Test custom error message."""
        error = ContextNotSetError("Custom context error")
        assert "Custom context error" in str(error)

    def test_can_be_caught_as_base(self):
        """Test can be caught as ElileError."""
        with pytest.raises(ElileError):
            raise ContextNotSetError()


class TestComplianceError:
    """Tests for ComplianceError."""

    def test_attributes(self):
        """Test ComplianceError attributes."""
        error = ComplianceError(
            "Criminal checks not allowed in EU",
            check_type="criminal_records",
            locale="EU",
        )

        assert error.check_type == "criminal_records"
        assert error.locale == "EU"
        assert "Criminal checks not allowed" in error.args[0]

    def test_str_representation(self):
        """Test string representation includes all info."""
        error = ComplianceError(
            "Check not permitted",
            check_type="financial",
            locale="DE",
        )

        str_repr = str(error)
        assert "DE" in str_repr
        assert "financial" in str_repr
        assert "ComplianceError" in str_repr

    def test_different_locales(self):
        """Test with different locale values."""
        us_error = ComplianceError("US error", check_type="credit", locale="US")
        eu_error = ComplianceError("EU error", check_type="credit", locale="EU")
        ca_error = ComplianceError("CA error", check_type="credit", locale="CA")

        assert us_error.locale == "US"
        assert eu_error.locale == "EU"
        assert ca_error.locale == "CA"


class TestBudgetExceededError:
    """Tests for BudgetExceededError."""

    def test_attributes(self):
        """Test BudgetExceededError attributes."""
        error = BudgetExceededError(
            "Operation would exceed budget",
            cost=25.0,
            budget_limit=100.0,
            accumulated=80.0,
        )

        assert error.cost == 25.0
        assert error.budget_limit == 100.0
        assert error.accumulated == 80.0

    def test_str_representation(self):
        """Test string representation shows all values."""
        error = BudgetExceededError(
            "Budget exceeded",
            cost=50.0,
            budget_limit=200.0,
            accumulated=175.0,
        )

        str_repr = str(error)
        assert "50" in str_repr
        assert "200" in str_repr
        assert "175" in str_repr
        assert "BudgetExceededError" in str_repr

    def test_zero_values(self):
        """Test with zero budget values."""
        error = BudgetExceededError(
            "Any cost exceeds zero budget",
            cost=0.01,
            budget_limit=0.0,
            accumulated=0.0,
        )

        assert error.cost == 0.01
        assert error.budget_limit == 0.0
        assert error.accumulated == 0.0

    def test_float_precision(self):
        """Test float values maintain precision."""
        error = BudgetExceededError(
            "Precise amounts",
            cost=0.123456789,
            budget_limit=100.987654321,
            accumulated=99.111111111,
        )

        assert error.cost == 0.123456789
        assert error.budget_limit == 100.987654321
        assert error.accumulated == 99.111111111


class TestConsentExpiredError:
    """Tests for ConsentExpiredError."""

    def test_attributes_with_uuid(self):
        """Test ConsentExpiredError with UUID consent token."""
        consent_token = uuid7()
        expiry = datetime.now(timezone.utc) - timedelta(hours=1)

        error = ConsentExpiredError(
            "Consent has expired",
            consent_token=consent_token,
            expiry=expiry,
        )

        assert error.consent_token == consent_token
        assert error.expiry == expiry

    def test_attributes_with_string_token(self):
        """Test ConsentExpiredError with string consent token."""
        consent_token = "CONSENT-12345"
        expiry = datetime.now(timezone.utc)

        error = ConsentExpiredError(
            "Consent expired",
            consent_token=consent_token,
            expiry=expiry,
        )

        assert error.consent_token == "CONSENT-12345"

    def test_str_representation(self):
        """Test string representation."""
        consent_token = uuid7()
        expiry = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        error = ConsentExpiredError(
            "Expired",
            consent_token=consent_token,
            expiry=expiry,
        )

        str_repr = str(error)
        assert str(consent_token) in str_repr
        assert "2026" in str_repr
        assert "ConsentExpiredError" in str_repr

    def test_timezone_aware_expiry(self):
        """Test with timezone-aware datetime."""
        expiry = datetime(2026, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        error = ConsentExpiredError("Expired", consent_token=uuid7(), expiry=expiry)

        assert error.expiry.tzinfo is not None


class TestConsentScopeError:
    """Tests for ConsentScopeError."""

    def test_attributes(self):
        """Test ConsentScopeError attributes."""
        error = ConsentScopeError(
            "Data type not in scope",
            required_scope="criminal_records",
            granted_scope={"identity", "employment", "education"},
        )

        assert error.required_scope == "criminal_records"
        assert error.granted_scope == {"identity", "employment", "education"}

    def test_str_representation(self):
        """Test string representation shows scope info."""
        error = ConsentScopeError(
            "Scope mismatch",
            required_scope="financial",
            granted_scope={"identity", "background"},
        )

        str_repr = str(error)
        assert "financial" in str_repr
        assert "identity" in str_repr or "background" in str_repr
        assert "ConsentScopeError" in str_repr

    def test_empty_granted_scope(self):
        """Test with empty granted scope."""
        error = ConsentScopeError(
            "No scope granted",
            required_scope="identity",
            granted_scope=set(),
        )

        assert error.granted_scope == set()
        assert "[]" in str(error)  # sorted empty set

    def test_single_granted_scope(self):
        """Test with single scope in granted set."""
        error = ConsentScopeError(
            "Limited scope",
            required_scope="criminal",
            granted_scope={"identity"},
        )

        assert error.granted_scope == {"identity"}

    def test_large_granted_scope(self):
        """Test with many scopes in granted set."""
        large_scope = {f"scope_{i}" for i in range(10)}
        error = ConsentScopeError(
            "Large scope",
            required_scope="not_in_scope",
            granted_scope=large_scope,
        )

        assert error.granted_scope == large_scope


class TestExceptionRaising:
    """Tests for raising and catching exceptions."""

    def test_raise_and_catch_context_not_set(self):
        """Test raising and catching ContextNotSetError."""
        try:
            raise ContextNotSetError("Test")
        except ContextNotSetError as e:
            assert "Test" in str(e)

    def test_raise_and_catch_compliance_error(self):
        """Test raising and catching ComplianceError."""
        try:
            raise ComplianceError("Not allowed", check_type="credit", locale="EU")
        except ComplianceError as e:
            assert e.check_type == "credit"
            assert e.locale == "EU"

    def test_catch_as_elile_error(self):
        """Test all exceptions can be caught as ElileError."""
        exceptions = [
            ContextNotSetError(),
            ComplianceError("test", check_type="x", locale="US"),
            BudgetExceededError("test", cost=1, budget_limit=0, accumulated=0),
            ConsentExpiredError("test", consent_token=uuid7(), expiry=datetime.now(timezone.utc)),
            ConsentScopeError("test", required_scope="x", granted_scope=set()),
        ]

        for exc in exceptions:
            with pytest.raises(ElileError):
                raise exc

    def test_exception_with_traceback(self):
        """Test exceptions preserve traceback."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as original:
                raise ComplianceError(
                    "Compliance failure", check_type="test", locale="US"
                ) from original
        except ComplianceError as e:
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ValueError)
