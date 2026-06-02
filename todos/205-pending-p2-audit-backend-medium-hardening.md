---
status: pending
priority: p2
issue_id: "205"
tags: [backend, drf, celery, security, performance, audit]
dependencies: []
source_review: "docs/audits/2026-06-02-full.md"
source_finding: "M1, M3, M4, M6, M7, M13"
---

# Backend medium-severity hardening (audit 2026-06-02)

## Problem

Six independent medium-severity backend issues from the full audit: an
unthrottled auth endpoint, two non-atomic multi-row writes, a silently-dropped
serializer field, an uncached public stats endpoint, and a missing Celery
durability flag.

## Findings

- **M6 (security) — `firebase_token_exchange` has no rate limit.**
  `backend/apps/users/firebase_auth_views.py:89-91`. AllowAny endpoint runs
  Firebase token crypto + DB user creation per call; every sibling auth entry
  point (`register`, `login`, OAuth) carries `@ratelimit`. Add `@ratelimit`
  (e.g. `key="ip", rate="10/m"`) via `apps.core.ratelimit`.
- **M3 / M4 — non-atomic forum writes.**
  `CreateTopicSerializer.create` (`apps/forum_integration/serializers.py:385-438`)
  and `CreatePostSerializer.create` (`:473-506`) each write Topic/Post(+RichPost)
  - save with no `transaction.atomic()` (ATOMIC_REQUESTS is off). A mid-failure
  leaves a half-formed topic. Wrap each in `with transaction.atomic():`.
- **M1 — `CareLogSerializer.activity_type_display` silently dropped.**
  `apps/garden_calendar/api/serializers.py:685-686` declares
  `CharField(source="get_activity_type_display")` but `CareLog.activity_type`
  has no `choices=`, so DRF raises `SkipField` and omits the key while
  drf-spectacular still advertises it. **Fix (doc-confirmed):** add `choices=`
  to the model field (makes `get_FOO_display` exist *and* drf-spectacular emits
  an enum) — needs a migration. Or drop the field if `activity_type` is free-form.
- **M7 — `forum_stats` uncached.** `apps/forum_integration/api_views.py:302-318`
  runs 3 COUNT queries on every public request. Add a short-TTL Redis cache
  (mirror the already-fixed `blog_stats` pattern).
- **M13 — Celery task lacks `acks_late`.**
  `apps/plant_identification/tasks.py:18-31`. A worker killed mid-identification
  (120s external I/O) loses the message. Set `acks_late=True` +
  `task_reject_on_worker_lost=True` — safe given the task's idempotency guard
  (Celery FAQ, doc-confirmed).

Source: audit 2026-06-02 (M1/M13 doc-research confirmed via Context7).

## Recommended Action

1. M6: add `@ratelimit` to `firebase_token_exchange` + a `freeze_time` 429 test.
2. M3/M4: wrap both `create()` bodies in `transaction.atomic()`.
3. M1: add `ACTIVITY_TYPE_CHOICES` to `CareLog.activity_type`, makemigrations,
   verify the serializer key now appears + schema emits an enum.
4. M7: cache `forum_stats` in Redis with an explicit TTL + `[CACHE]` logging.
5. M13: set `acks_late=True` + `task_reject_on_worker_lost=True`.

## Acceptance Criteria

- [ ] `firebase_token_exchange` returns 429 past the rate threshold (test).
- [ ] Forum topic/post creation is atomic (partial-failure test, or code review).
- [ ] `activity_type_display` appears in CareLog API responses + OpenAPI enum.
- [ ] `forum_stats` served from Redis on the second hit (cache log/test).
- [ ] `run_identification` declares `acks_late=True`; suite green.

## Work Log

### 2026-06-02 - Deferred from full audit

- Filed from `docs/audits/2026-06-02-full.md` (M1, M3, M4, M6, M7, M13).
  Deferred per user triage (risk-sensitive / migration-bearing items).

## Notes

M6 is the highest-value item here (unthrottled auth surface) — do it first.
M1 requires a DB migration; rebuild the test DB with `--noinput`.
