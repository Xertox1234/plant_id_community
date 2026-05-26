---
status: pending
priority: p2
issue_id: "099"
tags: [forum, frontend, data-integrity]
dependencies: []
---

# Wire is_pinned, is_locked, reaction_counts from backend in forumMappers

## Problem

`web/src/services/forumMappers.ts` hardcodes three fields in `mapTopicToThread`:

- `is_pinned: false` (line ~105) — never shows pinned topics as pinned in the UI
- `is_locked: false` (line ~105) — never shows locked threads as locked
- `reaction_counts: {}` (line ~124) — reaction summary always empty on thread cards

The backend sends `type` (Machina's pinned type) and `status` (locked) on the `BackendTopic`
shape; `reaction_counts` comes from the PostReaction aggregation endpoint.

## Recommended Action

1. In `forumMappers.ts`, map `is_pinned` from `topic.type === TOPIC_TYPE_STICKY` (value 2
   per Machina constants) and `is_locked` from `topic.status === TOPIC_UNLOCKED` (0 = unlocked,
   1 = locked).
2. For `reaction_counts`: either extend the topics list endpoint to include aggregated counts
   (backend change needed in `TopicSerializer`), or fetch them lazily in the thread card.
3. Add `BackendTopic` type fields `type` and `status` to `forumMappers.ts`'s backend type.

## Acceptance Criteria

- [ ] Pinned topics display the pinned indicator in `ThreadCard`.
- [ ] Locked threads display the locked indicator and disable reply input.
- [ ] `reaction_counts` on thread cards reflects real data (or is explicitly deferred with a
      TODO comment explaining the missing endpoint).
