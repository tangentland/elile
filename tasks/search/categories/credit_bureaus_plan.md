# Implementation Plan: Credit Bureau Search Engines (Experian, Equifax, TransUnion)

This document outlines the plan for integrating the three major credit bureaus as `SearchEngine` subclasses. These providers are a `Core` data source for financial records and identity verification. Access to this data is highly regulated under FCRA.

## 1. Class Structure

A base class will handle FCRA compliance logic, with specific implementations for each bureau.

```python
from elile.search.base import SearchEngine, SearchResult
from elile.compliance import fcrachecks

class CreditBureauSearchEngine(SearchEngine):
    """Abstract base for credit bureau integrations."""
    
    tier_category = "core"

    async def execute_check(self, check_type, subject, locale, **kwargs) -> SearchResult:
        # 1. Verify permissible purpose before proceeding
        fcrachecks.verify_permissible_purpose(subject.consent, check_type)

        # 2. Call the bureau-specific implementation
        return await self._bureau_execute(check_type, subject, locale, **kwargs)

    async def _bureau_execute(self, ...):
        raise NotImplementedError

class ExperianSearchEngine(CreditBureauSearchEngine):
    provider_id = "experian"
    
    async def _bureau_execute(self, ...):
        # Experian-specific API calls
        pass

class EquifaxSearchEngine(CreditBureauSearchEngine):
    provider_id = "equifax"

    async def _bureau_execute(self, ...):
        # Equifax-specific API calls
        pass

class TransUnionSearchEngine(CreditBureauSearchEngine):
    provider_id = "transunion"

    async def _bureau_execute(self, ...):
        # TransUnion-specific API calls
        pass
```

## 2. Configuration Parameters

Configuration will be standardized across the three bureaus.

| Parameter | Description | Example |
|---|---|---|
| `api_endpoint` | The base URL for the API. | `https://api.experian.com/` |
| `client_id` | OAuth 2.0 Client ID. | `abc123def456` |
| `client_secret` | OAuth 2.0 Client Secret. | `xyz789...` |
| `subscriber_code` | The account-specific code identifying our business. | `US01234567` |
| `end_user_code` | Code for the specific end-user (our customer), if required. | `CUST9876` |
| `permissible_purpose_code` | The FCRA code for employment screening. | `EMP` |

These will be stored as secrets, e.g., `EQUIFAX_CLIENT_ID`.

## 3. API Details & Integration Flow

Credit bureau APIs are typically synchronous request/response.

### Experian Connect API (Illustrative)

-   **API Documentation**: Access is restricted and requires an enterprise agreement. Documentation is provided during onboarding.
-   **Account Creation**: A rigorous and lengthy process. Requires proving FCRA compliance, undergoing security audits, and signing a multi-year contract. There is no public sandbox. A dedicated test environment is provided after contract signing.
-   **Authentication**: OAuth 2.0 Client Credentials flow to get a bearer token.
-   **Endpoints**:
    -   `POST /oauth2/v1/token`: Exchange `client_id` and `client_secret` for an access token.
    -   `POST /consumers/v1/credit-profile`: Submit subject's PII (Name, Address, SSN, DOB) to request a credit profile. The `permissible_purpose_code` must be included in the request body.
-   **Key Data Points**:
    -   Identity Verification: Name/Address/SSN match confirmation.
    -   Credit Summary: Total debt, utilization, payment history summary.
    -   Tradelines: Details on each credit account (loans, credit cards).
    -   Public Records: Bankruptcies, liens, judgments.
    -   Inquiries: Who has recently pulled the subject's credit.

## 4. `execute_check` Implementation Details

The `_bureau_execute` method will:

1.  Authenticate with the provider (e.g., OAuth2 token flow).
2.  Construct the request payload with the subject's PII and required purpose codes.
3.  Make a synchronous `POST` request to the credit profile endpoint.
4.  Receive the raw credit report data (typically in JSON or XML format).
5.  Pass the raw data to a dedicated normalizer function.
6.  The normalizer will transform the complex bureau-specific structure into a list of standardized `Finding` objects.
7.  Return a `SearchResult` containing the list of findings.

## 5. Data Normalization

This is the most complex part of the integration. Each bureau has a unique, deeply nested structure for their credit reports.

**Example Normalization (`Experian -> Finding`):**

```json
// Experian Raw Data (Public Record)
{
  "publicRecord": [
    {
      "type": "Bankruptcy",
      "filingType": "Chapter 7",
      "status": "Discharged",
      "dateFiled": "2022-03-15",
      "liabilities": "150000",
      "court": "US Bankruptcy Court, Northern District of California"
    }
  ]
}

// Normalized Elile Finding
{
  "finding_id": "...",
  "category": "financial",
  "severity": "high",
  "description": "Bankruptcy Filing: Chapter 7",
  "details": {
    "type": "Chapter 7 Bankruptcy",
    "status": "Discharged",
    "date": "2022-03-15",
    "liabilities": 150000,
    "jurisdiction": "US Bankruptcy Court, Northern District of California"
  },
  "source_provider": "experian"
}
```

A separate normalizer will be required for each bureau to handle tradelines, inquiries, and identity discrepancies, mapping them to `financial`, `verification`, or other `Finding` categories as appropriate. For example, a high number of recent credit inquiries could generate a `financial` finding with `severity: 'medium'` and a description of "Potential credit-seeking behavior."
