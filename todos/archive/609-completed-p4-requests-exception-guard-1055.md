---
status: completed
priority: p4
issue_id: "609"
tags: [backend, testing, guard, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1055 (todo 589, requests exception drift guard)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1055 (todo 589, requests exception drift guard). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

Item 1 is the round-2 low left after the owner-approved hand repair restored the three lost detections: a contrived `lambda e=None` rebinding inside a comprehension over `e.args` is no longer flagged.

## Findings

PR #1055 (todo sweep run 2026-10-11-2219, group g7, todos 589); follow-ups: verified; 2 item(s) the curator did not return were kept as stored.

1. **low** `backend/apps/core/tests/test_requests_exception_drift.py:667` By reasoning: the iterable is only judged tainted when a child's seeds hold the handler name. In `except E as e: [(lambda e=None: {"error": a})() for a in e.args]` the lambda binds e, so seeds exclude e, `e.args` reads clean, `a` is masked, and main's old flag is lost. Contrived.
2. **low** `backend/apps/core/tests/test_requests_exception_drift.py:678` Strictness is inconsistent: a def directly in a handler checks its defaults with ast.walk, so `m=type(e).__name__` is caught. One def deeper, _scopes uses_carried, so `def outer(): def render(m=type(e).__name__)` is missed. Not a regression.
3. **low** `scripts/inject/test_budget_rules.py:131` The edge test derives tail_cost by string-parsing a real excerpt's marker at share 200 (split on 'the first ' and '...]\n\n'). A rewording raises IndexError/ValueError instead of a clear assertion failure. The digit-count equality only partly guards it, and the edge partly mirrors production. | also: low: scripts/inject/test_budget_rules.py:139 Reads the marker text off a real excerpt() at share 200, rewrites the count, then asserts digit-count equality as a guard. Brittle: a marker that varies by share digits fails for the wrong reason, and the derived edge partly mirrors production. | low: scripts/inject/test_budget_rules.py:517 The work log says a marker wording change does not fail this test, but marker() parses on the literals 'the first ' and '...]\n\n', and the asserts still pin 'were not injected'. Rewording raises IndexError/ValueError or fails. The edges are derived, but the text is still pinned.
4. **low** `scripts/inject/test_budget_rules.py:139` The edge test reads the marker text off a real excerpt() at share 200 and rewrites the count. It then asserts a digit-count equality as a guard. This is brittle: a marker that varies by share digits makes the test fail for the wrong reason, and the derived edge partly mirrors production.
5. **low** `scripts/inject/test_budget_rules.py:517` The work log says a marker wording change does not fail this test, but `marker()` parses on the literals 'the first ' and '...]\n\n', and the asserts still pin 'were not injected'. Rewording any of these raises IndexError/ValueError or fails. The edges are derived, but the text is still pinned.

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: backend/apps/core/tests/test_requests_exception_drift.py:641_scopes subtracted the comprehension mask from closure_seeds too, so a lambda param sharing a clean comprehension variable's name lost its handler-default taint: `except Exception as e: return [(lambda line=f"{e}": {"error": line})() for line in items]` went quiet. (fixed on main: origin/main_scopes now does `masked = masked - _local_names(scope)` before the subtraction, with a comment citing this exact lambda-line case (hand repair before round 2).; the refuter agreed: Fixed on origin/main: _scopes does `masked = masked - _local_names(scope)` before subtracting, so the lambda param keeps its handler-default seed. Planted case a_lambda_param_spells_a_clean_comprehension_variable is in the expected set.)
- medium: backend/apps/core/tests/test_requests_exception_drift.py:658 Comprehension mask hid the exception from a lambda: `except E as e: return [(lambda: {"error": a})() for a in e.args]` passed, because masks came from the scope's `tainted`, which never holds the handler's `e`. (fixed on main: origin/main computes `seen = tainted.union(seeds of each child scope)` and passes it to_comprehension_shadowed, with a comment citing this exact case.; the refuter agreed: Fixed: `seen` = tainted plus child seeds. Comp target hr_arg is in derived (comprehension is a _bindings entry), seeds hold e, so e.args is not clean and nothing is masked. The planted case 'f'exc arg {hr_arg}'' is asserted.)
- medium: backend/apps/core/tests/test_requests_exception_drift.py:1110_params_defaulting_to used _carried instead of_mentions, so `def render(m=type(e).__name__)` inside a handler was no longer flagged, though the guard's docstring names type(e).**name** as a leak. (fixed on main: origin/main adds a `walk` param; the handler call site (line ~1133) passes `walk=ast.walk`, and the docstring cites type(e).**name** (hand repair before round 2).; the refuter agreed: Fixed: _params_defaulting_to takes a walk param, and the handler call at line 1133 passes walk=ast.walk, so type(e).**name** is caught. Planted a_default_names_the_exception_type 'f'type default {hr_type}'' is in the expected set.)
- low: backend/apps/core/tests/test_requests_exception_drift.py:2150 The new fixtures use the module globals SIBLING_ERR and BODY_CACHE. Quiet cases like approved_a_local_shadows_a_tainted_global are checked only through the aggregate set comparison, and source strings like 'SIBLING_ERR' are ambiguous between the flagged sibling and the shadowing local. (refuted: Not ambiguous: the shadowing local's dict value unparses as "f'local {SIBLING_ERR}'", not the bare 'SIBLING_ERR'. The exact-set equality would fail on a new false positive there, so the quiet case is checked.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1055 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g7`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-0349)

- Finding 1 fixed: `_scopes` takes a `reach` map (the names visible where a def inside a handler is defined, before its own bindings are subtracted) and judges comprehension iterables with it, so `[(lambda e=None: {"error": a})() for a in e.args]` is flagged again. Planted case `a_lambda_rebinding_the_name_reads_a_comprehension_over_the_exception` in `backend/apps/core/tests/test_requests_exception_drift.py`.
- Finding 2 fixed: the strict (`ast.walk`) default check now holds at any depth below the handler. `step` keeps a `strict` map of the handler's names in force in each def defined inside it, minus what that def binds, so `def outer(): def render(m=type(e).__name__)` is flagged. Planted case `a_default_two_defs_deep_names_the_exception_type`, with the quiet control `approved_a_middle_def_rebinds_the_exception_name` (`def outer(e=None)`).
- Findings 3, 4 and 5 (one item reported three times) fixed: `test_tail_only_empty_edge_is_exactly_the_marker_cost` in `scripts/inject/test_budget_rules.py` now measures the marker instead of parsing it: the file suffix is the longest run the excerpt shares with the file's end, and the skipped count's digits are swapped arithmetically. The share-digit guard became a self-consistency re-measure, and the test asserts no marker wording.
- Mutation checks: dropping `reach` fails only the finding-1 case, dropping the strict propagation fails only the finding-2 case, a reworded tail marker leaves the edge test green, and a 50 B over-reservation fails it.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest apps/core/tests/test_requests_exception_drift.py -q -p no:cacheprovider && python3 ../scripts/inject/test_budget_rules.py -v && grep -n -A8 'Implemented by the todo sweep (run 2026-10-12-0349)' ../todos/archive/609-completed-p4-requests-exception-guard-1055.md` — evidence `.sweep-evidence/g8/609-ac0.txt` (not committed), last lines:

  ```text
  48-
  49-- Finding 1 fixed: `_scopes` takes a `reach` map (the names visible where a def inside a handler is defined, before its own bindings are subtracted) and judges comprehension iterables with it, so `[(lambda e=None: {"error": a})() for a in e.args]` is flagged again. Planted case `a_lambda_rebinding_the_name_reads_a_comprehension_over_the_exception` in `backend/apps/core/tests/test_requests_exception_drift.py`.
  50-- Finding 2 fixed: the strict (`ast.walk`) default check now holds at any depth below the handler. `step` keeps a `strict` map of the handler's names in force in each def defined inside it, minus what that def binds, so `def outer(): def render(m=type(e).__name__)` is flagged. Planted case `a_default_two_defs_deep_names_the_exception_type`, with the quiet control `approved_a_middle_def_rebinds_the_exception_name` (`def outer(e=None)`).
  51-- Findings 3, 4 and 5 (one item reported three times) fixed: `test_tail_only_empty_edge_is_exactly_the_marker_cost` in `scripts/inject/test_budget_rules.py` now measures the marker instead of parsing it: the file suffix is the longest run the excerpt shares with the file's end, and the skipped count's digits are swapped arithmetically. The share-digit guard became a self-consistency re-measure, and the test asserts no marker wording.
  52-- Mutation checks: dropping `reach` fails only the finding-1 case, dropping the strict propagation fails only the finding-2 case, a reworded tail marker leaves the edge test green, and a 50 B over-reservation fails it.
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
