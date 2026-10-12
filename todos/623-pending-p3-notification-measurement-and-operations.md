---
status: pending
priority: p3
issue_id: "623"
tags: [backend, notifications, email, observability, operations, privacy]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Owner: repo-only slice now — outcome vocabulary shared with 619, remove misleading track_opens, worker/beat/queue alert counters; provider feedback ingestion, attribution, prod checks and baseline re-pointed to todo 625. Email provider unknown, decide later (2026-10-12). Owner: 623 executes after 619 merges and extends 619's outbox attempt states — no second ledger (2026-10-12). Owner: operational alerts go to Sentry — cron-monitor check-ins for beat-scheduled tasks plus Sentry events/error logs for broker, retry-exhaustion and missing-push-config failures (2026-10-12)"
---

# Measure delivery and engagement and verify notification operations

## Problem

The project cannot establish notification effectiveness from successful send logs alone. Delivery/bounce/complaint outcomes, cross-channel engagement and current production sender/worker health need an evidence-backed measurement and operational verification path.

## Findings

Source: Devin's read-only email/notification audit and backlog comparison, 2026-10-12. Production configuration, DNS, provider dashboards and live delivery rates were not inspected; missing configuration is not asserted.

- `backend/apps/core/models.py:23-39,102-125` declares delivered/bounced/opened/clicked states and fields, but the audit search found no live writers for provider delivery/bounce outcomes or callers of `mark_opened`/`mark_clicked` in the audited backend paths.
- `backend/apps/core/services/email_service.py:369-397` records successful sends only. `track_opens` at `:79,94` is unused; transactional email at `:399-444` bypasses that tracking. Blog newsletter and package digest use Django mail directly, so this model is not a complete delivery ledger.
- FCM and browser-push tasks log provider acceptance; this does not prove device display or a useful user action. Care tasks can retain a notification claim without a displayed message, so `notification_sent` is not delivery evidence.
- `backend/bin/start.sh:41-49,150-178` starts/supervises a co-located worker with embedded beat. `backend/docs/deployment/railway.md:223-230` notes that the web healthcheck does not establish worker health. Older environment claims in deployment prose must not substitute for current observations.
- `backend/plant_community_backend/settings.py:1373-1389` schedules weekly forum/blog emails and 15-minute care sweeps. Queue latency, skipped runs, provider failures and catch-up behavior are not measured by a successful web response.

## Recommended Action

1. Define a privacy-conscious event/state vocabulary shared with delivery work in todo 619: queued, attempted, provider-accepted, retrying, terminal-failed and suppressed; delivered/bounced/complained only where provider evidence exists. Cover all live send paths, not just EmailService.send_email.
2. Confirm the deployed email provider and supported feedback mechanism. Implement authenticated, replay-safe and idempotent delivery/bounce/complaint ingestion plus an appropriate suppression policy. Preserve security-mail recovery UX; do not keep retrying undeliverable addresses or silently imply recovery mail succeeded.
3. Measure notification click/open-in-app and meaningful outcomes such as verification completion, discussion revisits and care completion with a defined attribution window. Treat opens as optional/noisy, not proof of engagement; remove or implement the misleading track_opens interface deliberately.
4. Add operational counters and alerts for queue age, broker failures, retry exhaustion, disabled/misconfigured push, stale worker/beat activity and expected scheduled runs. Do not create a second competing delivery ledger; extend the agreed delivery state.
5. With owner approval, record current SMTP/sender setup, SPF/DKIM/DMARC results, Firebase/APNs and VAPID readiness, worker/beat health and controlled delivery observations. Record the existing single-worker/embedded-beat scaling constraint and define when a separate scheduler/queue is required.
6. Establish a baseline before adding notification volume: denominators for eligible, opted-out, unavailable-device, attempted and accepted/delivered users; click/action rates; unsubscribe/complaint rates; and reminder lateness. Set actionable thresholds based on observed data, not invented targets.

## Technical Details

Files: core email models/service, users account-mail paths, blog newsletter/digest, package forum digest, host forum tasks, garden reminders, push registration/router and web notification click handlers. Reference `backend/docs/patterns/domain/celery.md` and `backend/docs/patterns/security/secret-management.md`.

Existing work remains separate: 547 owns the physical-device due-care verification; 602 owns browser registration/security; 605/606 own their specific delivery fixes. Archived 335/286 establish historical worker/FCM work, not current production health. Provider integration must use documented signature verification and avoid raw addresses, tokens, message bodies or credentials in telemetry.

## Acceptance Criteria

- [ ] All live email/push send paths contribute consistent attempted/accepted/failed/suppressed outcomes; tests distinguish provider acceptance from delivered/displayed and from user engagement.
- [ ] Provider feedback authentication, malformed-event refusal, duplicate/replayed/out-of-order events and message correlation are tested. Bounce/complaint suppression prevents inappropriate future sends under a recorded policy without bypassing account-security controls. → todo 625 (re-pointed 2026-10-12)
- [ ] Click/action attribution is implemented with recorded consent/privacy, retention and deletion rules; tests cover attribution windows and no duplicate counting. Any decision not to collect opens is explicit, and the unused track_opens promise is removed or corrected. → todo 625 (re-pointed 2026-10-12)
- [ ] Tests or controlled fault injection demonstrate alerts for broker failure, aged queues, exhausted retries, missing push configuration and missed worker/beat activity without secrets or raw PII in logs.
- [ ] Owner-approved production checks record dates and observed results for sender-domain authentication, deployed provider settings, worker/beat and push readiness; unknowns stay explicitly open, not marked verified from repository defaults. → todo 625 (re-pointed 2026-10-12)
- [ ] Controlled test-inbox/device delivery evidence and an initial aggregate baseline are recorded, with observation window, denominators, delivery latency and click/action/unsubscribe outcomes; existing evidence from 547 may be reused with its build/date stated. → todo 625 (re-pointed 2026-10-12)
- [ ] Operational recovery steps and the single-scheduler/scaling constraint are documented in the existing deployment/pattern docs; relevant backend/consumer tests pass. Unavailable external checks remain open or are explicitly re-pointed before archive.

## Work Log

### 2026-10-12 - Created from effectiveness audit

- Grouped delivery feedback, engagement measurement, alerting and production evidence gaps. No active todo covering this end-to-end scope was found in the backlog comparison.
- No provider/DNS configuration or production user data was accessed or changed during filing. Production checks and any live messages require explicit approval.

### 2026-10-12 - Triage split (run 2026-10-12-1616)

- Owner decision at triage: repo-only slice here (outcome vocabulary, track_opens, alert counters, docs); provider feedback (AC2), attribution (AC3), prod checks (AC5) and baseline (AC6) re-pointed to [todo 625](625-pending-p3-notification-provider-feedback-and-prod-baseline.md). Provider unknown.

## Notes

P3 observability and operational assurance, not a claim of a live delivery outage. Coordinate implementation sequencing with todo 619 after those new todos are committed; dependencies are intentionally empty under todos/README.md's rule against uncommitted dependency IDs. Do not add tracking pixels or third-party analytics without the recorded privacy/product decision.
