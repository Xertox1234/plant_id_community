---
status: pending
priority: p4
issue_id: "499"
tags: [forum, moderation, wagtail, backend]
dependencies: []
---

# Forum pending queue: follow-ups from PR #895's review

## Problem

PR #895 (todo 495) closed the pending-queue gaps from PR #886's review. It went through three review rounds.
Round 2 blocked it on a high: Approve published a live topic's held edit that the row never showed. The owner
chose to narrow that fix and to close the edits-under-a-taken-down-topic gap as well, and approved a third
round (2026-09-29). Round 3 found nothing blocking.

The findings below were rated non-blocking and still hold after the repair. The earlier findings about
publishing a topic's latest revision, `TOPIC_ROW_FIELDS` and the topic-edit row were dropped: the repair
removed that path. Every file:line is in `backend/packages/wagtail_forum/wagtail_forum/admin_views.py` unless
noted. Line numbers are as of bb6f1c8d.

## Findings

1. **A moderator's own draft, or a cancelled workflow, becomes a one-click Approve row** (medium, rounds 2
   and 3). The crashed-edit clause `Q(live=True, has_unpublished_changes=True)` (F2) also matches a
   moderator's plain "Save draft" on a live post's snippet edit view, and "Cancel workflow" on a held edit.
   Both leave the same state: unpublished changes and no workflow state. Any other moderator can then
   publish that work-in-progress with Approve. It is attributed to `post.author`, not the editor, and skips
   trust and spam routing. No test covers it. Suggested: list the row only when the latest revision's
   `user` is the post's author (a crashed edit is always the author's own submission). Add tests for a
   moderator's Save and for Cancel workflow.
2. **A never-published opening post under a taken-down topic is a row nobody can act on** (medium, round 3,
   reported three times). It comes from the owner-approved repair. When a topic that went live from the
   admin is taken down while its opening post is still a draft, `pending_posts()` lists the post, because
   `first_published_at` is null. It gets no Approve (`_approve_allowed` is False) and no Reject
   (`_reject_target` is None, since the topic is not pending). The dashboard count stays up until the
   topic is restored. The Approve message (`:462`) calls the row a reply and says "Reject it instead", and
   the `_approve_allowed` docstring claims only a reply is listed there. Suggested: exclude opening posts
   under a taken-down topic in `pending_posts()`, or give the row a Reject that deletes the post. Add a test
   that reuses `test_reject_never_targets_a_live_topic`'s fixture plus a take-down.
3. **Possible lock-order deadlock** (medium, round 2). `_lock_pending_post` locks the Post, then the Topic.
   Rejecting a new topic cascades a delete that needs its sibling posts' locks, while a concurrent Approve
   or Reject of a reply locks that Post first. Suggested: lock the Topic row first, then the Post.
   Separately, no test pins the Topic lock or the Post-then-Topic order (`tests/test_pending_content.py`,
   the query-order test), for either Approve or Reject.
4. **The Approve guard's third operand is untested** (medium, round 1, `:515`). Every fixture that reaches
   `post.current_workflow_state is not None` also has `has_unpublished_changes=True`, so deleting that
   operand keeps the suite green. Add a fixture with an active state and no unpublished changes, or document
   the operand as defensive.
5. **Reaction counts are recounted only by the pending page's Approve** (low, round 3). Approving a held edit
   through Wagtail's workflow action on the snippet edit page still publishes the revision's stale
   `reaction_counts`. Recount in the Post branch of the `published` receiver instead, so every publish path
   keeps live counts.
6. **The Reject confirmation GET misreports why nothing happened** (low, rounds 1 and 2, `RejectPendingView.get`).
   - A missing `?revision=` is read as `''` and reported as "changed after this page loaded".
   - A row still pending but with no Reject target (a held edit, or an opening post under a live topic) is
     reported as "already decided, changed or removed". Tell the two cases apart.
7. **The Topic column shows the row's title, not a held revision's** (low, worker note and round 2). For a
   never-published topic with a held revision of its own, the Topic column and the Reject confirmation read
   `post.topic.title`. Check whether that matches what Approve publishes and what Reject deletes, and show
   the pending title where they differ.
8. **The class-level permission attributes read as the gate but are not** (low, round 3, `PendingContentView`).
   `permission_policy` / `permission_required` check only Post. The real gate is the `dispatch()` override
   that requires publish on Post and Topic. Drop the attributes, or comment that `dispatch()` is
   load-bearing. `test_publish_post_without_publish_topic_cannot_open_or_approve` catches a regression today.
9. **`[WARN]` log prefix** (low, rounds 2 and 3, `:448`). Per `docs/rules/api.md`, the bracket tag names a
   subsystem (`[CACHE]`, `[AUTH]`), not a severity. Use `[FORUM]` or similar.

## Acceptance Criteria

- [ ] Findings 1–9 are fixed, or each has a line here saying why not.
- [ ] Findings 1, 2 and 3 each have a test that fails when the fix is removed.

## Work Log

### 2026-09-29 - Filed from PR #895's review rounds 1–3

Round 2 never repairs, and round 3 (the owner's call) did not either. Round 1's refuter-dismissed high (an
edit published into a taken-down topic) is not here: the owner-approved repair fixed it.
