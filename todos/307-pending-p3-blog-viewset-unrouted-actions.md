---
status: pending
priority: p3
issue_id: "307"
tags: [backend, blog, api, cleanup]
dependencies: []
---

# `BlogPostPageViewSet` has 7 unrouted `@action` methods — route them or delete them

## Problem

`apps/blog/api/viewsets.py`'s `BlogPostPageViewSet` (the Wagtail API v2 viewset
mounted at `/api/v2/blog-posts/`) defines 7 custom `@action`-decorated methods,
but only ONE (`popular`) has an explicit `path()` entry wiring it to a URL in
`plant_community_backend/urls.py`. The other 6 are dead code: reachable by
nothing, referenced by nothing in `web/src`, exercised by no test that hits
them over HTTP.

Wagtail's API router does not auto-discover `@action`-decorated methods the
way DRF's `DefaultRouter` does — `BaseAPIViewSet.get_urlpatterns()`
(`wagtail/api/v2/views.py`) only ever wires the three fixed base routes
(`listing_view`/`detail_view`/`find_view`). Every custom action needs its own
explicit `path(...)` entry, exactly like `popular`'s. Nobody added the other
six.

## Findings

- Confirmed via `grep -n "@action" apps/blog/api/viewsets.py`: 7 custom
  actions total —
  - `featured` (line 298)
  - `recent` (line 308)
  - `popular` (line 327) — **the only one routed**
    (`plant_community_backend/urls.py:114-116`,
    `path("api/v2/blog-posts/popular/", BlogPostPageViewSet.as_view({"get": "popular"}), name="blog-posts-popular")`)
  - `by_category` (line 425)
  - `search_suggestions` (line 478)
  - `related` (line 514, `detail=True`)
  - `rss` (line 772)
  - `atom` (line 790)
- `grep -n "blog-posts.*<action>"` against `plant_community_backend/urls.py`
  for each of the other 6 — zero matches for all of them.
- `grep -rl "blog-posts/<action>"` against `web/src` — zero matches. The
  frontend (`web/src/services/blogService.ts`) only calls the base list
  endpoint, the detail endpoint, and `.../popular/`.
- `rss` and `atom` are explicitly unfinished, not just unrouted — their own
  docstring/comment says "You would implement RSS XML generation here" and
  they return JSON shaped like a feed, not actual RSS/Atom XML.
- `featured`, `recent`, `by_category`, `related`, `search_suggestions` look
  otherwise complete (real querysets, real serializer use, N+1-aware
  prefetching) — they read like finished features that were never wired up,
  not abandoned stubs.
- Discovered 2026-08-16 while investigating todo 306's `self.action` bug
  during the PR #540 code-review fix wave — `get_queryset()`'s conditional
  prefetch branch lists `("list", "popular", "featured", "recent",
  "related")`, which is what prompted checking whether those last three are
  even reachable.

## Proposed Solutions

### Option 1: Route the finished ones, delete the stubs (recommended)

- **Implementation:** add explicit `path()` entries for `featured`, `recent`,
  `by_category`, `search_suggestions`, `related` (mirroring `popular`'s
  pattern in `urls.py`) if the web/mobile clients have a use for them;
  delete `rss`/`atom` (and their now-provably-dead
  `get_queryset()`/prefetch branches) since they're unfinished stubs nobody
  is blocked on.
- **Pros:** closes the gap between "what the API claims to offer" and "what
  actually works"; removes genuinely dead placeholder code.
- **Cons:** routing 5 new endpoints without a confirmed frontend consumer is
  speculative work — may just be moving the "unused" problem from
  "unrouted" to "routed but uncalled."
- **Effort:** ~30 min routing + tests, if there's a real use case per action.
- **Risk:** low — additive routing, no behavior change to existing routes.

### Option 2: Delete all 7, keep only what's proven needed

- **Implementation:** delete `featured`/`recent`/`by_category`/
  `search_suggestions`/`related`/`rss`/`atom` entirely (and their
  `get_queryset()` prefetch-branch entries), keeping only `list`/`retrieve`/
  `popular`.
- **Pros:** smallest surface area; no speculative routing.
- **Cons:** loses working, tested-in-isolation code that might be wanted
  soon (e.g. `related` posts on the detail page, RSS for SEO/subscribers).
- **Effort:** ~15 min.
- **Risk:** low, but throws away otherwise-complete work.

## Recommended Action

This is a product decision, not a pure technical one — which of these 7 (if
any) the web or mobile client actually wants determines whether Option 1 or 2
applies, and per-action. Suggested triage:

1. Decide per action: is there a near-term UI use case?
   (`related` — "More like this" on the detail page; `featured`/`recent` —
   possible home/rail modules; `by_category`/`search_suggestions` — filter
   UX; `rss`/`atom` — SEO/subscriber feeds.)
2. Route the ones with a real use case (mirror `popular`'s `path()` entry +
   add a routing-parity test like the forum's
   `test_host_api_routes_match_package` pattern, or at minimum an HTTP-level
   test hitting the new URL).
3. Delete the rest, including their `get_queryset()` prefetch-branch
   entries in the `action in (...)` tuple — dead branches should not
   survive their action's deletion.

## Technical Details

- `backend/apps/blog/api/viewsets.py` — action definitions at lines 298,
  308, 327 (routed), 425, 478, 514, 772, 790.
- `backend/apps/blog/api/viewsets.py:162` — the `get_queryset()`
  conditional-prefetch branch's `action in ("list", "popular", "featured",
  "recent", "related")` tuple lists 3 of the unrouted actions; keep this
  tuple in sync with whichever actions survive.
- `backend/plant_community_backend/urls.py:111-116` — `popular`'s explicit
  `path()` is the pattern to mirror for any action kept.
- Related: todo 306 (the `self.action == "list"` vs `"listing_view"` bug —
  a DIFFERENT bug on the SAME viewset; fixing 306 does not fix this, and
  fixing this does not fix 306).

## Acceptance Criteria

- [ ] Each of the 7 actions is either routed (with a test hitting it over
      HTTP) or deleted (along with its `get_queryset()` prefetch-branch
      entry, if any).
- [ ] No action remains defined-but-unroutable after this todo closes.

## Work Log

### 2026-08-16 - Filed

- Surfaced while investigating todo 306 during the PR #540 code-review fix
  wave. Not a bug (nothing is broken — the actions simply can't be called),
  so filed as p3 cleanup/product-decision rather than a fix. User asked to
  file it for later triage rather than deciding now.

## Notes

- p3: no user-facing breakage, no security/data risk — this is "decide what
  to do with 7 methods nobody can call," not an incident.
- Do not conflate with todo 306: that fixes a `self.action` branching bug on
  the ROUTED endpoints; this decides the fate of the UNROUTED ones. Both
  touch the same file but are independent.
