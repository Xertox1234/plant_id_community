---
status: pending
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

- [ ] `GET /api/v1/forum/search/?q=<500 terms>` returns 200, not 500
- [ ] The cap lives in the package's settings defaults, host-overridable — no
      magic number in the view
- [ ] Test pins the exact failing shape (`"tomato " * 500`) and would fail if the
      cap is removed
- [ ] `UserMentionSearchView` (and any other unbounded `q` surface found) either
      carries the same bound or is documented as not vulnerable

## Work Log

### 2026-07-29 - Found while testing todo 275 (M12 semantic search)

- Isolated with a throwaway probe test proving the plain FTS path 500s with no
  semantic involvement; probe deleted after confirming.
- Not fixed in todo 275: unrelated to that todo's scope (AI round 2), and the fix
  is a behaviour change to a public package endpoint that deserves its own
  decision on truncate-vs-400.

## Notes

p2 rather than p1: it needs a deliberately malformed query, there is no data
exposure, and the forum currently has little traffic. It is still an anonymous
500 on a public endpoint, so it should not sit indefinitely.
