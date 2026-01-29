# Elile Architecture Document

## 1. System Overview

Elile is an employee risk assessment platform that performs comprehensive background investigations for pre-employment screening and ongoing employee monitoring. The system operates at global scale with locale-aware compliance enforcement.

### 1.1 Design Principles

- **Compliance-First**: All operations are gated by jurisdiction-specific compliance rules
- **Audit Everything**: Complete traceability of all data access and decisions
- **Provider Agnostic**: Abstracted interfaces for data providers and AI models
- **Resilient**: Graceful degradation when providers are unavailable
- **Scalable**: Async-first design supporting high-volume concurrent screenings
- **Configurable**: Flexible service tiers and options to match diverse customer needs

### 1.2 Key Actors

| Actor | Description |
|-------|-------------|
| **Requesting System** | HRIS or screening portal initiating background checks |
| **Subject** | Employee or candidate being screened (consent required) |
| **Reviewer** | Human analyst reviewing findings and making decisions |
| **Administrator** | System admin configuring compliance rules and providers |

---
<div style="break-after: page;"></div>

## 2. Service Model

The platform offers configurable service options across three dimensions: **Tier** (depth), **Vigilance** (frequency), and **Degrees** (breadth).

### 2.1 Service Tiers (Depth of Investigation)

Controls *what* data sources are queried and the thoroughness of analysis.

| Tier | Name | Description |
|------|------|-------------|
| **T1** | Standard | Comprehensive screening using core data sources |
| **T2** | Enhanced | Standard + premium data sources (behavioral, OSINT, data brokers) |

```
┌─────────────────────────────────────────────────────────────────┐
│                      TIER COMPARISON                             │
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
<div style="break-after: page;"></div>

### 2.2 Vigilance Levels (Monitoring Frequency)

Controls *how often* re-screening occurs for ongoing monitoring.

| Level | Name | Frequency | Checks/Year | Use Case |
|-------|------|-----------|-------------|----------|
| **V0** | Pre-screen | One-time only | 1 | Contractors, low-risk roles |
| **V1** | Annual | Every 12 months | 1 | Standard regulated employees |
| **V2** | Monthly | Every 30 days | 12 | Elevated risk, trading, treasury |
| **V3** | Bi-monthly | Twice per month | 24 | Critical infrastructure, nuclear |

```
┌─────────────────────────────────────────────────────────────────┐
│                  VIGILANCE MONITORING SCOPE                      │
├──────────┬─────────────┬────────────────────────────────────────┤
│ Level    │ Frequency   │ What's Monitored                       │
├──────────┼─────────────┼────────────────────────────────────────┤
│ V0       │ One-time    │ N/A - no ongoing monitoring            │
├──────────┼─────────────┼────────────────────────────────────────┤
│ V1       │ Annual      │ Full re-screen (same as initial)       │
├──────────┼─────────────┼────────────────────────────────────────┤
│ V2       │ Monthly     │ Criminal records, sanctions/PEP,       │
│          │             │ adverse media, regulatory actions,     │
│          │             │ civil litigation                       │
├──────────┼─────────────┼────────────────────────────────────────┤
│ V3       │ 2x/month    │ V2 checks + real-time sanctions alerts │
│          │             │ + continuous adverse media monitoring  │
│          │             │ + dark web monitoring (Enhanced only)  │
└──────────┴─────────────┴────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 2.3 Search Degrees (Relationship Breadth)

Controls *how wide* the relationship/connection analysis extends.

| Degree | Name | Scope | Available In |
|--------|------|-------|--------------|
| **D1** | Subject Only | Direct information about the subject | Standard, Enhanced |
| **D2** | Direct Connections | Subject + immediate associations | Standard, Enhanced |
| **D3** | Extended Network | D2 + second-degree connections | **Enhanced only** |

```
┌─────────────────────────────────────────────────────────────────┐
│                      DEGREE SCOPE DETAILS                        │
│                                                                  │
│  D1: SUBJECT ONLY                                               │
│  └── Subject's personal records only                            │
│                                                                  │
│  D2: DIRECT CONNECTIONS (includes D1)                           │
│  ├── Current/former employers (company sanctions, health)       │
│  ├── Business entities where subject is officer/director        │
│  ├── Business partners / co-founders                            │
│  ├── Household members (shared addresses)                       │
│  └── Disclosed relationships                                    │
│                                                                  │
│  D3: EXTENDED NETWORK (includes D1 + D2) - Enhanced only        │
│  ├── Directors/officers of connected entities                   │
│  ├── Subsidiary/parent company chains                           │
│  ├── Beneficial ownership tracing                               │
│  ├── Second-degree business connections                         │
│  ├── Shell company detection                                    │
│  └── Political exposure through connections                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 2.4 Human Review Options

Independent add-on controlling level of human oversight.

| Option | Description | Typical Use |
|--------|-------------|-------------|
| **Automated Only** | AI-generated report, no human review | Cost-sensitive, low-risk |
| **Analyst Review** | Human analyst reviews findings, validates accuracy | Standard default |
| **Investigator Escalation** | Deep-dive investigation on flagged items | Enhanced default |
| **Dedicated Case Manager** | Named analyst for high-touch cases | Executive, VIP |

### 2.5 Configuration Validation

```
┌─────────────────────────────────────────────────────────────────┐
│               VALID CONFIGURATION COMBINATIONS                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TIER          DEGREES         VIGILANCE       REVIEW           │
│  ──────────    ─────────       ──────────      ──────────       │
│  Standard  +   D1           +  V0-V3       +   Any      ✓ Valid │
│  Standard  +   D2           +  V0-V3       +   Any      ✓ Valid │
│  Standard  +   D3           +  Any         +   Any      ✗ Invalid│
│                                                                  │
│  Enhanced  +   D1           +  V0-V3       +   Any      ✓ Valid │
│  Enhanced  +   D2           +  V0-V3       +   Any      ✓ Valid │
│  Enhanced  +   D3           +  V0-V3       +   Any      ✓ Valid │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  CONSTRAINT: D3 (Extended Network) requires Enhanced tier       │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 2.6 Service Configuration Model

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
<div style="break-after: page;"></div>

### 2.7 Typical Role Configurations

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

---
<div style="break-after: page;"></div>

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SYSTEMS                                │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│   HRIS Systems  │  Data Providers │   AI Models     │   Notification        │
│   - Workday     │  - Core (T1)    │   - Claude      │   - Email             │
│   - SuccessF.   │  - Premium (T2) │   - GPT-4       │   - Webhooks          │
│   - Oracle HCM  │  - Data Brokers │   - Gemini      │                       │
│   - ADP         │  - OSINT        │                 │                       │
└────────┬────────┴────────┬────────┴────────┬────────┴───────────┬───────────┘
         │                 │                 │                     │
         ▼                 ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            INTEGRATION LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ HRIS Adapter │  │Provider Adpt.│  │ Model Adapter│  │ Notification │     │
│  │   Gateway    │  │   Gateway    │  │   Gateway    │  │   Gateway    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CORE PLATFORM                                   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        API GATEWAY / ORCHESTRATION                      │ │
│  │                         (Request routing, auth, rate limiting)          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│    ┌─────────────────────────────────┼─────────────────────────────────┐    │
│    ▼                                 ▼                                 ▼    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Service    │  │  Screening   │  │  Compliance  │  │    Report    │    │
│  │ Config Mgr   │  │   Engine     │  │    Engine    │  │   Generator  │    │
│  │              │  │  (LangGraph) │  │              │  │              │    │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘  └──────────────┘    │
│         │                 │                                                  │
│         ▼                 ▼                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │    Query     │  │     Risk     │  │  Connection  │  │    Audit     │    │
│  │  Generator   │  │   Analyzer   │  │    Mapper    │  │    Logger    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Subject    │  │   Screening  │  │   Service    │  │    Audit     │     │
│  │   Records    │  │   Results    │  │   Configs    │  │     Logs     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---
<div style="break-after: page;"></div>

## 4. Data Sources

### 4.1 Core Data Sources (Standard Tier)

Available in both Standard and Enhanced tiers.

```
┌─────────────────────────────────────────────────────────────────┐
│                    CORE DATA SOURCES (T1)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  IDENTITY VERIFICATION                                          │
│  ├── Government ID databases (SSA, DVLA, national registries)  │
│  ├── Address verification (postal, utility databases)          │
│  └── Multi-source identity confirmation                         │
│                                                                  │
│  CRIMINAL RECORDS                                               │
│  ├── National criminal databases                                │
│  ├── County/state court records                                 │
│  ├── International criminal (Interpol, country-specific)       │
│  └── Sex offender registries                                    │
│                                                                  │
│  EMPLOYMENT VERIFICATION                                        │
│  ├── The Work Number (Equifax)                                  │
│  ├── Direct employer verification                               │
│  └── Professional reference checks                              │
│                                                                  │
│  EDUCATION VERIFICATION                                         │
│  ├── National Student Clearinghouse                             │
│  ├── University registrar verification                          │
│  └── Professional certification bodies                          │
│                                                                  │
│  FINANCIAL RECORDS (where permitted)                            │
│  ├── Credit bureau reports (Experian, Equifax, TransUnion)     │
│  ├── Bankruptcy filings (PACER, national registries)           │
│  ├── Tax liens and judgments                                    │
│  └── Property records                                           │
│                                                                  │
│  SANCTIONS & WATCHLISTS                                         │
│  ├── OFAC SDN List                                              │
│  ├── UN Security Council sanctions                              │
│  ├── EU/UK sanctions lists                                      │
│  ├── PEP databases (World-Check, Dow Jones)                    │
│  └── National law enforcement watchlists                        │
│                                                                  │
│  CIVIL LITIGATION                                               │
│  ├── Federal court records (PACER)                              │
│  ├── State court records                                        │
│  └── Arbitration/mediation records                              │
│                                                                  │
│  REGULATORY & LICENSING                                         │
│  ├── Professional license verification                          │
│  ├── FINRA BrokerCheck                                          │
│  ├── State bar associations                                     │
│  ├── Medical board records                                      │
│  ├── SEC IAPD                                                   │
│  └── Industry-specific regulators (NRC, FERC, etc.)            │
│                                                                  │
│  ADVERSE MEDIA (Keyword-based)                                  │
│  ├── News archives (LexisNexis, Factiva)                       │
│  └── Public records aggregators                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

**Core Provider Categories:**

| Category | Providers | Check Types |
|----------|-----------|-------------|
| Aggregators | Sterling, HireRight, Checkr | Full suite |
| Credit Bureaus | Experian, Equifax, TransUnion | Credit, Identity |
| Court Records | PACER, CourtListener, state systems | Criminal, Civil |
| Sanctions | World-Check, Dow Jones, OFAC direct | PEP, Sanctions |
| Employment | The Work Number, direct verification | Employment history |
| Education | NSC, direct verification | Education |

### 4.2 Premium Data Sources (Enhanced Tier Only)

Additional sources available only with Enhanced tier.

```
┌─────────────────────────────────────────────────────────────────┐
│                  PREMIUM DATA SOURCES (T2)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DIGITAL FOOTPRINT / OSINT                                      │
│  ├── Username enumeration across platforms                      │
│  ├── Domain/IP ownership records (WHOIS)                        │
│  ├── Email breach detection                                     │
│  ├── Public social media analysis                               │
│  └── Online alias correlation                                   │
│                                                                  │
│  DARK WEB MONITORING                                            │
│  ├── Credential leak detection                                  │
│  ├── PII exposure monitoring                                    │
│  ├── Mention monitoring                                         │
│  └── Forum/marketplace surveillance                             │
│                                                                  │
│  BEHAVIORAL / DATA BROKERS                                      │
│  ├── Acxiom (demographics, interests, life events)             │
│  ├── Oracle Data Cloud / BlueKai (interest segments)           │
│  ├── Experian Marketing (consumer segments)                     │
│  ├── LiveRamp (identity resolution)                             │
│  ├── Nielsen (media consumption)                                │
│  └── Epsilon (transaction patterns)                             │
│                                                                  │
│  LOCATION / MOVEMENT DATA (with consent)                        │
│  ├── Foursquare / Factual (venue visits)                       │
│  ├── SafeGraph (foot traffic patterns)                          │
│  ├── Placer.ai (location analytics)                             │
│  └── Travel pattern analysis                                    │
│                                                                  │
│  ALTERNATIVE FINANCIAL DATA                                     │
│  ├── Utility payment history                                    │
│  ├── Rental payment history (Experian RentBureau)              │
│  ├── BNPL usage patterns                                        │
│  ├── Bank transaction analysis (Plaid, Finicity - consented)   │
│  └── Crypto wallet analysis                                     │
│                                                                  │
│  ADVANCED ADVERSE MEDIA                                         │
│  ├── AI-powered sentiment analysis                              │
│  ├── Context-aware relevance scoring                            │
│  ├── Multi-language monitoring                                  │
│  └── Social media sentiment                                     │
│                                                                  │
│  RELATIONSHIP INTELLIGENCE                                      │
│  ├── Beneficial ownership databases (OpenOwnership, etc.)      │
│  ├── Corporate registry deep analysis                           │
│  ├── Shell company detection algorithms                         │
│  ├── Political connection mapping                               │
│  ├── Pipl / FullContact (identity resolution)                  │
│  └── Extended network graph analysis                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

**Premium Provider Categories:**

| Category | Providers | Data Types |
|----------|-----------|------------|
| Data Brokers | Acxiom, Oracle Data Cloud, Experian Marketing | Behavioral, interests, demographics |
| Identity Resolution | Pipl, FullContact, LiveRamp | Cross-platform identity linking |
| Location Intelligence | Foursquare, SafeGraph, Placer.ai | Movement patterns, venue visits |
| Alternative Finance | Plaid, Finicity, Experian RentBureau | Transaction data, payment history |
| OSINT Platforms | Maltego, SpiderFoot, custom tools | Digital footprint aggregation |
| Dark Web | Recorded Future, Flashpoint, DarkOwl | Leak detection, threat intel |
| Corporate Intelligence | OpenCorporates, Orbis, Dun & Bradstreet | Beneficial ownership, corporate links |

### 4.3 Data Source Compliance Considerations

