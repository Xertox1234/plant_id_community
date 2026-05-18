---
status: pending
priority: p2
issue_id: "079"
tags: [performance, n+1, audit-2026-05-17]
dependencies: []
source_review: "docs/audits/2026-05-17-full.md"
source_finding: "H2,H3,H4,H7,H8,H9,H10"
---

# Eliminate remaining N+1 query findings (serializer count methods)

## Problem

Seven N+1 query findings from the 2026-05-17 full audit were deferred because each
needs coordinated changes: a `Count()` annotation on the viewset queryset, a
serializer change, and (per audit C3) re-pinning a strict `assertNumQueries` test.
Three sibling N+1s (H5, H6, H11) were fixed in the audit; these seven remain.

## Findings

All from `docs/audits/2026-05-17-full.md` (performance-reviewer):

- **H2** — `BlogCategorySerializer.get_post_count` runs a COUNT per category
  (`backend/apps/blog/serializers.py:36`). Categories are nested in every blog
  post list, so ~36 extra COUNTs per page.
- **H3** — `BlogPostListSerializer.get_comment_count` / `BlogPostPageSerializer.get_comment_count`
  COUNT per post (`backend/apps/blog/serializers.py:216,173`).
- **H4** — `BlogSeriesSerializer.get_post_count` / `BlogAuthorSerializer.get_post_count`
  per-row COUNT (`backend/apps/blog/serializers.py:54,103`).
- **H7** — `GardenBedListSerializer.plant_count` annotation deliberately disabled;
  model property does 2 COUNT/bed (`backend/apps/garden_calendar/api/views.py:568-572`).
- **H8** — `CommunityEventListSerializer` `attendee_count`/`spots_remaining`/`user_rsvp_status`
  hit the DB per event (`backend/apps/garden_calendar/api/serializers.py:42`); model
  properties `.count()`/`.get()` bypass the existing `prefetch_related('attendees')`.
- **H9** — `get_results_count` `.count()` bypasses prefetch in 6 serializer locations
  (`backend/apps/plant_identification/serializers.py:331,91,143,383,469,572`).
  NOTE: only switch a location to `len(obj.<rel>.all())` where the viewset actually
  prefetches the relation — otherwise it loads all rows and is worse than `.count()`.
- **H10** — `PlantCategorySerializer.get_plant_count` per category
  (`backend/apps/plant_identification/api/serializers.py:99`).

## Recommended Action

1. For each finding, annotate the count on the viewset's `get_queryset()` with
   `Count(...)` (use `filter=Q(...)` for conditional counts) and have the
   serializer field read the annotation.
2. For nested serializers (H2 — categories inside blog posts), put the annotation
   on the `Prefetch` queryset, not the outer queryset.
3. For H8/H9, where a prefetch already exists, the lighter fix is
   `len(obj.<rel>.all())` — but verify the prefetch is present on every code path.
4. For H7, understand why the annotation was commented out ("Currently causes
   issues") before re-enabling — the model has both `plant_count` and
   `utilization_rate` that each count.
5. Add/update strict `assertNumQueries`/`CaptureQueriesContext` tests with the
   new exact query counts (see audit C3 — removing inefficiency lowers counts and
   breaks tests pinned to the old number).

## Technical Details

Pattern reference: `backend/docs/patterns/performance/query-optimization.md`
("SerializerMethodField counting must be a `Count()` annotation"). Audit C3 in
`docs/audits/2026-05-17-full.md` is a worked example of the annotation + test
re-pin flow.

## Acceptance Criteria

- [ ] Each of H2/H3/H4/H7/H8/H9/H10 no longer issues a per-row COUNT.
- [ ] Affected list endpoints have a strict `assertNumQueries` test at the new count.
- [ ] `python manage.py test apps.blog apps.garden_calendar apps.plant_identification --noinput` passes.

## Work Log

### 2026-05-17 - Created

- Deferred from the 2026-05-17 full audit (Phase 4) per user triage decision.
