# Implementation Plan: Aggregator Search Engines (Sterling, HireRight, Checkr)

This document outlines the plan for integrating major background check aggregators as `SearchEngine` subclasses. These providers offer a broad suite of checks through a single API, making them ideal as foundational `Core` providers.

## 1. Class Structure

We will create a primary abstract base class `AggregatorSearchEngine` and then concrete implementations for each provider.

```python
from elile.search.base import SearchEngine, SearchResult

class AggregatorSearchEngine(SearchEngine):
    """Abstract base for full-suite background check aggregators."""
    
    # Common configuration for all aggregators
    # ...

class SterlingSearchEngine(AggregatorSearchEngine):
    provider_id = "sterling"
    tier_category = "core"
    
    async def execute_check(self, ...) -> SearchResult:
        # Sterling-specific implementation
        pass

class HireRightSearchEngine(AggregatorSearchEngine):
    provider_id = "hireright"
    tier_category = "core"

    async def execute_check(self, ...) -> SearchResult:
        # HireRight-specific implementation
        pass

class CheckrSearchEngine(AggregatorSearchEngine):
    provider_id = "checkr"
    tier_category = "core"

    async def execute_check(self, ...) -> SearchResult:
        # Checkr-specific implementation
        pass
```

## 2. Configuration Parameters

Each engine will require the following configuration parameters, managed via the application's settings:

| Parameter | Description | Example |
|---|---|---|
| `api_key` | The primary API key for authentication. | `sk_live_...` |
| `api_secret` | The API secret or client secret. | `a1b2c3d4...` |
| `api_base_url` | The base URL for the provider's API. | `https://api.checkr.com/v1/` |
| `webhook_secret` | Secret to verify incoming webhooks for async results. | `whsec_...` |
| `account_id` | Specific account or sub-account identifier, if applicable. | `acc_12345` |

These will be stored in the environment/secret manager, e.g., `STERLING_API_KEY`, `CHECKR_API_BASE_URL`.

## 3. API Details & Integration Flow

The general flow for these aggregators is similar:
1.  **Create Candidate/Subject**: Register the subject with the provider.
2.  **Order Report/Screening**: Initiate a set of checks (a "package").
3.  **Receive Webhooks**: Get notified as individual checks or the full report completes.
4.  **Fetch Results**: Retrieve the detailed results for each check.

### Checkr Example (Illustrative)

-   **API Documentation**: [https://docs.checkr.com/](https://docs.checkr.com/)
-   **Account Creation**: Requires signing up for a business account, which involves a sales and vetting process. A sandbox environment is available for development.
-   **Endpoints**:
    -   `POST /v1/candidates`: Create a candidate, receive a `candidate_id`.
    -   `POST /v1/reports`: Create a report, passing the `candidate_id` and a `package` name (e.g., `tasker_standard`). This initiates the screening.
    -   `GET /v1/reports/{report_id}`: Fetch the status and results of the report.
-   **Webhook Events**:
    -   `report.completed`: The entire report is finished.
    -   `report.adjudicated`: The report has been reviewed.
    -   `invitation.completed`: The candidate has submitted their PII.

## 4. `execute_check` Implementation Details

The `execute_check` method will orchestrate this flow:

1.  Check local cache for an existing `candidate_id` for the subject with this provider.
2.  If not found, call the "Create Candidate" endpoint and cache the ID.
3.  Map the `CheckType` from our system to the provider's `package` or equivalent concept. This mapping will be defined in a configuration file.
4.  Call the "Order Report" endpoint.
5.  Since results are asynchronous, the initial response will be `status: 'pending'`. The implementation will **not** wait. The screening engine will rely on a separate webhook ingestion service to receive the final results.
6.  The webhook handler will receive the `report.completed` event, fetch the full report data, normalize it into our `Finding` model, and store it in the `CachedDataSource`. It will then notify the main screening workflow (LangGraph) to proceed.

## 5. Data Normalization

The raw JSON response from each provider will be mapped to our internal `Finding` and `Entity` models. This is the most critical part of the implementation. A dedicated `normalizer` function will be created for each provider to handle their unique data structures for criminal records, employment history, etc.

**Example Normalization (`Checkr -> Finding`):**

```json
// Checkr Raw Data (Criminal Record)
{
  "id": "539fd88c424f7d9013000001",
  "status": "clear",
  "disposition": "clear",
  "charge": "Driving While Intoxicated",
  "sentence": "30 days jail (suspended), 1 year probation",
  "conviction_date": "2018-05-20",
  "court_jurisdiction": "Travis County, Texas"
}

// Normalized Elile Finding
{
  "finding_id": "...",
  "category": "criminal",
  "severity": "medium",
  "description": "Conviction: Driving While Intoxicated",
  "details": {
    "disposition": "conviction",
    "sentence": "30 days jail (suspended), 1 year probation",
    "date": "2018-05-20",
    "jurisdiction": "Travis County, Texas"
  },
  "source_provider": "checkr"
}
```

This ensures the rest of the system operates on a consistent data model, regardless of the underlying provider.