| Data Type | Compliance Concern | Mitigation |
|-----------|-------------------|------------|
| Behavioral/Interest data | May proxy for protected classes | Filter categories, document business necessity |
| Location data | Privacy laws, consent requirements | Explicit consent, purpose limitation |
| Social media | GDPR Art. 9, EEOC concerns | Limit to public, exclude protected content |
| Dark web | Data provenance concerns | Use for security only, not adverse decisions |
| Data broker segments | FCRA applicability unclear | Exclude from adverse action basis |
| Political/religious indicators | Protected in most jurisdictions | Exclude from analysis |

---
<div style="break-after: page;"></div>

## 5. Data Persistence & Evolution

The platform implements a comprehensive data persistence strategy to optimize costs, enable cross-screening data reuse, and support longitudinal risk analysis.

### 5.1 Entity Data Lake

Centralized storage for all discovered entities with cached provider data.

```
┌─────────────────────────────────────────────────────────────────┐
│                      ENTITY DATA LAKE                            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    ENTITY REGISTRY                       │    │
│  │                                                          │    │
│  │  All entities (subjects + discovered connections):      │    │
│  │  - Individuals (employees, candidates, associates)      │    │
│  │  - Organizations (employers, business entities)         │    │
│  │  - Addresses (residences, business locations)           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  DATA SOURCE CACHE                       │    │
│  │                                                          │    │
│  │  Per-entity, per-source cached results:                 │    │
│  │  - Raw provider response (encrypted)                    │    │
│  │  - Acquisition timestamp                                 │    │
│  │  - Freshness status (fresh | stale | expired)           │    │
│  │  - Cost incurred                                         │    │
│  │  - Source provider                                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 CROSS-SCREENING INDEX                    │    │
│  │                                                          │    │
│  │  Links entities across screenings:                       │    │
│  │  - Employee A → Company X (employer)                    │    │
│  │  - Employee B → Company X (employer) ← SHARED           │    │
│  │  - Employee C → Person D (household)                    │    │
│  │  - Employee E → Person D (business partner) ← SHARED    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.2 Cache Sharing Model

Data caching strategy based on data origin:

| Data Origin | Cache Scope | Rationale |
|-------------|-------------|-----------|
| **Paid external providers** | Platform-wide (shared) | Cost already incurred; maximize ROI |
| **Customer-provided data** | Customer-isolated | Proprietary; competitive sensitivity |

```
┌─────────────────────────────────────────────────────────────────┐
│                      CACHE ARCHITECTURE                          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              SHARED CACHE (Platform-wide)               │    │
│  │                                                          │    │
│  │  Paid external sources - shared across all customers:   │    │
│  │  - Court records (PACER, state courts)                  │    │
│  │  - Corporate registries                                  │    │
│  │  - Sanctions/PEP lists                                   │    │
│  │  - Credit bureaus                                        │    │
│  │  - Data brokers (Acxiom, etc.)                          │    │
│  │  - OSINT providers                                       │    │
│  │  - All paid API responses                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │         CUSTOMER-ISOLATED CACHE (per tenant)            │    │
│  │                                                          │    │
│  │  Customer-provided data - isolated per customer:        │    │
│  │  - Employee records from HRIS                           │    │
│  │  - Internal verification results                        │    │
│  │  - Customer-specific reference checks                   │    │
│  │  - Proprietary risk assessments                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.3 Data Freshness Model

Different data types age at different rates:

| Data Category | Freshness Window | Stale Window | Rationale |
|---------------|------------------|--------------|-----------|
| Sanctions/PEP | 0 (always refresh) | N/A | Regulatory requirement |
| Criminal records | 7 days | 30 days | Court batch updates |
| Adverse media | 24 hours | 7 days | Time-sensitive |
| Civil litigation | 14 days | 60 days | Less time-sensitive |
| Credit/Financial | 30 days | 90 days | Monthly cycles |
| Corporate registry | 30 days | 90 days | Quarterly filings |
| OSINT/Digital | 30 days | 90 days | Online presence evolves |
| Employment verification | 90 days | 180 days | Stable data |
| Behavioral/Data broker | 90 days | 180 days | Patterns change slowly |
| Education | 365 days | Never expires | Rarely changes |

**Freshness States:**
```
┌──────────┐   (freshness_window)   ┌──────────┐   (stale_window)   ┌──────────┐
│  FRESH   │ ─────────────────────► │  STALE   │ ─────────────────► │ EXPIRED  │
│          │                        │          │                     │          │
│ Use as-is│                        │ Use with │                     │ Must     │
│          │                        │ flag     │                     │ refresh  │
└──────────┘                        └──────────┘                     └──────────┘
```
<div style="break-after: page;"></div>

### 5.4 Stale Data Policy (Tier-Aware)

When data is stale, behavior varies by check type and service tier:

```
┌─────────────────────────────────────────────────────────────────┐
│                    STALE DATA POLICY MATRIX                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Check Type              │ Standard Tier    │ Enhanced Tier     │
│  ────────────────────────┼──────────────────┼─────────────────  │
│  Sanctions/PEP           │ BLOCK (refresh)  │ BLOCK (refresh)   │
│  Criminal records        │ Use + flag       │ BLOCK (refresh)   │
│  Adverse media           │ Use + flag       │ BLOCK (refresh)   │
│  Civil litigation        │ Use + flag       │ Use + flag        │
│  Credit/Financial        │ Use + flag       │ Use + flag        │
│  Employment verification │ Use + flag       │ Use + flag        │
│  Education               │ Use + flag       │ Use + flag        │
│  Corporate registry      │ Use + flag       │ Use + flag        │
│  Behavioral/Data broker  │ N/A              │ Use + flag        │
│  OSINT/Digital footprint │ N/A              │ Use + flag        │
│                                                                  │
│  BLOCK    = Wait for fresh data before proceeding               │
│  Use+flag = Proceed with stale data, flag in report,            │
│             queue async refresh                                  │
│                                                                  │
│  All policies configurable at platform level                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.5 Data Acquisition Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         DATA ACQUISITION FLOW                             │
│                                                                           │
│  Screening Request                                                        │
│       │                                                                   │
│       ▼                                                                   │
│  ┌─────────────────┐                                                     │
│  │ Resolve Entity  │ (see Entity Resolution below)                       │
│  │ (find or create)│                                                     │
│  └────────┬────────┘                                                     │
│           │                                                               │
│           ▼                                                               │
│  ┌─────────────────┐     ┌───────────────┐     ┌───────────────┐        │
│  │ Check Cache for │────►│    FRESH?     │────►│  Use cached   │        │
│  │ required checks │     │               │ Yes │  data         │        │
│  └─────────────────┘     └───────┬───────┘     └───────────────┘        │
│                                  │ No                                     │
│                                  ▼                                        │
│                          ┌───────────────┐     ┌───────────────┐        │
│                          │    STALE?     │────►│ Check policy  │        │
│                          │               │ Yes │ (tier-aware)  │        │
│                          └───────┬───────┘     └───────┬───────┘        │
│                                  │ No                  │                 │
│                                  ▼                     ▼                 │
│                          ┌───────────────┐     ┌───────────────┐        │
│                          │   EXPIRED /   │     │ Use + flag OR │        │
│                          │   MISSING     │     │ Block + wait  │        │
│                          └───────┬───────┘     └───────────────┘        │
│                                  │                                        │
│                                  ▼                                        │
│                          ┌───────────────┐                               │
│                          │ Query Provider│                               │
│                          │ + Cache Result│                               │
│                          │ + Track Cost  │                               │
│                          └───────────────┘                               │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.6 Entity Resolution

Matching/deduplicating entities across screenings with tier-based human review:

```
┌─────────────────────────────────────────────────────────────────┐
│                   ENTITY RESOLUTION FLOW                         │
│                                                                  │
│  Incoming Entity                                                 │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────┐                                            │
│  │  EXACT MATCH    │──── Match found ────► Use existing entity  │
│  │  (SSN, EIN,     │                                            │
│  │   passport)     │                                            │
│  └────────┬────────┘                                            │
│           │ No match                                             │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │  FUZZY MATCH    │──── High confidence ──► Use existing entity│
│  │  (name+DOB+addr)│     (score > 0.95)                         │
│  └────────┬────────┘                                            │
│           │ Ambiguous (0.70 - 0.95)                             │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    TIER CHECK                            │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │                                                          │    │
│  │  STANDARD TIER              │  ENHANCED TIER             │    │
│  │  ─────────────              │  ─────────────             │    │
│  │  Auto-resolve:              │  Queue for human review:   │    │
│  │  - Score > 0.85 → match     │  - Analyst validates match │    │
│  │  - Score < 0.85 → new entity│  - Can merge/split entities│    │
│  │  - Flag uncertainty in      │  - Resolution audit trail  │    │
│  │    report                   │                            │    │
│  │                             │                            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  No match (score < 0.70)                                        │
│       │                                                          │
│       ▼                                                          │
│  Create new entity                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.7 Versioned Entity Profiles

Each screening iteration creates an immutable profile snapshot:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENTITY PROFILE STORE                          │
│                                                                  │
│  Entity: John Smith (employee_12345)                            │
│  ├── Profile v1 (2024-01-15) ─ Pre-employment screening        │
│  │   ├── Findings snapshot                                      │
│  │   ├── Risk score: 0.15 (low)                                │
│  │   ├── Connections: 12 entities                              │
│  │   └── Data sources used: [list]                             │
│  │                                                               │
│  ├── Profile v2 (2024-07-15) ─ 6-month monitoring              │
│  │   ├── Findings snapshot                                      │
│  │   ├── Risk score: 0.22 (low) ↑                              │
│  │   ├── Connections: 18 entities (+6)                         │
│  │   ├── Delta from v1: New civil judgment discovered          │
│  │   └── Data sources used: [list]                             │
│  │                                                               │
│  └── Profile v3 (2025-01-15) ─ Annual re-screen                │
│      ├── Findings snapshot                                      │
│      ├── Risk score: 0.45 (medium) ↑↑                          │
│      ├── Connections: 35 entities (+17)                        │
│      ├── Delta from v2: 3 new shell companies detected         │
│      ├── Evolution signals: [network_expansion_rapid]          │
│      └── Data sources used: [list]                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.8 Risk Evolution Analytics

Pattern detection across profile versions to identify emerging risks.

```
┌─────────────────────────────────────────────────────────────────┐
│                  RISK EVOLUTION ANALYZER                         │
│                                                                  │
│  PHASE 1: RULE-BASED SIGNATURES (Initial Implementation)       │
│  ─────────────────────────────────────────────────────────      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              TEMPORAL PATTERN DETECTOR                   │    │
│  │                                                          │    │
│  │  Analyzes profile version deltas for:                   │    │
│  │                                                          │    │
│  │  NETWORK EVOLUTION                                       │    │
│  │  - Rapid network expansion (>200% in 6mo = shell co.)   │    │
│  │  - New high-risk connections appearing                  │    │
│  │  - Connections to newly-sanctioned entities             │    │
│  │  - Network clustering changes                           │    │
│  │                                                          │    │
│  │  FINANCIAL TRAJECTORY                                    │    │
│  │  - Progressive credit deterioration                     │    │
│  │  - Accumulating judgments/liens                         │    │
│  │  - Lifestyle inflation (behavioral data)               │    │
│  │  - New undisclosed business interests                   │    │
│  │                                                          │    │
│  │  BEHAVIORAL DRIFT                                        │    │
│  │  - Employment instability pattern                        │    │
│  │  - Geographic mobility anomalies                        │    │
│  │  - Digital footprint changes                            │    │
│  │                                                          │    │
│  │  LEGAL ESCALATION                                        │    │
│  │  - Civil → Criminal progression                         │    │
│  │  - Increasing litigation frequency                      │    │
│  │  - Regulatory action accumulation                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              SIGNATURE LIBRARY                           │    │
│  │                                                          │    │
│  │  Known risk evolution patterns (rule-based):            │    │
│  │  - "Insider threat trajectory"                          │    │
│  │  - "Financial distress cascade"                         │    │
│  │  - "Shell company buildup"                              │    │
│  │  - "Influence network construction"                     │    │
│  │  - "Identity fragmentation"                             │    │
│  │                                                          │    │
│  │  Analyst feedback loop: confirm/reject signals          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  PHASE 2: ML AUGMENTATION (Future, when data accumulates)      │
│  ─────────────────────────────────────────────────────────      │
│  - Training data from confirmed Phase 1 signals                │
│  - Anomaly detection for unknown patterns                      │
│  - Pattern discovery from historical profiles                  │
│  - Human-in-the-loop validation                                │
│                                                                  │
│  Prerequisites:                                                 │
│  - Sufficient profile version history                          │
│  - Labeled outcomes (confirmed risks, false positives)         │
│  - Analyst feedback corpus                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.9 Data Retention Policy

| Data Class | Default Retention | Configurable | Notes |
|------------|-------------------|--------------|-------|
| Profile versions | Indefinite | Yes | Core analytical value |
| Findings/analysis | Indefinite | Yes | Core analytical value |
| Connection graphs | Indefinite | Yes | Core analytical value |
| Raw provider responses | 1 year | Yes | Minimize storage |
| Behavioral data | 2 years | Yes | Privacy consideration |
| Audit logs | 7 years | No | Compliance requirement |

### 5.10 GDPR Erasure Capability

```
┌─────────────────────────────────────────────────────────────────┐
│                    GDPR ERASURE PROCESS                          │
│                                                                  │
│  Triggered by:                                                  │
│  - Subject erasure request (Art. 17)                           │
│  - Locale-based automatic policy (EU subjects)                 │
│  - Customer-initiated purge                                    │
│                                                                  │
│  Process:                                                       │
│  1. Validate request (identity, legal basis)                   │
│  2. Identify all entity references across system               │
│  3. For each data class:                                       │
│     - Delete OR anonymize (configurable)                       │
│     - Anonymization preserves aggregate analytics              │
│  4. Cascade through:                                           │
│     - Entity registry                                          │
│     - Profile versions                                         │
│     - Cached provider data                                     │
│     - Connection graphs (remove or anonymize edges)            │
│  5. Create audit record of erasure (retained for compliance)   │
│  6. Notify dependent systems                                   │
│                                                                  │
│  Exceptions (retained per legal requirement):                  │
│  - Audit logs (anonymized subject reference)                   │
│  - Aggregated/anonymized analytics                             │
│  - Legal hold data                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.11 Data Models

