# Task 5.6: Information Type Manager

## Overview

Implement manager that orchestrates information type processing in dependency order, ensuring foundation types complete before dependent types. Manages phase transitions and type dependencies.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 5.1: SAR State Machine (type state tracking)
- Task 2.1: Service Tiers (tier-based types)
- Task 2.6: Compliance Engine (permitted checks)

## Implementation Checklist

- [ ] Create InformationTypeManager with dependency graph
- [ ] Implement phase sequencing (Foundation → Records → Intelligence)
- [ ] Build dependency resolution logic
- [ ] Add tier-based type filtering
- [ ] Create compliance-aware type selection
- [ ] Write comprehensive manager tests

## Key Implementation

```python
# src/elile/investigation/information_type_manager.py
class InformationPhase(str, Enum):
    """Information gathering phases."""
    FOUNDATION = "foundation"  # Identity, Employment, Education
    RECORDS = "records"  # Criminal, Financial, etc.
    INTELLIGENCE = "intelligence"  # Adverse Media, Digital Footprint
    NETWORK = "network"  # D2/D3 expansion

class InformationTypeManager:
    """Manages information type processing order and dependencies."""

    def __init__(
        self,
        compliance_engine: ComplianceEngine,
        audit_logger: AuditLogger
    ):
        self.compliance = compliance_engine
        self.audit = audit_logger

        # Define dependency graph
        self.phase_types = {
            InformationPhase.FOUNDATION: [
                InformationType.IDENTITY,
                InformationType.EMPLOYMENT,
                InformationType.EDUCATION
            ],
            InformationPhase.RECORDS: [
                InformationType.CRIMINAL,
                InformationType.CIVIL,
                InformationType.FINANCIAL,
                InformationType.LICENSES,
                InformationType.REGULATORY,
                InformationType.SANCTIONS
            ],
            InformationPhase.INTELLIGENCE: [
                InformationType.ADVERSE_MEDIA,
                InformationType.DIGITAL_FOOTPRINT
            ]
        }

        # Types that require Enhanced tier
        self.enhanced_only_types = {
            InformationType.DIGITAL_FOOTPRINT
        }

    def get_types_for_phase(
        self,
        phase: InformationPhase,
        tier: ServiceTier,
        locale: Locale,
        role_category: RoleCategory
    ) -> list[InformationType]:
        """
        Get permitted information types for phase.

        Args:
            phase: Information gathering phase
            tier: Service tier
            locale: Subject locale
            role_category: Role category

        Returns:
            List of permitted types for this phase
        """
        types = self.phase_types.get(phase, [])

        # Filter by tier
        if tier == ServiceTier.STANDARD:
            types = [t for t in types if t not in self.enhanced_only_types]

        # Filter by compliance
        permitted_types = []
        for info_type in types:
            check_type = self._map_to_check_type(info_type)
            if self.compliance.is_check_permitted(
                check_type, locale, role_category, tier
            ):
                permitted_types.append(info_type)

        return permitted_types

    def get_next_types(
        self,
        completed_types: list[InformationType],
        tier: ServiceTier,
        locale: Locale,
        role_category: RoleCategory
    ) -> list[InformationType]:
        """
        Get next information types to process based on completed types.

        Args:
            completed_types: Types already completed
            tier: Service tier
            locale: Subject locale
            role_category: Role category

        Returns:
            Next types ready to process
        """
        # Determine current phase
        foundation_types = set(self.phase_types[InformationPhase.FOUNDATION])
        completed_set = set(completed_types)

        if not foundation_types.issubset(completed_set):
            # Still in foundation phase
            phase = InformationPhase.FOUNDATION
        elif not self._phase_complete(InformationPhase.RECORDS, completed_set):
            # Foundation done, move to records
            phase = InformationPhase.RECORDS
        else:
            # Records done, move to intelligence
            phase = InformationPhase.INTELLIGENCE

        # Get permitted types for phase
        available = self.get_types_for_phase(phase, tier, locale, role_category)

        # Filter out already completed
        next_types = [t for t in available if t not in completed_set]

        return next_types

    def _phase_complete(
        self,
        phase: InformationPhase,
        completed: set[InformationType]
    ) -> bool:
        """Check if phase is complete."""
        phase_types = set(self.phase_types.get(phase, []))
        return phase_types.issubset(completed)

    def must_complete_foundation_first(self) -> bool:
        """Foundation phase must complete before others."""
        return True

    def _map_to_check_type(self, info_type: InformationType) -> CheckType:
        """Map information type to check type."""
        mapping = {
            InformationType.IDENTITY: CheckType.IDENTITY_VERIFICATION,
            InformationType.CRIMINAL: CheckType.CRIMINAL_RECORDS,
            InformationType.EMPLOYMENT: CheckType.EMPLOYMENT_VERIFICATION,
            InformationType.EDUCATION: CheckType.EDUCATION_VERIFICATION,
            InformationType.FINANCIAL: CheckType.CREDIT_CHECK,
            InformationType.CIVIL: CheckType.CIVIL_LITIGATION,
            InformationType.LICENSES: CheckType.PROFESSIONAL_LICENSE,
            InformationType.REGULATORY: CheckType.REGULATORY_ACTIONS,
            InformationType.SANCTIONS: CheckType.SANCTIONS_PEP,
            InformationType.ADVERSE_MEDIA: CheckType.ADVERSE_MEDIA,
            InformationType.DIGITAL_FOOTPRINT: CheckType.DIGITAL_FOOTPRINT,
        }
        return mapping.get(info_type, CheckType.IDENTITY_VERIFICATION)
```

## Testing Requirements

### Unit Tests
- Phase-based type grouping
- Dependency resolution
- Tier-based filtering
- Compliance-based filtering
- Next types determination

### Integration Tests
- Complete phase progression
- Foundation → Records → Intelligence flow
- Enhanced tier type access

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] InformationTypeManager sequences types by phase
- [ ] Foundation phase must complete first
- [ ] Enhanced-only types filtered for Standard tier
- [ ] Compliance engine filters permitted types
- [ ] Next types calculated from completed types

## Deliverables

- `src/elile/investigation/information_type_manager.py`
- `tests/unit/test_information_type_manager.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - Information Type Dependencies

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
