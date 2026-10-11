---
status: completed
priority: p4
issue_id: "555"
tags: [todo-sweep, follow-ups, backend]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #945 (todo 490), run 2026-10-02-0335

## Problem

Promoted out of todo 527 on 2026-10-10 (owner decision: slice it per PR). Todo-sweep run 2026-10-02-0335
merged PR #945; its review rounds reported the non-blocking findings below, which a curation pass
checked against main and a refuter failed to refute. Line numbers are as of 2026-10-02, so re-check each
finding against main before acting on it.

## Findings

### PR #945 (todo 490)

1. **`backend/apps/core/tests/test_requests_exception_drift.py:835`** (medium, defect). Raise/return shortcut drops handler-derived nonlocal/global names that outlive the frame. `_handler_falls_through` gates `seeds |= derived` (835-836). A handler that always raises or returns therefore seeds nothing, and the nonlocal hoist (555) only sees `tainted`. But a nonlocal or global name survives the raise. Two shapes: a retry closure doing `nonlocal last; last = str(e); raise` while the parent returns {"error": last}, or a module-global last-error cache returned on the next call. The global half is a regression: the pre-PR guard flagged it. The nonlocal half was never flagged and is a hole in AC 1's nonlocal restoration. At runtime both return the api-key URL. 0 live sites.
   Suggested: Seed `(derived - {handler.name}) & (_nonlocal_names(scope) | _global_names(scope))` unconditionally, adding a `_global_names` mirror, and gate only the remaining derived names on fall-through. Plant nonlocal+raise, nonlocal+return and global+raise positives in PLANTED\_SCOPE's exact exc set. approved\_rebind\_after\_a\_handler\_that\_raises/\_returns must stay quiet.
   Seen on main: :835-836 `if _handler_falls_through(handler, try_node, enclosed): seeds |= derived - {handler.name}`; :555 hoists only `_nonlocal_names(scope) & tainted`. In-memory probe: nonlocal+raise and nonlocal+return give main [] / pre-PR []; global+raise (dict before the try; nested def after the handler) gives main [] / pre-PR ['LAST'], ['ERR']. Runtime: both leak the URL.

2. **`backend/apps/core/tests/test_requests_exception_drift.py:411`** (low, defect). The logger guard's new line order and dedupe (AC 6) are unpinned. The docstring (186) promises offenders in line order, each once. But test\_the\_guard\_flags\_a\_planted\_violation collapses the output into a set (411), and PLANTED has no nested def. Reverting `found` to a list in walk order keeps every test green, and the guard then reports a nested-def handler twice and out of order. The work log says all three guards are ordered. Only the failure message's presentation is affected.
   Suggested: Add a nested-def handler between two outer handlers to PLANTED, then assert the exact ordered (line, src) list with no duplicates.
   Seen on main: :209 `found = set()`; :411 `flagged = {src for _, src in ...}`. In-memory mutant (list, no sort): planted tests pass, and a nested-def specimen yields lines [10, 19, 15, 15] vs main's [10, 15, 19].

3. **`backend/apps/core/tests/test_requests_exception_drift.py:490`** (low, defect). \_local\_names claims Python's rules but counts class-body stores and ignores function-local imports. `_own_nodes` stops descending only at defs and lambdas (459). So `class M: body = 1` inside a child adds `body` to the child's locals and hides the parent's tainted `body`. At runtime the child's `body` is still the parent's, because a class body binds nothing in the function, so the leak is missed. Separately, a child's `import json` is not counted, so a shadowing import inherits the parent's tainted `json` (false positive). Both are pre-existing; the new docstring list (490-497) presents this as what Python counts.
   Suggested: In `_local_names`, skip ClassDef bodies (keep the class name) and count Import/ImportFrom aliases, or derive locals from stdlib `symtable`. Plant one case for each.
   Seen on main: :513 adds only the ClassDef's name, while class-body Name stores reach :510-512 through `_own_nodes`; there is no Import arm. Probe: class-body shape gives main [] / pre-PR [], with runtime returning 'PROVIDER BODY'. Import shape is flagged ['json.dumps({})'] on both.

