---
status: pending
priority: p4
issue_id: "473"
tags: [harness, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-09-28
owner_decision: "List a landed todo's earlier blocked worktrees in the wrap-up; cleanup does not remove them (2026-09-28)"
---

# Todo sweep v2 Part B: non-blocking findings from PR #868 round 1

## Problem

Round 1 of PR #868 found nothing blocking. It fixed four findings in the PR (a `record-triage --root`
path strip, resume finishing a staged repair, reopen order, rebase before the pre-push check).
These three were left for later.

## Findings

1. **A reopened todo that later lands drops its blocked worktree from the wrap-up.**
   `recorded_worktrees` skips archived todos (`scripts/todos/state.py`), so the
   blocked attempt's worktree under `.claude/worktrees/` is orphaned: a leaked directory
   and branch, not lost work.
2. **A todo reopened after a Land step 7 rebase conflict can't rename its branch again.**
   It already has its `<type>/<id>-<slug>` name, and the old worktree still has that
   branch checked out, so step 5's `git branch -m` fails on the redo. The runbook doesn't
   say what to do.
3. **`slot_env.py --worktree` checks only `is_dir()`.** `--worktree .` from `WT/backend`
   gives `PYTHONPATH=WT/backend/backend/packages/…` and a silent `.env` fallback.
   Checking that the path is a repo top level (`git rev-parse --show-toplevel`) would catch it.

4. **`record-triage --root` matches only the resolved root** (PR #868 round 2). If a
   triager reports `/tmp/x/b.py` for root `/private/tmp/x`, that path lands in
   `dropped_files`: it is visible there, but it loses its lane. Also matching the unresolved
   form would close this. The risk is low, because `triage-args` emits the resolved path.

## Acceptance Criteria

- [ ] The wrap-up lists a landed todo's earlier blocked worktrees, or cleanup removes them; with a test.
- [ ] The runbook (or the engine) handles a reopened todo whose branch is already renamed and checked out.
- [ ] `slot_env.py --worktree` refuses a path that is not a worktree's top level, with a test.
- [ ] `record-triage --root` keeps a path reported under either form of a symlinked root, with a test.

## Work Log

### 2026-09-28 - Filed from PR #868 round 1
