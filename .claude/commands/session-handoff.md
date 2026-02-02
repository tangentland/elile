# Session Handoff

Prepare a session handoff document for context compaction and continuation.

## Instructions

When this skill is invoked:

1. **Create or update handoff.md** with the current session state:
   ```
   ---
   Session Handoff for:
   Phase-NN-* in `docs/plans/phase-NN-*.md`
   Task X.Y in `docs/tasks/task-X.Y-*.md`

   Completed:
   - [What was implemented this session]
   - [Key files created/modified]
   - [Tests added]

   Git State:
   - Branch: [current branch]
   - Latest tag: [latest tag]
   - Total tests: [test count]

   Next Task: Task X.Z - [Name]
   - Location: docs/tasks/task-X.Z-*.md
   - Dependencies: [list]
   - Description: [brief description]

   ---
   # REMEMBER THESE CRITICAL INSTRUCTIONS
   [Include full instructions from CLAUDE.md]
   ---
   ```

2. **Output the compact command** for the user to run:
   ```
   Ready for compaction. Run:
   /compact read handoff.md and continue with the next task
   ```

## Usage

Before compacting:
```
/session-handoff
```

Then compact:
```
/compact read handoff.md and continue
```

## Notes

- Use this when context is getting large but you want to preserve session state
- The handoff document captures everything needed to resume work
- Always include the critical instructions section for continuity
