---
status: pending
priority: p3
issue_id: "088"
tags: [performance, n+1, blog]
dependencies: []
---

# Blog authors endpoint: N+1 on `expertise_areas` taggit field

## Problem

The `/blog/authors/` list endpoint (`BlogAuthorViewSet`, `apps/blog/views.py`)
issues one `taggit_tag` query per author. `BlogAuthorSerializer.expertise_areas`
is a `TagListSerializerField` (django-taggit); each author serialized triggers a
separate query to resolve its tags — a textbook N+1 that scales with the number
of authors on the page.

## Findings

- Discovered while writing the N+1 regression tests for todo 079. It is **not**
  a serializer count field, so it was out of scope for 079 (which covered
  `get_post_count` / `get_comment_count` / `get_results_count` style COUNTs).
- `BlogAuthorViewSet.get_queryset()` already `select_related('author')` and
  (since todo 079) annotates `_post_count`, but does not prefetch the tagged
  `expertise_areas` relation.

## Recommended Action

1. Add `.prefetch_related('expertise_areas')` to `BlogAuthorViewSet.get_queryset()`
   in `apps/blog/views.py` so taggit resolves all authors' tags in one query.
2. Verify `BlogAuthorSerializer.expertise_areas` (a `TagListSerializerField`)
   reads from the prefetch cache — taggit's `TaggableManager` supports
   `prefetch_related` on the tag relation.

## Technical Details

- Endpoint: `BlogAuthorViewSet` — `apps/blog/views.py`
- Serializer: `BlogAuthorSerializer.expertise_areas` — `apps/blog/serializers.py`
- Pattern reference: `backend/docs/patterns/performance/query-optimization.md`

## Acceptance Criteria

- [ ] `/blog/authors/` list issues a constant number of `taggit_tag` queries
      regardless of author count (verified by a strict query-count test —
      extend `apps/blog/tests/test_n_plus_1.py`).
- [ ] `python manage.py test apps.blog --noinput` passes.

## Work Log

### 2026-05-19 - Created

- Surfaced during todo 079 (N+1 serializer counts) — flagged as an out-of-scope
  sibling N+1 on the same endpoint and deferred to this follow-up.
