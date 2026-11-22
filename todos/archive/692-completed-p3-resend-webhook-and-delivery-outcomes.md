---
status: completed
priority: p3
issue_id: "692"
tags: [notifications, email, observability, operations, owner, prod]
dependencies: []
source_review: "todos/archive/638-completed-p3-notification-delivery-baseline.md"
source_finding: "AC2"
triage: blocked-prod
triaged: 2026-11-20
blocked_on: "Owner approval for read-only, counts-only prod DB queries: one on EmailProviderEvent linkage, one 14+ days after 2026-11-03 for counts and latency"
owner_decision: "Owner approved read-only, counts-only prod queries (no addresses) for EmailProviderEvent linkage, outcome counts and p50/p90 latency since 2026-11-03; run them in the remote session (2026-11-20)"
---

# Connect the Resend webhook and add delivery outcomes to the baseline

## Problem

Todo 625 shipped the Resend webhook endpoint
(`POST /api/v1/email/webhooks/resend/`), but it was never connected: the
2026-11-03 prod read for todo 638 found `RESEND_WEBHOOK_SECRET` **unset** and 0
`EmailProviderEvent` rows in 30 days. Until it is connected, production records
that Resend *accepted* each email and nothing after: no delivered, bounced or
complained status, no address suppression from bounces, and no send→delivered
latency. The initial baseline
(`docs/operations/notification-baseline.md` → "Initial baseline (2026-11-03)")
records those as not collected. Re-pointed from todo 638 on 2026-11-03.

## Recommended Action

1. Owner, Resend dashboard: create a webhook for `email.delivered`,
   `email.bounced`, `email.complained` and `email.suppressed` pointed at
   `https://api.houseplant-md.com/api/v1/email/webhooks/resend/`.
2. Owner: set its signing secret (`whsec_…`) as `RESEND_WEBHOOK_SECRET` on the
   `plant_id_community` Railway service, and declare it `preserve()` in
   `.railway/railway.ts` (an undeclared variable makes `railway apply` plan a
   deletion).
3. Owner, Resend dashboard: turn off Resend's own open and click tracking for
   `houseplant-md.com` (owner decision 2026-10-12: first-party clicks only).
4. After the first forum email following the change, confirm an
   `EmailProviderEvent` row links to its `EmailNotification` (`notification`
   set), which proves Resend keeps our client-set Message-ID over SMTP.
5. After a stated window (e.g. 14 days), re-run the aggregate counts behind the
   baseline table (read-only, owner-approved, counts only) and add delivered/bounced/complained counts and sent→delivered latency
   (p50/p90 of `delivered_at - sent_at`) to the baseline.

## Acceptance Criteria

- [x] `RESEND_WEBHOOK_SECRET` is set on Railway and declared in `.railway/railway.ts`; the webhook receives a signed event and records an `EmailProviderEvent`
- [x] Resend's own open/click tracking is off for `houseplant-md.com` (completed 2026-11-03: never set up; no tracking subdomain exists)
- [x] A provider event is linked to its `EmailNotification` via our Message-ID (or the gap is recorded if Resend rewrites it)
- [ ] The baseline doc records delivered/bounced/complained counts and sent→delivered latency over a stated window (re-pointed from todo 638)

## Work Log

### 2026-11-03 - Filed from todo 638

Prod read (owner-approved, aggregate-only): 9 forum emails sent in 30 days, all
with our Message-ID, none with a provider email id, 0 provider events.

### 2026-11-03 - Webhook connected; sender-domain filter

- Owner created the Resend webhook (All Events; the dashboard's event picker
  would not narrow) and set `RESEND_WEBHOOK_SECRET` on `plant_id_community`
  (piped from the clipboard). From 20:52:57 UTC an unsigned POST answers 401,
  not 503. `railway.ts` declaration: PR #1259.
- Resend's own tracking: the domain has no tracking subdomain, so Resend open
  and click tracking was never set up. Nothing to turn off (owner's Domains
  screenshot, 2026-11-03).
- The Resend account also sends for ocrecipes.com and lumatuner.com, and its
  webhooks are account-wide. Without a filter another product's complaint
  would have suppressed the address here. Fixed: events are acted on only for
  mail from `DEFAULT_FROM_EMAIL`'s domain; others are ignored and not recorded.

### 2026-11-21 - Prod read: delivery outcomes and linkage

Owner-approved read-only, counts-only read over `railway ssh … manage.py shell`
(run by Claude in the remote session; no addresses, subjects or ids printed).
Window **2026-11-03T20:52:57Z → 2026-11-22T01:57Z**, from the moment the
webhook was connected.

