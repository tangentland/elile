# Reporting Architecture

> **Prerequisites**: [01-design.md](01-design.md), [05-investigation.md](05-investigation.md)
>
> **See also**: [07-compliance.md](07-compliance.md) for FCRA requirements, [11-interfaces.md](11-interfaces.md) for report display

Different stakeholders require different views of screening results. The system generates persona-specific reports from the same underlying data.

## Report Persona Matrix

| Persona | Report Type | Content Focus | Data Depth | Format |
|---------|-------------|---------------|------------|--------|
| HR Manager | Summary Report | Risk level, recommendation, key flags | High-level | PDF, Dashboard |
| Compliance Officer | Audit Report | Data sources, consent, compliance checks | Full audit trail | PDF, JSON |
| Security Team | Investigation Report | Detailed findings, connections, threats | Complete | PDF, Structured |
| Investigator | Case File | Raw findings, cross-references, evidence | Complete + raw | PDF, Export |
| Subject | Disclosure Report | What was checked, summary results | Redacted | PDF, Portal |
| Executive | Portfolio Report | Aggregate risk, trends, statistics | Aggregated | Dashboard, PDF |

## HR Manager Summary Report

**Purpose:** Enable quick hiring decisions with appropriate risk context.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     BACKGROUND SCREENING SUMMARY                         │
│                                                                          │
│  Candidate: ████████████████           Position: Senior Analyst         │
│  Request ID: SCR-2025-00847            Date: January 27, 2025           │
│  Service: Standard | V0 | D2           Reviewed by: Jane Analyst        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  OVERALL RISK ASSESSMENT                                         │    │
│  │                                                                   │    │
│  │      ▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░  MODERATE (42/100)          │    │
│  │                                                                   │    │
│  │  Recommendation: PROCEED WITH CAUTION                            │    │
│  │  Requires: Additional verification of employment gap 2021-2022  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  KEY FINDINGS SUMMARY                                            │    │
│  │                                                                   │    │
│  │  ✓ Identity Verified         ✓ Education Confirmed               │    │
│  │  ✓ No Criminal Records       ✓ Credit Acceptable                 │    │
│  │  ⚠ Employment Gap Found      ✓ No Sanctions/PEP                  │    │
│  │  ✓ References Positive       ⚠ Minor Civil Judgment (resolved)   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  CATEGORY BREAKDOWN                                              │    │
│  │                                                                   │    │
│  │  Category          Status    Score    Notes                      │    │
│  │  ─────────────────────────────────────────────────────────       │    │
│  │  Identity          CLEAR     95       Multi-source verified      │    │
│  │  Criminal          CLEAR     100      No records found           │    │
│  │  Financial         REVIEW    65       Resolved judgment 2019     │    │
│  │  Employment        REVIEW    58       8-month gap unexplained    │    │
│  │  Education         CLEAR     100      Degree confirmed           │    │
│  │  Regulatory        CLEAR     100      Active licenses verified   │    │
│  │  Connections (D2)  CLEAR     88       No adverse associations    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  RECOMMENDED ACTIONS                                             │    │
│  │                                                                   │    │
│  │  1. Request explanation for employment gap (Jun 2021 - Feb 2022)│    │
│  │  2. Verify financial situation has stabilized since 2019        │    │
│  │  3. If satisfactory, proceed with hire                          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  [View Full Report]  [Request Additional Checks]  [Proceed to Offer]   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Content Specifications:**

| Section | Content | Data Source |
|---------|---------|-------------|
| Risk Assessment | Composite score (0-100), risk level, recommendation | Risk Analyzer output |
| Key Findings | Pass/Flag/Fail summary per check category | Finding categories |
| Category Breakdown | Per-category scores with brief notes | Category scores |
| Recommended Actions | AI-suggested next steps based on findings | Model-generated |

**Exclusions (HR Manager):**
- Raw data from providers
- Specific financial amounts
- Detailed litigation records
- Connection details (summary only)
- Source system identifiers

## Compliance Officer Audit Report

**Purpose:** Document compliance with regulations and audit requirements.

**Content Includes:**
- Consent reference and verification
- Disclosures provided (FCRA, state-specific)
- Compliance rules applied (with rule IDs)
- Data sources accessed (with timestamps, costs)
- Full audit trail (key events)
- Data handling compliance attestation

**Key Sections:**
1. Consent & Authorization
2. Compliance Rules Applied
3. Data Sources Accessed
4. Audit Trail (Key Events)
5. Data Handling Compliance

## Security Team Investigation Report

**Purpose:** Provide detailed findings for security assessment decisions.

**Content Includes:**
- Insider threat score with contributing/mitigating factors
- Connection network visualization (D3 analysis)
- Detailed findings with severity, source, confidence
- Evolution signals (compared to baseline)
- Full entity graph with risk propagation

