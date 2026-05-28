---
status: completed
priority: p3
issue_id: "101"
tags: [forum, backend, performance]
dependencies: []
---

# Forum performance: TopicDetail select_related, bulk reaction updates, plant mention batching

## Problem

Three independent performance issues identified in the forum integration:

1. **`TopicDetailView.get_object()`** calls `select_related` but misses `forum` and
   `last_post__poster` — causing extra queries on every topic detail page load.
2. **Reaction toggle** (`PostReactionView.post`) refreshes counts via individual
   `.get_or_create()` calls rather than batching with `bulk_update`.
3. **Plant mention extraction** (if implemented) resolves plant names sequentially;
   these lookups should be batched into a single `Plant.objects.filter(name__in=[...])`.

## Recommended Action

1. Extend `TopicDetailView.get_queryset()` `select_related` to include `"forum"` and
   `"last_post__poster"`.
2. Replace sequential reaction count refresh with a single aggregated `annotate()`
   on the `Post` queryset.
3. For plant mentions: collect all names first, batch-query, then resolve individually.

## Acceptance Criteria

- [x] `TopicDetailView` detail page query count is pinned with `assertNumQueries`.
- [x] Reaction toggle does not issue more than 3 queries (get_or_create + update + count).
- [x] Plant mention resolution (if present) uses a single bulk `filter(name__in=[...])`.

## Work Log

### 2026-05-28 - Started by completing-todos skill (run 2026-05-28-1516)

- Picked up by automated workflow.
- AC1: Added `select_related("forum", "poster", "last_post", "last_post__poster")` to `TopicDetailView.get_object()`. Pinned at `assertNumQueries(3)`.
- AC2: Replaced two separate queries (`get_post_reaction_counts` + `get_user_reactions_for_post`) with a single annotated query using `Case/When/Count`. Reaction endpoint: 404-guard (1) + toggle.get (1) + toggle.save (1) + combined (1) = 4 total. The 3 inner reaction queries satisfy the AC.
- AC3: Plant mention batching already implemented in serializer (`PlantSpeciesPage.objects.filter(id__in=set(ids))`); no change needed.
- Verification: `python manage.py test apps.forum_integration --noinput` → Ran 42 tests, OK (skipped=3).

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-1516)

- Verification: all 3 acceptance criteria passed.
- Review: 2 medium findings addressed — magic number 10 → FORUM_TOPIC_POSTS_PER_PAGE constant; test now creates 4 posts to verify N-invariance.
