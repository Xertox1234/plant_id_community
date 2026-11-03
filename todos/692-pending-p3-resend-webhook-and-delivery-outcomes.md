---
status: pending
priority: p3
issue_id: "692"
tags: [notifications, email, observability, operations, owner, prod]
dependencies: []
source_review: "todos/archive/638-completed-p3-notification-delivery-baseline.md"
source_finding: "AC2"
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

- [ ] `RESEND_WEBHOOK_SECRET` is set on Railway and declared in `.railway/railway.ts`; the webhook receives a signed event and records an `EmailProviderEvent`
- [ ] Resend's own open/click tracking is off for `houseplant-md.com`
- [ ] A provider event is linked to its `EmailNotification` via our Message-ID (or the gap is recorded if Resend rewrites it)
- [ ] The baseline doc records delivered/bounced/complained counts and sent→delivered latency over a stated window (re-pointed from todo 638)

## Work Log

### 2026-11-03 - Filed from todo 638

Prod read (owner-approved, aggregate-only): 9 forum emails sent in 30 days, all
with our Message-ID, none with a provider email id, 0 provider events.

## Notes

Owner-only for the dashboard and the Railway secret. Step 2's `railway.ts`
declaration is repo work and can ride with whichever PR records the result.
