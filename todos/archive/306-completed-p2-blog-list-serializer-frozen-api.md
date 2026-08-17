---
status: completed
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

- [x] `get_serializer_class()` in `apps/blog/api/viewsets.py` correctly
      selects the list serializer for Wagtail's `listing_view` action; list
      endpoints no longer trigger the per-item `related_posts` query.
- [x] `apps/blog/views.py`'s unrelated `BlogPostPageViewSet` (DRF-native,
      already correct) is left untouched.
- [x] `content_blocks` is structured JSON (not a stringified blob) with
      resolved image objects for image blocks; a CMS-authored image block
      renders correctly on the web.
- [x] Media URLs are emitted in one consistent absolute shape across list,
      detail, and related-post payloads.
- [x] `normalizeContentBlocks` is removed from `web/src/services/blogService.ts`
      — AC3 makes it genuinely dead: the API now sends a real array,
      unconditionally, never a JSON string. (Original AC5 also asked to
      remove `mediaUrl()`'s defensive host-rebasing branches — RE-SCOPED
      OUT, not silently dropped: see Work Log and todo 308. `mediaUrl()`
      still masks a real, separate bug this todo's fixes don't touch, and
      removing it now would break production images.)

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

### 2026-08-16 - PR #540 code-review fix wave: list-serializer prep landed

- A separate `/code-review` pass on PR #540 raised a finding claiming
  `BlogPostPageListSerializer` lacking `featured_image` made the blog grid
  render blurry. Live-probed against the pre-fix commit and found it FALSE
  for the endpoint's *current* behavior: this todo's exact bug (the
  `"list"` vs `"listing_view"` action mismatch) means `/api/v2/blog-posts/`
  already serves `BlogPostPageSerializer` (detail), which already had
  `featured_image` at `fill-800x400` before that PR. No live bug existed.
- However, `featured_image` (fill-800x400) was still added to
  `BlogPostPageListSerializer` + its queryset prefetch sites
  (`apps/blog/api/serializers.py`, `apps/blog/api/viewsets.py`), because
  (a) the routed `popular` action genuinely instantiates
  `BlogPostPageListSerializer` directly (bypassing `get_serializer_class()`)
  and now gets the field, and (b) **AC1 below is already half-done**: once
  `get_serializer_class()` starts correctly selecting the list serializer
  for `listing_view`, it will need `featured_image` present or the
  blurry-grid symptom the (mistaken) finding described would become real
  for the first time. No action needed on this AC beyond what's already
  landed — just don't be surprised the field is already there.
- Regression coverage: `apps/blog/tests/test_n_plus_1.py::BlogPostsListFeaturedImageContractTest`
  pins the current response contract (whichever serializer actually serves
  it) so this stays caught either way once AC1 ships.

### 2026-08-17 - Started by completing-todos skill (run 2026-08-17-0246)

- Picked up by automated workflow.

### 2026-08-17 - Implemented and verified

**AC1 — list/detail serializer routing.** Fixed
`BlogPostPageViewSet.get_serializer_class()` in `apps/blog/api/viewsets.py`
to check `self.action in ("list", "listing_view")` instead of just
`"list"` — Wagtail's router (`wagtail.api.v2.router`) registers this
endpoint's GET as `listing_view`, which the old check never matched. Kept
`"list"` too since this class's own `list()`/`retrieve()` wrappers (DRF
test/direct-call compatibility) set that action name.

**AC2 — `apps/blog/views.py` untouched.** Confirmed via `git diff --stat`:
zero changes to that file for the whole todo.

**AC3 — structured `content_blocks` + resolved images.** Added
`content_blocks = StreamFieldAPIField(read_only=True)` (Wagtail's own
`wagtail.api.v2.serializers.StreamField`) to `BlogPostPageSerializer`.
That alone still serializes an `ImageChooserBlock` as a bare PK (Wagtail's
own documented behavior — `Block.get_api_representation()` defaults to
`get_prep_value()`), so also added `apps/blog/blocks.py`:
`APIImageChooserBlock`, used for `plant_spotlight.image` in
`apps/blog/models.py`'s `BlogStreamBlocks`, resolving to
`{id, url, alt, width, height}` — matching the forum's
`serialize_image_for_api` precedent (`packages/wagtail_forum/.../serializers.py`)
for the identical problem, including its `request.build_absolute_uri()`
mechanism (see AC4 below for why, not `get_full_url()`). Required a
migration (`0013_alter_blogpostpage_content_blocks.py`) — the StreamField's
block-type dotted path is part of its deconstruct.

