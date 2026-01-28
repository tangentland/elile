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
| Queue | Redis Streams / RabbitMQ | Async job processing |
| Scheduler | Celery / APScheduler | Vigilance scheduling |
| Secrets | HashiCorp Vault | Secure credential management |
| Observability | OpenTelemetry + Prometheus | Tracing, metrics |
| Logging | structlog + ELK | Structured audit logs |

---
<div style="break-after: page;"></div>

## 11. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        KUBERNETES CLUSTER                        │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    INGRESS / API GATEWAY                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│    ┌─────────────────────────┼─────────────────────────┐        │
│    ▼                         ▼                         ▼        │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │  Screening   │     │    HRIS      │     │   Provider   │    │
│  │   Service    │     │   Gateway    │     │   Gateway    │    │
│  │  (replicas)  │     │  (replicas)  │     │  (replicas)  │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│         │                                         │             │
│         ▼                                         ▼             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │    Redis     │     │  Vigilance   │     │   Message    │    │
│  │   (Cache)    │     │  Scheduler   │     │    Queue     │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MANAGED SERVICES                            │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  PostgreSQL  │  │ Object Store │  │  Vault/KMS   │          │
│  │  (Primary)   │  │   (Reports)  │  │   (Secrets)  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
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

*Document Version: 0.3.0*
*Last Updated: 2025-01-27*
