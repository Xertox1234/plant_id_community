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
      `http://localhost`.
- [ ] `web/src/services/blogService.ts`'s `mediaUrl()` re-evaluated: either
      simplified (if the API is now trustworthy) or its docstring updated to
      reflect the actual current mechanism.
- [ ] No regression in existing blog API tests
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
