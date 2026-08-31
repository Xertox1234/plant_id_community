---
status: pending
priority: p3
issue_id: "324"
tags: [backend, wagtail, api, blog]
dependencies: []
---

# Four page-detail viewsets set `serializer_class`, a plain DRF attribute Wagtail never reads — 4 custom serializers are dead code

## Problem

`BlogAuthorPageViewSet`, `BlogIndexPageViewSet`, `BlogCategoryPageViewSet`
(`backend/apps/blog/api/viewsets.py`), and `PlantCategoryIndexPageViewSet`
(`backend/apps/plant_identification/api/endpoints.py`) each set
`serializer_class = <Custom Serializer>` to wire in their custom serializer.
That's a plain DRF `GenericAPIView` attribute — Wagtail's
`BaseAPIViewSet.get_serializer_class()` reads `base_serializer_class`
instead, never `serializer_class`. All four viewsets silently fall back to
Wagtail's stock `PageSerializer`, so `BlogAuthorPageSerializer`,
`BlogIndexPageSerializer`, `BlogCategoryPageSerializer`, and
`PlantCategoryIndexPageSerializer` never actually serialize anything on the
live endpoints — their custom fields (`author`, `bio`, `recent_posts`,
`featured_posts`, `category`, `posts`, `categories`, `featured_plants`, etc.)
are all dead code.

`PlantCategoryIndexPageViewSet` also lacks `versioning_class = None` — a
second, independent bug filed separately as todo 325, since that one 404s
the endpoint entirely rather than degrading its response shape. Fix both on
that one viewset; neither fix alone makes it work.

Discovered as a side effect of researching todo 308's live-probe
verification: fixing `BlogAuthorPageSerializer.get_recent_posts`'s URL
building (todo 308) is correct, but not live-verifiable via
`/api/v2/blog-authors/` today, because that field never appears in the
response at all.

## Findings

- `backend/apps/blog/api/viewsets.py:713,723,733` — `serializer_class =
  BlogIndexPageSerializer` / `BlogCategoryPageSerializer` /
  `BlogAuthorPageSerializer`, each on a `PagesAPIViewSet` subclass.
- `backend/apps/plant_identification/api/endpoints.py:397` —
  `PlantCategoryIndexPageViewSet.serializer_class = PlantCategoryIndexPageSerializer`
  (class defined at line 394). See todo 325 for this same viewset's other,
  independent bug (missing `versioning_class`).
- `venv/lib/python3.13/site-packages/wagtail/api/v2/views.py:52` —
  `BaseAPIViewSet.base_serializer_class = BaseSerializer` (the actual
  attribute `get_serializer_class()` reads, line 357/360).
- The correctly-wired pattern already exists in this project:
  `backend/apps/plant_identification/api/endpoints.py:32,165,216` all use
  `base_serializer_class = ...` for their snippet viewsets.
- Live-confirmed (2026-08-31): `GET https://api.houseplant-md.com/api/v2/blog-authors/`
  returns 200 with only stock Wagtail page fields (`id`, `title`, `slug`,
  `meta`) — no `author`, `bio`, `expertise_areas`, `social_links`,
  `post_count`, or `recent_posts`. `PlantCategoryIndexPageViewSet` couldn't
  be live-probed for this bug specifically — it 404s outright (todo 325)
  before serialization is ever reached.
- `BlogPostPageViewSet` (the main blog-post endpoint) does NOT have this bug
  — it overrides `get_serializer_class()` directly instead of setting a class
  attribute (`viewsets.py:70-86`), so it's unaffected.

## Recommended Action

1. In `backend/apps/blog/api/viewsets.py`, rename `serializer_class` to
   `base_serializer_class` on `BlogIndexPageViewSet`, `BlogCategoryPageViewSet`,
   and `BlogAuthorPageViewSet`.
2. In `backend/apps/plant_identification/api/endpoints.py`, same rename on
   `PlantCategoryIndexPageViewSet` — and add the `versioning_class = None`
   fix from todo 325 at the same time, since fixing only one leaves the
   endpoint either 404ing or still serializing with the stock serializer.
3. Live-probe each endpoint after deploy
   (`/api/v2/blog-authors/<id>/`, `/api/v2/blog-index/<id>/` or whatever the
   registered route is, `/api/v2/blog-categories/<id>/` if page-routed, and
   `PlantCategoryIndexPageViewSet`'s route once todo 325 also lands) and
   confirm the custom fields now appear.
4. Add a regression test per viewset asserting the custom field is present
   in the response (the class of bug this todo describes has no test
   coverage today specifically because the fields silently vanish rather
   than erroring — see `docs/rules/testing.md`'s `SkipField`/silent-omission
   guidance, and this session's memory:
   `project_drf_skipfield_silent_omission.md`, a close cousin of this exact
   failure mode).

## Technical Details

- `backend/apps/blog/api/viewsets.py:709-734`
- `backend/apps/blog/api/serializers.py`: `BlogIndexPageSerializer` (555),
  `BlogCategoryPageSerializer` (652), `BlogAuthorPageSerializer` (151).
- `backend/apps/plant_identification/api/endpoints.py:394-400`
  (`PlantCategoryIndexPageViewSet`); its serializer,
  `PlantCategoryIndexPageSerializer`, is in
  `backend/apps/plant_identification/api/serializers.py`.
- [todo 325](325-pending-p3-plant-species-endpoints-missing-versioning-class.md)
  — the other bug on `PlantCategoryIndexPageViewSet`.

## Acceptance Criteria

- [ ] All four viewsets use `base_serializer_class`, not `serializer_class`.
- [ ] A live probe of each affected endpoint (post-deploy) shows the custom
      fields in the response.
- [ ] A regression test per viewset pins presence of at least one custom
      field so this can't silently regress again.
- [ ] No regression in `apps.blog` or `apps.plant_identification` test suites.

## Work Log

### 2026-08-31 - Filed

- Discovered during todo 308 (Wagtail Site hostname / `get_full_url()` →
  `request.build_absolute_uri()`) while designing that todo's live-probe
  verification step. Verified via direct grep + read of `viewsets.py` and
  Wagtail's `BaseAPIViewSet` source, plus a live curl against
  `api.houseplant-md.com`. Out of scope for todo 308 — filed separately per
  that todo's plan.