```python
class Entity(BaseModel):
    """Core entity in the system."""
    entity_id: UUID
    entity_type: EntityType  # individual | organization | address
    canonical_identifiers: dict[str, str]  # SSN, EIN, passport, etc.
    created_at: datetime

    # Cross-reference tracking
    screenings: list[UUID]  # Screenings referencing this entity
    related_entities: list[EntityRelation]


class CachedDataSource(BaseModel):
    """Cached data from a provider for an entity."""
    cache_id: UUID
    entity_id: UUID
    provider_id: str
    check_type: CheckType

    # Origin (determines sharing scope)
    data_origin: DataOrigin  # paid_external | customer_provided
    customer_id: UUID | None  # Set if customer_provided

    # Freshness
    acquired_at: datetime
    freshness_status: FreshnessStatus  # fresh | stale | expired
    fresh_until: datetime
    stale_until: datetime

    # Data
    raw_response: bytes  # Encrypted
    normalized_data: dict

    # Cost tracking
    cost_incurred: Decimal
    cost_currency: str

<div style="break-after: page;"></div>

class EntityProfile(BaseModel):
    """Versioned profile snapshot for an entity."""
    profile_id: UUID
    entity_id: UUID
    version: int
    created_at: datetime

    # Trigger
    trigger_type: ProfileTrigger  # screening | monitoring | manual
    trigger_id: UUID  # Reference to screening/monitoring run

    # Snapshot
    findings: list[Finding]
    risk_score: RiskScore
    connections: list[EntityConnection]
    connection_count: int

    # Sources used
    data_sources_used: list[DataSourceRef]
    stale_data_used: list[DataSourceRef]  # Flagged stale sources

    # Comparison to previous
    previous_version: int | None
    delta: ProfileDelta | None


class ProfileDelta(BaseModel):
    """Changes between profile versions."""
    new_findings: list[Finding]
    resolved_findings: list[Finding]
    changed_findings: list[FindingChange]

    risk_score_change: float
    connection_count_change: int
    new_connections: list[EntityConnection]
    lost_connections: list[EntityConnection]

    # Computed signals
    evolution_signals: list[EvolutionSignal]


class EvolutionSignal(BaseModel):
    """Detected pattern in profile evolution."""
    signal_type: str  # e.g., "network_expansion", "financial_deterioration"
    confidence: float
    severity: str  # low | medium | high | critical
    description: str
    contributing_factors: list[str]
    pattern_signature: str | None  # Reference to known pattern library

    # Analyst feedback (for ML training)
    analyst_confirmed: bool | None
    feedback_timestamp: datetime | None


class DataOrigin(str, Enum):
    PAID_EXTERNAL = "paid_external"      # Shared cache
    CUSTOMER_PROVIDED = "customer_provided"  # Isolated cache


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
```

---
<div style="break-after: page;"></div>

## 6. Core Components

### 5.1 Service Configuration Manager

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
<div style="break-after: page;"></div>

### 5.2 Screening Engine (LangGraph Orchestration)

The central workflow engine that orchestrates the screening process.

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCREENING WORKFLOW                            │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │Initialize│───►│ Validate │───►│Compliance│───►│  Resolve │  │
│  │ Request  │    │  Config  │    │   Check  │    │  Sources │  │
│  └──────────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘  │
│                       │               │               │         │
│             (invalid) │     (blocked) │               ▼         │
│                       ▼               ▼         ┌──────────┐    │
│                 ┌──────────┐   ┌──────────┐    │ Execute  │    │
│                 │  Reject  │   │  Reject  │    │ Queries  │    │
│                 │ (config) │   │(compliance)   └────┬─────┘    │
│                 └──────────┘   └──────────┘         │          │
│                                                      ▼          │
│                                               ┌──────────┐      │
│                                               │ Analyze  │      │
│                                               │ Results  │      │
│                                               └────┬─────┘      │
│                                                    │            │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    │            │
│  │ Generate │◄───│  Score   │◄───│   Map    │◄───┘            │
│  │  Report  │    │  Risks   │    │Connections│                 │
│  └────┬─────┘    └──────────┘    └──────────┘                  │
│       │                                  ▲                      │
│       │                                  │ (D2/D3)              │
│       ▼                                  │                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │  Human   │───►│ Complete │    │ Expand   │                  │
│  │  Review  │    │          │    │ Network  │                  │
│  └──────────┘    └──────────┘    └──────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

**State Model:**
```python
class ScreeningState(TypedDict):
    # Request context
    request_id: str
    subject: SubjectInfo
    locale: Locale
    screening_type: ScreeningType  # pre_employment | ongoing_monitoring
    role_category: RoleCategory    # government | energy | finance | other

    # Service configuration
    service_config: ServiceConfiguration
    resolved_sources: list[DataSourceSpec]

    # Compliance
    permitted_checks: list[CheckType]
    blocked_checks: list[BlockedCheck]

    # Search state
    current_degree: SearchDegree   # d1 | d2 | d3
    queries: list[SearchQuery]
    results: list[SearchResult]

    # Entities discovered (for D2/D3)
    discovered_entities: list[Entity]
    entity_queue: list[Entity]     # Entities pending investigation

    # Analysis
    findings: list[Finding]
    risk_score: RiskScore
    connections: list[EntityConnection]

    # Output
    report: Report | None
    status: ScreeningStatus
    review_status: ReviewStatus    # pending | in_review | approved | escalated

    # Audit
    audit_trail: list[AuditEvent]
```
<div style="break-after: page;"></div>

### 5.3 Compliance Engine

Enforces jurisdiction-specific rules, now tier-aware.

```
┌─────────────────────────────────────────────────────────────────┐
│                      COMPLIANCE ENGINE                           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    RULE REPOSITORY                       │    │
│  │                                                          │    │
│  │  Rules indexed by:                                       │    │
│  │  - Locale (US, EU, CA, APAC, LATAM)                     │    │
│  │  - Check type                                            │    │
│  │  - Role category                                         │    │
│  │  - Data source tier (core vs premium)                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    RULE EVALUATOR                        │    │
│  │                                                          │    │
│  │  Input:  (locale, role_category, check_type,            │    │
│  │           service_tier, data_source)                    │    │
│  │  Output: (permitted: bool, restrictions: list)          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               TIER-AWARE RESTRICTIONS                    │    │
│  │                                                          │    │
│  │  Premium source restrictions (Enhanced tier):           │    │
│  │  - Behavioral data: Exclude protected categories        │    │
│  │  - Location data: Require explicit consent              │    │
│  │  - Social media: Public only, exclude Art. 9 content   │    │
│  │  - Dark web: Security use only, not for decisions      │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

**Extended Rule Definition:**
```python
class ComplianceRule(BaseModel):
    locale: Locale
    check_type: CheckType
    role_categories: list[RoleCategory] | None  # None = all roles

    # Tier applicability
    applicable_tiers: list[ServiceTier]  # Which tiers this rule applies to
    data_source_category: DataSourceCategory  # core | premium

    permitted: bool
    conditions: list[Condition]
    lookback_years: int | None
    required_disclosures: list[DisclosureType]
    data_restrictions: list[FieldRestriction]

    # Premium source specific
    requires_explicit_consent: bool = False
    excluded_data_categories: list[str] = []  # e.g., ["political", "religious"]
```

### 5.4 Data Provider Gateway

Unified interface with tier-aware routing.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA PROVIDER GATEWAY                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 PROVIDER REGISTRY                        │    │
│  │                                                          │    │
│  │  ┌─────────────────────┐  ┌─────────────────────┐       │    │
│  │  │   CORE PROVIDERS    │  │  PREMIUM PROVIDERS  │       │    │
│  │  │   (Standard tier)   │  │  (Enhanced tier)    │       │    │
│  │  │                     │  │                     │       │    │
│  │  │  - Court records    │  │  - Data brokers     │       │    │
│  │  │  - Credit bureaus   │  │  - OSINT platforms  │       │    │
│  │  │  - Employment       │  │  - Location intel   │       │    │
│  │  │  - Sanctions        │  │  - Dark web         │       │    │
│  │  │  - Education        │  │  - Alt. financial   │       │    │
│  │  └─────────────────────┘  └─────────────────────┘       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              TIER-AWARE REQUEST ROUTER                   │    │
│  │                                                          │    │
│  │  Routes based on:                                        │    │
│  │  - Service tier (determines available providers)        │    │
│  │  - Check type                                            │    │
│  │  - Locale/jurisdiction                                   │    │
│  │  - Provider availability and cost                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │    Core      │     │   Premium    │     │   Premium    │    │
│  │   Provider   │     │   Provider   │     │   Provider   │    │
│  │  (Sterling)  │     │   (Acxiom)   │     │   (Pipl)     │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

**Extended Provider Interface:**
```python
class DataProvider(Protocol):
    """Interface all data providers must implement."""

    @property
    def provider_id(self) -> str: ...

    @property
    def tier_category(self) -> DataSourceCategory: ...  # core | premium

    @property
    def supported_checks(self) -> list[CheckType]: ...

    @property
    def supported_locales(self) -> list[Locale]: ...

    @property
    def cost_tier(self) -> CostTier: ...  # For billing/optimization

    async def execute_check(
        self,
        check_type: CheckType,
        subject: SubjectInfo,
        locale: Locale,
        degree: SearchDegree,  # May affect query scope
    ) -> ProviderResult: ...

    async def health_check(self) -> ProviderHealth: ...
```
<div style="break-after: page;"></div>

### 5.5 Connection Mapper (Degree-Aware)

Maps relationships with depth controlled by search degree.

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONNECTION MAPPER                            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  ENTITY EXTRACTOR                        │    │
│  │                                                          │    │
│  │  Extracts entities from findings:                        │    │
│  │  - Organizations (employers, businesses)                 │    │
│  │  - Individuals (associates, directors)                   │    │
│  │  - Addresses (shared residences)                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  DEGREE CONTROLLER                       │    │
│  │                                                          │    │
│  │  D1: Extract entities, do not investigate               │    │
│  │  D2: Investigate direct connections (queue entities)    │    │
│  │  D3: Investigate + queue second-degree connections      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  GRAPH BUILDER                           │    │
│  │                                                          │    │
│  │  Builds relationship graph:                              │    │
│  │  - Subject → Entity connections                         │    │
│  │  - Entity → Entity connections (D2+)                    │    │
│  │  - Risk propagation through connections                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.6 Vigilance Scheduler

Manages ongoing monitoring based on vigilance level.

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIGILANCE SCHEDULER                           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  SCHEDULE MANAGER                        │    │
│  │                                                          │    │
│  │  V0: No scheduling (one-time)                           │    │
│  │  V1: Annual cron (full re-screen)                       │    │
│  │  V2: Monthly cron (delta checks)                        │    │
│  │  V3: Bi-monthly cron + real-time hooks                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  DELTA DETECTOR                          │    │
│  │                                                          │    │
│  │  Compares current results to baseline:                  │    │
│  │  - New findings                                          │    │
│  │  - Changed findings                                      │    │
│  │  - Resolved findings                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  ALERT EVALUATOR                         │    │
│  │                                                          │    │
│  │  Determines if changes warrant alert:                   │    │
│  │  - Severity thresholds                                   │    │
│  │  - Change significance                                   │    │
│  │  - Role-based escalation rules                          │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.7 Risk Analyzer

AI-powered analysis of collected data.

```
┌─────────────────────────────────────────────────────────────────┐
│                       RISK ANALYZER                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  FINDING EXTRACTOR                       │    │
│  │                                                          │    │
│  │  Uses AI models to extract structured findings from      │    │
│  │  raw provider data and unstructured text                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                FINDING CATEGORIZER                       │    │
│  │                                                          │    │
│  │  Categories:                                             │    │
│  │  - Criminal: Convictions, arrests, pending charges      │    │
│  │  - Financial: Bankruptcy, liens, judgments, distress    │    │
│  │  - Regulatory: License issues, sanctions, enforcement   │    │
│  │  - Reputation: Adverse media, litigation                │    │
│  │  - Verification: Discrepancies in claimed history       │    │
│  │  - Behavioral: Concerning patterns (Enhanced only)      │    │
│  │  - Network: Risky connections (D2/D3 only)             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  RISK SCORER                             │    │
│  │                                                          │    │
│  │  Inputs:                                                 │    │
│  │  - Finding severity                                      │    │
│  │  - Finding recency                                       │    │
│  │  - Role relevance (financial crime → finance role)      │    │
│  │  - Confidence level                                      │    │
│  │  - Corroboration across sources                         │    │
│  │  - Connection risk propagation (D2/D3)                  │    │
│  │                                                          │    │
│  │  Output: Composite risk score with category breakdown   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.8 HRIS Integration Gateway

Connects to HR systems for consent and workflow.

```
┌─────────────────────────────────────────────────────────────────┐
│                    HRIS INTEGRATION GATEWAY                      │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  WEBHOOK RECEIVER                        │    │
│  │                                                          │    │
│  │  Receives events:                                        │    │
│  │  - New hire initiated (includes service config)         │    │
│  │  - Consent granted                                       │    │
│  │  - Position change (may trigger tier change)            │    │
│  │  - Termination (stops monitoring)                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  EVENT PROCESSOR                         │    │
│  │                                                          │    │
│  │  - Validates consent scope matches service config       │    │
│  │  - Maps role to default service configuration           │    │
│  │  - Initiates appropriate screening workflow             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Workday    │     │ SuccessFactors│    │  Oracle HCM  │    │
│  │   Adapter    │     │   Adapter    │     │   Adapter    │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  RESULT PUBLISHER                        │    │
│  │                                                          │    │
│  │  - Status updates                                        │    │
│  │  - Risk summary (detail level configurable)             │    │
│  │  - Monitoring alerts                                     │    │
│  │  - Adverse action workflow triggers                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 5.9 Audit Logger

Comprehensive logging for compliance.

```
┌─────────────────────────────────────────────────────────────────┐
│                       AUDIT LOGGER                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  EVENT COLLECTOR                         │    │
│  │                                                          │    │
│  │  Captures all events including:                          │    │
│  │  - Service configuration used                            │    │
│  │  - Data sources queried (with tier)                     │    │
│  │  - Premium source access (Enhanced tier)                │    │
│  │  - Degree expansion decisions                           │    │
│  │  - Vigilance check executions                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               IMMUTABLE LOG STORE                        │    │
│  │                                                          │    │
│  │  Append-only with cryptographic integrity               │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---
<div style="break-after: page;"></div>

