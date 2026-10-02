---
status: completed
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

- [x] `nonlocal` child-to-parent taint is caught again, with a planted case.
- [x] A comprehension or walrus name no longer shadows the parent's taint, with a planted case.
- [x] Findings 3 and 4 are fixed with planted negative cases, or accepted here with a reason.
- [x] Nested unpacking and `match … as` are bindings, or the docstring stops claiming them.
- [x] A closure-in-handler planted case exists, and `tail_only`'s empty return is pinned.
- [x] Offenders are reported in line order.

## Work Log

### 2026-09-28 - Filed from PR #883 rounds 1 and 2 (todo sweep run 2026-09-28-2018)

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Failing-first: `PLANTED_SCOPE` + `test_the_guards_resolve_scopes_the_way_python_does`
  (exact flagged sets for both guards, plus line order) ran red against the merge-base
  guard before any change. That guard flagged `error`, `msg`, `reason` and `captured_body`
  and missed `err`, `nested_detail`, `whole`, `rest`, `others`, `body`, `nested`,
  `comp_body`, `line`, `matched_text`; it reported `second` before `first`.
- Finding 1: `_scopes()` hoists a child's tainted `nonlocal` names to the function that
  binds them and repeats the walk to a fixpoint (one pass on every file in the tree
  today). Finding 2: `_local_names()` no longer counts a comprehension's iteration
  variable as a local. A walrus still does, because PEP 572 binds it in the enclosing
  function -- probed at runtime (the walrus closure raised `UnboundLocalError`, the
  comprehension one read the parent) and pinned by `approved_walrus_rebinds_in_the_child`.
- Findings 3/4, fixed per the owner decision rather than accepted: a handler's bound name
  now reaches only the defs and lambdas inside that handler (`closure_seeds`), and a
  handler that always leaves by `raise`/`return` -- no `finally`, no `break`/`continue`,
  no enclosing `try`/`with` -- no longer seeds the code after the try
  (`_handler_falls_through`). Three conservative controls stay flagged; a fall-through
  handler followed by a rebind is still flagged, flow-insensitive by design.
- Finding 5: `_bindings()` yields the plain names a target binds through any depth of
  unpacking (`_target_names`) and treats `match` captures (`as`, `*rest`, `**others`, a
  bare capture) as bindings of the subject (`_pattern_names`); both count as locals in
  `_local_names()` too. Findings 6/7: closure- and lambda-in-handler positives;
  `test_budget_rules.py` pins `excerpt() == ""` at shares 1/40/120 (the marker costs
  137-139 B) with a non-empty control at 200; all three guards report `(lineno, source)`
  sorted by line and column, each site once.
- Full file: 1262 passed (1261 before, plus the new test); the wider reach flags no real
  site under `apps/`, `packages/` or `plant_community_backend/`.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `bash -c 'cd backend && grep -n -A9 -E "^def nonlocal_" apps/core/tests/test_requests_exception_drift.py && grep -n -B1 -A3 "hoisted = {}" apps/core/tests/test_requests_exception_drift.py && python3 scripts/todos/slot_env.py 5 -- backend/venv/bin/python -m pytest apps/core/tests/test_requests_exception_drift.py --create-db -q -p no:cacheprovider'` — evidence `.sweep-evidence/g5/490-ac0.txt` (not committed), last lines:

  ```text
    backend/venv/lib/python3.13/site-packages/fuzzywuzzy/fuzz.py:11: UserWarning: Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning
      warnings.warn('Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning')

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 1262 passed, 2 warnings in 6.90s =======================
  ```

- AC 2: `bash -c 'cd backend && grep -n -A8 -E "^def (comprehension_target_does_not_shadow_the_parent|approved_walrus_rebinds_in_the_child)" apps/core/tests/test_requests_exception_drift.py && grep -n -A4 "comprehension_targets = {" apps/core/tests/test_requests_exception_drift.py && python3 scripts/todos/slot_env.py 5 -- backend/venv/bin/python -m pytest apps/core/tests/test_requests_exception_drift.py --create-db -q -p no:cacheprovider'` — evidence `.sweep-evidence/g5/490-ac1.txt` (not committed), last lines:

  ```text
    backend/venv/lib/python3.13/site-packages/fuzzywuzzy/fuzz.py:11: UserWarning: Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning
      warnings.warn('Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning')

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 1262 passed, 2 warnings in 7.01s =======================
  ```

