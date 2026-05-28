---
status: pending
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

- [ ] `PostSerializer` includes `reaction_counts` in its response.
- [ ] `mapPostToPost` maps the field (no more hardcoded `{}`).
- [ ] Reaction counts display correctly on thread load without any user interaction.
- [ ] No N+1 query for reaction counts (use annotation or prefetch).

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.
