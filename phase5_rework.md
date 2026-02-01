# Phase 5 Rework Handoff

## Overview

Phase 5 (Investigation Engine) is marked as complete in `IMPLEMENTATION_STATUS.md` but **8 of 16 task implementations are missing**. The existing Phase 6 code depends on these missing modules and tests cannot run.

**Date**: 2026-02-01
**Priority**: P0 - Critical (blocks all testing)

---

## Current State

### Phase 5 Files That EXIST (Tasks 5.1-5.7, partial 5.10):
| Task | File | Status |
|------|------|--------|
| 5.1 | `investigation/sar_machine.py` | ✅ Exists |
| 5.2 | `investigation/query_planner.py` | ✅ Exists |
| 5.3 | `investigation/query_executor.py` | ✅ Exists |
| 5.4 | `investigation/result_assessor.py` | ✅ Exists |
| 5.5 | `investigation/query_refiner.py` | ✅ Exists |
| 5.6 | `investigation/information_type_manager.py` | ✅ Exists |
| 5.7 | `investigation/confidence_scorer.py` | ✅ Exists |
| 5.10 | `investigation/finding_extractor.py` | ⚠️ Stub only |
| - | `investigation/models.py` | ✅ Exists (SAR models) |

### Phase 5 Files That are MISSING:
| Task | File | Status |
|------|------|--------|
| 5.8 | `investigation/iteration_controller.py` | ❌ Missing |
| 5.9 | `investigation/sar_orchestrator.py` | ❌ Missing |
| 5.11 | `investigation/phases/foundation.py` | ❌ Missing |
| 5.12 | `investigation/phases/records.py` | ❌ Missing |
| 5.13 | `investigation/phases/intelligence.py` | ❌ Missing |
| 5.14 | `investigation/phases/network.py` | ❌ Missing (CRITICAL) |
| 5.15 | `investigation/phases/reconciliation.py` | ❌ Missing |
| 5.16 | `investigation/checkpoint.py` | ❌ Missing |

### Critical Blocker
`investigation/phases/network.py` is imported by:
- `src/elile/risk/connection_analyzer.py` (Task 6.6)
- `src/elile/investigation/phases/__init__.py`

**All tests fail to run** until this module exists.

---

## Implementation Order

Implement tasks in this order (respects dependencies):

1. **Task 5.8**: Iteration Controller
2. **Task 5.9**: SAR Loop Orchestrator
3. **Task 5.11**: Foundation Phase Handler
4. **Task 5.12**: Records Phase Handler
5. **Task 5.13**: Intelligence Phase Handler
6. **Task 5.14**: Network Phase Handler ⚠️ CRITICAL
7. **Task 5.15**: Reconciliation Phase Handler
8. **Task 5.16**: Investigation Checkpoint Manager

---

## Workflow For Each Task

### 1. Create Feature Branch
```bash
git checkout main
git pull origin main
git checkout -b feature/task-5.X-description
```

### 2. Read Task Specification
```
docs/tasks/task-5.X-description.md
```

### 3. Implement Module
- Create implementation file in `src/elile/investigation/`
- Follow patterns from existing modules (5.1-5.7)
- Update `src/elile/investigation/__init__.py` exports
- For phase handlers, update `src/elile/investigation/phases/__init__.py`

### 4. Write Tests
- Create `tests/unit/test_<module_name>.py`
- Target 90%+ coverage
- Include unit tests and integration tests where specified

### 5. Run Tests
```bash
uv run pytest tests/unit/test_<module_name>.py -v
```

### 6. Format and Lint
```bash
black . --line-length 100 --target-version py314
ruff check .
mypy src/elile
```

