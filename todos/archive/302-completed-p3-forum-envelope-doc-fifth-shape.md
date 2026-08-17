---
status: completed
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

- [x] `test_list_envelopes.py` asserts the envelope of both new routes.
- [x] README/docstring shape count matches reality.
- [x] Full package suite green.

## Work Log

### 2026-08-15 - Filed

- Out of scope for PR 2.5's final fix round (doc + test-table change spanning
  README/docstring); filed instead.

### 2026-08-17 - Started by completing-todos skill (run 2026-08-17-0246)

- Picked up by automated workflow.

### 2026-08-17 - Implemented

- Confirmed both routes empirically return `{"results": [...]}` only by
  reading `RecentTopicsView.get`/`ExpertsView.get`
  (`backend/packages/wagtail_forum/wagtail_forum/api/views.py:1793-1821,
  1861-1864`).
- Added `RESULTS_ONLY_ENVELOPE = {"results"}` to `test_list_envelopes.py`,
  a new `test_recent_topics_and_experts_are_the_results_only_envelope`
  asserting both `topics/recent/` and `users/experts/` against it, renamed
  `test_the_four_envelopes_are_actually_distinct` →
  `test_the_five_envelopes_are_actually_distinct` (now asserts `len(...) ==
  5`), and updated the module docstring's "four shapes" → "five shapes".
- Added a fifth table row to the README's `## List envelopes` section
  (`GET topics/recent/`, `GET users/experts/` → `{results}` — bare, no
  cursor, no `intro`) and changed "ships **four** list-collection shapes" →
  "**five**". Swept the file for other stale "four" references — the only
  other hit (`## Search backend`'s "so all four must be present") refers to
  the four Wagtail search backend apps, unrelated to envelopes; left as-is.
- Verification:
  ```
  $ python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_list_envelopes.py -v
  Pytest: 6 passed
  $ python -m pytest packages/wagtail_forum/ apps/forum_host/
  Pytest: 769 passed
  ```

### 2026-08-17 - Code review

- Dispatched `code-review-orchestrator` (triage-only this run — it routed to
  `cross-cutting-reviewer` and returned a dispatch prompt rather than
  invoking it itself), then dispatched `cross-cutting-reviewer` directly
  with that prompt.
- 2 medium findings, both accepted (verified against the file before
  fixing):
  1. README's "Mounting the API" `Routes:` sentence (line 173) enumerated
     every package endpoint group except `topics/recent/` and
     `users/experts/` — the exact routes this PR's envelope table now
     documents. Fixed: appended "recent topics, and community experts."
  2. README's `WAGTAILFORUM_PUBLIC_READ_CACHE_SECONDS` table row (line 258)
     listed the shared-cache-eligible anonymous endpoints as "board list,
     topic list, and search only" but `RecentTopicsView`/`ExpertsView` both
     mix in `PublicForumReadCacheMixin`
     (`wagtail_forum/api/views.py:1713,1833`) — confirmed by direct read.
     Fixed: added "recent topics, and experts rails" to the row.
- Both findings were pre-existing README gaps surfaced only because this
  PR's diff touches the same file/section — in scope as single-sentence
  additions adjacent to the lines already being edited, not scope creep.
- No test changes needed (README-only fix); re-ran the test file to confirm
  no regression: `pytest test_list_envelopes.py` → 6 passed.

### 2026-08-17 - Completed by completing-todos skill (run 2026-08-17-0246)

- Verification: all 3 acceptance criteria passed (test file 6/6, full
  package + host suite 769/769).
- Review: 2 medium findings from cross-cutting-reviewer, both repaired
  (README `Routes:` sentence + cache-TTL table row omitted the two new
  endpoints).
