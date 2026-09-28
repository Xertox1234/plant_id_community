---
status: completed
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

- [x] The wrap-up lists a landed todo's earlier blocked worktrees, or cleanup removes them; with a test.
- [x] The runbook (or the engine) handles a reopened todo whose branch is already renamed and checked out.
- [x] `slot_env.py --worktree` refuses a path that is not a worktree's top level, with a test.
- [x] `record-triage --root` keeps a path reported under either form of a symlinked root, with a test.

## Work Log

### 2026-09-28 - Filed from PR #868 round 1

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- Owner decision applied: `state.recorded_worktrees` now lists an archived todo's earlier blocked attempts
  (its own landed worktree was removed at cleanup, so it is left out); cleanup still removes nothing else.
- Runbook, Land step 5: a reopened todo whose `<type>/<id>-<slug>` is already taken (checked out in the
  earlier attempt's worktree) skips the rename if HEAD already has it, else renames to `…-<n>`; nothing is
  deleted or force-moved.
- `slot_env.py --worktree` refuses a path that is not a worktree's top level (`git rev-parse --show-toplevel`),
  naming the top level, and refuses a directory in no checkout.
- `record-triage --root` matches a reported path as given and resolved against the resolved root, so a
  `/tmp/...` path under a `/private/tmp` root (or the reverse, via a symlink) keeps its lane. Tests for all
  four in `test_state_flow.py`, `test_slot_env.py` and `test_state.py`.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_state_flow.py` — evidence `.sweep-evidence/g8/473-ac0.txt`, last lines:

  ```text
    PASS  482: finish still removes the run file when every todo is terminal and none is held
    PASS  473 AC1: the wrap-up lists a landed todo's earlier blocked worktree (not its removed own one)
    PASS  477 AC4: the rename message prints the source and destination unquoted

  All checks passed.
  ```

- AC 2: `grep -n -A7 "A reopened todo (todo 473)" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/.claude/skills/completing-todos/SKILL.md` — evidence `.sweep-evidence/g8/473-ac1.txt`, last lines:

  ```text
  141-   --abbrev-ref HEAD` already prints the name, skip the rename. Otherwise, when
  142-   `/usr/bin/git -C REPO rev-parse --verify --quiet refs/heads/<type>/<id>-<slug>` succeeds, rename to
  143-   `<type>/<id>-<slug>-<n>` instead, with `<n>` = the todo's attempts so far + 1 (the first free one), and name
  144-   the old branch and its worktree in the wrap-up.
  145-6. Commit the index only (never `-a`): `/usr/bin/git -C $WT commit -m "<type>(<scope>): <summary> (todo <id>)" -m "<2–4 bullets from the WORKER summary>" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
  ```

- AC 3: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_slot_env.py` — evidence `.sweep-evidence/g8/473-ac2.txt`, last lines:

  ```text
    PASS  479: a worktree without web/.env gets the main checkout's web values, comments stripped as Vite does
    PASS  479: a worktree with its own web/.env gets nothing from the main checkout (Vite reads its own)
    PASS  479: a value already in the environment wins

  All checks passed.
  ```

- AC 4: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_state.py` — evidence `.sweep-evidence/g8/473-ac3.txt`, last lines:

  ```text
    PASS  474 AC3: apply-triage refuses a stranded todo whose old and new paths both exist, naming both
    PASS  474: the refusal comes before anything is written (the other todo is untouched)
    PASS  474 AC4: a rerun of apply-triage on a later day adds no second 'Returned to pending' entry

  All checks passed.
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
