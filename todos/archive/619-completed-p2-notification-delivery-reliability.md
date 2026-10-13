---
status: completed
priority: p2
issue_id: "619"
tags: [backend, notifications, email, celery, reliability, security]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Owner: rechecks, then outbox — keep all of 619 here: first a shared send-time eligibility recheck slice, then a transactional outbox with per-recipient attempts and reconciliation (2026-10-12). Owner: ship all three parts (rechecks; outbox + migration + reconciliation; async lockout mail) in ONE PR (2026-10-12)"
---

# Revalidate and recover external notification deliveries

## Problem

Queued forum messages can outlive content visibility or recipient eligibility, and several delivery paths lose messages after broker or provider failures. Make sending recoverable per recipient without blindly resending a partially successful batch or weakening account-email abuse limits.

## Findings

Source: Devin's read-only email/notification audit and backlog comparison, 2026-10-12. These are source-confirmed paths, not production incidents or live-queue reproductions.

- `backend/apps/forum_host/tasks.py:535-594`: reply email fetches the post by ID and sends its current excerpt without rechecking publication, board visibility, or newly established blocks/mutes. The push paths at `:136-234`, `:246-371` and `:395-483` similarly lack these send-time checks. The in-app API already filters hidden topics (`backend/packages/wagtail_forum/wagtail_forum/api/notifications.py:39-65`).
- `backend/apps/core/services/email_service.py:179-225` returns False on send failure; `send_forum_email_batch` only logs that result. Its OperationalError retry intentionally protects the pre-send fetch, not SMTP failures.
- `backend/apps/blog/tasks.py:17-34` ignores `request_confirmation`'s False result; `backend/apps/blog/newsletter.py:242-277` catches mail failures. Newsletter confirmation can be lost without retry.
- `backend/apps/users/services.py:172-192` returns False on browser-push failure; the forum task does not retry a transient failed recipient.
- `backend/apps/users/email_verification.py:132-172,222-240` claims a verification-mail allowance before enqueue, catches broker failure, and has no durable recovery record. `backend/apps/users/constants.py:16-17` limits requests to five per 30 days.
- `backend/apps/core/security.py:235-237,257-316` sends lockout email inline; account-mail tasks already provide an asynchronous pattern. Weekly digest/newsletter send failures remain due, but their normal schedule is weekly, not a prompt failed-recipient retry.

## Recommended Action

1. Reproduce eligibility changes between enqueue and execution with controlled tests. Share a host-side eligibility check across forum email, mobile push and browser push, respecting package/host boundaries. Check current recipient state, content visibility, blocks/mutes, subscriptions where applicable, and preferences on retries too.
2. Design durable delivery intent and per-recipient/channel attempt state, preferably a transactional outbox with bounded retry/backoff and reconciliation after enqueue failure. Distinguish accepted, suppressed, retryable failure and terminal failure; False must not collapse opt-out and transport failure into the same retry decision.
3. Recover verification, newsletter-confirmation, forum-email and browser-push failures without replaying successful recipients. Reconcile failed weekly recipients within a bounded useful window. Move lockout SMTP off the request path while preserving security-mail policy.
4. Preserve verification abuse limits: recovery belongs to the original intent and must not consume extra request slots or enable unlimited new messages. Do not refund a slot blindly when broker acceptance is ambiguous.
5. Define behavior for worker interruption and provider-accepted-but-unacknowledged sends. Use provider idempotency where supported; otherwise document bounded at-least-once semantics rather than claiming exactly-once SMTP.

## Technical Details

Primary files are the sender/task modules cited above and `backend/apps/forum_host/notifications.py`. Reference `backend/docs/patterns/domain/celery.md` and `backend/docs/patterns/architecture/services.md` before implementation. Use isolated PostgreSQL/Redis tests and mocked SMTP/FCM/Web Push; do not test by sending to real members.

Existing work stays with its current owner: todo 606 covers the credentials-stop untried-recipient handoff; 605 covers stale digest email addresses and lock ownership; 602 covers browser-subscription renewal/security. Integrate with those fixes, do not duplicate or undo them. Archived 268 explains why whole-batch email retries are unsafe; archived 447 covers account-mail retries already shipped.

## Acceptance Criteria

- [x] Tests enqueue a forum event, then hide/unpublish/delete its content, block/mute its actor, disable its recipient or change applicable preferences; no now-ineligible external send occurs on initial execution or retry, and eligible controls still send.
- [x] Broker failure leaves a recoverable durable intent; reconciliation after recovery sends it without requiring another user request. Verification allowance tests retain the five-per-window abuse bound without charging recovery attempts as new requests.
- [x] Transient failures in verification, newsletter confirmation, forum email and browser push retry only failed eligible deliveries with bounded backoff; permanent failures, opt-outs and missing destinations do not enter endless retries.
- [x] Weekly email failure recovery is bounded and rechecks consent; empty digests remain silent and overlapping runs do not intentionally resend accepted recipients.
- [x] Partial-batch failure, duplicate enqueue, concurrent claim and worker-interruption tests pin the chosen idempotency/recovery contract; ambiguous provider acceptance and any residual duplicate window are recorded.
- [x] Lockout mail is queued without blocking login responses on SMTP, with tests for enqueue/send failures and no regression in lockout enforcement.
- [x] Relevant backend task, preference, unsubscribe, newsletter and account-security tests pass; failures are observable without logging message bodies, tokens or raw recipient addresses.

## Work Log

### 2026-10-12 - Created from read-only audit

- Grouped audit findings on send-time eligibility, broker recovery and per-recipient retries. User requested todo creation only; no application changes or production sends performed.
- Cross-checked pending 602/605/606 and archived 268/447; their existing scopes are referenced rather than recreated.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1737)

