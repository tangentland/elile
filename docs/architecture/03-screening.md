# Pre-Employment Screening

> **Prerequisites**: [01-design.md](01-design.md), [02-core-system.md](02-core-system.md)
>
> **See also**: [04-monitoring.md](04-monitoring.md) for ongoing monitoring, [05-investigation.md](05-investigation.md) for screening engine details

## Service Model Overview

The platform offers configurable service options across three dimensions: **Tier** (depth), **Vigilance** (frequency), and **Degrees** (breadth).

## Service Tiers (Depth of Investigation)

Controls *what* data sources are queried and the thoroughness of analysis.

| Tier | Name | Description |
|------|------|-------------|
| **T1** | Standard | Comprehensive screening using core data sources |
| **T2** | Enhanced | Standard + premium data sources (behavioral, OSINT, data brokers) |

```
┌─────────────────────────────────────────────────────────────────┐
│                      TIER COMPARISON                            │
├─────────────────────────────────┬────────────────┬──────────────┤
│ Check Category                  │ Standard (T1)  │ Enhanced (T2)│
├─────────────────────────────────┼────────────────┼──────────────┤
│ Identity Verification           │ ✓ Multi-source │ ✓ + Biometric│
│ Criminal (Domestic)             │ ✓ National+Cnty│ ✓            │
│ Criminal (International)        │ ✓              │ ✓            │
│ Employment History              │ ✓ 5 employers  │ ✓ Full + gaps│
│ Education                       │ ✓ All claimed  │ ✓ + Activities│
│ Credit/Financial                │ ✓ Where permtd │ ✓            │
│ Alternative Financial           │ ○              │ ✓            │
│ Bankruptcy/Liens/Judgments      │ ✓              │ ✓            │
│ Sanctions/PEP                   │ ✓              │ ✓            │
│ Civil Litigation                │ ✓ Federal+State│ ✓            │
│ Regulatory/License Verification │ ✓ + Enforcement│ ✓            │
│ Adverse Media                   │ ✓ Keyword      │ ✓ AI-analyzed│
│ Digital Footprint/OSINT         │ ○              │ ✓            │
│ Social Network Analysis         │ ○              │ ✓            │
│ Behavioral/Data Broker          │ ○              │ ✓ (consented)│
│ Location Pattern Analysis       │ ○              │ ✓ (consented)│
│ Dark Web Monitoring             │ ○              │ ✓            │
│ Extended Network (D3)           │ ○              │ ✓            │
├─────────────────────────────────┼────────────────┼──────────────┤
│ Default Human Review            │ Analyst        │ Investigator │
└─────────────────────────────────┴────────────────┴──────────────┘
  ✓ = Included    ○ = Not included / Not available
```

## Search Degrees (Relationship Breadth)

Controls *how wide* the relationship/connection analysis extends.

| Degree | Name | Scope | Available In |
|--------|------|-------|--------------|
| **D1** | Subject Only | Direct information about the subject | Standard, Enhanced |
| **D2** | Direct Connections | Subject + immediate associations | Standard, Enhanced |
| **D3** | Extended Network | D2 + second-degree connections | **Enhanced only** |

```
┌─────────────────────────────────────────────────────────────────┐
│                      DEGREE SCOPE DETAILS                       │
│                                                                 │
│  D1: SUBJECT ONLY                                               │
│  └── Subject's personal records only                            │
│                                                                 │
│  D2: DIRECT CONNECTIONS (includes D1)                           │
│  ├── Current/former employers (company sanctions, health)       │
│  ├── Business entities where subject is officer/director        │
│  ├── Business partners / co-founders                            │
│  ├── Household members (shared addresses)                       │
│  └── Disclosed relationships                                    │
│                                                                 │
│  D3: EXTENDED NETWORK (includes D1 + D2) - Enhanced only        │
│  ├── Directors/officers of connected entities                   │
│  ├── Subsidiary/parent company chains                           │
│  ├── Beneficial ownership tracing                               │
│  ├── Second-degree business connections                         │
│  ├── Shell company detection                                    │
│  └── Political exposure through connections                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Human Review Options

Independent add-on controlling level of human oversight.

| Option | Description | Typical Use |
|--------|-------------|-------------|
| **Automated Only** | AI-generated report, no human review | Cost-sensitive, low-risk |
| **Analyst Review** | Human analyst reviews findings, validates accuracy | Standard default |
| **Investigator Escalation** | Deep-dive investigation on flagged items | Enhanced default |
| **Dedicated Case Manager** | Named analyst for high-touch cases | Executive, VIP |

## Configuration Validation

```
┌─────────────────────────────────────────────────────────────────┐
│               VALID CONFIGURATION COMBINATIONS                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TIER          DEGREES         VIGILANCE       REVIEW           │
│  ──────────    ─────────       ──────────      ──────────       │
│  Standard  +   D1           +  V0-V3       +   Any      ✓ Valid │
│  Standard  +   D2           +  V0-V3       +   Any      ✓ Valid │
│  Standard  +   D3           +  Any         +   Any      ✗ Invalid│
│                                                                 │
│  Enhanced  +   D1           +  V0-V3       +   Any      ✓ Valid │
│  Enhanced  +   D2           +  V0-V3       +   Any      ✓ Valid │
│  Enhanced  +   D3           +  V0-V3       +   Any      ✓ Valid │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  CONSTRAINT: D3 (Extended Network) requires Enhanced tier       │
└─────────────────────────────────────────────────────────────────┘
```

## Service Configuration Model

```python
class ServiceConfiguration(BaseModel):
    """Complete service configuration for a screening."""

    tier: ServiceTier              # standard | enhanced
    vigilance: VigilanceLevel      # v0 | v1 | v2 | v3
    degrees: SearchDegree          # d1 | d2 | d3
    human_review: ReviewLevel      # automated | analyst | investigator | dedicated

    # Custom overrides (optional)
    additional_checks: list[CheckType] = []
    excluded_checks: list[CheckType] = []

    def validate(self) -> bool:
        """Validate configuration constraints."""
        # D3 requires Enhanced tier
        if self.degrees == SearchDegree.D3 and self.tier != ServiceTier.ENHANCED:
            return False
        return True


