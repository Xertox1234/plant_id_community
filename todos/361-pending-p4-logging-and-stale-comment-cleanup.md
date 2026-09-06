---
status: pending
priority: p4
issue_id: "361"
tags: [code-quality, logging, backend]
dependencies: []
source_review: "github-issues-185-186"
---

# Log-prefix and stale-comment cleanup (surviving half of issues #185/#186)

## Problem

GitHub issues #185 and #186 (both filed 2025-11-11 by a "Pattern Recognition
Specialist" audit, both LOW) sat untouched for ten months. They are converted
here so the todo sweeps can see them — but **most of #185 is already dead**, and
importing it verbatim would have created make-work.

## Findings

Verified against the tree on 2026-09-06 before conversion, not taken on trust:

| Source | Item | Verified state |
| --- | --- | --- |
| #185 (1) | `console.error` in `web/src/utils/csrf.ts` | **Already fixed.** The file now uses `logger.error`/`logger.debug`/`logger.warn` throughout, all with `[CSRF]` prefixes (`csrf.ts:66,72,81,88,91`). Nothing to do. |
| #185 (2) | `backend/apps/forum/constants.py:133-134` cache-key prefixes | **Obsolete.** `apps/forum` was retired in the wagtail_forum rebuild; the path no longer exists and `CACHE_PREFIX_TRUST_LIMITS` / `CACHE_PREFIX_DAILY_ACTIONS` appear nowhere in `backend/`. The "requires cache invalidation after deployment" warning is likewise moot. |
| #185 (3) | Stale `# TODO 040 fix` comments | **Still present** — `backend/apps/blog/signals.py:69, 99, 129` (the issue said 67/99/134; lines have drifted). Todo 040 is long complete. |
| #186 | Unprefixed log statements | **Partly valid.** `apps/plant_identification/services/plant_id_service.py` has 3 unprefixed `logger.*("...")` calls against 1 prefixed. The issue's repo-wide "5%" figure was never re-measured and should not be trusted as scope. |

So two of the four original items are closed by time, and two survive.

## Recommended Action

1. Delete the three `# TODO 040 fix` trailing comments in
   `backend/apps/blog/signals.py` (lines 69, 99, 129). Comment-only change.
2. Re-measure the log-prefix gap before doing anything about it — count
   unprefixed `logger.*` calls across `backend/apps/`, rather than inheriting
   the stale 5% claim. If the real count is small, add the bracketed prefixes;
   if it is large, split it out and re-rate.
3. Do **not** revisit #185 items 1 and 2. They are recorded above as resolved
   and obsolete so the next reader does not re-derive that.

## Technical Details

- Prefix convention in use: `[CACHE]`, `[PERF]`, `[ERROR]`, `[CIRCUIT]`,
  `[RATE_LIMIT]`, `[SPAM]`, `[CSRF]`. Prefixes exist to make logs filterable.
- Caution when re-measuring: `apps.*` loggers in this project run with
  `propagate=False`, so they are invisible to `caplog` — a test asserting on
  prefixes needs the handler attached directly, not `caplog` alone.
- Original sources: GitHub issues #185 and #186, both closed on 2026-09-06 with
  a pointer to this file.

## Acceptance Criteria

- [ ] No `TODO 040` string remains in `backend/apps/blog/signals.py`
- [ ] Actual repo-wide unprefixed-logger count recorded in this file before any
      prefix work begins
- [ ] Prefixes added to whatever that count identifies, or the item explicitly
      re-scoped with a reason
- [ ] Backend suite still green

## Notes

p4, dropped from the issues' original P3/LOW: half the original scope no longer
exists, and what remains is three comment deletions plus an unmeasured tidy-up.
Recorded rather than discarded only because the stale comments actively mislead
— they point at a todo that has been done for months.

## Work Log

### 2026-09-06 - Converted from GitHub issues #185/#186

- Converted during a GitHub cleanup sweep so the backlog lives in `todos/`
  where the sweep skills can see it; GitHub issues cannot be swept.
- Each of the four original items was checked against the current tree first.
  Two were already resolved or obsolete and are deliberately not carried
  forward as work.
