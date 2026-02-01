# Task 2.11: Service Tier Presets

**Priority**: P1
**Phase**: 2 - Compliance Engine
**Estimated Effort**: 2 days
**Dependencies**: Task 2.1 (Compliance Rules Engine)

## Context

Define and implement service tier presets that bundle compliance rules, data sources, and investigation depths. Presets simplify screening configuration and ensure consistent compliance across organizations.

**Architecture Reference**: [03-screening.md](../docs/architecture/03-screening.md) - Service Tiers
**Related**: [02-core-system.md](../docs/architecture/02-core-system.md) - Configuration

## Objectives

1. Define Standard and Enhanced tier presets
2. Map tiers to allowed data sources and check types
3. Create preset validation rules
4. Support tier-specific entitlements
5. Enable preset customization per organization

## Technical Approach

### Preset Models

```python
# src/elile/compliance/presets/models.py
from enum import Enum
from typing import List, Dict, Set
from pydantic import BaseModel
from elile.compliance.models import CheckType
from elile.screening.models import ServiceTier, Degree

class PresetScope(str, Enum):
    """Preset applicability scope."""
    GLOBAL = "global"
    LOCALE_SPECIFIC = "locale_specific"
    ORG_CUSTOM = "org_custom"

class TierPreset(BaseModel):
    """Service tier preset configuration."""
    tier: ServiceTier
    name: str
    description: str
    scope: PresetScope

    # Investigation depth
    default_degree: Degree
    allowed_degrees: List[Degree]

    # Check types
    included_checks: Set[CheckType]
    optional_checks: Set[CheckType]

    # Data sources
    data_source_tier: int  # 1=core, 2=premium

    # Limits
    max_lookback_years: int
    max_concurrent_screenings: int

    # Pricing (for reference)
    base_cost_usd: float
    cost_per_check_usd: float

class LocalePresetOverride(BaseModel):
    """Locale-specific preset overrides."""
    locale: str
    tier: ServiceTier

    # Override specific checks
    excluded_checks: Set[CheckType] = set()
    required_checks: Set[CheckType] = set()

    # Override limits
    max_lookback_years: Optional[int] = None
```

### Preset Definitions

```python
# src/elile/compliance/presets/definitions.py
from elile.compliance.presets.models import TierPreset, PresetScope
from elile.compliance.models import CheckType
from elile.screening.models import ServiceTier, Degree

# Standard Tier Preset
STANDARD_PRESET = TierPreset(
    tier=ServiceTier.STANDARD,
    name="Standard Screening",
    description="Core background checks for standard positions",
    scope=PresetScope.GLOBAL,

    default_degree=Degree.D1,
    allowed_degrees=[Degree.D1, Degree.D2],

    included_checks={
        CheckType.IDENTITY_VERIFICATION,
        CheckType.CRIMINAL_RECORDS,
        CheckType.EMPLOYMENT_VERIFICATION,
        CheckType.EDUCATION_VERIFICATION,
        CheckType.SANCTIONS_WATCHLIST,
    },

    optional_checks={
        CheckType.CREDIT_REPORT,
        CheckType.PROFESSIONAL_LICENSES,
    },

    data_source_tier=1,  # Core sources only
    max_lookback_years=7,
    max_concurrent_screenings=100,

    base_cost_usd=50.0,
    cost_per_check_usd=5.0
)

# Enhanced Tier Preset
ENHANCED_PRESET = TierPreset(
    tier=ServiceTier.ENHANCED,
    name="Enhanced Screening",
    description="Comprehensive screening for sensitive positions",
    scope=PresetScope.GLOBAL,

    default_degree=Degree.D2,
    allowed_degrees=[Degree.D1, Degree.D2, Degree.D3],

    included_checks={
        CheckType.IDENTITY_VERIFICATION,
        CheckType.CRIMINAL_RECORDS,
        CheckType.EMPLOYMENT_VERIFICATION,
        CheckType.EDUCATION_VERIFICATION,
        CheckType.SANCTIONS_WATCHLIST,
        CheckType.PROFESSIONAL_LICENSES,
        CheckType.CIVIL_LITIGATION,
        CheckType.ADVERSE_MEDIA,
        CheckType.SOCIAL_MEDIA_OSINT,
        CheckType.DARK_WEB_MONITORING,
    },

    optional_checks={
        CheckType.CREDIT_REPORT,
        CheckType.FINANCIAL_REGULATORY,
    },

    data_source_tier=2,  # Premium sources included
    max_lookback_years=10,
    max_concurrent_screenings=500,

    base_cost_usd=150.0,
    cost_per_check_usd=10.0
)

# Preset registry
TIER_PRESETS = {
    ServiceTier.STANDARD: STANDARD_PRESET,
    ServiceTier.ENHANCED: ENHANCED_PRESET,
}
```

### Locale Overrides

