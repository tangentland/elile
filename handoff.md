---
Session Handoff for:
Phase 4 in `docs/plans/phase-04-data-providers.md`
Task 4.11 in `docs/tasks/task-4.11-sanctions-provider.md`

Completed:
- Implemented SanctionsProvider for OFAC, UN, EU, PEP, Interpol screening
- Created NameMatcher with Jaro-Winkler, phonetic, and token-based fuzzy matching
- Built SanctionsUpdateScheduler for real-time list updates
- Comprehensive type definitions for sanctions lists and match results
- 175 new unit tests (types, matcher, provider, scheduler)

Key Files Created/Modified:
- `src/elile/providers/sanctions/__init__.py` - Module exports
- `src/elile/providers/sanctions/types.py` - SanctionsList, SanctionedEntity, SanctionsMatch
- `src/elile/providers/sanctions/matcher.py` - NameMatcher with fuzzy algorithms
- `src/elile/providers/sanctions/provider.py` - SanctionsProvider class
- `src/elile/providers/sanctions/scheduler.py` - SanctionsUpdateScheduler
- `tests/unit/providers/sanctions/` - 4 test files with 175 tests

Git State:
- Branch: feature/task-4.11-sanctions-provider
- Latest tag: phase4/task-4.11 (after merge)
- Total tests: 3680

Next Task: Task 4.12 - Education Verification Provider
- Location: docs/tasks/task-4.12-education-provider.md (if exists) or check P1-TASKS-SUMMARY.md
- Dependencies: Task 4.4, 4.7
- Priority: P1

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
- Task 4.11 Sanctions Provider is complete
- Phase 4 P1 tasks: 1/6 Complete
- Total P1 tasks: 21/57 Complete
- Next P1 task: Task 4.12 Education Verification Provider
- Sanctions provider uses sample data; production would integrate actual OFAC/UN/EU APIs
---
