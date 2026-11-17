---
status: completed
priority: p1
issue_id: "702"
tags: [legal, privacy, operations, docs]
dependencies: []
triage: ready
triaged: 2026-11-17
owner_decision: "Breach contact and notifier identity stay launch-time blanks like the other operator fields (2026-11-17)"
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

- [x] The three files exist and the runbook names each regulator with its
      deadline and its notice contents.
- [x] The processor register lists every service that `backend/` sends
      personal data to (`grep` the settings for each key name).
- [x] The deployment checklist points at the runbook and has no Heroku
      commands in its incident section.

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit: documents only, no code; the owner should read the
  runbook before it is relied on.

### 2026-11-10 - Processor register written (item 3 only)

- `docs/operations/processors.md` exists, written for todo 707 (L15). It has
  no agreement links and several "unsourced" cells. The breach runbook, the
  breach register and the checklist pointer are not started.

### 2026-11-17 - Implemented by the todo sweep (run 2026-11-17-1542)

- Added `docs/operations/breach-runbook.md`: first-hour containment, the
  real-risk-of-significant-harm test, and for the Alberta OIPC, the federal
  OPC, California (residents and Attorney General) and Mexico the deadline and
  the notice contents. PIPEDA ss. 10.1-10.3, its Regulations and LFPDPPP
  art. 19 were re-read; Alberta PIPA, PIPEDA s. 28 and California s. 1798.82
  (the fetch was refused) are marked "(not re-read)" for the owner to confirm.
- Added `docs/operations/breach-register.md`: column rules, 24-month
  retention, no identifying details in the public repo, empty register.
- `docs/operations/processors.md`: added plant.health, Google web sign-in,
  browser push services and Anthropic (owner-run eval); GitHub sign-in and
  OpenWeather (garden coordinates) as wired but not declared in production;
  the services that get no personal data; and a key index mapping every
  outside-service key in settings and `backend/apps` to its row.
- `docs/DEPLOYMENT_SECURITY_CHECKLIST.md`: the incident steps no longer use
  Heroku or a local log file; they point at the runbook and the register.
- The breach contact stays the launch-time `[[PRIVACY_OFFICER_NAME]]` /
  `[[CONTACT_EMAIL]]` blanks (owner decision 2026-11-17).

### 2026-11-17 - Verified by the todo sweep (run 2026-11-17-1542)

- AC 1: `bash -c 'R=docs/operations; ls -1 $R/breach-runbook.md $R/breach-register.md $R/processors.md && grep -nE "^### |^- \*\*(When|What it contains|People affected|Attorney General|Regulator)" $R/breach-runbook.md'` — evidence `.sweep-evidence/g1/702-ac0.txt` (not committed), last lines:

  ```text
  182:### Mexico: affected people
  187:- **When:** "de forma inmediata" (immediately), for a breach at any stage of
  191:- **What it contains:** art. 19 lists no contents. Give at least what the
  196:- **Regulator:** the authority is the Secretaría Anticorrupción y Buen
  200:### A breach at a processor
  ```

- AC 2: `bash -c 'cd . && m=0; for k in $(grep -rhoE "(config|os\.getenv|os\.environ\.get)\(.[A-Z0-9_]*(API_KEY|ACCESS_KEY[A-Z_]*|_DSN|CLIENT_ID|CLIENT_SECRET|R2_[A-Z_]+|DATABASE_URL|REDIS_URL|BROKER_URL|CELERY_RESULT_BACKEND|EMAIL_HOST[A-Z_]*|VAPID_[A-Z_]*|FIREBASE_[A-Z_]*|WEBHOOK_SECRET)." --include=*.py backend/plant_community_backend/settings.py backend/apps backend/packages | sed -E "s/^[^(]*\(.//; s/.$//" | sort -u); do if grep -qF "\`$k\`" docs/operations/processors.md; then echo "OK $k"; else echo "MISSING $k"; m=1; fi; done; exit $m'` — evidence `.sweep-evidence/g1/702-ac1.txt` (not committed), last lines:

  ```text
  OK SENTRY_DSN
  OK TREFLE_API_KEY
  OK UNSPLASH_ACCESS_KEY
  OK VAPID_PRIVATE_KEY
  OK VAPID_PUBLIC_KEY
  ```

- AC 3: `bash -c 'F=docs/DEPLOYMENT_SECURITY_CHECKLIST.md; sed -n "/Emergency Rollback/,\$p" $F; echo ---; echo runbook_links=$(sed -n "/Emergency Rollback/,\$p" $F | grep -c operations/breach-runbook.md); n=$(grep -ci heroku $F); echo heroku_count_whole_file=$n; test $n -eq 0 && sed -n "/Emergency Rollback/,\$p" $F | grep -q operations/breach-runbook.md'` — evidence `.sweep-evidence/g1/702-ac2.txt` (not committed), last lines:

  ```text
  **Next Review:** Before every production deployment
  **Contact:** Development team security lead
  ---
  runbook_links=1
  heroku_count_whole_file=0
  ```

### 2026-11-17 - Completed by the todo sweep (run 2026-11-17-1542)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

P1: the duty exists today, whether or not a breach has happened. A lawyer
should check the runbook's thresholds.
