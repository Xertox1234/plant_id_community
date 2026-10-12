---
status: pending
priority: p3
issue_id: "625"
tags: [backend, notifications, email, observability, operations, privacy]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Owner: approved looking up the provider and read-only prod checks (2026-10-12); provider is Resend over SMTP (smtp.resend.com:587 TLS, from houseplant-md.com), so build Resend webhook (Svix-signed) feedback ingestion and suppression. Owner: attribution = first-party signed click redirects only, no opens, no pixel/third-party analytics, 90-day retention, deleted with the account; remove the track_opens promise (2026-10-12). Owner: AC4 baseline re-pointed to todo 638 (2026-10-12). Test sends NOT approved"
---

# Ingest provider delivery feedback, attribute engagement and record a production baseline

## Problem

Split from todo 623 at triage (run 2026-10-12-1616, owner decision 2026-10-12): 623 ships the repo-only slice (outcome vocabulary, track_opens, alert counters, docs). This todo owns the provider-dependent and production-dependent work from 623's AC2, AC3, AC5 and AC6. The deployed email provider is unknown (owner, 2026-10-12).

## Findings

- No bounce/complaint/webhook ingestion exists; `mark_opened`/`mark_clicked` in `backend/apps/core/models.py` have no callers.
- Sender-domain authentication (SPF/DKIM/DMARC), provider settings, worker/beat health and a delivery baseline have never been recorded from production.

## Recommended Action

1. Owner identifies the deployed email provider and its feedback mechanism; then build authenticated, replay-safe, idempotent feedback ingestion and a suppression policy on 623's outcome vocabulary.
2. Decide consent/privacy/retention for click/action attribution; implement it or record a dated decision not to.
3. With owner approval, record production checks and an initial aggregate baseline.

## Acceptance Criteria

- [ ] Provider feedback authentication, malformed-event refusal, duplicate/replayed/out-of-order events and message correlation are tested. Bounce/complaint suppression prevents inappropriate future sends under a recorded policy without bypassing account-security controls.
- [ ] Click/action attribution is implemented with recorded consent/privacy, retention and deletion rules; tests cover attribution windows and no duplicate counting. Any decision not to collect opens is explicit, and the unused track_opens promise is removed or corrected.
- [ ] Owner-approved production checks record dates and observed results for sender-domain authentication, deployed provider settings, worker/beat and push readiness; unknowns stay explicitly open, not marked verified from repository defaults.
- [ ] Controlled test-inbox/device delivery evidence and an initial aggregate baseline are recorded, with observation window, denominators, delivery latency and click/action/unsubscribe outcomes; existing evidence from 547 may be reused with its build/date stated. → todo 638 (re-pointed 2026-10-12)

## Work Log

### 2026-10-12 - Split from 623 at triage

- Criteria 623 AC2, AC3, AC5 and AC6 re-pointed here by owner decision; wording carried over unchanged. 623's slice may already remove track_opens; if so, AC2 here is satisfied for that clause by citing it.

### 2026-10-12 - Triage and owner-approved read-only prod checks (run 2026-10-12-1748)

- Owner approved identifying the provider and read-only production checks; test sends were not approved. AC4 (baseline) re-pointed to [todo 638](638-pending-p3-notification-delivery-baseline.md).
- Observed 2026-10-12T17:50Z. Provider: Resend over SMTP. Railway `production` has `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST=smtp.resend.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=True`, and `DEFAULT_FROM_EMAIL` at `houseplant-md.com`. Only variable names and non-secret values were read.
- DNS, via 1.1.1.1: `_dmarc.houseplant-md.com` = `v=DMARC1; p=none; rua=mailto:…@dmarc-reports.cloudflare.net`. `resend._domainkey.houseplant-md.com` has a published DKIM key (`p=MIGfMA0…`). `send.houseplant-md.com` TXT = `v=spf1 include:amazonses.com ~all` and its MX = `10 feedback-smtp.us-east-1.amazonses.com`. The root `houseplant-md.com` has no SPF TXT and no MX. DMARC is monitor-only (`p=none`), which is an open hardening item, not verified enforcement.
- Worker/beat: Railway logs show `[start] worker pid 5 (celery … worker -B --schedule=/tmp/celerybeat-schedule --concurrency=2 …)`, `beat: Starting...` and `celery@8571ef8ca71b ready.` at 2026-10-12 17:27:57, then `Scheduler: Sending due task care-task-reminders` at 17:30:00 and 17:45:00. The embedded beat is on schedule.
- Push readiness: `FIREBASE_CREDENTIALS_B64`, `FIREBASE_PROJECT_ID`, `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` are set. Names only; that the values are valid is not proven by presence.

## Notes

Production checks and live messages require explicit owner approval; never read production unasked. No tracking pixels or third-party analytics without a recorded privacy decision.
