---
status: pending
priority: p3
issue_id: "726"
tags: [notifications, email, observability, backend]
dependencies: []
---

# Link Resend webhook events to their EmailNotification

## Problem

The Resend webhook records signed events in production, but none of them links
to the `EmailNotification` it reports on. So no forum email ever gets a
delivered, bounced or complained status, `delivered_at` is never set, and the
notification baseline cannot report `delivered_at − sent_at`. Address-level
suppression is not affected. Re-homed from todo 692 on 2026-11-21.

## Findings

- Prod read 2026-11-21 (owner-approved, read-only, counts only; todo 692 Work
  Log): window 2026-11-03T20:52:57Z → 2026-11-22T01:57Z, 9 `EmailProviderEvent`
  rows over 4 emails, **0 of 9 linked** to an `EmailNotification`. The one
  forum email in the window (forum_reply, 2026-11-04) carries our Message-ID
  and no provider email id; its `email.sent` and `email.delivered` events
  arrived within 10 minutes of the send but neither linked.
- Matching (`backend/apps/core/email_feedback.py`, the lookup around
  `normalize_message_id`) tries `data.message_id` against
  `EmailNotification.message_id`, then `data.email_id` against
  `provider_email_id`. The row never gets a `provider_email_id`, because that is
  only stored from a first message-id match.
- The Message-ID is set by `EmailService._message_id`
  (`backend/apps/core/services/email_service.py`) as `<hpmd.{uuid}@{sender domain}>`
  and sent as a header over SMTP (`smtp.resend.com:587`).
- Hypothesis, not verified: Resend over SMTP does not echo a client-set
  Message-ID in `data.message_id` (or rewrites it). The event's
  `data.message_id` is not stored, so what Resend returned is unknown.

## Proposed Solutions

### Option 1: Find out what Resend returns, then match on it

- **Implementation:** store the event's `data.message_id` (it carries no
  address) on `EmailProviderEvent`, read the next forum email's events, and fix
  the matcher to the form Resend actually sends.
- **Pros:** small change; keeps SMTP.
- **Cons:** needs one more real forum email and a prod read before the fix.
- **Effort:** hours.
- **Risk:** low.

### Option 2: Send tracked mail through Resend's API

- **Implementation:** send `EmailService.send_email` mail with Resend's HTTP
  API and store the returned email id as `provider_email_id` at send time.
- **Pros:** correlation no longer depends on a header surviving SMTP.
- **Cons:** a second transport, a new dependency or client, and its own
  failure handling.
- **Effort:** a day.
- **Risk:** medium (changes the send path).

## Recommended Action

1. Do Option 1's diagnosis first: record `data.message_id` on each event.
2. After the next forum email, read (owner-approved, counts and shape only, no
   addresses) what form the stored `message_id` takes, and fix matching to it;
   fall back to Option 2 if Resend returns nothing usable.
3. Re-read the baseline and add `delivered_at − sent_at` p50/p90 to
   `docs/operations/notification-baseline.md`.

## Technical Details

- `backend/apps/core/email_feedback.py`, `backend/apps/core/models.py`
  (`EmailProviderEvent`), `backend/apps/core/services/email_service.py`.
- Tests: `backend/apps/core/tests/test_email_feedback.py`.
- Baseline: `docs/operations/notification-baseline.md` → "Delivery outcomes
  (2026-11-21)".

## Acceptance Criteria

- [ ] A forum email's Resend events link to its `EmailNotification` and set its
  `delivered_at` / `bounced_at` (observed in production, dated)
- [ ] A baseline re-read records `delivered_at − sent_at` p50/p90 over a stated
  window in `docs/operations/notification-baseline.md`

## Work Log

### 2026-11-21 - Filed from todo 692

- Created by the todo sweep (run 2026-11-20-2202) from the owner-confirmed
  linkage gap in todo 692's 2026-11-21 prod read.
