# Implementation Plan: Location Intelligence Search Engines (Foursquare, SafeGraph)

This document outlines the plan for integrating location intelligence providers. These are `Premium` data sources used in the `Enhanced` tier. This data is extremely sensitive and its use is subject to the highest level of consent and compliance scrutiny. It is used to analyze patterns of movement for subjects in high-security roles.

## 1. Class Structure

A base class will enforce the strict consent requirements.

```python
from elile.search.base import SearchEngine, SearchResult
from elile.compliance import consent_manager

class LocationIntelligenceSearchEngine(SearchEngine):
    """Abstract base for location and movement data providers."""
    
    tier_category = "premium"

    async def execute_check(self, check_type, subject, locale, **kwargs) -> SearchResult:
        # 1. Verify explicit, specific consent for location data was given.
        # This must be a separate, opt-in consent beyond the standard screening.
        consent_manager.verify_consent_for_location_data(subject.consent)

        # 2. Call the provider-specific implementation
        return await self._provider_execute(check_type, subject, locale, **kwargs)

    async def _provider_execute(self, ...):
        raise NotImplementedError

class FoursquareSearchEngine(LocationIntelligenceSearchEngine):
    provider_id = "foursquare"
    
    async def _provider_execute(self, ...):
        # Foursquare-specific API calls
        pass

class SafeGraphSearchEngine(LocationIntelligenceSearchEngine):
    provider_id = "safegraph"

    async def _provider_execute(self, ...):
        # SafeGraph-specific data access
        pass
```

## 2. Configuration Parameters

| Parameter | Description | Example |
|---|---|---|
| `api_key` | API key for the provider. | `fsq_api_key...` |
| `api_endpoint` | Base URL for the API. | `https://api.foursquare.com/v3/` |
| `safegraph_s3_bucket` | S3 bucket for SafeGraph data delivery. | `s3://safegraph-data-share` |
| `safegraph_aws_role` | IAM role to assume for S3 access. | `arn:aws:iam::123:role/SafeGraphAccess` |

## 3. API Details & Integration Flow

Accessing this data is complex and typically involves matching our subject's identifiers against the provider's dataset. The "raw" data is often mobile advertising IDs (MAIDs), which we must first link to our subject via an identity resolution provider.

### Foursquare

-   **API Documentation**: [https://location.foursquare.com/developer/](https://location.foursquare.com/developer/)
-   **Account Creation**: Enterprise sales process. Use case is heavily vetted for privacy compliance.
-   **Integration Flow**:
    1.  **Offline Match**: We provide Foursquare with a list of our subjects' PII (e.g., hashed emails, phone numbers).
    2.  Foursquare matches this against their identity graph and provides us with the corresponding Foursquare User IDs. This is a privacy-preserving join.
    3.  **API Query**: We can then use the `GET /users/{USER_ID}/visits` endpoint to retrieve a history of venue visits for that user.
    4.  The data includes venue name, category, address, and timestamp.

### SafeGraph

-   **Data Delivery**: SafeGraph typically delivers data in bulk files via an AWS S3 data share, not a real-time API.
-   **Account Creation**: Enterprise sales process.
-   **Integration Flow**:
    1.  **Offline Match**: Similar to Foursquare, we would work with SafeGraph or a third-party data onboarder (like LiveRamp) to match our subjects' PII to MAIDs in the SafeGraph dataset.
    2.  **Data Ingestion**: We would set up a data pipeline to ingest SafeGraph's "Patterns" dataset, which contains aggregated foot traffic data for millions of points of interest (POIs).
    3.  **Querying**: We would query our local copy of this data, filtering for the MAIDs corresponding to our subject to see which POIs they have visited.

## 4. `execute_check` Implementation Details

1.  The method will first ensure it has a mobile identifier (MAID or Foursquare ID) for the subject, likely retrieved from a prior call to an identity resolution provider.
2.  If no identifier is available, the check cannot be performed and will return an empty result.
3.  **Foursquare**: It will make a direct API call to the `visits` endpoint.
4.  **SafeGraph**: It will query our internal data warehouse where the SafeGraph data has been ingested.
5.  The results (a list of venue visits over a specific time period) will be passed to the normalizer.

## 5. Data Normalization

The goal is not to track every movement, but to identify patterns that may be relevant to risk. The normalizer will categorize visits and look for significant signals.

**Example Normalization (`Foursquare -> Finding`):**

**Foursquare Raw Result (list of visits):**
```json
[
  { "venue": { "name": "Casino Royale", "category": "Casino" }, "timestamp": "..." },
  { "venue": { "name": "Shady Loans Inc.", "category": "Payday Loans" }, "timestamp": "..." },
  { "venue": { "name": "Embassy of Foreign Country X", "category": "Embassy" }, "timestamp": "..." },
  { "venue": { "name": "Main Street Church", "category": "Church" }, "timestamp": "..." }
]
```

**Normalization Logic & Generated Findings:**
The normalizer uses a mapping of venue categories to risk indicators.

-   `"Casino"` -> Frequent visits could indicate gambling habits.
-   `"Payday Loans"` -> Could indicate financial distress.
-   `"Embassy"` -> Visits to embassies of countries of concern could be a major security risk.
-   `"Church"` -> This is a **protected category**. The compliance rules in the base class should already prevent this data from being used, but the normalizer provides a second line of defense and **must discard this visit**.

```json
[
  {
    "finding_id": "...",
    "category": "behavioral",
    "severity": "medium",
    "description": "Location Pattern: Frequent visits to casinos.",
    "details": { "venue_category": "Casino", "visit_count": 5, "time_period": "last_30_days" },
    "source_provider": "foursquare"
  },
  {
    "finding_id": "...",
    "category": "behavioral",
    "severity": "high",
    "description": "Location Pattern: Visit to a high-risk financial institution.",
    "details": { "venue_name": "Shady Loans Inc.", "venue_category": "Payday Loans" },
    "source_provider": "foursquare"
  },
  {
    "finding_id": "...",
    "category": "security",
    "severity": "critical",
    "description": "Location Pattern: Visit to a foreign government facility.",
    "details": { "venue_name": "Embassy of Foreign Country X" },
    "source_provider": "foursquare"
  }
]
```

These findings provide powerful, context-rich signals to a human investigator in the `Enhanced` tier. They are never used for automated decision-making.
