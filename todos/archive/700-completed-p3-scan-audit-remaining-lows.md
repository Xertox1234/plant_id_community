---
status: completed
priority: p3
issue_id: "700"
tags: [scan, plant-id, celery, quota]
dependencies: []
triage: ready
triaged: 2026-11-17
owner_decision: "L3: keep fail-open on Redis outage and add a Sentry alert; L15: option 2, accept rare duplicate scan-finished push, no migration (2026-11-17)"
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

- [x] L3: decision recorded with its date; a test shows the chosen behaviour
      with Redis unavailable.
- [x] L15: a test kills the notify task between claim and fan-out and shows
      the push is still sent (or the accepted trade-off recorded).

## Work Log

### 2026-11-06 - Filed from the scan-2 audit

- Bundled by owner choice at triage ("One bundled todo").

### 2026-11-17 - Implemented by the todo sweep (run 2026-11-17-1802)

- L3, decision recorded 2026-11-17 (owner): keep failing open on a Redis outage and alert. `QuotaManager.can_call_plant_id` and `reserve_plant_id` now send a Sentry `capture_message` on every Plant.id fail-open (no client, or a Redis error mid-call), naming only the exception class (a Redis error can carry the connection URL). Throttled process-locally to one per `PLANT_ID_QUOTA_FAIL_OPEN_ALERT_SECONDS` (300 s), since every allowance GET takes that path and the Django cache is the Redis that is down. `can_call_plant_id` reads the counters directly so a mid-call error reaches its alerting `except` instead of being swallowed as 0.
- L3 test: `backend/apps/plant_identification/tests/test_quota_manager.py` patches `get_redis_connection` to raise (and a client whose `get`/`incrby` raise): both methods return True, one alert per window, no URL or password in the message. Not changed: the PlantNet fail-open paths and the per-GET Redis PING (outside the owner decision).
- L15, owner option 2 (2026-11-17, no migration): `notify_scan_job_finished` is `acks_late=True`, `reject_on_worker_lost=True`, and sets `notified_at` only after the per-device sends are enqueued. Accepted trade-off: a worker killed between the fan-out and the mark sends the push twice. Tests in `backend/apps/plant_identification/tests/test_scan_task.py` kill the task before the fan-out (redelivery pushes) and after it (two sends), and pin both task options.
- Caveat: `reject_on_worker_lost` covers a lost pool child; a whole-container kill is redelivered only after the Redis broker's visibility timeout (default about 1 h, not set in settings). Not changed here.
- Audit manifest `docs/audits/2026-11-05-scan-2.md` rows L3 and L15 and the Deferred Items lines updated.

### 2026-11-17 - Verified by the todo sweep (run 2026-11-17-1802)

- AC 1: `bash -c "cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest apps/plant_identification/tests/test_quota_manager.py --create-db -q -p no:cacheprovider && grep -n 'L3, decision recorded 2026-11-17' todos/archive/700-completed-p3-scan-audit-remaining-lows.md"` — evidence `.sweep-evidence/g1/700-ac0.txt` (not committed), last lines:

  ```text
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 6 passed, 2 warnings in 0.27s =========================
  78:- L3, decision recorded 2026-11-17 (owner): keep failing open on a Redis outage and alert. `QuotaManager.can_call_plant_id` and `reserve_plant_id` now send a Sentry `capture_message` on every Plant.id fail-open (no client, or a Redis error mid-call), naming only the exception class (a Redis error can carry the connection URL). Throttled process-locally to one per `PLANT_ID_QUOTA_FAIL_OPEN_ALERT_SECONDS` (300 s), since every allowance GET takes that path and the Django cache is the Redis that is down. `can_call_plant_id` reads the counters directly so a mid-call error reaches its alerting `except` instead of being swallowed as 0.

  exit=0
  ```

- AC 2: `bash -c "cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest apps/plant_identification/tests/test_scan_task.py -k 'notify' --create-db -q -p no:cacheprovider && grep -n 'Accepted trade-off' todos/archive/700-completed-p3-scan-audit-remaining-lows.md"` — evidence `.sweep-evidence/g1/700-ac1.txt` (not committed), last lines:

  ```text
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ================ 3 passed, 23 deselected, 2 warnings in 21.56s =================
  80:- L15, owner option 2 (2026-11-17, no migration): `notify_scan_job_finished` is `acks_late=True`, `reject_on_worker_lost=True`, and sets `notified_at` only after the per-device sends are enqueued. Accepted trade-off: a worker killed between the fan-out and the mark sends the push twice. Tests in `backend/apps/plant_identification/tests/test_scan_task.py` kill the task before the fan-out (redelivery pushes) and after it (two sends), and pin both task options.

  exit=0
  ```

### 2026-11-17 - Completed by the todo sweep (run 2026-11-17-1802)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
