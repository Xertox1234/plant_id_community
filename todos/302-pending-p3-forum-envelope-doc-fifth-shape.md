---
status: pending
priority: p3
issue_id: "302"
tags: [forum, backend, docs, testing]
dependencies: []
---

# Document the fifth forum list envelope shape (`{results}`-only)

## Problem

The wagtail_forum package documents "four list-collection envelope shapes"
(README + `test_list_envelopes.py`, which asserts `set(resp.json()) == ENVELOPE`
strictly). PR 2.5 added `topics/recent/` and `users/experts/`, which both return
a bare `{"results": [...]}` — a fifth shape equal to none of the four. The
routes were correctly added to the cache-header path list, but the envelope
table, README framing, and `test_the_four_envelopes_are_actually_distinct`
still say four.

## Findings

- `RecentTopicsView` / `ExpertsView`
  (`backend/packages/wagtail_forum/wagtail_forum/api/views.py`) return
  `{"results": [...]}` only — proven empirically during the PR 2.5 final fix
  round (probe test, deleted).
- `test_list_envelopes.py` uses strict set equality, so the new routes cannot
  be force-fitted into an existing row without failing.
- Surfaced by the PR 2.5 final-review fix round (commit bd8b426), which
  deliberately left the envelope table untouched rather than invent a shape.

## Recommended Action

1. Add a fifth `RESULTS_ONLY` envelope row to `test_list_envelopes.py` covering
   `topics/recent/` and `users/experts/`.
2. Update the README's envelope section (and the module docstring, if it counts
   shapes) from four to five.
3. Extend `test_the_four_envelopes_are_actually_distinct` (and rename it
   honestly) to include the new shape.

## Acceptance Criteria

- [ ] `test_list_envelopes.py` asserts the envelope of both new routes.
- [ ] README/docstring shape count matches reality.
- [ ] Full package suite green.

## Work Log

### 2026-08-15 - Filed

- Out of scope for PR 2.5's final fix round (doc + test-table change spanning
  README/docstring); filed instead.
