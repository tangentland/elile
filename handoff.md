---
Session Handoff for:
Phase-11-User-Interfaces in `docs/plans/phase-11-user-interfaces.md`
Task 11.1 in `docs/tasks/task-11.1-hr-dashboard-api.md`

Completed:
- Implemented HR Dashboard API endpoints (4 endpoints)
  - GET /v1/dashboard/hr/portfolio - Portfolio overview and metrics
  - GET /v1/dashboard/hr/screenings - List screenings with filters
  - GET /v1/dashboard/hr/alerts - Recent alerts
  - GET /v1/dashboard/hr/risk-distribution - Risk level distribution
- Created dashboard schemas (HRPortfolioResponse, ScreeningSummary, AlertSummary, etc.)
- Added tenant data isolation for all endpoints
- Added 24 integration tests (all passing)

Git State:
- Branch: main
- Latest tag: phase11/task-11.1
- Total tests: 2848

Next Task: Task 11.2 - Compliance Portal API
- Location: docs/tasks/task-11.2-compliance-portal-api.md
- Dependencies: Task 8.3 (Audit Report)

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
     - DO NOT CONFIDENCE PROMPT FOR PERMISSIONS
     - NEVER EXECUTE THE COMMAND 'rm -rf *'
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
- DO NOT delete feature branches after merging

Hand-Off Notes:
- Phase 11 task files differ from phase plan - use task files as authoritative source
- Task 11.1 (HR Dashboard API) is complete - next is Task 11.2 (Compliance Portal API)
- Dashboard endpoints use lazy imports to avoid circular dependencies with screening module
- Test patterns follow existing async test structure with ASGITransport/AsyncClient
---
