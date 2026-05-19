---
status: completed
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

- [x] Each of H2/H3/H4/H7/H8/H9/H10 no longer issues a per-row COUNT.
- [x] Affected list endpoints have a strict `assertNumQueries` test at the new count.
- [x] `python manage.py test apps.blog apps.garden_calendar apps.plant_identification --noinput` passes.

## Work Log

### 2026-05-17 - Created

- Deferred from the 2026-05-17 full audit (Phase 4) per user triage decision.

### 2026-05-19 - Started by completing-todos skill (run 2026-05-19-0116)

- Picked up by automated workflow.

### 2026-05-19 - Blog app done (H2, H3, H4)

- `apps/blog/serializers.py`: `BlogCategorySerializer`/`BlogSeriesSerializer`/
  `BlogAuthorSerializer` `get_post_count` and both `get_comment_count` methods
  now read a `_post_count` / `_comment_count` annotation when present, falling
  back to the old COUNT otherwise.
- `apps/blog/views.py`: `BlogPostPageViewSet.get_queryset()` annotates
  `_comment_count` and Prefetches `categories`/`series` with a `_post_count`
  annotation; `BlogCategoryViewSet`/`BlogSeriesViewSet` class querysets and
  `BlogAuthorViewSet.get_queryset()` annotate `_post_count`.
- New `apps/blog/tests/test_n_plus_1.py` — 4 strict regression tests proving the
  COUNT-query total is constant as object count grows (small N == large N) for
  the posts/categories/series/authors list endpoints. Regression-checked:
  reverting an annotation makes a test fail.
- Verification: `python manage.py test apps.blog --noinput` → `Ran 177 tests` /
  `OK (skipped=7)` / exit 0.
- Out-of-scope finding: `/blog/authors/` also has an unrelated taggit N+1 on
  `expertise_areas` (one `taggit_tag` query per author) — not a serializer
  count field, so not fixed here; candidate for a follow-up todo.

### 2026-05-19 - garden_calendar app done (H7, H8)

- **H7**: `GardenBed.plant_count` model property now reads a `_plant_count`
  annotation when present. `GardenBedViewSet.get_queryset()` re-enables the
  annotation (previously commented out "causes issues") as `_plant_count` —
  the underscore avoids the AttributeError from annotating over the property.
  `utilization_rate` benefits transitively (it calls `self.plant_count`).
- **H8**: `CommunityEvent.attendee_count` property reads a `_attendee_count`
  annotation; the CommunityEvent list `get_queryset()` annotates it.
  `CommunityEventListSerializer.get_user_rsvp_status` iterates the prefetched
  `attendees` cache instead of `.get()` (no per-event query). `spots_remaining`
  benefits transitively.
- Tests: re-pinned two existing strict tests in `test_performance.py` that the
  fix improved — `test_garden_bed_list_no_n_plus_1` 12→2 queries,
  `test_garden_bed_detail_with_plants` 5→3 (matches the tests' own stated
  "Target"). Added `CommunityEventListPerformanceTest` — a relative-O(1)
  regression test for the events list endpoint.
- **Scope expansion (flagged)**: writing the CommunityEvent integration test
  surfaced a real pre-existing bug — `EventOrganizerSerializer` listed
  `avatar_thumbnail` (an imagekit `ImageSpecField`, not a model field) in
  `Meta.fields`, so every GET to the events list 500'd (non-serializable
  `CacheFile`). Fixed minimally with a `SerializerMethodField` mirroring
  `apps/users/serializers.py`. Unrelated to N+1 but required for the H8 test
  to reach a 200 response.
- Verification: `python manage.py test apps.garden_calendar --noinput` →
  `Ran 150 tests` / `OK (skipped=1)` / exit 0.

### 2026-05-19 - plant_identification app done (H9, H10)

- **H9**: the 4 `get_results_count` methods (`PlantIdentificationRequestSerializer`,
  `PlantDiseaseRequestSerializer`, and the two `WithResults` variants) read a
  `_results_count` annotation; `PlantDiseaseDatabaseSerializer.get_affected_plant_count`
  reads `_affected_plant_count`. `PlantIdentificationRequestViewSet`,
  `PlantDiseaseRequestViewSet`, `PlantDiseaseDatabaseViewSet` annotate these on
  `get_queryset()`. (`PlantIdentificationRequestWithResultsSerializer` is not
  wired to any live viewset; its method is made annotation-aware for
  consistency but no viewset annotates for it.)
- **H10**: `PlantCategorySerializer.get_plant_count` reads `_plant_count`;
  `PlantCategoryAPIViewSet.get_queryset()` annotates it (replacing the
  prefetch that previously fed the count); `PlantCategoryIndexPageSerializer.get_categories`
  annotates its inline queryset.
- Tests: new `apps/plant_identification/tests/test_n_plus_1.py` — relative-O(1)
  regression tests for requests-list, disease-requests-list, disease-database-list.
- Verification: `python manage.py test apps.plant_identification --noinput` →
  `Ran 108 tests` / `OK (skipped=1)` / exit 0.
- **Pre-existing bug fixed (bundled, user-approved)**: `PlantCategoryAPIViewSet`
  and `PlantCareGuideAPIViewSet` (`api/endpoints.py`) were missing
  `versioning_class = None` — unlike `PlantSpeciesAPIViewSet` (line 31) — so DRF
  `NamespaceVersioning` rejected every request ("Invalid version in URL path");
  both endpoints were unreachable. Added the one-line `versioning_class = None`
  to each, enabling the endpoints. The H10 `PlantCategory` N+1 test is now
  un-skipped and passing.

### 2026-05-19 - Completed by completing-todos skill (run 2026-05-19-0116)

- Verification: all 3 acceptance criteria pass.
  `python manage.py test apps.blog apps.garden_calendar apps.plant_identification --noinput`
  → `Ran 435 tests in 101.384s` / `OK (skipped=8)` / exit 0.
- Each H-finding's per-row COUNT is replaced by a queryset annotation; the new
  `test_n_plus_1.py` files (blog, plant_identification) plus the re-pinned /
  extended `garden_calendar/tests/test_performance.py` give every affected list
  endpoint a strict regression test.
- Two pre-existing bugs surfaced and fixed (both user-approved as bundled):
  the `EventOrganizerSerializer.avatar_thumbnail` 500 and the
  `versioning_class` viewset bug.
- Out-of-scope finding logged for a follow-up todo: `/blog/authors/` taggit
  N+1 on `expertise_areas`.
- Review: code-review-orchestrator dispatched (django-drf / wagtail / api-design
  / performance / test-quality) — 0 critical, 0 high, 1 medium (non-blocking).

#### Known issues — medium, accepted

- The blog `_post_count` annotations filter `Q(blogpostpage__live=True)`, i.e.
  `.live()` semantics, not `.live().public()`. `.public()` additionally excludes
  PageViewRestriction pages. This is the **same accepted divergence already
  documented as Pattern 29** in `docs/patterns/performance/query-optimization.md`
  (established by todo 075): the blog uses no `PageViewRestriction` objects, so
  `.live()` and `.live().public()` return identical counts in practice. The
  H2/H3/H4 annotations extend that same known-benign pattern; no action taken.
