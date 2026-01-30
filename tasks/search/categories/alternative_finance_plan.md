# Implementation Plan: Alternative Finance Search Engines (Plaid, Finicity)

This document outlines the plan for integrating alternative finance data providers. These are `Premium` data sources used in the `Enhanced` tier, providing insight into a subject's financial behavior beyond traditional credit reports. This data is accessed via open banking APIs and requires explicit, direct consent from the subject.

## 1. Class Structure

A base class will manage the consent flow, which is unique to this data type.

```python
from elile.search.base import SearchEngine, SearchResult
from elile.compliance import consent_manager

class AlternativeFinanceSearchEngine(SearchEngine):
    """Abstract base for open banking and alternative finance data providers."""
    
    tier_category = "premium"

    async def execute_check(self, check_type, subject, locale, **kwargs) -> SearchResult:
        # This check requires a direct, interactive login from the subject.
        # The engine will generate a link for the subject to complete this flow.
        
        # 1. Generate a provider-specific link for the Plaid/Finicity Link flow.
        link_token = await self._create_link_token(subject)
        
        # 2. Send this link to the subject. This will be handled by the orchestration engine.
        # For this plan, we assume the method returns a special result indicating
        # that user interaction is required.
        return SearchResult(
            status='pending_user_action',
            provider_id=self.provider_id,
            raw_data={'link_token': link_token}
        )

    async def _create_link_token(self, subject):
        raise NotImplementedError
        
    # A separate method will be called by a webhook when the user completes the flow.
    async def process_completed_flow(self, public_token):
        raise NotImplementedError

class PlaidSearchEngine(AlternativeFinanceSearchEngine):
    provider_id = "plaid"
    
    async def _create_link_token(self, subject):
        # Plaid-specific link token creation
        pass
        
    async def process_completed_flow(self, public_token):
        # Exchange public token for access token and fetch data
        pass
```

## 2. Configuration Parameters

| Parameter | Description | Example |
|---|---|---|
| `client_id` | Plaid Client ID. | `abc123def456` |
| `secret` | Plaid API Secret. | `xyz789...` |
| `api_endpoint` | The base URL for the API (e.g., development, production). | `https://development.plaid.com` |

## 3. API Details & Integration Flow

### Plaid

-   **API Documentation**: [https://plaid.com/docs/](https://plaid.com/docs/)
-   **Account Creation**: Sign up on the Plaid website. A sandbox is available for free. Production access requires approval and is priced per linked account.
-   **Integration Flow (Highly Interactive)**:
    1.  **Create Link Token**: Our backend calls Plaid's `/link/token/create` endpoint. This token initializes the Plaid Link UI for a specific user and product (e.g., `transactions`, `assets`).
    2.  **User Interaction**: The screening engine sends the `link_token` to the subject (e.g., via the Subject Portal). The subject uses this token to open the Plaid Link UI, where they select their bank, enter their credentials, and grant consent.
    3.  **Public Token Exchange**: Upon success, the Plaid UI gives us a temporary `public_token`.
    4.  Our backend calls `/item/public_token/exchange` to trade the `public_token` for a permanent `access_token`. This `access_token` is securely stored and represents our permission to access that subject's bank data.
    5.  **Data Fetching**: We can now use the `access_token` to call various endpoints:
        -   `/transactions/get`: Retrieve transaction history.
        -   `/assets/report/create`: Create a consolidated report of assets.
        -   `/identity/get`: Verify account holder's identity.

## 4. `execute_check` Implementation Details

This engine is different from others.

-   The initial `execute_check` call only generates the `link_token` and returns a `pending_user_action` status.
-   The screening workflow pauses at this step and notifies the subject.
-   A separate, secure webhook endpoint in our application must be created to receive the `public_token` from the Plaid Link UI.
-   When the webhook is called, it will invoke the `process_completed_flow` method.
-   This method will perform the token exchange, fetch the transaction/asset data, and pass it to the normalizer.
-   Finally, it will store the normalized `Finding` objects and notify the screening workflow to resume.

## 5. Data Normalization

The raw transaction data is a firehose of information. The normalizer's job is to extract meaningful risk signals. An AI model is ideal for this kind of analysis.

**Example Normalization (`Plaid Transactions -> Finding`):**

**Plaid Raw Transaction Data:**
```json
[
  { "name": "PAYCHECK - ACME CORP", "amount": -2500, "category": ["Transfer", "Deposit", "Payroll"] },
  { "name": "ONLINE GAMBLING SITE", "amount": 500, "category": ["Service", "Gaming"] },
  { "name": "Venmo payment to Jane Doe", "amount": 1000, "category": ["Transfer", "P2P"] },
  { "name": "NSF Fee - Insufficient Funds", "amount": 35, "category": ["Fee", "Bank Fee"] }
]
```

**AI-Powered Normalization Process:**
-   **Prompt**: "You are a financial risk analyst. Analyze the following bank transactions and identify any potential risk signals relevant to pre-employment screening. Categorize signals such as gambling activity, undisclosed income, signs of financial distress, or large unexplained transfers."
-   **Input**: The raw transaction list.
-   **AI Output (structured JSON)**:
    ```json
    [
      { "signal": "gambling_activity", "description": "Payment to 'ONLINE GAMBLING SITE'", "amount": 500 },
      { "signal": "financial_distress", "description": "Received 'NSF Fee - Insufficient Funds'", "amount": 35 },
      { "signal": "undisclosed_income_source", "description": "Possible undeclared income from 'Venmo payment to Jane Doe' if Jane Doe is not a known contact.", "amount": 1000 }
    ]
    ```

**Generated Elile Findings:**
```json
[
  {
    "finding_id": "...",
    "category": "behavioral",
    "severity": "medium",
    "description": "Financial Pattern: Payments to gambling sites detected.",
    "details": { "transaction_name": "ONLINE GAMBLING SITE", "amount": 500 },
    "source_provider": "plaid"
  },
  {
    "finding_id": "...",
    "category": "financial",
    "severity": "medium",
    "description": "Financial Distress: Insufficient funds fee incurred.",
    "details": { "fee_type": "NSF Fee" },
    "source_provider": "plaid"
  }
]
```
This provides deep, behavioral financial insights that are impossible to get from a standard credit report.