4. **`backend/apps/core/tests/test_requests_exception_drift.py:511`** (low, defect). A child's own comprehension variable now inherits the parent's taint (new false positive). Excluding comprehension targets (503-511) is right for reads after the comprehension and wrong inside it. `_mentions` (713) ignores comprehension scope. So a child's `[{"error": line} for line in items]` or `", ".join(body for body in items)` is flagged by both response guards whenever the parent has a tainted `line`/`body`. Python binds that name inside the comprehension, so nothing leaks. New vs pre-PR, which was quiet; only the read-after direction is planted. Low: it fails closed (CI noise) and has 0 live sites.
   Suggested: When checking a dict or value inside a comprehension, mask that comprehension's own target names from `tainted` unless its `iter` is tainted. This keeps the `comp_body`, `piece`, `a` and `ln` positives. Alternatively, treat comprehensions as scopes in `check`/`_mentions`. Plant the quiet neighbour beside comprehension\_target\_does\_not\_shadow\_the\_parent.
   Seen on main: :503-511 `comprehension_targets` excluded from the child's names; :713 `_mentions` walks every Name. Probe: child `[{"error": line} for line in items]` gives main ['line'] / pre-PR []; genexp variant flagged on main / pre []; exc-guard variant main ['msg'] / pre []. Runtime returns the item, not the parent's body.

5. **`backend/apps/core/tests/test_requests_exception_drift.py:828`** (low, defect). closure\_seeds misses a def after the handler in the same loop body, which the handler can call on a later iteration. Only defs/lambdas with `child.lineno <= handler.end_lineno` (828) receive the handler's names. Shape: `for url in urls: try: ... except E as exc: return fail()` followed by `def fail(): return {"error": str(exc)}`. On iteration 2 the handler calls the `fail` defined in iteration 1 while `exc` is bound, and the dict carries the api-key URL. The pre-PR guard flagged this; main does not. The work log (archive :167) accepted it as 'not covered on purpose'; the owner decision did not cover it.
   Suggested: Also seed a post-handler def/lambda when it and the handler's try share an enclosing For/AsyncFor/While among the scope's own nodes. approved\_later\_closure\_reads\_a\_rebound\_handler\_name has no loop, so it stays quiet. Plant the loop shape as a positive.
   Seen on main: :828 `if child.lineno <= handler.end_lineno:`. Probe: loop shape gives main exc [] / pre-PR ['str(exc)']. Runtime: loop(['ok','bad']) returns {'error': '401 ... api-key=SECRET'}.

6. **`backend/apps/core/tests/test_requests_exception_drift.py:829`** (low, defect). A handler closure that captures the exception through a parameter default is never flagged. Shape: `def render(exc=e): return {"error": str(exc)}` or `lambda exc=e: {...}` inside the handler. The default evaluates `e` in the handler, but `visible - own` (829) subtracts the parameter, and a default is not a binding, so the child's `exc` is never tainted. At runtime the dict carries the api-key URL. Pre-existing (the pre-PR guard is silent too), but it means the new closure-in-handler cases cover less than they appear to.
   Suggested: When filling closure\_seeds for a child, also seed each parameter whose default `_mentions` the handler's visible names. Plant the def and lambda variants as positives.
   Seen on main: :829 `.update(visible - own)`, where `own` = `_local_names(child)`, which includes params (:500-501). Probe: def and lambda default-arg shapes give main exc [] / pre-PR []. Runtime: both return {'error': '401 ... api-key=SECRET'}.

