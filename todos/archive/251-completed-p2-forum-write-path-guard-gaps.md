---
status: completed
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

- [x] Test: DELETE on a post in a closed topic → 409; in a locked topic → 409
      (two separate tests, one per operand).
- [x] Test: PATCH and DELETE on a `post.locked` post are rejected for the
      author; moderator behavior decided + tested.
- [x] The opening-post 409 message no longer references a nonexistent
      endpoint (schema description at views.py:429 updated to match).
- [x] Full forum suite green.

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (findings #5–#7), re-verified on main d52cf14.

### 2026-07-04 - Started by completing-todos skill (run 2026-07-04-0200)

- Picked up by automated workflow.

### 2026-07-04 - Implemented (run 2026-07-04-0200)

Changes in `wagtail_forum/api/views.py` (`PostWriteView`):

- **#6 per-post lock** — `_get_editable` now computes `is_moderator` once and,
  after the author-or-moderator check, raises `Conflict("Post is locked.")` when
  `post.locked and not is_moderator`. Enforced on BOTH PATCH and DELETE (shared
  helper). Moderators bypass — Wagtail's "privileged users edit locked objects".
- **#5 DELETE topic guard** — DELETE now mirrors PATCH: `Conflict("Topic is
  closed or locked.")` when `topic.is_closed or topic.locked`, before the
  opening-post check. Delete-accurate wording (not PATCH's "…to edits").
- **#7 impossible message** — opening-post message → `"Opening posts cannot be
  deleted via the API."`; DELETE `@extend_schema` description updated to match
  (dropped the "delete the topic instead" advice — no topic-delete endpoint
  exists in either URL config).

**Tradeoff (chosen, not overlooked):** mirroring PATCH means the DELETE topic
guard has NO moderator bypass, so moderators also lose delete-on-a-frozen-thread.
This is a reduction from the prior no-guard behavior, taken deliberately per the
todo's "mirror PATCH; PATCH currently doesn't [bypass]" — a delete mutating a
closed/locked topic's `reply_count`/`last_post_at` would desync it. If product
wants moderator override on frozen threads, that's a separate spec change (would
apply to PATCH too).

Tests added to `tests/api/test_post_edit_delete.py` (per-operand isolation,
message-distinguished 409s): `test_delete_on_closed_topic_conflicts`,
`test_delete_on_locked_topic_conflicts`, `test_edit_locked_post_rejected_for_author`,
`test_delete_locked_post_rejected_for_author`, `test_moderator_bypasses_post_lock`;
extended `test_delete_opening_post_conflicts` with the #7 message assertion.

Verification:
- `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_post_edit_delete.py
  --create-db` → **17 passed**.
- Full forum suite `pytest packages/wagtail_forum/ apps/forum_host/ --create-db`
  → **164 passed**.

### 2026-07-04 - Completed by completing-todos skill (run 2026-07-04-0200)

- Verification: all 4 acceptance criteria passed (17 file tests + 164 full forum
  suite, quoted above).
- Review: `code-review-orchestrator` returned 0 blocking findings (0 critical/
  high). 2 INFO findings, accepted (below-medium, not blocking):
  - `test_moderator_bypasses_post_lock` covers moderator PATCH of a locked post
    but not moderator DELETE; the bypass is the shared `_get_editable` helper, so
    the untested DELETE variant runs identical code (moderator DELETE is also
    covered on a non-locked post by `test_moderator_can_edit_and_delete_others_post`).
  - Message asymmetry — PATCH "Topic is closed to edits." vs DELETE "Topic is
    closed or locked." for a frozen topic; intentional (operation- vs
    condition-specific wording), both 409.