**Key Sections:**
1. Threat Assessment
2. Connection Network (D3 Analysis)
3. Detailed Findings
4. Evolution Signals

## Subject Disclosure Report (FCRA Compliant)

**Purpose:** Inform subject of screening results; required for adverse action.

**Content Includes:**
- What was checked (list of check types)
- Summary of results (pass/flag/fail)
- Items requiring attention
- Subject rights under FCRA
- Data sources used
- Dispute process information

**Exclusions:**
- Risk scores
- AI assessments
- Connection analysis
- Source system identifiers
- Internal notes

## Executive Portfolio Report

**Purpose:** Aggregate view of organizational screening metrics and risk posture.

**Content Includes:**
- Portfolio risk snapshot (distribution)
- Screening activity metrics
- Top risk categories
- Risk by business unit
- Evolution alerts
- Spend & efficiency metrics

## Report Generation Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     REPORT GENERATION PIPELINE                           │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    UNIFIED DATA MODEL                            │    │
│  │                                                                  │    │
│  │  All reports draw from the same underlying data:                │    │
│  │  - Screening results                                            │    │
│  │  - Findings (categorized, scored)                               │    │
│  │  - Connection graphs                                            │    │
│  │  - Evolution signals                                            │    │
│  │  - Audit trail                                                  │    │
│  │  - Compliance metadata                                          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    PERSONA FILTER ENGINE                         │    │
│  │                                                                  │    │
│  │  Applies persona-specific:                                      │    │
│  │  - Field visibility rules (what data to include)                │    │
│  │  - Aggregation rules (detail vs. summary)                       │    │
│  │  - Redaction rules (PII masking levels)                         │    │
│  │  - Compliance overlays (FCRA disclosures, etc.)                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │                                          │
│         ┌────────────────────┼────────────────────┐                    │
│         ▼                    ▼                    ▼                    │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐           │
│  │  HR Summary  │     │   Audit      │     │  Security    │           │
│  │   Template   │     │  Template    │     │  Template    │           │
│  └──────────────┘     └──────────────┘     └──────────────┘           │
│         │                    │                    │                    │
│         ▼                    ▼                    ▼                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    OUTPUT FORMATTERS                             │    │
│  │                                                                  │    │
│  │  PDF Generator │ JSON Exporter │ Dashboard API │ Email Template │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Report Access Control

| Report Type | Default Access | Override Available |
|-------------|----------------|-------------------|
| HR Summary | HR Manager role | Yes (by admin) |
| Audit Report | Compliance role | No |
| Security Report | Security role + clearance | No |
| Investigator Case | Investigator role + case assignment | No |
| Subject Disclosure | Subject (authenticated) | No |
| Executive Portfolio | Executive role | Yes (delegate) |

## Report Data Models

```python
class ReportRequest(BaseModel):
    """Request to generate a report."""
    screening_id: UUID
    report_type: ReportType
    persona: ReportPersona
    format: OutputFormat  # pdf | json | html

    # Access control
    requester_id: UUID
    requester_role: Role

    # Options
    include_raw_data: bool = False  # Security/Investigator only
    redaction_level: RedactionLevel = RedactionLevel.STANDARD


class GeneratedReport(BaseModel):
    """A generated report."""
    report_id: UUID
    screening_id: UUID
    report_type: ReportType

    # Content
    content: bytes  # PDF or JSON
    format: OutputFormat

    # Metadata
    generated_at: datetime
    generated_by: str  # System or user ID
    template_version: str

    # Access tracking
    access_token: str  # Time-limited access
    access_expiry: datetime
    access_log: list[ReportAccess]


class ReportPersona(str, Enum):
    HR_MANAGER = "hr_manager"
    COMPLIANCE = "compliance"
    SECURITY = "security"
    INVESTIGATOR = "investigator"
    SUBJECT = "subject"
    EXECUTIVE = "executive"
```

## Report Templates

Each report type uses a template that defines:
- Sections to include
- Field visibility rules
- Aggregation rules
- Redaction rules
- Compliance requirements

```python
class ReportTemplate(BaseModel):
    persona: ReportPersona
    sections: list[ReportSection]

    # Field rules
    visible_fields: list[str]
    redacted_fields: list[str]
    aggregated_fields: list[str]

    # Compliance
    required_disclosures: list[DisclosureType]
    legal_notices: list[str]

    # Formatting
    branding: BrandingConfig
    layout: LayoutConfig
```

---

*See [11-interfaces.md](11-interfaces.md) for report display in dashboards*
*See [07-compliance.md](07-compliance.md) for FCRA disclosure requirements*
