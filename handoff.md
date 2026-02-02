---
Session Handoff for:
Phase-04-data-providers in `docs/plans/phase-04-data-providers.md`
Task 4.14 in `docs/tasks/task-4.14-osint-aggregator.md`

Completed:
- Implemented OSINT Aggregator Provider (Task 4.14)
- Created OSINTSource enum with 50+ source types
- Implemented deduplication logic using SequenceMatcher similarity
- Implemented entity extraction with regex patterns (emails, phones, URLs, social handles)
- Implemented relationship extraction for employment, education, board positions
- Created OSINTProvider with gather_intelligence and execute_check methods
- 109 new tests for OSINT provider
- All tests passing (4026 total)

Git State:
- Branch: main
- Latest tag: phase4/task-4.14
- Total tests: 4026

Next Task: Task 4.15 - Provider Circuit Breaker
- Location: docs/tasks/task-4.15-circuit-breaker.md
- Dependencies: 4.1, 4.6

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
- P1 tasks Phase 4: 4/6 complete (4.11-4.14 done, 4.15-4.16 remaining)
- Task 4.15 (Provider Circuit Breaker) may overlap with existing CircuitBreaker in providers/health.py - review scope
- Task 4.16 (LLM Synthesis Provider) depends on Task 5.10 (Finding Extractor) which is complete
---
