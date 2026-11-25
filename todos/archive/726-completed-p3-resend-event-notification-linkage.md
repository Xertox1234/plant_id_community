---
status: completed
priority: p3
issue_id: "726"
tags: [notifications, email, observability, backend]
dependencies: []
triage: ready
triaged: 2026-11-22
owner_decision: "Ship step 1 now (EmailProviderEvent.message_id migration + store data.message_id); the prod-read criterion stays open (owner 2026-11-22)"
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
  rows over 4 emails, none linked to an `EmailNotification`. The one
  forum email in the window (forum_reply, 2026-11-04) carries our Message-ID
  and no provider email id; its `email.delivered` event arrived within 10
  minutes of the send but did not link. That is the only evidence (n = 1):
  `email.sent` and `suppression.added` are not in `HANDLED_EVENTS`, so
  `ingest()` ignores them before any matching, and the other 3 emails have no
  `EmailNotification` row. Also check whether Resend sends `email.suppressed`
  at all: prod recorded `suppression.added`, which the code does not act on.
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

- [ ] A forum email's Resend events link to its `EmailNotification` and set its → todo 733 (re-pointed 2026-11-22)
  `delivered_at` / `bounced_at` (observed in production, dated)
- [ ] A baseline re-read records `delivered_at − sent_at` p50/p90 over a stated → todo 733 (re-pointed 2026-11-22)
  window in `docs/operations/notification-baseline.md`

## Work Log

### 2026-11-21 - Filed from todo 692

- Created by the todo sweep (run 2026-11-20-2202) from the owner-confirmed
  linkage gap in todo 692's 2026-11-21 prod read.

### 2026-11-22 - Implemented by the todo sweep (run 2026-11-22-1957)

- Step 1 of the Recommended Action (owner decision 2026-11-22): new
  `EmailProviderEvent.message_id` (migration
  `backend/apps/core/migrations/0010_emailproviderevent_message_id.py`,
  `db_default=""` for a rolling deploy) stores each event's `data.message_id`
  as reported, on every recorded event, `email.sent` included.
- A reported id that quotes a recipient address is stored blank
  (`_storable_message_id` in `backend/apps/core/email_feedback.py`), so the
  ledger still holds no address. Matching is unchanged.
- Tests in `backend/apps/core/tests/test_email_feedback.py`; the baseline's
  "Stored data" bullet and the linkage hypothesis in
  `docs/operations/notification-baseline.md` now say the id is stored.
- Both acceptance criteria stay open: they need a real forum email and an
  owner-approved prod read (steps 2 and 3).

### 2026-11-23 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; review is on the PR.

### 2026-11-23 - Review round 1: non-blocking findings

- **Fixed: the baseline doc still pointed at 726 for open work (medium).** Five places in
  `docs/operations/notification-baseline.md` now point at todo 733, and 733 gained a "Carried
  over from todo 726" section with the fix-matching step and the `email.suppressed` check.
- **Fixed: blank meant both "Resend sent none" and "dropped" (low, two reviewers).** A dropped
  id is stored as `redacted:recipient` (`MESSAGE_ID_REDACTED`). Test updated.
- **Fixed: a recipient `parseaddr` cannot read was skipped (low).** The check falls back to the
  raw string, as `address_hash` does. New test; removing the fallback fails it.
- **Fixed: a NUL in the id would fail the insert and 500 the webhook (low).** NUL is removed.
  New test; removing the strip fails it.
- **Fixed: no nearest-neighbour test (low).** A new test keeps an id that names another
  address; a filter that blanks every id fails it.
- **Declined, wording changed: encoded, cc/bcc and cut-off addresses are not recognised (low,
  three phrasings).** The guard checks the verbatim recipient only. The docstring, the model
  comment and the baseline now say "verbatim" instead of "no address is ever stored" for this
  field. The webhook is signed, and Resend's ids have not been seen to carry an address.
- **Declined: our Message-ID carries the notification's uuid and outlives a deleted
  notification (low).** It is pseudonymous, nothing else keeps the uuid, and the event row is
  deleted after `EMAIL_FEEDBACK_RETENTION_DAYS`.

### 2026-11-23 - Review round 2: non-blocking findings

- **Fixed: a lone surrogate or a NUL in `data.message_id` made the webhook answer 500 (low; one
  reviewer marked it a regression for `email.sent`).** Round 1's NUL strip covered only the stored
  value, not the lookup on handled events, and not characters UTF-8 cannot encode. The id is now
  cleaned once in `parse_event` (`_db_safe`), so the lookup and the insert both get it. One
  parametrized test covers NUL and a lone surrogate on `email.sent` and `email.delivered`;
  without the cleaning all four cases fail. `data.email_id` has the same gap on main and is
  left as it is.
- **Declined: an address that straddles the 255-character cut is not matched (low).** Reachable
  only if Resend sends a very long id; the guard is documented as verbatim-only.
- **No change: the flagged test edits (low).** The reviewer confirmed no existing test was
  weakened: 60 lines added against main, none removed.
