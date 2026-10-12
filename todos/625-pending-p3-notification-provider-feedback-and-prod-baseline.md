---
status: pending
priority: p3
issue_id: "625"
tags: [backend, notifications, email, observability, operations, privacy]
dependencies: []
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
- [ ] Controlled test-inbox/device delivery evidence and an initial aggregate baseline are recorded, with observation window, denominators, delivery latency and click/action/unsubscribe outcomes; existing evidence from 547 may be reused with its build/date stated.

## Work Log

### 2026-10-12 - Split from 623 at triage

- Criteria 623 AC2, AC3, AC5 and AC6 re-pointed here by owner decision; wording carried over unchanged. 623's slice may already remove track_opens; if so, AC2 here is satisfied for that clause by citing it.

## Notes

Production checks and live messages require explicit owner approval; never read production unasked. No tracking pixels or third-party analytics without a recorded privacy decision.
