"""Tests for dark web breach database."""

from datetime import datetime

import pytest

from elile.providers.darkweb.breach_database import (
    BreachDatabase,
    create_breach_database,
)


class TestBreachDatabase:
    """Tests for BreachDatabase class."""

    @pytest.fixture
    def db(self) -> BreachDatabase:
        """Create a breach database instance."""
        return BreachDatabase()

    def test_database_has_breaches(self, db: BreachDatabase) -> None:
        """Test that database has known breaches."""
        count = db.get_breach_count()
        assert count > 0

    def test_get_breach_linkedin(self, db: BreachDatabase) -> None:
        """Test getting LinkedIn breach."""
        breach = db.get_breach("linkedin_2021")
        assert breach is not None
        assert breach.breach_name == "LinkedIn 2021"
        assert breach.source_company == "LinkedIn"
        assert breach.records_affected == 700000000

    def test_get_breach_facebook(self, db: BreachDatabase) -> None:
        """Test getting Facebook breach."""
        breach = db.get_breach("facebook_2019")
        assert breach is not None
        assert breach.breach_name == "Facebook 2019"
        assert "phone" in breach.data_types

    def test_get_breach_not_found(self, db: BreachDatabase) -> None:
        """Test getting non-existent breach."""
        breach = db.get_breach("nonexistent_breach")
        assert breach is None

    def test_search_by_domain_linkedin(self, db: BreachDatabase) -> None:
        """Test searching by LinkedIn domain."""
        breaches = db.search_by_domain("linkedin.com")
        assert len(breaches) > 0
        assert breaches[0].breach_name == "LinkedIn 2021"

    def test_search_by_domain_case_insensitive(self, db: BreachDatabase) -> None:
        """Test domain search is case insensitive."""
        breaches = db.search_by_domain("LINKEDIN.COM")
        assert len(breaches) > 0

    def test_search_by_domain_not_found(self, db: BreachDatabase) -> None:
        """Test searching non-existent domain."""
        breaches = db.search_by_domain("unknown-domain.com")
        assert len(breaches) == 0

    def test_search_by_company_adobe(self, db: BreachDatabase) -> None:
        """Test searching by company name."""
        breaches = db.search_by_company("Adobe")
        assert len(breaches) > 0
        assert any(b.breach_id == "adobe_2013" for b in breaches)

    def test_search_by_company_case_insensitive(self, db: BreachDatabase) -> None:
        """Test company search is case insensitive."""
        breaches = db.search_by_company("adobe")
        assert len(breaches) > 0

    def test_search_by_company_partial(self, db: BreachDatabase) -> None:
        """Test partial company name search."""
        breaches = db.search_by_company("Capital")
        assert len(breaches) > 0
        assert any("Capital One" in (b.source_company or "") for b in breaches)

    def test_search_by_data_type_email(self, db: BreachDatabase) -> None:
        """Test searching by data type."""
        breaches = db.search_by_data_type("email")
        assert len(breaches) > 0

    def test_search_by_data_type_ssn(self, db: BreachDatabase) -> None:
        """Test searching for SSN breaches."""
        breaches = db.search_by_data_type("ssn")
        assert len(breaches) > 0
        # Equifax breach should be in SSN results
        assert any(b.breach_id == "equifax_2017" for b in breaches)

    def test_get_all_breaches(self, db: BreachDatabase) -> None:
        """Test getting all breaches."""
        breaches = db.get_all_breaches()
        assert len(breaches) == db.get_breach_count()

    def test_get_breaches_after_date(self, db: BreachDatabase) -> None:
        """Test getting breaches after a date."""
        cutoff = datetime(2020, 1, 1)
        breaches = db.get_breaches_after(cutoff)

        # All returned breaches should be after cutoff
        for breach in breaches:
            if breach.breach_date:
                assert breach.breach_date > cutoff

    def test_get_breaches_with_ssn(self, db: BreachDatabase) -> None:
        """Test getting breaches with SSN exposure."""
        breaches = db.get_breaches_with_ssn()
        assert len(breaches) > 0

        for breach in breaches:
            assert "ssn" in [dt.lower() for dt in breach.data_types]

    def test_get_total_records_affected(self, db: BreachDatabase) -> None:
        """Test getting total records affected."""
        total = db.get_total_records_affected()
        assert total > 0
        # Should be in the billions given the known breaches
        assert total > 1000000000


class TestKnownBreaches:
    """Tests for specific known breaches."""

    @pytest.fixture
    def db(self) -> BreachDatabase:
        """Create a breach database instance."""
        return BreachDatabase()

    @pytest.mark.parametrize(
        "breach_id,expected_company",
        [
            ("linkedin_2021", "LinkedIn"),
            ("facebook_2019", "Facebook/Meta"),
            ("adobe_2013", "Adobe"),
            ("dropbox_2012", "Dropbox"),
            ("equifax_2017", "Equifax"),
            ("yahoo_2013", "Yahoo"),
            ("marriott_2018", "Marriott International"),
            ("twitter_2022", "Twitter"),
            ("capital_one_2019", "Capital One"),
        ],
    )
    def test_known_breaches_exist(
        self, db: BreachDatabase, breach_id: str, expected_company: str
    ) -> None:
        """Test that known breaches exist and have correct company."""
        breach = db.get_breach(breach_id)
        assert breach is not None, f"Breach {breach_id} should exist"
        assert breach.source_company == expected_company

    def test_yahoo_is_largest(self, db: BreachDatabase) -> None:
        """Test that Yahoo breach is the largest."""
        yahoo = db.get_breach("yahoo_2013")
        all_breaches = db.get_all_breaches()

        assert yahoo is not None
        assert yahoo.records_affected is not None

        for breach in all_breaches:
            if breach.records_affected and breach.breach_id != "yahoo_2013":
                assert yahoo.records_affected >= breach.records_affected

    def test_equifax_has_sensitive_data(self, db: BreachDatabase) -> None:
        """Test that Equifax breach has sensitive data types."""
        equifax = db.get_breach("equifax_2017")
        assert equifax is not None

        sensitive_types = ["ssn", "birth_date", "drivers_license"]
        for data_type in sensitive_types:
            assert data_type in equifax.data_types


class TestCreateBreachDatabase:
    """Tests for create_breach_database factory function."""

    def test_create_database(self) -> None:
        """Test creating a breach database."""
        db = create_breach_database()
        assert isinstance(db, BreachDatabase)
        assert db.get_breach_count() > 0
