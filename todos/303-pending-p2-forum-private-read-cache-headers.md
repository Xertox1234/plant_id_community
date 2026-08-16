---
status: pending
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

- [ ] Every authenticated GET in wagtail_forum sends explicit
      no-store/private Cache-Control.
- [ ] `test_read_cache_headers.py` pins the full private list (drift-proof).
- [ ] Full package suite green.

## Work Log

### 2026-08-15 - Filed

- Out of PR #538 scope (pre-existing behavior beyond the PR's endpoints);
  `me/stats/` fixed in-PR as the exemplar.
