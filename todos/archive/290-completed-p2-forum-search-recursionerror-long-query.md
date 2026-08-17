---
status: completed
priority: p2
issue_id: "290"
tags: [forum, search, availability, security]
dependencies: []
---

# Forum search 500s (RecursionError) on a many-term query

## Problem

`GET /api/v1/forum/search/?q=<~500 space-separated terms>` returns **500**
(`RecursionError`) on the **anonymous, public** search endpoint. A ~1-request
unauthenticated 500 with a cheap payload is an availability/DoS-amplification
concern: each hit burns a worker through a deep recursion before failing, and the
per-IP `search` throttle (30/m) still permits 30 of them per minute per IP.

Found incidentally while writing todo 275's semantic-search tests (2026-07-29).
It is **pre-existing and unrelated** to that change — reproduced on the plain FTS
path with no `?semantic=` param involved.

## Findings

Empirically probed against the real endpoint (throwaway test, backend venv):

```
500-term plain search (no semantic param) -> 500
100-term plain search                     -> 200
single 3500-char term                     -> 200
```

- So the trigger is **term count**, not query length — a single long token is
  fine. The recursion is in Wagtail's search-query parsing/AND-tree construction,
  which nests one level per term.
- Logged as `apps.core.exceptions … "Unhandled exception: RecursionError"` then
  `"Internal Server Error: /api/v1/forum/search/"`.
- `SearchView` (`backend/packages/wagtail_forum/wagtail_forum/api/views.py:1247`)
  caps `page` (`MAX_PAGE`) but applies **no bound to `q`** — neither length nor
  term count — before handing it to `backend.search(...)`.
- Contrast: the semantic path *does* bound its query
  (`constants.SIMILAR_QUERY_MAX_CHARS = 500`, applied in
  `apps/forum_host/semantic_search.py`) because embedding cost scales with input.
  Todo 275's test uses one long token specifically to avoid this bug.

## Recommended Action

1. Bound the query in the package `SearchView` before it reaches the search
   backend — a term-count cap is the one that matches the failure mode, plus a
   length cap for good measure. Both belong in the package's `conf.py`
   defaults (host-overridable), not hardcoded.
2. Decide the posture deliberately: **truncate** the term list (keeps the search
   useful, silently ignores the tail) vs **400** (honest, but breaks a client that
   pastes a paragraph into the box). Truncation matches the semantic path's
   existing behaviour and is the recommended default.
3. Pin it with a test at the failing shape (`"tomato " * 500` → 200, not 500) so
   the regression cannot return.
4. Check the sibling search surfaces for the same unbounded `q`:
   `UserMentionSearchView` (`api/user_search.py`) and any blog search path.

## Technical Details

- `backend/packages/wagtail_forum/wagtail_forum/api/views.py` — `SearchView.get`,
  `MAX_PAGE`/`PAGE_SIZE` precedent for where a bound belongs.
- `backend/packages/wagtail_forum/wagtail_forum/conf.py` — where the new
  `SEARCH_MAX_*` defaults go (host-overridable, per the package's settings
  contract).
- `backend/apps/forum_host/semantic_search.py` + `constants.SIMILAR_QUERY_MAX_CHARS`
  — the existing bounded-query precedent to mirror.
- Rule reference: `docs/rules/api.md` ("validate at the boundary").

## Acceptance Criteria

- [x] `GET /api/v1/forum/search/?q=<500 terms>` returns 200, not 500
- [x] The cap lives in the package's settings defaults, host-overridable — no
      magic number in the view
- [x] Test pins the exact failing shape (`"tomato " * 500`) and would fail if the
      cap is removed
- [x] `UserMentionSearchView` (and any other unbounded `q` surface found) either
      carries the same bound or is documented as not vulnerable

## Work Log

### 2026-07-29 - Found while testing todo 275 (M12 semantic search)

- Isolated with a throwaway probe test proving the plain FTS path 500s with no
  semantic involvement; probe deleted after confirming.
- Not fixed in todo 275: unrelated to that todo's scope (AI round 2), and the fix
  is a behaviour change to a public package endpoint that deserves its own
  decision on truncate-vs-400.

### 2026-08-17 - Started by completing-todos skill (run 2026-08-17-0246)

- Picked up by automated workflow.

### 2026-08-17 - Implemented and verified

- Added `SEARCH_MAX_TERMS` (50) and `SEARCH_MAX_QUERY_CHARS` (500) to
  `wagtail_forum/conf.py` DEFAULTS (host-overridable, documented in README.md).
- `SearchView.get` (`packages/wagtail_forum/wagtail_forum/api/views.py`) now
  truncates `q` to the char cap, then to the term cap, before it reaches
  `backend.search(...)`. Truncate posture per the todo's recommendation.
- `UserMentionSearchView` uses a plain `istartswith` ORM filter, never calls
  the modelsearch backend — documented as not vulnerable in a code comment.
  No other `backend.search(...)` call site exists outside `SearchView`
  (grepped `apps/blog`, `apps/forum_host`, package).
- Tests added: package-level `test_search_many_term_query_returns_200_not_500`
  (pins the exact failing shape) and
  `test_search_term_count_is_bounded_before_reaching_backend` (asserts the
  backend actually receives 50 terms, not 500); host-mount-level
  `test_search_many_term_query_is_bounded_not_500` in
  `apps/forum_host/tests/test_api_mounted.py` (SearchView is throttle-subclassed
  at the host layer — package tests alone don't exercise that path).

  ```
  $ python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py \
      apps/forum_host/tests/test_api_mounted.py \
      packages/wagtail_forum/wagtail_forum/tests/api/test_user_search.py -q
  30 passed, 1 warning in 16.81s
  ```

- Full package + host suite (regression check, no Topic list field touched so
  the narrower subset — not the whole-repo pytest — is sufficient per
  `docs/rules/testing.md`):

  ```
  $ python -m pytest packages/wagtail_forum apps/forum_host -q
  767 passed, 2 warnings in 140.34s
  ```

  (First run caught `test_readme_documents_every_setting` failing on the two
  new settings — fixed by documenting them in `packages/wagtail_forum/README.md`;
  re-run above is green.)
- All 4 acceptance criteria verified and checked off above.

### 2026-08-17 - Completed by completing-todos skill (run 2026-08-17-0246)

- Verification: all 4 acceptance criteria passed, including a red/green
  mutation check (git-stashed the fix, confirmed the pinning test actually
  fails with 500 before restoring it).
- Review: `code-review-orchestrator` dispatched against the 7 changed files
  (package + host layers), 0 findings (critical/high/medium/low), after a
  follow-up round to include two files edited after the initial dispatch.

## Notes

p2 rather than p1: it needs a deliberately malformed query, there is no data
exposure, and the forum currently has little traffic. It is still an anonymous
500 on a public endpoint, so it should not sit indefinitely.