## 7. Data Flow

### 6.1 Pre-Employment Screening Flow

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
<div style="break-after: page;"></div>

### 6.2 Ongoing Monitoring Flow (Vigilance)

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIGILANCE SCHEDULER                           │
│                                                                  │
│   V1 (Annual)      V2 (Monthly)       V3 (Bi-monthly)          │
│       │                │                    │                   │
│       │                │                    │                   │
│       ▼                ▼                    ▼                   │
│   ┌───────┐        ┌───────┐           ┌───────┐               │
│   │ Full  │        │ Delta │           │ Delta │               │
│   │Re-scrn│        │ Check │           │ Check │               │
│   └───────┘        └───────┘           └───┬───┘               │
│                                             │                   │
│                                    ┌────────┴────────┐         │
│                                    ▼                 ▼         │
│                              ┌─────────┐      ┌──────────┐     │
│                              │Real-time│      │Continuous│     │
│                              │Sanctions│      │Adverse   │     │
│                              │ Alerts  │      │Media Mon.│     │
│                              └─────────┘      └──────────┘     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Delta   │────►│  Alert  │────►│ Trigger │────►│  HRIS   │
│Detected │     │ Evaluate│     │ Review  │     │ Notify  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
```

---
<div style="break-after: page;"></div>

### 6.5 Intelligent Iterative Search Process

The system uses an intelligent search process that proceeds through information types in a deliberate sequence, using a Search-Assess-Refine (SAR) loop for each type. Findings from earlier types actively reshape queries for later types.

#### 6.5.1 Information Type Dependency Graph

Information types are organized into **phases** based on dependencies:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    INFORMATION TYPE DEPENDENCY GRAPH                     │
│                                                                          │
│  PHASE 1: FOUNDATION (Sequential, must complete)                        │
│  ════════════════════════════════════════════                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │   Identity   │───►│  Employment  │───►│  Education   │              │
│  │ Verification │    │   History    │    │ Verification │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│         │                   │                   │                        │
│         │ (names, DOB,      │ (employers,       │ (schools,              │
│         │  addresses,       │  titles, dates,   │  degrees,              │
│         │  SSN confirmed)   │  colleagues)      │  dates)                │
│         │                   │                   │                        │
│         └───────────────────┴───────────────────┘                        │
│                             │                                            │
│                             ▼                                            │
│  PHASE 2: RECORDS (Parallel within phase, uses Phase 1 data)            │
│  ═══════════════════════════════════════════════════════════            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   Criminal   │  │    Civil     │  │  Financial   │                  │
│  │   Records    │  │  Litigation  │  │   /Credit    │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │ Professional │  │  Regulatory  │  │  Sanctions   │                  │
│  │   Licenses   │  │   Actions    │  │    / PEP     │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
│                             │                                            │
│                             ▼                                            │
│  PHASE 3: INTELLIGENCE (Uses all prior phases)                          │
│  ═════════════════════════════════════════════                          │
│  ┌──────────────┐  ┌──────────────┐                                    │
│  │   Adverse    │  │   Digital    │ ◄── Enhanced Tier Only             │
│  │    Media     │  │  Footprint   │                                    │
│  └──────────────┘  └──────────────┘                                    │
│                             │                                            │
│                             ▼                                            │
│  PHASE 4: NETWORK (Expands from discovered entities)                    │
│  ═══════════════════════════════════════════════════                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │ D1: Subject  │───►│ D2: Direct   │───►│ D3: Extended │              │
│  │   Complete   │    │ Connections  │    │   Network    │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│                                                ▲                         │
│                                                │ Enhanced Tier Only      │
│                             │                                            │
│                             ▼                                            │
│  PHASE 5: RECONCILIATION & DECEPTION ANALYSIS                          │
│  ════════════════════════════════════════════════════════════           │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │  Inconsistencies are RISK SIGNALS, not just data issues: │          │
│  │  • Analyze inconsistency patterns (single vs. systematic)│          │
│  │  • Score deception likelihood based on type & pattern    │          │
│  │  • Cross-reference to attempt resolution                  │          │
│  │  • Generate RiskFinding for unresolved/suspicious items  │          │
│  └──────────────────────────────────────────────────────────┘          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 6.5.2 Search-Assess-Refine (SAR) Loop

Each information type runs through this iterative loop:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     SEARCH-ASSESS-REFINE LOOP                            │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         SEARCH                                   │    │
│  │                                                                  │    │
│  │  Generate queries using:                                        │    │
│  │  • Subject identifiers (name, DOB, SSN, addresses)             │    │
│  │  • Facts discovered in completed types (employers, schools)    │    │
│  │  • Gap-filling queries from previous iteration                 │    │
│  │  • Type-specific query templates                               │    │
│  │                                                                  │    │
│  │  Query enrichment examples:                                     │    │
│  │  • Identity → Employment: Use confirmed name variants          │    │
│  │  • Employment → Criminal: Use employer addresses for counties  │    │
│  │  • Education → Licenses: Use degree type for relevant boards   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                              │                                           │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         ASSESS                                   │    │
│  │                                                                  │    │
│  │  Analyze results:                                               │    │
│  │  • Extract structured findings (facts, dates, entities)        │    │
│  │  • Calculate type confidence score                              │    │
│  │  • Identify gaps (expected info not found)                     │    │
│  │  • Detect inconsistencies → queue for Phase 5                  │    │
│  │  • Discover new entities → queue for network phases            │    │
│  │  • Track information gain (new facts this iteration)           │    │
│  │                                                                  │    │
│  │  Outputs:                                                       │    │
│  │  • type_confidence: float (0.0 - 1.0)                          │    │
│  │  • gaps: list[str] (what we expected but didn't find)          │    │
│  │  • info_gain_rate: float (new facts / total queries)           │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                              │                                           │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         REFINE                                   │    │
│  │                                                                  │    │
│  │  Decision logic:                                                │    │
│  │                                                                  │    │
│  │  IF type_confidence >= CONFIDENCE_THRESHOLD (0.85)             │    │
│  │     → Mark type COMPLETE, proceed to next type                 │    │
│  │                                                                  │    │
│  │  ELSE IF iterations >= MAX_ITERATIONS (3)                      │    │
│  │     → Mark type COMPLETE (capped), proceed                     │    │
│  │                                                                  │    │
│  │  ELSE IF info_gain_rate < MIN_GAIN (0.1)                       │    │
│  │     → Mark type COMPLETE (diminishing returns)                 │    │
│  │                                                                  │    │
│  │  ELSE                                                           │    │
│  │     → Generate refined queries targeting gaps                  │    │
│  │     → Loop back to SEARCH                                       │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 6.5.3 Cross-Type Query Enrichment

Facts discovered in earlier types inform queries for later types:

| Source Type | Target Type | Enrichment |
|-------------|-------------|------------|
| Identity | All | Confirmed name variants, DOB, addresses |
| Identity | Criminal | Counties from confirmed addresses |
| Employment | Criminal | Counties from employer locations |
| Employment | Civil | Employer names for litigation search |
| Employment | Regulatory | Industry for relevant regulators |
| Education | Licenses | Degree type → relevant licensing boards |
| All | Adverse Media | All confirmed names, employers, schools |
| All | Network D2 | Discovered colleagues, business partners |

#### 6.5.4 Inconsistency Risk Scoring

Inconsistencies are potential deception indicators, scored by type and pattern:

| Inconsistency Type | Base Score | Risk Implication |
|-------------------|------------|------------------|
| Date minor, spelling variant | 0.1 | Common data entry issues |
| Date significant (months off) | 0.3 | May hide employment gaps |
| Title/degree mismatch | 0.3-0.5 | Credential inflation |
| Employment gap hidden | 0.6 | Deliberate concealment |
| Education inflated | 0.7 | Likely falsification |
| Employer fabricated | 0.8 | Fabrication |
| Timeline impossible | 0.7 | Logical impossibility |
| Multiple identities | 0.9 | Strong fraud signal |
| Systematic pattern (4+) | 0.95 | Coordinated deception |

**Pattern Modifiers:**
- 2-3 inconsistencies (same field): ×1.3
- 2-3 inconsistencies (different fields): ×1.5
- 4+ inconsistencies: ×2.0
- Span 3+ information types: ×1.5
- Directional bias (all inflate credentials): ×1.8

#### 6.5.5 Knowledge Base Structure

Accumulated facts for query enrichment:

```python
class KnowledgeBase(BaseModel):
    # Identity facts
    confirmed_names: list[str]       # Including variants, maiden names
    confirmed_dob: date | None
    confirmed_addresses: list[Address]

    # Employment facts
    employers: list[EmployerRecord]  # Name, dates, title, location

    # Education facts
    schools: list[EducationRecord]   # Name, degree, dates

    # Professional facts
    licenses: list[LicenseRecord]    # Type, number, jurisdiction

    # Discovered entities (for network expansion)
    discovered_people: list[PersonEntity]
    discovered_orgs: list[OrgEntity]

    # Jurisdictions for targeted searches
    known_counties: list[str]
    known_states: list[str]
```

#### 6.5.6 Configuration Parameters

```python
class IterativeSearchConfig(BaseModel):
    # Confidence thresholds
    confidence_threshold: float = 0.85
    foundation_confidence_threshold: float = 0.90

    # Iteration limits
    max_iterations_per_type: int = 3
    foundation_max_iterations: int = 4

    # Diminishing returns
    min_gain_threshold: float = 0.1

    # Network phase
    network_max_entities_per_degree: int = 20

    # Reconciliation
    max_reconciliation_queries: int = 10
    auto_resolve_low_severity: bool = True

    # Inconsistency analysis
    systematic_pattern_threshold: int = 4
    cross_type_pattern_threshold: int = 3
```

---
<div style="break-after: page;"></div>

## 8. API Design

### 7.1 Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/screenings` | POST | Initiate new screening with service config |
| `/v1/screenings/{id}` | GET | Get screening status/results |
| `/v1/screenings/{id}/report` | GET | Download screening report |
| `/v1/subjects/{id}/monitor` | POST | Start ongoing monitoring |
| `/v1/subjects/{id}/monitor` | PUT | Update vigilance level |
| `/v1/subjects/{id}/monitor` | DELETE | Stop monitoring |
| `/v1/service-configs` | GET | List available service configurations |
| `/v1/service-configs/validate` | POST | Validate a service configuration |
| `/v1/compliance/rules` | GET | List compliance rules |
| `/v1/audit/events` | GET | Query audit log |

### 7.2 Screening Request Schema

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


class ServiceConfiguration(BaseModel):
    tier: ServiceTier              # standard | enhanced
    vigilance: VigilanceLevel      # v0 | v1 | v2 | v3
    degrees: SearchDegree          # d1 | d2 | d3
    human_review: ReviewLevel      # automated | analyst | investigator | dedicated

    # Optional customizations
    additional_checks: list[CheckType] = []
    excluded_checks: list[CheckType] = []
```

---
<div style="break-after: page;"></div>

## 9. Security Architecture

### 8.1 Data Protection

| Data Type | At Rest | In Transit | Access Control |
|-----------|---------|------------|----------------|
| PII | AES-256 encryption | TLS 1.3 | Role-based + need-to-know |
| Premium source data | AES-256 + additional isolation | TLS 1.3 | Enhanced tier entitlement |
| API Keys | Vault/HSM | TLS 1.3 | Service accounts only |
| Audit Logs | Encrypted, immutable | TLS 1.3 | Append-only, admin read |
| Reports | Encrypted | TLS 1.3 | Time-limited access tokens |

<div style="break-after: page;"></div>

### 8.2 Access Control Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    RBAC + ABAC HYBRID                            │
│                                                                  │
│  Roles:                                                          │
│  - admin: Full system access, compliance rule management        │
│  - analyst: Review findings, generate reports                   │
│  - operator: Initiate screenings, view status                   │
│  - auditor: Read-only access to audit logs                      │
│  - service: Machine-to-machine API access                       │
│                                                                  │
│  Attributes:                                                     │
│  - locale: Restricts access to locale-appropriate data          │
│  - organization: Multi-tenant isolation                         │
│  - tier_access: Standard vs Enhanced data access               │
│  - clearance: Access to sensitive findings                      │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 8.3 Data Retention

| Data Type | Retention Period | Basis |
|-----------|------------------|-------|
| Screening results | 7 years | FCRA, SOX |
| Premium source data | 30 days raw, 7 years findings | Minimize exposure |
| Audit logs | 7 years | Compliance |
| Consent records | Duration of employment + 7 years | Legal |

---
<div style="break-after: page;"></div>
## 10. Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Language | Python 3.14 | Async support, AI/ML ecosystem |
| Orchestration | LangGraph | Stateful workflows, conditional routing |
| AI Models | Claude, GPT-4, Gemini | Multi-model redundancy |
| API Framework | FastAPI | Async, OpenAPI, validation |
| Database | PostgreSQL | ACID, JSON support, mature |
| Cache | Redis | Session state, rate limiting |
| Background Jobs | ARQ / Dramatiq | Async job processing (Redis-backed) |
| Scheduler | APScheduler | In-process vigilance scheduling |
| Secrets | Environment / Vault | Secure credential management |
| Observability | OpenTelemetry + Prometheus | Tracing, metrics |
| Logging | structlog | Structured audit logs |

---
<div style="break-after: page;"></div>

## 11. Modular Monolith Architecture

### 11.1 Why Modular Monolith?

The platform uses a **modular monolith** architecture rather than microservices:

| Benefit | Description |
|---------|-------------|
| **Simplified Operations** | Single deployment unit; no service mesh, discovery, or inter-service networking |
| **Easier Debugging** | Full stack traces; no distributed tracing required for most issues |
| **Lower Latency** | In-process function calls vs. network hops between services |
| **Transactional Integrity** | Database transactions span module boundaries naturally |
| **Team Efficiency** | Small team can iterate quickly without coordination overhead |
| **Future Flexibility** | Well-defined module boundaries allow extraction to services later if needed |

### 11.2 Module Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ELILE MODULAR MONOLITH                           │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         API LAYER (FastAPI)                         │ │
│  │   /v1/screenings  /v1/subjects  /v1/reports  /v1/admin  /v1/webhooks│
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      APPLICATION SERVICES                           │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │ │
│  │  │  Screening   │ │  Monitoring  │ │   Report     │ │   Admin    │ │ │
│  │  │   Service    │ │   Service    │ │   Service    │ │  Service   │ │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        DOMAIN MODULES                               │ │
│  │                                                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ SCREENING MODULE                                              │  │ │
│  │  │ • ScreeningEngine (LangGraph workflow)                       │  │ │
│  │  │ • QueryGenerator                                              │  │ │
│  │  │ • ResultAnalyzer                                              │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ COMPLIANCE MODULE                                             │  │ │
│  │  │ • RuleEngine                                                  │  │ │
│  │  │ • LocaleResolver                                              │  │ │
│  │  │ • ConsentValidator                                            │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ RISK MODULE                                                   │  │ │
│  │  │ • RiskAnalyzer                                                │  │ │
│  │  │ • EvolutionDetector                                           │  │ │
│  │  │ • ConnectionMapper                                            │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ ENTITY MODULE                                                 │  │ │
│  │  │ • EntityRegistry                                              │  │ │
│  │  │ • ProfileVersioning                                           │  │ │
│  │  │ • EntityResolution                                            │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ REPORT MODULE                                                 │  │ │
│  │  │ • ReportGenerator                                             │  │ │
│  │  │ • PersonaFilter                                               │  │ │
│  │  │ • PDFRenderer                                                 │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     INTEGRATION ADAPTERS                            │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │ │
│  │  │   Provider   │ │    HRIS      │ │  AI Model    │ │Notification│ │ │
│  │  │   Adapters   │ │   Adapters   │ │   Adapters   │ │  Adapters  │ │ │
│  │  │              │ │              │ │              │ │            │ │ │
│  │  │ • Sterling   │ │ • Workday    │ │ • Claude     │ │ • Email    │ │ │
│  │  │ • Checkr     │ │ • SAP SF     │ │ • GPT-4      │ │ • Webhook  │ │ │
│  │  │ • PACER      │ │ • Oracle     │ │ • Gemini     │ │ • SMS      │ │ │
│  │  │ • World-Check│ │ • ADP        │ │              │ │            │ │ │
│  │  │ • Acxiom     │ │              │ │              │ │            │ │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     INFRASTRUCTURE LAYER                            │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │ │
│  │  │  Repository  │ │    Cache     │ │  Job Queue   │ │   Audit    │ │ │
│  │  │   (SQLAlchemy)│ │   (Redis)    │ │   (ARQ)      │ │   Logger   │ │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 11.3 Module Boundaries & Communication

Modules communicate through well-defined interfaces, not direct imports of internal classes:

```python
# Module public interface (elile/screening/__init__.py)
from .service import ScreeningService
from .models import ScreeningRequest, ScreeningResult, ScreeningStatus

