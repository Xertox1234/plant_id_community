---
status: pending
priority: p4
issue_id: "476"
tags: [harness, todo-sweep]
dependencies: []
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

- [ ] `schemaErrors` reports an unknown schema type as a clear problem instead of throwing,
      with a test.
- [ ] `schemaErrors` checks `items` whenever it is present, with a test.
- [ ] A re-run verdict that fails only on "tree not clean before verification" is handled
      deliberately (returned without a worker retry, or the tree is checked first), with a
      test.
- [ ] Whether the post-repair verifier re-runs on a null verdict is decided and recorded.

## Work Log

### 2026-09-28 - Filed from PR #871 round 1