**AC4 — media URL consistency.** Two separate, pre-existing inconsistencies,
both fixed:
- Shape: `related_posts[].featured_image` (`_get_post_image`) was a bare
  URL string while `featured_image`/`featured_image_thumb`/`social_image`
  (`ImageRenditionField`) were `{url, full_url, width, height, alt}` dicts.
  Unified on the dict shape everywhere.
- Mechanism: added `RequestAwareImageRenditionField` (subclasses
  `ImageRenditionField`, overrides `full_url` to use `get_full_url(request,
  ...)` instead of `Rendition.full_url`'s `settings.WAGTAILADMIN_BASE_URL`)
  — collapses two disagreeing host-resolution mechanisms in this file onto
  one. **Important finding, not initially obvious:** this does NOT by
  itself make the host correct in production. Live-probed reasoning +
  source read of `wagtail.api.v2.utils.get_full_url` → `Site.find_for_request`:
  this deploy has no Wagtail `Site` record for its real domain, so
  `get_full_url()` falls back to the seeded default (`localhost:80`) —
  same wrong host `Rendition.full_url` produced, via a different
  mechanism. Confirmed independently by `web/src/services/blogService.ts`'s
  `mediaUrl()` docstring (live-probed 2026-08-16, `http://localhost/media/...`).
  Filed as todo 308 rather than fixed here (infra/Site-config change, not a
  serializer shape fix — different risk class, different todo). Given this,
  `APIImageChooserBlock` (new code, no pre-existing behavior to preserve)
  deliberately uses `request.build_absolute_uri()` instead — genuinely
  host-correct today, no Site dependency — rather than propagating the
  same broken mechanism into new code.
- Also fixed, found via the new tests (not originally in scope but directly
  adjacent): `get_related_posts()`'s per-related-post URL construction
  (`get_full_url(request, post.get_url())`) crashed the WHOLE detail
  endpoint with a 500 (`AttributeError: 'NoneType' object has no attribute
  'startswith'`) when a related post's `get_url()` legitimately returns
  None (unroutable page) — the top-level `get_url()` on the SAME class
  already guards for exactly this, this call site didn't. Extracted
  `_get_post_image` guards `SourceImageIOError`/`OSError` too (missing
  media file), per `docs/rules/wagtail.md`'s binding rule.

**AC5 — web cleanup.** `normalizeContentBlocks` removed from
`blogService.ts` (dead code once AC3 shipped — 3 tests pinning its
JSON-string-parsing workaround removed, since that scenario can no longer
occur). `mediaUrl()` deliberately left untouched — see AC5's note above and
todo 308. Also updated: `PlantSpotlightBlockValue.image` type (was
`{url, title?, alt?}`, now `ImageBlockValue` — matches the real
`APIImageChooserBlock` shape), `RelatedPostSummary.featured_image` type
(was `string | null`, now `BlogPostImage | null`), and their 2 real call
sites (`StreamFieldRenderer.tsx`'s plant_spotlight alt-fallback,
`BlogDetailPage.tsx`'s related-post `<img src>`).

**Incidental cleanup** (formatter/linter surfaced while touching these
files, unrelated to this todo's logic but zero-risk): 5 pre-existing
unused imports in `apps/blog/models.py`
(`django.urls.reverse`, `imagekit.models.ImageSpecField`,
`imagekit.processors.ResizeToFill`, `wagtail.admin.panels.InlinePanel`,
`wagtail.models.Orderable`), and 2 in web
(`BlogCategoryListResponse` in `blogService.ts`, `FetchBlogPostsOptions` +
`logger` in `blogService.test.ts` after its logger-assertion tests were
removed).

**Verification:**

```
$ python -m pytest apps/blog -q
227 passed, 7 skipped, 3 warnings in 70.57s
```

Mutation-tested AC1 (git-stash `viewsets.py` → `BlogPostsListSerializerRoutingTest
::test_list_serves_light_serializer` genuinely fails with `'related_posts'
unexpectedly found in {...}` → restored → green) and AC4's crash fix
(temporarily reverted `_get_post_url`'s None-guard → `test_related_posts_
featured_image_matches_top_level_shape` genuinely fails with `AssertionError:
500 != 200` → restored → green).

```
$ npm run type-check   # clean
$ npm run test -- --run
Test Files  80 passed (80)
     Tests  892 passed (892)
$ npm run lint   # 0 errors (1 pre-existing warning in generated coverage/ artifact)
```

`manage.py spectacular`: confirmed the Wagtail-router-mounted `/api/v2/blog-posts/`
endpoint isn't introspected by drf-spectacular at all (0 matches for
"blog-posts" in the generated schema) — same as `wagtail_forum`'s views in
prior todos. No new errors/warnings attributable to any changed file.

### 2026-08-17 - Code review + repair

`code-review-orchestrator` on the full diff: 0 critical, 2 medium, 3 low, 2
info. All CONFIRMED and repaired except one low, acknowledged as inherent
(not actionable):

- **[medium, fixed]** `APIImageChooserBlock.get_api_representation` caught
  only `SourceImageIOError`, narrower than `_get_post_image`'s
  `(SourceImageIOError, OSError)` for the identical failure mode (missing
  media file). Widened to match.
- **[medium, fixed]** Same method returned `{"error": "SourceImageIOError"}`
  on that failure — not a valid `ImageBlockValue` (no id/url/width/height).
  A client guarding only on `value.image` truthiness would render `<img
  src="undefined">`. Changed to return `None`, matching `_get_post_image`'s
  contract exactly.
- **[low, fixed]** That error path was untested. Added
  `test_plant_spotlight_image_degrades_to_none_on_missing_source_file`
  (mocks `get_rendition` to raise `SourceImageIOError`, asserts 200 +
  `image: None`). Mutation-tested: reverted the fix, confirmed genuine
  failure (`{'error': 'SourceImageIOError'} is not None`), restored, green.
- **[low, fixed]** `BlogPostsListSerializerRoutingTest`'s docstring claimed
  it proves "the N+1 is actually gone" — overclaims relative to what the
  test measures (field absence, not a query count). Reworded to state
  precisely what's proven and why a query-count assertion isn't used here
  (would double-count the unrelated pre-existing
  `BlogCategorySerializer.get_post_count()` N+1 — already documented in
  the implementation Work Log above).
- **[low, acknowledged, not actioned]** Migration hardcodes
  `apps.blog.blocks.APIImageChooserBlock`'s dotted path in `block_lookup`.
  This is inherent to how Wagtail deconstructs ANY custom StreamField block
  class for migrations — not something this PR introduced or can avoid
  short of not writing a custom block at all. No action.
- **[info, fixed]** `RequestAwareImageRenditionField` silently fell through
  to the superclass's `Rendition.full_url` (the Site-based mechanism this
  field exists to replace) when no request is in context, while
  `_get_post_image` explicitly set `full_url: None` for the same case.
  Reviewer's specific claim ("key omitted") was verified false by reading
  `ImageRenditionField.to_representation` — the key is always present from
  the superclass — but the underlying asymmetry (different VALUES on no
  request) was real and worth closing for both consistency and because
  falling back to the Site-based mechanism undermines this todo's own
  point. Now explicit `None` in both places.
- **[info, no action]** Confirmed `RequestAwareImageRenditionField`
  (`get_full_url()`, Sites-based) vs `APIImageChooserBlock`
  (`request.build_absolute_uri()`, request-based) dispatch is intentional
  and documented — see AC4 in the implementation Work Log above for the
  reasoning (todo 308 tracks unifying these once the Site-hostname bug is
  fixed).

Re-verified after repair:

```
$ python -m pytest apps/blog -q
228 passed, 7 skipped, 3 warnings in 65.01s
$ python manage.py check
System check identified no issues (0 silenced).
```

### 2026-08-17 - Completed by completing-todos skill (run 2026-08-17-0246)

- Verification: 4 of 5 acceptance criteria met and checked; the 5th
  (`mediaUrl()` simplification) legitimately re-scoped to todo 308 with
  full evidence, not silently dropped — see that AC's note.
- Review: 7 findings total (2 medium + 3 low fixed, 1 low acknowledged as
  inherent/not-actionable, 2 info no-action). No unaddressed blocking
  findings.
