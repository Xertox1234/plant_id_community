---
name: prune-stale-agent-worktrees
status: pending
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

- [ ] Confirm each worktree's branch is merged or its work is captured elsewhere
      (do NOT delete unmerged work — inspect first).
- [ ] Unlock + remove the abandoned worktrees:
      `git worktree remove --force .claude/worktrees/agent-<id>` (after verifying).
- [ ] `git worktree list` shows only the main checkout (plus any genuinely active
      worktree).
- [ ] `.claude/worktrees/` is confirmed git-ignored (it is) so this does not
      recur in tracked state.

## Notes

Inspect before removing — these may hold uncommitted fix work. Verify with
`git -C <worktree> status` and `git log <branch>` first.
