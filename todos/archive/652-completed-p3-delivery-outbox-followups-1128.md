---
status: completed
priority: p3
issue_id: "652"
tags: [notifications, delivery, outbox, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-16
owner_decision: "Fix both lows: SMTP 554 at RCPT/DATA classification and the web-push re-accept dedup (F4), with tests (2026-10-16)"
---

# Follow-ups from PR #1128 (todo 619, notification delivery outbox)

## Problem

Todo-sweep run 2026-10-12-1737 merged PR #1128 (todo 619: send-time rechecks, the `core.DeliveryIntent` outbox and
async lockout mail). The non-blocking review findings are below. The curator merged duplicates and checked each
item against main, and the refuter tried to refute what was left; the items that survived are listed. The two
medium findings the owner asked to fix before merge (SMTP session faults treated as permanent, and a duplicate
lockout mail on a late retry) were fixed in the PR and dropped here. Filed at p3 because three mediums affect
whether mail is retried or dropped.

## Findings

PR #1128 (todo sweep run 2026-10-12-1737, group g1, todos 619); follow-ups: verified.

1. **medium** `backend/apps/forum_host/tasks.py:930` A False send with last_outcome still None defaults to TRANSIENT, so mark_retry runs, though send_notification can return False without reaching send_email (preference gate, missing copy). Contradicts the comment that a non-transport False is never retried.
2. **medium** `backend/apps/users/tasks.py:85` send_verification_email_task claims its row before reading the account; an OperationalError autoretry after claim_one finds the row still claimed (15-min lease), claim_one returns None, has_any is True, and the mail is dropped as a duplicate until reconciliation re-drives it. | also: send_verification_email_task claims its row before reading the account (is_email_verified, verification_url). An OperationalError after the claim autoretries, the retry finds the row still claimed, and has_any() drops it as a duplicate. The mail then waits for the 15-min lease plus reconcile.
3. **medium** `backend/apps/users/tasks.py:143` send_lockout_email_task treats SecurityMonitor.`_send_lockout_notification`'s None (nobody to send to) as a failed send, burning retries and ending in mark_failed 'send_failed' instead of a suppressed outcome.
4. **low** `backend/apps/forum_host/notifications.py:487` The outbox unique constraint (kind, event, subject_key=post, recipient) with ignore_conflicts swallows the browser push when an answer is unaccepted and accepted again, while FCM push still goes out, so the channels disagree.
5. **low** `backend/apps/forum_host/tasks.py:670` Any failed web push on a still-active subscription counts as transient (VAPID unset, pywebpush missing, 400/403/413 WebPushException), so such rows retry up to DELIVERY_MAX_ATTEMPTS with backoff though no retry can succeed. | also: Any False from send_web_push_notification where the subscription is still active is classified as transient. That includes a missing VAPID key, pywebpush not installed, and permanent 400/403/413 errors. Each recipient is retried up to DELIVERY_MAX_ATTEMPTS times through reconcile and logs an error each time.

