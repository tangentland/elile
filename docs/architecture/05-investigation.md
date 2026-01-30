# Investigation & Screening Engine

> **Prerequisites**: [01-design.md](01-design.md), [02-core-system.md](02-core-system.md), [03-screening.md](03-screening.md)
>
> **See also**: [06-data-sources.md](06-data-sources.md) for provider details, [07-compliance.md](07-compliance.md) for rule enforcement

This document covers the screening engine implementation, the Search-Assess-Refine (SAR) loop, risk analysis, and connection mapping.

## Screening Engine (LangGraph Orchestration)

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

## Screening State Model

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

## Intelligent Iterative Search Process

The system uses an intelligent search process that proceeds through information types in a deliberate sequence, using a Search-Assess-Refine (SAR) loop for each type.

### Information Type Dependency Graph

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

### Search-Assess-Refine (SAR) Loop

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

### Cross-Type Query Enrichment

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

### Inconsistency Risk Scoring

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

### Knowledge Base Structure

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

### Configuration Parameters

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

## Connection Mapper (Degree-Aware)

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

## Risk Analyzer

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

## Finding Model

```python
class Finding(BaseModel):
    """A discrete finding from the screening process."""
    finding_id: UUID
    finding_type: FindingType
    category: FindingCategory

    # Content
    summary: str
    details: str
    raw_data: dict | None  # Original provider data

    # Scoring
    severity: Severity  # low | medium | high | critical
    confidence: float  # 0.0 - 1.0
    relevance_to_role: float  # 0.0 - 1.0

    # Provenance
    sources: list[DataSourceRef]
    corroborated: bool  # Found in multiple sources

    # Temporal
    finding_date: date | None  # When the event occurred
    discovered_at: datetime  # When we found it

    # Entity reference (for D2/D3 findings)
    subject_entity_id: UUID
    connection_path: list[UUID] | None  # Path from subject


class FindingCategory(str, Enum):
    CRIMINAL = "criminal"
    FINANCIAL = "financial"
    REGULATORY = "regulatory"
    REPUTATION = "reputation"
    VERIFICATION = "verification"
    BEHAVIORAL = "behavioral"
    NETWORK = "network"
```

---

*See [06-data-sources.md](06-data-sources.md) for provider integration*
*See [08-reporting.md](08-reporting.md) for how findings become reports*
