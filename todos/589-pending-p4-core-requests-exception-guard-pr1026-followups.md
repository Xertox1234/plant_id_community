---
status: pending
priority: p4
issue_id: "589"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1026 (todo 555)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1026 (the requests-exception leak guard). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1026 (todo sweep run 2026-10-11-1448, group g3, todos 555); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/core/tests/test_requests_exception_drift.py:1034` Parameter-default capture is followed only for a def whose lines fall inside the handler, a direct own-node of the handler's scope, seeded only with handler names. Missed: `def render(m=msg)` after a fall-through handler, a def nested in `outer`, and every default in the body guard (`def g(b=response.text)`). | also: `_params_defaulting_to` runs only for direct children of the scope that holds the handler. A def nested one level deeper, as in `except E as e: def outer(): def render(c=e): return {"error": c}`, evaluates its default in `outer`, which has no handlers, so `c` is never seeded and the leak is missed. | (line 1035) The finding-6 default fix only seeds defs that are direct own-nodes of the scope holding the handler. Probed in memory: `except E as e: def outer(): def render(c=e): return {'error': f'{c}'}` gives [], and `body = response.text; def g(b=body): return {'error': b}` gives [] from both guards. | (line 1037, low) Default capture is followed only for a def inside the handler and only for the handler's names. A default naming a derived name after the handler (`def f(m=msg)`) is missed. So is any default in the body guard (`def f(b=response.text)`, line 1101), since `b` is a param and the dict value has no `.text`.
2. **medium** `backend/apps/core/tests/test_requests_exception_drift.py:971` Comprehension shadowing applies only at the dict-value check (`_mentions`). `_tainted_names` still taints through shadowed reads, so a one-hop local is a false positive: `out = ", ".join(line for line in items); return {"error": out}` or `out = [msg for msg in items]` in a child is flagged. | also: (line 972, low) The comprehension shadow only masks reads directly inside a response dict. `_tainted_names` still taints `x = [line for line in items]` from the parent's tainted `line`, so `{"error": x}` in a child stays a false positive one hop away, which is the refactor the guard expects.
3. **medium** `backend/apps/core/tests/test_requests_exception_drift.py:1017` A handler-tainted `global` reaches only the declaring function and its closures. `_scopes` hoists nonlocal names but never globals, so a sibling `def status(): return {"error": LAST_ERROR}` reading the module cache is missed; the test comment ('the next call returns it') overstates coverage. | also: A global that outlives a raising handler is tracked only in the same function and its closures. A sibling function `def b(): return {'error': CACHE}` that reads the cached global is not flagged, and the docstring/test comment ('the next call returns it') overstate the coverage. | The guard catches a handler-tainted `global` only when the same function or its closures read it. `_scopes` hoists `nonlocal` names but not `global` ones, so `except E as e: LAST = str(e); raise` in one function and `return {"error": LAST}` in a sibling function goes unflagged. This gap existed before the change and is only partly closed.
4. **medium** `backend/apps/core/tests/test_requests_exception_drift.py:1035` The finding-6 default fix only seeds defs that are direct own-nodes of the scope holding the handler. Probed in memory: `except E as e: def outer(): def render(c=e): return {'error': f'{c}'}` gives [], and `body = response.text; def g(b=body): return {'error': b}` gives [] from both guards.
5. **low** `backend/apps/core/tests/test_requests_exception_drift.py:846` `_comprehension_shadowed` returns at `_SCOPES`, so a lambda inside a comprehension that reads the comprehension's own clean variable is not shadowed: `[(lambda: {"error": line})() for line in items]` in a child is flagged as leaking the parent's tainted `line`.
6. **low** `backend/apps/core/tests/test_requests_exception_drift.py:836` `_comprehension_shadowed` judges an iterable clean via `_carried`, which drops non-value-preserving call args, so `[{"error": msg} for msg in wrap(msg)]` with msg tainted is masked, while the same flow as `msg = wrap(msg)` stays flagged.
7. **low** `scripts/inject/test_budget_rules.py:116` test_tail_only_empty_edge_is_exactly_the_marker_cost pins literal shares 139/140/141 that depend on the tail marker's text and the specimen; any marker wording change turns it red, and nothing derives the edge from the marker length. | also: New test pins literal byte shares 139/140/141 tied to the tail-marker text; it is additive and justified (it tightens a loose bracket), but will fail on any wording change to the marker, not on a real regression.
8. **low** `backend/apps/core/tests/test_requests_exception_drift.py:1037` Default capture is followed only for a def inside the handler and only for the handler's names. A default naming a derived name after the handler (`def f(m=msg)`) is missed. So is any default in the body guard (`def f(b=response.text)`, line 1101), since `b` is a param and the dict value has no `.text`.
9. **low** `backend/apps/core/tests/test_requests_exception_drift.py:972` The comprehension shadow only masks reads directly inside a response dict. `_tainted_names` still taints `x = [line for line in items]` from the parent's tainted `line`, so `{"error": x}` in a child stays a false positive one hop away, which is the refactor the guard expects.

4 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: backend/apps/core/tests/test_requests_exception_drift.py:1900 The new `approved_*` specimens (import shadow, comprehension shadow, walrus) are asserted only by absence from the exact result sets, so only the paired positive cases show the guard actually ran over them. (refuted: Exact set equality is a per-specimen assertion: each approved specimen uses a unique name (own_line, own_msg, comp_walrus, json.dumps({})), so a false positive adds a new string and fails the assert. Positives in the same planted file prove the guard ran over it.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1026 (todo 555).
