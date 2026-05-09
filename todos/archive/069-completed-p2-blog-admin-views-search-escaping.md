---
status: completed
priority: p2
issue_id: "069"
tags: [security, blog, input-validation, search]
dependencies: []
source_review: "docs/reviews/2026-05-07-1641-full-review.md"
source_finding: "25"
---

# Blog admin_views: icontains without wildcard escaping

## Problem

Four `icontains` filters in `backend/apps/blog/admin_views.py` pass raw user-supplied
query strings directly to Django ORM. PostgreSQL LIKE wildcards (`%`, `_`) in the query
are not escaped, allowing wildcard injection that can affect search result sets and
load patterns. The project-wide fix is `escape_search_query()` from
`apps.core.utils.query_sanitization`.

## Findings

- `backend/apps/blog/admin_views.py` line ~81: content/author/title search uses
  `icontains=search_query` without escaping — review finding #25.
- Line ~267: post title/description/introduction search uses `icontains=query` without
  escaping — review finding #26.
- Line ~283: comment content/author search uses `icontains=query` without escaping
  — review finding #27.
- Line ~290: category name/description search uses `icontains=query` without escaping
  — review finding #28.
- Source: 2026-05-07-1641 full review, `django-drf-reviewer`.

## Recommended Action

1. Import `escape_search_query` at the top of `admin_views.py` (check if already
   imported elsewhere in the file first).
2. For each affected search block, wrap the query variable before it is used in any
   `icontains` filter:
   ```python
   safe_query = escape_search_query(search_query)
   # then use safe_query in all icontains filters
   ```
3. Apply to all four call sites (lines ~81, ~267, ~282, ~290).

## Technical Details

- File: `backend/apps/blog/admin_views.py`
- Helper: `apps.core.utils.query_sanitization.escape_search_query`
- Pattern doc: `backend/docs/patterns/security/input-validation.md`
- Companion findings for same pattern across the blog module (higher finding numbers,
  lower priority): viewsets.py search_suggestions (#46), views.py (#71, #77, #78).

## Acceptance Criteria

- [x] `escape_search_query()` applied to all four icontains call sites in `admin_views.py`.
- [x] A query containing `%` or `_` does not produce wildcard expansion — all 8 icontains
      filters use `safe_query = escape_search_query(...)` (grep confirmed, lines 81, 83–85, 266, 270–272, 285–286, 293–294).
- [x] `python manage.py test apps.blog.tests --noinput` passes (158 tests, 7 skipped, 0 failures).

## Work Log

### 2026-05-09 - Completed by completing-todos skill (run 2026-05-09-1435)

- Verification: all 3 acceptance criteria passed.
  - escape_search_query() applied at lines 81 and 266; all 8 icontains filters use safe_query.
  - grep confirms no raw icontains=query or icontains=search_query remain.
  - 158 blog tests pass (7 skipped, 0 failures).
- Review: 2 low (missing .strip() — repaired both); 2 info (accepted).
- .strip() added before escape_search_query() at both search_query and query fetch sites.

### 2026-05-09 - Started by completing-todos skill (run 2026-05-09-1435)

- Picked up by automated workflow.

### 2026-05-09 - Created from review 2026-05-07-1641

- Findings #25–#28: four icontains without escape_search_query in admin_views.py.
- Security/runtime findings #4, #11, #13, #16–#22 all confirmed already fixed in
  current code; these blog admin escaping findings are the open security work.
