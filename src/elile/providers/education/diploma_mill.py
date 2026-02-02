"""Diploma mill detection for education verification.

This module provides detection of diploma mills - unaccredited institutions
that offer fraudulent degrees with little or no academic requirements.
"""

import re
from difflib import SequenceMatcher

from .types import AccreditationType, Institution


class DiplomaMilDetector:
    """Detector for diploma mills and degree mills.

    Uses multiple strategies:
    - Known diploma mill database
    - Red flag pattern detection
    - Accreditation verification
    - Domain analysis

    Usage:
        detector = DiplomaMilDetector()
        flags = detector.check_institution("Belford University")
        if flags:
            print(f"Diploma mill detected: {flags}")
    """

    # Known diploma mills (sample - in production this would be a comprehensive database)
    KNOWN_DIPLOMA_MILLS: set[str] = {
        # US-based diploma mills
        "almeda university",
        "american coastline university",
        "ashwood university",
        "belford university",
        "breyer state university",
        "california pacific university",
        "clayton college of natural health",
        "concordia college and university",
        "corllins university",
        "frederick taylor university",
        "hamilton university",
        "hill university",
        "irish international university",
        "lacrosse university",
        "lexington university",
        "madison university",
        "nations university",
        "northfield university",
        "pacific western university",
        "palmetto college",
        "parkwood university",
        "preston university",
        "richmond university",
        "rochville university",
        "saint regis university",
        "shaftesbury university",
        "stanton university",
        "university of atlanta",
        "university of berkley",
        "university of devonshire",
        "university of dunham",
        "university of palmers green",
        "university of ravenhurst",
        "warren national university",
        "western states university",
        "wexford university",
        "wilshire university",
        "woodfield university",
        "yorker international university",
        # International diploma mills
        "adam smith university",
        "american world university",
        "bircham international university",
        "commonwealth open university",
        "kennedy western university",
        "university degree program",
    }

    # Suspicious domain patterns
    SUSPICIOUS_DOMAINS: list[str] = [
        r"\.edu\..*\..*",  # fake .edu subdomains
        r"accredited.*university",
        r"instant.*degree",
        r"fast.*degree",
        r"degree.*days",
        r"life.*experience.*degree",
    ]

    # Red flag patterns in institution names
    RED_FLAG_PATTERNS: list[tuple[str, str]] = [
        (r"university of \w+ online", "Generic 'University of X Online' pattern"),
        (r"american .* university$", "Generic 'American X University' pattern"),
        (r"international .* university$", "Generic 'International X University' pattern"),
        (r"online degree", "Mentions 'online degree' in name"),
        (r"diploma mill", "Contains 'diploma mill' term"),
        (r"accredited fast", "Claims fast accreditation"),
        (r"life experience", "Offers life experience degrees"),
        (r"degree in \d+ days?", "Promises degree in specific days"),
        (r"no classes required", "No classes required claim"),
        (r"instant degree", "Instant degree offer"),
    ]

    # Legitimate accreditation bodies
    LEGITIMATE_ACCREDITORS: set[str] = {
        # US Regional accreditors
        "higher learning commission",
        "hlc",
        "middle states commission on higher education",
        "msche",
        "new england commission of higher education",
        "neche",
        "northwest commission on colleges and universities",
        "nwccu",
        "southern association of colleges and schools",
        "sacscoc",
        "wasc senior college and university commission",
        "wscuc",
        # National accreditors
        "accrediting commission of career schools and colleges",
        "accsc",
        "distance education accrediting commission",
        "deac",
    }

    # Known fake accreditors
    FAKE_ACCREDITORS: set[str] = {
        "accreditation council for online academia",
        "central states consortium of colleges",
        "council on online education accreditation",
        "international accreditation association",
        "international accreditation organization",
        "national accreditation agency",
        "universal accreditation council",
        "world association of universities and colleges",
        "world online education accrediting commission",
    }

    def __init__(self) -> None:
        """Initialize the detector."""
        # Normalize known mills for matching
        self._normalized_mills = {self._normalize(name) for name in self.KNOWN_DIPLOMA_MILLS}

    def _normalize(self, name: str) -> str:
        """Normalize a name for comparison."""
        return re.sub(r"[^\w\s]", "", name.lower().strip())

    def check_institution(self, institution_name: str) -> list[str]:
        """Check if an institution appears to be a diploma mill.

        Args:
            institution_name: Name of the institution to check.

        Returns:
            List of flags/reasons if diploma mill detected, empty list if clean.
        """
        flags: list[str] = []
        normalized = self._normalize(institution_name)

        # Check against known diploma mills
        if normalized in self._normalized_mills:
            flags.append(f"Institution '{institution_name}' is in known diploma mill database")

        # Check for fuzzy matches against known mills
        # Use a high threshold (0.92) to avoid false positives on legitimate institutions
        for mill in self._normalized_mills:
            similarity = SequenceMatcher(None, normalized, mill).ratio()
            if similarity > 0.92 and normalized != mill:
                flags.append(f"Name very similar to known diploma mill: {mill} ({similarity:.0%})")
                break

        # Check red flag patterns
        name_lower = institution_name.lower()
        for pattern, description in self.RED_FLAG_PATTERNS:
            if re.search(pattern, name_lower, re.IGNORECASE):
                flags.append(f"Red flag pattern: {description}")

        return flags

    def check_accreditor(self, accreditor_name: str | None) -> list[str]:
        """Check if an accreditor is legitimate.

        Args:
            accreditor_name: Name of the accrediting body.

        Returns:
            List of flags if suspicious, empty list if legitimate or unknown.
        """
        if not accreditor_name:
            return []

        flags: list[str] = []
        normalized = self._normalize(accreditor_name)

        # Check against fake accreditors
        for fake in self.FAKE_ACCREDITORS:
            fake_normalized = self._normalize(fake)
            if normalized == fake_normalized:
                flags.append(f"Uses known fake accreditor: {accreditor_name}")
            elif SequenceMatcher(None, normalized, fake_normalized).ratio() > 0.85:
                flags.append(f"Accreditor name similar to known fake: {fake}")

        # Check if NOT a legitimate accreditor (only flag if claiming accreditation)
        is_legitimate = any(
            self._normalize(legit) in normalized or normalized in self._normalize(legit)
            for legit in self.LEGITIMATE_ACCREDITORS
        )

        if not is_legitimate and accreditor_name.strip():
            flags.append(f"Accreditor '{accreditor_name}' not recognized as legitimate")

        return flags

    def check_website(self, website: str | None) -> list[str]:
        """Check if a website has suspicious patterns.

        Args:
            website: Institution website URL.

        Returns:
            List of flags if suspicious, empty list if clean.
        """
        if not website:
            return []

        flags: list[str] = []
        website_lower = website.lower()

        # Check suspicious domain patterns
        for pattern in self.SUSPICIOUS_DOMAINS:
            if re.search(pattern, website_lower, re.IGNORECASE):
                flags.append(f"Suspicious website pattern detected: {pattern}")

        # Check for suspicious TLDs
        suspicious_tlds = [".ws", ".tk", ".ml", ".ga", ".cf"]
        for tld in suspicious_tlds:
            if website_lower.endswith(tld):
                flags.append(f"Uses suspicious TLD: {tld}")

        return flags

    def check_institution_full(self, institution: Institution) -> list[str]:
        """Perform comprehensive diploma mill check on an institution.

        Args:
            institution: Institution to check.

        Returns:
            List of all flags found.
        """
        flags: list[str] = []

        # Check institution name
        flags.extend(self.check_institution(institution.name))

        # Check aliases
        for alias in institution.aliases:
            alias_flags = self.check_institution(alias)
            for flag in alias_flags:
                flags.append(f"Alias check: {flag}")

        # Check accreditor
        flags.extend(self.check_accreditor(institution.accreditor_name))

        # Check website
        flags.extend(self.check_website(institution.website))

        # Check accreditation status
        if institution.accreditation == AccreditationType.UNACCREDITED:
            flags.append("Institution is unaccredited")
        elif institution.accreditation == AccreditationType.REVOKED:
            flags.append("Institution's accreditation has been revoked")

        # Check if explicitly flagged
        if institution.is_diploma_mill:
            flags.append("Institution is flagged as diploma mill in database")

        return list(set(flags))  # Remove duplicates


def create_diploma_mill_detector() -> DiplomaMilDetector:
    """Factory function to create a DiplomaMilDetector.

    Returns:
        Configured DiplomaMilDetector instance.
    """
    return DiplomaMilDetector()


# Convenience function
def is_diploma_mill(institution_name: str) -> tuple[bool, list[str]]:
    """Quick check if an institution name appears to be a diploma mill.

    Args:
        institution_name: Name to check.

    Returns:
        Tuple of (is_diploma_mill, list_of_flags).
    """
    detector = DiplomaMilDetector()
    flags = detector.check_institution(institution_name)
    return len(flags) > 0, flags