__all__ = ["ScreeningService", "ScreeningRequest", "ScreeningResult", "ScreeningStatus"]

# Internal implementation details are NOT exported
# Other modules import only from the public interface
```

**Communication Patterns:**

| Pattern | Use Case | Example |
|---------|----------|---------|
| **Direct call** | Synchronous, in-request | `compliance.validate(request)` |
| **Domain events** | Async notification, decoupled | `ScreeningCompleted` event triggers report generation |
| **Job queue** | Background processing | Provider data fetching, PDF generation |

```
┌─────────────────────────────────────────────────────────────────┐
│                  MODULE COMMUNICATION PATTERNS                   │
│                                                                  │
│  SYNCHRONOUS (in-process function calls)                        │
│  ─────────────────────────────────────────                      │
│                                                                  │
│  API Request                                                     │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────┐  validate()  ┌─────────────┐                  │
│  │  Screening  │─────────────►│ Compliance  │                  │
│  │  Service    │◄─────────────│   Module    │                  │
│  └─────────────┘   result     └─────────────┘                  │
│       │                                                          │
│       │ analyze()                                                │
│       ▼                                                          │
│  ┌─────────────┐                                                │
│  │    Risk     │                                                │
│  │   Module    │                                                │
│  └─────────────┘                                                │
│                                                                  │
│  ASYNCHRONOUS (domain events via in-memory bus)                 │
│  ───────────────────────────────────────────────                │
│                                                                  │
│  ┌─────────────┐  ScreeningCompleted  ┌─────────────┐          │
│  │  Screening  │─────────────────────►│   Report    │          │
│  │  Service    │      (event)         │   Module    │          │
│  └─────────────┘                      └─────────────┘          │
│                          │                                       │
│                          ▼                                       │
│                   ┌─────────────┐                               │
│                   │Notification │                               │
│                   │   Module    │                               │
│                   └─────────────┘                               │
│                                                                  │
│  BACKGROUND (job queue for heavy/external work)                 │
│  ──────────────────────────────────────────────                 │
│                                                                  │
│  ┌─────────────┐   enqueue()   ┌─────────────┐  fetch  ┌─────┐ │
│  │  Screening  │──────────────►│  Job Queue  │────────►│Worker│ │
│  │  Service    │               │   (Redis)   │         │     │ │
│  └─────────────┘               └─────────────┘         └─────┘ │
│                                                            │     │
│                                                            ▼     │
│                                                    ┌───────────┐ │
│                                                    │ Provider  │ │
│                                                    │ Adapter   │ │
│                                                    └───────────┘ │
└─────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 11.4 Process Model

The application runs as two process types that can be scaled independently:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          PROCESS MODEL                                   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        WEB PROCESS                                  │ │
│  │                                                                      │ │
│  │  uvicorn elile.main:app --workers N                                │ │
│  │                                                                      │ │
│  │  Responsibilities:                                                  │ │
│  │  • HTTP API requests (FastAPI)                                      │ │
│  │  • WebSocket connections (alerts, real-time updates)               │ │
│  │  • Webhook receivers (HRIS events)                                 │ │
│  │  • Health checks                                                    │ │
│  │                                                                      │ │
│  │  Scaling: Horizontal via process count (--workers) or load balancer│ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                       WORKER PROCESS                                │ │
│  │                                                                      │ │
│  │  arq elile.worker.WorkerSettings --concurrency N                   │ │
│  │                                                                      │ │
│  │  Responsibilities:                                                  │ │
│  │  • Provider data fetching (HTTP calls to external APIs)            │ │
│  │  • LangGraph workflow execution (screening pipeline)               │ │
│  │  • Report generation (PDF rendering)                               │ │
│  │  • Vigilance scheduled checks                                       │ │
│  │  • Entity resolution (background deduplication)                    │ │
│  │                                                                      │ │
│  │  Scaling: Horizontal via worker count or concurrency setting       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     SCHEDULER PROCESS (optional)                    │ │
│  │                                                                      │ │
│  │  python -m elile.scheduler                                         │ │
│  │                                                                      │ │
│  │  Responsibilities:                                                  │ │
│  │  • Vigilance cron jobs (V1/V2/V3 check triggers)                   │ │
│  │  • Data freshness expiration checks                                │ │
│  │  • Cleanup jobs (cache pruning, audit log rotation)                │ │
│  │                                                                      │ │
│  │  Note: Can be embedded in worker process for simpler deployments   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 11.5 Deployment Options

The modular monolith supports multiple deployment targets:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       DEPLOYMENT OPTIONS                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  OPTION A: SINGLE VM / BARE METAL (Simplest)                           │
│  ───────────────────────────────────────────                            │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         SINGLE SERVER                            │    │
│  │                                                                   │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │    │
│  │  │   Web   │  │ Worker  │  │ Worker  │  │Scheduler│            │    │
│  │  │ Process │  │   #1    │  │   #2    │  │         │            │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │    │
│  │       │            │            │            │                   │    │
│  │       └────────────┴────────────┴────────────┘                   │    │
│  │                         │                                         │    │
│  │                    ┌────┴────┐                                   │    │
│  │                    │  Redis  │                                   │    │
│  │                    └─────────┘                                   │    │
│  │                                                                   │    │
│  │  Managed: PostgreSQL (RDS/Cloud SQL)                            │    │
│  │  Process Manager: systemd / supervisord                         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  OPTION B: CONTAINER (Docker Compose / ECS / Cloud Run)                │
│  ──────────────────────────────────────────────────────                 │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     CONTAINER ORCHESTRATION                      │    │
│  │                                                                   │    │
│  │  ┌───────────────────┐  ┌───────────────────┐                   │    │
│  │  │   Web Container   │  │  Worker Container │                   │    │
│  │  │   (2-4 replicas)  │  │   (2-4 replicas)  │                   │    │
│  │  │                   │  │                   │                   │    │
│  │  │  CMD: uvicorn     │  │  CMD: arq         │                   │    │
│  │  │       --workers 2 │  │       --concurrency 10                │    │
│  │  └───────────────────┘  └───────────────────┘                   │    │
│  │           │                      │                               │    │
│  │           └──────────┬───────────┘                               │    │
│  │                      ▼                                           │    │
│  │  ┌──────────────────────────────────────────────────────────┐   │    │
│  │  │              MANAGED SERVICES                             │   │    │
│  │  │  PostgreSQL (RDS)  │  Redis (ElastiCache)  │  S3 (Reports)│   │    │
│  │  └──────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  OPTION C: PLATFORM-AS-A-SERVICE (Railway, Render, Fly.io)             │
│  ─────────────────────────────────────────────────────────              │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         PAAS PLATFORM                            │    │
│  │                                                                   │    │
│  │  Service: elile-web          Service: elile-worker              │    │
│  │  ┌───────────────────┐       ┌───────────────────┐              │    │
│  │  │ Procfile: web     │       │ Procfile: worker  │              │    │
│  │  │ Instances: 2      │       │ Instances: 2      │              │    │
│  │  └───────────────────┘       └───────────────────┘              │    │
│  │                                                                   │    │
│  │  Addons: PostgreSQL, Redis, S3-compatible storage               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 11.6 Scaling Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SCALING STRATEGY                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  VERTICAL SCALING (Scale Up)                                            │
│  ──────────────────────────                                             │
│  • Increase CPU/RAM on web and worker processes                        │
│  • Increase database connection pool size                              │
│  • Increase Redis memory                                                │
│                                                                          │
│  Suitable for: Initial growth, up to ~1000 concurrent screenings       │
│                                                                          │
│  HORIZONTAL SCALING (Scale Out)                                         │
│  ─────────────────────────────                                          │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     LOAD BALANCER                                │    │
│  │                   (nginx / ALB / Cloud LB)                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│         │              │              │              │                   │
│         ▼              ▼              ▼              ▼                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐            │
│  │  Web #1   │  │  Web #2   │  │  Web #3   │  │  Web #4   │            │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘            │
│                                                                          │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐            │
│  │ Worker #1 │  │ Worker #2 │  │ Worker #3 │  │ Worker #4 │            │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘            │
│         │              │              │              │                   │
│         └──────────────┴──────────────┴──────────────┘                   │
│                              │                                           │
│                    ┌─────────┴─────────┐                                │
│                    ▼                   ▼                                 │
│             ┌───────────┐       ┌───────────┐                           │
│             │  Redis    │       │ PostgreSQL│                           │
│             │ (Cluster) │       │ (Primary/ │                           │
│             │           │       │  Replica) │                           │
│             └───────────┘       └───────────┘                           │
│                                                                          │
│  Suitable for: High volume, ~10,000+ concurrent screenings             │
│                                                                          │
│  FUTURE: MODULAR EXTRACTION                                             │
│  ─────────────────────────                                              │
│  If specific modules become bottlenecks, they can be extracted:        │
│  • Provider Gateway → Separate service (high external API load)        │
│  • Report Generator → Separate service (CPU-intensive PDF rendering)   │
│  • Module boundaries already defined; extraction is straightforward    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 11.7 Configuration Management

```python
# elile/config/settings.py

class Settings(BaseSettings):
    """Application configuration via environment variables."""

    # Database
    database_url: PostgresDsn
    database_pool_size: int = 20
    database_pool_overflow: int = 10

    # Redis
    redis_url: RedisDsn
    redis_pool_size: int = 10

    # API Keys (secrets)
    anthropic_api_key: SecretStr
    openai_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    # Provider API Keys
    sterling_api_key: SecretStr | None = None
    world_check_api_key: SecretStr | None = None
    # ... other providers

    # Feature Flags
    enable_enhanced_tier: bool = True
    enable_evolution_analytics: bool = True
    enable_human_review_queue: bool = True

    # Process Configuration
    web_workers: int = 4
    worker_concurrency: int = 10
    scheduler_enabled: bool = True

    # Observability
    otel_endpoint: str | None = None
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
```

**Environment-based deployment:**

```bash
# .env.production
DATABASE_URL=postgresql://user:pass@db.example.com:5432/elile
REDIS_URL=redis://redis.example.com:6379/0
ANTHROPIC_API_KEY=sk-ant-...
LOG_LEVEL=INFO
LOG_FORMAT=json
WEB_WORKERS=4
WORKER_CONCURRENCY=20
```

---
<div style="break-after: page;"></div>

## 12. Open Questions / Decisions Needed

1. **Provider Strategy**: Build direct integrations vs. use aggregator (Sterling/HireRight)?
2. **Multi-tenancy**: Single instance multi-tenant vs. tenant-per-deployment?
3. **AI Model Selection**: Which model for which task (extraction vs. scoring)?
4. **Report Format**: PDF generation approach, template system?
5. **Adverse Action Workflow**: Full FCRA workflow in-system vs. HRIS-managed?
6. **Premium Data Consent**: Separate consent flow for Enhanced tier data sources?
7. **Billing Integration**: Usage-based billing hooks for tier/vigilance/degree?

---
<div style="break-after: page;"></div>

## 13. Implementation Phases

This section will be expanded after architecture review.

| Phase | Focus | Key Deliverables |
|-------|-------|------------------|
| 1 | Foundation | Service model, core screening, compliance engine |
| 2 | Standard Tier | Core data providers, D1/D2 connections |
| 3 | Enhanced Tier | Premium providers, D3 network analysis |
| 4 | Vigilance | Scheduler, monitoring, delta detection |
| 5 | HRIS Integration | Workday connector, consent workflow |
| 6 | Production | Security hardening, scalability, observability |

---
<div style="break-after: page;"></div>

## 14. Per-Persona Report Types

Different stakeholders require different views of screening results. The system generates persona-specific reports from the same underlying data.

### 14.1 Report Persona Matrix