- Send-time recheck: new `backend/apps/forum_host/eligibility.py::recheck` runs in all four forum send tasks (FCM single/batch, browser push, email) on every attempt: active account, preferences, address, and for dispatched payloads (which now carry a server-only `actor_id`) post/topic/board visibility, blocks/mutes against the actor and the topic subscription.
- Outbox: new `core.DeliveryIntent` (migration `core/0007`) and `backend/apps/core/delivery.py`. `dispatch()` records one row per recipient for forum email and browser push in the bell-row savepoint; tasks claim with one conditional UPDATE after their up-front reads, record one outcome per recipient, and only transient failures (`EmailService.last_outcome`, a still-active subscription) back off; `reconcile_deliveries` (beat, 5 min) re-drives lost enqueues, due retries and expired leases, expires after 24 h and prunes after 14 days. FCM keeps its per-device retry (todos 593/606/621) and gets only the recheck.
- Account mail: the verification allowance claim and its outbox row share a transaction, so reconciliation recovers a refused enqueue without charging a slot; the task claims before sending. Newsletter confirmations retry failures with bounded backoff and record an intent (subscriber pk only) when the signup enqueue fails. Lockout mail moved to `send_lockout_email_task`, which reads the lockout details from the cache; the login request never touches SMTP.
- Weekly digest and newsletter: a run reporting `failed=N` schedules at most two recovery runs of the same command, whose claim rechecks consent and skips accepted sends.
- Delivery contract (at-least-once, one message per interrupted worker) documented in `backend/apps/core/delivery.py` and `backend/docs/patterns/domain/celery.md`. SMTP failure logs now carry the exception type, not its text, which quoted the recipient address.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1737)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -q apps/forum_host/tests/test_send_time_eligibility.py` — evidence `.sweep-evidence/g1/619-ac0.txt` (not committed), last lines:

  ```text
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 14 passed, 2 warnings in 19.82s ========================

  exit=0
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -q apps/forum_host/tests/test_delivery_outbox.py -k 'writes_one_row or lost_enqueue or rolled_back' && cd . && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -q apps/users/tests/test_mail_recovery.py::VerificationRecoveryTest apps/blog/tests/test_newsletter_recovery.py::SignupBrokerFailureTest apps/users/tests/test_email_verification_hardening.py::VerificationCapTest apps/users/tests/test_email_verification_hardening.py::MailIsQueuedTest` — evidence `.sweep-evidence/g1/619-ac1.txt` (not committed), last lines:

  ```text
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 14 passed, 3 warnings in 20.66s ========================

  exit=0
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -q apps/forum_host/tests/test_delivery_outbox.py -k 'partial or back_off or permanent or opt_out or browser_push' && cd . && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -q apps/users/tests/test_mail_recovery.py::VerificationRecoveryTest apps/blog/tests/test_newsletter_recovery.py::ConfirmationRetryTest` — evidence `.sweep-evidence/g1/619-ac2.txt` (not committed), last lines:

  ```text
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 9 passed, 3 warnings in 19.16s ========================

  exit=0
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -q apps/forum_host/tests/test_delivery_outbox.py -k 'weekly or digest_recovery' && cd . && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -q packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_nothing_new_means_no_email_and_no_marker_write packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_an_overlapping_run_exits_on_the_lock_but_a_dry_run_ignores_it packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_the_claim_skips_a_member_who_left_after_the_chunk_was_read && cd . && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -q apps/blog/tests/test_newsletter_digest.py -k 'empty_week or second_run or overlapping_run or failed_send_gives'` — evidence `.sweep-evidence/g1/619-ac3.txt` (not committed), last lines:

  ```text
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 4 passed, 37 deselected, 3 warnings in 20.66s =================

  exit=0
  ```

- AC 5: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -q apps/forum_host/tests/test_delivery_outbox.py -k 'partial or duplicate or two_workers or interrupted or lost_outcome' && grep -n -A12 'At-least-once, not exactly-once' apps/core/delivery.py && grep -n 'At-least-once' docs/patterns/domain/celery.md` — evidence `.sweep-evidence/g1/619-ac4.txt` (not committed), last lines:

  ```text
  52-once.
  53-"""
  172:- **At-least-once.** No provider idempotency key is available, so a worker

  exit=0
  ```

- AC 6: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -q apps/users/tests/test_mail_recovery.py::LockoutMailIsQueuedTest apps/users/tests/test_account_lockout.py apps/core/tests/test_mail_call_sites_deprecation_gate.py` — evidence `.sweep-evidence/g1/619-ac5.txt` (not committed), last lines:

  ```text
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 36 passed, 3 warnings in 25.16s ========================

  exit=0
  ```

- AC 7: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -q apps/forum_host apps/users apps/blog apps/core apps/garden_calendar packages/wagtail_forum/wagtail_forum/tests/test_digest.py packages/wagtail_forum/wagtail_forum/tests/test_notifications.py` — evidence `.sweep-evidence/g1/619-ac6.txt` (not committed), last lines:

  ```text
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  =========== 3785 passed, 8 skipped, 5 warnings in 309.39s (0:05:09) ============

  exit=0
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1737)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

P2 for privacy-sensitive stale sends and lost account/engagement messages. This is one backend reliability initiative; use incremental implementation slices rather than changing all senders in one unverified diff. Care reminders remain FCM-only with the owner-approved 24-hour lookback (archived 410). Measurement and provider feedback are tracked separately in todo 623; that prose reference is not an execution dependency.
