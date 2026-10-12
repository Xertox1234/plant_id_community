---
status: completed
priority: p4
issue_id: "588"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Item 1: decline as the intended todo 432 behaviour; a clean unheld edit publishes (owner, 2026-10-11)"
---

# Follow-ups from PR #1035 (todos 554, 557, 561, 574, 579)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1035 (forum pending-edit screen, summary panel and log-prefix gate). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

Note from the run: items 5 and 6 were fixed on the PR before it merged (NEEDS_CHANGES edits are no longer published by a topic publish, and JSON autosaves skip the re-screen; see the dropped list). Item 1 survives only for its remaining part: a clean, unheld later edit still publishes with no staleness check.

## Findings

PR #1035 (todo sweep run 2026-10-11-1448, group g2, todos 554, 557, 561, 574, 579); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **medium** `backend/packages/wagtail_forum/wagtail_forum/signals.py:334` Todo 579 lets the author PATCH a pending opening post. A Topic publish outside the pending page (snippet Publish, clean Topic SpamCheckTask finish) runs `_publish_counterpart`(prefer_latest_revision=True) and publishes the newest post revision, even one spam held in NEEDS_CHANGES or one no moderator saw. | also: `_get_patchable` now lets an author PATCH their pending opening post, so publishing the topic from the Topic snippet editor publishes the post's newest revision via `_publish_counterpart`, even a spam-held (NEEDS_CHANGES) edit. That edit may have been saved after the moderator read the body, and nothing checks for staleness. (signals.py:303) | New since 579: the author can PATCH a pending opening post. A Topic Publish from the snippet editor then publishes the post's latest revision, even one the re-screen flagged (NEEDS_CHANGES) or one written after the moderator looked. The pending page's revision check is bypassed. | PATCH now lets the author add revisions to a pending opening post. A topic publish from /cms/ (snippet Publish, or a clean Topic SpamCheckTask finish) runs `_publish_counterpart`(prefer_latest_revision=True), which publishes the latest post revision even when spam flagged it (NEEDS_CHANGES) or no moderator has seen it. (signals.py:299)
2. **medium** `backend/packages/wagtail_forum/wagtail_forum/models/moderation.py:82` The new `except Exception` around the spam backend also catches DB errors raised inside Wagtail's atomic workflow start(). The follow-up task_state.reject() (a DB write) then raises TransactionManagementError, losing the fail-closed record and masking the original error. | also: The new `except Exception` around the spam backend then calls task_state.reject() (a DB write). If the backend failure was a DB error inside Wagtail's atomic start(), the transaction is poisoned and the reject raises TransactionManagementError, so the fail-closed record is lost. (moderation.py:493)
3. **medium** `web/src/pages/forum/ThreadDetailPage.tsx:1181` postCount adds newReplyCount (replies the poll saw but did not load), an estimate that may include later-deleted replies; small impact since the server's too_short is handled. The `+ newReplyCount` term has no test: reverting it keeps all tests green. | also: The `+ newReplyCount` term in ThreadSummaryPanel's postCount has no test. Reverting it to `totalPosts + 1` keeps every test in the diff green (ThreadSummaryPanel tests pass postCount directly). The button would again hide on a grown thread.
4. **medium** `web/src/components/forum/ThreadSummaryPanel.tsx:222` Regression from the `!outcome` guard: after a server too_short answer, if postCount drops below MIN_POSTS both too-short lines hide (outer by `!outcome`, inner by `!tooShort`) and the button is hidden too, so the panel shows no explanation.
5. **medium** `backend/packages/wagtail_forum/wagtail_forum/signals.py:299` PATCH now lets the author add revisions to a pending opening post. A topic publish from /cms/ (snippet Publish, or a clean Topic SpamCheckTask finish) runs `_publish_counterpart`(prefer_latest_revision=True), which publishes the latest post revision even when spam flagged it (NEEDS_CHANGES) or no moderator has seen it.
6. **medium** `backend/packages/wagtail_forum/wagtail_hooks.py:277` after_edit_snippet also fires on Wagtail 8 autosave (on by default, WAGTAIL_AUTOSAVE_INTERVAL=500). Autosave POSTs with no action-* key, so each autosave of a pending opening post cancels and restarts the workflow and calls the paid LLM spam backend, which can flag half-typed drafts.
7. **medium** `backend/packages/wagtail_forum/wagtail_forum/models/moderation.py:493` The new `except Exception` around the spam backend then calls task_state.reject() (a DB write). If the backend failure was a DB error inside Wagtail's atomic start(), the transaction is poisoned and the reject raises TransactionManagementError, so the fail-closed record is lost.

