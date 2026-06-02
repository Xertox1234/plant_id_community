---
status: pending
priority: p3
issue_id: "206"
tags: [backend, drf, performance, security, firebase, audit]
dependencies: []
source_review: "docs/audits/2026-06-02-full.md"
source_finding: "L1, L4, L5, L6, L9, L10, L11, L12, L13, M5-residual"
---

# Backend low-severity cleanup (audit 2026-06-02)

## Problem

Nine low-severity backend findings from the full audit — minor perf, API
consistency, PII-log, and dependency-hygiene items. None is user-facing or
exploitable today; batched for a low-priority sweep.

## Findings

- **L1 — PyJWT dev-pin drift.** `backend/requirements-dev.txt:124` pins
  `2.10.1` while prod is `2.13.0`; CI `pip-audit` only scans `requirements.txt`,
  so the drift is un-gated. Bump dev to `2.13.0`.
- **L9 — raw email in log.** `apps/users/firebase_auth_views.py:276` raises
  `ValueError(f"...{firebase_email}")` → logged unredacted at `:233`. Redact via
  `redact_email()` like every other auth log site.
- **L10 — stale docstring re-advertises client identity fields.**
  `apps/users/firebase_auth_views.py:99-104` still documents `email`/
  `display_name` request params (the C8 vuln vector). Code ignores them — remove
  from the docstring to prevent re-wiring.
- **L11 — `email` not DB-unique.** `apps/users/firebase_auth_views.py:294`
  `User.objects.get(email=...)` catches only `DoesNotExist`; a duplicate email
  would raise `MultipleObjectsReturned` → 500. App-layer reg uniqueness
  mitigates. Either add `unique=True` (migration) or catch the exception.
- **L4 — `get_can_rsvp` bypasses prefetch.**
  `apps/garden_calendar/api/serializers.py:178` — detail serializer, +1 query.
- **L5 — `_retry_after_seconds` window parsing.** `apps/core/exceptions.py:37-46`
  only handles `/Nm` `/Ns`; `"5/15m"` → 3600 fallback. Latent (no such window in
  use). Parse the numeric multiplier.
- **L6 — forum `TopicDetailView` pagination shape diverges**
  (`apps/forum_integration/api_views.py:207-218`) from the DRF-standard shape.
- **L12 — model-instance cache attribute in serializer.**
  `apps/forum_integration/serializers.py:167-174` sets `obj._rich_post_cache`
  (the anti-pattern in `docs/LEARNINGS.md:222`). Latent. Convert to a
  serializer-keyed cache.
- **L13 — `plant_data_stats` uncached** (`apps/blog/api_views.py:306-332`), 5
  COUNTs, staff-only/low-traffic. Collapse to one `aggregate()`.
- **C3 (Phase-6 discovery) — harvest stats drop lb/bunch quantities.**
  `apps/garden_calendar/api/views.py` `statistics` aggregates per-unit on keys
  `"lbs"`/`"bunches"`, but the model's `HARVEST_UNITS` are `"lb"`/`"bunch"` — so
  harvests in those units never appear in `total_quantity_by_unit`. Pre-existing
  data bug (the M10 refactor preserved it). Fix the keys to match the constants
  (or map), and extend `test_audit_aggregates.py` to assert an `lb` harvest shows up.
- **M5-residual — `oauth_views.py` Retry-After.** `apps/users/oauth_views.py:25`
  still imports raw `django_ratelimit.decorators.ratelimit` (the M5 fix landed in
  `plant_identification/views.py` but this file was deferred). Swap to
  `apps.core.ratelimit.ratelimit` so the `10/m` OAuth limits emit `Retry-After:
  60`. **Blocked by:** the file carries 14 pre-existing F401 unused imports that
  the pre-commit flake8 gate flags on any touch — clean those by hand first
  (auth module, verify no import side-effects), then swap the import.

Source: audit 2026-06-02.

## Recommended Action

Address opportunistically. Quick wins first: L1 (one-line bump), L9/L10
(PII/docstring), L13/L4/L6 (perf/consistency). L11/L5/L12 need slightly more care
(migration / parser / cache refactor).

## Acceptance Criteria

- [ ] `requirements-dev.txt` PyJWT == `2.13.0`.
- [ ] No raw email reaches logs on the invalid-email path; docstring no longer
      lists client identity params.
- [ ] L4/L13 query counts reduced (pin with `assertNumQueries`).
- [ ] L5/L6/L11/L12 resolved or explicitly accepted with rationale.

## Work Log

### 2026-06-02 - Deferred from full audit

- Filed from `docs/audits/2026-06-02-full.md` (L1, L4, L5, L6, L9–L13).

## Notes

p3 — none are exploitable or user-facing today. L9/L10 (PII discipline) are the
most worth doing despite low severity.
