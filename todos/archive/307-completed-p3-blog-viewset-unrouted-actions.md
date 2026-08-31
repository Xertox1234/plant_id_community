---
status: completed
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
- Discovered 2026-08-16 while implementing todo 306 (`BlogPostPageSerializer`
  media-URL/StreamField fix): the DETAIL response already embeds
  `related_posts` directly (`get_related_posts()` in
  `apps/blog/api/serializers.py`, now hardened by 306's `_get_post_url`/
  `_get_post_image` fixes). That makes the standalone `related` `@action`
  (line 514) look redundant with what the detail endpoint already serves —
  worth weighing in the triage below, not a reason to route it by default.

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

- [x] Each of the 7 actions is either routed (with a test hitting it over
      HTTP) or deleted (along with its `get_queryset()` prefetch-branch
      entry, if any).
- [x] No action remains defined-but-unroutable after this todo closes.

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

### 2026-08-31 - Started by completing-todos skill (run 2026-08-31-0302)

- Picked up by automated workflow. Triage decision confirmed with user via
  plan-mode AskUserQuestion beforehand: route all 5 non-feed actions
  (`featured`, `recent`, `by_category`, `search_suggestions`, `related`),
  delete `rss`/`atom` plus the now-purposeless `BlogFeedViewSet` class and
  its `blog-feeds` endpoint registration. Follow-up todo 322 filed for a
  real RSS/Atom implementation via `django.contrib.syndication`.

### 2026-08-31 - Implemented and verified

