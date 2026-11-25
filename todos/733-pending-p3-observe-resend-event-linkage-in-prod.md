---
status: pending
priority: p3
issue_id: "733"
tags: [notifications, email, observability, backend]
dependencies: ["726"]
---

# Observe Resend event linkage in production

## Problem

Todo 726 shipped step 1: each Resend webhook event now stores its
`data.message_id` (`EmailProviderEvent.message_id`, migration 0010). Whether
that is enough to link a forum email's events to its `EmailNotification` can
only be seen in production, with a real forum email and an owner-approved
read-only prod read. These two checks moved here from 726 on 2026-11-22 so
step 1 could merge (owner decision 2026-11-22).

## Carried over from todo 726

Todo 726 is archived with step 1 only. Its remaining steps live here:

- Read what form the stored `message_id` takes and fix the matching in
  `apps/core/email_feedback.py` to it. If Resend returns nothing usable, fall
  back to 726's Option 2 (send tracked mail through Resend's API).
- Check whether Resend ever sends `email.suppressed`; prod has recorded only
  `suppression.added`, which the code stores and ignores.
- A stored `redacted:recipient` means the id quoted a recipient address and
  was dropped; blank means Resend sent none.

## Acceptance Criteria

- [ ] A forum email's Resend events link to its `EmailNotification` and set its
  `delivered_at` / `bounced_at` (observed in production, dated)
- [ ] A baseline re-read records `delivered_at − sent_at` p50/p90 over a stated
  window in `docs/operations/notification-baseline.md`

## Work Log

### 2026-11-22 - Filed

- Re-pointed from todo 726 (sweep run 2026-11-22-1957) on the owner's decision of
  2026-11-22: "Yes, re-point to 733". After 726 deploys, send one forum email, then
  read the stored `message_id` shape and the event-to-notification links in prod.
