---
status: pending
priority: p1
issue_id: "702"
tags: [legal, privacy, operations, docs]
dependencies: []
---

# Breach register, notification runbook and processor register

## Problem

There is no record of personal-data breaches and no procedure for notifying
regulators or users. Keeping a breach record is a standing duty under PIPEDA
s. 10.3 (24 months), and Alberta PIPA s. 34.1 requires notice to the
Commissioner without unreasonable delay. There is also no list of the
processors that receive personal data.

## Findings

Source: `docs/audits/2026-11-10-auth-legal.md`, rows H4 and M20.

- **H4** `docs/DEPLOYMENT_SECURITY_CHECKLIST.md:840-865` is the only incident
  text: generic, with stale Heroku commands. A search of `docs/` found no
  register and no runbook.
- **M20** No processor / data-processing-agreement register and no privacy
  impact assessment under `docs/`.

## Recommended Action

1. Add `docs/operations/breach-runbook.md`: how to judge "real risk of
   significant harm", who is notified (Alberta OIPC, the federal OPC for
   cross-border data, affected users; California and Mexico if users there
   are affected), the deadlines, and what each notice must contain.
2. Add `docs/operations/breach-register.md`: one row per incident (date,
   what, data, people affected, assessment, notices sent), kept 24 months at
   least. Every incident is recorded, including ones judged not notifiable.
3. Add `docs/operations/processors.md`: each processor, what it receives,
   where it stores it, the agreement link, and how deletion is asked for.
4. Replace the stale section of the deployment checklist with a pointer.

## Technical Details

Processors seen in code: Railway, Cloudflare (R2), Firebase / Google, Sentry,
Resend, Plant.id, PlantNet, OpenAI. The storage country of each is to be
confirmed from its own documentation (see todo 701, L16).

## Acceptance Criteria

- [ ] The three files exist and the runbook names each regulator with its
      deadline and its notice contents.
- [ ] The processor register lists every service that `backend/` sends
      personal data to (`grep` the settings for each key name).
- [ ] The deployment checklist points at the runbook and has no Heroku
      commands in its incident section.

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit: documents only, no code; the owner should read the
  runbook before it is relied on.

## Notes

P1: the duty exists today, whether or not a breach has happened. A lawyer
should check the runbook's thresholds.
