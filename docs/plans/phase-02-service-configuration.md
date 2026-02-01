# Phase 2: Service Configuration & Compliance

## Overview

Phase 2 implements the service tier model (Standard/Enhanced), investigation degrees (D1/D2/D3), vigilance levels (V0-V3), and the compliance engine for locale-based rule enforcement. This phase establishes the business logic for configuring screening services and ensuring regulatory compliance.

**Duration Estimate**: 2-3 weeks
**Team Size**: 2-3 developers
**Risk Level**: High (compliance errors have legal consequences)

## Phase Goals

- ✓ Define service tiers, investigation degrees, and vigilance levels
- ✓ Build configuration validator for tier/degree/vigilance combinations
- ✓ Implement compliance engine with US (FCRA) and EU (GDPR) rules
- ✓ Create consent management system
- ✓ Build data source resolver (maps config → providers)

## Tasks

| Seq | Task Name | Priority | Status | Dependencies | Plan Document |
|-----|-----------|----------|--------|--------------|---------------|
| 2.1 | Service Tier Models | P0 | Not Started | 1.1 | [task-2.1-service-tiers.md](../tasks/task-2.1-service-tiers.md) |
| 2.2 | Investigation Degree Models | P0 | Not Started | 1.1 | [task-2.2-investigation-degrees.md](../tasks/task-2.2-investigation-degrees.md) |
| 2.3 | Vigilance Level Models | P0 | Not Started | 1.1 | [task-2.3-vigilance-levels.md](../tasks/task-2.3-vigilance-levels.md) |
| 2.4 | Service Configuration Validator | P0 | Not Started | 2.1, 2.2, 2.3 | [task-2.4-config-validator.md](../tasks/task-2.4-config-validator.md) |
| 2.5 | Compliance Rule Repository | P0 | Not Started | 1.1 | [task-2.5-compliance-rules.md](../tasks/task-2.5-compliance-rules.md) |
| 2.6 | Compliance Engine (Rule Evaluator) | P0 | Not Started | 2.5, 1.3 | [task-2.6-compliance-engine.md](../tasks/task-2.6-compliance-engine.md) |
| 2.7 | Consent Management System | P0 | Not Started | 1.1, 1.4 | [task-2.7-consent-management.md](../tasks/task-2.7-consent-management.md) |
| 2.8 | Data Source Resolver | P0 | Not Started | 2.1, 2.6 | [task-2.8-data-source-resolver.md](../tasks/task-2.8-data-source-resolver.md) |
| 2.9 | FCRA Compliance Rules (US) | P0 | Not Started | 2.5 | [task-2.9-fcra-rules.md](../tasks/task-2.9-fcra-rules.md) |
| 2.10 | GDPR Compliance Rules (EU) | P0 | Not Started | 2.5 | [task-2.10-gdpr-rules.md](../tasks/task-2.10-gdpr-rules.md) |
| 2.11 | Service Preset Templates | P1 | Not Started | 2.4 | [task-2.11-service-presets.md](../tasks/task-2.11-service-presets.md) |
| 2.12 | Entitlement Checker | P1 | Not Started | 1.4, 2.1 | [task-2.12-entitlement-checker.md](../tasks/task-2.12-entitlement-checker.md) |

## Key Data Models

### Service Configuration
```python
class ServiceTier(str, Enum):
    STANDARD = "standard"  # T1: Core sources only
    ENHANCED = "enhanced"  # T2: Core + premium (behavioral, dark web, OSINT)

class InvestigationDegree(str, Enum):
    D1 = "d1"  # Subject only
    D2 = "d2"  # Subject + direct connections
    D3 = "d3"  # Subject + extended network (Enhanced only)

class VigilanceLevel(str, Enum):
    V0 = "v0"  # Pre-screen only
    V1 = "v1"  # Annual re-screen
    V2 = "v2"  # Monthly delta checks
    V3 = "v3"  # Bi-monthly + real-time sanctions

class ServiceConfig(BaseModel):
    tier: ServiceTier
    degree: InvestigationDegree
    vigilance: VigilanceLevel
    human_review: HumanReviewLevel

    def validate_combination(self) -> None:
        """D3 requires Enhanced tier."""
        if self.degree == InvestigationDegree.D3 and self.tier != ServiceTier.ENHANCED:
            raise ValueError("D3 requires Enhanced tier")
```

### Compliance Rules
```python
class ComplianceRule(Base):
    rule_id: UUID
    jurisdiction: str  # US, EU, CA, etc.
    rule_type: str  # check_permitted, lookback_limit, redaction, etc.
    check_type: str | None  # criminal, financial, etc.
    role_category: str | None  # government, finance, healthcare
    rule_logic: dict  # JSON rule definition
    active: bool

class ComplianceRuleset:
    """Evaluated rules for a specific locale + role combination."""
    locale: str
    permitted_checks: set[CheckType]
    lookback_limits: dict[CheckType, int]  # Days
    redaction_rules: list[RedactionRule]
    disclosure_requirements: list[DisclosureRequirement]
```

### Consent
```python
class ConsentRecord(Base):
    consent_id: UUID
    subject_entity_id: UUID
    tenant_id: UUID
    consent_scope: ConsentScope  # basic, enhanced, premium
    granted_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    consent_text: str  # The actual consent language shown
    signature_proof: str  # IP, timestamp, acceptance record
```

## Phase Acceptance Criteria

### Functional Requirements
- [x] Service configuration validator rejects invalid combinations (D3 + Standard tier)
- [x] Compliance engine returns correct permitted checks for US/EU locales
- [x] FCRA rules enforce 7-year lookback limit
- [x] GDPR rules block criminal checks for non-regulated roles
- [x] Consent system tracks scope and expiration
- [x] Data source resolver maps tier + locale → provider list

### Testing Requirements
- [x] Unit tests for all service models and validators
- [x] Compliance rule evaluation tests (100+ test cases covering locales)
- [x] Integration tests for consent workflow
- [x] Security tests: Cannot bypass compliance checks

### Documentation Requirements
- [x] Service tier comparison chart
- [x] Compliance rule documentation by jurisdiction
- [x] Consent flow diagrams

### Review Gates
- [x] Legal review: Compliance rules accuracy (FCRA, GDPR)
- [x] Architecture review: Service configuration model
- [x] Security review: Consent management

---

*Phase Owner: [Assign team lead]*
*Last Updated: 2026-01-29*
