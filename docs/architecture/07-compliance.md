# Compliance & Security

> **Prerequisites**: [01-design.md](01-design.md), [03-screening.md](03-screening.md)
>
> **See also**: [06-data-sources.md](06-data-sources.md) for data handling, [08-reporting.md](08-reporting.md) for audit reports

## Compliance Engine

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

## Compliance Rule Definition

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

## Locale-Specific Rules

| Locale | Key Restrictions |
|--------|------------------|
| **US** | FCRA (7-year lookback, adverse action notices), state ban-the-box laws |
| **EU/UK** | GDPR Art. 6/9, criminal data only for regulated roles, right to erasure |
| **Canada** | PIPEDA, RCMP for criminal checks |
| **APAC** | Highly variable by country |
| **LATAM** | Brazil LGPD, Argentina strict privacy |

### US Compliance Details

| Regulation | Requirements |
|------------|--------------|
| **FCRA** | 7-year lookback for most records; disclosure before check; adverse action process |
| **State Ban-the-Box** | Varies by state; some prohibit criminal questions on application |
| **CA ICRAA** | Additional California-specific disclosures and procedures |
| **NYC Fair Chance Act** | Criminal checks only after conditional offer |
| **EEOC Guidelines** | Individualized assessment for criminal records |

### EU/UK Compliance Details

| Regulation | Requirements |
|------------|--------------|
| **GDPR Art. 6** | Lawful basis required; legitimate interest or consent |
| **GDPR Art. 9** | Special category data (criminal, health) requires explicit justification |
| **UK DBS** | Official disclosure service for criminal records |
| **Right to Erasure** | Subject can request deletion (with exceptions) |

## Security Architecture

### Data Protection

| Data Type | At Rest | In Transit | Access Control |
|-----------|---------|------------|----------------|
| PII | AES-256 encryption | TLS 1.3 | Role-based + need-to-know |
| Premium source data | AES-256 + additional isolation | TLS 1.3 | Enhanced tier entitlement |
| API Keys | Vault/HSM | TLS 1.3 | Service accounts only |
| Audit Logs | Encrypted, immutable | TLS 1.3 | Append-only, admin read |
| Reports | Encrypted | TLS 1.3 | Time-limited access tokens |

### Access Control Model

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

### Data Retention

| Data Type | Retention Period | Basis |
|-----------|------------------|-------|
| Screening results | 7 years | FCRA, SOX |
| Premium source data | 30 days raw, 7 years findings | Minimize exposure |
| Audit logs | 7 years | Compliance |
| Consent records | Duration of employment + 7 years | Legal |

## Audit Logger

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

## Audit Event Types

| Event Type | Data Captured |
|------------|---------------|
| `screening.initiated` | Request details, service config, consent reference |
| `compliance.check` | Rules evaluated, permitted/blocked checks |
| `provider.query` | Provider ID, check type, cost, cache hit |
| `entity.resolved` | Resolution method, confidence score |
| `finding.extracted` | Finding type, severity, source |
| `risk.scored` | Score components, category breakdown |
| `report.generated` | Report type, persona, access granted to |
| `report.accessed` | Accessor, timestamp, IP |
| `review.decision` | Reviewer, decision, rationale |
| `alert.generated` | Alert type, severity, recipients |
| `data.erased` | Erasure request, data classes removed |

## GDPR Erasure Capability

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

## Consent Management

### Consent Scope

Consent must cover the specific checks being performed:

| Service Configuration | Required Consent Scope |
|----------------------|------------------------|
| Standard, D1 | Basic background check consent |
| Standard, D2 | Basic + connection investigation |
| Enhanced, D1 | Enhanced (behavioral, OSINT) consent |
| Enhanced, D2-D3 | Enhanced + extended network consent |
| Location data | Explicit location tracking consent |
| Dark web | Explicit security monitoring consent |

### Consent Verification

```python
class ConsentVerification(BaseModel):
    consent_reference: str
    consent_scope: list[ConsentScope]
    consent_date: datetime
    verification_method: str  # "e_signature" | "in_person" | "hris_api"

    # Disclosure tracking
    fcra_disclosure_provided: bool
    fcra_disclosure_date: datetime | None
    state_disclosures: list[StateDisclosure]

    # Validity
    is_valid: bool
    covers_requested_checks: bool
    missing_scopes: list[ConsentScope]
```

## Adverse Action Process

FCRA-required process when taking adverse action based on screening:

```
┌─────────────────────────────────────────────────────────────────┐
│                   ADVERSE ACTION WORKFLOW                        │
│                                                                  │
│  ┌─────────────────┐                                            │
│  │ Preliminary     │ ── Finding triggers potential adverse       │
│  │ Adverse Action  │    action decision                         │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Pre-Adverse     │ ── Subject receives:                       │
│  │ Notice          │    - Copy of consumer report               │
│  │                 │    - Summary of FCRA rights                │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Waiting Period  │ ── Minimum 5 business days                 │
│  │ (5+ days)       │    Subject can dispute findings            │
│  └────────┬────────┘                                            │
│           │                                                      │
│     ┌─────┴─────┐                                               │
│     ▼           ▼                                                │
│  [Dispute]   [No Dispute]                                       │
│     │           │                                                │
│     ▼           ▼                                                │
│  ┌──────────┐  ┌─────────────────┐                              │
│  │ Re-      │  │ Final Adverse   │ ── Subject receives:         │
│  │ investigate│  │ Action Notice   │    - Final decision         │
│  └──────────┘  │                 │    - CRA contact info        │
│                │                 │    - Dispute rights          │
│                └─────────────────┘                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

*See [08-reporting.md](08-reporting.md) for Compliance Audit Report*
*See [11-interfaces.md](11-interfaces.md) for Subject Portal dispute flow*
