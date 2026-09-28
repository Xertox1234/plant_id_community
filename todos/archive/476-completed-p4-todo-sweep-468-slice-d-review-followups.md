---
status: completed
priority: p4
issue_id: "476"
tags: [harness, todo-sweep]
dependencies: []
triage: blocked-owner
triaged: 2026-09-28
blocked_on: "An owner decision on whether the post-repair verifier in todo-review.js re-runs after a null verdict, as execute does (criterion 4)."
owner_decision: "The post-repair verifier re-runs once after a null verdict, as execute does; check the tree before the re-run (2026-09-28)"
---

# Todo sweep: non-blocking findings from PR #871 round 1 (todo 468 slice D)

## Problem

Round 1 of PR #871 found nothing blocking: the workflow fixture validator, dropping
`CLAIMED_TREE`, and the verifier re-run after a null verdict. These four findings were
left for later.

## Findings

1. **The fixture validator throws on a schema type it does not know.** `type: 'number'`,
   `'null'` or a type array makes `IS[schema.type]` throw, which surfaces as a misleading
   "no stage threw" failure (`scripts/todos/test_workflows.js`, `schemaErrors`). No schema
   uses one today.
2. **An `items` without `type: 'array'` is not checked.** No schema has one today.
3. **A verifier that dies part-way can dirty the tree for its re-run** (hypothesis, not
   reproduced in a real sweep). If the first verifier leaves untracked output, the re-run
   fails with "tree not clean before verification" and the worker is retried on that tree.
   Before PR #871 the group went straight to `failed`.
4. **The post-repair verifier in `todo-review.js` has no re-run on a null verdict.** The
   owner's decision was about the execute stage; nothing records whether review should
   match.

## Acceptance Criteria

- [x] `schemaErrors` reports an unknown schema type as a clear problem instead of throwing,
      with a test.
- [x] `schemaErrors` checks `items` whenever it is present, with a test.
- [x] A re-run verdict that fails only on "tree not clean before verification" is handled
      deliberately (returned without a worker retry, or the tree is checked first), with a
      test.
- [x] Whether the post-repair verifier re-runs on a null verdict is decided and recorded.

## Work Log

### 2026-09-28 - Filed from PR #871 round 1

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- `schemaErrors` reports an unknown schema type as `unknown schema type "…"` instead of throwing, knows
  `number` and `null` and type lists, and checks `items` (and `maxItems`) on any array value.
- Decided and recorded (owner, 2026-09-28): the post-repair verifier in `todo-review.js` re-runs once after
  a null verdict, as `todo-execute.js` does, and the re-run checks the tree first. Both workflows' re-run
  prompts say an earlier verifier returned nothing and to do the clean check first, changing nothing.
- `todo-execute.js`: a re-run verdict that fails only on `tree not clean before verification` is returned
  without a worker retry (the leftovers are the dead verifier's, not the worker's). A first verifier that
  finds a dirty tree still gets the retry, and so does a re-run that also found a real problem.
- Tests in `test_workflows.js` for each case; `todo-verifier.md` step 1 carries the re-run rule.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `node /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_workflows.js` — evidence `.sweep-evidence/g8/476-ac0.txt`, last lines:

  ```text
    PASS  476 AC2: items are checked whenever present, even without type: array
    PASS  WORKER schema is identical in execute and review
    PASS  VERDICT schema is identical in execute and review

  All checks passed.
  ```

- AC 2: `node /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_workflows.js` — evidence `.sweep-evidence/g8/476-ac1.txt`, last lines:

  ```text
    PASS  476 AC2: items are checked whenever present, even without type: array
    PASS  WORKER schema is identical in execute and review
    PASS  VERDICT schema is identical in execute and review

  All checks passed.
  ```

- AC 3: `node /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_workflows.js` — evidence `.sweep-evidence/g8/476-ac2.txt`, last lines:

  ```text
    PASS  476 AC2: items are checked whenever present, even without type: array
    PASS  WORKER schema is identical in execute and review
    PASS  VERDICT schema is identical in execute and review

  All checks passed.
  ```

- AC 4: `sh -c 'grep -n -A2 "Decided and recorded" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/todos/476-pending-p4-todo-sweep-468-slice-d-review-followups.md; grep -n "Todo 476" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/.claude/workflows/todo-review.js /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/.claude/workflows/todo-execute.js; node /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_workflows.js | grep -E "476|All checks"'` — evidence `.sweep-evidence/g8/476-ac3.txt`, last lines:

  ```text
    PASS  476: a re-run that also found a real problem still retries the worker
    PASS  476: a FIRST verifier that finds a dirty tree (the worker left it) still gets the worker retry
    PASS  476 AC1: an unknown schema type is reported, not thrown
    PASS  476 AC2: items are checked whenever present, even without type: array
  All checks passed.
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
