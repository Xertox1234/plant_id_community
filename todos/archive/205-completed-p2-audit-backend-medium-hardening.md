---
status: completed
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

- [x] `firebase_token_exchange` returns 429 past the rate threshold (test).
- [x] Forum topic/post creation is atomic (partial-failure test, or code review).
- [x] `activity_type_display` appears in CareLog API responses + OpenAPI enum.
- [x] `forum_stats` served from Redis on the second hit (cache log/test).
- [x] `run_identification` declares `acks_late=True`; suite green.

## Work Log

### 2026-06-02 - Deferred from full audit

- Filed from `docs/audits/2026-06-02-full.md` (M1, M3, M4, M6, M7, M13).
  Deferred per user triage (risk-sensitive / migration-bearing items).

### 2026-06-02 - Started by completing-todos skill (run 2026-06-02-2322)

- Picked up by automated workflow. Implementation order (trivial→risky, per
  advisor): M13 → M3/M4 → M7 → M6 → M1 (M1 last; carries the DB migration).

### 2026-06-02 - Implemented + verified (run 2026-06-02-2322)

**M13** — `apps/plant_identification/tasks.py`: added `acks_late=True` +
`reject_on_worker_lost=True` to `run_identification`. Note: the todo said
`task_reject_on_worker_lost` but that is the *global config* setting; the
per-task decorator option is `reject_on_worker_lost` (Context7 Celery docs).
Durability scope: the service commits `status="processing"` *before* the 120s
external I/O (`identification_service.py:76`), so `acks_late` protects the
queued→processing window; once processing starts, the idempotency guard
short-circuits any redelivery (no dup work, but a mid-processing crash leaves the
request stuck — a stuck-request reaper would be a separate follow-up).

**M3/M4** — `apps/forum_integration/serializers.py`: wrapped both
`CreateTopicSerializer.create` and `CreatePostSerializer.create` write blocks in
`with transaction.atomic():` (added `from django.db import transaction`).

**M7** — `apps/forum_integration/api_views.py` + `constants.py`: cache
`forum_stats` under `FORUM_STATS_CACHE_KEY` / `FORUM_STATS_CACHE_TTL` (60s) with
`[CACHE] HIT/MISS` logging. NB: the todo referenced the "already-fixed blog_stats
pattern" but `blog_stats` is in fact uncached — mirrored the project's
`django.core.cache` convention instead.

**M6** — `apps/users/firebase_auth_views.py`: `@ratelimit(key="ip",
rate=RATE_LIMITS["auth_endpoints"]["firebase_token_exchange"]="10/m", ...)` via
`apps.core.ratelimit` (rate-preserving wrapper → correct `Retry-After`).

**M1** — `apps/garden_calendar/{constants,models}.py` + migration
`0006_carelog_activity_type_choices.py`: added `ACTIVITY_TYPE_CHOICES`
(superset of all client-sent values + `other`) to `CareLog.activity_type`. The
auto-generated migration bundled unrelated `plantimage.uuid` drift — hand-wrote a
carelog-only migration instead (state-only; `choices` is no DB constraint).

Verification (all `--noinput` fresh DB where migration-affected):
```text
apps.users.tests.test_firebase_auth ............ Ran 22 tests OK
apps.users.tests.test_rate_limiting ............ Ran 9 tests OK
apps.forum_integration ......................... Ran 71 tests OK (skipped=3)
apps.garden_calendar ........................... Ran 155 tests OK (skipped=1)
apps.plant_identification ...................... Ran 110 tests OK
manage.py spectacular .......................... ActivityTypeEnum emitted;
                                                 activity_type_display in schema
manage.py check ................................ no issues (0 silenced)
flake8 (changed files) ......................... CLEAN
```
New tests: M6 429+Retry-After("60")+per-IP, M7 `assertNumQueries(0)` 2nd hit,
M1 `activity_type_display == "Watering"`, M13 task flags. Also removed two
pre-existing unused imports in `test_viewsets.py` (flagged by pre-commit flake8
on the file I was already editing).

#### Code review — 0 critical / 0 high / 0 medium (clean)

`code-review-orchestrator` (django-drf, security, performance, celery-async,
api-design, test-quality lenses). It independently re-verified all five
hard-scrutiny items with evidence — notably confirming M1 has no backward-compat
break: mobile + web never write `activity_type`, and the only out-of-enum values
in the tree (`account_created`, `trust_level_upgrade`) belong to a *different*
model (`ActivityLog` in the `users` app), not `CareLog`.

Known issues (non-blocking, forward-looking — recorded, not actioned):
- **LOW** `firebase_auth_views.py` — `key="ip"` `10/m` can collectively throttle
  carrier-grade-NAT mobile users sharing one egress IP. Matches existing OAuth
  views (`oauth_views.py` also `10/m` per IP), so accepted.
- **INFO** `models.py` `CareLog.activity_type` — now that `choices` constrains
  *writes*, a future client sending an out-of-enum value (e.g. `water`) gets a
  400; client vocab and the enum must stay in sync.

### 2026-06-02 - Completed by completing-todos skill (run 2026-06-02-2322)

- Verification: all 5 acceptance criteria passed (4 affected suites green:
  users 22+9, forum 71, garden 155, plant_id 110; OpenAPI enum + system check +
  flake8 clean).
- Review: 0 critical / 0 high / 0 medium; 2 LOW/INFO recorded above (accepted).

## Notes

M6 is the highest-value item here (unthrottled auth surface) — do it first.
M1 requires a DB migration; rebuild the test DB with `--noinput`.