class ServiceTier(str, Enum):
    STANDARD = "standard"
    ENHANCED = "enhanced"


class VigilanceLevel(str, Enum):
    V0_PRESCREEN = "v0"      # One-time
    V1_ANNUAL = "v1"         # Every 12 months
    V2_MONTHLY = "v2"        # Every 30 days
    V3_BIMONTHLY = "v3"      # Twice per month


class SearchDegree(str, Enum):
    D1_SUBJECT = "d1"        # Subject only
    D2_DIRECT = "d2"         # Direct connections
    D3_EXTENDED = "d3"       # Extended network (Enhanced only)


class ReviewLevel(str, Enum):
    AUTOMATED = "automated"
    ANALYST = "analyst"
    INVESTIGATOR = "investigator"
    DEDICATED = "dedicated"
```

## Typical Role Configurations

| Sector | Role | Tier | Vigilance | Degrees | Review |
|--------|------|------|-----------|---------|--------|
| Government | Administrative | Standard | V1 | D1 | Analyst |
| Government | Policy/Intel | Enhanced | V2 | D2 | Investigator |
| Government | Classified | Enhanced | V3 | D3 | Investigator |
| Finance | Operations | Standard | V1 | D1 | Analyst |
| Finance | Client Advisory | Standard | V2 | D2 | Analyst |
| Finance | Trading/Treasury | Enhanced | V3 | D2 | Investigator |
| Finance | C-Suite | Enhanced | V2 | D3 | Dedicated |
| Energy | Field Ops | Standard | V1 | D1 | Analyst |
| Energy | Control Room | Standard | V2 | D1 | Analyst |
| Energy | Nuclear | Enhanced | V3 | D2 | Investigator |

## Service Configuration Manager

Validates and manages service configurations for screenings.

```
┌─────────────────────────────────────────────────────────────────┐
│                  SERVICE CONFIGURATION MANAGER                   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              CONFIGURATION VALIDATOR                     │    │
│  │                                                          │    │
│  │  Validates:                                              │    │
│  │  - Tier/Degree constraints (D3 → Enhanced only)         │    │
│  │  - Locale compatibility                                  │    │
│  │  - Customer entitlements                                 │    │
│  │  - Check type availability                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              DATA SOURCE RESOLVER                        │    │
│  │                                                          │    │
│  │  Maps configuration to specific data sources:           │    │
│  │  - Tier → Available provider categories                 │    │
│  │  - Degrees → Relationship query scope                   │    │
│  │  - Vigilance → Monitoring schedule                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              ENTITLEMENT CHECKER                         │    │
│  │                                                          │    │
│  │  Verifies customer has access to requested:             │    │
│  │  - Tier level                                            │    │
│  │  - Vigilance frequency                                   │    │
│  │  - Specific data sources                                │    │
│  │  - Human review levels                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Pre-Employment Screening Flow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  HRIS   │────►│ Validate│────►│Resolve  │────►│Compliance│────►│ Execute │
│ Request │     │ Config  │     │ Sources │     │  Filter  │     │ Core    │
│ (T/V/D) │     │         │     │(T1/T2)  │     │          │     │ Queries │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └────┬────┘
                                                                      │
                    ┌─────────────────────────────────────────────────┘
                    │
                    ▼ (if Enhanced)
              ┌─────────┐     ┌─────────┐     ┌─────────┐
              │ Execute │────►│ Analyze │────►│   Map   │
              │ Premium │     │ Results │     │Connections
              │ Queries │     │         │     │(D1/D2/D3)│
              └─────────┘     └─────────┘     └────┬────┘
                                                   │
                    ┌──────────────────────────────┘
                    │ (if D2/D3)
                    ▼
              ┌─────────┐     ┌─────────┐     ┌─────────┐
              │ Expand  │────►│ Execute │────►│ Analyze │
              │ Network │     │ Entity  │     │ Entity  │
              │         │     │ Queries │     │ Results │
              └─────────┘     └─────────┘     └────┬────┘
                                                   │
                    ┌──────────────────────────────┘
                    ▼
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  HRIS   │◄────│ Adverse │◄────│  Human  │◄────│ Generate│◄────│  Score  │
│ Update  │     │ Action? │     │ Review  │     │ Report  │     │  Risks  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘
```

## Screening Request Schema

```python
class ScreeningRequest(BaseModel):
    # Subject identification
    subject: SubjectInfo

    # Compliance context (REQUIRED)
    locale: Locale
    role_category: RoleCategory

    # Service configuration (REQUIRED)
    service_config: ServiceConfiguration

    # Or use preset
    # service_preset: str  # e.g., "government_classified"

    # Workflow
    callback_url: str | None
    priority: Priority = Priority.NORMAL

    # Consent reference
    consent_reference: str
```

---

*See [04-monitoring.md](04-monitoring.md) for ongoing monitoring (Vigilance)*
*See [05-investigation.md](05-investigation.md) for screening engine details*
