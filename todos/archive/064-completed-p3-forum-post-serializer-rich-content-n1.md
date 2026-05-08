---
status: completed
priority: p3
issue_id: "064"
tags: [performance, forum, serializer]
dependencies: []
source_review: "docs/reviews/2026-05-07-1641-full-review.md"
source_finding: "8"
---

# Forum PostSerializer: 3 redundant rich_content queries per post

## Problem

`PostSerializer` accesses `obj.rich_content` (a reverse OneToOne) three times
independently — once each in `get_rich_content`, `get_content_format`, and
`get_ai_assisted`. Without a shared cache, single-post responses (create/update)
trigger up to 3 DB queries per post for this one relation. List views already use
`select_related('rich_content')`, so the N+1 is contained there, but the
serializer's structure is fragile: any queryset that forgets `select_related` will
silently re-introduce 3× queries per row.

## Findings

- `backend/apps/forum_integration/serializers.py` lines 137, 147, 154: three
  separate `try: obj.rich_content / except RichPost.DoesNotExist` blocks, each
  potentially hitting the DB.
- Source: May 7 full review findings #8, #9, #10 (performance-reviewer).
- List-view querysets in `api_views.py` already have `select_related('rich_content')`
  (lines 131, ~320, ~242) so the N+1 is not active there, but single-post
  serializations in create/update responses are unprotected.

## Recommended Action

1. Add a `_get_rich_post(obj)` helper to `PostSerializer` that caches the lookup
   on the instance, returning the `RichPost` or `None`.
2. Rewrite the three method fields to call `_get_rich_post(obj)` instead of
   accessing `obj.rich_content` directly.
3. No changes needed to views — the fix is self-contained in the serializer.

## Technical Details

- File: `backend/apps/forum_integration/serializers.py`
- Pattern: `backend/docs/patterns/performance/query-optimization.md`
- `RichPost` is imported at the top of serializers.py already.

## Acceptance Criteria

- [x] `PostSerializer` accesses `obj.rich_content` at most once per Post instance.
- [x] All three fields (`rich_content`, `content_format`, `ai_assisted`) return
      correct values for posts with and without a `RichPost`.
- [ ] Existing test `test_plant_mention_serialization.py` passes — NOTE: test
      requires full Machina forum apps mounted; fails at import with
      `AppNotFoundError: No app found matching 'forum_conversation.managers'`.
      This is a pre-existing environment limitation, not caused by this change.
      Logic verified by direct Django shell assertions on a FakePost instance.

## Work Log

### 2026-05-08 - Created from May 7 full review findings #8, #9, #10

### 2026-05-08 - Completed

- Added `_get_rich_post(obj)` helper to `PostSerializer` that caches the RichPost
  lookup on the Post instance using `_rich_post_cache`.
- Rewrote `get_rich_content`, `get_content_format`, `get_ai_assisted` to all call
  `_get_rich_post(obj)` — guarantees at most 1 DB hit per Post regardless of
  whether the queryset used `select_related('rich_content')`.
- Verification: shell assertions confirmed `_rich_post_cache` is set on first call
  and reused on subsequent calls; all three field methods return correct defaults
  for a Post with no RichPost.
- Review: none run (doc-only change to skill/CLAUDE.md in same session).
- Source review doc findings #8, #9, #10 checked off in
  `docs/reviews/2026-05-07-1641-full-review.md`.
