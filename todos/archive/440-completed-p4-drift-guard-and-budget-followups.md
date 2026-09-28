---
status: completed
priority: p4
issue_id: "440"
tags: [backend, harness, guards]
dependencies: []
source_review: "PR #822"
triage: ready
triaged: 2026-09-28
---

# Response-dict drift guards and budget_rules: remaining reach limits

## Problem

Todo 391 added a local-taint pass to the response-dict drift guards
(`backend/apps/core/tests/test_requests_exception_drift.py`) and hardened
`scripts/inject/budget_rules.py`. The bundled `/code-review` of PR #822
verified these gaps, all non-blocking.

## Findings

- **Exception taint stops at the handler.** `err = str(e)` inside `except`,
  then `return {"error": err}` AFTER the try/except, is not flagged. Scope
  the exception taint to the enclosing function, like the body guard.
- **`str.join` is missing from `VALUE_PRESERVING_METHODS`**, so
  `" ".join(["failed", str(e)])` / `"".join([response.text])` bound to a
  local walk past both guards.
- **Only Assign/AnnAssign/AugAssign/NamedExpr propagate taint**: `for`,
  `async for`, `with ... as` and comprehension targets bound from a tainted
  value do not.
- **`ast.walk(func)` descends into nested defs**, so taint leaks between a
  nested function and its parent (false positives), and inner functions are
  scanned twice. The lambda's `# noqa: E731` sits on the wrong line.
- **`budget_rules.tail_only()` can return `""`** when the final rule is
  longer than the tail room, so a routed domain contributes nothing and no
  "open the file" marker. Falling back to a raw mid-line suffix plus
  `tail_marker` keeps the documented "every routed domain contributes
  something". Predates #822.

## Acceptance Criteria

- [x] Each finding is fixed with a failing-first test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #822 review round 1

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- All five findings fixed, none declined. Failing-first: `PLANTED_REACH` +
  `test_the_guards_reach_past_the_handler_and_through_every_binding` (exact
  flagged sets for both guards) and `EveryRoutedDomainContributesTests` were
  written and run red before any guard or `budget_rules` change.
- Exception taint: locals a handler derives from its exception now seed a taint
  pass over the whole enclosing function (`err = str(e)` in the handler,
  `return {"error": err}` after it). The bound name itself does not, since
  Python unbinds it when the handler exits. Nested handlers report a site once.
- `join` added to `VALUE_PRESERVING_METHODS`. `_bindings()` now also follows
  `for` / `async for` / `with ... as` / comprehension targets.
- A new `_own_nodes()`/`_scopes()` walk stops at nested defs and lambdas.
  Taint no longer leaks from a child to its parent or into a child that
  rebinds the name. A closure still inherits the free variables it reads. The
  misplaced `# noqa: E731` lambda became `_is_body()`.
- `budget_rules.tail_only()` now falls back to a raw mid-line suffix plus
  `tail_marker`. It returns "" only when the share cannot hold the marker
  itself (~150 B, below any real share).

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `bash -c 'cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_4f691fda-f6b-3/backend && python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_4f691fda-f6b-3/scripts/todos/slot_env.py 3 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest apps/core/tests/test_requests_exception_drift.py --create-db -q -p no:cacheprovider && python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_4f691fda-f6b-3/scripts/inject/test_budget_rules.py -v'` — evidence `.sweep-evidence/g11/440-ac0.txt`, last lines:

  ```text

  ----------------------------------------------------------------------
  Ran 5 tests in 0.000s

  OK
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
