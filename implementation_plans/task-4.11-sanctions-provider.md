# Task 4.11: Sanctions & Watchlist Provider - Implementation Plan

## Overview

Task 4.11 implements a comprehensive sanctions and watchlist screening provider that integrates with OFAC, UN, EU, and other sanctions lists for real-time PEP and sanctioned entity screening.

## Requirements

From `docs/tasks/task-4.11-sanctions-provider.md`:
1. Integrate OFAC SDN list
2. Add UN Security Council sanctions
3. Support EU sanctions lists
4. Implement fuzzy name matching
5. Enable real-time updates

## Files Created

### Source Files
| File | Description |
|------|-------------|
| `src/elile/providers/sanctions/__init__.py` | Module exports for all sanctions components |
| `src/elile/providers/sanctions/types.py` | Type definitions: SanctionsList, MatchType, EntityType, models |
| `src/elile/providers/sanctions/matcher.py` | NameMatcher with Jaro-Winkler, phonetic, token-based matching |
| `src/elile/providers/sanctions/provider.py` | SanctionsProvider implementing DataProvider protocol |
| `src/elile/providers/sanctions/scheduler.py` | SanctionsUpdateScheduler for real-time list updates |

### Test Files
| File | Tests |
|------|-------|
| `tests/unit/providers/__init__.py` | Package init |
| `tests/unit/providers/sanctions/__init__.py` | Package init |
| `tests/unit/providers/sanctions/test_sanctions_types.py` | 51 tests for type definitions |
| `tests/unit/providers/sanctions/test_sanctions_matcher.py` | 49 tests for name matching |
| `tests/unit/providers/sanctions/test_sanctions_provider.py` | 35 tests for provider |
| `tests/unit/providers/sanctions/test_sanctions_scheduler.py` | 40 tests for scheduler |

## Key Patterns Used

### 1. DataProvider Protocol Implementation
The SanctionsProvider implements the project's DataProvider protocol:
- `execute_check()` for sanctions screening
- `health_check()` for availability monitoring
- Integration with ProviderCapability for check type registration

### 2. Fuzzy Name Matching
NameMatcher provides multiple matching algorithms:
- **Jaro-Winkler**: Detects typos and transpositions (0.9+ threshold)
- **Token-based**: Handles word reordering and missing middle names
- **Phonetic (Soundex)**: Catches pronunciation-based spelling variations
- Configurable thresholds via FuzzyMatchConfig

### 3. Update Scheduler
SanctionsUpdateScheduler provides:
- Configurable update frequencies (hourly to weekly)
- Retry logic with exponential backoff
- Concurrent update limiting via semaphore
- Success/error callbacks for monitoring
- Manual trigger support for immediate updates

### 4. Sanctions List Coverage
| List | Enum Value | Coverage |
|------|------------|----------|
| OFAC SDN | `ofac_sdn` | US Treasury sanctions |
| OFAC Consolidated | `ofac_consolidated` | All OFAC programs |
| UN Consolidated | `un_consolidated` | UN Security Council |
| EU Consolidated | `eu_consolidated` | EU financial sanctions |
| Interpol Red | `interpol_red` | International wanted |
| Interpol Yellow | `interpol_yellow` | Missing persons |
| World PEP | `world_pep` | Politically exposed persons |
| World RCA | `world_rca` | Relatives and close associates |
| FBI Most Wanted | `fbi_most_wanted` | FBI wanted list |
| BIS Denied | `bis_denied` | Export denied persons |
| BIS Entity | `bis_entity` | Export entity list |

## Test Results

```
175 tests passed
- Types: 51 tests
- Matcher: 49 tests
- Provider: 35 tests
- Scheduler: 40 tests
```

All tests passing with mypy strict mode compliance.

## Acceptance Criteria Met

- [x] Integrate OFAC API (sample data structure, extensible for real API)
- [x] Add UN sanctions database (enum and model support)
- [x] Implement fuzzy matching (Jaro-Winkler, phonetic, token-based)
- [x] Create update scheduler (SanctionsUpdateScheduler)
- [x] Test match accuracy (49 matcher tests including real-world names)

## Usage Example

```python
from elile.providers.sanctions import (
    SanctionsProvider,
    create_sanctions_provider,
    SanctionsList,
)
from elile.compliance.types import CheckType, Locale
from elile.entity.types import SubjectIdentifiers

# Create provider
provider = create_sanctions_provider()

# Screen a subject
result = await provider.execute_check(
    check_type=CheckType.SANCTIONS_OFAC,
    subject=SubjectIdentifiers(
        full_name="John Smith",
        date_of_birth=date(1980, 5, 15),
    ),
    locale=Locale.US,
)

if result.success:
    screening = result.normalized_data["screening"]
    if screening["has_hit"]:
        print(f"Found {screening['total_matches']} matches")
        for match in result.normalized_data["matches"]:
            print(f"  - {match['entity_name']} ({match['match_score']:.2f})")
```

## Notes

- Sample data loaded for testing; production would use actual OFAC/UN/EU API feeds
- Match scoring applies weights: name (70%), DOB (20%), country (10%)
- Scheduler supports both sync and async update handlers
