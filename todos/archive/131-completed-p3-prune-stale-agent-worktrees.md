---
name: prune-stale-agent-worktrees
status: completed
priority: p3
created: 2026-05-30
tags: [harness, worktrees, hygiene]
source_review: "docs/audits/2026-05-30-harness.md"
source_finding: "F7"
---

# Prune stale locked agent worktrees

## Problem

`git worktree list` shows two `locked` agent worktrees:

- `.claude/worktrees/agent-ad69486e286e62700` (branch `fix/diagnosis-service-auth`)
  — a full repo checkout that pollutes `find`/tree output across the repo.
- `.claude/worktrees/agent-aff2d3d2efe25dff5` (branch `fix/forum-search-filters`).

Both appear abandoned.

## Acceptance criteria

- [x] Confirm each worktree's branch is merged or its work is captured elsewhere
      (do NOT delete unmerged work — inspect first).
- [x] Unlock + remove the abandoned worktrees:
      `git worktree remove --force .claude/worktrees/agent-<id>` (after verifying).
- [x] `git worktree list` shows only the main checkout (plus any genuinely active
      worktree).
- [x] `.claude/worktrees/` is confirmed git-ignored (it is) so this does not
      recur in tracked state.

## Notes

Inspect before removing — these may hold uncommitted fix work. Verify with
`git -C <worktree> status` and `git log <branch>` first.

## Work Log

### 2026-05-31 - Started by completing-todos skill (run 2026-05-31-1432)

- Picked up by automated workflow.
- Inspected `fix/diagnosis-service-auth` (8af95a8): no uncommitted changes; top commits
  are `fix(web): remove dead getAuthHeaders in diagnosisService` (merged as PR #306) and
  `fix diagnosisService.test.ts` (merged as PR #315). Branch fully captured in main.
- Inspected `fix/forum-search-filters` (c85164b): no uncommitted changes; top commit
  `fix(forum): searchForum — forward page params, derive has_next` merged as PR #305.
  Branch fully captured in main.
- Ran `git worktree unlock` + `git worktree remove --force` on both. No errors.
- `git worktree list` output: only main checkout at `59f2056 [chore/todo-housekeeping]`.
- `.claude/worktrees/` confirmed ignored via `.gitignore:176` (`.claude/*` pattern).
- No source files changed — operational task only; code review skipped.

### 2026-05-31 - Completed by completing-todos skill (run 2026-05-31-1432)

- Verification: all 4 acceptance criteria passed.
- Review: 0 findings — operational task, no source code changed.
