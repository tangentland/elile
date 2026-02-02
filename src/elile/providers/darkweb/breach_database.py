"""Breach database for dark web monitoring.

This module provides a database of known data breaches and compromised
credential sources for reference in dark web monitoring.
"""

from datetime import datetime

from .types import BreachInfo


class BreachDatabase:
    """Database of known data breaches.

    Provides lookup and matching capabilities for known breach events.
    In production, this would be populated from breach notification services
    and regularly updated.

    Usage:
        db = BreachDatabase()
        breaches = db.search_by_domain("linkedin.com")
        breach = db.get_breach("linkedin_2021")
    """

    # Sample breach database (in production, would be dynamically loaded)
    KNOWN_BREACHES: dict[str, BreachInfo] = {
        "linkedin_2021": BreachInfo(
            breach_id="linkedin_2021",
            breach_name="LinkedIn 2021",
            breach_date=datetime(2021, 4, 1),
            discovered_date=datetime(2021, 6, 22),
            source_company="LinkedIn",
            records_affected=700000000,
            data_types=["email", "full_name", "phone", "workplace", "education"],
            is_verified=True,
            breach_description="Scraped data of 700M LinkedIn users posted for sale",
        ),
        "facebook_2019": BreachInfo(
            breach_id="facebook_2019",
            breach_name="Facebook 2019",
            breach_date=datetime(2019, 4, 1),
            discovered_date=datetime(2021, 4, 3),
            source_company="Facebook/Meta",
            records_affected=533000000,
            data_types=["email", "phone", "full_name", "location", "birth_date"],
            is_verified=True,
            breach_description="Data of 533M users exposed including phone numbers",
        ),
        "adobe_2013": BreachInfo(
            breach_id="adobe_2013",
            breach_name="Adobe 2013",
            breach_date=datetime(2013, 10, 1),
            discovered_date=datetime(2013, 10, 3),
            source_company="Adobe",
            records_affected=153000000,
            data_types=["email", "password_hash", "username"],
            is_verified=True,
            breach_description="153M accounts with poorly encrypted passwords",
        ),
        "dropbox_2012": BreachInfo(
            breach_id="dropbox_2012",
            breach_name="Dropbox 2012",
            breach_date=datetime(2012, 7, 1),
            discovered_date=datetime(2016, 8, 1),
            source_company="Dropbox",
            records_affected=68000000,
            data_types=["email", "password_hash"],
            is_verified=True,
            breach_description="68M account credentials leaked",
        ),
        "equifax_2017": BreachInfo(
            breach_id="equifax_2017",
            breach_name="Equifax 2017",
            breach_date=datetime(2017, 5, 13),
            discovered_date=datetime(2017, 9, 7),
            source_company="Equifax",
            records_affected=147900000,
            data_types=["ssn", "birth_date", "address", "drivers_license"],
            is_verified=True,
            breach_description="Major breach exposing SSNs and financial data",
        ),
        "yahoo_2013": BreachInfo(
            breach_id="yahoo_2013",
            breach_name="Yahoo 2013-2014",
            breach_date=datetime(2013, 8, 1),
            discovered_date=datetime(2016, 9, 22),
            source_company="Yahoo",
            records_affected=3000000000,
            data_types=["email", "password_hash", "security_questions"],
            is_verified=True,
            breach_description="Largest known breach affecting 3B accounts",
        ),
        "marriott_2018": BreachInfo(
            breach_id="marriott_2018",
            breach_name="Marriott/Starwood 2018",
            breach_date=datetime(2014, 1, 1),
            discovered_date=datetime(2018, 11, 30),
            source_company="Marriott International",
            records_affected=500000000,
            data_types=["name", "email", "phone", "passport", "payment_card"],
            is_verified=True,
            breach_description="Guest reservation database compromised",
        ),
        "twitter_2022": BreachInfo(
            breach_id="twitter_2022",
            breach_name="Twitter 2022",
            breach_date=datetime(2022, 1, 1),
            discovered_date=datetime(2022, 7, 21),
            source_company="Twitter",
            records_affected=5400000,
            data_types=["email", "phone", "twitter_handle"],
            is_verified=True,
            breach_description="API vulnerability exposed user contact info",
        ),
        "capital_one_2019": BreachInfo(
            breach_id="capital_one_2019",
            breach_name="Capital One 2019",
            breach_date=datetime(2019, 3, 1),
            discovered_date=datetime(2019, 7, 29),
            source_company="Capital One",
            records_affected=106000000,
            data_types=["ssn", "bank_account", "credit_score", "address"],
            is_verified=True,
            breach_description="AWS misconfiguration exposed customer data",
        ),
        "experian_2020": BreachInfo(
            breach_id="experian_2020",
            breach_name="Experian Brazil 2020",
            breach_date=datetime(2020, 1, 1),
            discovered_date=datetime(2021, 1, 19),
            source_company="Experian",
            records_affected=220000000,
            data_types=["cpf", "name", "address", "income", "credit_score"],
            is_verified=True,
            breach_description="Brazilian consumer credit data exposed",
        ),
    }

    # Domain to breach mapping
    DOMAIN_MAPPINGS: dict[str, list[str]] = {
        "linkedin.com": ["linkedin_2021"],
        "facebook.com": ["facebook_2019"],
        "adobe.com": ["adobe_2013"],
        "dropbox.com": ["dropbox_2012"],
        "equifax.com": ["equifax_2017"],
        "yahoo.com": ["yahoo_2013"],
        "marriott.com": ["marriott_2018"],
        "starwood.com": ["marriott_2018"],
        "twitter.com": ["twitter_2022"],
        "capitalone.com": ["capital_one_2019"],
        "experian.com": ["experian_2020"],
    }

    def __init__(self) -> None:
        """Initialize the breach database."""
        self._breaches = self.KNOWN_BREACHES.copy()
        self._domain_map = self.DOMAIN_MAPPINGS.copy()

    def get_breach(self, breach_id: str) -> BreachInfo | None:
        """Get a breach by ID.

        Args:
            breach_id: The breach identifier.

        Returns:
            BreachInfo if found, None otherwise.
        """
        return self._breaches.get(breach_id)

    def search_by_domain(self, domain: str) -> list[BreachInfo]:
        """Search for breaches by domain.

        Args:
            domain: Domain to search for (e.g., "linkedin.com").

        Returns:
            List of matching BreachInfo objects.
        """
        domain_lower = domain.lower().strip()
        breach_ids = self._domain_map.get(domain_lower, [])
        return [self._breaches[bid] for bid in breach_ids if bid in self._breaches]

    def search_by_company(self, company_name: str) -> list[BreachInfo]:
        """Search for breaches by company name.

        Args:
            company_name: Company name to search for.

        Returns:
            List of matching BreachInfo objects.
        """
        company_lower = company_name.lower().strip()
        matches = []
        for breach in self._breaches.values():
            if breach.source_company and company_lower in breach.source_company.lower():
                matches.append(breach)
        return matches

    def search_by_data_type(self, data_type: str) -> list[BreachInfo]:
        """Search for breaches containing a specific data type.

        Args:
            data_type: Type of data to search for (e.g., "ssn", "email").

        Returns:
            List of matching BreachInfo objects.
        """
        data_type_lower = data_type.lower().strip()
        matches = []
        for breach in self._breaches.values():
            if data_type_lower in [dt.lower() for dt in breach.data_types]:
                matches.append(breach)
        return matches

    def get_all_breaches(self) -> list[BreachInfo]:
        """Get all breaches in the database.

        Returns:
            List of all BreachInfo objects.
        """
        return list(self._breaches.values())

    def get_breaches_after(self, after_date: datetime) -> list[BreachInfo]:
        """Get breaches that occurred after a specific date.

        Args:
            after_date: The cutoff date.

        Returns:
            List of BreachInfo objects occurring after the date.
        """
        matches = []
        for breach in self._breaches.values():
            if breach.breach_date and breach.breach_date > after_date:
                matches.append(breach)
        return matches

    def get_breaches_with_ssn(self) -> list[BreachInfo]:
        """Get breaches that exposed SSN data.

        Returns:
            List of BreachInfo objects containing SSN exposure.
        """
        return self.search_by_data_type("ssn")

    def get_breach_count(self) -> int:
        """Get total number of breaches in database.

        Returns:
            Number of breaches.
        """
        return len(self._breaches)

    def get_total_records_affected(self) -> int:
        """Get total records affected across all breaches.

        Returns:
            Total records affected.
        """
        return sum(b.records_affected for b in self._breaches.values() if b.records_affected)


def create_breach_database() -> BreachDatabase:
    """Factory function to create a BreachDatabase.

    Returns:
        Configured BreachDatabase instance.
    """
    return BreachDatabase()