```python
# src/elile/compliance/presets/locale_overrides.py
from elile.compliance.presets.models import LocalePresetOverride
from elile.compliance.models import CheckType
from elile.screening.models import ServiceTier

# US-specific overrides
US_STANDARD_OVERRIDE = LocalePresetOverride(
    locale="US",
    tier=ServiceTier.STANDARD,
    required_checks={
        CheckType.FCRA_DISCLOSURE,
        CheckType.FCRA_AUTHORIZATION,
    },
    max_lookback_years=7  # FCRA 7-year rule
)

# EU-specific overrides
EU_STANDARD_OVERRIDE = LocalePresetOverride(
    locale="EU",
    tier=ServiceTier.STANDARD,
    excluded_checks={
        CheckType.CREDIT_REPORT,  # Generally prohibited
    },
    required_checks={
        CheckType.GDPR_CONSENT,
        CheckType.RIGHT_TO_WORK,
    }
)

# Canada-specific overrides
CA_STANDARD_OVERRIDE = LocalePresetOverride(
    locale="CA",
    tier=ServiceTier.STANDARD,
    required_checks={
        CheckType.PIPEDA_CONSENT,
    }
)

# Override registry
LOCALE_OVERRIDES: Dict[str, Dict[ServiceTier, LocalePresetOverride]] = {
    "US": {
        ServiceTier.STANDARD: US_STANDARD_OVERRIDE,
    },
    "EU": {
        ServiceTier.STANDARD: EU_STANDARD_OVERRIDE,
    },
    "CA": {
        ServiceTier.STANDARD: CA_STANDARD_OVERRIDE,
    },
}
```

### Preset Service

```python
# src/elile/compliance/presets/service.py
from typing import Optional, Set
from elile.compliance.presets.definitions import TIER_PRESETS
from elile.compliance.presets.locale_overrides import LOCALE_OVERRIDES
from elile.compliance.presets.models import TierPreset, LocalePresetOverride
from elile.compliance.models import CheckType
from elile.screening.models import ServiceTier

class PresetService:
    """Service for managing tier presets."""

    def get_preset(
        self,
        tier: ServiceTier,
        locale: Optional[str] = None
    ) -> TierPreset:
        """Get preset with locale-specific overrides applied."""
        # Get base preset
        preset = TIER_PRESETS[tier].copy(deep=True)

        # Apply locale overrides
        if locale:
            preset = self._apply_locale_overrides(preset, locale)

        return preset

    def _apply_locale_overrides(
        self,
        preset: TierPreset,
        locale: str
    ) -> TierPreset:
        """Apply locale-specific overrides to preset."""
        # Check for exact locale match
        if locale in LOCALE_OVERRIDES:
            overrides = LOCALE_OVERRIDES[locale].get(preset.tier)
            if overrides:
                preset = self._merge_overrides(preset, overrides)

        # Check for region match (e.g., US-CA -> US)
        region = locale.split("-")[0]
        if region != locale and region in LOCALE_OVERRIDES:
            overrides = LOCALE_OVERRIDES[region].get(preset.tier)
            if overrides:
                preset = self._merge_overrides(preset, overrides)

        return preset

    def _merge_overrides(
        self,
        preset: TierPreset,
        overrides: LocalePresetOverride
    ) -> TierPreset:
        """Merge overrides into preset."""
        # Remove excluded checks
        preset.included_checks -= overrides.excluded_checks

        # Add required checks
        preset.included_checks |= overrides.required_checks

        # Override limits
        if overrides.max_lookback_years is not None:
            preset.max_lookback_years = overrides.max_lookback_years

        return preset

    def get_allowed_checks(
        self,
        tier: ServiceTier,
        locale: str
    ) -> Set[CheckType]:
        """Get all allowed checks for tier and locale."""
        preset = self.get_preset(tier, locale)
        return preset.included_checks | preset.optional_checks

    def is_check_allowed(
        self,
        tier: ServiceTier,
        locale: str,
        check_type: CheckType
    ) -> bool:
        """Check if specific check is allowed."""
        allowed = self.get_allowed_checks(tier, locale)
        return check_type in allowed

    def get_required_checks(
        self,
        tier: ServiceTier,
        locale: str
    ) -> Set[CheckType]:
        """Get required checks for tier and locale."""
        preset = self.get_preset(tier, locale)
        return preset.included_checks

    def validate_screening_config(
        self,
        tier: ServiceTier,
        locale: str,
        requested_checks: Set[CheckType],
        degree: Degree
    ) -> tuple[bool, Optional[str]]:
        """Validate screening configuration against preset."""
        preset = self.get_preset(tier, locale)

        # Check degree is allowed
        if degree not in preset.allowed_degrees:
            return False, f"Degree {degree} not allowed for tier {tier}"

        # Check all required checks are included
        missing = preset.included_checks - requested_checks
        if missing:
            return False, f"Missing required checks: {missing}"

        # Check no prohibited checks are requested
        allowed = preset.included_checks | preset.optional_checks
        prohibited = requested_checks - allowed
        if prohibited:
            return False, f"Prohibited checks: {prohibited}"

        return True, None

# Global preset service
preset_service = PresetService()
```

