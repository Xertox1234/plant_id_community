---
status: completed
priority: p4
issue_id: "499"
tags: [forum, moderation, wagtail, backend]
dependencies: []
triage: ready
triaged: 2026-10-02
owner_decision: "Finding 2: exclude the orphan draft opening post from pending_posts(); no Reject-that-deletes row (2026-10-02)"
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

## Resolution

Outcome of each finding (todo sweep run 2026-10-02-0335). Line numbers have moved; names are stable.

1. Fixed. `pending_posts()` lists a crashed edit only while the latest revision is the author's own and no
   `TaskState` points at it. A moderator's draft fails the first test and a cancelled workflow the second;
   a crash passes both, because the API saves the revision as the author and the rollback removes the task
   state. Tests: `test_a_moderators_draft_of_a_live_post_is_not_pending`,
   `test_a_held_edit_whose_workflow_was_cancelled_is_not_pending`. Checked on the way: the default spam
   workflow never offers Cancel (the state has no requester and its task is already rejected); a host's
   human-review workflow, or the shell, can cancel.
2. Fixed per the owner decision. A never-published opening post under a taken-down topic is not pending, and
   it is listed again, as an opening post, if the topic is restored. Test:
   `test_a_draft_opening_post_under_a_taken_down_topic_is_not_pending`. Only replies are listed under a
   taken-down topic now, so the Approve message and the `_approve_allowed` docstring are accurate.
3. Fixed, not as suggested. Post-then-topic stays, because it is the order of every API write (edit, delete,
   reports auto-hide: lock the post, then update the topic's counters), and taking the topic first would
   move the deadlock onto those paths. Instead Reject of an opening post locks every post in the thread, in
   pk order, before the topic, so the cascade no longer takes post locks after the topic row. Tests pin the
   order for Approve and for Reject: `test_approve_locks_the_post_then_its_topic_before_the_lookup`,
   `test_reject_of_a_new_topic_locks_its_whole_thread_before_the_topic`.
4. Fixed. New fixture with an active state and nothing unpublished (a workflow started on the live
   revision): `test_approve_clears_an_active_state_with_nothing_unpublished`. The operand is documented in
   `approve_pending_post`.
5. Fixed, not as suggested. `Post.with_content_json` keeps the live row's `reaction_counts`, so no publish
   path (Approve, the snippet editor's Publish, a workflow finish, a revert) writes a revision's snapshot,
   at no query cost. A recount in the `published` receiver would add three queries to every publish.
   Approve's own recount is gone as redundant. Tests:
   `test_any_publish_of_a_held_edit_keeps_the_live_reaction_counts`,
   `test_the_editor_draft_of_a_held_edit_carries_the_live_reaction_counts`.
6. Fixed. Reject (the GET confirmation, and the POST alike) reports a missing revision and a still-pending row
   that has no Reject on their own: `test_reject_confirmation_without_a_revision_says_so`,
   `test_reject_confirmation_of_a_row_with_no_reject_says_why`.
7. No change; checked, and they match. For a never-published topic the row is the pending title: Wagtail's
   `EditAction` writes a non-live object's row on every save, and the API has no topic edit. Approve
   publishes the topic from its row. So the Topic column, the Reject confirmation and the published title
   are one title, even with the retitle held. Pinned by
   `test_a_new_topics_held_retitle_is_the_title_shown_and_published`.
8. Fixed. `PendingContentView` no longer sets `permission_policy` / `permission_required`; `dispatch()` says
   it is the only gate. `test_publish_post_without_publish_topic_cannot_open_or_approve` still covers it.
9. Fixed. The unreadable-body warning is `[MODERATION]`, not `[WARN]`.

## Acceptance Criteria

- [x] Findings 1–9 are fixed, or each has a line here saying why not.
- [x] Findings 1, 2 and 3 each have a test that fails when the fix is removed.

## Work Log

### 2026-09-29 - Filed from PR #895's review rounds 1–3

Round 2 never repairs, and round 3 (the owner's call) did not either. Round 1's refuter-dismissed high (an
edit published into a taken-down topic) is not here: the owner-approved repair fixed it.

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- `pending_posts()` lists a crashed edit only when it is the author's own unscreened revision (finding 1)
  and leaves out a draft opening post under a taken-down topic, per the owner decision (finding 2). Reject
  locks a new topic's whole thread before the topic (finding 3). Each fix has a test, and a mutation run
  that removes it fails that test.
- Findings 3 and 5 are fixed differently from the suggestion, for the reasons under Resolution: the
  suggested topic-first lock order would deadlock against the API writes, and a receiver recount would cost
  every publish three queries where `Post.with_content_json` costs none.
- Finding 7 needed no change: the check found the Topic column, the Reject confirmation and the published
  title already agree, and a test now pins it.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `python3 .sweep-evidence/g12/findings_499.py` — evidence `.sweep-evidence/g12/499-ac0.txt` (not committed), last lines:

  ```text
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 54 passed, 3 warnings in 23.54s ========================
  RESULT: every finding has an outcome line and the tests pass
  ```

- AC 2: `python3 .sweep-evidence/g12/mutation_check.py` — evidence `.sweep-evidence/g12/499-ac1.txt` (not committed), last lines:

  ```text
        ================ 2 failed, 52 deselected, 3 warnings in 17.87s =================
  == control: the same tests on the unmutated file
        ================ 5 passed, 49 deselected, 3 warnings in 17.74s =================
     pytest exit 0 -> PASS
  RESULT: ALL MUTATIONS CAUGHT
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
