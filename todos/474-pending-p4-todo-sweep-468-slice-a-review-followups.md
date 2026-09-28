---
status: pending
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

- [ ] A verify-only todo on a merged group cycle keeps its verify-only brief or is
      planned on its own, with a test.
- [ ] A dependency cycle inside one shared-file group plans as one group, or is refused
      for those todos only, with a test.
- [ ] apply-triage refuses, or reports, a stranded todo whose old and new paths both
      exist, with a test.
- [ ] A rerun of apply-triage on a later day does not add a second "Returned to pending"
      entry, with a test.

## Work Log

### 2026-09-28 - Filed from PR #869 round 1
