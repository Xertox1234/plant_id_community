---
status: pending
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

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1128 review (todo sweep run 2026-10-12-1737)

Filed by the closing step of the run from `state.py followups-md g1`, plus two lows from the repair review.
