---
status: pending
priority: p2
issue_id: "698"
tags: [scan, plant-id, cost, owner-decision]
dependencies: []
source_review: "docs/audits/2026-11-05-scan-2.md"
source_finding: "H1"
---

# Scan 2.0: failed and late-cancelled scans still spend Plant.id for free

## Problem

The Scan 2.0 audit (H1) closed the cheap window: a cancel or stale expiry that
lands before the worker reaches the paid call now stops it. Two paths still
spend the app-wide Plant.id quota (default 3 calls/day) at no cost to the user,
because the stated rule is "failed and cancelled scans cost nothing":

1. a cancel timed while the Plant.id call is already in flight;
2. a diagnose scan of non-plant photos, which ends `failed` (no plant named)
   after spending 2 calls.

One free account repeating either, with fresh photos each time (the result
cache is keyed by image hash), can use up the day's Plant.id budget and put
every user on `plant_id_busy`. `SCAN_CREATE_RATE` is `100/h`, so the rate
limit barely slows it.

## Findings

- `backend/apps/plant_identification/tasks.py`: `_finalize` drops the outcome
  of a job that left `processing`, so a late cancel charges nothing; a
  `failed` job gets `charged_as=""` (`scan_jobs.classify_scan`).
- `backend/apps/plant_identification/scan_jobs.py` `counted_created_at`: only
  active jobs and `charged_as=<kind>` count against the allowance.
- `backend/apps/plant_identification/constants.py`: `SCAN_CREATE_RATE = "100/h"`.
- Source: scan-2 audit 2026-11-05, H1 residual (manifest Verification column).

## Proposed Solutions

### Option 1: Charge a scan once Plant.id was actually called (Recommended)

- **Implementation:** the task records that Plant.id was called; a job that
  ends `failed` or `cancelled` after that keeps `charged_as=<mode>`, so it
  counts against the allowance like a finished one. Copy in the app changes
  from "costs nothing" to "costs nothing unless the check already ran".
- **Pros:** closes both paths with one rule; bounded by the user's own
  allowance (1 free diagnose/day).
- **Cons:** a genuine no-plant photo now costs the user their daily check.
- **Effort:** half a day. **Risk:** low.

### Option 2: Cap free failures/cancels per user per day

- **Implementation:** a separate per-user counter of failed + cancelled scans
  that made a paid call; refuse create past N (e.g. 3) with a 429.
- **Pros:** keeps "failed costs nothing" for honest mistakes.
- **Cons:** a second limit to explain; N × 2 calls still exceeds the 3/day cap.
- **Effort:** half a day. **Risk:** low.

### Option 3: Lower `SCAN_CREATE_RATE` only

- Cheapest, but does not close either path.

## Recommended Action

1. Owner picks the rule (option 1, 2 or 3).
2. Implement it in `tasks.py` / `scan_jobs.py`, with tests that run a late
   cancel and a no-plant diagnose and assert the allowance.
3. Update the CLAUDE.md `SCAN_DIAGNOSE_DAILY_*` row and the app copy.

## Technical Details

- Audit manifest: `docs/audits/2026-11-05-scan-2.md` (H1 row).
- Pattern: `backend/docs/patterns/architecture/services.md`.

## Acceptance Criteria

- [ ] Owner decision recorded here with its date.
- [ ] A test proves a late-cancelled diagnose and a no-plant diagnose follow
      the chosen rule.

## Work Log

### 2026-11-06 - Filed from the scan-2 audit

- Filed as the owner-decision residual of H1 (fixed in the audit PR for the
  cancel-before-the-call window).
