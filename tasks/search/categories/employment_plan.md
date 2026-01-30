# Implementation Plan: Employment Verification Search Engines

This document outlines the plan for integrating employment history verification providers. This is a `Core` check type, fundamental to confirming a subject's background.

## 1. Class Structure

We will support both automated database lookups (The Work Number) and manual verification workflows.

```python
from elile.search.base import SearchEngine, SearchResult

class EmploymentVerificationEngine(SearchEngine):
    """Abstract base for employment verification providers."""
    tier_category = "core"

class TheWorkNumberSearchEngine(EmploymentVerificationEngine):
    """Automated verification via The Work Number by Equifax."""
    provider_id = "the_work_number"

    async def execute_check(self, ...) -> SearchResult:
        # API-based verification
        pass

class DirectVerificationEngine(EmploymentVerificationEngine):
    """Handles manual or semi-automated direct outreach to employers."""
    provider_id = "direct_verification"

    async def execute_check(self, ...) -> SearchResult:
        # Triggers a human-in-the-loop workflow
        pass
```

## 2. Configuration Parameters

| Provider | Parameter | Description | Example |
|---|---|---|---|
| The Work Number | `account_code` | TWN employer account code. | `12345` |
| The Work Number | `username` | API user credentials. | `elile_api_user` |
| The Work Number | `password` | API user password. | `twn_secret` |
| The Work Number | `api_endpoint` | The API endpoint URL. | `https://api.theworknumber.com/` |
| Direct Verification | `workflow_engine_url` | URL for internal workflow tool (e.g., Camunda). | `http://camunda:8080/engine-rest` |

## 3. API Details & Integration Flow

### The Work Number (TWN)

-   **API Documentation**: Provided by Equifax after signing a commercial agreement. Access is restricted.
-   **Account Creation**: Requires a credentialed account with Equifax Workforce Solutions. This is an enterprise product.
-   **Integration Flow**:
    1.  Authenticate to the TWN API.
    2.  Submit a request including the subject's PII (SSN is required) and the employer's name or code. Crucially, the subject's **signed consent form** must be uploaded or referenced.
    3.  The API returns a report, usually synchronously, containing all employment records they have for that subject from participating employers.
    4.  The data includes employer name, start date, end date, and title. Salary information may be available but requires a higher level of consent.

### Direct Verification

This is not a typical API integration but a **human-in-the-loop process** orchestrated by our system.

-   **Integration Flow**:
    1.  The `DirectVerificationEngine` is invoked when an employer is not in The Work Number or when a client requests direct confirmation.
    2.  The `execute_check` method does not call an external API. Instead, it creates a task in a human workflow system (like a BPMN engine or a simple task queue).
    3.  The task is assigned to a human verification specialist. The task contains the subject's name, the claimed employer, and contact information for the employer's HR department.
    4.  The specialist calls or emails the employer to verify the claimed dates and title.
    5.  The specialist enters the results (e.g., "Verified," "Discrepancy Found," "Unable to Verify") into the workflow system.
    6.  The workflow system calls back to our application via a webhook or API call to update the screening status and provide the results.

## 4. `execute_check` Implementation Details

-   **The Work Number**: This will be a standard synchronous API call. The method will receive the subject's claimed employment history, query TWN for each employer, and compare the results.
-   **Direct Verification**: This method will format the verification request and push it into the human task queue. It will return an immediate `status: 'pending'` result. The actual result will arrive later via a webhook from the workflow tool.

The screening engine will be configured to **first** try The Work Number. If an employer record is not found, it will **then** automatically trigger the `DirectVerificationEngine` as a fallback.

## 5. Data Normalization

The primary task is to compare the claimed history with the verified history and generate `Finding` objects for any discrepancies.

**Example Normalization (`The Work Number -> Finding`):**

**Input Data:**
-   **Claimed**: Employer: "Google LLC", Title: "Senior Software Engineer", Start: "2020-01-15", End: "2023-06-30"
-   **TWN Result**: Employer: "Google, Inc.", Title: "Software Engineer III", Start: "2020-01-20", End: "2023-06-28"

**Normalization Logic:**
-   The normalizer compares the records.
-   Employer name is a fuzzy match ("Google LLC" vs "Google, Inc.") -> OK.
-   Dates are within a small tolerance (e.g., +/- 7 days) -> OK.
-   Title is different ("Senior Software Engineer" vs "Software Engineer III"). This is a discrepancy.

**Generated Elile Finding:**

```json
{
  "finding_id": "...",
  "category": "verification",
  "severity": "low",
  "description": "Discrepancy in job title at Google, Inc.",
  "details": {
    "field": "job_title",
    "claimed": "Senior Software Engineer",
    "verified": "Software Engineer III",
    "employer": "Google, Inc."
  },
  "source_provider": "the_work_number"
}
```

If TWN had returned no record for Google, the finding would be:

```json
{
  "finding_id": "...",
  "category": "verification",
  "severity": "medium",
  "description": "Unable to verify employment at Google, Inc.",
  "details": {
    "employer": "Google, Inc.",
    "status": "no_record_found"
  },
  "source_provider": "the_work_number"
}
```
This "Unable to verify" finding would then trigger the `DirectVerificationEngine` workflow.
