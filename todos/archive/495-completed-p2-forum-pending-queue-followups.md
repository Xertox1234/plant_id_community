---
status: completed
priority: p2
issue_id: "495"
tags: [forum, moderation, wagtail, backend]
dependencies: []
triage: ready
triaged: 2026-09-29
owner_decision: "Owner picked: F1 publish the topic's latest revision so its active state clears; F2 add a pending-page clause for live posts with unpublished changes and no active state; F3 recount reactions after publishing; F9 keep a held reply in a taken-down topic listed but offer only Reject (no Approve); F10 also require publish permission on Topic (2026-09-29)"
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
7. **Reject is an unchecked link to Wagtail's generic delete view** (medium, final review round).
   Nothing re-checks the topic between page load and the delete confirmation. If another moderator
   approves in between, Reject hard-deletes a now-live thread and all its replies, breaking
   `_reject_target`'s "never a live topic" rule. Add a POST reject view shaped like
   `ApprovePendingView`: lock the post, re-run `pending_posts()` and `_reject_target()`, compare the
   revision, then delete.
8. **A real Reject doesn't return to the pending page** (medium). Wagtail 8.0's `confirm_delete.html`
   POSTs to the delete URL without `next`, so the success redirect goes to the snippet index. Only
   the Cancel link returns. The column docstring claims otherwise. Carry `next` through, which a
   custom reject view (finding 7) would do.
9. **A held reply in a topic that was later taken down stays listed** (low). Approve publishes it
   into the hidden topic and fires `reply_added`, which notifies subscribers with a link that 404s.
   Exclude replies whose topic was taken down, or offer only Reject for them.
10. **Approve publishes the Topic with `skip_permission_checks=True` after checking only
    `publish_post`** (low). A host that grants `publish_post` without `publish_topic` lets that user
    publish topics. Also require publish on Topic, or document that one implies the other.
11. **A second Approve shows the admin 404 page** (low), even when the first request published the
    post (a double-click). Redirect to the pending page with an "already decided" message, and keep
    the no-republish guarantee.
12. **The dashboard pending item shows for every admin user** (low), linking to a page gated on
    `publish_post`, and runs the `pending_posts()` count on every dashboard load. Return early unless
    `user_can_moderate_pending(request.user)`.
13. **Tests** (`tests/test_pending_content.py`):
    - The Kind-column checks are bare substrings of the whole admin page ("Edit" is in Wagtail's
      chrome anyway). Assert each row's own cell, or `_pending_kind` per row.
    - The Approve permission check accepts `status_code in (302, 403)`. Under `require_admin_access`
      a non-AJAX `PermissionDenied` always redirects, so 403 is unreachable: assert 302 and
      `Location == reverse("wagtailadmin_home")`.
    - `pending_posts()`'s second clause (opening post live, topic still a draft: the todo 422 repair
      case) has no fixture that reaches it alone; deleting it leaves the suite green.
    - The Reject and title links are asserted only as `href` strings, never followed by a
      "Forum Moderators" member. Add a click-through test (the todo 345 shape).
    - `default_ordering = "submitted_at"` and the `pk` tie-break are untested.
    - `tests/test_topic_approval.py:166` (not changed by PR #886) hardcodes `/cms/` in this
      host-agnostic package. Use `reverse`.
    - The Approve row lock is tested only sequentially (the second request 404s). A concurrent
      double-Approve test would pin the lock itself.

## Acceptance Criteria

- [x] Findings 1–12 are fixed, with a test each that fails when the fix is removed, or each has a line
      here saying why not.
- [x] Each gap in finding 13 has a test that fails when the guard it names is removed.

## Work Log

### 2026-09-28 - Filed from PR #886's review (todo 423)

Findings 7–12, and the last four test gaps, come from the final review round after the owner-approved
fix. It found no blocking issues; PR #886 merged as 358d774a.

### 2026-09-29 - Implemented by the todo sweep (run 2026-09-29-1448)

- `pending_posts()` gains the crashed-edit clause (F2) and no longer lists a taken-down topic through
  its own state. Approve publishes a topic's latest revision when it has an active state and keeps the
  row's counters (F1), skips republishing a live post with nothing pending (F4), recounts reactions
  (F3), and refuses a held reply in a taken-down topic, which now gets Reject only (F9).
- Reject is now `RejectPendingView`: a confirmation page and a POST that locks the row, re-runs
  `pending_posts()` and `_reject_target()`, compares the revision, deletes through the registered
  delete action, and returns to the pending page (F7, F8). It needs `delete` on its target.
- The page, Approve, menu item and dashboard item need `publish` on Post and Topic (F10, F12). A
  second Approve redirects with "already decided" instead of 404ing (F11), which changed three
  existing tests' 404 assertions. "Opening post" labels a draft opening post under a live topic (F5),
  and an unreadable pending body is logged and flagged, not replaced by the live one (F6).
- F13: per-row Kind cells, a 302-to-home permission assertion, a fixture reaching the second clause
  alone, a Forum Moderators click-through, ordering and tie-break tests, `reverse()` in
  `test_topic_approval.py`, and a query-order test for the row lock. Real threads are out because
  `docs/rules/testing.md` bans `django_db(transaction=True)`.

### 2026-09-29 - Verified by the todo sweep (run 2026-09-29-1448)

- AC 1: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_ea0dd9bf-e46-1/.sweep-evidence/g1/mutation_check.py ac0` — evidence `.sweep-evidence/g1/495-ac0.txt`, last lines:

  ```text
      pytest exit 1 -> CAUGHT; file restored: True
      =========================== short test summary info ============================
      FAILED packages/wagtail_forum/wagtail_forum/tests/test_pending_content.py::test_dashboard_pending_item_is_only_for_users_who_can_open_the_page
      ============================== 1 failed in 0.99s ===============================
  RESULT: ALL MUTATIONS CAUGHT
  ```

- AC 2: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_ea0dd9bf-e46-1/.sweep-evidence/g1/mutation_check.py ac1` — evidence `.sweep-evidence/g1/495-ac1.txt`, last lines:

  ```text
      pytest exit 1 -> CAUGHT; file restored: True
      =========================== short test summary info ============================
      FAILED packages/wagtail_forum/wagtail_forum/tests/test_pending_content.py::test_approve_locks_the_post_row_before_it_looks_the_post_up
      ============================== 1 failed in 0.94s ===============================
  RESULT: ALL MUTATIONS CAUGHT
  ```

### 2026-09-29 - Completed by the todo sweep (run 2026-09-29-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
