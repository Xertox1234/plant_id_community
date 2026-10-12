---
status: pending
priority: p4
issue_id: "645"
tags: [core, tests, follow-ups]
dependencies: []
---

# Follow-ups from PR #1101 (todo 633, requests-exception drift guard)

## Problem

Todo-sweep run 2026-10-12-1724 merged PR #1101 (todo 633, requests-exception drift guard). The non-blocking review findings are
below. The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: these follow-ups are the end state of the
one extra pass, so this todo is filed, not swept.

## Findings

PR #1101 (todo sweep run 2026-10-12-1724, group g7, todos 633); follow-ups: verified.

1. **low** `backend/apps/core/tests/test_requests_exception_drift.py:1146` The Finding-2 fix only covers defaults one def below a clean comprehension. A lambda inside a clean comprehension still inherits the comprehension's `e` in strict, so a default two scopes down is a false positive, e.g. `[(lambda: (lambda q=type(e).__name__: {'error': q})())() for e in items]`.
2. **low** `backend/apps/core/tests/test_requests_exception_drift.py:1165` Strict-mode comprehension shadowing decides 'clean iterable' with _carried, which skips opaque-call arguments. So `[(lambda m=x.__name__: {"error": m})() for x in (type(e),)]` or `for e in wrap(e)` reads as clean and the default stays quiet. Strict ast.walk flagged it before this change.
3. **low** `scripts/inject/test_budget_rules.py:160` The settle loop still cannot fail today. Both shares have three digits, so the first re-measure already equals the cost. The byte-exact edge assertions after the loop carry the real protection.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1101 review (todo sweep run 2026-10-12-1724)

Filed by the closing step of the run from `state.py followups-md g7`.
