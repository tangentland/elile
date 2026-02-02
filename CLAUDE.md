# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Elile is an employee risk assessment platform for organizations with critical roles in government, energy, finance, and other sensitive sectors. The system conducts comprehensive background investigations for pre-employment screening and ongoing employee monitoring at global scale.

### Primary Use Cases

1. **Pre-Employment Screening**: Comprehensive background checks before hiring for critical positions
2. **Ongoing Monitoring**: Continuous screening of current employees for emerging risks

### Key Requirements

- **Locale-Aware Compliance**: All operations require target employee locale specification to enforce jurisdiction-specific compliance rules (FCRA, GDPR, PIPEDA, etc.)
- **Consent Management**: Consent is required and managed through HRIS workflow integration (assume consent granted; HRIS connectors are a planned integration)
- **Audit Trail**: Complete logging of all research activities for compliance and accountability

## Core Architecture

- **Modular Monolith**: Single deployable unit with well-defined module boundaries; simpler operations, easier debugging, future extraction path
- **Multi-Model Integration**: Integrates multiple AI models (Claude, GPT-4, Gemini) for analysis redundancy and specialized tasks
- **LangGraph Orchestration**: Workflow management with conditional routing and state persistence
- **Compliance Engine**: Locale-based rules engine that filters permitted checks by jurisdiction and role type
- **Data Provider Abstraction**: Unified interface for multiple background check data sources

## Data Source Categories

### Biographical / Identity Verification
- Government ID databases, address verification
- Sanctions/PEP lists (OFAC, UN, EU, World-Check)
- Watchlists (Interpol, national law enforcement)

### Professional / Employment
- Employment verification (The Work Number, direct verification)
- Education verification (National Student Clearinghouse, registrars)
- Professional licenses (state boards, FINRA, medical boards)
- LinkedIn (official API with consent)

### Financial
- Credit reports (jurisdiction-dependent - US: FCRA; EU: generally prohibited)
- Bankruptcy and insolvency records
- Liens, judgments, regulatory actions

### Legal / Criminal
- Criminal records (jurisdiction-dependent restrictions)
- Civil litigation records
- Regulatory enforcement actions
- Adverse media monitoring

## Compliance Framework

| Locale | Key Restrictions |
|--------|------------------|
| US | FCRA (7-year lookback, adverse action notices), state ban-the-box laws |
| EU/UK | GDPR Art. 6/9, criminal data only for regulated roles, right to erasure |
| Canada | PIPEDA, RCMP for criminal checks |
| APAC | Highly variable by country |
| LATAM | Brazil LGPD, Argentina strict privacy |

## Planned Integrations

### HRIS Platforms (Consent & Workflow)
- Workday
- SAP SuccessFactors
- Oracle HCM
- ADP
- BambooHR

### Background Check Data Providers
- Sterling, Checkr, HireRight (aggregated providers)
- Direct court/registry access where available

## Development Commands

**IMPORTANT**: Always use `uv run` or the project venv for all Python commands.

### Code Formatting
```bash
uv run black . --line-length 100 --target-version py314
```

### Linting
```bash
uv run ruff check .
```

### Type Checking
```bash
uv run mypy src/elile
```

### Testing
```bash
uv run pytest -v
```

### Test Count
```bash
uv run python -m pytest --collect-only -q 2>&1 | tail -3
```

## Project Structure

```
src/elile/
├── agent/          # LangGraph workflow orchestration
├── config/         # Configuration and settings
├── models/         # AI model adapters (Claude, OpenAI, Gemini)
├── search/         # Search query building and execution
├── risk/           # Risk analysis and scoring
├── compliance/     # Locale-aware compliance engine (planned)
├── providers/      # Data provider integrations (planned)
├── hris/           # HRIS platform connectors (planned)
└── utils/          # Shared utilities and exceptions
```

## Development Guidelines

- Python 3.14 target version
- Line length: 100 characters (Black formatting)
- Strict type hints (mypy strict mode)
- **UUIDv7 for all identifiers**: Time-ordered UUIDs (Python 3.14 native `uuid.uuid7()`) for natural chronological sorting
- All operations must accept locale parameter
- Comprehensive audit logging for all data access
- Rate limiting and retry logic for external APIs

## Permissions
**IMPORTANT - You are allowed to execute any command within the elile project directory**

## Context Management (CRITICAL)

**CODEBASE_INDEX.md is your primary reference** - always consult it first to:
- Understand module structure and class locations
- Find existing implementations before creating new code
- Locate test files and patterns
- Reduce context overhead by reading the index instead of exploring multiple files

