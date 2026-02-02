---
Session Handoff for:
Phase-12-Production-Readiness in `docs/plans/phase-12-production-readiness.md`
Task 12.2 in `docs/tasks/task-12.2-database-optimization.md`

Completed:
- Task 12.1: Performance Profiling - OpenTelemetry tracing and Prometheus metrics
- Created `src/elile/observability/` module with tracing.py and metrics.py
- Added ObservabilityMiddleware for HTTP request metrics
- Added `/metrics` endpoint for Prometheus scraping
- 89 new tests added

Git State:
- Branch: main
- Latest tag: phase12/task-12.1
- Total tests: 2963

Next Task: Task 12.2 - Database Optimization
- Location: docs/tasks/task-12.2-database-optimization.md
- Dependencies: Task 12.1 (complete)

---

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
- DO NOT delete feature branches

Hand-Off Notes:
- Phase 12 P0 progress: 1/4 tasks complete (25%)
- Next task (12.2 Database Optimization) depends on 12.1 which is now complete
- New observability module available at `src/elile/observability/`
- Metrics endpoint at `/metrics` for Prometheus scraping
---
