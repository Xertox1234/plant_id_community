---
status: pending
priority: p3
issue_id: "512"
tags: [tooling, todo-sweep]
dependencies: []
---

# Todo sweep: Land and merge friction seen in run 2026-10-01-0121

## Problem

Run 2026-10-01-0121 merged 10 todos (#904–#913), but Land and merge needed hand fixes. Each issue
below would recur on any run. They are listed in the order they cost time.

## Findings

1. **`gh pr merge --auto --delete-branch` can delete a sweep worktree's files.** When a PR's checks
   have already passed, `--auto` merges at once. `gh` then removes the local branch, and because a sweep
   worktree has that branch checked out, it tries to remove the worktree too. The sandbox stopped it
   part-way: in `.claude/worktrees/wf_010041ec-ccf-1` (PR #904), 358 tracked files were deleted
   and `.git/worktrees/<name>` was left behind. That worktree now needs `git worktree remove --force`.
   Workaround used for the rest of the run: arm from outside the checkout with
   `gh pr merge <n> --repo <owner/repo> --auto --squash --delete-branch`, so `gh` never touches local
   git. Fix: put that form in `completing-todos` Stage C step 2 (and in the triage PR step).
2. **`land.py` quotes evidence tails with trailing whitespace, so the Land commit fails.** The quoted
   vitest output keeps blank lines that are only spaces. `trailing-whitespace` rewrites the archived
   todo, the commit aborts, and Land has to re-add and recommit. Fix: strip trailing whitespace from
   each quoted evidence line in `land.py` (flip-acs/archive), with a test.
3. **A fixer hook that changes a verified file trips `ensure-worktree`'s lost-work check.**
   On PR #907, `end-of-file-fixer` removed one trailing blank line from
   `web/docs/patterns/react-typescript.md` during the Land commit. `_land_only_diff` allows only
   `todos/`, `docs/reviews/` and `.secrets.baseline`, so the next `ensure-worktree` refused
   ("lost its staged work"). It was cleared by re-recording `tree_id` after showing the diff was one blank
   line, the way the runbook does after a clean rebase. Fix: either the worker (or the verifier, before
   it records `tree_id`) runs the pre-commit fixers on the staged files, or `_check_worktree` accepts a
   diff that only removes trailing whitespace or blank lines at EOF.
4. **The kimi gate timed out on 7 of the 10 Land commits** (`kimi-review timed out; skipping gate`),
   so most of the run is recorded as `kimi: skipped`. Diffs were 3–14 files. Check whether the timeout is
   too short for a sweep-sized diff, or whether the gate is slow under parallel load.
5. **A wedged GitHub Actions job blocks auto-merge with no runbook step.** On PR #906, Web CI run
   36803499395 stayed `in_progress` for over 80 minutes. `gh run cancel` said it was completed,
   `force-cancel` said it was not in progress, and `rerun` said it was already running. An empty commit
   pushed after `ensure-worktree` (same tree, so the reviews still hold) started a fresh run. Fix: add this
   recovery to the runbook's Merge confirmation section.
6. **The runbook says "wave W" without saying waves are 0-indexed.** `execute-args --wave 1` on a fresh
   run fails with "wave 0 has not finished executing". Say "waves start at 0" in Stage B step 1.

## Acceptance Criteria

- [ ] Findings 1, 2, 3 and 5 are fixed in code or in the `completing-todos` runbook, each with a test or a
      dry-run note in the Work Log.
- [ ] Finding 4 is investigated; the Work Log records the timeout value and either a change or why it stays.
- [ ] Finding 6 is a one-line runbook edit.

## Work Log

- 2026-09-30: Filed from the main session of todo-sweep run 2026-10-01-0121.
