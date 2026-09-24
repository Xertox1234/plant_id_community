---
status: pending
priority: p4
issue_id: "440"
tags: [backend, harness, guards]
dependencies: []
source_review: "PR #822"
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

- [ ] Each finding is fixed with a failing-first test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #822 review round 1