### Organization Preset Customization

```python
# src/elile/compliance/presets/org_customization.py
from typing import Optional, Dict
from pydantic import BaseModel
from elile.compliance.presets.models import TierPreset
from elile.compliance.models import CheckType
from elile.screening.models import ServiceTier

class OrgPresetCustomization(BaseModel):
    """Organization-specific preset customization."""
    org_id: str
    tier: ServiceTier

    # Custom check configuration
    additional_checks: Set[CheckType] = set()
    excluded_checks: Set[CheckType] = set()

    # Custom limits
    max_lookback_years: Optional[int] = None
    max_concurrent_screenings: Optional[int] = None

class OrgPresetService:
    """Service for organization-specific preset customization."""

    def __init__(self):
        self._customizations: Dict[tuple[str, ServiceTier], OrgPresetCustomization] = {}

    def set_customization(
        self,
        org_id: str,
        tier: ServiceTier,
        customization: OrgPresetCustomization
    ) -> None:
        """Set organization customization."""
        key = (org_id, tier)
        self._customizations[key] = customization

    def get_preset_for_org(
        self,
        org_id: str,
        tier: ServiceTier,
        locale: str
    ) -> TierPreset:
        """Get preset with org customization applied."""
        from elile.compliance.presets.service import preset_service

        # Start with base preset (with locale overrides)
        preset = preset_service.get_preset(tier, locale)

        # Apply org customization
        key = (org_id, tier)
        if key in self._customizations:
            customization = self._customizations[key]
            preset = self._apply_customization(preset, customization)

        return preset

    def _apply_customization(
        self,
        preset: TierPreset,
        customization: OrgPresetCustomization
    ) -> TierPreset:
        """Apply organization customization."""
        # Add additional checks
        preset.optional_checks |= customization.additional_checks

        # Remove excluded checks
        preset.included_checks -= customization.excluded_checks
        preset.optional_checks -= customization.excluded_checks

        # Override limits
        if customization.max_lookback_years is not None:
            preset.max_lookback_years = customization.max_lookback_years

        if customization.max_concurrent_screenings is not None:
            preset.max_concurrent_screenings = customization.max_concurrent_screenings

        return preset

# Global org preset service
org_preset_service = OrgPresetService()
```

## Implementation Checklist

### Preset Definitions
- [ ] Define Standard tier preset
- [ ] Define Enhanced tier preset
- [ ] Create locale-specific overrides
- [ ] Map check types to tiers
- [ ] Define tier limits and costs

### Preset Service
- [ ] Implement preset retrieval
- [ ] Apply locale overrides
- [ ] Add validation logic
- [ ] Support org customization
- [ ] Create preset comparison

### Integration
- [ ] Integrate with compliance engine
- [ ] Add preset selection UI
- [ ] Update screening creation
- [ ] Add preset documentation
- [ ] Create migration path

### Testing
- [ ] Test preset retrieval
- [ ] Test locale overrides
- [ ] Test org customization
- [ ] Validate check permissions
- [ ] Test preset validation

## Testing Strategy

```python
# tests/compliance/presets/test_preset_service.py
import pytest
from elile.compliance.presets.service import preset_service
from elile.compliance.models import CheckType
from elile.screening.models import ServiceTier, Degree

def test_get_standard_preset():
    """Test Standard tier preset."""
    preset = preset_service.get_preset(ServiceTier.STANDARD)

    assert preset.tier == ServiceTier.STANDARD
    assert preset.default_degree == Degree.D1
    assert CheckType.IDENTITY_VERIFICATION in preset.included_checks

def test_locale_override():
    """Test locale-specific override."""
    preset = preset_service.get_preset(ServiceTier.STANDARD, locale="EU")

    # Credit report should be excluded in EU
    assert CheckType.CREDIT_REPORT not in preset.included_checks
    assert CheckType.GDPR_CONSENT in preset.included_checks

def test_check_allowed():
    """Test check permission validation."""
    allowed = preset_service.is_check_allowed(
        ServiceTier.STANDARD,
        "US",
        CheckType.CRIMINAL_RECORDS
    )
    assert allowed

def test_validate_config():
    """Test screening configuration validation."""
    valid, error = preset_service.validate_screening_config(
        tier=ServiceTier.STANDARD,
        locale="US",
        requested_checks={
            CheckType.IDENTITY_VERIFICATION,
            CheckType.CRIMINAL_RECORDS,
        },
        degree=Degree.D1
    )
    assert valid
    assert error is None
```

## Success Criteria

- [ ] All tier presets defined and documented
- [ ] Locale overrides apply correctly
- [ ] Organization customization works
- [ ] Preset validation catches invalid configs
- [ ] Check permissions enforced correctly
- [ ] Preset tests achieve >90% coverage

## Documentation

- Document all tier presets and included checks
- Create locale override reference
- Add preset selection guide
- Document customization options

## Future Enhancements

- Add preset versioning
- Create preset templates library
- Support industry-specific presets
- Add cost estimation based on presets
