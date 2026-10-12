---
status: pending
priority: p4
issue_id: "633"
tags: [core, tests, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
---

# Follow-ups from PR #1078 (todo 609, requests-exception drift guard)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1078 (todo 609, requests-exception drift guard). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1078 (todo sweep run 2026-10-12-0349, group g8, todos 609); follow-ups: verified.

1. **medium** `backend/apps/core/tests/test_requests_exception_drift.py:1133` The deeper strict-default check uses only the handler's own names (strict[outer]), not names a middle def derives from them. `def outer(): msg = e; def render(m=type(msg).__name__)` inside a handler is not flagged, so 'at any depth' holds only partly. | also: The deeper strict-default check only looks at the handler's own names (strict[outer]), not names a middle def derives from them. `def outer(): msg = e; def render(m=type(msg).__name__)` inside a handler is not flagged (I probed it: []). The same shape directly in the handler is flagged, so 'at any depth' only holds partly.
2. **low** `backend/apps/core/tests/test_requests_exception_drift.py:1136` The deep strict default check calls _params_defaulting_to(child, handler_names, walk=ast.walk) without `shadowed`, so a lambda default reading a comprehension's own `e` inside a def in the handler is a false positive (same FP already existed one level up). | also: The deep strict check calls _params_defaulting_to with ast.walk and no `shadowed`, so a lambda default that reads a comprehension's own clean `e` inside a def in the handler is a false positive: `def outer(items): return [(lambda m=type(e).__name__: {"error": m})() for e in items]` gets flagged (I probed it). | The new depth-strict default check calls_params_defaulting_to(child, handler_names, walk=ast.walk) with no `shadowed`, so a comprehension variable named like the exception gets flagged. Probe: `def outer(): return [(lambda m=type(e).__name__: {'error': m})() for e in ['a']]` under the handler is flagged. The same false positive already existed one level up.
3. **low** `scripts/inject/test_budget_rules.py:152` The self-consistency re-measure tail_cost_at(tail_cost + 1) == tail_cost is in practice the same call as the line before (both shares 3-digit), so it cannot fail and does not guard the share-digit edge it replaced. | also: The self-consistency re-measure tail_cost_at(tail_cost + 1) == tail_cost is in practice the same call as the line before. Both shares are 3-digit (~140 vs 201), so it cannot fail and does not guard the share-digit edge it replaced.
4. **low** `scripts/inject/test_budget_rules.py:160` The edge test no longer asserts the marker's start or wording; it relies on `test_tail_only_returns_empty_only_below_the_marker_cost` for that. `split()` also relies on the fixture's last line being all "x", so a fixture change could make it return an empty body. | also: The marker-cost test no longer asserts the marker's shape (startswith/'were not injected'). The sibling test only checks that wording at share=200, so a marker-less bare suffix at the edge share would still pass here. The mutation checks do cover an over-reservation.
5. **low** `todos/archive/609-completed-p4-requests-exception-guard-1055.md:58` The 'Verified' and 'Completed' Work Log headings are dated 2026-10-11, but the run is 2026-10-12-0349 and the Implemented entry above them is dated 2026-10-12, so the log is misdated and out of order. | also: The 'Verified' and 'Completed' Work Log headings are dated 2026-10-11, but the run is 2026-10-12-0349 and the Implemented entry above is dated 2026-10-12. The log is out of order and misdated.

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: scripts/inject/test_budget_rules.py:129 The comment says the fixture's last line is all "x" and the marker never ends in an "x", but long_final_line_file() ends in "x\n" like the marker; the split works only because the suffixes are shorter than the 2000-x line. The stated reason is wrong. | also: The comment says the fixture's last line is all "x" and the marker never ends in an "x". But long_final_line_file() ends in "\n", like the marker. The split works only because the suffixes are shorter than the 2000-x line. A body that took in the whole line would overcount by the marker's trailing newline. | The new comment says the fixture's last line is all "x", but long_final_line_file() ends in "x\n". The split still works because the marker ends in "\n\n" and the byte before any in-run suffix is "x". The stated reason is wrong, though, and could mislead the next editor. (refuted: The comment is right. Both markers end in "\n\n", and the tail body (shares ~140-200) lies inside the 2000-x run, so the reversed common prefix stops at marker '\n' vs file 'x'. The whole-line overcount is unreachable at these shares.)
- low: scripts/inject/test_budget_rules.py:146 The edge/marker-cost test no longer asserts the marker's shape or wording; it relies on the sibling test, which checks wording only at share=200, so a marker-less bare suffix at the edge share would still pass. split() also relies on the all-"x" fixture line. (refuted: A bare suffix with no marker would fail: split() asserts body < len(out) ('no marker before the suffix'), and at_edge must be exactly tail_cost+1 bytes. Phrasing 0 (no wording assert; split depends on the all-x fixture) holds.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1078 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g8`.
