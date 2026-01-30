# Implementation Plan: OSINT Platform Search Engines (Maltego, SpiderFoot)

This document outlines the plan for integrating Open Source Intelligence (OSINT) platforms. These are `Premium` data sources used in the `Enhanced` tier to aggregate a subject's digital footprint from public sources.

## 1. Class Structure

These platforms often have two modes: automated API calls and interactive tools for investigators. Our `SearchEngine` will focus on the automated, API-driven data aggregation.

```python
from elile.search.base import SearchEngine, SearchResult

class OsintPlatformSearchEngine(SearchEngine):
    """Abstract base for OSINT aggregation platforms."""
    tier_category = "premium"

class SpiderFootSearchEngine(OsintPlatformSearchEngine):
    """Uses the SpiderFoot HX API to run automated OSINT scans."""
    provider_id = "spiderfoot"

    async def execute_check(self, ...) -> SearchResult:
        # SpiderFoot-specific implementation
        pass

class MaltegoSearchEngine(OsintPlatformSearchEngine):
    """
    Orchestrates Maltego transforms via their API. 
    Note: Maltego is primarily a GUI tool, so API usage is for specific 'transforms'.
    """
    provider_id = "maltego"

    async def execute_check(self, ...) -> SearchResult:
        # Maltego-specific implementation
        pass
```

## 2. Configuration Parameters

| Provider | Parameter | Description | Example |
|---|---|---|---|
| SpiderFoot | `api_key` | API key for SpiderFoot HX. | `sf_api_key...` |
| SpiderFoot | `api_endpoint` | URL of the SpiderFoot HX instance. | `https://myinstance.spiderfoot.net/api/` |
| Maltego | `api_key` | API key for the Maltego transform server. | `mt_api_key...` |
| Maltego | `api_endpoint` | URL for the transform server. | `https://transforms.maltego.com/` |

## 3. API Details & Integration Flow

### SpiderFoot HX

-   **API Documentation**: [https://docs.spiderfoot.net/api-reference/](https://docs.spiderfoot.net/api-reference/)
-   **Account Creation**: Requires a subscription to SpiderFoot HX (the commercial, cloud-based version) or running a self-hosted instance of the open-source version.
-   **Integration Flow**:
    1.  **Initiate Scan**: Call `POST /api/scan` to start a new scan. The request body specifies the "scan target" (e.g., a domain name, email address, or username discovered via Pipl) and the desired modules to run (e.g., `sfp_social`, `sfp_dns`, `sfp_darksearch`).
    2.  The API returns a `scan_id`.
    3.  **Monitor Status**: Periodically call `GET /api/scan-status?id={scan_id}` to check if the scan is complete.
    4.  **Fetch Results**: Once complete, call `GET /api/scan-results?id={scan_id}` to retrieve the aggregated data. The results can be requested in various formats (JSON, CSV).

## 4. `execute_check` Implementation Details

1.  This engine will be invoked after an identity resolution provider like Pipl has been used, so it will have a rich set of inputs (emails, usernames, etc.).
2.  The `execute_check` method will iterate through the key identifiers for the subject:
    -   For each **email address**, it will launch a scan.
    -   For each **username**, it will launch a scan.
    -   For each **domain name** associated with the subject, it will launch a scan.
3.  Since the scans are long-running, the method will initiate them and return a `status: 'pending'` result.
4.  A separate background task (or a polling mechanism within the screening workflow) will be responsible for checking the scan status and retrieving the results once they are ready.
5.  The raw results from all the scans will be collected and passed to the normalizer.

## 5. Data Normalization

OSINT platforms generate a massive amount of data of varying quality. The normalizer's job is to sift through this data, verify its connection to the subject, and identify potentially relevant information. An AI model is essential for this task.

**Example Normalization (`SpiderFoot -> Finding`):**

**SpiderFoot Raw Result (a single item from a large JSON):**
```json
{
  "type": "SOCIAL_MEDIA",
  "data": "https://twitter.com/smithy70",
  "module": "sfp_social",
  "source": "Scan of username 'smithy70'"
},
{
  "type": "WEBSITE_FOR_SALE",
  "data": "domain: shady-business.com, owner_email: j.smith@email.com",
  "module": "sfp_dns",
  "source": "Scan of email 'j.smith@email.com'"
}
```

**AI-Powered Normalization Process:**
-   **Prompt**: "You are a digital footprint analyst. Review the following OSINT findings for a subject named John Smith. Identify any information that could be relevant for a high-risk employment screening, such as undisclosed business interests, controversial public statements, or association with risky online activities. For each relevant item, create a structured finding."
-   **Input**: The curated list of raw findings. The AI would also be given the full text/content from the discovered social media profiles.
-   **AI Output (structured JSON)**:
    ```json
    [
      { "signal": "undisclosed_business", "description": "Subject's email is associated with a domain 'shady-business.com' that is listed for sale.", "source": "DNS Records" },
      { "signal": "controversial_public_statements", "description": "Twitter profile @smithy70 contains posts with aggressive language and political extremism.", "source": "Twitter" }
    ]
    ```

**Generated Elile Findings:**
```json
[
  {
    "finding_id": "...",
    "category": "reputation",
    "severity": "medium",
    "description": "Digital Footprint: Association with potentially undisclosed business activity.",
    "details": { "domain": "shady-business.com", "link": "subject's email" },
    "source_provider": "spiderfoot"
  },
  {
    "finding_id": "...",
    "category": "reputation",
    "severity": "high",
    "description": "Digital Footprint: Public social media contains potentially problematic content.",
    "details": { "profile": "https://twitter.com/smithy70", "content_summary": "Aggressive language and political extremism" },
    "source_provider": "spiderfoot"
  }
]
```
The compliance engine must ensure that any analysis of social media content automatically filters out information related to protected classes (race, religion, etc.) to comply with EEOC guidelines. The AI prompt will be explicitly engineered to ignore such content.