**General Workflow Instructions**:
1. Read `CODEBASE_INDEX.md` first when starting work on any task
2. Use the index to identify which specific files to read
3. Only read files directly when you need implementation details not in the index
4. When searching for patterns or conventions, check the index first

**Never explore blindly** - the index documents all modules, classes, and their purposes.

## Session Start

When starting a new session after a handoff:

1. **Read handoff.md** provided by the user (from previous session's stdout)
2. **Read docs/architecture/architecture.md** to understand the architecture
2. **Verify git state** matches handoff (branch, tag)
3. **Read the phase description** from `docs/plans/phase-NN-*.md`
4. **Read the next task** from `docs/tasks/task-X.Y-*.md`
5. **Check dependencies** in `IMPLEMENTATION_STATUS.md`
6. **Create feature branch** and begin implementation

## When to Pause Mid-Task

Only pause within a task if:
- Blocking dependency not yet implemented
- Ambiguous requirements need user clarification
- User explicitly requests a pause
- Critical decision requires user input

**Do not ask** "Should I proceed?" or "Ready for the next task?" - follow the Task Completion Workflow.

## Task Completion Workflow

**IMPORTANT** Operate in Continuous Implementation Mode:
1. **Identify next task**
   - Check handoff.md for next pending task in the current phase
   - Or, check IMPLEMENTATION_STATUS.md for next pending task in the current phase
2. **Prepare documentation update commands** (Context Optimization)
   - At task start, prepare sed commands for documentation updates
   - Cache these commands to execute at task end (avoids re-reading large docs)
   - Example sed patterns to prepare:
     ```bash
     # IMPLEMENTATION_STATUS.md - Update task status
     sed -i '' 's/| X.Y | Task Name | ⏳ Pending/| X.Y | Task Name | ✅ Complete/' IMPLEMENTATION_STATUS.md

     # P0-TASKS-SUMMARY.md - Update task status
     sed -i '' 's/| X.Y | Task Name | ⏳ Pending/| X.Y | Task Name | ✅ Complete/' docs/plans/P0-TASKS-SUMMARY.md

     # phase-NN-*.md - Update task status
     sed -i '' 's/| X.Y | Task Name | P0 | ⏳ Pending/| X.Y | Task Name | P0 | ✅ Complete/' docs/plans/phase-NN-*.md

     # Update counts (use sed arithmetic or prepare full replacement)
     ```
   - Store prepared commands mentally or in notes for execution after implementation
3. **Complete current task** - Implement, test, and document
4. **Update ALL documentation** (execute prepared commands + manual updates):
   - Execute cached sed commands from step 2
   - `CODEBASE_INDEX.md` - Add new module/class documentation (manual)
   - `IMPLEMENTATION_STATUS.md` - Mark task complete, update counts
   - `docs/plans/phase-NN-*.md` - Update task status in phase plan
   - `docs/plans/PN-TASKS-SUMMARY.md` - Update the relevant priority summary (P0, P1, P2, or P3)
   - `docs/plans/MASTER_IMPLEMENTATION_PLAN.md` - Update phase status and counts
5. **Save implementation plan** to `implementation_plans/task-X.Y-description.md`:
   - Overview and requirements
   - Files created/modified
   - Key patterns used
   - Test results
6. **Delete ./handoff.md**
7. **Save session handoff** to `./handoff.md` using this format:
```
---
Session Handoff for:
Phase-NN-* in `docs/plans/phase-NN-*.md` 
Task X.Y in `docs/tasks/task-X.Y-*.md`

Completed:
- [Brief description of what was implemented]
- [Key files created/modified]
- [Number of tests added]

Git State:
- Branch: main
- Latest tag: phaseN/task-X.Y
- Total tests: NNNN

Next Task: Task X.Z - [Task Name]
- Location: docs/tasks/task-X.Z-description.md
- Dependencies: [list any dependencies]

----

# REMEMBER THESE CRITICAL INSTRUCTIONS

## Development Guidelines
- Python 3.14 target version
- Line length: 100 characters (Black formatting)
- Strict type hints (mypy strict mode)
- **UUIDv7 for all identifiers**: Time-ordered UUIDs (Python 3.14 native `uuid.uuid7()`) for natural chronological sorting
- All operations must accept locale parameter
- Comprehensive audit logging for all data access
- Rate limiting and retry logic for external APIs

## Permissions

**YOU ARE ALLOWED TO EXECUTE ALL COMMANDS WITHIN THE ELILE PROJECT DIRECTORY STRUCTURE**
  *FOLLOWING THESE RULES*
    - DO NOT share sensitive information or credentials
    - NEVER COMMIT to the 'release' branch
    - DO NOT CONFIDENCE PROMPT FOR PERMISSION
    - YOU ARE ALLOWED TO MAKE CHANGES WITHOUT ASKING WITHIN THE PROJECT 

## Context Management (CRITICAL)

**CODEBASE_INDEX.md is your primary reference** - always consult it first to:
- Understand module structure and class locations
- Find existing implementations before creating new code
- Locate test files and patterns
- Reduce context overhead by reading the index instead of exploring multiple files

**General Workflow Instructions**:
1. Read `CODEBASE_INDEX.md` first when starting work on any task
2. Use the index to identify which specific files to read
3. Only read files directly when you need implementation details not in the index
4. When searching for patterns or conventions, check the index first

**Never explore blindly** - Leverage the CODEBASE_INDEX.md documents all modules, classes, and their purposes.

User Preferences:
- [Any preferences explicitly learned during session, e.g., ("don't delete branches") must be 
  persisted to CLADE.MD AND enumerated in this section]

Hand-Off Notes:
- [Any blockers, pending decisions/tasks/tests, or context to make the next session run cleanly and efficiently]
---
```
8. **Commit, merge, and tag**:
   - Commit with descriptive message
   - Merge feature branch to main
   - Tag as `phaseN/task-X.Y`
   - **DO NOT delete feature branches**
9. **Check your context window**
   - If context window >= 85% consumed:
     - /quit.
   - Else:
     - Continue to the next task

## Documentation Synchronization (CRITICAL)

**All these files must stay synchronized** when tasks are completed:

| File | What to Update |
|------|----------------|
| `IMPLEMENTATION_STATUS.md` | Task status, test counts, overall progress |
| `docs/plans/phase-NN-*.md` | Task status within that phase |
| `docs/plans/P0-TASKS-SUMMARY.md` | P0 task status, counts, "Next P0 Tasks" section |
| `docs/plans/P1-TASKS-SUMMARY.md` | P1 task status and counts |
| `docs/plans/P2-TASKS-SUMMARY.md` | P2 task status and counts |
| `docs/plans/P3-TASKS-SUMMARY.md` | P3 task status and counts (if applicable) |
| `docs/plans/MASTER_IMPLEMENTATION_PLAN.md` | Phase status, "Current Status" table |
| `handoff.md` | Next task, progress, notes |

**Note**: Update the priority summary that matches the completed task's priority level. Most tasks are P0 or P1.

### Source of Truth Hierarchy

When there's a conflict, trust in this order:
1. **Individual task files** (`docs/tasks/task-X.Y-*.md`) - Priority field is authoritative
2. **IMPLEMENTATION_STATUS.md** - Current implementation status is authoritative
3. **Phase plans** (`docs/plans/phase-NN-*.md`) - Task status within phase
4. **P0-TASKS-SUMMARY.md** - Aggregated P0 tracking (derived from above)
5. **MASTER_IMPLEMENTATION_PLAN.md** - High-level phase status (derived from above)

### P0 Task Tracking

**Milestone 1 = All P0 tasks across Phases 1-12** (76 total)

| Phase | P0 Tasks |
|-------|----------|
| 1-5 | 44 |
| 6 | 7 (Task 6.8 is P1, not P0) |
| 7 | 7 (Tasks 7.8-7.11 are P1) |
| 8 | 4 |
| 9 | 4 |
| 10 | 4 |
| 11 | 2 |
| 12 | 4 |
| **Total** | **76** |

### Common Documentation Errors to Avoid

1. **Priority mismatches**: Always check the task file's Priority field
2. **Stale "Next Task" in handoff.md**: Must match actual next P0 task
3. **Incorrect counts**: Cross-reference P0-TASKS-SUMMARY with phase plans
4. **Task name discrepancies**: Task files are authoritative for names

---

## Planning & Task Documentation

### Document Hierarchy

```
docs/plans/MASTER_IMPLEMENTATION_PLAN.md    <- ROOT: Master implementation plan
├── docs/plans/P0-TASKS-SUMMARY.md          <- Priority summaries by P-level
├── docs/plans/P1-TASKS-SUMMARY.md
├── docs/plans/P2-TASKS-SUMMARY.md
├── docs/plans/phase-01-core-infrastructure.md    <- Phase plans with task lists
├── docs/plans/phase-02-service-configuration.md
├── ...
├── docs/plans/phase-12-production-readiness.md
└── docs/tasks/task-X.Y-description.md      <- Individual task specifications
```

### Root Planning Document

**`docs/plans/MASTER_IMPLEMENTATION_PLAN.md`** is the master implementation plan containing:
- All 12 development phases with priorities and dependencies
- Phase dependency tree (which phases depend on others)
- Priority definitions (P0-P3)
- Development principles and task tracking format

**Always start here** to understand the overall implementation roadmap.

### Priority Task Summaries

Task summaries organized by priority level for quick reference:

| Document | Content |
|----------|---------|
| `docs/plans/P0-TASKS-SUMMARY.md` | Critical path tasks required for basic screening |
| `docs/plans/P1-TASKS-SUMMARY.md` | Essential features for production use |
| `docs/plans/P2-TASKS-SUMMARY.md` | Important but incrementally deliverable |
| `docs/plans/P3-TASKS-SUMMARY.md` | Nice-to-have features for future iterations |

### Phase Plans

Each phase has a dedicated plan document in `docs/plans/phase-NN-description.md`:

| Phase | Document | Status |
|-------|----------|--------|
| 1 | `phase-01-core-infrastructure.md` | Complete |
| 2 | `phase-02-service-configuration.md` | Complete |
| 3 | `phase-03-entity-management.md` | Complete |
| 4 | `phase-04-data-providers.md` | Complete |
| 5 | `phase-05-investigation-engine.md` | Complete |
| 6 | `phase-06-risk-analysis.md` | Complete (11/12, P2 deferred) |
| 7 | `phase-07-screening-service.md` | P0 Complete (7/11) |
| 8-12 | `phase-08-*.md` through `phase-12-*.md` | Not Started |

### Task Definitions

Individual task specifications in `docs/tasks/task-X.Y-description.md`:

- **Phase 5**: `task-5.1` through `task-5.16` (Investigation Engine)
- **Phase 6**: `task-6.1` through `task-6.12` (Risk Analysis)
- **Phase 7**: `task-7.1` through `task-7.11` (Screening Service)
- **Phase 8**: `task-8.1` through `task-8.10` (Reporting System)
- **Phase 9**: `task-9.1` through `task-9.12` (Monitoring & Vigilance)
- **Phase 10**: `task-10.1` through `task-10.10` (Integration Layer)
- **Phase 11**: `task-11.1` through `task-11.11` (User Interfaces)
- **Phase 12**: `task-12.1` through `task-12.19` (Production Readiness)

Each task file includes: overview, dependencies, implementation checklist, key code, testing requirements, and acceptance criteria.

### Task Execution Order

Tasks are executed based on **priority** and **dependencies**:

1. **Priority Order**: P0 (Critical) → P1 (High) → P2 (Medium) → P3 (Low)
2. **Dependency Order**: Within a priority level, tasks are ordered by their dependencies
3. **Phase Order**: Phases must respect the dependency tree in the root planning document

**Example execution flow**:
```
P0 tasks in Phase 5 (all dependencies met)
  → P0 tasks in Phase 6 (depends on Phase 5)
    → P0 tasks in Phase 7 (depends on Phase 6)
      → P1 tasks in Phase 5-7 (after P0 complete)
        → P1 tasks in Phase 8-10 (after Phase 7 P0)
```

**To determine the next task**: Check `IMPLEMENTATION_STATUS.md` for the next pending P0 task with all dependencies satisfied. If all P0 tasks in current phases are complete, move to P1 tasks.

## Architecture Documentation

See `docs/architecture/` for detailed system design, organized by domain:

| Document | Content |
|----------|---------|
| [README.md](docs/architecture/README.md) | Index, dependency diagram, reading order |
| [01-design.md](docs/architecture/01-design.md) | Design principles, "why modular monolith" |
| [02-core-system.md](docs/architecture/02-core-system.md) | Storage, database, API structure, data models |
| [03-screening.md](docs/architecture/03-screening.md) | Service tiers (Standard/Enhanced), degrees (D1-D3), screening flow |
| [04-monitoring.md](docs/architecture/04-monitoring.md) | Vigilance levels (V0-V3), ongoing monitoring, alerts |
| [05-investigation.md](docs/architecture/05-investigation.md) | Screening engine, SAR loop, risk analysis |
| [06-data-sources.md](docs/architecture/06-data-sources.md) | Core (T1) and Premium (T2) provider categories |
| [07-compliance.md](docs/architecture/07-compliance.md) | Compliance engine, security, data retention |
| [08-reporting.md](docs/architecture/08-reporting.md) | Per-persona report types (6 report types) |
| [09-integration.md](docs/architecture/09-integration.md) | API endpoints, HRIS gateway, webhooks |
| [10-platform.md](docs/architecture/10-platform.md) | Module structure, deployment, scaling |
| [11-interfaces.md](docs/architecture/11-interfaces.md) | User interfaces (5 portals/dashboards) |
| [12-roadmap.md](docs/architecture/12-roadmap.md) | Open questions, implementation phases |

