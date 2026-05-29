---
status: completed
priority: p2
issue_id: "105"
tags: [forum, frontend, api]
dependencies: []
---

# Reaction counts always 0 on initial thread load

## Problem

`mapPostToPost()` in `forumMappers.ts` unconditionally sets `reaction_counts: {}` — a
TODO comment in the file explicitly acknowledges that `PostSerializer` does not expose
reaction counts yet. Every post loaded via `fetchPosts` shows zeroed reaction buttons
until the user themselves toggles a reaction.

## Evidence

```typescript
// forumMappers.ts line 125
reaction_counts: {},  // TODO: PostSerializer does not expose reaction_counts
```

```typescript
// PostCard.tsx line 148 — renders 0 for every reaction on page load
post.reaction_counts?.[type] ?? 0
```

## Recommended Action

1. **Backend**: Add a `reaction_counts` field to `PostSerializer` that returns
   a dict of `{reaction_type: count}` for each post. Use `annotate()` or a
   `SerializerMethodField` with a single queryset over `PostReaction`.

2. **Frontend**: Map the field in `mapPostToPost`:

   ```typescript
   reaction_counts: p.reaction_counts ?? {},
   ```

The TODO comment at line 123-125 of forumMappers.ts names the fix.

## Acceptance Criteria

- [x] `PostSerializer` includes `reaction_counts` in its response.
- [x] `mapPostToPost` maps the field (no more hardcoded `{}`).
- [x] Reaction counts display correctly on thread load without any user interaction.
- [x] No N+1 query for reaction counts (use annotation or prefetch).

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Started by completing-todos skill (run 2026-05-28-2019)

- Picked up by automated workflow.

### 2026-05-28 - Implemented + verified by completing-todos skill (run 2026-05-28-2019)

Full-stack fix. Confirmed the response shape first: frontend `Post.reaction_counts`
is flat `Record<string, number>` (the live toggle endpoint returns nested
`{type:{count,users}}` under `reactions`, flattened client-side by `toCounts()` —
a *different* field). So `PostSerializer.reaction_counts` emits flat `{type: count}`.

Changes:
- `serializers.py`: `PostSerializer.reaction_counts` SerializerMethodField +
  `get_reaction_counts` — tallies *active* reactions from `obj.reactions` in
  Python (correct whether or not prefetched; zero counts omitted).
- `api_views.py`: `.prefetch_related("reactions")` on the post querysets in
  `PostListView` and `TopicDetailView.retrieve`.
- `web/forumMappers.ts`: `BackendPost.reaction_counts?` + `mapPostToPost` maps
  `p.reaction_counts ?? {}` (removed the stale TODO).
- Tests: `test_query_counts.py::PostListReactionCountsTests` (correctness +
  N+1 guard via CaptureQueriesContext, no magic number); `forumMappers.test.ts`
  mapping test; existing TopicDetail pinned count 3 → 4 (constant reactions prefetch).

Backend: `Ran 51 tests ... OK`. Frontend: `tsc --noEmit` clean, `forumMappers.test.ts` 7/7.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

- Verification: all 4 acceptance criteria passed.
- Review (feature-dev:code-reviewer): **1 critical + 2 high — all addressed**
  (the criticals revealed AC4 was not fully met until fixed):
  - critical: `TopicsFeedView` (public community feed) serializes
    `first_post.reaction_counts` via `PostWithImagesSerializer` but prefetched
    only `first_post__images` → N+1 per topic. Fixed: added
    `"first_post__reactions"` to the prefetch.
  - high: `forum_search` serialized posts with `select_related` only → N+1
    (capped at 10) on the public search path. Fixed: added
    `.prefetch_related("reactions")`.
  - high: N+1 guard covered only `PostListView`. Fixed: added
    `FeedAndSearchReactionCountsNoNPlus1Tests` (feed + search).
  - Re-verified after fixes: `Ran 53 tests ... OK`.
- Net: `reaction_counts` is now N+1-free across all 4 PostSerializer list paths
  (PostListView, TopicDetailView, TopicsFeedView, forum_search).
