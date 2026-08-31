---
status: pending
priority: p3
issue_id: "326"
tags: [backend, wagtail, api, blog]
dependencies: []
---

# Legacy `apps/blog/serializers.py` has the same Site-rooted-URL landmine todo 308 closed elsewhere — and may be dead code

## Problem

`apps/blog/serializers.py` (distinct from `apps/blog/api/serializers.py`,
which todo 308 fixed) is a second, older REST-framework-based serializer
module backing a second, separate blog API surface — mounted at `/blog/`
(via `apps/blog/urls.py`'s router → `apps/blog/views.py`'s
`BlogPostPageViewSet`), live-routed today, distinct from the Wagtail-API-v2
`/api/v2/blog-posts/` surface the web frontend actually calls.

`BlogPostPageSerializer.get_url` and `BlogPostListSerializer.get_url` in
this file (lines 211-216, 269-274) both do:

```python
def get_url(self, obj):
    request = self.context.get("request")
    if request:
        return request.build_absolute_uri(obj.get_url())
    return obj.get_url()
```

This is exactly the landmine todo 308 identified and closed in
`apps/blog/api/serializers.py`: `obj.get_url()` called bare (no `request`)
returns an already-absolute, Site-rooted string once more than one Wagtail
`Site` row exists (see todo 308's `_absolute_page_url` docstring for the
full mechanism), and `request.build_absolute_uri()` passes an
already-absolute string through unchanged — so this endpoint would emit the
wrong host under the exact same conditions todo 308 fixed elsewhere. Today
(single Site row, no production Site configured at all) it's part of the
SAME localhost-resolution bug todo 308 fixes everywhere else.

## Findings

- `apps/blog/serializers.py:211-216` (`BlogPostPageSerializer.get_url`) and
  `:269-274` (`BlogPostListSerializer.get_url`) — both landmine-prone.
- Live-routed: `apps/blog/urls.py` registers
  `router.register(r"posts", views.BlogPostPageViewSet, basename="blog-posts")`,
  mounted at `path("blog/", include("apps.blog.urls"))` in
  `plant_community_backend/urls.py` (appears twice, in different env
  branches) — so `GET /blog/posts/` is a real, reachable route.
- **Zero consumers found anywhere in this codebase**: grepped `web/src`,
  `plant_community_mobile/lib`, and the backend itself for `blog/posts` and
  `apps.blog.serializers` — the only hits are the router registration
  itself and an import in `apps/blog/admin_views.py`. The web frontend
  exclusively calls `/api/v2/blog-posts/...`
  (`web/src/services/blogService.ts:115,142,173`). This looks like
  superseded/legacy code from before the Wagtail API v2 migration
  (todo 306/308's broader context), never removed.
- **Zero test coverage**: grepped `apps/blog/tests/*.py` for imports from
  `apps.blog.serializers` (not `apps.blog.api.serializers`) or any request
  to `/blog/posts/` — none found.
- Discovered by the `/code-review` pass on todo 308's PR — invisible to
  that todo's own grep-based audit (which searched for `get_full_url(`
  call sites; this file never used `get_full_url()` at all, it already
  called `build_absolute_uri()` directly, just on the wrong input).

## Recommended Action

Decide the bigger question first, since it changes the fix entirely:

1. **If this endpoint is confirmed dead** (no consumer — internal or
   external/third-party — actually depends on it): delete
   `apps/blog/serializers.py`, `apps/blog/views.py`'s `BlogPostPageViewSet`
   and the sibling viewsets it doesn't share with the live API, and the
   `/blog/` router mount, rather than patching a landmine in code nobody
   uses. Confirm via Railway access logs or an equivalent traffic check
   before deleting — "no consumer in this repo" isn't proof nothing
   external calls it.
2. **If it must stay** (e.g. a third-party integration depends on it):
   apply the same fix as todo 308 — replace `obj.get_url()` with
   `obj.get_url_parts(request=request)[2]` (the always-relative page path)
   before calling `build_absolute_uri()`, matching
   `apps/blog/api/serializers.py`'s `_absolute_page_url` helper. Add test
   coverage first (none exists today) — at minimum a single-Site
   regression test and, if todo 308's multi-Site test pattern is judged
   worth replicating, a second-Site one too.

## Technical Details

- `apps/blog/serializers.py:211-216,269-274`
- `apps/blog/urls.py`, `apps/blog/views.py`
- `apps/blog/api/serializers.py`'s `_absolute_page_url` — the reference fix
  pattern from todo 308, if Option 2 is chosen.

## Acceptance Criteria

- [ ] A decision is made and recorded: keep-and-fix, or delete.
- [ ] If kept: `get_url` no longer calls `build_absolute_uri()` on
      `obj.get_url()`'s raw output; a regression test is added.
- [ ] If deleted: the dead router mount, viewset, and serializer file are
      removed; confirm no other backend code imports from
      `apps.blog.serializers` first (`apps/blog/admin_views.py` does —
      check what it needs before deleting).
- [ ] No regression in `apps.blog` test suite either way.

## Work Log

### 2026-08-31 - Filed

- Surfaced by a `/code-review` pass on todo 308's PR (fix/wagtail-api-absolute-urls),
  which found this file independently of todo 308's own scoping (grep for
  `get_full_url(`, which this file never called). Verified live-routed via
  `urls.py`/`views.py` read; verified zero consumers via repo-wide grep
  across web/mobile/backend. Out of scope for todo 308 — filed separately.
