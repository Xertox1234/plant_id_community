---
status: pending
priority: p3
issue_id: "211"
tags: [celery, plant-identification, backend, resilience, tech-debt]
dependencies: []
source_review: "docs/audits/2026-06-02-full.md"
source_finding: "none (discovered while implementing todo 208)"
---

# Decide on Celery enablement + synchronous plant-ID path resilience

## Problem

`CELERY_ENABLED` is **never defined in settings**, so
`getattr(settings, "CELERY_ENABLED", False)` is always `False`. The plant-ID
create endpoint therefore runs identification **synchronously, in the
request/response cycle**, and the Celery task `run_identification` is **dormant**
(only enqueued inside `if use_celery:` at `views.py:178`). Two consequences:

1. The autoretry / `on_failure` resilience added in todo 208 is correct but
   **inert** until Celery is actually enabled — the live path has no retry at all.
2. On the live synchronous path, a transient external-API failure still produces
   **fake fallback results** (`Rosa damascena` / `Monstera` / `Ficus`) and marks
   the request `identified`/`needs_help` — the anti-pattern the 2026-06-02 audit
   flagged. todo 208 deliberately preserved this (gated behind
   `reraise_transient=False`) to avoid a live regression; it was not fixed.

## Findings

- `apps/plant_identification/views.py:171` — `use_celery = getattr(settings,
  "CELERY_ENABLED", False)`; `CELERY_ENABLED` is absent from
  `plant_community_backend/settings.py` (grep returns only this read site), so it
  is permanently `False`.
- `apps/plant_identification/views.py:178` — `run_identification.delay(...)` is
  the only enqueue site, inside the dead `if use_celery:` branch.
- `apps/plant_identification/views.py:189,195,273` — the synchronous callers of
  `identify_plant_from_request` (the live path).
- `apps/plant_identification/services/identification_service.py` — the
  `reraise_transient` flag (todo 208) defaults `False`; sync callers get the
  legacy swallow→fallback behavior. The fake-fallback rows come from
  `_create_fallback_results` (the `Rosa/Monstera/Ficus` list).
- Source: discovered while implementing todo 208 (advisor flagged the shared
  service's blast radius; user chose the zero-regression opt-in flag and deferred
  this decision). See todo 208 Work Log.

## Proposed Solutions

### Option 1: Enable Celery for plant identification (Recommended)

- **Implementation:** define `CELERY_ENABLED` in settings (env-driven), confirm a
  worker + broker run in each environment, then the task's autoretry/`on_failure`
  (todo 208) becomes the live resilience path. Front-end already polls the
  `status`/`results` actions, so async is viable.
- **Pros:** real retry on transient failures; no in-request blocking on up-to-120s
  external I/O; the durability work (`acks_late`/`reject_on_worker_lost`) starts
  mattering.
- **Cons:** requires a running worker everywhere (incl. dev/CI); needs the
  websocket/poll UX verified end-to-end.
- **Effort:** hours. **Risk:** medium — operational (worker availability).

### Option 2: Harden the synchronous path itself

- **Implementation:** keep sync processing but stop emitting fake fallback results
  on a transient API error — mark the request `failed` (or `needs_help` with an
  honest "service unavailable" message) instead of fabricated suggestions.
- **Pros:** removes the audit-flagged fake-fallback anti-pattern without operating
  a worker fleet.
- **Cons:** still no retry; a user-visible behavior change (was 201 + fake
  results).
- **Effort:** ~1 hour. **Risk:** low–medium (UX change).

## Recommended Action

1. Decide async-vs-sync for plant ID (Option 1 vs 2) — likely Option 1 long-term.
2. If Option 1: add `CELERY_ENABLED = config("CELERY_ENABLED", default=False,
   cast=bool)` to settings, wire it on per environment, and verify a queued
   request retries on a transient `ExternalAPIError` and finalizes via
   `on_failure` (the todo 208 tests already cover the task internals).
3. Independently of 1/2, revisit `_create_fallback_results`: returning fabricated
   species on an API failure is misleading — prefer an honest failure/needs-help
   state.

## Technical Details

- Retry/`on_failure` machinery: `apps/plant_identification/tasks.py`
  (`IdentificationTask`, `autoretry_for`, `TERMINAL_STATUSES`).
- Sync vs async branch: `apps/plant_identification/views.py:165-195`
  (`perform_create`).
- The `reraise_transient` flag: `services/identification_service.py`
  `identify_plant_from_request(...)`.
- Pattern doc: `backend/docs/patterns/domain/celery.md`.

## Acceptance Criteria

- [ ] A documented decision (async-via-Celery vs hardened-sync) is recorded and
      implemented.
- [ ] If Celery is enabled: a transient `ExternalAPIError` on a queued request
      triggers a real retry and the request finalizes `failed` after exhaustion
      (not stuck `processing`), verified by a test against the live enqueue path.
- [ ] On the chosen live path, a transient external-API failure no longer returns
      fabricated `Rosa/Monstera/Ficus` fallback species.

## Work Log

### 2026-06-03 - Created

- Filed as the deferred follow-up from todo 208 (audit H1/M12). 208 fixed the
  task-side autoretry/`on_failure` but found the task is dormant
  (`CELERY_ENABLED` unset) and intentionally preserved the synchronous
  fake-fallback behavior to avoid a live regression.

## Notes

p3: the feature works today (sync path returns results), so this is resilience +
correctness hardening and an operational decision, not an active failure. Related:
todo 208 (archived), audit `docs/audits/2026-06-02-full.md`.