27 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: backend/apps/core/services/email_service.py:124 classify_send_error marks any smtp_code>=500 PERMANENT, including server-wide faults (SMTPAuthenticationError 535, SMTPSenderRefused, 5xx quota/relay errors), so an SMTP credential or quota outage terminally fails every forum email row in the batch. (fixed on main: On origin/main classify_send_error returns PERMANENT only for SMTPRecipientsRefused with all codes >=500 or SMTPDataError >=500; everything else (auth 535, sender refused, HELO) is TRANSIENT, per its docstring.; the refuter agreed: On main classify_send_error returns PERMANENT only for SMTPRecipientsRefused with every code >=500 or SMTPDataError >=500. SMTPAuthenticationError, SMTPSenderRefused, HELO and every other error return TRANSIENT, so a credential or quota outage no longer fails rows for good.)
- medium: backend/apps/core/services/email_service.py:124 classify_send_error marks any exception with smtp_code>=500 as PERMANENT. That includes SMTPAuthenticationError (535) and SMTPSenderRefused (5xx), which are relay credential or config faults, not recipient faults. During a credential outage every forum email row gets mark_failed and is lost for good. (refuted: On main classify_send_error returns PERMANENT only for SMTPRecipientsRefused with every code >=500 or SMTPDataError >=500. SMTPAuthenticationError, SMTPSenderRefused, HELO and every other error return TRANSIENT, so a credential or quota outage no longer fails rows for good.)
- medium: backend/apps/users/tasks.py:143 send_lockout_email_task treats `_send_lockout_notification`'s None (user vanished or has no email) as a failure and retries; on a retry it never calls mark_retry, so the claimed row stays leased and reconciliation can re-drive it after the lease while the Celery retry is pending (duplicate mail). | also: send_lockout_email_task claims its intent only when retries==0 and leaves it CLAIMED during Celery retries. If a retry runs late, past the 15-min lease (e.g. queue backed up behind a 30-min digest), reconcile re-drives the row and both tasks send: duplicate lockout mail. (refuted: Still true: `_send_lockout_notification` returns None when the user is gone or has no email (a race after the task's own check) and the task sends that to mark_retry/mark_failed 'send_failed'. Both 'also' phrasings are fixed: claim_one(intent_id) runs on every attempt and mark_retry runs before each retry, so the row is never left CLAIMED.)
- medium: backend/apps/users/management/commands/expire_unverified_accounts.py:75 The new NOT_USER_DATA exemption for core.DeliveryIntent has no test; deleting it would stop every account with a verification outbox row from expiring and nothing in the suite would fail. (refuted: test_a_real_registration_left_alone_for_eight_days_is_deleted posts to /register/, and send_verification_email calls record_one, which writes a DeliveryIntent. That relation (related_name '+') shows up through get_fields(include_hidden=True), so without the exemption _extra_data keeps the account and the test's deleted=1 assertion fails.)

Added from the focused review of the owner-requested repair (398df114) on PR #1128:

- **low** `backend/apps/core/services/email_service.py:123` A credential or quota outage can still fail rows for good when the relay answers at RCPT or DATA rather than at AUTH. For example, blank credentials skip login and RCPT gets `554 5.7.1 relay denied`, or a paused SES account returns `554` at DATA. Both are classed PERMANENT.
- **low** `backend/apps/users/tests/test_mail_recovery.py` No test covers `send_lockout_email_task` with `intent_id=None` (a direct enqueue, no outbox row) on a failed send followed by a retry.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1128 review (todo sweep run 2026-10-12-1737)

Filed by the closing step of the run from `state.py followups-md g1`, plus two lows from the repair review.

### 2026-10-16 - Implemented by the todo sweep (run 2026-10-16-1135)

- Finding 1 fixed: `send_forum_reply_notification` / `send_forum_event_notification` set `EmailOutcome.PERMANENT` when there is no copy, so `send_forum_email_batch` fails that row instead of retrying it. An outcome still unset now only means an error escaped `send_email` before the send, which is still retried. Test: `test_a_send_with_no_email_copy_is_failed_not_retried`.
- Findings 2 and 3 fixed in `backend/apps/users/tasks.py`. The verification task does its reads before the claim, and hands its row back (`delivery.release`) when an OperationalError comes before the send, so the autoretry can claim it again. The lockout task records a `None` from `_send_lockout_notification` as suppressed `no_destination`, not a failed send. The `intent_id=None` test gap (the second repair-review low) is covered by `test_a_direct_enqueue_retries_a_failed_send_without_an_outbox_row`.
- SMTP 554 low fixed (owner decision): `classify_send_error` now looks at the RFC 3463 enhanced code. Only 5.1/5.2/5.3/5.6 (recipient, mailbox, destination system, content) are PERMANENT; 5.7.x, and a 554 with no enhanced code, are TRANSIENT. The old `SMTPDataError(554, b"message rejected")` PERMANENT row in `apps/core/tests/test_classify_send_error.py` moved to TRANSIENT on purpose, because it is the paused-account case.
- F4 fixed (owner decision), by sending again on every channel rather than silencing FCM. PR #1132's `test_a_re_accepted_answer_is_not_dropped_by_quiet_hours` pins that a re-accept pushes FCM again. So when a re-accept finds the first acceptance's web-push or email row already finished (`delivery.finished`), it runs without an outbox batch. A row still pending or claimed (the same acceptance in flight) still dedups. Tests are in `apps/forum_host/tests/test_solution_notifications.py`.
- Finding 5 declined: the VAPID-unset case is already finished up front as `channel_off` (`web_push_enabled()`), and pywebpush is a pinned requirement. For a 400/403/413, the shared `send_web_push_notification` would have to report a status, which is beyond this todo. Those retries stop at `DELIVERY_MAX_ATTEMPTS`.

### 2026-10-16 - Verified by the todo sweep (run 2026-10-16-1135)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest apps/core/tests/test_classify_send_error.py apps/forum_host/tests/test_delivery_outbox.py apps/forum_host/tests/test_solution_notifications.py apps/forum_host/tests/test_quiet_hours_and_coalescing.py apps/users/tests/test_mail_recovery.py --create-db -p no:cacheprovider -v; grep -n 'fixed\|declined' ../todos/archive/652-completed-p3-delivery-outbox-followups-1128.md` — evidence `.sweep-evidence/g6/652-ac0.txt` (not committed), last lines:

  ```text
  60:- Finding 1 fixed: `send_forum_reply_notification` / `send_forum_event_notification` set `EmailOutcome.PERMANENT` when there is no copy, so `send_forum_email_batch` fails that row instead of retrying it. An outcome still unset now only means an error escaped `send_email` before the send, which is still retried. Test: `test_a_send_with_no_email_copy_is_failed_not_retried`.
  61:- Findings 2 and 3 fixed in `backend/apps/users/tasks.py`. The verification task does its reads before the claim, and hands its row back (`delivery.release`) when an OperationalError comes before the send, so the autoretry can claim it again. The lockout task records a `None` from `_send_lockout_notification` as suppressed `no_destination`, not a failed send. The `intent_id=None` test gap (the second repair-review low) is covered by `test_a_direct_enqueue_retries_a_failed_send_without_an_outbox_row`.
  62:- SMTP 554 low fixed (owner decision): `classify_send_error` now looks at the RFC 3463 enhanced code. Only 5.1/5.2/5.3/5.6 (recipient, mailbox, destination system, content) are PERMANENT; 5.7.x, and a 554 with no enhanced code, are TRANSIENT. The old `SMTPDataError(554, b"message rejected")` PERMANENT row in `apps/core/tests/test_classify_send_error.py` moved to TRANSIENT on purpose, because it is the paused-account case.
  63:- F4 fixed (owner decision), by sending again on every channel rather than silencing FCM. PR #1132's `test_a_re_accepted_answer_is_not_dropped_by_quiet_hours` pins that a re-accept pushes FCM again. So when a re-accept finds the first acceptance's web-push or email row already finished (`delivery.finished`), it runs without an outbox batch. A row still pending or claimed (the same acceptance in flight) still dedups. Tests are in `apps/forum_host/tests/test_solution_notifications.py`.
  64:- Finding 5 declined: the VAPID-unset case is already finished up front as `channel_off` (`web_push_enabled()`), and pywebpush is a pinned requirement. For a 400/403/413, the shared `send_web_push_notification` would have to report a status, which is beyond this todo. Those retries stop at `DELIVERY_MAX_ATTEMPTS`.
  ```

### 2026-10-16 - Completed by the todo sweep (run 2026-10-16-1135)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-16 - Review round 1: non-blocking findings (run 2026-10-16-1135)

- Fixed, medium x2 + low x2 (F4 re-accept, `backend/apps/forum_host/notifications.py`): the worker's re-accept
  sent the browser push and email with no outbox batch. That skipped pacing, quiet hours and retry, and with
  no cap, toggling accept and clear could email the answerer without limit. The finished-check-then-insert
  was also racy. Owner decision 2026-10-16: reopen with a 24 h cooldown. `delivery.record_reaccept`
  (`backend/apps/core/delivery.py`) locks the finished row and reopens it as pending under a new batch, so
  the normal paced and retried path runs. Inside `FORUM_REACCEPT_COOLDOWN_SECONDS` (24 h) it returns
  `REACCEPT_COOLING`, and that channel is not enqueued. The phone push is unchanged. The rewritten
  `test_accepting_a_cleared_answer_again_notifies_on_every_channel` covers quiet inside the cooldown,
  reopened under the batch past it, and a second toggle quiet again. It fails with the cooldown check
  disabled, and with the reopen disabled.
- Fixed, low x2 (`backend/apps/users/tasks.py` lockout): the lockout task claimed its row before its reads,
  so an OperationalError autoretried into its own claim (the finding-2 class). The reads now come first,
  and a send-time OperationalError releases the row. The new lockout test fails on origin/main's task and
  passes now.
- Fixed, low (no test for the verification reorder): the new `test_a_database_error_before_the_claim_does_not_drop_the_mail`
  (verification) fails on origin/main's task and passes now.
- Declined, low (verification outcome writes after the claim): an OperationalError in `mark_*` means the
  database is down. The row stays claimed and reconciliation re-drives it after the lease, which is the
  documented at-least-once window.
- Declined, low x2 (bare 5xx relay wording such as `550 relay not permitted`; 5.4.1/5.5.x): without an
  enhanced code, a 5xx at RCPT is ambiguous. The owner decision covered only the 554 paused-account case,
  so a recipient fault stays the default rather than guessing from wording.
- Declined, low (the re-accept test does not show delivery): the rewritten test runs both batch tasks
  against the reopened rows. The delivery itself is covered by the outbox suites.
- Declined, low (split the re-accept test): its steps are one flow, and every assertion names its step.
- No change, low x2 (justified edit of a 554 case): it is the owner-directed reclassification.

### 2026-10-16 - Review round 2 and owner-approved round 3 repair (run 2026-10-16-1135)

- Owner approved one round 3 (2026-10-16) after round 2 blocked on a high.
- Fixed, high + medium x2 + low x2 (`backend/apps/core/delivery.py` `record_reaccept`): a reopened row kept
  its old `created_at`. Because of the 24 h cooldown that was always past `DELIVERY_MAX_AGE_SECONDS`, so
  reconciliation expired the row as FAILED instead of re-driving it after a lost enqueue, retry or hold.
  The reopen now resets `created_at`. The cooldown is measured from `created_at` too (the last record or
  reopen), so a bulk outcome update that skips `auto_now` (the low about `mark_retry`/`reconcile` not
  bumping `updated_at`) no longer affects it. The integration test now ages both timestamps, loses the
  enqueue and runs `reconcile()`, asserting both rows are re-driven and none expired. The new
  `apps/core/tests/test_delivery_reaccept.py` covers the first record, in-flight dedup (pending and
  claimed), the cooldown, the reopen, and re-drive rather than expiry. Three tests fail with the reset
  removed and pass now.
- Fixed, low (`backend/apps/users/tasks.py`): the round-1 `except OperationalError` around
  `_send_lockout_notification` was dead, since that method catches every error and returns False. It is
  removed, and a comment says the DB fault is retried through `mark_retry`.
- Fixed, low (`record_reaccept` type hints): the parameters are annotated.
- Fixed, low (`test_a_duplicate_acceptance_signal_still_records_one_batch` was vacuous): it now asserts that
  both dispatches enqueue (in-flight dedup), which a cooldown hit would not do.
- Declined, low x2 (5.4.x at RCPT; bare `550 relay denied`): as in round 1, without an enhanced code the
  owner decision covers only 554, and recipient fault stays the default.
- Broad run of apps/core, users and forum_host: 3327 passed and 1 failed (`test_r2_storage` sqlite warning,
  the known local-env failure, unrelated).
