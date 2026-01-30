# Implementation Plan: Data Broker Search Engines (Acxiom, Oracle Data Cloud)

This document outlines the plan for integrating major data brokers. These are `Premium` data sources used in the `Enhanced` tier to gather behavioral, demographic, and interest-based data on a subject. Use of this data is subject to strict compliance rules.

## 1. Class Structure

We will create a base class to handle common compliance and consent checks, with specific implementations for each broker.

```python
from elile.search.base import SearchEngine, SearchResult
from elile.compliance import consent_manager

class DataBrokerSearchEngine(SearchEngine):
    """Abstract base for data broker integrations."""
    
    tier_category = "premium"

    async def execute_check(self, check_type, subject, locale, **kwargs) -> SearchResult:
        # 1. Verify explicit consent for behavioral data was given
        consent_manager.verify_consent_for_behavioral_data(subject.consent)

        # 2. Filter out queries for protected categories based on jurisdiction
        if locale.is_eu():
            kwargs["excluded_categories"] = ["political", "religious", "health"]

        # 3. Call the broker-specific implementation
        return await self._broker_execute(check_type, subject, locale, **kwargs)

    async def _broker_execute(self, ...):
        raise NotImplementedError

class AcxiomSearchEngine(DataBrokerSearchEngine):
    provider_id = "acxiom"
    
    async def _broker_execute(self, ...):
        # Acxiom-specific API calls
        pass

class OracleDataCloudSearchEngine(DataBrokerSearchEngine):
    provider_id = "oracle_data_cloud"

    async def _broker_execute(self, ...):
        # Oracle-specific API calls
        pass
```

## 2. Configuration Parameters

| Parameter | Description | Example |
|---|---|---|
| `api_key` | The API key for the provider. | `acxiom_key...` |
| `api_secret` | The API secret for the provider. | `acxiom_secret...` |
| `api_endpoint` | The base URL for the API. | `https://api.acxiom.com/v2/` |
| `audience_taxonomy_id` | ID for the specific set of data segments we are licensed to use. | `taxonomy-123` |

## 3. API Details & Integration Flow

### Acxiom

-   **API Documentation**: Access is highly restricted and requires a major enterprise license agreement. Documentation is provided as part of the onboarding.
-   **Account Creation**: A lengthy enterprise sales and legal process. Acxiom vets customers and their use cases carefully. No public sandbox is available.
-   **Integration Flow**:
    1.  Acxiom's APIs are typically focused on "identity resolution" and "data enrichment."
    2.  First, we would use their `Match API` to resolve the subject's PII (name, address, email) to Acxiom's internal, persistent identifier for that individual.
    3.  Once we have the Acxiom ID, we use their `Enrichment API` to request specific data packages or "audiences."
    4.  The request would specify the data segments we are interested in (e.g., "Life Events," "Purchasing Habits," "Interests").
    5.  The API returns a JSON object containing the requested data segments for the individual.

## 4. `execute_check` Implementation Details

1.  The `_broker_execute` method will receive the subject's PII.
2.  It will call the provider's "Match" or "Resolve" endpoint to get their internal ID for the subject.
3.  It will then call the "Enrichment" endpoint, requesting the data segments relevant to our risk analysis (e.g., "Recent Mover," "High-Value Purchaser," "Travel Enthusiast").
4.  The method will receive the list of segments associated with the subject.
5.  This list will be passed to the normalizer.

## 5. Data Normalization

Data from brokers is not typically a direct "finding" but rather a set of attributes or "segments." The normalization process involves mapping these segments to potential risk indicators. This mapping must be carefully curated and reviewed by compliance to avoid proxying for protected classes.

**Example Normalization (`Acxiom -> Finding`):**

**Acxiom Raw Result:**
```json
{
  "acxiom_id": "ax123-abc-def",
  "segments": [
    { "id": "789", "name": "Recent Mover - New State" },
    { "id": "456", "name": "Luxury Automotive Buyer" },
    { "id": "111", "name": "Frequent International Traveler" },
    { "id": "222", "name": "Investment & Finance Interest" }
  ]
}
```

**Normalization Logic & Generated Findings:**
The normalizer checks each segment against a library of "behavioral risk signals."

-   `"Recent Mover - New State"` -> Could indicate instability.
-   `"Luxury Automotive Buyer"` -> Could indicate lifestyle inconsistent with income (when cross-referenced with financial data).
-   `"Frequent International Traveler"` -> Could be relevant for roles with access to sensitive IP.

```json
[
  {
    "finding_id": "...",
    "category": "behavioral",
    "severity": "low",
    "description": "Behavioral Signal: Recent cross-state move.",
    "details": { "segment": "Recent Mover - New State" },
    "source_provider": "acxiom"
  },
  {
    "finding_id": "...",
    "category": "behavioral",
    "severity": "low",
    "description": "Behavioral Signal: Frequent international travel.",
    "details": { "segment": "Frequent International Traveler" },
    "source_provider": "acxiom"
  }
]
```

**Crucially**, these findings are **never** used as the sole basis for an adverse decision. They are used in the `Enhanced` tier to provide context to a human investigator. For example, a "Luxury Automotive Buyer" segment combined with a high debt-to-income ratio from a credit report might trigger a "Financial Stress" risk signal in the main Risk Analyzer. The data broker finding itself is just a piece of the puzzle.
