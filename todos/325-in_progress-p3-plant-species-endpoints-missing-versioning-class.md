---
status: in_progress
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

- [x] Both viewsets set `versioning_class = None`.
- [ ] A live probe of both endpoints (post-deploy) returns 200, not 404.
      **Not checked** — needs the actual Railway deploy to ship this fix
      first; same situation as todo 308's AC #1 and todo 324's AC #2 (see
      Work Log). Verified locally instead via the real Django test client
      hitting the real URLconf.
- [x] A smoke test per endpoint pins the 200 status so this can't silently
      regress again.
      `apps/plant_identification/tests/test_page_viewsets_versioning_and_wiring.py`
      — `PlantSpeciesPageViewSetVersioningTestCase` (list+detail) and
      `PlantCategoryIndexPageViewSetTestCase.test_list_endpoint_returns_200_not_404`.
      `python manage.py test apps.plant_identification.tests.test_page_viewsets_versioning_and_wiring --keepdb`
      → `Ran 5 tests ... OK`.
- [x] No regression in `apps.plant_identification` test suite.
      `python manage.py test apps --noinput` → `Ran 829 tests ... OK
      (skipped=8)` (full suite, not just this app, run fresh).

## Work Log

### 2026-08-31 - Filed

- Discovered during todo 308 (Wagtail Site hostname / `get_full_url()` →
  `request.build_absolute_uri()`) while designing that todo's live-probe
  verification step. Verified via direct grep + read of `endpoints.py` and
  a live curl against `api.houseplant-md.com`. Out of scope for todo 308 —
  filed separately per that todo's plan.

### 2026-08-31 - Started by completing-todos skill (run 2026-08-31-1849)

- Picked up by automated workflow (batched with 324/326/327).

### 2026-08-31 - Fixed, plus two further latent bugs it uncovered

- `versioning_class = None` added to both `PlantSpeciesPageViewSet` and
  `PlantCategoryIndexPageViewSet` as prescribed. `PlantCategoryIndexPageViewSet`
  also got todo 324's `get_serializer_class()` override fix in the same
  change (both bugs live on the same viewset, per this todo's own
  cross-reference to todo 324).
- Fixing the 404 immediately surfaced it was masking TWO further crashes
  (500s, not 404s) that had never been reachable before — required fixes,
  not scope creep, since the endpoint wouldn't actually work without them:
  1. **`ImproperlyConfigured` on `/api/v2/plants/`**: `Meta.fields` on
     `PlantSpeciesPageSerializer`, `PlantSpeciesPageListSerializer`, and
     `PlantCategoryIndexPageSerializer` all wrongly listed a literal
     `"meta"` string. Wagtail's `to_representation()` builds the `meta`
     sub-object itself from `self.meta_fields` — a serializer field
     literally named `"meta"` has no corresponding model attribute, so DRF's
     `build_unknown_field()` raised `ImproperlyConfigured` the instant any
     real object was serialized (invisible before only because the 404
     fired first). Removed `"meta"` from all three.
  2. **`AttributeError: no attribute 'meta_fields'`**: after fixing (1),
     `BaseSerializer.to_representation()`'s `self.meta_fields` read still
     crashed — Wagtail's dynamic `get_serializer_class()` factory normally
     injects `meta_fields` as an instance attribute, but bypassing that
     factory (required for todo 324's fix) means it's never set unless
     declared explicitly. Traced this through EVERY affected serializer,
     including ones nested as plain fields inside the Page serializers
     (`PlantSpeciesSerializer` nested in `plant_species`/`care_guide` chains,
     `PlantCategorySerializer` nested in `categories`, `PlantCareGuideSerializer`
     nested in `care_guide`) — each independently crashes the instant it's
     actually serialized, since DRF calls each nested serializer's own
     `to_representation()`. Added `meta_fields = ["type", "detail_url"]`
     (matching the one existing correct precedent in this codebase,
     `BlogCategorySerializer`) to all of: `PlantSpeciesPageSerializer`,
     `PlantSpeciesPageListSerializer`, `PlantCategoryIndexPageSerializer`,
     `PlantSpeciesSerializer`, `PlantCategorySerializer`,
     `PlantCareGuideSerializer`.
- A third bug (shared with todo 324, see that todo's Work Log for the full
  mechanism): `PlantSpeciesPageSerializer`, `PlantSpeciesPageListSerializer`,
  and `PlantCategoryIndexPageSerializer`'s `get_url` methods were silently
  never invoked — DRF's `ModelSerializer` auto-builds a real field for `url`
  from `Page`'s own same-named property whenever there's no *explicit*
  `url = serializers.SerializerMethodField()` declaration, even when a
  `get_url` method exists. Added the explicit declaration to all three,
  restoring todo 308's fix on a field that was about to start actually
  working for the first time (exactly the risk item 4 of this todo's
  Recommended Action flagged in advance).
- All three bugs were found via HTTP-level regression tests (hitting the
  real `/api/v2/` routes), not by static reading — each crashed with a
  distinct traceback the first time the endpoint was actually exercised
  end-to-end.

### 2026-08-31 - Verified, NOT archived (live-probe AC pending post-deploy)

- Full verification evidence quoted in the Acceptance Criteria section
  above. `python manage.py test apps --noinput` → `Ran 829 tests ... OK
  (skipped=8)`, run fresh right before this entry.
- **Per the `completing-todos` skill's verification gate, the live-probe AC
  cannot be flipped yet** — needs an actual Railway deploy first. Stays
  `in_progress`, matching todo 324 and todo 308's precedent. Once
  merged+deployed: `curl https://api.houseplant-md.com/api/v2/plants/` and
  `.../api/v2/plant-index/` should both return 200 (not 404) — record the
  output, check the AC, archive.
- Review: `code-review-orchestrator` ran on the full batch diff (todos
  324/325/326/327 as one diff) — 0 critical, 0 high, 1 medium, 1 low, 1
  info, all three verified as false positives against source — including
  its "medium" claim that `PlantSpeciesPageViewSet` was still missing
  `versioning_class`, directly re-checked here and confirmed present at
  `endpoints.py:297` (see todo 326's Work Log for the full detail —
  reviewer misread diff hunk-header line offsets). Nothing to repair.
