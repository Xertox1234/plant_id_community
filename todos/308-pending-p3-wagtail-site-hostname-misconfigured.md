---
status: pending
priority: p3
issue_id: "308"
tags: [backend, wagtail, config, media]
dependencies: []
---

# Wagtail Site record has no production hostname — API `full_url`/Site-based URLs resolve to localhost

## Problem

Every image/page URL in the blog API that's built via `get_full_url(request,
...)` (`wagtail.api.v2.utils`) — page URLs, author-page URLs, related-post
URLs, `RequestAwareImageRenditionField.full_url` — resolves the host via
`Site.find_for_request(request)`, NOT the actual incoming request's Host
header. This deploy has no Wagtail `Site` record configured for its real
production domain, so `Site.find_for_request` falls back to whatever Wagtail's
initial migration seeded (`hostname="localhost", port=80,
is_default_site=True`). Every one of those URLs therefore resolves to
`http://localhost/...` in production — confirmed by a live probe from the web
client (`web/src/services/blogService.ts`'s `mediaUrl()` docstring, written
2026-08-16 against production) and independently by this project's own
management commands, which query `Site.objects.get(is_default_site=True)` and
never write a production hostname anywhere.

The web client papers over this today with `mediaUrl()`: it ignores whatever
host the API sends and always re-bases any `/media/` path onto
`VITE_API_URL`. That workaround is NOT removable until this is fixed (see
todo 306's Work Log, which deliberately left it in place for exactly this
reason).

## Findings

- `Site.find_for_request()` (`wagtail/models/sites.py`) matches the request's
  Host header against `Site.hostname`/`Site.port`; with no matching Site it
  falls back to `is_default_site=True`.
- No code in this repo creates or updates a `Site` record — grepped
  `Site.objects.create`/`hostname=` across `apps/*`, only reads
  (`is_default_site=True`) in `apps/blog/management/commands/seed_demo_blog.py`
  and `apps/forum_host/management/commands/seed_default_forum.py`.
- `apps/blog/blocks.py`'s `APIImageChooserBlock` (todo 306) deliberately
  used `request.build_absolute_uri()` instead of `get_full_url()` for exactly
  this reason — it reads the real incoming request's host directly, no Site
  involved — and IS host-correct today. Every other URL-building call site in
  `apps/blog/api/serializers.py` still uses `get_full_url()` and is NOT.
- `settings.WAGTAILADMIN_BASE_URL` (`plant_community_backend/settings.py:428`)
  has the same problem via a different mechanism — defaults to
  `http://localhost:8000` when unset, which `Rendition.full_url` (Wagtail's
  own stock field, no longer used directly since todo 306) also relied on.

## Recommended Action

Two independent fixes, either sufficient on its own — pick based on what's
faster to verify on Railway:

1. **Configure the Site record.** In a data migration or a one-time
   management command run against production, update (or create) the
   `is_default_site=True` Site's `hostname`/`port` to match the real
   production domain (Railway's app URL and/or the Cloudflare-fronted custom
   domain, if todo 296 ever ships). Verify with a live probe of
   `/api/v2/blog-posts/<id>/` that `featured_image.full_url` and
   `related_posts[].url` return the real host, not `localhost`.
2. **Switch `get_full_url()` call sites to `request.build_absolute_uri()`.**
   Mirrors the `APIImageChooserBlock`/forum `serialize_image_for_api`
   pattern, which already works without any Site configuration. Touches
   `RequestAwareImageRenditionField`, `_get_post_url`, `_get_author_page_url`,
   `BlogSeriesSerializer.get_posts_url`, `BlogCategorySerializer.get_url` in
   `apps/blog/api/serializers.py`. Lower operational risk (no infra change)
   but doesn't fix `WAGTAILAPI_BASE_URL`-dependent behavior elsewhere in the
   Wagtail API if any exists — audit for other `get_full_url()` callers
   project-wide before committing to this as the sole fix.

Whichever is chosen, update `web/src/services/blogService.ts`'s `mediaUrl()`
docstring and (if safe) simplify it — that's the actual unblock for the AC5
half of todo 306 that was deliberately left undone.

## Technical Details

- `backend/apps/blog/api/serializers.py`: `RequestAwareImageRenditionField`,
  `_get_post_url`, `_get_author_page_url`,
  `BlogSeriesSerializer.get_posts_url`, `BlogCategorySerializer.get_url` —
  all call `get_full_url(request, ...)`.
- `backend/apps/blog/blocks.py`: `APIImageChooserBlock` — already uses
  `request.build_absolute_uri()`, the reference pattern for Option 2.
- `backend/plant_community_backend/settings.py:428`:
  `WAGTAILADMIN_BASE_URL` setting (separate mechanism, same symptom).
- `web/src/services/blogService.ts`: `mediaUrl()` — the frontend workaround
  to re-evaluate once this is fixed.

## Acceptance Criteria

- [ ] A live probe of a production (or production-equivalent staging) blog
      detail endpoint shows `featured_image.full_url` and
      `related_posts[].url` resolving to the real domain, not
      `http://localhost`. **Outstanding** — needs a post-merge Railway
      deploy plus at least one live blog post to probe (prod currently has
      zero); requires the user's explicit go-ahead before touching prod
      data. See Work Log.
- [x] `web/src/services/blogService.ts`'s `mediaUrl()` re-evaluated: either
      simplified (if the API is now trustworthy) or its docstring updated to
      reflect the actual current mechanism. Docstring updated; rebase logic
      kept as defense-in-depth (see Work Log).
- [x] No regression in existing blog API tests
      (`apps/blog/tests/test_n_plus_1.py`, `test_blog_viewsets_caching.py`).

## Work Log

