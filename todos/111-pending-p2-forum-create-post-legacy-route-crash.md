---
status: pending
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

- [ ] Legacy `/api/forum/topics/<id>/posts/create/` is either removed or returns `{ data: ... }`.
- [ ] No crash path exists where `res.data` could be `undefined` in `createPost`.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.