7. **`backend/apps/core/tests/test_requests_exception_drift.py:1354`** (low, defect). Eight branches of the new scope/exit analysis survive mutation, though the banner claims every shape is pinned both ways. Under each of these mutants all six planted tests pass and a probed leak goes unflagged (fails open): With/AsyncWith dropped from `_enclosed_tries` (737; try under `with suppress`); Break dropped (759; break before raise); TryStar dropped from `_TRY` (718; `except* ... as eg`); Starred (623) or List (625) arm of `_target_names` dropped; `<=` changed to `<` at 828 (lambda on the handler's last line). Two more are unpinned: a walrus inside a comprehension (the PEP 572 claim at 497; widening `comprehension_targets` adds a false positive), and `_nonlocal_owner` picking the nearest binder (584; farthest moves the hit to the wrong scope). Low: main flags every shape today.
   Suggested: Add cases to PLANTED\_SCOPE's exact sets. Positives: a raising handler under `with contextlib.suppress`, break before raise, `except* Exception as eg` (use an assignment, since return is illegal there), `head, *tail = ...`, `[a, b] = ...`, a lambda on the handler's closing line. Quiet cases: a walrus in a comprehension `if` inside the child, and outer plus middle both binding a name the deepest scope declares nonlocal.
   Seen on main: Mutants run in memory on main's source (With :737, Break :759, TryStar :718, Starred :623, List :625, \<= :828, walrus :503, owner :584): all 6 planted tests pass every time. Shapes flip, e.g. with-suppress main ['suppressed'] vs mutant []; nonlocal owner main line 14 vs mutant line 16. :1354 says 'pinned in both directions'.

8. **`scripts/inject/test_budget_rules.py:109`** (low, defect). test\_tail\_only\_returns\_empty\_only\_below\_the\_marker\_cost brackets the empty threshold about 60 B loosely. Measured on main: share 139 gives "", share 140 gives the marker plus a bare newline, and 141 is the first output ending in "x\\n". The test checks shares 1/40/120 with a control at 200. A 50 B over-reservation for the marker (empty through share 189) therefore passes all six tests.
   Suggested: Pin literal edges: excerpt(text, 139) == "", and excerpt(text, 140) is non-empty and starts with the marker. Keep 200 as the content control. Re-measure when the marker text changes.
   Seen on main: test\_budget\_rules.py:109 `for share in (1, 40, 120)`, :112 `excerpt(text, 200, ...)`. In-memory mutant `room = max(share - tail_cost - 50, 0)` in budget\_rules.py: last empty share 189, 6/6 tests pass.

## Acceptance Criteria

- [x] Each of its 8 findings is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- All 8 findings fixed, each with a test; nothing left as is. In `backend/apps/core/tests/test_requests_exception_drift.py`: a handler-derived `nonlocal`/`global` name now seeds the scope even when the handler raises or returns (new `_global_names`) (1). `_local_names` skips class-body stores and counts `import` names (3). New `_comprehension_shadowed` masks a comprehension's own variable when its iterable is untainted, in both response guards (4). A def later in the same loop body as the handler is seeded (`_loop_bodies`) (5), and so is a parameter whose default reads the exception (`_params_defaulting_to`) (6).
- New `test_the_logger_guard_reports_in_line_order_once` pins the exact ordered `(line, src)` list. PLANTED gained a nested-def handler between two outer ones (2).
- PLANTED_SCOPE gained positives for findings 1/3/5/6, the six finding-7 positives (`with contextlib.suppress`, break before raise, `except*`, starred and list unpacking, a lambda on the handler's last line), and quiet cases: a child's own import, a child's comprehension variable (list, genexp, exception), a walrus in a child's comprehension, and nearest-binder `nonlocal` (whose middle dict is the positive).
- `scripts/inject/test_budget_rules.py`: new `test_tail_only_empty_edge_is_exactly_the_marker_cost` pins share 139 to `""`, 140 to the marker alone, and 141 to the first content (8).
- Mutation-checked: a mutant of each fix, the eight finding-7 branches, a walk-order logger `found`, and a 50 B marker over-reservation each fail a planted test. The live sweep of every backend file stays green.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `cd backend && sh -c 'python3 scripts/todos/slot_env.py --main-root . 2 -- backend/venv/bin/python -m pytest backend/apps/core/tests/test_requests_exception_drift.py scripts/inject/test_budget_rules.py -q -p no:cacheprovider --create-db && backend/venv/bin/python .sweep-evidence/g3/mutants.py .'` — evidence `.sweep-evidence/g3/555-ac0.txt` (not committed), last lines:

  ```text
  KILLED   f7 walrus widened -> ['guards_resolve_scopes_the_way_python_doe']
  KILLED   f7 owner farthest -> ['guards_resolve_scopes_the_way_python_doe']
  budget UNMUTATED failing: []
  KILLED   f8 marker over-reserved 50 B -> ['test_tail_only_empty_edge_is_exactly_the_marker_cost']
  RESULT: every mutant killed, unmutated green
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
