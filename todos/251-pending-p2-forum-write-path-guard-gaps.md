---
status: pending
priority: p2
issue_id: "251"
tags: [forum, wagtail, moderation, bug]
dependencies: []
source_review: "docs/reviews/2026-07-02-2252-forum-write-path-trial.md"
source_finding: "5"
---

# Close the forum write-path guard gaps (DELETE on locked topics, per-post locks, impossible 409 advice)

## Context

Todo-244's review trial verified three guard gaps in `PostWriteView`
(`backend/packages/wagtail_forum/wagtail_forum/api/views.py`), re-confirmed on
main `d52cf14`. Findings #5–#7 in the source review. Blocks the forum-writes
deploy; sibling of todo 250 (same file, different mechanisms).

## Problem

1. **DELETE skips the closed/locked-topic guard** (#5): PATCH 409s on
   `topic.is_closed or topic.locked` (views.py:401) but the delete handler
   checks only `is_opening_post` (views.py:434) — an author can remove posts
   from a moderator-frozen thread, and the unpublish recount mutates the
   frozen topic's `reply_count`/`last_post_at`.
2. **Per-post `LockableMixin` lock ignored** (#6): Post is admin-lockable
   (LockableMixin; the registered SnippetViewSet exposes the lock UI), but no
   write path checks `post.locked` — a trusted author's PATCH publishes over
   a moderator-locked post. Wagtail only enforces locks in admin views, never
   programmatically.
3. **Impossible 409 advice** (#7): DELETE on an opening post returns
   "Cannot delete the opening post; delete the topic." (views.py:435) but no
   topic-delete endpoint exists in either URL config — the advertised
   follow-up is impossible for API clients (admin-only).

## Recommended Action

- Add the `is_closed or locked` 409 guard to the DELETE handler (mirroring
  PATCH; decide whether moderators bypass it — PATCH currently doesn't).
- Check `post.locked` in `_get_editable` (409 or 403 for non-moderators;
  Wagtail semantics: locked = only the locking user/privileged users edit).
- Fix the 409 message to describe reality (e.g. "opening posts cannot be
  deleted via the API") — or, if topic deletion is wanted, that is a spec
  change to raise with the user first, not part of this todo.

## Technical Details

- Files: `backend/packages/wagtail_forum/wagtail_forum/api/views.py`,
  tests in `W/tests/api/test_post_edit_delete.py`.
- The spec decision log (todo 231) explicitly chose "opening-post delete
  rejects 409" and "delete=unpublish" — keep those contracts.
- Guard tests must cover EACH `or` operand independently
  (docs/rules + cross-cutting-reviewer or-guard rule; see also todo 253).

## Acceptance Criteria

- [ ] Test: DELETE on a post in a closed topic → 409; in a locked topic → 409
      (two separate tests, one per operand).
- [ ] Test: PATCH and DELETE on a `post.locked` post are rejected for the
      author; moderator behavior decided + tested.
- [ ] The opening-post 409 message no longer references a nonexistent
      endpoint (schema description at views.py:429 updated to match).
- [ ] Full forum suite green.

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (findings #5–#7), re-verified on main d52cf14.