| Persona | Report Type | Content Focus | Data Depth | Format |
|---------|-------------|---------------|------------|--------|
| HR Manager | Summary Report | Risk level, recommendation, key flags | High-level | PDF, Dashboard |
| Compliance Officer | Audit Report | Data sources, consent, compliance checks | Full audit trail | PDF, JSON |
| Security Team | Investigation Report | Detailed findings, connections, threats | Complete | PDF, Structured |
| Investigator | Case File | Raw findings, cross-references, evidence | Complete + raw | PDF, Export |
| Subject | Disclosure Report | What was checked, summary results | Redacted | PDF, Portal |
| Executive | Portfolio Report | Aggregate risk, trends, statistics | Aggregated | Dashboard, PDF |

### 14.2 HR Manager Summary Report

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
<div style="break-after: page;"></div>

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

### 14.3 Compliance Officer Audit Report

**Purpose:** Document compliance with regulations and audit requirements.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      COMPLIANCE AUDIT REPORT                             │
│                                                                          │
│  Screening ID: SCR-2025-00847          Locale: US-CA (California)       │
│  Subject: ████████████████             Generated: 2025-01-27 14:32 UTC  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  CONSENT & AUTHORIZATION                                         │    │
│  │                                                                   │    │
│  │  Consent Reference: CON-2025-00847-A                            │    │
│  │  Consent Date: 2025-01-25 09:14:22 UTC                          │    │
│  │  Consent Scope: Standard Tier, V0 Pre-screen, D2 Connections    │    │
│  │  FCRA Disclosure: ✓ Provided 2025-01-25 09:12:18 UTC           │    │
│  │  CA ICRAA Disclosure: ✓ Provided 2025-01-25 09:12:18 UTC       │    │
│  │  Consent Verification: ✓ E-signature validated                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  COMPLIANCE RULES APPLIED                                        │    │
│  │                                                                   │    │
│  │  Rule ID          Jurisdiction    Check Type     Status          │    │
│  │  ─────────────────────────────────────────────────────────       │    │
│  │  FCRA-001         US Federal      Criminal       ✓ Applied       │    │
│  │  CA-ICRAA-003     California      Criminal       ✓ Applied       │    │
│  │  CA-AB1008-001    California      Criminal       ✓ Applied       │    │
│  │  FCRA-612         US Federal      Credit         ✓ Applied       │    │
│  │  EEOC-GUIDE-001   US Federal      All            ✓ Applied       │    │
│  │                                                                   │    │
│  │  Rules Blocking Checks: None                                     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  DATA SOURCES ACCESSED                                           │    │
│  │                                                                   │    │
│  │  Provider            Check Type        Access Time     Cost      │    │
│  │  ─────────────────────────────────────────────────────────       │    │
│  │  Equifax             Credit            09:45:12        $4.50     │    │
│  │  Sterling            Criminal (Ntl)    09:45:15        $12.00    │    │
│  │  LA County Courts    Criminal (Cnty)   09:46:01        $3.00     │    │
│  │  Work Number         Employment        09:47:22        $8.00     │    │
│  │  NSC                 Education         09:48:01        $5.00     │    │
│  │  World-Check         Sanctions/PEP     09:45:10        $2.00     │    │
│  │  PACER               Civil Litigation  09:49:15        $1.50     │    │
│  │  ─────────────────────────────────────────────────────────       │    │
│  │  Total Cost: $36.00                                              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  AUDIT TRAIL (Key Events)                                        │    │
│  │                                                                   │    │
│  │  Timestamp           Event                         Actor         │    │
│  │  ─────────────────────────────────────────────────────────       │    │
│  │  2025-01-25 09:12    Consent documents provided    System        │    │
│  │  2025-01-25 09:14    Consent granted               Subject       │    │
│  │  2025-01-25 09:15    Screening initiated           HR Portal     │    │
│  │  2025-01-25 09:45    Data collection started       System        │    │
│  │  2025-01-25 09:52    Data collection complete      System        │    │
│  │  2025-01-25 10:15    AI analysis complete          System        │    │
│  │  2025-01-26 14:00    Human review started          J. Analyst    │    │
│  │  2025-01-27 11:30    Human review complete         J. Analyst    │    │
│  │  2025-01-27 11:30    Report generated              System        │    │
│  │                                                                   │    │
│  │  [Download Full Audit Log (847 events)]                          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  DATA HANDLING COMPLIANCE                                        │    │
│  │                                                                   │    │
│  │  ✓ PII encrypted at rest (AES-256)                              │    │
│  │  ✓ PII encrypted in transit (TLS 1.3)                           │    │
│  │  ✓ Data minimization applied (role-appropriate)                 │    │
│  │  ✓ Retention policy: 7 years (FCRA)                             │    │
│  │  ✓ Access restricted to authorized personnel                    │    │
│  │  ✓ Immutable audit log maintained                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  [Export JSON]  [Download PDF]  [View Immutable Log Hash]               │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 14.4 Security Team Investigation Report

**Purpose:** Provide detailed findings for security assessment decisions.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SECURITY INVESTIGATION REPORT                         │
│                                                                          │
│  Subject: ████████████████             Case: INV-2025-00847             │
│  Service: Enhanced | V2 | D3           Classification: CONFIDENTIAL     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  THREAT ASSESSMENT                                               │    │
│  │                                                                   │    │
│  │  Insider Threat Score: ▓▓▓▓▓▓▓░░░  ELEVATED (68/100)            │    │
│  │                                                                   │    │
│  │  Contributing Factors:                                           │    │
│  │  • Financial stress indicators (recent bankruptcy filing)        │    │
│  │  • Undisclosed foreign business connection                       │    │
│  │  • Network includes 2 entities with sanctions adjacency         │    │
│  │  • Rapid network expansion in past 12 months (+340%)            │    │
│  │                                                                   │    │
│  │  Mitigating Factors:                                             │    │
│  │  • Long tenure at previous cleared positions                     │    │
│  │  • No criminal history                                           │    │
│  │  • Positive counterintelligence indicators                      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  CONNECTION NETWORK (D3 Analysis)                                │    │
│  │                                                                   │    │
│  │               [Subject]                                          │    │
│  │                   │                                              │    │
│  │     ┌─────────────┼─────────────┐                               │    │
│  │     │             │             │                               │    │
│  │   [Emp A]      [Emp B]      [Bus C]                             │    │
│  │     │          ⚠ FLAGGED       │                                │    │
│  │   [Reg]          │          ┌──┴──┐                             │    │
│  │                  │       [Dir D] [Dir E]                        │    │
│  │            [PEP Adjacency]   ⚠       ⚠                          │    │
│  │                           SANCTIONS  SANCTIONS                   │    │
│  │                           ADJACENT   ADJACENT                    │    │
│  │                                                                   │    │
│  │  Legend: ⚠ = Risk Flag    [Entity] = Normal                    │    │
│  │                                                                   │    │
│  │  Total Entities: 47 | D1: 1 | D2: 12 | D3: 34                   │    │
│  │  Flagged Entities: 5 | High Risk: 2 | Moderate: 3               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  DETAILED FINDINGS                                               │    │
│  │                                                                   │    │
│  │  [FINANCIAL-001] Bankruptcy Filing - HIGH                       │    │
│  │  ─────────────────────────────────────────────────────────      │    │
│  │  Type: Chapter 7 Personal Bankruptcy                             │    │
│  │  Filed: 2024-09-15 | Discharged: 2025-01-10                     │    │
│  │  Amount: $127,450 in discharged debt                            │    │
│  │  Source: PACER (Central District of California)                 │    │
│  │  Confidence: 0.99                                                │    │
│  │  Security Relevance: Financial vulnerability may increase       │    │
│  │                      susceptibility to coercion/bribery         │    │
│  │                                                                   │    │
│  │  [NETWORK-001] Undisclosed Business Connection - HIGH           │    │
│  │  ─────────────────────────────────────────────────────────      │    │
│  │  Entity: Meridian Holdings LLC (Delaware)                       │    │
│  │  Role: 40% Beneficial Owner (via shell structure)               │    │
│  │  Discovered: Corporate registry + beneficial ownership trace    │    │
│  │  Concern: Not disclosed on application; shell company structure │    │
│  │  Source: OpenCorporates + Delaware Registry                     │    │
│  │  Confidence: 0.95                                                │    │
│  │                                                                   │    │
│  │  [NETWORK-002] Sanctions-Adjacent Connection - MEDIUM           │    │
│  │  ─────────────────────────────────────────────────────────      │    │
│  │  Subject → Business C → Director D → Entity on OFAC SDN        │    │
│  │  Path Length: 3 degrees                                          │    │
│  │  Relationship: Business C director also directs sanctioned co.  │    │
│  │  Assessment: Indirect connection; no direct sanctions exposure  │    │
│  │  Source: World-Check + OFAC SDN + Corporate Registry            │    │
│  │  Confidence: 0.88                                                │    │
│  │                                                                   │    │
│  │  [+ 12 more findings...]                                        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  EVOLUTION SIGNALS (Compared to baseline 12 months ago)         │    │
│  │                                                                   │    │
│  │  Signal                    Severity    Change                    │    │
│  │  ─────────────────────────────────────────────────────────       │    │
│  │  network_expansion         HIGH        +340% (12→47 entities)   │    │
│  │  shell_company_buildup     HIGH        +3 new shell companies   │    │
│  │  financial_deterioration   HIGH        Bankruptcy filed          │    │
│  │  undisclosed_interests     MEDIUM      1 new undisclosed entity │    │
│  │                                                                   │    │
│  │  Pattern Match: "Financial Distress + Network Opacity"          │    │
│  │  Historical correlation: 34% of similar patterns preceded       │    │
│  │                          insider threat incidents                │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  [Export to Case Management]  [Schedule Interview]  [Escalate]          │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 14.5 Subject Disclosure Report (FCRA Compliant)

**Purpose:** Inform subject of screening results; required for adverse action.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   YOUR BACKGROUND CHECK RESULTS                          │
│                                                                          │
│  Hello ████████████████,                                                │
│                                                                          │
│  Your background check for [Company Name] has been completed.           │
│  Below is a summary of what was reviewed.                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  WHAT WAS CHECKED                                                │    │
│  │                                                                   │    │
│  │  ✓ Identity Verification                                         │    │
│  │  ✓ Criminal Records (National and County)                        │    │
│  │  ✓ Employment History (Past 5 Employers)                         │    │
│  │  ✓ Education Verification                                        │    │
│  │  ✓ Credit History                                                │    │
│  │  ✓ Civil Court Records                                           │    │
│  │  ✓ Professional License Verification                            │    │
│  │  ✓ Sanctions and Watchlist Screening                            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  SUMMARY OF RESULTS                                              │    │
│  │                                                                   │    │
│  │  Items Verified Successfully:           7                        │    │
│  │  Items Requiring Attention:             1                        │    │
│  │  Items That Could Not Be Verified:      0                        │    │
│  │                                                                   │    │
│  │  ─────────────────────────────────────────────────────────       │    │
│  │                                                                   │    │
│  │  ⚠ ITEM REQUIRING ATTENTION:                                    │    │
│  │                                                                   │    │
│  │  Employment History: We were unable to verify employment at      │    │
│  │  [Previous Employer] for the dates June 2021 - February 2022.   │    │
│  │  The employer did not respond to our verification request.       │    │
│  │                                                                   │    │
│  │  ─────────────────────────────────────────────────────────       │    │
│  │                                                                   │    │
│  │  Note: A resolved civil judgment from 2019 was found but is     │    │
│  │  shown as paid in full.                                          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  YOUR RIGHTS                                                     │    │
│  │                                                                   │    │
│  │  Under the Fair Credit Reporting Act (FCRA), you have the       │    │
│  │  right to:                                                       │    │
│  │                                                                   │    │
│  │  • Request a free copy of your background check report          │    │
│  │  • Dispute any information you believe is inaccurate            │    │
│  │  • Contact the reporting agency directly                         │    │
│  │  • Add a statement to your file                                  │    │
│  │                                                                   │    │
│  │  To dispute information or request your full report:            │    │
│  │  [Start Dispute Process]                                         │    │
│  │                                                                   │    │
│  │  Consumer Reporting Agency:                                      │    │
│  │  Elile Background Services                                       │    │
│  │  disputes@elile.com | 1-800-XXX-XXXX                            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  DATA SOURCES USED                                               │    │
│  │                                                                   │    │
│  │  • National criminal database                                    │    │
│  │  • Los Angeles County Court Records                             │    │
│  │  • Equifax Consumer Credit Report                               │    │
│  │  • The Work Number (Employment verification)                    │    │
│  │  • National Student Clearinghouse                               │    │
│  │  • OFAC Sanctions List                                          │    │
│  │  • California State Bar                                         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  [Download PDF Report]  [File a Dispute]  [Contact Support]             │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 14.6 Executive Portfolio Report