- **Routed** `featured`, `recent`, `by_category`, `search_suggestions`,
  `related` in `plant_community_backend/urls.py` (manual `path()` entries
  mirroring `popular`'s existing pattern; `related` uses `<int:pk>/`,
  verified against Wagtail's own `<int:pk>/` detail-route converter).
- **Deleted** `BlogFeedViewSet` in its entirety from
  `apps/blog/api/viewsets.py` (the `rss`/`atom` non-functional JSON stubs
  plus the class itself, since it had no purpose left) and its
  `api_router.register_endpoint("blog-feeds", ...)` registration from
  `urls.py`.
- Drive-by: removed the dead `from ..models import BlogComment` import in
  `related()`; reworded the stale `get_queryset()` else-branch comment.
- Added `apps/blog/tests/test_blog_viewset_routing.py`: an HTTP-level test
  per newly-routed action (hits the real URLconf via the Django test
  client, not `as_view()` direct dispatch) plus a routing-parity guard
  (`test_all_extra_actions_are_routed`) enumerating
  `BlogPostPageViewSet.get_extra_actions()` against `urls.py`'s
  `urlpatterns`, modeled on the forum's
  `test_host_api_routes_match_package`. Updated the now-inaccurate
  "Not URL-routed" docstring on `SearchSuggestionsActionWildcardTests` in
  `test_search_wildcards.py`.
- **Verification — full `apps.blog` suite** (fresh DB, `--noinput` —
  `--keepdb` hit the known Wagtail-root-truncation residue issue from a
  prior narrower run, see `docs/LEARNINGS.md`):
  ```
  Ran 226 tests in 53.443s
  OK (skipped=7)
  ```
- **Verification — new routing tests specifically**:
  ```
  Ran 6 tests in 1.145s
  OK
  ```
  (5 HTTP-level action tests + `test_all_extra_actions_are_routed`, the
  routing-parity guard.)
- **Verification — live dev server smoke test** (`manage.py runserver`,
  real HTTP via `urllib`, not just the test client):
  ```
  http://localhost:8000/api/v2/blog-posts/featured/ -> 200
  http://localhost:8000/api/v2/blog-posts/recent/ -> 200
  http://localhost:8000/api/v2/blog-posts/by_category/ -> 200
  http://localhost:8000/api/v2/blog-posts/search_suggestions/?q=a -> 200
  http://localhost:8000/api/v2/blog-posts/popular/ -> 200
  http://localhost:8000/api/v2/blog-feeds/ -> 404
  http://localhost:8000/api/v2/blog-posts/4/related/ -> 200
  ```
- **Verification — schema + system check**: `manage.py spectacular` still
  generates the schema (exit 0; pre-existing warnings/errors are all in
  unrelated apps, none newly introduced by this change);
  `manage.py check` → "System check identified no issues (0 silenced)."
- `grep -rn "BlogFeedViewSet" backend/` → zero remaining references in
  code (two mentions in `backend/docs/plan.md`, a dated Oct 2025 planning
  snapshot — left untouched as out of scope).
- All 7 actions accounted for: `popular` (already routed), `featured`,
  `recent`, `by_category`, `search_suggestions`, `related` (newly routed
  + tested), `rss`/`atom` (deleted). Both acceptance criteria verified.

### 2026-08-31 - Code review (wagtail-reviewer + cross-cutting-reviewer)

- Dispatched via `code-review-orchestrator`. 2 HIGH, 5 MEDIUM/LOW findings
  (after dedup across the two reviewers).
- **Blocking, repaired**: `featured()` and `recent()` both sliced
  `self.get_queryset()` with no `.order_by()` at all — wagtail-reviewer
  empirically reproduced (a throwaway probe with 3 posts at distinct
  publish dates, created out of chronological order, came back in
  creation order, not `-first_published_at`). Pre-existing code, but
  UNREACHABLE before this todo — routing it now shipped a "recent posts"
  endpoint that didn't actually return posts in recency order. Fixed by
  adding `.order_by("-first_published_at")` to both, matching the
  convention `by_category`/`related`/`popular` already use. Added a
  permanent regression test class
  (`BlogPostPageViewSetOrderingTestCase`, 2 tests) with posts created in
  scrambled creation-vs-publish-date order so a creation-order fallback
  bug can't slip back in unnoticed.
- **Repaired (non-blocking but direct residue of this diff's own edits)**:
  - Removed a second dead `from ..models import BlogComment` import in
    `get_queryset()`'s list-style branch (the twin of the one already
    removed from `related()` — missed on the first pass).
  - Removed the now-stale `"format"` entry (comment: "For RSS/Atom
    feeds") from `known_query_parameters` — dead now that
    `BlogFeedViewSet` is gone.
  - Reworded the `get_queryset()` else-branch comment again — my first
    reword cited `search_suggestions` as an example, but that action
    never calls `get_queryset()` at all (same class of error `by_category`
    already correctly avoids); dropped the inaccurate example rather than
    guess a correct one.
  - Updated `docs/blog/API_REFERENCE.md`: replaced the stale RSS/Atom
    section (which described the deleted `blog-feeds` endpoint as live
    and "Production Ready") with a note pointing at todo 322; dropped the
    "RSS/Atom Feeds" bullet from the feature summary.
  - Strengthened `test_all_extra_actions_are_routed` to also assert the
    matched `path()` dispatches to the correct viewset class *and* the
    correct action name (`callback.cls` / `callback.actions["get"]`), not
    just that a matching path string exists — a copy-paste error wiring
    the right path text to the wrong action would have passed the
    original, weaker version.
- **Known issues — accepted at completion** (non-blocking, pre-existing
  patterns not introduced by this diff, left as-is per the "surgical
  changes" convention):
  - None of the 5 newly-routed actions have `@extend_schema` — same gap
    as `popular`, the action they were modeled on; OpenAPI schema is
    unaffected either way (`manage.py spectacular` still generates
    cleanly).
  - No `assertNumQueries` pin on `featured`/`recent`/`related` in the new
    test file — `by_category` already has one elsewhere
    (`test_blog_viewsets_caching.py`); worth adding as test-hardening but
    not required for correctness.
  - The routing-parity guard only covers `BlogPostPageViewSet` — a
    sibling viewset that later grows an unrouted `@action` wouldn't be
    caught. No other registered viewset currently defines one.
- **Re-verification after repair**: full `apps.blog` suite, fresh DB:
  ```
  Ran 228 tests in 31.021s
  OK (skipped=7)
  ```
  (226 → 228: the 2 new ordering regression tests.) `manage.py check` and
  `manage.py spectacular` both still clean.

### 2026-08-31 - Completed by completing-todos skill (run 2026-08-31-0302)

- Verification: all 228 `apps.blog` tests pass on a fresh DB; both
  acceptance criteria flipped with evidence quoted above.
- Review: 7 findings total (2 HIGH, 5 MEDIUM/LOW) via
  `code-review-orchestrator` → `wagtail-reviewer` + `cross-cutting-reviewer`.
  Both HIGH findings repaired (missing `order_by()` on `featured`/`recent`)
  plus all 5 non-blocking findings, since each was direct residue of this
  diff's own edits. 2 known-issue items accepted (pre-existing gaps,
  logged above, not fixed — out of surgical scope).
- User deviation from the "never commit" rail (confirmed, per
  `[[feedback_todo_slice_means_merged_pr]]`): committing, pushing, and
  opening a PR for this single-slice todo at the user's explicit request.
