---
status: pending
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

- [ ] `updatePost` returns a `Post` with the correct non-empty `thread` field.
- [ ] No caller receives `post.thread === ''` after a successful edit.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.
