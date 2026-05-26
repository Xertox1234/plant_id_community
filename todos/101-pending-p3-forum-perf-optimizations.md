---
status: pending
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

- [ ] `TopicDetailView` detail page query count is pinned with `assertNumQueries`.
- [ ] Reaction toggle does not issue more than 3 queries (get_or_create + update + count).
- [ ] Plant mention resolution (if present) uses a single bulk `filter(name__in=[...])`.
