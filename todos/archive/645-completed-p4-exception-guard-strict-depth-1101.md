---
status: completed
priority: p4
issue_id: "645"
tags: [core, tests, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1101 review (todo sweep run 2026-10-12-1724)

Filed by the closing step of the run from `state.py followups-md g7`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-2056)

- Finding 1 fixed: in `backend/apps/core/tests/test_requests_exception_drift.py` the strict names a def inherits no longer include a name a clean comprehension around it rebinds (`_comprehension_shadowed` masks), so a default two scopes below `for e in items` is quiet, in the handler and a def deeper. Two `approved_*` fixtures pin it.
- Finding 2 fixed for `for e in wrap(e)`: the strict-mode comprehension judgement now walks the iterable with `ast.walk` (new `walk=` parameter), so a call on the exception no longer unmasks `e`; three flagged fixtures (handler, a def deeper, two scopes down) pin it. Each fix was mutation-checked: reverting it fails `test_the_guards_resolve_scopes_the_way_python_does`.
- Finding 2, the `for x in (type(e),)` shape, declined: it was never flagged (probed against the pre-#1101 guard, commit 0596f2c7), and it is the same as `x = type(e); def render(m=x.__name__)`, which the guard leaves quiet by design because an opaque call's argument is not carried (todo 589 finding 6, todo 391).
- Finding 3 declined: confirmed the settle loop in `scripts/inject/test_budget_rules.py` settles on the first re-measure (139 B both times). It is a convergence step for a marker that drops below 100 B, not a check; the byte-exact edge assertions after it carry the protection. The comment now says so.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-2056)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 6 -- venv/bin/python -m pytest apps/core/tests/test_requests_exception_drift.py ../scripts/inject/test_budget_rules.py --create-db -q -p no:cacheprovider && grep -n '^- Finding' ../todos/archive/645-completed-p4-exception-guard-strict-depth-1101.md` — evidence `.sweep-evidence/g6/645-ac0.txt` (not committed), last lines:

  ```text
  ====================== 1380 passed, 2 warnings in 10.69s =======================
  41:- Finding 1 fixed: in `backend/apps/core/tests/test_requests_exception_drift.py` the strict names a def inherits no longer include a name a clean comprehension around it rebinds (`_comprehension_shadowed` masks), so a default two scopes below `for e in items` is quiet, in the handler and a def deeper. Two `approved_*` fixtures pin it.
  42:- Finding 2 fixed for `for e in wrap(e)`: the strict-mode comprehension judgement now walks the iterable with `ast.walk` (new `walk=` parameter), so a call on the exception no longer unmasks `e`; three flagged fixtures (handler, a def deeper, two scopes down) pin it. Each fix was mutation-checked: reverting it fails `test_the_guards_resolve_scopes_the_way_python_does`.
  43:- Finding 2, the `for x in (type(e),)` shape, declined: it was never flagged (probed against the pre-#1101 guard, commit 0596f2c7), and it is the same as `x = type(e); def render(m=x.__name__)`, which the guard leaves quiet by design because an opaque call's argument is not carried (todo 589 finding 6, todo 391).
  44:- Finding 3 declined: confirmed the settle loop in `scripts/inject/test_budget_rules.py` settles on the first re-measure (139 B both times). It is a convergence step for a marker that drops below 100 B, not a check; the byte-exact edge assertions after it carry the protection. The comment now says so.
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-2056)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-12 - Review round 1: non-blocking findings declined (owner decision)

The owner decided on 2026-10-12 that this batch's non-blocking review findings are recorded here, not filed as
new todos. Round 1 found nothing blocking. These low findings are declined:

- With `walk=ast.walk`, `carries()` walks into a lambda inside a strict comprehension iterable. So in
  `for e in map(lambda e: e.x, items)`, a lambda parameter with the same name counts as the exception. Declined:
  the guard errs toward flagging, and nothing on main has that shape.
- The `test_budget_rules.py` comment names only the edge dropping below 100 B. The cost also moves when the
  edge's digit count changes the other way, past 999 B. Declined: this is comment wording only.
- No `approved_*` fixture pins the declined `for x in (type(e),)` shape as quiet. Declined: pinning a shape
  that was declined is not needed.
