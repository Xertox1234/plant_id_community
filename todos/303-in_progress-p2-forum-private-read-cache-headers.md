---
status: in_progress
priority: p2
issue_id: "303"
tags: [forum, backend, security, caching]
dependencies: []
---

# Sweep authenticated forum reads for explicit no-store cache headers

## Problem

Authenticated per-user GET endpoints in wagtail_forum that don't use
`PrivateForumReadCacheMixin` emit neither `Cache-Control` nor `Vary`, so a
shared cache/CDN with a "cache everything" rule (this app runs behind
Cloudflare) can store one user's payload and serve it to another — no header
distinguishes them. Found on the new `me/stats/` by the PR #538 round-2
review (fixed there); the review confirmed the same gap pre-exists on
`me/profile/` and possibly other authenticated reads.

## Findings

- `PrivateForumReadCacheMixin` exists precisely for this
  (`backend/packages/wagtail_forum/wagtail_forum/api/views.py`) — some
  authed reads use it, others don't.
- `me/stats/` was fixed + pinned in `test_read_cache_headers.py` in PR #538;
  the pinning pattern to extend is there.
- Absence is invisible to review: nothing fails when a header is missing —
  only the pin list catches drift.

## Recommended Action

1. Enumerate every IsAuthenticated GET in the package (`urls.py` sweep).
2. Apply `PrivateForumReadCacheMixin` to each (me/profile, notifications,
   bookmarks, drafts — whatever the sweep finds).
3. Extend `test_read_cache_headers.py` with a private-paths list mirroring
   `_public_paths()`, asserting the no-store header on every one — so any
   future authed read added without the mixin fails the pin.

## Acceptance Criteria

- [x] Every authenticated GET in wagtail_forum sends explicit
      no-store/private Cache-Control.
- [x] `test_read_cache_headers.py` pins the full private list (drift-proof).
- [x] Full package suite green.

## Work Log

### 2026-08-15 - Filed

- Out of PR #538 scope (pre-existing behavior beyond the PR's endpoints);
  `me/stats/` fixed in-PR as the exemplar.

### 2026-08-17 - Started by completing-todos skill (run 2026-08-17-0246)

- Picked up by automated workflow.

### 2026-08-17 - Implemented and verified

- Enumerated every `IsAuthenticated` GET in the package (`urls.py` sweep,
  cross-checked against `permission_classes` on each view class). Found 6
  missing `PrivateForumReadCacheMixin` beyond the `me/stats/` exemplar:
  - `MeProfileView` (`api/views.py`)
  - `PostRevisionListView`, `PostRevisionDetailView` (`api/views.py`) —
    author-only-while-unedited privacy gate (todo 282), unrelated to caching
  - `NotificationListView`, `NotificationUnreadCountView` (`api/notifications.py`)
  - `UserMentionSearchView` (`api/user_search.py`)
  Added the mixin to each (ahead of the base class in the MRO, matching the
  `MeStatsView` precedent).
- Confirmed 3 views deliberately stay OUT of scope, with reasoning:
  - `PublicProfileView` — `AllowAny`, not authenticated-gated; content is
    identical for every caller (keyed by username in the URL, not by who's
    asking), so it's a `PublicForumReadCacheMixin` candidate, not this todo's
    concern (cross-user leak of PER-CALLER state).
  - `SyncView` — no explicit `permission_classes`; the package/host default
    (`IsAuthenticatedOrReadOnly`) makes a GET-only view like this
    anonymous-accessible, so it's not "IsAuthenticated." Its response body
    doesn't reference `request.user` (confirmed via source read) — no
    per-caller field to leak either.
  - `NotificationMarkReadView`, `TopicSubscriptionView` — POST/DELETE only,
    no GET method at all; the mixin only touches GET/HEAD.
- Extended `test_read_cache_headers.py`: replaced the narrow
  `test_me_stats_is_never_shared_cached` with a general
  `_authenticated_only_paths()` list (mirroring `_public_paths()`/
  `_private_paths()`) covering all 6 fixed endpoints + me/stats/, and one
  test asserting `no-store`/`private`/`Vary: Cookie, Authorization` on every
  path — any future `IsAuthenticated` GET added without the mixin now fails
  this pin, per the AC.

  ```
  $ python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_read_cache_headers.py -q
  7 passed, 1 warning in 17.50s
  ```

- Verified the new test actually catches drift (not hollow): git-stashed all
  6 mixin additions, re-ran — genuinely fails (`KeyError: 'cache-control'` on
  the first unfixed path, `me/profile/`), restored the fix, re-ran green.
- Full package + host suite (no Topic list field touched, narrower subset
  sufficient per `docs/rules/testing.md`):

  ```
  $ python -m pytest packages/wagtail_forum apps/forum_host -q
  767 passed, 2 warnings in 217.59s
  ```

- `manage.py spectacular` schema generation: no new errors/warnings on any of
  the 6 changed views (checked by grepping the class names in the output).
