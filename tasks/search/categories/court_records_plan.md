# Implementation Plan: Court Records Search Engines (PACER, CourtListener)

This document outlines the plan for integrating federal and state court record providers. These are `Core` data sources for criminal and civil litigation checks.

## 1. Class Structure

We will implement separate classes for federal and state-level searches. PACER is the primary source for federal records. For state records, we can use an aggregator like CourtListener or integrate with state-specific systems over time.

```python
from elile.search.base import SearchEngine, SearchResult

class CourtRecordSearchEngine(SearchEngine):
    """Abstract base for court record providers."""
    tier_category = "core"

class PacerSearchEngine(CourtRecordSearchEngine):
    """Searches the Public Access to Court Electronic Records (PACER) system for federal cases."""
    provider_id = "pacer"

    async def execute_check(self, ...) -> SearchResult:
        # PACER-specific implementation
        pass

class CourtListenerSearchEngine(CourtRecordSearchEngine):
    """Searches the CourtListener RECAP archive, which mirrors PACER and includes some state courts."""
    provider_id = "courtlistener"

    async def execute_check(self, ...) -> SearchResult:
        # CourtListener-specific implementation
        pass
```

## 2. Configuration Parameters

| Provider | Parameter | Description | Example |
|---|---|---|---|
| PACER | `username` | PACER account username. | `elile_user` |
| PACER | `password` | PACER account password. | `pacer_secret_pass` |
| PACER | `api_key` | API key for the Case Locator. | `pacer_api_key` |
| CourtListener | `api_key` | API token for the CourtListener API. | `Token 123abc...` |

These will be stored as secrets.

## 3. API Details & Integration Flow

### PACER

-   **API Documentation**: PACER has a legacy system and a newer API. We will target the **PACER Case Locator API**. Documentation is available upon registration.
-   **Account Creation**: Requires registering for a PACER account at [pacer.gov](https://pacer.gov/). This is an individual or corporate account. Billing is usage-based (per page/search).
-   **Integration Flow**:
    1.  Authenticate to get a session token.
    2.  Use the `find-party` endpoint, searching by name, and optionally DOB or SSN (if available).
    3.  The search returns a list of cases the party is involved in across all federal courts (District, Bankruptcy, Appellate).
    4.  For each relevant case, we must make subsequent calls to retrieve the **docket report**.
    5.  The docket report contains the list of all filings and events in the case. This must be parsed to determine the nature of the case (criminal/civil), its status, and the outcome.

### CourtListener

-   **API Documentation**: [https://www.courtlistener.com/api/](https://www.courtlistener.com/api/)
-   **Account Creation**: Sign up for an account on the website. An API key can be generated from the user profile. A free tier is available, but a paid subscription is necessary for production volume.
-   **Integration Flow**:
    1.  Use the `search` endpoint with a query string. Example: `q=party:"John Smith"`
    2.  The API supports filtering by jurisdiction, case type, and date.
    3.  The search results provide case metadata. We can then fetch detailed information, including docket entries and opinions.
    4.  CourtListener's data is scraped from PACER and other sources, so it may not be as real-time as a direct PACER search but is often cheaper and easier to work with.

## 4. `execute_check` Implementation Details

1.  The method will receive the subject's name and any known aliases. It will also use known addresses to narrow searches by jurisdiction (e.g., search federal courts in districts where the subject has lived).
2.  It will connect to the provider (PACER or CourtListener) and execute the search.
3.  The implementation must handle pagination of results.
4.  For each case returned, it will perform an initial filtering step to remove irrelevant cases (e.g., cases where the subject is a minor, or has a different middle name and address).
5.  For the remaining cases, it will fetch the detailed docket report.
6.  The raw docket text will be passed to a normalizer function.

## 5. Data Normalization

The core challenge is parsing the docket report to understand the case. This is often semi-structured text. An AI model (like Claude or GPT-4) is well-suited for this task.

**Example Normalization (`PACER Docket -> Finding`):**

**Raw Docket Entry:**
`10/25/2022  #53  JUDGMENT as to John Robert Smith (1), Count 1, Defendant is sentenced to 24 months imprisonment, 3 years supervised release, $100 special assessment. Signed by Judge Jane Doe.`

**AI-Powered Normalization Process:**
-   **Prompt**: "You are a legal analysis tool. Parse the following docket entry and extract the case outcome. Identify the charge, sentence, and date. Classify this as a criminal or civil matter."
-   **Input**: The raw docket entry text.
-   **AI Output (structured JSON)**:
    ```json
    {
      "case_type": "criminal",
      "disposition": "conviction",
      "charge": "Count 1 (charge details from elsewhere in docket)",
      "outcome_date": "2022-10-25",
      "sentence": {
        "imprisonment_months": 24,
        "supervised_release_years": 3,
        "special_assessment_usd": 100
      }
    }
    ```

**Final Elile Finding:**

```json
{
  "finding_id": "...",
  "category": "criminal",
  "severity": "critical",
  "description": "Conviction: 24 months imprisonment",
  "details": {
    "disposition": "conviction",
    "sentence": "24 months imprisonment, 3 years supervised release, $100 special assessment",
    "date": "2022-10-25",
    "jurisdiction": "PACER (Federal)"
  },
  "source_provider": "pacer"
}
```

This AI-assisted normalization is crucial for turning unstructured court records into actionable, structured `Finding` objects.