**Purpose:** Aggregate view of organizational screening metrics and risk posture.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   EXECUTIVE RISK DASHBOARD                               │
│                                                                          │
│  Organization: Acme Corporation          Period: Q4 2025                │
│  Generated: 2025-01-27                   Prepared for: C-Suite          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  PORTFOLIO RISK SNAPSHOT                                         │    │
│  │                                                                   │    │
│  │  Active Employees Monitored: 12,847                              │    │
│  │  Average Risk Score: 18.4 (LOW)                                  │    │
│  │                                                                   │    │
│  │  Risk Distribution:                                              │    │
│  │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░  LOW (76%)                  │    │
│  │  ▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░  MODERATE (18%)              │    │
│  │  ▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  HIGH (5%)                   │    │
│  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  CRITICAL (1%)               │    │
│  │                                                                   │    │
│  │  Quarter-over-Quarter Change: ↓ 2.1 points (IMPROVING)          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌───────────────────────────────────┬─────────────────────────────┐    │
│  │  SCREENING ACTIVITY (Q4)         │  TOP RISK CATEGORIES         │    │
│  │                                   │                              │    │
│  │  New Hires Screened:    847      │  1. Financial (23%)          │    │
│  │  Monitoring Checks:   4,231      │  2. Employment Gaps (18%)    │    │
│  │  Alerts Generated:      127      │  3. Network Risk (12%)       │    │
│  │  Escalations:            14      │  4. Regulatory (8%)          │    │
│  │  Adverse Actions:         3      │  5. Criminal (4%)            │    │
│  │                                   │                              │    │
│  │  Clear Rate: 94.2%               │  [View Category Details]     │    │
│  └───────────────────────────────────┴─────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  RISK BY BUSINESS UNIT                                           │    │
│  │                                                                   │    │
│  │  Business Unit          Headcount    Avg Score    Trend         │    │
│  │  ─────────────────────────────────────────────────────────       │    │
│  │  Treasury Operations        124        34.2       ↑ +2.1        │    │
│  │  IT Security                 89        28.7       ↓ -1.4        │    │
│  │  Executive Office            23        26.1       → stable      │    │
│  │  Client Advisory            412        22.4       ↓ -3.2        │    │
│  │  Operations               8,847        15.2       ↓ -0.8        │    │
│  │  ...                                                             │    │
│  │                                                                   │    │
│  │  ⚠ Treasury Operations showing elevated risk trend              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  EVOLUTION ALERTS                                                │    │
│  │                                                                   │    │
│  │  Employees showing significant risk evolution this quarter:     │    │
│  │                                                                   │    │
│  │  • 3 employees: Financial distress patterns emerging            │    │
│  │  • 2 employees: Rapid network expansion (Enhanced tier)         │    │
│  │  • 1 employee: New sanctions-adjacent connection discovered     │    │
│  │                                                                   │    │
│  │  All flagged for enhanced monitoring or investigation.          │    │
│  │                                                                   │    │
│  │  [View Evolution Details]                                        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  SPEND & EFFICIENCY                                              │    │
│  │                                                                   │    │
│  │  Q4 Screening Spend: $127,450                                   │    │
│  │  Cost per Screen: $28.42 (↓ 8% from Q3)                         │    │
│  │  Cache Hit Rate: 34% (cost savings: ~$18,200)                   │    │
│  │                                                                   │    │
│  │  Tier Breakdown:                                                 │    │
│  │  Standard: 89% of screenings | $21.50 avg                       │    │
│  │  Enhanced: 11% of screenings | $84.20 avg                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  [Download Full Report]  [Schedule Briefing]  [Drill Down by Unit]      │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 14.7 Report Generation Architecture

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

**Report Access Control:**

| Report Type | Default Access | Override Available |
|-------------|----------------|-------------------|
| HR Summary | HR Manager role | Yes (by admin) |
| Audit Report | Compliance role | No |
| Security Report | Security role + clearance | No |
| Investigator Case | Investigator role + case assignment | No |
| Subject Disclosure | Subject (authenticated) | No |
| Executive Portfolio | Executive role | Yes (delegate) |

---
<div style="break-after: page;"></div>

## 15. User Interface Requirements

The platform requires multiple user interfaces to serve different personas and workflows.

### 15.1 Interface Overview

| Interface | Primary Users | Purpose |
|-----------|---------------|---------|
| **Screening Portal** | HR, Hiring Managers | Initiate screenings, view status, access reports |
| **Review Dashboard** | Analysts, Investigators | Review findings, make decisions, document rationale |
| **Monitoring Console** | Security, Compliance | View ongoing monitoring, respond to alerts |
| **Admin Console** | Administrators | Configure rules, manage providers, system settings |
| **Subject Portal** | Candidates, Employees | View status, dispute findings, provide information |
| **Executive Dashboard** | Leadership | Portfolio view, trends, metrics |

### 15.2 Screening Portal (HR Interface)

**Purpose:** Enable HR teams to initiate and track background screenings.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ☰ ELILE                    Screening Portal              Jane HR ▼    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  📊 DASHBOARD                                          [+ New]  │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │    │
│  │  │    12    │  │     5    │  │     3    │  │     4    │        │    │
│  │  │ Pending  │  │In Review │  │ Complete │  │  Action  │        │    │
│  │  │ Consent  │  │          │  │ Today    │  │ Required │        │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  🔍 Search: [________________________] [Filter ▼] [Date Range ▼]│    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  RECENT SCREENINGS                                               │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │ SCR-2025-00851 │ Sarah Johnson │ Sr. Analyst │ Finance  │    │    │
│  │  │ [████████████████████░░░░░░░░░░] 67% Complete            │    │    │
│  │  │ Status: Data collection in progress                      │    │    │
│  │  │ Est. completion: Jan 28, 2025                            │    │    │
│  │  │ Config: Standard | V1 | D2                               │    │    │
│  │  │ [View Details]                                           │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  │                                                                  │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │ SCR-2025-00847 │ John Smith │ VP Operations │ Energy    │    │    │
│  │  │ [████████████████████████████████] ✓ Complete           │    │    │
│  │  │ Risk: ●●●○○ MODERATE   │ Recommendation: PROCEED W/CAUT │    │    │
│  │  │ ⚠ 2 items requiring attention                          │    │    │
│  │  │ [View Report] [Request Interview] [Proceed to Offer]   │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  │                                                                  │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │ SCR-2025-00842 │ Maria Garcia │ Contractor │ IT         │    │    │
│  │  │ [████████████████████████████████] ✓ Complete           │    │    │
│  │  │ Risk: ●○○○○ LOW        │ Recommendation: PROCEED        │    │    │
│  │  │ ✓ All checks clear                                      │    │    │
│  │  │ [View Report] [Proceed to Offer]                        │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  │                                                                  │    │
│  │  [Show More...]                                                 │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

**New Screening Form:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ☰ ELILE                  New Screening Request           Jane HR ▼    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  CANDIDATE INFORMATION                                    1/4   │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  ┌─────────────────────┐  ┌─────────────────────┐              │    │
│  │  │ First Name *        │  │ Last Name *         │              │    │
│  │  │ [Sarah            ] │  │ [Johnson          ] │              │    │
│  │  └─────────────────────┘  └─────────────────────┘              │    │
│  │                                                                  │    │
│  │  ┌─────────────────────┐  ┌─────────────────────┐              │    │
│  │  │ Email *             │  │ Phone               │              │    │
│  │  │ [sarah@email.com  ] │  │ [555-123-4567     ] │              │    │
│  │  └─────────────────────┘  └─────────────────────┘              │    │
│  │                                                                  │    │
│  │  ┌─────────────────────────────────────────────┐               │    │
│  │  │ Date of Birth *                             │               │    │
│  │  │ [MM/DD/YYYY        ]  📅                    │               │    │
│  │  └─────────────────────────────────────────────┘               │    │
│  │                                                                  │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │ SSN (Last 4 required; full SSN speeds processing)       │    │    │
│  │  │ [XXX-XX-1234      ]                                     │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  POSITION DETAILS                                         2/4   │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  ┌─────────────────────┐  ┌─────────────────────┐              │    │
│  │  │ Position Title *    │  │ Department *        │              │    │
│  │  │ [Senior Analyst   ] │  │ [Finance ▼        ] │              │    │
│  │  └─────────────────────┘  └─────────────────────┘              │    │
│  │                                                                  │    │
│  │  ┌─────────────────────┐  ┌─────────────────────┐              │    │
│  │  │ Role Category *     │  │ Work Location *     │              │    │
│  │  │ [Finance ▼        ] │  │ [US-California ▼  ] │              │    │
│  │  └─────────────────────┘  └─────────────────────┘              │    │
│  │                                                                  │    │
│  │  ⓘ Role category determines default service configuration      │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  SERVICE CONFIGURATION                                    3/4   │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  Use preset: [Finance - Standard ▼]   or customize below       │    │
│  │                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │ SERVICE TIER (What data sources)                          │  │    │
│  │  │                                                            │  │    │
│  │  │  ◉ Standard                    ○ Enhanced                  │  │    │
│  │  │    Core data sources             + Premium sources         │  │    │
│  │  │    Identity, criminal,           OSINT, behavioral,        │  │    │
│  │  │    employment, education,        data brokers, dark web    │  │    │
│  │  │    credit, sanctions                                       │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │ MONITORING (How often)                                    │  │    │
│  │  │                                                            │  │    │
│  │  │  ◉ V0 Pre-screen Only          ○ V1 Annual                │  │    │
│  │  │  ○ V2 Monthly                  ○ V3 Bi-monthly            │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │ SEARCH DEPTH (How wide)                                   │  │    │
│  │  │                                                            │  │    │
│  │  │  ○ D1 Subject Only             ◉ D2 Direct Connections    │  │    │
│  │  │  ○ D3 Extended Network (requires Enhanced)                │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │ HUMAN REVIEW                                              │  │    │
│  │  │                                                            │  │    │
│  │  │  ○ Automated Only              ◉ Analyst Review           │  │    │
│  │  │  ○ Investigator Escalation     ○ Dedicated Case Manager   │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  Configuration: Standard | V0 | D2 | Analyst                   │    │
│  │  Estimated Cost: $32.00                                         │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  CONSENT                                                  4/4   │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  ◉ Send consent request to candidate via email                 │    │
│  │  ○ Candidate will provide consent in person                    │    │
│  │  ○ Consent already obtained (Reference: [____________])        │    │
│  │                                                                  │    │
│  │  ☑ Include California ICRAA disclosure (required for CA)       │    │
│  │  ☑ Include FCRA Summary of Rights                              │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  [Cancel]                                    [Save Draft] [Submit →]    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 15.3 Review Dashboard (Analyst Interface)

**Purpose:** Enable analysts to efficiently review findings and document decisions.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ☰ ELILE                   Review Dashboard            Amy Analyst ▼   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ 📋 REVIEW QUEUE                                    [Filters ▼]   │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │                                                                   │   │
│  │  ┌─────────────────┬───────────────────────────────────────────┐ │   │
│  │  │                 │                                           │ │   │
│  │  │  MY QUEUE (7)   │  Case: SCR-2025-00847                    │ │   │
│  │  │                 │  John Smith │ VP Operations │ Energy     │ │   │
│  │  │  ─────────────  │                                           │ │   │
│  │  │                 │  Risk Score: ●●●○○ 42 (MODERATE)         │ │   │
│  │  │  ▶ SCR-00847 ●● │  Time in Queue: 2h 14m                   │ │   │
│  │  │    John Smith   │                                           │ │   │
│  │  │    Moderate     │  ┌─────────────────────────────────────┐ │ │   │
│  │  │                 │  │ FINDINGS TO REVIEW                   │ │ │   │
│  │  │  ─────────────  │  ├─────────────────────────────────────┤ │ │   │
│  │  │                 │  │                                      │ │ │   │
│  │  │  SCR-00852 ●    │  │  ⚠ EMPLOYMENT GAP           [OPEN]  │ │ │   │
│  │  │    Maria Lopez  │  │  ──────────────────────────────────  │ │ │   │
│  │  │    Low          │  │  8-month gap: Jun 2021 - Feb 2022   │ │ │   │
│  │  │                 │  │  Employer "TechCorp" did not respond │ │ │   │
│  │  │  SCR-00849 ●●   │  │  to verification requests (3 attempts)│ │   │
│  │  │    Alex Chen    │  │                                      │ │ │   │
│  │  │    Moderate     │  │  Source: The Work Number, Direct     │ │ │   │
│  │  │                 │  │  Confidence: 0.92                    │ │ │   │
│  │  │  SCR-00848 ●●●  │  │                                      │ │ │   │
│  │  │    Bob Wilson   │  │  AI Assessment: Gap may indicate     │ │ │   │
│  │  │    High         │  │  undisclosed employment or personal  │ │ │   │
│  │  │                 │  │  circumstances. Recommend interview. │ │ │   │
│  │  │  SCR-00846 ●    │  │                                      │ │ │   │
│  │  │    Carol Davis  │  │  Analyst Action:                     │ │ │   │
│  │  │    Low          │  │  ○ Confirm as risk                   │ │ │   │
│  │  │                 │  │  ○ Dismiss (with reason)             │ │ │   │
│  │  │  SCR-00844 ●    │  │  ◉ Request more information          │ │ │   │
│  │  │    Dan Evans    │  │                                      │ │ │   │
│  │  │    Low          │  │  Notes: [Recommend HR interview    ] │ │ │   │
│  │  │                 │  │         [to clarify gap. Candidate ] │ │ │   │
│  │  │  SCR-00843 ●●   │  │         [has strong refs otherwise ] │ │ │   │
│  │  │    Eve Foster   │  │                                      │ │ │   │
│  │  │    Moderate     │  │  [Save Note]        [Resolve Finding]│ │ │   │
│  │  │                 │  │                                      │ │ │   │
│  │  └─────────────────┴──┴──────────────────────────────────────┘ │ │   │
│  │                                                                   │   │
│  │                       │  ⚠ CIVIL JUDGMENT          [PENDING]  │ │   │
│  │                       │  ──────────────────────────────────    │ │   │
│  │                       │  Judgment: $4,200 (2019)               │ │   │
│  │                       │  Status: Satisfied/Paid 2020-03-15     │ │   │
│  │                       │  Source: LA County Superior Court      │ │   │
│  │                       │  Confidence: 0.99                      │ │   │
│  │                       │                                        │ │   │
│  │                       │  AI Assessment: Resolved financial     │ │   │
│  │                       │  matter. No ongoing concern unless     │ │   │
│  │                       │  pattern exists.                       │ │   │
│  │                       │                                        │ │   │
│  │                       │  [Confirm Clear] [Flag for Review]     │ │   │
│  │                       │                                        │ │   │
│  │                       └────────────────────────────────────────┘ │   │
│  │                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ CASE SUMMARY                                                │ │   │
│  │  ├─────────────────────────────────────────────────────────────┤ │   │
│  │  │                                                              │ │   │
│  │  │  Total Findings: 8     Reviewed: 6     Pending: 2          │ │   │
│  │  │                                                              │ │   │
│  │  │  ✓ Identity (clear)    ✓ Criminal (clear)                  │ │   │
│  │  │  ⚠ Financial (review)  ⚠ Employment (review)               │ │   │
│  │  │  ✓ Education (clear)   ✓ Sanctions (clear)                 │ │   │
│  │  │  ✓ References (clear)  ✓ Connections (clear)               │ │   │
│  │  │                                                              │ │   │
│  │  │  [View Full Report]  [View Connection Graph]                │ │   │
│  │  │                                                              │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ CASE DECISION                                               │ │   │
│  │  ├─────────────────────────────────────────────────────────────┤ │   │
│  │  │                                                              │ │   │
│  │  │  Overall Recommendation:                                    │ │   │
│  │  │  ○ Clear - Proceed with hire                               │ │   │
│  │  │  ◉ Proceed with Caution - Minor concerns noted             │ │   │
│  │  │  ○ Hold - Additional investigation needed                  │ │   │
│  │  │  ○ Do Not Proceed - Significant concerns                   │ │   │
│  │  │                                                              │ │   │
│  │  │  Decision Notes (required):                                 │ │   │
│  │  │  ┌───────────────────────────────────────────────────────┐ │ │   │
│  │  │  │ Employment gap and resolved judgment noted. Gap      │ │ │   │
│  │  │  │ should be addressed in interview but does not        │ │ │   │
│  │  │  │ disqualify. Financial matter fully resolved.         │ │ │   │
│  │  │  └───────────────────────────────────────────────────────┘ │ │   │
│  │  │                                                              │ │   │
│  │  │  [Save Draft]              [Complete Review & Submit →]     │ │   │
│  │  │                                                              │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │                                                                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 15.4 Monitoring Console (Security Interface)

