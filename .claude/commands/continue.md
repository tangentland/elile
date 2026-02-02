# Continue Session

Resume work from a previous session by reading the handoff document and continuing with the next task.

## Instructions

1. **Read the handoff document** at `./handoff.md` to understand:
   - What was completed in the previous session
   - Current git state (branch, tag)
   - Next task to implement
   - Any blockers or pending decisions

2. **Read the task specification** at the path indicated in handoff.md (typically `docs/tasks/task-X.Y-*.md`)

3. **Verify git state** matches what's documented in handoff.md:
   - Check current branch
   - Verify latest tag exists

4. **Read CODEBASE_INDEX.md** to understand module structure before making changes

5. **Continue implementation** following the Task Completion Workflow in CLAUDE.md:
   - Prepare documentation update commands
   - Implement the task
   - Run tests
   - Update all documentation
   - Commit, merge, and tag
   - Create new handoff.md for next session

## Usage

After compaction:
```
/compact then run /continue
```

Or directly:
```
/continue
```

## Notes

- This skill is designed to work seamlessly after `/compact`
- If handoff.md doesn't exist, check IMPLEMENTATION_STATUS.md for the next task
- Always follow the critical instructions in CLAUDE.md
