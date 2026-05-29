---
status: completed
priority: p3
issue_id: "112"
tags: [forum, frontend, data-integrity]
dependencies: []
---

# updatePost passes empty string as threadId — returned Post has thread:''

## Problem

`forumService.ts` line 172: `return mapPostToPost(res.data, '')` — the empty string
literal `''` is passed as `threadId`. Every successfully edited post has `thread: ''`
in the returned object. Any downstream code that reads `post.thread` to navigate or
re-fetch will silently receive an empty string and produce a broken URL.

## Recommended Action

`PostUpdateView` should include the topic id in its response, or the caller should
pass the known thread id into `updatePost`. The simplest fix:

1. Add `thread` to `PostUpdateView`'s response serializer output (it's on the `Post.topic_id`).
2. In `forumService.ts`, read it from the response: `mapPostToPost(res.data, String(res.data.topic_id))`.

Alternatively, `updatePost` could accept the `threadId` as a parameter:

```typescript
export async function updatePost(postId: number, threadId: string, data: ...): Promise<Post>
```

Check all callers of `updatePost` before changing the signature.

## Acceptance Criteria

- [x] `updatePost` returns a `Post` with the correct non-empty `thread` field.
- [x] No caller receives `post.thread === ''` after a successful edit.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

Chose Option 1 (backend exposes topic id; frontend reads it) — `updatePost` has
no production callers yet, so making it intrinsically correct beats a signature
change.

Changes:
- `serializers.py`: `PostSerializer` gained `topic_id = IntegerField(read_only=True)`
  (reads the existing `Post.topic_id` FK column — no extra query). It's the
  response shape for `PostUpdateView.update()` → `{data: PostSerializer(post).data}`.
- `forumMappers.ts`: `BackendPost.topic_id?: number`.
- `forumService.ts`: `updatePost` → `mapPostToPost(res.data, String(res.data.topic_id))`
  (was `''`).
- Tests: backend `test_post_serializer_includes_topic_id`; frontend updatePost
  test asserts `p.thread === '77'`.

Verification: backend `Ran 59 tests ... OK` (N+1 pins unaffected); frontend `tsc`
clean, `forumService.test.ts` 19/19.

Review (feature-dev:code-reviewer): 0 critical/high.
- medium — **fixed**: `searchForum` also mapped `thread: ''`; search posts carry
  `topic_id` (same PostSerializer), so it now maps `String(p.topic_id)`. Added a
  search-test assertion (`thread === '12'`). (Strictly beyond AC2's "after an
  edit", but the same bug class — fixed rather than deferred since it was a
  one-liner with the data already present.)
- low — **accepted**: `String(res.data.topic_id)` would yield "undefined" if the
  field were ever absent. Cannot happen today (serializer always includes it);
  guarding with a `''` fallback would silently reintroduce the original bug, so
  left as-is rather than over-engineered.
