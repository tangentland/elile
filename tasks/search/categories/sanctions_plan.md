# Implementation Plan: Sanctions & Watchlist Search Engines

This document outlines the plan for integrating Sanctions and Politically Exposed Persons (PEP) data sources. These are `Core` providers, critical for regulatory compliance (AML, KYC, anti-terrorism).

## 1. Class Structure

We will use a combination of direct government sources (OFAC) and commercial aggregators (World-Check).

```python
from elile.search.base import SearchEngine, SearchResult

class SanctionsSearchEngine(SearchEngine):
    """Abstract base for sanctions and watchlist providers."""
    tier_category = "core"

class OfacSearchEngine(SanctionsSearchEngine):
    """Searches the US Treasury's Office of Foreign Assets Control (OFAC) SDN list."""
    provider_id = "ofac_direct"

    async def execute_check(self, ...) -> SearchResult:
        # Implementation for OFAC's free, direct data feed.
        pass

class WorldCheckSearchEngine(SanctionsSearchEngine):
    """Searches the Refinitiv World-Check One API, a comprehensive aggregator."""
    provider_id = "world_check"

    async def execute_check(self, ...) -> SearchResult:
        # Implementation for the premium World-Check API.
        pass

class DowJonesSearchEngine(SanctionsSearchEngine):
    """Searches the Dow Jones Factiva/Risk & Compliance API."""
    provider_id = "dow_jones"

    async def execute_check(self, ...) -> SearchResult:
        # Implementation for the premium Dow Jones API.
        pass
```

## 2. Configuration Parameters

| Provider | Parameter | Description | Example |
|---|---|---|---|
| OFAC | `sdn_data_url` | URL to the latest OFAC SDN data file. | `https://www.treasury.gov/ofac/downloads/sdn.xml` |
| World-Check | `api_key` | API key for World-Check One. | `wc1_api_key...` |
| World-Check | `api_secret` | API secret for World-Check One. | `wc1_api_secret...` |
| World-Check | `api_endpoint` | Base URL for the API. | `https://api.refinitiv.com/world-check/v2/` |
| Dow Jones | `api_key` | API key for Dow Jones. | `dj_api_key...` |
| Dow Jones | `api_endpoint` | API endpoint. | `https://api.dowjones.com/risk/` |

## 3. API Details & Integration Flow

### OFAC Direct

-   **API/Data Feed**: OFAC provides its Specially Designated Nationals (SDN) list and other sanctions lists for free in various formats (XML, CSV). There is no real-time search API; instead, we must download the data and search it locally.
-   **Account Creation**: No account needed.
-   **Integration Flow**:
    1.  Create a background job that runs daily (or more frequently).
    2.  The job downloads the latest SDN list from the Treasury's URL.
    3.  The data is parsed and loaded into a dedicated, searchable data store (e.g., a specific PostgreSQL table, Elasticsearch index).
    4.  The `OfacSearchEngine.execute_check` method will then query this **local copy** of the data.
    5.  The search logic must be robust, using fuzzy name matching (e.g., Levenshtein distance) and checking against known aliases and DOBs.

### World-Check One

-   **API Documentation**: [https://developers.refinitiv.com/en/api-catalog/world-check-one/world-check-one-api](https://developers.refinitiv.com/en/api-catalog/world-check-one/world-check-one-api)
-   **Account Creation**: Requires a commercial subscription with Refinitiv, which is a significant enterprise expense. A sandbox is provided with the subscription.
-   **Integration Flow**:
    1.  Authenticate via OAuth to get a bearer token.
    2.  Use the `POST /cases` endpoint to create a screening case for the subject, providing their name, DOB, and country of residence.
    3.  The API returns a `caseId`.
    4.  Use `GET /cases/{caseId}/results` to retrieve the screening results. The API performs the fuzzy matching and returns potential hits.
    5.  The results include details on the matched entity, the list they appeared on (e.g., OFAC, EU Sanctions, Interpol), and why they were listed.

## 4. `execute_check` Implementation Details

-   **OFAC**: The method will perform a fuzzy search against our local database. It's fast and free but limited to OFAC lists and requires us to manage the data and search logic.
-   **World-Check**: The method will make a real-time API call to the World-Check service. This is slower and more expensive but provides much broader coverage (hundreds of global lists, PEPs, adverse media) and handles the complexities of fuzzy matching.

The system should be configured to use World-Check or Dow Jones as the primary provider, with the direct OFAC search as a fallback or for lower-tier services.

## 5. Data Normalization

Commercial providers like World-Check provide structured data that is relatively easy to normalize.

**Example Normalization (`World-Check -> Finding`):**

```json
// World-Check Raw Result
{
  "results": [
    {
      "referenceId": "e-12345",
      "matchedTerm": "John Robert Smith",
      "secondaryFields": [
        { "type": "DOB", "value": "1970-05-21" }
      ],
      "sources": [
        {
          "sourceName": "OFAC - Specially Designated Nationals List",
          "sourceType": "Sanctions"
        }
      ],
      "categories": ["SANCTION", "CRIME - TERRORISM"],
      "pepStatus": "null"
    }
  ]
}

// Normalized Elile Finding
{
  "finding_id": "...",
  "category": "regulatory",
  "severity": "critical",
  "description": "Sanctions Match: OFAC SDN List",
  "details": {
    "list": "OFAC - Specially Designated Nationals List",
    "match_confidence": 0.98,
    "categories": ["SANCTION", "CRIME - TERRORISM"],
    "matched_on": ["name", "dob"]
  },
  "source_provider": "world_check"
}
```

If the match includes a `pepStatus`, a separate `regulatory` finding with `severity: 'medium'` and description "Politically Exposed Person (PEP)" would be created. This distinction is important for risk analysis.
