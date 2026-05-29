---
status: completed
priority: p2
issue_id: "111"
tags: [forum, frontend, api]
dependencies: []
---

# createPost reads res.data but legacy route returns res.post — crash if legacy URL hit

## Problem

`forumService.ts` line 163: `createPost` casts the response as
`{ data: BackendPost }` and reads `res.data`. The modern view `PostCreateView` at
`/api/v1/forum/posts/create/` correctly returns `{ data: ... }`.

However, the legacy `CreatePostView` is still registered at
`/api/forum/topics/<id>/posts/create/` and returns `{ message, post: ... }` (key `post`,
not `data`). If any caller hits the legacy URL, `res.data` is `undefined` and
`mapPostToPost(undefined, ...)` throws accessing `undefined.id`.

## Recommended Action

Two options — pick one:

**Option A (preferred):** Remove the legacy `CreatePostView` URL registration from
`api_urls.py` or `urls.py` if it is no longer used by any frontend caller.

**Option B:** Normalise the legacy view's response shape to match the modern one
(`{ data: ... }`).

Before either: confirm no current caller uses the legacy URL by grepping all frontend
services and the mobile app for the old path.

## Acceptance Criteria

- [x] Legacy `/api/forum/topics/<id>/posts/create/` is either removed or returns `{ data: ... }`.
- [x] No crash path exists where `res.data` could be `undefined` in `createPost`.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

**Decision: Option A (remove) + harden createPost** (user choice). Verified first
that no web/mobile production caller hit the legacy route — the web `createPost`
and its test use only the modern `/posts/create/` (`PostCreateView`, returns
`{data}`).

Changes:
- `api_urls.py`: removed the `create_post_legacy` URL registration.
- `api_views.py`: deleted the now-dead `CreatePostView` class (referenced only by
  the removed URL; no dangling imports — its imports are shared with other views).
- `forumService.ts`: `createPost` now throws a clear error if `res?.data` is
  missing, instead of crashing in `mapPostToPost` on `undefined.id`.
- Tests: `test_legacy_post_create_route_removed` (asserts
  `reverse("forum_api:create_post_legacy")` → `NoReverseMatch`; used reverse-by-name
  because a Wagtail catch-all matches arbitrary paths so `resolve()` won't 404);
  `forumService.test.ts` guard test (old `{message, post}` shape → clear throw).

Verification:
- Backend `Ran 58 tests ... OK (skipped=3)`. Frontend `tsc` clean,
  `forumService.test.ts` 19/19.
- AC1 covered by the running `test_legacy_post_create_route_removed`; AC2 by the
  running frontend guard test.

Review (feature-dev:code-reviewer): 0 critical/high; removal confirmed complete
and safe (both `/api/v1/forum/` and `/api/forum/` mounts cleaned via the single
api_urls edit). One **Important** observation, accepted as pre-existing:
- `test_reply_with_plant_mention_and_fetch_enriched` (whose reply call I migrated
  to the modern route + `topic` in body) is `@unittest.skip`'d under **todo 067**
  ("Invalid version in URL path"). I temporarily un-skipped it to check: it fails
  at the *topic-create* step on the `/api/forum/` mount (the 067 bug), before
  reaching my migrated reply line — so the migration is correct-by-inspection but
  has **no running coverage** until 067 is fixed. The migration was still
  necessary: leaving it on the removed legacy route would make it error when 067
  un-skips it. Re-skipped; not introduced by this todo.
