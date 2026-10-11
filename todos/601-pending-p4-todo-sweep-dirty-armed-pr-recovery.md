---
status: pending
priority: p4
issue_id: "601"
tags: [todo-sweep, tooling, docs]
dependencies: []
---

# `completing-todos` has no recovery step for an armed PR that goes conflicting

## Problem

An armed PR whose checks are all green can sit `OPEN` indefinitely because a peer PR merged first and left
a conflict. GitHub reports that only as `mergeStateStatus: DIRTY` / `mergeable: CONFLICTING`, which a
check-rollup poll never reads. It happened twice on 2026-10-11:

- PR #1035 (run 2026-10-11-1448). `docs/LEARNINGS.md` 2026-10-11 "An armed PR stalled on a conflict no check
  reported".
- PR #1040 (run 2026-10-11-1929). The only conflict was `.secrets.baseline` `generated_at`, after #1035 merged.

Both were recovered by hand the same way. `.claude/skills/completing-todos/SKILL.md` does not describe that
recovery, and its Merge confirmation section only covers a wedged CI job.

## Acceptance Criteria

- [ ] The Merge confirmation section documents the DIRTY recovery, run with the sandbox off:
      `ensure-worktree`, then `git -C $WT merge origin/main` (a merge commit, never a rebase plus force-push),
      resolve the conflicts, and re-run the group's gates on the merged tree. Then `git add` the resolved
      paths, `state.py annotate $RUN G --field tree_id=$(git -C $WT write-tree)`, commit, `ensure-worktree`
      again and push. It also says to confirm auto-merge is still armed. It says which conflicts are
      mechanical (`todos/`, append-only docs, `.secrets.baseline` line numbers and `generated_at`) and that
      any other conflict stops the group for the owner.
- [ ] The skill's guidance for waiting on an armed PR says to read `mergeStateStatus` and treat `DIRTY` as a
      stop, not only failed checks.

## Work Log
