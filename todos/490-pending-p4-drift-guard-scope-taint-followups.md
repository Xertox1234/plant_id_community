---
status: pending
priority: p4
issue_id: "490"
tags: [backend, security, testing]
dependencies: []
source_review: "PR #883"
triage: ready
triaged: 2026-10-02
owner_decision: "Fix findings 3/4: nested-unpack and match-as names become real bindings in the guard's scope analysis, with planted cases (2026-10-02)"
---

# Requests-exception drift guard: non-blocking findings from PR #883 (todo 440)

## Problem

PR #883 made the requests-exception drift guard scope-aware (`_scopes`, per-scope taint) so that
nested defs stop leaking taint. Both review rounds were clean. The reviewers probed some shapes
that `origin/main`'s whole-function `ast.walk` caught and the new walk misses. Those come first
below, because this guard runs on every backend file.

## Findings

1. **Child-to-parent taint through `nonlocal` is lost.** This is a regression against main. A
   nested def that does `nonlocal body; body = response.text` no longer taints the parent's
   `return {"error": body}`. Probed: main flags it, and the new code returns `[]`
   (`test_requests_exception_drift.py:494-510`).
2. **Comprehension and walrus names shadow the parent.** `_local_names` counts them as the
   child's own locals, so a closure that also reads the parent's tainted variable of the same
   name loses the taint (`:479`).
3. **Handler names leak to every nested def.** A closure that reads a parent variable reusing a
   handler's name (`except … as error:` and later `error = "Service unavailable"`) is falsely
   flagged (`:675`).
4. **`seeds |= derived` ignores flow.** `msg = str(e); logger.error(msg); raise` followed by
   `msg = "Service unavailable"; return {"error": msg}` is flagged (`:673`).
5. **Target unpacking is one level deep.** `for i, (k, line) in …` leaves `line` untainted, and
   `match … case … as s` captures are not bindings, although the docstring claims every binding
   is covered (`:576`).
6. **Coverage gaps.** No planted case has a closure or lambda inside a handler reading the
   exception (`:676`). `test_budget_rules.py:93` never pins that `tail_only` returns `""` when the
   share cannot carry the marker.
7. **Offenders are listed in DFS order, not line order** (`:678`).

## Acceptance Criteria

- [ ] `nonlocal` child-to-parent taint is caught again, with a planted case.
- [ ] A comprehension or walrus name no longer shadows the parent's taint, with a planted case.
- [ ] Findings 3 and 4 are fixed with planted negative cases, or accepted here with a reason.
- [ ] Nested unpacking and `match … as` are bindings, or the docstring stops claiming them.
- [ ] A closure-in-handler planted case exists, and `tail_only`'s empty return is pinned.
- [ ] Offenders are reported in line order.

## Work Log

### 2026-09-28 - Filed from PR #883 rounds 1 and 2 (todo sweep run 2026-09-28-2018)
