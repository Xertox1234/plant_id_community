---
status: completed
priority: p2
issue_id: "072"
tags: [api-design, validation, security, blog, viewsets]
dependencies: []
source_review: "docs/reviews/2026-05-07-1641-full-review.md"
source_finding: "40"
---

# Blog api/viewsets.py: bare int() casts and unescaped search return 500s

## Problem

Four places in `backend/apps/blog/api/viewsets.py` use bare `int()` on query-string
parameters with no `try/except ValueError`. Non-numeric input (e.g. `limit=abc`) raises
an unhandled exception and returns HTTP 500 instead of 400. Additionally, `listing_view`
has a division `offset // limit` that raises `ZeroDivisionError` when `limit=0`.
A fifth issue: `search_suggestions` passes the raw query directly to `icontains` without
`escape_search_query()` wildcard escaping.

## Findings

All in `backend/apps/blog/api/viewsets.py`:

- **#40** Line ~300: `recent()` — `limit = int(request.GET.get("limit", 10))` with no
  error handling and no upper bound cap.
- **#42** Line ~322: `popular()` — `days = int(request.GET.get("days", ...))` has no
  `try/except` (the `limit` param is capped but `days` is not protected).
- **#46** Line ~422: `search_suggestions` — `name__icontains=query` with raw user input,
  no `escape_search_query()` call.
- **#49** Line ~504: `listing_view` — `offset = int(...)` and `limit = int(...)` both
  bare; if `limit=0` the subsequent `offset // limit` raises `ZeroDivisionError`.

Source: 2026-05-07-1641 full review, `api-design-reviewer` and `wagtail-reviewer`.

## Recommended Action

1. Wrap all four `int()` calls in `try/except ValueError` and return
   `Response({'error': 'invalid parameter'}, status=400)` on failure:
   ```python
   try:
       limit = int(request.GET.get("limit", 10))
   except ValueError:
       return Response({"error": "limit must be an integer"}, status=400)
   ```
2. Cap `recent` `limit` with a `MAX_LIMIT` constant (follow `POPULAR_POSTS_MAX_LIMIT`
   precedent already set for `popular`).
3. In `listing_view`, guard against `limit <= 0` after parsing.
4. In `search_suggestions`, import and apply `escape_search_query()` to `query` before
   any `icontains` filter.

## Technical Details

- File: `backend/apps/blog/api/viewsets.py`
- Constant to add: `RECENT_POSTS_MAX_LIMIT = 50` (or reuse `POPULAR_POSTS_MAX_LIMIT`).
- Search escaping helper: `apps.core.utils.query_sanitization.escape_search_query`
- Pattern docs:
  - `backend/docs/patterns/architecture/rate-limiting.md` (error response shapes)
  - `backend/docs/patterns/security/input-validation.md` (wildcard escaping)

## Acceptance Criteria

- [x] `recent()` wraps int() in try/except ValueError → 400; capped at RECENT_POSTS_MAX_LIMIT=50.
- [x] `popular()` wraps both limit and days in try/except → 400.
- [x] `listing_view` wraps offset/limit in try/except → 400; guards limit <= 0.
- [x] RECENT_POSTS_DEFAULT_LIMIT and RECENT_POSTS_MAX_LIMIT added to blog/constants.py.
- [x] `search_suggestions` applies `escape_search_query(query)` before both icontains filters.
- [x] 158 blog tests pass (7 skipped): `python manage.py test apps.blog.tests --noinput`.

## Work Log

### 2026-05-09 - Completed by completing-todos skill (run 2026-05-09-1435)

- Verification: all 6 acceptance criteria passed; 158 tests pass.
- Review: 2 high repaired (missing limit <= 0 guard in recent(); limit <= 0 and days < 0
  guards in popular()); 0 remaining blocking findings.

### 2026-05-09 - Started by completing-todos skill (run 2026-05-09-1435)

- Picked up by automated workflow.

### 2026-05-09 - Created from review 2026-05-07-1641

- Findings #40, #42, #46, #49: bare int() casts and unescaped icontains in viewsets.py.