**Purpose:** Monitor ongoing screenings and respond to alerts.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ☰ ELILE               Monitoring Console             Mike Security ▼  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  🔔 ACTIVE ALERTS                                    [Settings] │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │ 🔴 CRITICAL │ ALT-2025-00127 │ 14 min ago                │  │    │
│  │  │ ─────────────────────────────────────────────────────────  │  │    │
│  │  │ Subject: James Wilson (Treasury Operations)               │  │    │
│  │  │ Alert: New sanctions match - OFAC SDN List update         │  │    │
│  │  │ Match Type: Name + DOB (confidence: 0.94)                 │  │    │
│  │  │ Monitoring: V3 Bi-monthly │ Enhanced Tier                 │  │    │
│  │  │                                                            │  │    │
│  │  │ [View Details] [Acknowledge] [Escalate to Investigator]   │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │ 🟠 HIGH │ ALT-2025-00126 │ 2 hours ago                   │  │    │
│  │  │ ─────────────────────────────────────────────────────────  │  │    │
│  │  │ Subject: Patricia Chen (IT Security)                      │  │    │
│  │  │ Alert: Evolution signal - Rapid network expansion         │  │    │
│  │  │ Detail: Connection count +280% in 30 days (12 → 46)      │  │    │
│  │  │ Pattern: "Network opacity" signature detected             │  │    │
│  │  │ Monitoring: V2 Monthly │ Enhanced Tier                    │  │    │
│  │  │                                                            │  │    │
│  │  │ [View Network Graph] [Acknowledge] [Schedule Interview]   │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │ 🟡 MEDIUM │ ALT-2025-00125 │ 6 hours ago                 │  │    │
│  │  │ ─────────────────────────────────────────────────────────  │  │    │
│  │  │ Subject: Robert Kim (Operations)                          │  │    │
│  │  │ Alert: New civil judgment filed                           │  │    │
│  │  │ Detail: Breach of contract suit, $45,000                  │  │    │
│  │  │ Monitoring: V1 Annual │ Standard Tier                     │  │    │
│  │  │                                                            │  │    │
│  │  │ [View Details] [Acknowledge] [Notify HR]                  │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  [Show 12 more alerts...]                                       │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  📊 MONITORING OVERVIEW                                         │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  ┌──────────────────────────────────────────────────────────┐   │    │
│  │  │ MONITORED POPULATION                                      │   │    │
│  │  │                                                           │   │    │
│  │  │ Total Monitored: 12,847                                   │   │    │
│  │  │                                                           │   │    │
│  │  │ By Vigilance:          By Tier:                          │   │    │
│  │  │ V1 Annual:   8,234     Standard:  11,429                 │   │    │
│  │  │ V2 Monthly:  3,891     Enhanced:   1,418                 │   │    │
│  │  │ V3 Bi-mthly:   722                                       │   │    │
│  │  │                                                           │   │    │
│  │  │ Checks Scheduled Today: 847                               │   │    │
│  │  │ Checks Completed Today: 612                               │   │    │
│  │  │ Checks Pending: 235                                       │   │    │
│  │  └──────────────────────────────────────────────────────────┘   │    │
│  │                                                                  │    │
│  │  ┌──────────────────────────────────────────────────────────┐   │    │
│  │  │ ALERT TREND (Last 30 Days)                               │   │    │
│  │  │                                                           │   │    │
│  │  │  Critical ▁▁▂▁▁▁▁▁▁▁▃▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁█                │   │    │
│  │  │  High     ▂▃▂▄▃▂▃▂▄▃▂▃▂▄▃▂▃▂▄▃▂▃▂▄▃▂▃▂▄▅                │   │    │
│  │  │  Medium   ▄▅▄▅▄▅▄▅▄▅▄▅▄▅▄▅▄▅▄▅▄▅▄▅▄▅▄▅▄▅                │   │    │
│  │  │  Low      ▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆                │   │    │
│  │  │           └────────────────────────────────┘              │   │    │
│  │  │           Dec 28                        Jan 27            │   │    │
│  │  └──────────────────────────────────────────────────────────┘   │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  🔍 QUICK SEARCH                          [Advanced Search →]   │    │
│  │  [Search by name, ID, or department...                        ] │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 15.5 Subject Portal (Candidate/Employee Interface)

**Purpose:** Allow subjects to view their screening status, provide information, and dispute findings.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ELILE                  Candidate Portal                   Sarah J. ▼  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                                                                  │    │
│  │      Hello Sarah,                                               │    │
│  │                                                                  │    │
│  │      Your background check for Acme Corporation is in progress.│    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  STATUS                                                         │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  [✓] Consent Provided ────────────────────────────── Jan 25    │    │
│  │      │                                                          │    │
│  │  [✓] Information Collected ───────────────────────── Jan 25    │    │
│  │      │                                                          │    │
│  │  [▶] Verification In Progress ─────────────────────  Now       │    │
│  │      │                                                          │    │
│  │      │  ✓ Identity Verification      Complete                  │    │
│  │      │  ✓ Criminal Records           Complete                  │    │
│  │      │  ▶ Employment History         In Progress               │    │
│  │      │  ○ Education Verification     Pending                   │    │
│  │      │  ○ Reference Checks           Pending                   │    │
│  │      │                                                          │    │
│  │  [ ] Review ──────────────────────────────────────── Pending   │    │
│  │      │                                                          │    │
│  │  [ ] Complete ────────────────────────────────────── Pending   │    │
│  │                                                                  │    │
│  │  Estimated Completion: January 28, 2025                        │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  ⚠ ACTION NEEDED                                                │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  We were unable to verify one of your previous employers.      │    │
│  │  Please provide additional documentation.                       │    │
│  │                                                                  │    │
│  │  Employer: TechCorp Inc.                                        │    │
│  │  Dates: June 2021 - February 2022                              │    │
│  │                                                                  │    │
│  │  Acceptable documentation:                                      │    │
│  │  • W-2 form for 2021 or 2022                                   │    │
│  │  • Pay stubs from TechCorp                                      │    │
│  │  • Employment letter on company letterhead                     │    │
│  │                                                                  │    │
│  │  [Upload Documentation]                                         │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  YOUR RIGHTS                                                    │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  Under federal and state law, you have the right to:           │    │
│  │                                                                  │    │
│  │  • Request a copy of your background check report              │    │
│  │  • Dispute any information you believe is inaccurate           │    │
│  │  • Receive notice before any adverse action is taken           │    │
│  │                                                                  │    │
│  │  [Request Report Copy]  [Start a Dispute]  [Learn More]        │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  Questions? Contact support@elile.com or call 1-800-XXX-XXXX           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

**Dispute Flow:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ELILE                  File a Dispute                     Sarah J. ▼  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  DISPUTE INFORMATION                                            │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │                                                                  │    │
│  │  You are disputing information in your background check.        │    │
│  │  Please provide details below. We are required to investigate  │    │
│  │  your dispute within 30 days.                                   │    │
│  │                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │ What are you disputing? *                                 │  │    │
│  │  │                                                            │  │    │
│  │  │ ○ Criminal record information                             │  │    │
│  │  │ ◉ Employment history                                      │  │    │
│  │  │ ○ Education verification                                  │  │    │
│  │  │ ○ Financial/credit information                            │  │    │
│  │  │ ○ Identity information                                    │  │    │
│  │  │ ○ Other                                                   │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │ Describe the error: *                                     │  │    │
│  │  │ ┌─────────────────────────────────────────────────────┐   │  │    │
│  │  │ │ The report shows I did not work at TechCorp from    │   │  │    │
│  │  │ │ June 2021 to February 2022. This is incorrect. I    │   │  │    │
│  │  │ │ was employed there during this entire period. The   │   │  │    │
│  │  │ │ company has since closed, which may explain why     │   │  │    │
│  │  │ │ verification failed.                                 │   │  │    │
│  │  │ └─────────────────────────────────────────────────────┘   │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │ Supporting documentation (optional but recommended):      │  │    │
│  │  │                                                            │  │    │
│  │  │  📎 W2_2021_TechCorp.pdf                    [Remove]      │  │    │
│  │  │  📎 TechCorp_PayStub_Dec2021.pdf            [Remove]      │  │    │
│  │  │                                                            │  │    │
│  │  │  [+ Add More Files]                                       │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │ ☑ I certify that the information I have provided is      │  │    │
│  │  │   true and accurate to the best of my knowledge.          │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  [Cancel]                               [Submit Dispute →]      │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  What happens next?                                                     │
│  1. We will investigate your dispute within 30 days                    │
│  2. You will receive written notification of the results               │
│  3. If we correct information, we'll notify anyone who received it     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 15.6 Admin Console

**Purpose:** System configuration and management for administrators.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ☰ ELILE                   Admin Console               Admin User ▼    │
├──────────┬──────────────────────────────────────────────────────────────┤
│          │                                                              │
│  MENU    │  COMPLIANCE RULES                              [+ New Rule] │
│          │                                                              │
│ ─────────│  ┌───────────────────────────────────────────────────────┐  │
│          │  │ 🔍 Filter: [All Locales ▼] [All Check Types ▼]        │  │
│ Dashboard│  └───────────────────────────────────────────────────────┘  │
│          │                                                              │
│ ─────────│  ┌───────────────────────────────────────────────────────┐  │
│          │  │                                                        │  │
│ Compliance│ │  Rule ID: FCRA-001                                    │  │
│ Rules    │  │  Jurisdiction: US Federal                             │  │
│ ▶        │  │  Check Type: Criminal Records                         │  │
│          │  │  Status: ● Active                                     │  │
│ Providers│  │                                                        │  │
│          │  │  Requirements:                                         │  │
│ Service  │  │  • 7-year lookback limit                              │  │
│ Configs  │  │  • Disposition required (no arrest-only)              │  │
│          │  │  • Relevance to position required                     │  │
│ Users    │  │                                                        │  │
│          │  │  [Edit] [Disable] [View History]                      │  │
│ Audit    │  │                                                        │  │
│ Logs     │  └───────────────────────────────────────────────────────┘  │
│          │                                                              │
│ System   │  ┌───────────────────────────────────────────────────────┐  │
│ Health   │  │                                                        │  │
│          │  │  Rule ID: CA-ICRAA-003                                │  │
│ ─────────│  │  Jurisdiction: US-California                          │  │
│          │  │  Check Type: Criminal Records                         │  │
│ Settings │  │  Status: ● Active                                     │  │
│          │  │                                                        │  │
│          │  │  Requirements (in addition to FCRA):                  │  │
│          │  │  • Additional disclosure to subject                   │  │
│          │  │  • Subject can receive copy before employer           │  │
│          │  │  • Specific adverse action procedures                 │  │
│          │  │                                                        │  │
│          │  │  [Edit] [Disable] [View History]                      │  │
│          │  │                                                        │  │
│          │  └───────────────────────────────────────────────────────┘  │
│          │                                                              │
│          │  ┌───────────────────────────────────────────────────────┐  │
│          │  │                                                        │  │
│          │  │  Rule ID: GDPR-DATA-002                               │  │
│          │  │  Jurisdiction: EU                                     │  │
│          │  │  Check Type: Behavioral Data                          │  │
│          │  │  Status: ● Active                                     │  │
│          │  │                                                        │  │
│          │  │  Restrictions:                                         │  │
│          │  │  • Explicit consent required (separate from screening)│  │
│          │  │  • Exclude: political, religious, health, orientation │  │
│          │  │  • Purpose limitation enforced                        │  │
│          │  │  • Right to erasure supported                         │  │
│          │  │                                                        │  │
│          │  │  [Edit] [Disable] [View History]                      │  │
│          │  │                                                        │  │
│          │  └───────────────────────────────────────────────────────┘  │
│          │                                                              │
│          │  [Show 47 more rules...]                                    │
│          │                                                              │
└──────────┴──────────────────────────────────────────────────────────────┘
```
<div style="break-after: page;"></div>

### 15.7 Interface Requirements Summary

| Interface | Key Requirements |
|-----------|------------------|
| **Screening Portal** | Quick screening initiation, status tracking, report access, HRIS integration hooks |
| **Review Dashboard** | Queue management, finding-by-finding review, decision documentation, AI assistance |
| **Monitoring Console** | Real-time alerts, alert triage, trend visualization, quick subject lookup |
| **Admin Console** | Rule management, provider configuration, user management, audit access |
| **Subject Portal** | Status visibility, document upload, dispute filing, FCRA rights information |
| **Executive Dashboard** | Portfolio metrics, trend analysis, risk distribution, cost tracking |

### 15.8 Cross-Cutting UI Requirements

**Accessibility (WCAG 2.1 AA):**
- Keyboard navigation for all functions
- Screen reader compatibility
- Sufficient color contrast
- Focus indicators
- Alt text for all images/icons

**Responsiveness:**
- Desktop-first design (primary use case)
- Tablet support for Review Dashboard (field analysts)
- Mobile support for Subject Portal only
- Minimum supported width: 1024px (desktop), 768px (tablet), 320px (mobile)

**Performance:**
- Initial page load < 2 seconds
- Subsequent navigation < 500ms
- Real-time updates via WebSocket for alerts
- Pagination for large data sets (50 items default)

**Security:**
- Session timeout: 30 minutes idle
- Re-authentication for sensitive actions (adverse action, dispute resolution)
- Audit logging of all user actions
- Role-based UI element visibility

---

*Document Version: 0.5.0*
*Last Updated: 2025-01-28*
