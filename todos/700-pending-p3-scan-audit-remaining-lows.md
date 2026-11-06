---
status: pending
priority: p3
issue_id: "700"
tags: [scan, plant-id, celery, quota]
dependencies: []
source_review: "docs/audits/2026-11-05-scan-2.md"
source_finding: "L3, L15"
---

# Scan 2.0 audit: the two remaining low findings

## Problem

Two low findings from the 2026-11-05 Scan 2.0 audit were not fixed in its PR:
one is a policy call, the other needs a schema change the audit did not
justify. The owner chose to bundle the remaining lows into one todo.

## Findings

- **L3, quota fails open when Redis is down.** `QuotaManager.can_call_plant_id`
  and `reserve_plant_id` return True on a Redis outage (documented), so the
  app-wide Plant.id cap disappears for its duration. `QuotaManager()` also
  PINGs Redis on every allowance GET
  (`backend/apps/plant_identification/services/quota_manager.py`,
  `scan_jobs.allowance_for`).
- **L15, a push lost when the worker dies mid fan-out.**
  `notify_scan_job_finished` sets `notified_at` before enqueuing the
  per-device sends, with early ack. A worker killed between the claim and the
  fan-out leaves `notified_at` set and no push sent
  (`backend/apps/plant_identification/tasks.py`).

## Proposed Solutions

### L3

- **Option 1 (Recommended):** fail closed for **diagnose** creates only (the
  paid path), so a Redis outage answers `plant_id_busy` rather than spending
  uncapped; identify keeps working through PlantNet.
- **Option 2:** keep failing open, but alert (Sentry) on the warning line.

### L15

- **Option 1 (Recommended):** add `notify_claimed_at` alongside
  `notified_at`; a claim older than a few minutes without `notified_at` is
  re-claimable by the M2 stale sweep. Needs a migration.
- **Option 2:** `acks_late=True` + `reject_on_worker_lost=True` on the notify
  task, and set `notified_at` only after the fan-out (accepts a rare duplicate
  push instead of a lost one).

## Recommended Action

1. L3: owner picks fail-closed-for-diagnose vs alert; implement with a test
   that drives a Redis outage.
2. L15: implement option 2 (smaller) unless a duplicate push is unacceptable.

## Technical Details

- Manifest: `docs/audits/2026-11-05-scan-2.md`, rows L3 and L15.
- `backend/docs/patterns/domain/celery.md`, `docs/rules/celery.md`.

## Acceptance Criteria

- [ ] L3: decision recorded with its date; a test shows the chosen behaviour
      with Redis unavailable.
- [ ] L15: a test kills the notify task between claim and fan-out and shows
      the push is still sent (or the accepted trade-off recorded).

## Work Log

### 2026-11-06 - Filed from the scan-2 audit

- Bundled by owner choice at triage ("One bundled todo").
