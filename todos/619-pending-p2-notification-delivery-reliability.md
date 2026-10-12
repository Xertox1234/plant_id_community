---
status: pending
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

- [ ] Tests enqueue a forum event, then hide/unpublish/delete its content, block/mute its actor, disable its recipient or change applicable preferences; no now-ineligible external send occurs on initial execution or retry, and eligible controls still send.
- [ ] Broker failure leaves a recoverable durable intent; reconciliation after recovery sends it without requiring another user request. Verification allowance tests retain the five-per-window abuse bound without charging recovery attempts as new requests.
- [ ] Transient failures in verification, newsletter confirmation, forum email and browser push retry only failed eligible deliveries with bounded backoff; permanent failures, opt-outs and missing destinations do not enter endless retries.
- [ ] Weekly email failure recovery is bounded and rechecks consent; empty digests remain silent and overlapping runs do not intentionally resend accepted recipients.
- [ ] Partial-batch failure, duplicate enqueue, concurrent claim and worker-interruption tests pin the chosen idempotency/recovery contract; ambiguous provider acceptance and any residual duplicate window are recorded.
- [ ] Lockout mail is queued without blocking login responses on SMTP, with tests for enqueue/send failures and no regression in lockout enforcement.
- [ ] Relevant backend task, preference, unsubscribe, newsletter and account-security tests pass; failures are observable without logging message bodies, tokens or raw recipient addresses.

## Work Log

### 2026-10-12 - Created from read-only audit

- Grouped audit findings on send-time eligibility, broker recovery and per-recipient retries. User requested todo creation only; no application changes or production sends performed.
- Cross-checked pending 602/605/606 and archived 268/447; their existing scopes are referenced rather than recreated.

## Notes

P2 for privacy-sensitive stale sends and lost account/engagement messages. This is one backend reliability initiative; use incremental implementation slices rather than changing all senders in one unverified diff. Care reminders remain FCM-only with the owner-approved 24-hour lookback (archived 410). Measurement and provider feedback are tracked separately in todo 623; that prose reference is not an execution dependency.
