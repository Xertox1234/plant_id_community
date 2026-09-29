---
status: pending
priority: p2
issue_id: "495"
tags: [forum, moderation, wagtail, backend]
dependencies: []
---

# Forum pending queue: follow-ups from PR #886's review

## Problem

PR #886 (todo 423) added Reports › Pending forum content. Its two review rounds, plus an owner-approved
third fix, closed the blocking findings:

- a taken-down held edit could be republished;
- Reject could delete a live topic;
- Approve could publish a revision the moderator never saw, or publish twice.

The non-blocking findings below are still open. Every file:line is in
`backend/packages/wagtail_forum/wagtail_forum/admin_views.py` unless noted.

## Findings

1. **A live topic with its own active workflow state never leaves the queue.** `pending_posts()` lists
   the opening post of any topic with an active state (the `Exists(topic_state)` clause), for example a
   spam-held admin edit of a live topic. `approve_pending_post` publishes the topic only when it was
   never published, so that state is never cleared. The page flashes "Published", but the row and the
   dashboard count stay. Publish `topic.latest_revision` (or cancel the state) whenever the topic has
   an active state, or drop the clause for topics already published. No test builds a topic state.
2. **A crashed edit never shows up.** When `submit_edit_for_moderation`'s moderation step crashes, the
   post stays live with an unpublished revision and no workflow state (it was rolled back). The API
   tells the author "pending", but the pending page, now the only signal, never lists it. Add a clause
   for live posts with unpublished changes and no active state, or record crashed edits.
3. **Approving a held edit resets reaction counts.** Publishing the held revision writes back every
   field in its snapshot, including `reaction_counts`. Reactions added between the edit and the
   approval are lost until the next recount. Copy the row's current counts into the revision before
   publishing, or recount afterwards.
4. **An already-live post is republished from an older revision.** For a row whose post is already
   live (a live opening post under a pending topic, or under a topic with an active state),
   `approve_pending_post` republishes `latest_revision` without the `created_at <= updated_at`
   staleness guard that `signals._publish_counterpart` uses, so row-only fields revert. Skip the post
   publish for a live post with no active state, and publish only the topic.
5. **The Kind label says "New topic" for a draft opening post under a live topic.** Since PR #886 this
   only affects the label; Reject is decided by `_reject_target`. Label that case accurately.
6. **`_pending_body` silently shows the live body** when a revision's `body` fails to parse as JSON
   (kimi WARNING on PR #886). The moderator then sees the approved text instead of the pending one.
   Log it, or show that the pending text could not be read.
7. **Tests** (`tests/test_pending_content.py`):
   - The Kind-column checks are bare substrings of the whole admin page ("Edit" is in Wagtail's
     chrome anyway). Assert each row's own cell, or `_pending_kind` per row.
   - The Approve permission check accepts `status_code in (302, 403)`. Pin the one status the admin
     wrapper returns, and its `Location`.
   - The Approve row lock is tested only sequentially (the second request 404s). A concurrent
     double-Approve test would pin the lock itself.

## Acceptance Criteria

- [ ] Findings 1–6 are fixed, with a test each that fails when the fix is removed, or each has a line
      here saying why not.
- [ ] Each gap in finding 7 has a test that fails when the guard it names is removed.

## Work Log

### 2026-09-28 - Filed from PR #886's review (todo 423)
