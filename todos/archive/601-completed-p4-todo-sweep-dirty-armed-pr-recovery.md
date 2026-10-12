---
status: completed
priority: p4
issue_id: "601"
tags: [todo-sweep, tooling, docs]
dependencies: []
triage: ready
triaged: 2026-10-11
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

- [x] The Merge confirmation section documents the DIRTY recovery, run with the sandbox off:
      `ensure-worktree`, then `git -C $WT merge origin/main` (a merge commit, never a rebase plus force-push),
      resolve the conflicts, and re-run the group's gates on the merged tree. Then `git add` the resolved
      paths, `state.py annotate $RUN G --field tree_id=$(git -C $WT write-tree)`, commit, `ensure-worktree`
      again and push. It also says to confirm auto-merge is still armed. It says which conflicts are
      mechanical (`todos/`, append-only docs, `.secrets.baseline` line numbers and `generated_at`) and that
      any other conflict stops the group for the owner.
- [x] The skill's guidance for waiting on an armed PR says to read `mergeStateStatus` and treat `DIRTY` as a
      stop, not only failed checks.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- `.claude/skills/completing-todos/SKILL.md` Merge confirmation gains "Waiting on an armed PR": a poll reads
  `mergeStateStatus`/`mergeable` with the checks and treats `DIRTY` as a stop, since a conflict is not a check.
- It also gains the `DIRTY` recovery (sandbox off): `ensure-worktree`, fetch, `merge origin/main` (merge commit,
  no force-push), mechanical conflicts only (`todos/`, append-only docs, `.secrets.baseline` `generated_at` and
  line numbers; anything else aborts and blocks the group), re-run gates, `git add`, `annotate tree_id`, commit,
  `ensure-worktree`, push, confirm auto-merge is armed. The Sandbox-off steps list now names this merge.
- `scripts/todos/test_state_flow.py` `runbook_tests` asserts both paragraphs and the recovery's step order.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `sed -n '/^## Merge confirmation/,/^## Wrap-up/p' .claude/skills/completing-todos/SKILL.md` — evidence `.sweep-evidence/g15/601-ac0.txt` (not committed), last lines:

  ```text
  7. `ensure-worktree` again, then `/usr/bin/git -C $WT push origin <branch>` (no `-u`, no `--force`).
  8. Confirm auto-merge is still armed (`gh pr view <n> --repo $GH_REPO --json autoMergeRequest,mergeStateStatus`)
     and arm it again if not (see **Arming auto-merge**). Then go back to waiting.

  ## Wrap-up
  ```

- AC 2: `grep -n -A7 'Waiting on an armed PR' .claude/skills/completing-todos/SKILL.md` — evidence `.sweep-evidence/g15/601-ac1.txt` (not committed), last lines:

  ```text
  362-armed PR stalled on a conflict no check reported"). So a poll or loop that waits on an armed PR reads
  363-`gh pr view <n> --repo $GH_REPO --json state,mergeStateStatus,mergeable,statusCheckRollup`, not the checks
  364-alone, and stops on any of: `MERGED`, `CLOSED`, a failed required check, or `mergeStateStatus` `DIRTY`.
  365-Treat `DIRTY` as a stop, never as "still waiting", and recover it as below.
  366-
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