### 7. Commit with Descriptive Message
```bash
git add src/elile/investigation/<file>.py
git add tests/unit/test_<file>.py
git add src/elile/investigation/__init__.py
git commit -m "$(cat <<'EOF'
Implement Task 5.X: <Task Name>

- <Key deliverable 1>
- <Key deliverable 2>
- <Number> unit tests passing

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### 8. Tag the Commit
```bash
git tag phase5/task-5.X
```

### 9. Merge to Main (DO NOT DELETE BRANCH)
```bash
git checkout main
git merge feature/task-5.X-description
git push origin main
git push origin phase5/task-5.X
git push origin feature/task-5.X-description
```

### 10. Update Documentation
- Update `IMPLEMENTATION_STATUS.md` with actual completion
- Update `CODEBASE_INDEX.md` with new module documentation

---

## Task Details

### Task 5.8: Iteration Controller
**File**: `src/elile/investigation/iteration_controller.py`
**Test**: `tests/unit/test_iteration_controller.py`
**Spec**: `docs/tasks/task-5.8-iteration-controller.md`

**Key Classes**:
- `IterationController` - Manages SAR loop flow decisions
- `IterationDecision` - Decision with context
- `ControllerConfig` - Configuration
- `DecisionType` - Enum (CONTINUE, THRESHOLD, CAPPED, DIMINISHED)

**Dependencies**: Task 5.1, 5.7, 5.4

---

### Task 5.9: SAR Loop Orchestrator
**File**: `src/elile/investigation/sar_orchestrator.py`
**Test**: `tests/unit/test_sar_orchestrator.py`
**Spec**: `docs/tasks/task-5.9-sar-loop-orchestrator.md`

**Key Classes**:
- `SARLoopOrchestrator` - Coordinates all SAR components
- `OrchestratorConfig` - Configuration
- `InvestigationResult` - Complete investigation result
- `TypeCycleResult` - Single type cycle result
- `ProgressEvent` - Progress tracking events

**Dependencies**: Tasks 5.1-5.8

---

### Task 5.11: Foundation Phase Handler
**File**: `src/elile/investigation/phases/foundation.py`
**Test**: `tests/unit/test_foundation_phase.py`
**Spec**: `docs/tasks/task-5.11-foundation-phase-handler.md`

**Key Classes**:
- `FoundationPhaseHandler` - Sequential identity/employment/education
- `BaselineProfile` - Combined baseline data
- `IdentityBaseline`, `EmploymentBaseline`, `EducationBaseline`
- `VerificationStatus` - Enum
- `FoundationConfig`, `FoundationPhaseResult`

**Dependencies**: Task 5.1, 5.9

---

### Task 5.12: Records Phase Handler
**File**: `src/elile/investigation/phases/records.py`
**Test**: `tests/unit/test_records_phase.py`
**Spec**: `docs/tasks/task-5.12-records-phase-handler.md`

**Key Classes**:
- `RecordsPhaseHandler` - Parallel processing of 6 record types
- `RecordsProfile` - Combined records data
- `CriminalRecord`, `CivilRecord`, `FinancialRecord`, `LicenseRecord`, `RegulatoryRecord`, `SanctionsRecord`
- `RecordSeverity`, `RecordType` - Enums
- `RecordsConfig`, `RecordsPhaseResult`

**Dependencies**: Task 5.11

---

### Task 5.13: Intelligence Phase Handler
**File**: `src/elile/investigation/phases/intelligence.py`
**Test**: `tests/unit/test_intelligence_phase.py`
**Spec**: `docs/tasks/task-5.13-intelligence-phase-handler.md`

**Key Classes**:
- `IntelligencePhaseHandler` - Parallel OSINT processing
- `IntelligenceProfile` - Media, social, professional data
- `MediaMention`, `MediaSentiment`, `MediaCategory`
- `SocialProfile`, `SocialPlatform`
- `ProfessionalPresence`, `RiskIndicator`
- `IntelligenceConfig`, `IntelligencePhaseResult`

**Dependencies**: Task 5.12

---

### Task 5.14: Network Phase Handler ⚠️ CRITICAL
**File**: `src/elile/investigation/phases/network.py`
**Test**: `tests/unit/test_network_phase.py`
**Spec**: `docs/tasks/task-5.14-network-phase-handler.md`

**Key Classes**:
- `NetworkPhaseHandler` - Sequential D2/D3 processing
- `NetworkProfile` - Entities, relations, risk connections
- `DiscoveredEntity` - Entity discovered in network
- `EntityRelation` - Relationship between entities
- `RiskConnection` - Risky connection with recommendation
- `RelationType`, `EntityType`, `RiskLevel`, `ConnectionStrength` - Enums
- `NetworkConfig`, `NetworkPhaseResult`

**Dependencies**: Task 5.13

**CRITICAL**: This module is imported by `risk/connection_analyzer.py`. The following must be exported:
```python
from elile.investigation.phases.network import (
    ConnectionStrength,
    DiscoveredEntity,
    EntityRelation,
    EntityType,
    NetworkProfile,
    RelationType,
    RiskConnection,
    RiskLevel,
)
```

---

### Task 5.15: Reconciliation Phase Handler
**File**: `src/elile/investigation/phases/reconciliation.py`
**Test**: `tests/unit/test_reconciliation_phase.py`
**Spec**: `docs/tasks/task-5.15-reconciliation-phase-handler.md`

**Key Classes**:
- `ReconciliationPhaseHandler` - Cross-source conflict resolution
- `ReconciliationProfile` - Consolidated findings
- `Inconsistency`, `InconsistencyType` - Conflict tracking
- `ConflictResolution`, `ResolutionStatus`
- `DeceptionAnalysis`, `DeceptionRiskLevel`
- `ReconciliationConfig`, `ReconciliationPhaseResult`

**Dependencies**: Task 5.14

---

### Task 5.16: Investigation Checkpoint Manager
**File**: `src/elile/investigation/checkpoint.py`
**Test**: `tests/unit/test_checkpoint_manager.py`
**Spec**: `docs/tasks/task-5.16-investigation-resume.md`

**Key Classes**:
- `InvestigationCheckpointManager` - State persistence
- `InvestigationCheckpoint` - Serializable checkpoint
- `TypeStateSnapshot` - Type state serialization
- `CheckpointReason`, `CheckpointStatus` - Enums
- `CheckpointConfig`, `ResumeResult`

**Dependencies**: Task 5.9

---

## After All Tasks Complete

### 1. Run Full Test Suite
```bash
uv run pytest -v
```

### 2. Verify Test Count
The test count should increase significantly. Update `IMPLEMENTATION_STATUS.md` with accurate counts.

### 3. Update IMPLEMENTATION_STATUS.md
- Verify all task statuses are accurate
- Update test counts
- Update phase completion percentages

### 4. Verify Phase 6 Tests Run
```bash
uv run pytest tests/unit/test_risk*.py tests/unit/test_*analyzer*.py tests/unit/test_*detector*.py -v
```

---

## Important Notes

1. **NEVER delete feature branches** - They preserve implementation history
2. **Always tag commits** with `phaseN/task-X.Y` format
3. **Follow existing patterns** from Tasks 5.1-5.7
4. **Use UUIDv7** for all identifiers (`uuid7()`)
5. **Python 3.14** target version
6. **100 character line length** (Black formatting)
7. **Strict type hints** (mypy strict mode)

---

## Git State Reference

**Current Branch**: main
**Latest Commit**: 087ef73 (sync;)
**Feature Branches Exist**: Up to task-4.6 only

---

## Contact

If requirements are unclear, refer to:
- Task specification in `docs/tasks/task-5.X-*.md`
- Architecture docs in `docs/architecture/05-investigation.md`
- Existing implementations in `src/elile/investigation/` for patterns
