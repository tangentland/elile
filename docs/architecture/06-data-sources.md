# Data Sources & Provider Integration

> **Prerequisites**: [01-design.md](01-design.md), [02-core-system.md](02-core-system.md)
>
> **See also**: [03-screening.md](03-screening.md) for tier definitions, [07-compliance.md](07-compliance.md) for data handling rules

## Core Data Sources (Standard Tier)

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
│  SOCIAL MEDIA (Publicly available)                              │
│  ├── Social media profile search                                │
│  └── Public post content analysis (keyword-based)               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Core Provider Categories

| Category | Providers | Check Types |
|----------|-----------|-------------|
| Aggregators | Sterling, HireRight, Checkr | Full suite |
| Credit Bureaus | Experian, Equifax, TransUnion | Credit, Identity |
| Court Records | PACER, CourtListener, state systems | Criminal, Civil |
| Sanctions | World-Check, Dow Jones, OFAC direct | PEP, Sanctions |
| Employment | The Work Number, direct verification | Employment history |
| Education | NSC, direct verification | Education |
| Social Media | Social-Searcher, LinkedIn, X, Facebook, Mastodon, Bluesky | Public posts, connections |

## Premium Data Sources (Enhanced Tier Only)

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

### Premium Provider Categories

| Category | Providers | Data Types |
|----------|-----------|------------|
| Data Brokers | Acxiom, Oracle Data Cloud, Experian Marketing | Behavioral, interests, demographics |
| Identity Resolution | Pipl, FullContact, LiveRamp | Cross-platform identity linking |
| Location Intelligence | Foursquare, SafeGraph, Placer.ai | Movement patterns, venue visits |
| Alternative Finance | Plaid, Finicity, Experian RentBureau | Transaction data, payment history |
| OSINT Platforms | Maltego, SpiderFoot, custom tools | Digital footprint aggregation |
| Dark Web | Recorded Future, Flashpoint, DarkOwl | Leak detection, threat intel |
| Corporate Intelligence | OpenCorporates, Orbis, Dun & Bradstreet | Beneficial ownership, corporate links |

## Data Source Compliance Considerations

| Data Type | Compliance Concern | Mitigation |
|-----------|-------------------|------------|
| Behavioral/Interest data | May proxy for protected classes | Filter categories, document business necessity |
| Location data | Privacy laws, consent requirements | Explicit consent, purpose limitation |
| Social media | GDPR Art. 9, EEOC concerns | Limit to public, exclude protected content |
| Dark web | Data provenance concerns | Use for security only, not adverse decisions |
| Data broker segments | FCRA applicability unclear | Exclude from adverse action basis |
| Political/religious indicators | Protected in most jurisdictions | Exclude from analysis |

## Data Provider Gateway

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

## Provider Interface

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

## Entity Resolution

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

## Provider Availability & Fallback

The gateway handles provider unavailability gracefully:

| Scenario | Action |
|----------|--------|
| Provider timeout | Retry with exponential backoff (max 3) |
| Provider error | Try alternate provider if available |
| Provider down | Mark provider unhealthy, route to alternates |
| No alternate | Flag as incomplete, continue with other checks |
| All providers down | Partial report with unavailable checks noted |

## Cost Tracking

Every provider query tracks cost for billing and optimization:

```python
class ProviderQueryCost(BaseModel):
    query_id: UUID
    provider_id: str
    check_type: CheckType

    # Cost
    base_cost: Decimal
    volume_discount: Decimal
    final_cost: Decimal
    currency: str

    # Attribution
    screening_id: UUID
    customer_id: UUID

    # Cache impact
    cache_hit: bool  # If True, no cost incurred
    cache_saved: Decimal | None  # Cost we would have paid
```

---

*See [02-core-system.md](02-core-system.md) for caching strategy*
*See [07-compliance.md](07-compliance.md) for data handling rules*
