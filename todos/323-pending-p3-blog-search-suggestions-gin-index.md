---
status: pending
priority: p3
issue_id: "323"
tags: [backend, blog, api, performance, database]
dependencies: []
---

# `search_suggestions` uses `title__icontains` with no GIN trigram index — add one now that it's routed

## Problem

`BlogPostPageViewSet.search_suggestions` (routed in todo 307) does
`BlogPostPage.objects.live().public().filter(title__icontains=query)` —
a substring lookup with no supporting GIN trigram index. Per
`docs/rules/database.md`: "Add GIN indexes for `__icontains` / full-text
search columns; plain B-tree indexes do not accelerate substring
search." This endpoint was unreachable before todo 307 (no `path()`
entry), so the missing index never mattered in practice; now it's a
live, public, unauthenticated endpoint.

## Findings

- Surfaced by `kimi-review` (WARNING) while codifying todo 307:
  *"`search_suggestions` uses `title__icontains` which requires a GIN
  index for acceptable performance on any non-trivial dataset. Verify
  that a GIN index exists on the `title` column of `BlogPostPage` (or
  add one via a migration) now that this endpoint is routed and
  reachable."*
- Confirmed via `grep`: no `GinIndex`/`trigram`/`pg_trgm` reference
  anywhere in `apps/blog/migrations/` or `apps/blog/models.py`.
  `BlogPostPage.search_fields` uses Wagtail's own `index.SearchField`
  (full-text search backend), which is a **separate** mechanism from a
  plain-Postgres `title__icontains` ORM filter — it does not help this
  query.
- Not urgent today: current dataset is small (dev/early-prod scale), so
  a sequential scan is cheap. Becomes a real cost once the blog has a
  meaningful number of posts.
- Same class of issue as the `by_category`/`related`-adjacent GIN-index
  guidance already documented in `docs/rules/database.md`; this todo is
  just applying it to a newly-live endpoint, not a novel pattern.

## Recommended Action

1. Add a migration enabling the `pg_trgm` extension (if not already
   enabled — check `backend/plant_community_backend/settings.py` /
   existing migrations for `TrigramExtension` first) and a `GinIndex`
   with `opclasses=["gin_trgm_ops"]` on `BlogPostPage.title`.
2. Confirm with `EXPLAIN ANALYZE` that `title__icontains` now uses the
   index (Bitmap Index Scan) instead of a sequential scan.
3. Consider whether the same treatment is worth it for
   `search_suggestions`'s tag-name lookup
   (`Tag.objects.filter(name__icontains=query, ...)`) — `taggit`'s `Tag`
   model may already have appropriate indexing; check before assuming
   it needs the same fix.

## Technical Details

- `backend/apps/blog/api/viewsets.py` — `search_suggestions` action
  (title-match query around `title__icontains=query`).
- `backend/apps/blog/models.py` — `BlogPostPage` model, would need the
  `GinIndex` added to `Meta.indexes`.
- Pattern reference: `backend/docs/patterns/performance/query-optimization.md`
  ("Add GIN indexes for `__icontains`" rule).
- Related: todo 307 (routed this action; this todo addresses a
  performance gap the routing surfaced, not a correctness bug).

## Acceptance Criteria

- [ ] `BlogPostPage.title` has a GIN trigram index (migration + model
      `Meta.indexes` entry).
- [ ] `EXPLAIN ANALYZE` on the `title__icontains` query shows an index
      scan, not a sequential scan, against a dataset large enough to
      matter (or a documented note that Postgres's planner still
      prefers seq scan below some row count, which is expected/fine).

## Work Log

### 2026-08-31 - Filed

- Filed while codifying todo 307 (blog viewset routing) — `kimi-review`
  flagged the missing index on the newly-reachable `search_suggestions`
  endpoint. Not blocking merge (small dataset today), filed as p3
  follow-up rather than expanding todo 307's scope with a migration.

## Notes

- p3: performance/scalability concern, not a correctness bug — the
  endpoint returns correct results today, just via a seq scan.
