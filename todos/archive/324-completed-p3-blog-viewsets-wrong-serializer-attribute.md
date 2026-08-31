---
status: completed
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

**PR split note**: this todo's own fix for `PlantCategoryIndexPageViewSet`
ships together with todo 325's PR, not this one — both viewsets' fixes
live in the same file (`endpoints.py`/`serializers.py`) as todo 325's
`versioning_class` fix and the further crashes that fix uncovered (see
todo 325's Work Log), so they were committed as a single file-level unit.
This PR covers only the three blog viewsets
(`BlogIndexPageViewSet`/`BlogCategoryPageViewSet`/`BlogAuthorPageViewSet`).

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
5. **Once the endpoints are live**, check each serializer's top-level
   `"url"` field too — `BlogAuthorPageSerializer`, `BlogIndexPageSerializer`,
   `BlogCategoryPageSerializer` (and `PlantCategoryIndexPageSerializer`)
   list `"url"` in `Meta.fields` but never define a `get_url` method, so DRF
   auto-builds it as a plain `ReadOnlyField()` reading the Page model's
   `url` property directly — `Page.get_url(request=None)`, no request, same
   class of Site-based host bug todo 308 fixed elsewhere (confirmed
   empirically: `serializer.get_fields()['url']` is a bare
   `ReadOnlyField(source=None)`). Invisible today only because these
   endpoints are currently dead code (this todo) — fixing *this* todo
   without also adding a `get_url`/`_absolute_page_url` override
   re-surfaces the todo-308 bug on a field that's about to start working
   for the first time.

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

- [x] All four viewsets' custom fields are actually wired to the live
      response. **Corrected from the original text** ("use
      `base_serializer_class`, not `serializer_class`") — that rename alone
      was verified NOT to work (see Work Log); the fix that was actually
      verified to work is each viewset overriding `get_serializer_class()`
      to return the custom serializer directly, matching
      `BlogPostPageViewSet`'s established pattern.
- [x] A live probe of each affected endpoint (post-deploy) shows the custom
      fields in the response. Seeded content via `seed_demo_blog --confirm`
      (extended by #603 to create `BlogAuthorPage`/`BlogCategoryPage`) and
      live-probed all three: `/api/v2/blog-index/` shows `featured_posts`/
      `categories`/`recent_posts`; `/api/v2/blog-authors/` shows `bio`/
      `expertise_areas`/`post_count`/`recent_posts` with correct nested
      posts per author; `/api/v2/blog-categories/` shows `category`/`posts`
      with correct nested posts per category. All `url` fields
      request-derived (`https://api.houseplant-md.com/...`), not `localhost`.
- [x] A regression test per viewset pins presence of at least one custom
      field so this can't silently regress again. `python manage.py test
      apps.blog.tests.test_page_viewsets_serializer_wiring
      apps.plant_identification.tests.test_page_viewsets_versioning_and_wiring
      --keepdb` → `Ran 11 tests ... OK`.
- [x] No regression in `apps.blog` or `apps.plant_identification` test suites.
      `python manage.py test apps --noinput` → `Ran 829 tests ... OK
      (skipped=8)`.

## Work Log

### 2026-08-31 - Filed

- Discovered during todo 308 (Wagtail Site hostname / `get_full_url()` →
  `request.build_absolute_uri()`) while designing that todo's live-probe
  verification step. Verified via direct grep + read of `viewsets.py` and
  Wagtail's `BaseAPIViewSet` source, plus a live curl against
  `api.houseplant-md.com`. Out of scope for todo 308 — filed separately per
  that todo's plan.

### 2026-08-31 - Started by completing-todos skill (run 2026-08-31-1849)

- Picked up by automated workflow (batched with 325/326/327).

### 2026-08-31 - Recommended Action item 1 corrected — the prescribed fix doesn't work

- The rename `serializer_class` → `base_serializer_class` (this todo's
  original item 1) was implemented and empirically tested via an HTTP-level
  regression test (`GET /api/v2/blog-index/<id>/`, asserting custom fields
  present) — it FAILED with `500 AttributeError`, then even after fixing
  that, the custom fields were still absent from the response.
- Root cause, confirmed by reading `wagtail/api/v2/views.py`'s
  `_get_serializer_class()`/`get_serializer_class()`: Wagtail's
  `get_serializer_class()` is unconditionally called and always builds a
  serializer *dynamically* from `model.api_fields`
  (`get_serializer_class(model, field_names, meta_fields, ..., base=cls.base_serializer_class)`,
  `wagtail/api/v2/serializers.py`'s factory function) — `base_serializer_class`
  is only the PARENT CLASS for that dynamic construction, never reused as
  "the serializer to call directly." Since `BlogIndexPage`/`BlogCategoryPage`/
  `BlogAuthorPage`/`PlantCategoryIndexPage` don't define `api_fields`, the
  dynamically-built serializer has none of `BlogIndexPageSerializer` etc.'s
  own custom `SerializerMethodField`s — a `base_serializer_class` rename
  alone can never surface them, regardless of attribute name.
- **Actual fix**: override `get_serializer_class()` on each viewset to
  `return` the custom serializer class directly — bypassing Wagtail's
  dynamic construction entirely. This is the exact pattern
  `BlogPostPageViewSet` (the one viewset in this file that already worked
  correctly) already used. Applied to all four viewsets
  (`BlogIndexPageViewSet`, `BlogCategoryPageViewSet`, `BlogAuthorPageViewSet`,
  `PlantCategoryIndexPageViewSet`).
- This also surfaced two further latent bugs needed for the fix to actually
  work end-to-end (not scope creep — required dependencies, documented in
  full in todo 325's Work Log since todo 325's fix is what actually exercised
  them via HTTP for the first time): a missing `meta_fields` class attribute
  (Wagtail's `BaseSerializer.to_representation()` reads it unconditionally,
  normally injected only by the dynamic factory this fix bypasses), and a
  missing explicit `url = serializers.SerializerMethodField()` declaration
  (without it, DRF's auto field-building silently wins over each
  serializer's `get_url` method, since `Page` has its own same-named `url`
  property — reintroducing the exact todo-308 bug this fix's item 5 was
  supposed to prevent).
- AC #1's text ("All four viewsets use `base_serializer_class`, not
  `serializer_class`") is corrected below to describe the fix that was
  actually verified to work.

### 2026-08-31 - Verified, NOT archived (AC #2 pending post-deploy)

- Verification: new regression test file
  `apps/blog/tests/test_page_viewsets_serializer_wiring.py` (6 tests) plus
  `apps/plant_identification/tests/test_page_viewsets_versioning_and_wiring.py::PlantCategoryIndexPageViewSetTestCase`
  (3 tests) all pass — each asserts the real `/api/v2/` route returns the
  serializer's custom fields (`featured_posts`/`categories`/`recent_posts`
  for blog-index; `category`/`posts` for blog-categories; `author`/`bio`/
  `expertise_areas`/`post_count`/`recent_posts` for blog-authors;
  `categories`/`featured_plants` for plant-index) and a request-derived
  `url`. Full backend suite: `python manage.py test apps --noinput` →
  `Ran 829 tests ... OK (skipped=8)`.
- **Per the `completing-todos` skill's verification gate, AC #2 (live probe
  shows custom fields in prod) cannot be flipped to `[x]` yet** —
  `/api/v2/blog-authors/`, `/api/v2/blog-index/`, `/api/v2/blog-categories/`
  all return zero items in production today (no author/index/category
  pages seeded), so there is nothing to probe until this branch merges,
  deploys, and content is seeded. This is the exact same situation as todo
  308's AC #1 (that todo stayed `pending`/`in_progress` post-merge until a
  post-deploy live probe was run and recorded, then was archived
  separately). **This todo stays `in_progress`, not archived, pending that
  same follow-up.** Once merged+deployed, seed the relevant content,
  live-probe each endpoint, check AC #2, and archive per the standard
  `completing-todos` flow.
- Review: `code-review-orchestrator` ran on the full batch diff (todos
  324/325/326/327 as one diff) — 0 critical, 0 high, 1 medium, 1 low, 1
  info, all three verified as false positives against source (see todo
  326's Work Log for the detail — reviewer misread diff hunk-header line
  offsets). Nothing to repair.

### 2026-08-31 - Deployed; partial live probe (1 of 3 endpoints has content)

- Merged via PR #598. Railway auto-deployed on push to `main`
  (deployment `6f4cf794`, commit `43f1c31`, `SUCCESS`).
- Post-deploy live probe: `/api/v2/blog-index/` unexpectedly already has
  content in production (`BlogIndexPage` id 16, "Blog") — **AC #2
  confirmed for this endpoint**:
  `curl https://api.houseplant-md.com/api/v2/blog-index/16/` returns
  `featured_posts: []`, `categories: []`, `recent_posts` (6 posts, each
  with a request-derived `url` starting `https://api.houseplant-md.com/`),
  and the page's own `url` = `https://api.houseplant-md.com/blog/` — the
  fix works end-to-end against real production data, not just the test
  suite.
- `/api/v2/blog-authors/` and `/api/v2/blog-categories/` still return zero
  items (`{"meta": {"total_count": 0}, "items": []}`) — no
  `BlogAuthorPage`/`BlogCategoryPage` content exists in prod yet, so their
  custom fields still can't be observed live. **AC #2 stays unchecked** —
  it's now 1-of-3 confirmed, not all three. Not archiving yet.
- Incidental observation while probing (not a regression, pre-existing,
  untouched by this session's PRs): nested `categories[].url` on each
  blog post is `null` in the live response.
  `BlogCategorySerializer.get_url` (`apps/blog/api/serializers.py:134-144`)
  looks up a matching `BlogCategoryPage` for each `BlogCategory` and
  returns `None` when none exists — consistent with `blog-categories`
  itself returning zero items above. Expected, not a bug.
- Remaining follow-up: once `BlogAuthorPage`/`BlogCategoryPage` content is
  seeded (or if never seeded, that itself is a valid "this AC just can't
  be fully satisfied" outcome worth a decision), live-probe the other two
  endpoints, check AC #2, archive.

### 2026-08-31 - Seeded, live-probed, completed

- `seed_demo_blog` extended (PR #603, merged, deployed) to also create
  `BlogAuthorPage`/`BlogCategoryPage` — the plain `User`/`BlogCategory`
  rows the command already created were never enough; these page types
  are what the fixed endpoints actually serve, and nobody had ever
  created one, in prod or in the seed data.
- Ran `railway ssh --service plant_id_community "python manage.py
  seed_demo_blog --confirm"` (same guarded, idempotent command already
  used for todo 308) against production: `Created author page
  iris_delgado.` / `sam_whitaker.` / `june_park.` / `theo_brandt.`,
  `Created category page care.` / `propagation.` / `pests-diseases.` /
  `design.`, `Blog seed complete: 0 post(s) created, 6 already present.
  4 author page(s), 4 category page(s) confirmed.`
- Live-probed both remaining endpoints against production:
  `/api/v2/blog-authors/` returns 4 items, each with populated `bio`,
  `expertise_areas`, `post_count`, and `recent_posts` (correct posts per
  author, e.g. June Park → "Killed by kindness" + "Spider mites move in
  before you notice"), all `url` fields resolving to
  `https://api.houseplant-md.com/blog/<slug>/`.
  `/api/v2/blog-categories/` returns 4 items, each with populated
  `category` and `posts` (correct posts per category, e.g. Design → 2
  posts), same request-derived `url` pattern.
  Combined with `/api/v2/blog-index/`'s earlier confirmation, all three
  affected endpoints are now proven working against real production data.
- AC #2 checked. All acceptance criteria satisfied. Archived.