- AC 3: `bash -c 'cd backend && grep -n -A10 -E "^def (approved_later_closure_reads_a_rebound_handler_name|approved_rebind_after_a_handler_that_raises|approved_rebind_after_a_handler_that_returns|rebind_after_a_handler_that_falls_through)" apps/core/tests/test_requests_exception_drift.py && grep -n -E "closure_seeds|_handler_falls_through" apps/core/tests/test_requests_exception_drift.py && python3 scripts/todos/slot_env.py 5 -- backend/venv/bin/python -m pytest apps/core/tests/test_requests_exception_drift.py --create-db -q -p no:cacheprovider'` — evidence `.sweep-evidence/g5/490-ac2.txt` (not committed), last lines:

  ```text
    backend/venv/lib/python3.13/site-packages/fuzzywuzzy/fuzz.py:11: UserWarning: Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning
      warnings.warn('Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning')

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 1262 passed, 2 warnings in 6.94s =======================
  ```

- AC 4: `bash -c 'cd backend && grep -n -A10 -E "^def (nested_unpacking_binds_every_name|match_captures_are_bindings|approved_match_capture_rebinds_in_the_child)" apps/core/tests/test_requests_exception_drift.py && grep -n -A3 -E "^def (_target_names|_pattern_names)" apps/core/tests/test_requests_exception_drift.py && python3 scripts/todos/slot_env.py 5 -- backend/venv/bin/python -m pytest apps/core/tests/test_requests_exception_drift.py --create-db -q -p no:cacheprovider'` — evidence `.sweep-evidence/g5/490-ac3.txt` (not committed), last lines:

  ```text
    backend/venv/lib/python3.13/site-packages/fuzzywuzzy/fuzz.py:11: UserWarning: Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning
      warnings.warn('Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning')

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 1262 passed, 2 warnings in 6.64s =======================
  ```

- AC 5: `bash -c 'cd backend && grep -n -A8 -E "^def (closure_in_a_handler_reads_the_exception|lambda_in_a_handler_reads_the_exception)" apps/core/tests/test_requests_exception_drift.py && python3 scripts/todos/slot_env.py 5 -- backend/venv/bin/python -m pytest apps/core/tests/test_requests_exception_drift.py --create-db -q -p no:cacheprovider && grep -n -A12 "def test_tail_only_returns_empty_only_below_the_marker_cost" scripts/inject/test_budget_rules.py && python3 scripts/inject/test_budget_rules.py -v'` — evidence `.sweep-evidence/g5/490-ac4.txt` (not committed), last lines:

  ```text

  ----------------------------------------------------------------------
  Ran 6 tests in 0.000s

  OK
  ```

- AC 6: `bash -c 'cd backend && grep -n -E "sorted\(found|Line order|== sorted\(" apps/core/tests/test_requests_exception_drift.py && grep -n -A6 "^def two_sites_in_one_function_report_in_line_order" apps/core/tests/test_requests_exception_drift.py && python3 scripts/todos/slot_env.py 5 -- backend/venv/bin/python -m pytest apps/core/tests/test_requests_exception_drift.py --create-db -q -p no:cacheprovider'` — evidence `.sweep-evidence/g5/490-ac5.txt` (not committed), last lines:

  ```text
    backend/venv/lib/python3.13/site-packages/fuzzywuzzy/fuzz.py:11: UserWarning: Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning
      warnings.warn('Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning')

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 1262 passed, 2 warnings in 7.56s =======================
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-02 - Repaired by the todo sweep (run 2026-10-02-0335)

- Round 1 found a regression in the finding-3 fix: `closure_seeds` seeded only the defs and
  lambdas lexically inside a handler, so a closure defined before the handler and called from
  it (`def fail(): return {"error": str(exc)}` ... `except E as exc: return fail()`) went
  unflagged. The merge-base guard flagged that shape, and at runtime the dict carries the
  exception (probed: an earlier def and an earlier lambda both returned the provider text).
- `step` now collects the scope's own defs and lambdas once and seeds every one defined before
  or inside the handler (`child.lineno <= handler.end_lineno`) with the handler's visible names
  minus the child's own locals. A closure after the handler stays unseeded: Python unbinds the
  name on exit, so it can only read a rebound value or raise `NameError` (probed), which keeps
  `approved_later_closure_reads_a_rebound_handler_name` quiet.
- Planted: `closure_before_the_handler_reads_the_exception` and
  `lambda_before_the_handler_reads_the_exception` (positives, added to the exact set) and
  `approved_earlier_closure_rebinds_the_handler_name` (the control: an earlier closure that
  binds the name itself is not seeded with it). Not covered on purpose: a closure defined after
  the handler inside a loop that could call it on a later iteration -- seeding it would reopen
  finding 3.
- Full file: 1262 passed; the wider reach still flags no real site under `apps/`, `packages/`
  or `plant_community_backend/`.
