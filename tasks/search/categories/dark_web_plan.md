# Implementation Plan: Dark Web Monitoring Search Engines (Recorded Future, DarkOwl)

This document outlines the plan for integrating dark web intelligence providers. These are `Premium` data sources used in the `Enhanced` tier to discover if a subject's credentials or PII have been exposed in data breaches or are being discussed on illicit forums.

**Compliance Note:** Data from the dark web cannot be used as a basis for adverse action. It is a security intelligence tool used to assess risk and protect the subject and the company. Findings must be clearly labeled as such.

## 1. Class Structure

A base class will enforce the compliance rules for handling dark web data.

```python
from elile.search.base import SearchEngine, SearchResult

class DarkWebSearchEngine(SearchEngine):
    """Abstract base for dark web intelligence providers."""
    
    tier_category = "premium"

    async def execute_check(self, check_type, subject, locale, **kwargs) -> SearchResult:
        # Compliance check: Ensure findings from this source are marked
        # as "not for adverse action". This will be handled in the normalizer.
        return await self._provider_execute(check_type, subject, locale, **kwargs)

    async def _provider_execute(self, ...):
        raise NotImplementedError

class RecordedFutureSearchEngine(DarkWebSearchEngine):
    provider_id = "recorded_future"
    
    async def _provider_execute(self, ...):
        pass

class DarkOwlSearchEngine(DarkWebSearchEngine):
    provider_id = "darkowl"

    async def _provider_execute(self, ...):
        pass
```

## 2. Configuration Parameters

| Parameter | Description | Example |
|---|---|---|
| `api_key` | API key for the provider. | `rf_api_key...` |
| `api_endpoint` | The base URL for the API. | `https://api.recordedfuture.com/` |

## 3. API Details & Integration Flow

### Recorded Future

-   **API Documentation**: [https://support.recordedfuture.com/hc/en-us/categories/360002322233-API-Documentation](https://support.recordedfuture.com/hc/en-us/categories/360002322233-API-Documentation)
-   **Account Creation**: Requires a significant enterprise subscription.
-   **Integration Flow**:
    1.  Recorded Future's API is organized around "entities" (IPs, domains, hashes) and "intelligence cards."
    2.  To search for a subject's data, we would use their `Identity` API.
    3.  We would query for entities like email addresses, phone numbers, and usernames that were previously discovered by an identity resolution provider like Pipl.
    4.  The query would look for these identifiers in breach corpuses and on dark web forums/marketplaces.
    5.  `GET /identity/lookup?email=j.smith@email.com`
    6.  The API returns a list of "risks" associated with that identifier, such as "Exposed in Breach" or "Mentioned on Dark Web Marketplace." It provides details on the breach/mention, including the source and the type of data exposed.

## 4. `execute_check` Implementation Details

1.  This engine will be called after identity resolution, so it will have a list of emails and usernames to search for.
2.  The `_provider_execute` method will iterate through each identifier (email, phone number) for the subject.
3.  For each identifier, it will make a synchronous call to the provider's API.
4.  It will aggregate all the "risks" or "mentions" returned from the API across all identifiers.
5.  This aggregated list of raw results is then passed to the normalizer.

## 5. Data Normalization

The normalizer's job is to translate the provider's "risks" into our standardized `Finding` model, ensuring they are flagged correctly for compliance.

**Example Normalization (`Recorded Future -> Finding`):**

**Recorded Future Raw Result:**
```json
{
  "risks": [
    {
      "type": "IdentityBreach",
      "criticality": "High",
      "evidence": {
        "breachName": "Collection #1",
        "compromisedDataType": ["EmailAddress", "Password"],
        "breachDate": "2019-01-01"
      }
    },
    {
      "type": "DarkWebMention",
      "criticality": "Medium",
      "evidence": {
        "forumName": "XSS.is",
        "postTitle": "Selling credentials for corporate network",
        "snippet": "...have access for j.smith@acme.com, looking for $500..."
      }
    }
  ]
}
```

**Normalization Logic & Generated Findings:**
The normalizer creates a separate `Finding` for each risk, carefully setting the category and adding a compliance flag.

```json
[
  {
    "finding_id": "...",
    "category": "security",
    "severity": "high",
    "description": "Credential Exposure: Email and password found in 'Collection #1' breach.",
    "details": {
      "breach_name": "Collection #1",
      "data_types": ["EmailAddress", "Password"],
      "breach_date": "2019-01-01"
    },
    "source_provider": "recorded_future",
    "compliance_flags": ["not_for_adverse_action"]
  },
  {
    "finding_id": "...",
    "category": "security",
    "severity": "critical",
    "description": "Dark Web Mention: Subject's corporate email mentioned for sale on illicit forum.",
    "details": {
      "source_forum": "XSS.is",
      "context": "Corporate network access being sold."
    },
    "source_provider": "recorded_future",
    "compliance_flags": ["not_for_adverse_action"]
  }
]
```

The `compliance_flags: ["not_for_adverse_action"]` is the most important part of this normalization. The downstream Risk Analyzer and Report Generator will use this flag to ensure this information is only visible to the Security Team or Investigator persona and is never used to make a hiring decision. It serves as a vital security signal for protecting the subject and the company from account takeover or other attacks.
