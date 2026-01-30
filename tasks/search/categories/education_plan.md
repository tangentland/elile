# Implementation Plan: Education Verification Search Engines

This document outlines the plan for integrating education verification providers. This is a `Core` check to validate a subject's claimed academic credentials.

## 1. Class Structure

Similar to employment verification, this will involve both an automated provider (National Student Clearinghouse) and a manual fallback.

```python
from elile.search.base import SearchEngine, SearchResult

class EducationVerificationEngine(SearchEngine):
    """Abstract base for education verification providers."""
    tier_category = "core"

class NationalStudentClearinghouseEngine(EducationVerificationEngine):
    """Automated verification via the National Student Clearinghouse (NSC)."""
    provider_id = "nsc"

    async def execute_check(self, ...) -> SearchResult:
        # API-based verification with NSC
        pass

class DirectSchoolVerificationEngine(EducationVerificationEngine):
    """Handles manual or semi-automated direct outreach to educational institutions."""
    provider_id = "direct_school_verification"

    async def execute_check(self, ...) -> SearchResult:
        # Triggers a human-in-the-loop workflow
        pass
```

## 2. Configuration Parameters

| Provider | Parameter | Description | Example |
|---|---|---|---|
| NSC | `account_id` | NSC client account number. | `001234` |
| NSC | `username` | API user ID. | `ELILE_API` |
| NSC | `password` | API password. | `nsc_secret` |
| NSC | `api_endpoint` | The URL for the NSC API. | `https://api.studentclearinghouse.org/` |
| Direct Verification | `workflow_engine_url` | URL for internal workflow tool. | `http://camunda:8080/engine-rest` |

## 3. API Details & Integration Flow

### National Student Clearinghouse (NSC)

-   **API Documentation**: NSC provides API access through its "DiplomaVerify" and "DegreeVerify" services. Documentation is provided upon signing a commercial agreement.
-   **Account Creation**: Requires a business account with NSC. This is the industry standard for education verification in the United States, covering over 98% of postsecondary institutions.
-   **Integration Flow**:
    1.  Authenticate to the NSC API.
    2.  Submit a request for each claimed degree. The request includes the subject's PII (Name, DOB), the institution name, degree title, and graduation date. Consent is required.
    3.  The API typically provides a synchronous response.
        -   **Instant Match**: If the data matches their records exactly, they provide an immediate confirmation.
        -   **Pending**: If the data is close but not an exact match, or if the school requires manual processing, the request goes into a pending state. We would need to poll for updates or receive a webhook.
    4.  The result confirms the degree, major, and graduation date.

### Direct School Verification

-   **Integration Flow**: This is a human-in-the-loop process, triggered when NSC cannot provide an instant confirmation or for institutions not covered by NSC (e.g., many international universities).
    1.  The `DirectSchoolVerificationEngine` is invoked.
    2.  It creates a task in our human workflow system.
    3.  The task is assigned to a verification specialist with the details of the claimed degree.
    4.  The specialist contacts the school's registrar's office via phone, email, or a dedicated online portal. This often requires submitting a signed consent form from the subject.
    5.  The specialist receives confirmation from the registrar and enters the verified data into the workflow system.
    6.  The workflow system calls back to our application to update the screening with the results.

## 4. `execute_check` Implementation Details

-   **NSC**: The method will query the NSC API for each claimed degree. If the result is instant, it will be processed. If it is pending, the status will be updated, and the system will wait for an asynchronous update.
-   **Direct School Verification**: This method will create the task in the human workflow queue and return `status: 'pending'`.

The screening engine will always try `NSC` first. A "no record found" or a "pending for manual processing" result from NSC will automatically trigger the `DirectSchoolVerificationEngine`.

## 5. Data Normalization

The primary goal is to detect discrepancies between the claimed and verified education history.

**Example Normalization (`NSC -> Finding`):**

**Input Data:**
-   **Claimed**: School: "University of California, Berkeley", Degree: "Bachelor of Science", Major: "Computer Science", Graduation: "May 2020"
-   **NSC Result**: School: "University of California, Berkeley", Degree: "Bachelor of Arts", Major: "Cognitive Science", Graduation: "May 2020"

**Normalization Logic:**
-   The normalizer compares the records.
-   School and graduation date match.
-   Degree title ("Bachelor of Science" vs "Bachelor of Arts") is a discrepancy.
-   Major ("Computer Science" vs "Cognitive Science") is a major discrepancy.

**Generated Elile Findings:**

```json
[
  {
    "finding_id": "...",
    "category": "verification",
    "severity": "medium",
    "description": "Discrepancy in degree title from University of California, Berkeley",
    "details": {
      "field": "degree_title",
      "claimed": "Bachelor of Science",
      "verified": "Bachelor of Arts",
      "institution": "University of California, Berkeley"
    },
    "source_provider": "nsc"
  },
  {
    "finding_id": "...",
    "category": "verification",
    "severity": "high",
    "description": "Discrepancy in major from University of California, Berkeley",
    "details": {
      "field": "major",
      "claimed": "Computer Science",
      "verified": "Cognitive Science",
      "institution": "University of California, Berkeley"
    },
    "source_provider": "nsc"
  }
]
```

If the subject claimed a degree but NSC returned "No Record Found," a single `high` severity finding would be generated for "Unable to verify degree," which would then trigger the manual verification process.
