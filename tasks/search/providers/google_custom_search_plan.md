# Implementation Plan: Google Custom Search Engine

This document outlines the plan for integrating the Google Custom Search JSON API as a `SearchEngine` subclass. This provider will be used for targeted adverse media and digital footprint analysis. It can serve as a `Core` provider for basic keyword searches and as a component within the `Premium` OSINT workflow.

## 1. Class Structure

```python
from elile.search.base import SearchEngine, SearchResult

class GoogleCustomSearchEngine(SearchEngine):
    """
    A search engine that uses the Google Custom Search JSON API to perform
    targeted web searches for adverse media or other public information.
    """
    provider_id = "google_custom_search"
    # This can be used in both Core and Premium tiers depending on the query's nature.
    # We will default to 'core' and let the screening engine decide.
    tier_category = "core"

    async def execute_check(self, check_type, subject, locale, **kwargs) -> SearchResult:
        # Implementation details below
        pass
```

## 2. Account Creation & Configuration

To use this API, two main components are required: a **Google API Key** and a **Programmable Search Engine ID**.

1.  **Google API Key Creation**:
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project (e.g., "Elile Search Integration").
    *   Navigate to "APIs & Services" > "Credentials".
    *   Click "Create Credentials" > "API key".
    *   Copy the generated API key. It's recommended to restrict this key to only be able to access the "Custom Search API".
    *   Enable the **"Custom Search API"** for your project in the API Library.

2.  **Programmable Search Engine ID Creation**:
    *   Go to the [Programmable Search Engine control panel](https://programmablesearchengine.google.com/).
    *   Click "Add" to create a new search engine.
    *   Configure the search engine:
        *   **Name**: Elile Adverse Media Search
        *   **What to search?**: Select "Search the entire web". This is crucial for broad searches.
        *   Enable "Image search" and "SafeSearch".
    *   After creation, go to the "Setup" page for the new search engine.
    *   The **"Search engine ID"** will be displayed on this page. Copy this ID.

## 3. Configuration Parameters

The engine will require the following configuration parameters, managed via the application's settings:

| Parameter | Description | Example |
|---|---|---|
| `api_key` | The Google Cloud API key. | `AIzaSy...` |
| `search_engine_id` | The ID of the configured Programmable Search Engine. | `cx=01757...` |

These will be stored in the environment/secret manager as `GOOGLE_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID`.

## 4. API Details & Integration Flow

-   **API Documentation**: [https://developers.google.com/custom-search/v1/using_rest](https://developers.google.com/custom-search/v1/using_rest)
-   **Endpoint**: A single `GET` endpoint is used for all queries.
    -   `https://www.googleapis.com/customsearch/v1`
-   **Key Query Parameters**:
    -   `key`: The API key.
    -   `cx`: The Search Engine ID.
    -   `q`: The search query string.
    -   `num`: Number of results to return (max 10 per page).
    -   `start`: The index of the first result to return (for pagination).

## 5. `execute_check` Implementation Details

1.  The method will receive the subject's name and other identifiers from the `KnowledgeBase`.
2.  It will also receive a set of keywords relevant to the check type (e.g., for adverse media: "arrest", "fraud", "lawsuit", "investigation").
3.  It will construct a series of precise search queries. Example:
    *   `"John Robert Smith" AND ("fraud" OR "scandal")`
    *   `"John R. Smith" AND "Acme Corp" AND "lawsuit"`
4.  For each query, it will make a `GET` request to the Google Custom Search API.
5.  The implementation must handle pagination. A typical search might involve fetching the first 3-5 pages (30-50 results) to get a comprehensive overview.
6.  All the raw search result items will be aggregated into a list.
7.  This list of items will be passed to the normalizer function for analysis.

## 6. Data Normalization

The normalizer will process the list of search results to identify relevant hits and create `Finding` objects. An AI model is highly effective for this task due to the unstructured nature of web page snippets.

**Example Normalization (`Google Search Result -> Finding`):**

**Google API Raw Result Item:**
```json
{
  "title": "John Smith, former exec, charged in $5M fraud scheme - Reuters",
  "link": "https://www.reuters.com/article/john-smith-fraud-charges",
  "snippet": "Federal prosecutors have charged John Robert Smith, a former executive at a tech startup, in connection with a wire fraud scheme that allegedly defrauded investors of over $5 million.",
  "pagemap": { "metatags": [{ "og:site_name": "Reuters" }] }
}
```

**AI-Powered Normalization Process:**
-   **Prompt**: "You are a risk analyst reviewing web search results for a person named 'John Robert Smith'. Analyze the following search result snippet and title. Does it represent potential adverse media? If so, extract the key allegation, the source, and assign a severity level (low, medium, high, critical)."
-   **Input**: The raw JSON item from the Google API.
-   **AI Output (structured JSON)**:
    ```json
    {
      "is_adverse": true,
      "severity": "high",
      "category": "reputation",
      "description": "Subject charged in a $5M wire fraud scheme.",
      "source": "Reuters"
    }
    ```

**Generated Elile Finding:**
```json
{
  "finding_id": "...",
  "category": "reputation",
  "severity": "high",
  "description": "Adverse Media: Subject charged in connection with a wire fraud scheme.",
  "details": {
    "source_url": "https://www.reuters.com/article/john-smith-fraud-charges",
    "publication": "Reuters",
    "snippet": "Federal prosecutors have charged John Robert Smith, a former executive at a tech startup, in connection with a wire fraud scheme that allegedly defrauded investors of over $5 million."
  },
  "source_provider": "google_custom_search"
}
```
This process allows the system to automatically sift through dozens of search results, flagging only the ones that represent a potential risk and structuring them for review by a human analyst.
