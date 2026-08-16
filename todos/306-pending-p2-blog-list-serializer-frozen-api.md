---
status: pending
priority: p2
issue_id: "306"
tags: [backend, blog, api, performance]
dependencies: []
---

# Fix blog list serializer action mapping + structured StreamField + consistent media URLs

## Problem

`BlogPostPageViewSet.get_serializer_class()` in
`backend/apps/blog/api/viewsets.py:68-72` branches on
`getattr(self, "action", None) == "list"` to pick a lighter list serializer,
but this class subclasses Wagtail's `PagesAPIViewSet`, which uses its own
action names — `listing_view` for the list endpoint and `detail_view` for
the detail endpoint (`wagtail/api/v2/views.py:90,103`; confirmed Wagtail
itself gates on `self.action == "listing_view"` internally at
`wagtail/api/v2/views.py:364`) — not DRF's stock `list`/`retrieve`. The
`"list"` check therefore never matches, so every list request to
`/api/v2/blog-posts/` (the blog index grid, the "Popular this month" rail,
the "More from the blog" strip) silently serves the full
`BlogPostPageSerializer` meant for a single detail page — including the
per-item server-computed `related_posts` field, which is an N+1 query for
every post row in the list.

Note there is a **second, unrelated** class with the same name,
`BlogPostPageViewSet` in `backend/apps/blog/views.py:48`, a plain DRF
`ReadOnlyModelViewSet` (not Wagtail's `PagesAPIViewSet`). Its identical-
looking `self.action == "list"` check at `views.py:128-132` is correct for
that class — DRF's own `ListModelMixin` really does set `self.action =
"list"`. That viewset is registered under a different router
(`backend/apps/blog/urls.py`) and is **not** what the web client calls
(`web/src/services/blogService.ts` hits `/api/v2/blog-posts/`, which routes
to `apps/blog/api/viewsets.py`'s class via
`backend/plant_community_backend/urls.py:60`,
`api_router.register_endpoint("blog-posts", BlogPostPageViewSet)`). Fix only
`apps/blog/api/viewsets.py` — do not touch `apps/blog/views.py`.

## Findings

- `content_blocks` is returned as a stringified raw StreamField JSON blob
  (DRF `ModelSerializer`'s default rendering of a Wagtail `StreamField`),
  not a structured list. The web client has to `JSON.parse` it itself
  (`normalizeContentBlocks` in `web/src/services/blogService.ts`) before
  `StreamFieldRenderer` can walk it.
- In that raw-JSON shape, an `ImageChooserBlock` inside the stream serializes
  as a bare integer PK (the chooser's `to_python`/native value), not an
  image object with a URL. A CMS-authored image block embedded in a blog
  body therefore cannot render on the web at all — no amount of
  client-side `mediaUrl()` hardening can recover a URL from an integer.
- Media URLs are emitted in three inconsistent shapes across the API
  surface: relative rendition paths, request-based absolute URLs, and
  Wagtail `Site`-record-based absolute URLs (whose host is not always
  trustworthy in a multi-environment deploy). The web papers over all
  three with a defensive `mediaUrl()` helper instead of the API emitting
  one consistent, always-absolute shape.

## Recommended Action

1. Fix `BlogPostPageViewSet.get_serializer_class()` in
   `apps/blog/api/viewsets.py` to branch on Wagtail's real action names
   (`listing_view` for list, `detail_view` for detail) instead of DRF's
   `list`/`retrieve`, so the list endpoint actually serves the lighter
   serializer and stops paying the `related_posts` N+1 on every row.
2. Give the API a properly structured StreamField representation (Wagtail's
   own StreamField API v2 serialization, or a custom field) so
   `content_blocks` arrives as real nested blocks — including a resolved
   image object (URL, alt, dimensions) for `ImageChooserBlock`, not a PK.
3. Standardize media URL emission to one consistent, always-absolute shape
   across list/detail/related payloads.
4. Once the API contract changes, delete `normalizeContentBlocks` from
   `web/src/services/blogService.ts` and simplify `mediaUrl()` to a single
   pass-through — both were client-side workarounds for the shapes above.

## Acceptance Criteria

- [ ] `get_serializer_class()` in `apps/blog/api/viewsets.py` correctly
      selects the list serializer for Wagtail's `listing_view` action; list
      endpoints no longer trigger the per-item `related_posts` query.
- [ ] `apps/blog/views.py`'s unrelated `BlogPostPageViewSet` (DRF-native,
      already correct) is left untouched.
- [ ] `content_blocks` is structured JSON (not a stringified blob) with
      resolved image objects for image blocks; a CMS-authored image block
      renders correctly on the web.
- [ ] Media URLs are emitted in one consistent absolute shape across list,
      detail, and related-post payloads.
- [ ] `normalizeContentBlocks` and the defensive branches in `mediaUrl()`
      are removed from `web/src/services/blogService.ts` once the API
      change ships.

## Work Log

### 2026-08-16 - Filed

- Findings surfaced during the PR 3 (Canopy blog) final-review fix wave.
  The blog API was contractually frozen for the duration of PR 3 (spec
  Global Constraint — the web client had to build against the API as-is),
  so these ship as a follow-up rather than in-PR fixes. Confirmed via
  Wagtail source (`venv/lib/python3.13/site-packages/wagtail/api/v2/views.py`)
  that `listing_view`/`detail_view` are the real action names, and
  disambiguated the two same-named `BlogPostPageViewSet` classes before
  filing, to avoid a future fix landing in the wrong file.
