---
status: completed
priority: p3
issue_id: "512"
tags: [tooling, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-10-01
owner_decision: "Finding 3: _check_worktree tolerates a diff from the recorded tree when every changed line differs only by trailing whitespace or by blank lines at end of file (2026-10-01)"
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

- [x] Findings 1, 2, 3 and 5 are fixed in code or in the `completing-todos` runbook, each with a test or a
      dry-run note in the Work Log.
- [x] Finding 4 is investigated; the Work Log records the timeout value and either a change or why it stays.
- [x] Finding 6 is a one-line runbook edit.

## Work Log

- 2026-09-30: Filed from the main session of todo-sweep run 2026-10-01-0121.

### 2026-10-01 - Implemented by the todo sweep (run 2026-10-01-1858)

- Findings 1, 5, 6 (runbook, `completing-todos/SKILL.md`): a new **Arming auto-merge** rule, used by both
  arming sites (triage PR step 2, Stage C step 2), is `gh pr merge <n> --repo $GH_REPO --auto --squash
  --delete-branch` from REPO (`GH_REPO` from `gh repo view`), so gh leaves local git alone. Merge confirmation
  gains the wedged-CI recovery (`ensure-worktree` → `commit --allow-empty` → `ensure-worktree` → push, then
  check auto-merge is still armed), and the Sandbox list names that commit. Stage B step 1 says waves start at 0.
  Dry run: new `runbook_tests()` in `test_state_flow.py` checks every `gh pr merge` line carries `--repo`, the
  wave-0 sentence, and the recovery; a real-git check shows an empty commit on top of Land leaves
  `ensure-worktree` passing.
- Finding 2 (`land.py`): `_fence_quote` strips trailing whitespace from each quoted tail line and emits a blank
  one empty, not as the two-space indent. `test_land.py` quotes a vitest-shaped tail with spaces-only lines and
  asserts no line ends in whitespace after flip-acs or archive; both halves were mutation-checked.
- Finding 3 (`state.py`, owner decision 2026-10-01): `_land_only_diff` also accepts a changed path whose
  contents differ only by trailing whitespace or blank lines (or the final newline) at end of file, compared
  blob to blob. A mid-file blank line, whitespace inside a line, an added/deleted/re-moded file, a binary or a
  symlink still refuses. 15 real-git cases in `test_state_flow.py` (one nested three directories deep, as on
  PR #907); the mode and binary guards were mutation-checked.
- Finding 4 (kimi gate): `scripts/kimi-precommit.sh` ran `timeout 150`. With `--verify deterministic`, the
  engine makes one draft call: 3 attempts × 90 s client timeout + 3 s backoff = 273 s, under its own 330 s
  budget. So 150 s cut off any review whose first attempt timed out before its retry could finish. Raised to
  300 s, and Stage D step 6 now gives the commit `timeout: 600000`. That this caused the 7 timeouts is a
  hypothesis, not measured: kimi-review was not run to time it, because that is spend nobody asked for. The
  Claude Code PreToolUse `kimi-review.sh` hook has its own 180 s timeout, but it never fires on Land's
  `/usr/bin/git` commit (its regex wants a bare `git`), so it was left alone.

### 2026-10-01 - Verified by the todo sweep (run 2026-10-01-1858)

- AC 1: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_292f584f-de7-1/scripts/todos/test_land.py && python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_292f584f-de7-1/scripts/todos/test_state_flow.py` — evidence `.sweep-evidence/g1/512-ac0.txt`, last lines:

  ```text
    PASS  512: Stage B step 1 says waves start at 0
    PASS  512: ... and wave 0 is a fresh run's first wave
    PASS  512: Merge confirmation gives the wedged-CI recovery (an empty commit between ensure-worktree runs)

  All checks passed.
  ```

- AC 2: `bash -n /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_292f584f-de7-1/scripts/kimi-precommit.sh && grep -n "GATE_TIMEOUT\|timeout 150" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_292f584f-de7-1/scripts/kimi-precommit.sh && grep -n "timeout=90.0\|retries=2, base_delay\|return 330$" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_292f584f-de7-1/scripts/kimi-review && grep -n -A8 "Finding 4 (kimi gate)" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_292f584f-de7-1/todos/512-pending-p3-todo-sweep-land-friction-run-2026-10-01.md` — evidence `.sweep-evidence/g1/512-ac1.txt`, last lines:

  ```text
  83-  budget. So 150 s cut off any review whose first attempt timed out before its retry could finish. Raised to
  84-  300 s, and Stage D step 6 now gives the commit `timeout: 600000`. That this caused the 7 timeouts is a
  85-  hypothesis, not measured: kimi-review was not run to time it, because that is spend nobody asked for. The
  86-  Claude Code PreToolUse `kimi-review.sh` hook has its own 180 s timeout, but it never fires on Land's
  87-  `/usr/bin/git` commit (its regex wants a bare `git`), so it was left alone.
  ```

- AC 3: `/usr/bin/git -C /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_292f584f-de7-1 diff -U0 7a58aaf749d0bb7159eecf4fca3fe3348f995c78 -- .claude/skills/completing-todos/SKILL.md | grep -B1 "Waves start at 0"; python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_292f584f-de7-1/scripts/todos/test_state_flow.py | grep "waves start at 0\|wave 0 is a fresh\|All checks passed\|FAILED"` — evidence `.sweep-evidence/g1/512-ac2.txt`, last lines:

  ```text
  @@ -111,0 +119 @@ With `--limit N`, execute only the first ⌈N / workers⌉ waves and list the de
  +   Waves start at 0: a fresh run's first call is `--wave 0`.
    PASS  512: Stage B step 1 says waves start at 0
    PASS  512: ... and wave 0 is a fresh run's first wave
  All checks passed.
  ```

### 2026-10-01 - Completed by the todo sweep (run 2026-10-01-1858)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
