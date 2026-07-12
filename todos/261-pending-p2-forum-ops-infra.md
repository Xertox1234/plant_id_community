---
status: pending
priority: p2
issue_id: "261"
tags: [forum, ops, celery, ci, e2e]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "H21, M34, M42, L17"
---

# Forum epic: ops, scheduling, E2E & caching

## Problem

Operational gaps around the forum: tombstone pruning is documented and tested
but never scheduled anywhere (unbounded table growth; the 30-day retention
contract is silently unenforced), the write path has zero E2E coverage, hot
public reads carry no HTTP cache headers despite sitting behind Cloudflare, and
CI has no migration-drift gate. p2 epic from the 2026-07-11 forum-modernization
audit.

## Findings

- **H21** — Tombstone pruning never scheduled: `prune_forum_tombstones`
  documents "run daily via beat/cron" and is unit-tested, but no
  `CELERY_BEAT_SCHEDULE` exists anywhere and `railway.json` never invokes it —
  `TopicDeletedLog` grows unbounded
  (`W/management/commands/prune_forum_tombstones.py:1-8`).
- **M34** — Forum write path has no E2E coverage: the golden-path spec is
  unauthenticated-browse-only by its own comment (predates Spec 2);
  create/reply/edit/delete/react/upload exist only as mocked component tests
  (`web/e2e/forum-golden-path.spec.ts:3-4`).
- **M42** — No HTTP-layer caching/conditional requests (Cache-Control/ETag) on
  hot public reads — DISTINCT from the documented no-Redis-app-cache decision
  (`backend/docs/patterns/architecture/caching.md:186-198`); board/topic lists
  are public + read-heavy and the deploy already sits behind Cloudflare.
  Caveat: post-list `can_edit`/`can_delete` is per-user — caching must be
  anon-scoped/varied.
- **L17** — No `makemigrations --check` gate in CI (verified currently clean;
  preventive given 11 forum migrations and schema churn history)
  (`.github/workflows/backend-ci.yml`).

## Recommended Action

1. **H21 — but first, verify prod Celery topology.** The Railway deploy (per
   `railway.json` + deploy state) may run no Celery worker or beat process at
   all — in which case `send_forum_push` (`.delay()`-only) also never executes
   in production, a bigger problem than pruning. Investigate, then either:
   Option A — add a worker+beat service on Railway with a
   `CELERY_BEAT_SCHEDULE` entry for daily pruning; Option B — Railway cron
   invoking `manage.py prune_forum_tombstones` (no beat dependency) and an
   explicit decision about push-task execution. Record the topology in the
   deploy docs either way.
2. **M34 E2E**: authed Playwright spec — login → create thread → reply → edit
   → react → delete against a real backend (mirror the existing golden-path
   harness; decide CI backend provisioning: service container vs local-only
   tag).
3. **M42 caching**: `Cache-Control: public, s-maxage` on anonymous board/topic
   list + search responses with correct `Vary` (cookie/auth) or split-path
   handling; ETag/Last-Modified where cheap (`updated_at` is indexed).
4. **L17**: add `python manage.py makemigrations --check --dry-run` to backend
   CI.

## Technical Details

- `backend/docs/patterns/domain/celery.md` for task/beat conventions;
  `docs/rules/celery.md` is auto-injected on edits.
- Cache work must not leak per-user capabilities: verify `can_edit/can_delete`
  are only in authed responses or vary correctly — add a test asserting an
  anon response never carries user-specific fields alongside cache headers.
- Railway proxy note for E2E/caching debugging:
  `RATELIMIT_TRUSTED_PROXY_COUNT=2` (real client = 2nd-from-last XFF entry).

## Acceptance Criteria

- [ ] Prod Celery topology documented; tombstones older than 30 days actually
      pruned on schedule in that topology (evidence: log line or row-count
      check after a scheduled run)
- [ ] Push-task execution home in prod confirmed as part of the topology check
- [ ] Authed E2E covers create → reply → edit → react → delete
- [ ] Anonymous hot reads carry cache headers; authed/user-specific responses
      provably uncached or varied (test)
- [ ] CI fails when model changes lack migrations

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 4 open findings per the manifest's Phase 4 grouping table.
- Added the prod-Celery-topology investigation step: H21's missing beat
  schedule implies the worker/beat presence question, which also gates push
  delivery (C2/todo 253).

## Notes

p2. The topology investigation (step 1) is cheap and load-bearing for two
other epics — do it first even if the rest waits.

Phase 6 review residue (2026-07-11 audit, celery reviewer, LOW): the FCM
retry backoff (30/60/120s) has no jitter — a correlated FCM outage retries
every queued push in lockstep. Fine at current scale; add randomized offset
if push volume grows.
