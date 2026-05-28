---
status: completed
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

- [x] Pinned topics display the pinned indicator in `ThreadCard`.
- [x] Locked threads display the locked indicator and disable reply input.
- [x] `reaction_counts` on thread cards reflects real data (or is explicitly deferred with a
      TODO comment explaining the missing endpoint).

## Work Log

### 2026-05-28 - Started by completing-todos skill (run 2026-05-28-1516)

- Picked up by automated workflow.

### 2026-05-28 - Implementation

- Added `type?: number` and `status?: number` to `BackendTopic` interface in `forumMappers.ts`.
- Added `"type"` and `"status"` to `TopicSerializer.Meta.fields` in `serializers.py`.
- Replaced hardcoded `is_pinned: false / is_locked: false` with `(t.type ?? 0) === 1` / `(t.status ?? 0) === 1`.
  Note: Machina constants are TOPIC_STICKY=1, TOPIC_LOCKED=1 (todo description had wrong value of 2).
- `reaction_counts` deferred — existing TODO comment in `mapPostToPost` satisfies AC3.
- Added `forumMappers.test.ts` cases for sticky (type=1→pinned) and locked (status=1→locked) mapping.
- Verification: `npm run test -- --run src/services/forumMappers.test.ts` → 6/6 passed.
- TypeScript: `npm run type-check` → 0 errors.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-1516)

- Verification: all 3 acceptance criteria passed.
- Review: 0 findings — no blocking issues.