- 9 `EmailProviderEvent` rows over 4 emails: 4 `email.sent`, 3
  `email.delivered`, 1 `email.bounced` (Permanent), 1 `suppression.added`;
  0 complaints. 1 suppressed address. 8 of 9 events carry Resend's email id.
- 1 forum `EmailNotification` in the window (forum_reply, 2026-11-04), with our
  Message-ID and no provider email id. Its `email.sent` and `email.delivered`
  events arrived within 10 minutes of the send, but **0 of 9 events link to an
  `EmailNotification`**. Hypothesis, not verified (the event's `data.message_id`
  is not stored): Resend over SMTP does not echo our client-set Message-ID.
  The correlation fix moves to todo 726.
- Sent→delivered latency, Resend side, pairing `email.sent` and
  `email.delivered` by Resend's email id: 0.8 s, 0.9 s, 1.1 s (n = 3; p50
  0.9 s, p90 ≈ 1.1 s). `delivered_at − sent_at` on `EmailNotification` cannot
  be computed: no row is ever linked, so `delivered_at` is never set.

For the worker: write these figures into `docs/operations/notification-baseline.md`
as a new section after "Initial baseline (2026-11-03)", update its "Delivery
latency" bullet, and create `todos/726-pending-p3-resend-event-notification-linkage.md`
(correlate Resend events to `EmailNotification`, e.g. send via Resend's API to
capture its email id, or store the event's `data.message_id` to see what Resend
returns; ACs: a forum email's events set its row's `delivered_at`/`bounced_at`,
and a baseline re-read records `delivered_at − sent_at` p50/p90). Criteria 1
and 3 of this todo (0-based 0 and 2) are owner-confirmed.

### 2026-11-21 - Implemented by the todo sweep (run 2026-11-20-2202)

- `docs/operations/notification-baseline.md`: new section "Delivery outcomes
  (2026-11-21)" after "Initial baseline (2026-11-03)", with the window, event
  counts by type, delivered/bounced/complained (3 / 1 / 0), 1 suppressed
  address, the one eligible event (n = 1) not linked, and Resend-side sent→delivered latency
  (n = 3, p50 0.9 s, p90 ≈ 1.1 s).
- Same doc: the "Delivery latency" bullet, the Correlation bullet and "Still
  open" items 1–4 now say what is done and that `delivered_at − sent_at` waits
  on todo 726.
- Created `todos/726-pending-p3-resend-event-notification-linkage.md` for the
  event-to-`EmailNotification` linkage fix.
- `RESEND_WEBHOOK_SECRET: preserve()` was already in `.railway/railway.ts`
  (PR #1259); no change there.

### 2026-11-21 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-20-2202)

- AC 1: confirmed by the owner on 2026-11-21: "Owner confirmed (2026-11-21) on the approved counts-only prod read: RESEND_WEBHOOK_SECRET set and declared (#1259); 9 signed EmailProviderEvent rows recorded since 2026-11-03 20:52 UTC (4 email.sent, 3 email.delivered, 1 email.bounced Permanent, 1 suppression.added)" (`state.py confirm`; no command or evidence)
- AC 3: confirmed by the owner on 2026-11-21: "Owner confirmed (2026-11-21) the gap is recorded: 0 of 9 events link to an EmailNotification; the one forum email (2026-11-04) had email.sent + email.delivered events within 10 min but neither linked, and the row has no provider_email_id. Hypothesis, not verified: Resend over SMTP does not echo our client-set Message-ID. Fix re-homed to new todo 726" (`state.py confirm`; no command or evidence)

- Round-1 review (2026-11-21, non-blocking, fixed by hand): "0 of 9 linked" overstated the evidence, because `email.sent` and `suppression.added` are never matched by design. Reworded to n = 1 (the forum email's `email.delivered`) in the baseline doc, todo 726 and here, and noted that `suppression.added` is recorded but not acted on.
- Criterion 4 stays unticked only because its text says "re-pointed from todo 638", which the engine reads as a re-point. The counts are recorded in the baseline doc's "Delivery outcomes (2026-11-21)" section, and the owner confirmed it on 2026-11-21 ("Confirm all three"). The latency there is a Resend-side substitute; the `delivered_at − sent_at` p50/p90 that criterion 4 names is not computable until events link, and moves to todo 726.

### 2026-11-21 - Completed by the todo sweep (run 2026-11-20-2202)

- Archived by `land.py archive`; review is on the PR.

## Notes

Owner-only for the dashboard and the Railway secret. Step 2's `railway.ts`
declaration is repo work and can ride with whichever PR records the result.