### 2026-08-17 - Filed

- Discovered while implementing todo 306 (blog list serializer + StreamField
  - media URL consistency): fixing the *shape* inconsistency of
  `related_posts[].featured_image` (bare string vs. rendition dict)
  surfaced that the underlying *host* was already wrong for reasons outside
  that todo's scope. Confirmed via `Site.find_for_request` source read +
  cross-referencing the web team's 2026-08-16 live-probe comment in
  `blogService.ts`, not fixed live since it's an infra/config change
  (Site record) or a broader refactor (many call sites), not a serializer
  shape fix.

### 2026-08-31 - Implemented (Option 2: `get_full_url()` → `request.build_absolute_uri()`)

- Verified Wagtail's exact `get_full_url()`/`get_base_url()` source before
  committing to an approach — confirmed `WAGTAILAPI_BASE_URL` (unset) then
  `Site.find_for_request()` (falls back to seeded `localhost:80`) is the
  full mechanism. Confirmed this project's own
  `backend/docs/cowork/05-headless-serving.md:668` already documents
  `request.build_absolute_uri()` as the correct pattern, and that
  `WAGTAILAPI_BASE_URL` only matters for `wagtailfrontendcache` (not used
  in this project) — ruling out both alternative fixes (Site record,
  `WAGTAILAPI_BASE_URL`) in favor of Option 2.
- **Landmine found and closed, not just documented**: `Page.get_url()`
  (called bare, no `request`, at every page-URL call site in this codebase)
  decides relative-vs-absolute by counting Wagtail `Site` rows, and
  prepends the *Site's* `root_url` once there's more than one — an
  already-absolute string `request.build_absolute_uri()` would then pass
  through unchanged, silently reintroducing this exact bug the moment a
  second `Site` row ever exists. Fixed by building every page URL from
  `page.get_url_parts(request=request)[2]` (always the bare relative path,
  never Site-rooted) instead of `page.get_url()` — a shared
  `_absolute_page_url(request, page)` helper in both
  `apps/blog/api/serializers.py` and
  `apps/plant_identification/api/serializers.py`. Verified this is not just
  "doesn't break" but actually correct for a multi-Site setup, by keeping
  (not removing) `test_full_url_is_request_derived_not_settings_based`'s
  second-`Site`-row setup and adding a new `response.data["url"]`
  assertion — both `full_url` and `url` correctly reflect the request's
  actual host (`blog.example.com`) even with 2 Sites present.
- 16 call sites swapped total: 9 in `apps/blog/api/serializers.py`, 7 in
  `apps/plant_identification/api/serializers.py`. `get_full_url` import
  removed from both files (confirmed via grep, zero references remain).
  `apps/blog/blocks.py` docstring updated (it previously contrasted itself
  against `get_full_url()` "used elsewhere" — no longer true).
- Two exact-count query pins in `apps/blog/tests/test_analytics.py`
  (`test_popular_posts_query_optimization`,
  `test_popular_posts_all_time_query_count`) dropped by exactly 1 query
  each (8→7, 7→6) — the fix eliminates a redundant `Site.find_for_request()`
  DB lookup that used to run alongside `get_url_parts()`'s own
  `Site.get_site_root_paths()` lookup; now only the latter runs (and it's
  shared/cached across the whole list via the request object). Pins
  updated with an explanatory comment, not silently changed.
- Full verification: `python manage.py test apps.blog --noinput` (241
  tests, exit 0) and `python manage.py test apps.plant_identification
  --noinput` (110 tests, exit 0) — used `--noinput`, not `--keepdb`, since
  both suites create Wagtail pages (CLAUDE.md gotcha #6); ran sequentially,
  not concurrently. `pre-commit run` clean (black/flake8/isort/eslint/
  prettier/kimi-review all pass). Web: `npm run test` (35/35 pass,
  unmodified — docstring-only change) and `npm run type-check` clean.
- `web/src/services/blogService.ts`'s `mediaUrl()` docstring updated to
  describe the new mechanism; the host-rebasing logic itself was
  deliberately **kept**, not removed — it becomes a same-value no-op once
  the backend fix is live, and removing it can't be verified safe until
  AC #1's live probe actually runs. `blogService.test.ts` and
  `BlogDetailPage.test.tsx` were left untouched (their assertions don't
  change; only their comments describe the old workaround, which is
  optional churn, not required by this todo).
- Filed two follow-up todos for out-of-scope bugs surfaced while designing
  AC #1's live-probe step (both verified live against
  `api.houseplant-md.com`, not just read from code):
  [todo 324](324-pending-p3-blog-viewsets-wrong-serializer-attribute.md)
  (`BlogAuthorPageViewSet`/`BlogIndexPageViewSet`/`BlogCategoryPageViewSet`
  and `PlantCategoryIndexPageViewSet` all set `serializer_class` instead of
  `base_serializer_class` — 4 custom serializers are dead code on the live
  endpoints) and
  [todo 325](325-pending-p3-plant-species-endpoints-missing-versioning-class.md)
  (`PlantSpeciesPageViewSet`/`PlantCategoryIndexPageViewSet` are missing
  `versioning_class = None` and 404 on every request — that second viewset
  needs both fixes).
- **AC #1 intentionally left unchecked.** It requires a live probe against
  production, which needs (a) this PR merged and Railway redeployed, and
  (b) at least one real blog post with a featured image + related post to
  probe (prod currently has zero — `total_count: 0`), which likely means
  running the seed command against prod. That's a production-data action
  and needs the user's explicit go-ahead before it happens — not something
  to do unilaterally on the strength of the 2026-08-16 live-probe
  precedent. Todo stays `status: pending` until that probe runs and its
  output is recorded here.
