# Implementation Plan: Identity Resolution Search Engines (Pipl, FullContact)

This document outlines the plan for integrating identity resolution providers. These are `Premium` data sources used in the `Enhanced` tier. Their primary purpose is to build a more complete digital picture of a subject by linking disparate pieces of PII (emails, phone numbers, social media handles) to a single identity. This is a key enabler for OSINT and digital footprint analysis.

## 1. Class Structure

A base class will define the common interface for identity resolution.

```python
from elile.search.base import SearchEngine, SearchResult

class IdentityResolutionSearchEngine(SearchEngine):
    """Abstract base for identity resolution and data enrichment providers."""
    
    tier_category = "premium"

    async def execute_check(self, ...) -> SearchResult:
        # Provider-specific implementation
        pass

class PiplSearchEngine(IdentityResolutionSearchEngine):
    provider_id = "pipl"
    
    async def execute_check(self, ...) -> SearchResult:
        # Pipl-specific API calls
        pass

class FullContactSearchEngine(IdentityResolutionSearchEngine):
    provider_id = "fullcontact"

    async def execute_check(self, ...) -> SearchResult:
        # FullContact-specific API calls
        pass
```

## 2. Configuration Parameters

| Parameter | Description | Example |
|---|---|---|
| `api_key` | The API key for the provider. | `pipl_api_key...` |
| `api_endpoint` | The base URL for the API. | `https://api.pipl.com/` |

## 3. API Details & Integration Flow

### Pipl

-   **API Documentation**: [https://docs.pipl.com/](https://docs.pipl.com/)
-   **Account Creation**: Requires a business account. A free trial is available, but production use requires a paid subscription based on match volume.
-   **Integration Flow**:
    1.  The primary endpoint is a `POST` to `/search`.
    2.  The request body can contain any PII we have on the subject: name, address, email, phone number, username, etc. The more identifiers provided, the more accurate the match.
    3.  The API returns a "person" object that consolidates all known information about the matched individual. This includes:
        -   Names and aliases
        -   Addresses (current and historical)
        -   Phone numbers
        -   Email addresses
        -   Usernames and social media profile URLs
        -   Associated people (family members, business associates)
        -   Career and education history

## 4. `execute_check` Implementation Details

1.  The `execute_check` method will be called early in the `Enhanced` tier screening process.
2.  It will gather all PII currently known about the subject (from their application, credit report, etc.).
3.  It will make a single, comprehensive query to the Pipl API.
4.  The API's response is a rich "person" object. This object is not a "finding" in itself. Instead, it's a **data enrichment** step.
5.  The `SearchResult` will contain the raw person object. The screening engine orchestrator (LangGraph) will then use this enriched data to inform subsequent searches.

**Example Workflow:**
1.  `PiplSearchEngine` is called.
2.  It returns a person object containing a list of 5 email addresses and 3 usernames associated with the subject.
3.  The screening engine then uses this new information to fuel other searches:
    -   The `DarkWebSearchEngine` is called for each of the 5 email addresses.
    -   The `OsintSearchEngine` is called for each of the 3 usernames to find public social media activity.

## 5. Data Normalization

The primary output is not a `Finding`, but an update to the subject's `KnowledgeBase` in the screening workflow.

**Example Normalization (`Pipl -> KnowledgeBase`):**

**Pipl Raw Result:**
```json
{
  "person": {
    "names": [{ "display": "John Robert Smith" }, { "display": "Johnny Smith" }],
    "emails": [{ "address": "j.smith@email.com" }, { "address": "smithy70@email.com" }],
    "usernames": [{ "content": "smithy70" }, { "content": "john_r_smith" }],
    "relationships": [{ "type": "family", "names": [{ "display": "Jane Smith" }] }]
  }
}
```

**Normalization Logic:**
The normalizer iterates through the Pipl response and adds new, unique identifiers to the central `KnowledgeBase` for the screening.

**Updated `KnowledgeBase`:**
```python
# In-memory state of the screening workflow
knowledge_base = {
    "confirmed_names": ["John Smith", "John Robert Smith", "Johnny Smith"],
    "confirmed_emails": ["j.smith@email.com", "smithy70@email.com"],
    "confirmed_usernames": ["smithy70", "john_r_smith"],
    "discovered_people": [
        {"name": "Jane Smith", "relationship": "family"}
    ]
}
```

This enriched `KnowledgeBase` is then used as input for all subsequent `Premium` searches.

A secondary function of the normalizer can be to generate `verification` findings if the Pipl data contradicts information provided by the subject. For example, if Pipl returns a different DOB than the one claimed, a `low` severity `verification` finding would be created.
