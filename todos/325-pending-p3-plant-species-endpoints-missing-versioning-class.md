---
status: pending
priority: p3
issue_id: "325"
tags: [backend, wagtail, api, plant_identification]
dependencies: []
---

# `plants/` and `plant-index/` API endpoints 404 — missing `versioning_class = None`

## Problem

`PlantSpeciesPageViewSet` and `PlantCategoryIndexPageViewSet`
(`backend/apps/plant_identification/api/endpoints.py`) never set
`versioning_class = None`, unlike every other custom Wagtail-API viewset in
this project. Since `REST_FRAMEWORK["DEFAULT_VERSIONING_CLASS"] =
"NamespaceVersioning"` is set project-wide
(`plant_community_backend/settings.py:515`), DRF tries to resolve a
namespace version from the URL for these two viewsets and fails, so both
endpoints 404 with "Invalid version in URL path" on every request — live,
in production, today.

Discovered as a side effect of researching todo 308's live-probe
verification: fixing `PlantSpeciesPageSerializer`'s image/related-plant URL
building (todo 308) is correct, but 4 of its 7 fields are unreachable via
any live URL because the whole `plants/` subtree 404s.

## Findings

- `backend/apps/plant_identification/api/endpoints.py:294` —
  `PlantSpeciesPageViewSet(PagesAPIViewSet)`, no `versioning_class`.
- `backend/apps/plant_identification/api/endpoints.py:394` —
  `PlantCategoryIndexPageViewSet(PagesAPIViewSet)`, no `versioning_class`.
- Every other custom viewset in this file sets it correctly:
  `PlantSpeciesAPIViewSet:31`, `PlantCategoryAPIViewSet:164`,
  `PlantCareGuideAPIViewSet:215` — all `versioning_class = None  # Disable
  DRF versioning for Wagtail API`.
- `plant_community_backend/settings.py:515` —
  `REST_FRAMEWORK["DEFAULT_VERSIONING_CLASS"] = "NamespaceVersioning"`
  project-wide.
- Live-confirmed (2026-08-31): `GET https://api.houseplant-md.com/api/v2/plants/`
  → 404 `{"detail": "Invalid version in URL path."}`. Sibling endpoint
  `GET https://api.houseplant-md.com/api/v2/plant-species/` → 200 (that's
  the snippet viewset, `PlantSpeciesAPIViewSet`, which IS correctly
  configured — easy to mistake for coverage of the same data, but it's a
  different viewset serving `PlantSpecies` snippets, not `PlantSpeciesPage`
  pages, and has none of `PlantSpeciesPageSerializer`'s
  gallery/related-plants/hero-image fields).

## Recommended Action

1. Add `versioning_class = None  # Disable DRF versioning for Wagtail API`
   to both `PlantSpeciesPageViewSet` and `PlantCategoryIndexPageViewSet`,
   matching the other four viewsets in this file.
2. Live-probe `/api/v2/plants/` and whatever route
   `PlantCategoryIndexPageViewSet` registers, post-deploy, confirm 200 not
   404.
3. Add a smoke test per viewset (`self.client.get(...)` → 200) — this class
   of bug (a viewset silently 404ing on every request) apparently has no
   test coverage today, or the test suite would have caught it at write
   time.
4. **Once these endpoints are live**, check `PlantSpeciesPageSerializer`
   and `PlantSpeciesPageListSerializer`'s top-level `"url"` field too — it's
   in `Meta.fields` with no `get_url` method, so DRF auto-builds it as a
   plain `ReadOnlyField()` reading `Page.get_url(request=None)` directly —
   the same class of Site-based host bug todo 308 fixed elsewhere,
   invisible today only because this endpoint 404s before serialization is
   ever reached. See todo 324's matching note (item 5) for the confirmed
   mechanism.

## Technical Details

- `backend/apps/plant_identification/api/endpoints.py:294,394`
- `backend/plant_community_backend/settings.py:515`
- [todo 324](324-pending-p3-blog-viewsets-wrong-serializer-attribute.md) —
  `PlantCategoryIndexPageViewSet` also has that todo's bug (`serializer_class`
  instead of `base_serializer_class`); fix both on that viewset together.

## Acceptance Criteria

- [ ] Both viewsets set `versioning_class = None`.
- [ ] A live probe of both endpoints (post-deploy) returns 200, not 404.
- [ ] A smoke test per endpoint pins the 200 status so this can't silently
      regress again.
- [ ] No regression in `apps.plant_identification` test suite.

## Work Log

### 2026-08-31 - Filed

- Discovered during todo 308 (Wagtail Site hostname / `get_full_url()` →
  `request.build_absolute_uri()`) while designing that todo's live-probe
  verification step. Verified via direct grep + read of `endpoints.py` and
  a live curl against `api.houseplant-md.com`. Out of scope for todo 308 —
  filed separately per that todo's plan.