20 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py:286 Wagtail 8 autosaves revision-enabled snippets by default. An autosave POST has no action-* key, so after_edit_snippet re-runs the spam workflow (cancel, new state, paid backend call) on every autosave of a pending opening post and can flag half-typed drafts. (fixed on main: The hook now returns early when not request.accepts('text/html'), with a comment that this skips Wagtail 8 JSON autosaves (mirrors expects_json_response). Only an explicit Save draft screens.; the refuter agreed: wagtail_hooks.py:288 returns early when not request.accepts('text/html'). Wagtail's autosave JS sends Accept: application/json, and expects_json_response (mixins.py:966) uses this same test. So JSON autosaves never reach the screen, and only an explicit Save draft does.)
- medium: backend/packages/wagtail_forum/wagtail_forum/signals.py:248 `.order_by().distinct()` leaves author_ids unordered, so `_refresh_profile`'s select_for_update locks run in a nondeterministic order, and the test at test_topic_approval.py:607 asserts an exact call order that Postgres does not guarantee. (refuted: In the cited test, author is excluded via exclude_author_id (linked publish), so the query yields only other.pk and the asserted order is deterministic. Lock order was never author-ordered: before .order_by() it followed Post.Meta created_at, so this is no regression and no failure is shown.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1035 (todos 554, 557, 561, 574, 579).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Items 2 and 7 (one bug), fixed: `SpamCheckTask.start` in `backend/packages/wagtail_forum/wagtail_forum/models/moderation.py` now runs the spam backend inside a `transaction.atomic()` savepoint. A DB error from the backend rolls back to the savepoint, so the fail-closed `reject()` still writes its record, and the comment names the backend's own error. Test: `test_spam_backend_db_error_still_fails_closed_with_a_record` in `tests/test_workflow_routing.py` (it fails without the savepoint, with `InternalError: current transaction is aborted`).
- Item 4, fixed: the outer too-short line in `web/src/components/forum/ThreadSummaryPanel.tsx` now hides only beside a `ready` summary, so after a server `too_short` the panel still explains the missing button when the count drops below 3. Test in `ThreadSummaryPanel.test.tsx`; it fails with the old `!outcome` guard.
- Item 3, test added: `ThreadDetailPage.test.tsx` now covers the `+ newReplyCount` term (the poll sees an unloaded reply, and the Summarize button appears before the pill is clicked); reverting it to `totalPosts + 1` fails the test. The estimate part is declined: a reply deleted after the poll can only offer a click the server answers with `too_short`, which the panel handles.
- Item 1 declined, per the owner decision (2026-10-11): "decline as the intended todo 432 behaviour; a clean unheld edit publishes".
- Items 5 and 6 were already fixed before PR #1035 merged: `signals.py` publishes the row, not the held edit, when the opening post is in NEEDS_CHANGES (`_held_for_changes`), and `wagtail_hooks.py:288` returns early on JSON autosaves (`request.accepts("text/html")`).

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `{ cd backend && python3 scripts/todos/slot_env.py --main-root . 6 -- backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_workflow_routing.py -q --create-db -p no:cacheprovider && cd web && npx vitest run src/components/forum/ThreadSummaryPanel.test.tsx src/pages/forum/ThreadDetailPage.test.tsx && grep -n -A8 'Implemented by the todo sweep (run 2026-10-11-2219)' todos/archive/588-completed-p4-forum-pending-edit-pr1035-followups.md; }` — evidence `.sweep-evidence/g6/588-ac0.txt` (not committed), last lines:

  ```text
  54-- Items 2 and 7 (one bug), fixed: `SpamCheckTask.start` in `backend/packages/wagtail_forum/wagtail_forum/models/moderation.py` now runs the spam backend inside a `transaction.atomic()` savepoint. A DB error from the backend rolls back to the savepoint, so the fail-closed `reject()` still writes its record, and the comment names the backend's own error. Test: `test_spam_backend_db_error_still_fails_closed_with_a_record` in `tests/test_workflow_routing.py` (it fails without the savepoint, with `InternalError: current transaction is aborted`).
  55-- Item 4, fixed: the outer too-short line in `web/src/components/forum/ThreadSummaryPanel.tsx` now hides only beside a `ready` summary, so after a server `too_short` the panel still explains the missing button when the count drops below 3. Test in `ThreadSummaryPanel.test.tsx`; it fails with the old `!outcome` guard.
  56-- Item 3, test added: `ThreadDetailPage.test.tsx` now covers the `+ newReplyCount` term (the poll sees an unloaded reply, and the Summarize button appears before the pill is clicked); reverting it to `totalPosts + 1` fails the test. The estimate part is declined: a reply deleted after the poll can only offer a click the server answers with `too_short`, which the panel handles.
  57-- Item 1 declined, per the owner decision (2026-10-11): "decline as the intended todo 432 behaviour; a clean unheld edit publishes".
  58-- Items 5 and 6 were already fixed before PR #1035 merged: `signals.py` publishes the row, not the held edit, when the opening post is in NEEDS_CHANGES (`_held_for_changes`), and `wagtail_hooks.py:288` returns early on JSON autosaves (`request.accepts("text/html")`).
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
