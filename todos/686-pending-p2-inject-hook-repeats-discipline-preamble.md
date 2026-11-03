---
status: pending
priority: p2
issue_id: "686"
tags: [harness, hooks, context]
dependencies: []
triage: ready
triaged: 2026-11-03
owner_decision: "Option 2 only: skip the discipline preamble only for paths outside the repo; every repo edit keeps the full preamble (2026-11-03)"
---

# inject-patterns.sh repeats the 4.4 KB discipline preamble on every edit, even outside the repo

## Problem

The PreToolUse injection hook prepends `docs/rules/_discipline.md` (4,426 bytes) to **every** Edit/Write, and the code says "Never deduped". The preamble also goes to files **outside the repo**: memory files, side-session notes, scratchpad. In a single session, around 15 edits added about 65 KB of identical text to the context. Every agent pays this, and subagents and todo workers pay it on every edit too.

## Findings

- `.claude/hooks/inject-patterns.sh`: the comment `(2) Always-on discipline floor, read from an editable data file. Never deduped.` is followed by `cat "$RULES_DIR/_discipline.md"`. The domain-rule tier and the trigger tier are already deduped per session through `session_id`. The floor is not.
- **Outside-repo paths.** `REL="${FILE_PATH#"$PROJECT_ROOT"/}"` leaves an outside path unchanged, so no domain matches, but the floor is still injected. Observed 2026-11-03 (username-leak session, PR #1252):
  - full preamble on `~/.claude/projects/.../memory/MEMORY.md`
  - full preamble on a memory file
  - full preamble on two files in `~/Library/Application Support/Claude/side-session-notes/...`
- "Never deduped" was a deliberate choice: the floor is meant to bind every edit. Why it was chosen is not recorded next to the code.

## Proposed Solutions

### Option 1: skip outside the repo, and send the full floor once per session (recommended)

- **Implementation:**
  - Exit 0 when `FILE_PATH` is absolute and not under `PROJECT_ROOT`.
  - Inject the full floor on a session's first edit only.
  - After that, inject a one-line reminder such as `DISCIPLINE: see the preamble earlier in this session (docs/rules/_discipline.md)`, using the same `session_id` dedup the rule tier uses.
- **Pros:** about 4.3 KB saved on every edit after the first; nothing injected for non-repo files.
- **Cons:** after context compaction the first copy may be summarised away. Mitigation: dedup on a marker that expires, or re-send the full floor every N edits.
- **Effort:** 1–2 hours, including `test-inject-patterns.sh` cases.
- **Risk:** low. The rule and trigger tiers are unchanged.

### Option 2: only skip paths outside the repo

- **Pros:** uncontroversial; keeps "every edit" semantics inside the repo.
- **Cons:** keeps about 4.4 KB per repo edit.
- **Effort:** 30 min.

## Recommended Action

1. **Owner call:** Option 1 or Option 2. Option 2 alone is safe to ship without asking.
2. Add the outside-root early exit. Mind the worktree case: `PROJECT_ROOT` is the worktree, and worktree paths are inside it.
3. If Option 1 is chosen, dedup the floor on `session_id` the same way the domain tier does, and emit the one-line pointer after the first copy.
4. Add tests to `.claude/hooks/test-inject-patterns.sh`:
   - an outside path → no output
   - a second repo edit in the same session → pointer only
   - a new session → full floor

## Technical Details

- Hook: `.claude/hooks/inject-patterns.sh`. Floor: `docs/rules/_discipline.md`.
- Existing dedup: the comment `session_id drives per-session dedup of the domain-rule tier`.
- `.claude/` changes reach only NEW worktrees (root CLAUDE.md, Harness Automation).

## Acceptance Criteria

- [ ] An Edit/Write to a path outside the project root produces no injected context. A hook test covers it.
- [ ] If Option 1 is chosen: the second and later repo edits in one session carry at most a one-line pointer instead of the 4.4 KB floor. A hook test covers it.
- [ ] `bash .claude/hooks/test-inject-patterns.sh` passes.

## Work Log

### 2026-11-03 - Filed

- Found while fixing the username email leak (PR #1252). The owner asked for todos for repeated agent friction: "if every agent we call has to do some kind of run around every single time then that is something that should be fixed."
