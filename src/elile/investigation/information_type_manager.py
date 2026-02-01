"""Information Type Manager for SAR loop orchestration.

This module implements the information type sequencing and dependency management
for the SAR loop. It ensures foundation types (identity, employment, education)
complete before dependent types (criminal, financial, etc.) are processed.

Key features:
- Phase-based information gathering (Foundation → Records → Intelligence → Network)
- Tier-based type filtering (Standard vs Enhanced)
- Compliance-aware type selection
- Dependency resolution for type ordering
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from elile.agent.state import InformationType, ServiceTier
from elile.compliance.types import CheckType, Locale, RoleCategory
from elile.core.logging import get_logger

if TYPE_CHECKING:
    from elile.compliance.engine import ComplianceEngine

logger = get_logger(__name__)


class InformationPhase(str, Enum):
    """Information gathering phases.

    Phases define the order in which information types are processed:
    1. Foundation: Identity, Employment, Education (must complete first)
    2. Records: Criminal, Civil, Financial, Licenses, Regulatory, Sanctions
    3. Intelligence: Adverse Media, Digital Footprint
    4. Network: D2/D3 relationship expansion
    5. Reconciliation: Cross-type verification
    """

    FOUNDATION = "foundation"
    RECORDS = "records"
    INTELLIGENCE = "intelligence"
    NETWORK = "network"
    RECONCILIATION = "reconciliation"


@dataclass
class TypeDependency:
    """Dependency specification for an information type."""

    info_type: InformationType
    phase: InformationPhase
    depends_on: list[InformationType] = field(default_factory=list)
    requires_enhanced: bool = False
    primary_check_type: CheckType | None = None


# Information type dependencies and phase assignments
TYPE_DEPENDENCIES: dict[InformationType, TypeDependency] = {
    # Foundation types (no dependencies)
    InformationType.IDENTITY: TypeDependency(
        info_type=InformationType.IDENTITY,
        phase=InformationPhase.FOUNDATION,
        depends_on=[],
        primary_check_type=CheckType.IDENTITY_BASIC,
    ),
    InformationType.EMPLOYMENT: TypeDependency(
        info_type=InformationType.EMPLOYMENT,
        phase=InformationPhase.FOUNDATION,
        depends_on=[InformationType.IDENTITY],
        primary_check_type=CheckType.EMPLOYMENT_VERIFICATION,
    ),
    InformationType.EDUCATION: TypeDependency(
        info_type=InformationType.EDUCATION,
        phase=InformationPhase.FOUNDATION,
        depends_on=[InformationType.IDENTITY],
        primary_check_type=CheckType.EDUCATION_VERIFICATION,
    ),
    # Records types (depend on foundation)
    InformationType.CRIMINAL: TypeDependency(
        info_type=InformationType.CRIMINAL,
        phase=InformationPhase.RECORDS,
        depends_on=[InformationType.IDENTITY],
        primary_check_type=CheckType.CRIMINAL_NATIONAL,
    ),
    InformationType.CIVIL: TypeDependency(
        info_type=InformationType.CIVIL,
        phase=InformationPhase.RECORDS,
        depends_on=[InformationType.IDENTITY],
        primary_check_type=CheckType.CIVIL_LITIGATION,
    ),
    InformationType.FINANCIAL: TypeDependency(
        info_type=InformationType.FINANCIAL,
        phase=InformationPhase.RECORDS,
        depends_on=[InformationType.IDENTITY],
        primary_check_type=CheckType.CREDIT_REPORT,
    ),
    InformationType.LICENSES: TypeDependency(
        info_type=InformationType.LICENSES,
        phase=InformationPhase.RECORDS,
        depends_on=[InformationType.IDENTITY],
        primary_check_type=CheckType.LICENSE_VERIFICATION,
    ),
    InformationType.REGULATORY: TypeDependency(
        info_type=InformationType.REGULATORY,
        phase=InformationPhase.RECORDS,
        depends_on=[InformationType.IDENTITY, InformationType.EMPLOYMENT],
        primary_check_type=CheckType.REGULATORY_ENFORCEMENT,
    ),
    InformationType.SANCTIONS: TypeDependency(
        info_type=InformationType.SANCTIONS,
        phase=InformationPhase.RECORDS,
        depends_on=[InformationType.IDENTITY],
        primary_check_type=CheckType.SANCTIONS_OFAC,
    ),
    # Intelligence types (depend on foundation + some records)
    InformationType.ADVERSE_MEDIA: TypeDependency(
        info_type=InformationType.ADVERSE_MEDIA,
        phase=InformationPhase.INTELLIGENCE,
        depends_on=[InformationType.IDENTITY, InformationType.EMPLOYMENT],
        primary_check_type=CheckType.ADVERSE_MEDIA,
    ),
    InformationType.DIGITAL_FOOTPRINT: TypeDependency(
        info_type=InformationType.DIGITAL_FOOTPRINT,
        phase=InformationPhase.INTELLIGENCE,
        depends_on=[InformationType.IDENTITY],
        requires_enhanced=True,
        primary_check_type=CheckType.DIGITAL_FOOTPRINT,
    ),
    # Network types (depend on multiple)
    InformationType.NETWORK_D2: TypeDependency(
        info_type=InformationType.NETWORK_D2,
        phase=InformationPhase.NETWORK,
        depends_on=[InformationType.IDENTITY, InformationType.EMPLOYMENT],
        primary_check_type=CheckType.NETWORK_D2,
    ),
    InformationType.NETWORK_D3: TypeDependency(
        info_type=InformationType.NETWORK_D3,
        phase=InformationPhase.NETWORK,
        depends_on=[InformationType.NETWORK_D2],
        requires_enhanced=True,
        primary_check_type=CheckType.NETWORK_D3,
    ),
    # Reconciliation (depends on all other types being complete)
    InformationType.RECONCILIATION: TypeDependency(
        info_type=InformationType.RECONCILIATION,
        phase=InformationPhase.RECONCILIATION,
        depends_on=[
            InformationType.IDENTITY,
            InformationType.EMPLOYMENT,
            InformationType.EDUCATION,
            InformationType.CRIMINAL,
        ],
        primary_check_type=None,  # No direct check type
    ),
}

# Phase ordering
PHASE_ORDER: list[InformationPhase] = [
    InformationPhase.FOUNDATION,
    InformationPhase.RECORDS,
    InformationPhase.INTELLIGENCE,
    InformationPhase.NETWORK,
    InformationPhase.RECONCILIATION,
]

# Types by phase for quick lookup
PHASE_TYPES: dict[InformationPhase, list[InformationType]] = {
    InformationPhase.FOUNDATION: [
        InformationType.IDENTITY,
        InformationType.EMPLOYMENT,
        InformationType.EDUCATION,
    ],
    InformationPhase.RECORDS: [
        InformationType.CRIMINAL,
        InformationType.CIVIL,
        InformationType.FINANCIAL,
        InformationType.LICENSES,
        InformationType.REGULATORY,
        InformationType.SANCTIONS,
    ],
    InformationPhase.INTELLIGENCE: [
        InformationType.ADVERSE_MEDIA,
        InformationType.DIGITAL_FOOTPRINT,
    ],
    InformationPhase.NETWORK: [
        InformationType.NETWORK_D2,
        InformationType.NETWORK_D3,
    ],
    InformationPhase.RECONCILIATION: [
        InformationType.RECONCILIATION,
    ],
}


@dataclass
class TypeSequence:
    """Result of type sequencing analysis."""

    next_types: list[InformationType]
    current_phase: InformationPhase
    phase_complete: bool
    all_complete: bool
    blocked_types: list[InformationType] = field(default_factory=list)
    blocked_reasons: dict[InformationType, str] = field(default_factory=dict)


class InformationTypeManager:
    """Manages information type processing order and dependencies.

    The InformationTypeManager ensures that:
    1. Foundation types complete before dependent types
    2. Type dependencies are satisfied before processing
    3. Tier-restricted types are filtered appropriately
    4. Compliance rules are respected per locale

    Example:
        ```python
        manager = InformationTypeManager(compliance_engine=engine)

        # Get initial types for screening
        sequence = manager.get_next_types(
            completed_types=[],
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
            role_category=RoleCategory.STANDARD,
        )
        # Returns: IDENTITY (only, as EMPLOYMENT/EDUCATION depend on IDENTITY)

        # After IDENTITY completes
        sequence = manager.get_next_types(
            completed_types=[InformationType.IDENTITY],
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
            role_category=RoleCategory.STANDARD,
        )
        # Returns: EMPLOYMENT, EDUCATION, CRIMINAL, CIVIL, etc.
        ```
    """

    def __init__(self, compliance_engine: "ComplianceEngine | None" = None):
        """Initialize the information type manager.

        Args:
            compliance_engine: Optional compliance engine for type filtering.
                If not provided, compliance filtering is skipped.
        """
        self.compliance = compliance_engine
        self._type_dependencies = TYPE_DEPENDENCIES

    def get_types_for_phase(
        self,
        phase: InformationPhase,
        tier: ServiceTier,
        locale: Locale,
        role_category: RoleCategory = RoleCategory.STANDARD,
    ) -> list[InformationType]:
        """Get permitted information types for a phase.

        Args:
            phase: Information gathering phase.
            tier: Service tier (Standard or Enhanced).
            locale: Subject locale for compliance filtering.
            role_category: Role category for compliance filtering.

        Returns:
            List of permitted types for this phase.
        """
        types = PHASE_TYPES.get(phase, [])

        # Filter by tier
        if tier == ServiceTier.STANDARD:
            types = [
                t for t in types if not self._type_dependencies[t].requires_enhanced
            ]

        # Filter by compliance
        if self.compliance:
            permitted_types = []
            for info_type in types:
                if self._is_type_permitted(info_type, locale, role_category, tier):
                    permitted_types.append(info_type)
            return permitted_types

        return types

    def get_next_types(
        self,
        completed_types: list[InformationType],
        tier: ServiceTier,
        locale: Locale,
        role_category: RoleCategory = RoleCategory.STANDARD,
    ) -> TypeSequence:
        """Get next information types to process based on completed types.

        Determines which types are ready to process by checking:
        1. All dependencies are satisfied
        2. Type is permitted for the tier
        3. Type is permitted by compliance rules

        Args:
            completed_types: Types already completed.
            tier: Service tier.
            locale: Subject locale.
            role_category: Role category.

        Returns:
            TypeSequence with next types and phase information.
        """
        completed_set = set(completed_types)

        # Determine current phase
        current_phase = self._get_current_phase(completed_set)

        # Check if current phase is complete
        phase_complete = self._is_phase_complete(current_phase, completed_set, tier)

        # Find all types ready to process
        next_types: list[InformationType] = []
        blocked_types: list[InformationType] = []
        blocked_reasons: dict[InformationType, str] = {}

        # Check ALL phases - types can be started if their dependencies are met
        for phase in PHASE_ORDER:
            phase_types = self.get_types_for_phase(phase, tier, locale, role_category)

            for info_type in phase_types:
                if info_type in completed_set:
                    continue

                # Check dependencies
                dep = self._type_dependencies[info_type]
                missing_deps = [d for d in dep.depends_on if d not in completed_set]

                if missing_deps:
                    blocked_types.append(info_type)
                    blocked_reasons[info_type] = (
                        f"Waiting for: {', '.join(d.value for d in missing_deps)}"
                    )
                else:
                    next_types.append(info_type)

        # Check if all types are complete
        all_permitted = self._get_all_permitted_types(tier, locale, role_category)
        all_complete = completed_set >= set(all_permitted)

        logger.debug(
            "Next types calculated",
            current_phase=current_phase.value,
            completed=len(completed_set),
            next_count=len(next_types),
            blocked_count=len(blocked_types),
        )

        return TypeSequence(
            next_types=next_types,
            current_phase=current_phase,
            phase_complete=phase_complete,
            all_complete=all_complete,
            blocked_types=blocked_types,
            blocked_reasons=blocked_reasons,
        )

    def get_type_dependencies(self, info_type: InformationType) -> list[InformationType]:
        """Get dependencies for an information type.

        Args:
            info_type: Information type to check.

        Returns:
            List of types that must complete before this type.
        """
        dep = self._type_dependencies.get(info_type)
        if dep:
            return dep.depends_on.copy()
        return []

    def get_type_phase(self, info_type: InformationType) -> InformationPhase | None:
        """Get the phase for an information type.

        Args:
            info_type: Information type to check.

        Returns:
            The phase this type belongs to, or None if unknown.
        """
        dep = self._type_dependencies.get(info_type)
        if dep:
            return dep.phase
        return None

    def is_foundation_type(self, info_type: InformationType) -> bool:
        """Check if a type is a foundation type.

        Foundation types (identity, employment, education) must complete
        before other types can be fully processed.

        Args:
            info_type: Information type to check.

        Returns:
            True if this is a foundation type.
        """
        return info_type in PHASE_TYPES[InformationPhase.FOUNDATION]

    def requires_foundation_complete(self) -> bool:
        """Check if foundation phase must complete before others.

        Returns:
            True (foundation always required first).
        """
        return True

    def _get_current_phase(self, completed_set: set[InformationType]) -> InformationPhase:
        """Determine the current phase based on completed types."""
        for phase in PHASE_ORDER:
            phase_types = set(PHASE_TYPES[phase])
            if not phase_types.issubset(completed_set):
                return phase
        return InformationPhase.RECONCILIATION

    def _is_phase_complete(
        self,
        phase: InformationPhase,
        completed_set: set[InformationType],
        tier: ServiceTier,
    ) -> bool:
        """Check if a phase is complete.

        A phase is complete when all permitted types in that phase
        have been processed.
        """
        phase_types = set(PHASE_TYPES.get(phase, []))

        # Filter out enhanced-only types for standard tier
        if tier == ServiceTier.STANDARD:
            phase_types = {
                t for t in phase_types if not self._type_dependencies[t].requires_enhanced
            }

        return phase_types.issubset(completed_set)

    def _is_type_permitted(
        self,
        info_type: InformationType,
        locale: Locale,
        role_category: RoleCategory,
        tier: ServiceTier,
    ) -> bool:
        """Check if a type is permitted by compliance rules."""
        if not self.compliance:
            return True

        dep = self._type_dependencies.get(info_type)
        if not dep or not dep.primary_check_type:
            return True  # No check type means always permitted

        result = self.compliance.evaluate_check(
            locale=locale,
            check_type=dep.primary_check_type,
            role_category=role_category,
            tier=tier,
        )
        return result.permitted

    def _get_all_permitted_types(
        self,
        tier: ServiceTier,
        locale: Locale,
        role_category: RoleCategory,
    ) -> list[InformationType]:
        """Get all types permitted for the given parameters."""
        permitted = []
        for phase in PHASE_ORDER:
            permitted.extend(self.get_types_for_phase(phase, tier, locale, role_category))
        return permitted


def create_information_type_manager(
    compliance_engine: "ComplianceEngine | None" = None,
) -> InformationTypeManager:
    """Factory function to create an InformationTypeManager.

    Args:
        compliance_engine: Optional compliance engine for type filtering.

    Returns:
        Configured InformationTypeManager instance.
    """
    return InformationTypeManager(compliance_engine=compliance_engine)
