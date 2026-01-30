# Implementation Plan: Social-Searcher Search Engine

This document outlines the plan for integrating the Social-Searcher API as a `SearchEngine` subclass. This provider will be used as a `Core` data source to find public social media posts across various networks, supporting reputation and digital footprint analysis.

## 1. Class Structure

The implementation will be a single class that can target different social networks based on a parameter.

```python
from elile.search.base import SearchEngine, SearchResult

class SocialSearcherSearchEngine(SearchEngine):
    """
    A search engine that uses the Social-Searcher API to find public posts
    mentioning a subject on various social networks.
    """
    provider_id = "social_searcher"
    tier_category = "core"

    async def execute_check(
        self, 
        check_type, 
        subject, 
        locale, 
        service_type: str,  # e.g., "twitter", "facebook", "linkedin"
        **kwargs
    ) -> SearchResult:
        # Implementation details below
        pass
```

The `service_type` parameter is crucial as it allows the screening engine to target specific networks (e.g., professional networks like LinkedIn vs. more public ones like Twitter/X) based on the nature of the screening.

## 2. Account Creation & Configuration

1.  **Account Creation**:
    *   Navigate to [https://www.social-searcher.com/social-buzz-api/](https://www.social-searcher.com/social-buzz-api/).
    *   Sign up for an API plan. There are free tiers suitable for development and testing, but a paid plan (e.g., Basic or Professional) will be required for production volume and to remove rate limits.
    *   Once registered, the API key will be available in the user's account dashboard.

## 3. Configuration Parameters

The engine will require the following configuration parameter, managed via the application's settings:

| Parameter | Description | Example |
|---|---|---|
| `api_key` | The API key provided by Social-Searcher. | `a1b2c3d4e5f6a7b8c9d0...` |

This will be stored in the environment/secret manager as `SOCIAL_SEARCHER_API_KEY`.

## 4. API Details & Integration Flow

-   **API Documentation**: [https://www.social-searcher.com/social-buzz-api/](https://www.social-searcher.com/social-buzz-api/)
-   **Endpoint**: `https://api.social-searcher.com/v2/search`
-   **Key Query Parameters**:
    -   `key`: The API key.
    -   `q`: The search query string (e.g., the subject's name or username).
    -   `network`: The specific social network to search. This will be mapped from our `service_type` parameter. Supported values include `twitter`, `facebook`, `linkedin`, `instagram`, `tiktok`, etc.
    -   `limit`: The number of posts to return.

-   **Integration Flow**:
    1.  The `execute_check` method is called with the subject's name and the target `service_type`.
    2.  A search query `q` is constructed (e.g., `"John Smith"`).
    3.  An API `GET` request is made to the endpoint with the query, API key, and the `network` parameter set to the value of `service_type`.
    4.  The API returns a JSON object containing a list of `posts`.
    5.  This list of posts is passed to the normalizer for analysis.

## 5. `execute_check` Implementation Details

1.  The method will validate that the provided `service_type` is a supported network.
2.  It will construct a precise search query, likely using the subject's full name in quotes. If available from prior identity resolution steps, it will prefer searching for a confirmed username on that specific service.
3.  It will make a synchronous call to the Social-Searcher API.
4.  The raw `posts` array from the JSON response will be extracted.
5.  This array will be passed to the normalizer function.

## 6. Data Normalization

The normalizer's role is to analyze the content of the returned posts to identify potential risks. Given the unstructured nature of post text, an AI model is the ideal tool for this analysis.

**Compliance Note:** The analysis must be carefully firewalled to ignore any content related to protected classes (e.g., religion, political affiliation, race, disability, etc.) as per EEOC and other regulations.

**Example Normalization (`Social-Searcher Post -> Finding`):**

**Social-Searcher Raw Post Item:**
```json
{
  "posted": "2023-10-27T10:00:00Z",
  "network": "twitter",
  "url": "https://twitter.com/smithy70/status/12345",
  "user": {
    "name": "John Smith",
    "url": "https://twitter.com/smithy70"
  },
  "text": "So angry at my boss, someone should do something about him. This whole company is a joke. #badboss"
}
```

**AI-Powered Normalization Process:**
-   **Prompt**: "You are a compliance-aware risk analyst. Review the following social media post. Identify if it contains any content that falls into these specific categories: (1) Threats of violence, (2) Hate speech, (3) Admission of illegal acts, (4) Publicly expressed anger towards an employer that suggests workplace conflict. **You must ignore** any mention of political views, religion, family status, or other protected characteristics."
-   **Input**: The raw post `text`.
-   **AI Output (structured JSON)**:
    ```json
    {
      "is_adverse": true,
      "severity": "medium",
      "category": "reputation",
      "reason": "Publicly expressed anger towards an employer that suggests workplace conflict.",
      "quote": "So angry at my boss, someone should do something about him."
    }
    ```

**Generated Elile Finding:**
```json
{
  "finding_id": "...",
  "category": "reputation",
  "severity": "medium",
  "description": "Social Media: Public post indicates potential for workplace conflict.",
  "details": {
    "source_network": "twitter",
    "post_url": "https://twitter.com/smithy70/status/12345",
    "post_snippet": "So angry at my boss, someone should do something about him. This whole company is a joke."
  },
  "source_provider": "social_searcher"
}
```
This AI-assisted process turns a stream of public posts into structured, reviewable findings, while the carefully constructed prompt helps ensure compliance by focusing only on pre-defined, job-related risk categories.
