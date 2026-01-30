# Implementation Plan: Corporate Intelligence Search Engines (OpenCorporates, Orbis)

This document outlines the plan for integrating corporate intelligence providers. These are `Premium` data sources used in the `Enhanced` tier, particularly for `D2` (Direct Connections) and `D3` (Extended Network) searches. They are essential for uncovering undisclosed business interests, mapping corporate networks, and identifying beneficial ownership.

## 1. Class Structure

We will create a base class and specific implementations for each provider.

```python
from elile.search.base import SearchEngine, SearchResult

class CorporateIntelligenceSearchEngine(SearchEngine):
    """Abstract base for corporate registry and beneficial ownership data providers."""
    tier_category = "premium"

class OpenCorporatesSearchEngine(CorporateIntelligenceSearchEngine):
    """Searches the OpenCorporates database of companies and officers."""
    provider_id = "open_corporates"

    async def execute_check(self, ...) -> SearchResult:
        pass

class OrbisSearchEngine(CorporateIntelligenceSearchEngine):
    """Searches the Bureau van Dijk Orbis database for comprehensive company data."""
    provider_id = "orbis"

    async def execute_check(self, ...) -> SearchResult:
        pass
```

## 2. Configuration Parameters

| Provider | Parameter | Description | Example |
|---|---|---|---|
| OpenCorporates | `api_key` | API token for OpenCorporates. | `oc_api_key...` |
| OpenCorporates | `api_endpoint` | Base URL for the API. | `https://api.opencorporates.com/v0.4/` |
| Orbis | `username` | Username for the Orbis API. | `elile_user` |
| Orbis | `password` | Password for the Orbis API. | `orbis_secret` |
| Orbis | `api_endpoint` | URL for the Orbis API. | `https://api.bvdinfo.com/` |

## 3. API Details & Integration Flow

### OpenCorporates

-   **API Documentation**: [https://api.opencorporates.com/documentation/API-Reference](https://api.opencorporates.com/documentation/API-Reference)
-   **Account Creation**: Requires a paid subscription. A free, rate-limited version is available for testing.
-   **Integration Flow**:
    1.  **Search Officers**: Use the `officers/search` endpoint to find individuals. The query can include the person's name and jurisdiction. `q=John Smith&jurisdiction_code=us_de`
    2.  The result is a list of officer roles matching the name. Each result links to a company.
    3.  **Get Company Details**: For each company the officer is associated with, call the `companies/{jurisdiction_code}/{company_number}` endpoint to get details about that company (status, address, other officers).
    4.  This allows us to build a network graph: Subject -> Officer Role -> Company -> Other Officers.

### Orbis (by Bureau van Dijk)

-   **API Documentation**: Access is restricted to enterprise customers.
-   **Account Creation**: Requires a very significant enterprise license. Orbis is one of the most comprehensive and expensive corporate data sources in the world.
-   **Integration Flow**:
    1.  Orbis APIs allow for complex searching for companies and individuals.
    2.  A key feature is searching for **Beneficial Ownership (UBO)**. We can search for a person and find companies where they are the ultimate beneficial owner, even through complex chains of shell companies.
    3.  The API can return full corporate trees, ownership percentages, and historical data.

## 4. `execute_check` Implementation Details

This engine is central to the `D2` and `D3` degree searches.

1.  The `execute_check` method is called with the subject's name.
2.  It queries the provider's "officer search" or "person search" endpoint.
3.  The results are a list of companies the subject is associated with.
4.  For each of these companies, the normalizer will create two things:
    -   An `Entity` object for the company.
    -   A `Finding` object describing the relationship.
5.  In a `D2` or `D3` search, the screening engine will take the newly discovered company `Entity` and add it to the queue of entities to be investigated, effectively expanding the search network.

## 5. Data Normalization

The normalizer translates the corporate data into our `Finding` and `Entity` models.

**Example Normalization (`OpenCorporates -> Finding`):**

**OpenCorporates Raw Result:**
```json
{
  "officer": {
    "name": "John Robert Smith",
    "position": "Director",
    "company": {
      "name": "Shady Holdings Inc.",
      "company_number": "12345",
      "jurisdiction_code": "us_de",
      "inactive": true,
      "dissolution_date": "2021-05-10"
    }
  }
}
```

**Generated Elile Finding:**
```json
{
  "finding_id": "...",
  "category": "network",
  "severity": "low", // Severity would be higher if the company was active or on a watchlist
  "description": "Subject was Director of 'Shady Holdings Inc.' (dissolved).",
  "details": {
    "entity_name": "Shady Holdings Inc.",
    "entity_type": "organization",
    "relationship": "Director",
    "status": "dissolved",
    "jurisdiction": "Delaware, US"
  },
  "source_provider": "open_corporates"
}
```

**Generated Elile Entity (for network expansion):**
```json
{
  "entity_id": "...",
  "entity_type": "organization",
  "canonical_identifiers": {
    "open_corporates_id": "us_de/12345"
  },
  "names": ["Shady Holdings Inc."],
  // ... other details
}
```

If the subject's name was found on the application, but this directorship was not, the normalizer would create an additional `high` severity `verification` finding for an **undisclosed business interest**. This is one of the most critical signals this search engine provides.
