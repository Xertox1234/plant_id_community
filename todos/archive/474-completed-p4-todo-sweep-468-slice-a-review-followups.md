---
status: completed
priority: p4
issue_id: "474"
tags: [harness, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-09-28
owner_decision: "AC1/AC2: keep the brief/plan alone, and refuse only the cycle's todos (2026-09-28)"
---

# Todo sweep: non-blocking findings from PR #869 round 1 (todo 468 slice A)

## Problem

Round 1 of PR #869 found three blocking issues, fixed in the PR: the review lane
applied to any `source_review` value, a retried member blocked after regrouping stayed
in its group, and a retried group could hold a lane the run's last wave held. It also
fixed one cheap non-blocking one: `blocked-owner` was written after a worker block. These
four were left for later.

## Findings

1. **A verify-only todo on a merged cycle loses "verify only".** `group._merge_cycles`
   folds every group on a group-level cycle into one, so a verify-only todo on such a
   chain (102 -> 103 verify-only -> 101, with 101 and 102 sharing a file) ends up in a
   code group whose brief says `verify_only: false` (`scripts/todos/group.py`).
2. **A cycle inside one shared-file group now stops the whole plan.** Two todos that
   share a file and depend on each other used to plan as one group. `plan()` now refuses
   every todo-level cycle with `CycleError`, which stops every ready todo. No open todo
   has such a cycle today.
3. **apply-triage: both paths present.** When the old `in_progress` file and the new
   pending file both exist, the rename is skipped and the old file stays, so the id is
   duplicated (`scripts/todos/state.py`, `apply_triage`).
4. **apply-triage: a rerun on a later day repeats the Work Log line.** The duplicate
   check matches the heading, which includes `today`.

## Acceptance Criteria

- [x] A verify-only todo on a merged group cycle keeps its verify-only brief or is
      planned on its own, with a test.
- [x] A dependency cycle inside one shared-file group plans as one group, or is refused
      for those todos only, with a test.
- [x] apply-triage refuses, or reports, a stranded todo whose old and new paths both
      exist, with a test.
- [x] A rerun of apply-triage on a later day does not add a second "Returned to pending"
      entry, with a test.

## Work Log

### 2026-09-28 - Filed from PR #869 round 1

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- Owner decision read as: the brief and the grouping keep their shape (no per-todo verify-only flag, no
  splitting of a shared-file group), and a cycle that cannot be planned is refused for its own todos only.
- A group cycle through a verify-only todo is no longer merged (which lost "verify only"): `group.plan`
  refuses the todos on that cycle, and their dependents, with a reason naming the verify-only todo; the rest
  of the plan goes ahead.
- A dependency cycle between todos that share a file (one group) is refused for those todos and their
  dependents instead of raising `CycleError` for the whole plan. A cycle across groups still raises.
- apply-triage refuses, before writing anything, a stranded todo whose in_progress and pending files both
  exist, naming both; its "Returned to pending" duplicate check no longer includes the date. Tests in
  `test_group.py` and `test_state.py`.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_group.py` — evidence `.sweep-evidence/g8/474-ac0.txt`, last lines:

  ```text
    PASS  468: the review-doc lane is named after the doc, and has a description for the brief
    PASS  PR #869: a source_review outside docs/reviews/*.md is not a lane
    PASS  planning is deterministic

  All checks passed.
  ```

- AC 2: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_group.py` — evidence `.sweep-evidence/g8/474-ac1.txt`, last lines:

  ```text
    PASS  468: the review-doc lane is named after the doc, and has a description for the brief
    PASS  PR #869: a source_review outside docs/reviews/*.md is not a lane
    PASS  planning is deterministic

  All checks passed.
  ```

- AC 3: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_state.py` — evidence `.sweep-evidence/g8/474-ac2.txt`, last lines:

  ```text
    PASS  474 AC3: apply-triage refuses a stranded todo whose old and new paths both exist, naming both
    PASS  474: the refusal comes before anything is written (the other todo is untouched)
    PASS  474 AC4: a rerun of apply-triage on a later day adds no second 'Returned to pending' entry

  All checks passed.
  ```

- AC 4: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_state.py` — evidence `.sweep-evidence/g8/474-ac3.txt`, last lines:

  ```text
    PASS  474 AC3: apply-triage refuses a stranded todo whose old and new paths both exist, naming both
    PASS  474: the refusal comes before anything is written (the other todo is untouched)
    PASS  474 AC4: a rerun of apply-triage on a later day adds no second 'Returned to pending' entry

  All checks passed.
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
