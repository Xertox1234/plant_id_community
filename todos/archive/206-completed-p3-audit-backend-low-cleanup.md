---
status: completed
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

- [x] `requirements-dev.txt` PyJWT == `2.13.0`.
- [x] No raw email reaches logs on the invalid-email path; docstring no longer
      lists client identity params.
- [x] L4/L13 query counts reduced (pin with `assertNumQueries`).
- [x] L5/L6/L11/L12 resolved or explicitly accepted with rationale.

## Work Log

### 2026-06-02 - Deferred from full audit

- Filed from `docs/audits/2026-06-02-full.md` (L1, L4, L5, L6, L9–L13).

### 2026-06-05 - Started by completing-todos skill (run 2026-06-05-0228)

- Picked up by automated workflow. Scope: full finding set incl. M5-residual
  (in `source_finding`) and C3 (harvest-stats data bug).

### 2026-06-05 - Implemented + verified (run 2026-06-05-0228)

**Resolved (code change):**

- **L1** — `requirements-dev.txt:124` PyJWT `2.10.1` → `2.13.0` (matches prod).
- **L9** — `firebase_auth_views.py` invalid-email `ValueError` now wraps the value
  in `redact_email()`; the message is surfaced via `str(e)` into a warning log.
- **L10** — removed `email`/`display_name` from the `firebase_token_exchange`
  docstring request body; added a note that client identity fields are ignored
  (C8 vector).
- **L11** — added `except User.MultipleObjectsReturned` around the email-fallback
  `.get()`; a duplicate email now fails closed as a 409 (redacted log) instead of
  a 500.
- **L5** — `apps/core/exceptions.py::_retry_after_seconds` now parses the numeric
  multiplier (`5/15m` → 900) while preserving bare-unit windows (`30/m` → 60).
- **L4** — `CommunityEventDetailSerializer.get_can_rsvp` iterates the prefetched
  `attendees` (mirrors `get_user_rsvp_status`) instead of `obj.attendees.get()`,
  removing the per-event query.
- **L12** — `forum_integration/serializers.py::_get_rich_post` now caches on the
  serializer instance (dict keyed by pk) instead of `obj._rich_post_cache` — the
  exact anti-pattern in `docs/LEARNINGS.md:220` / query-optimization Pattern 27.
- **L13** — `blog/api_views.py::plant_data_stats` collapses the four PlantSpecies
  counts into one conditional `aggregate()` (5 queries → 2).
- **C3** — `garden_calendar/api/views.py::statistics` derives unit keys from
  `Harvest.HARVEST_UNITS` so `lb`/`bunch` (and `kg`/`g`/`basket`) are no longer
  dropped by the drifted `["lbs", ..., "bunches"]` literal.
- **M5-residual** — `users/oauth_views.py` swapped `django_ratelimit.decorators.
  ratelimit` → `apps.core.ratelimit.ratelimit` (drop-in wrapper) so the `10/m`
  OAuth limits emit a correct `Retry-After`. Cleaned the 14 pre-existing F401
  unused imports the flake8 gate flagged (verified each is unused + not re-exported
  before removing; auth module, no side-effect imports).

**Accepted with rationale:**

- **L6** — forum `TopicDetailView` pagination shape kept as-is. Switching to the
  DRF-standard `{count,next,previous,results}` shape is a breaking API-contract
  change (drops `current_page`/`total_pages` the web client consumes, and would
  need absolute next/previous URLs). The current richer shape is functional; not
  worth the client breakage for a p3 cosmetic divergence.

**Verification (commands run, `backend/venv`):**

- `flake8 --max-line-length=120 --extend-ignore=E203,W503` on all 10 touched
  files → exit 0 (incl. `oauth_views.py`, previously 14 F401).
- `pre-commit run isort/black/flake8 --files <touched>` → isort Passed, black
  reformatted 2 files (cosmetic), flake8 Passed.
- AC1: `grep PyJWT requirements-dev.txt` → `PyJWT==2.13.0`.
- AC2: docstring no longer lists `email`/`display_name`; `grep "Invalid Firebase
  email"` → `redact_email(firebase_email)`.
- AC3: `test_audit_aggregates.CommunityEventDetailRSVPQueryTest` pins the detail
  request at `assertNumQueries(3)` (L4 — `.get()` revert → 4 trips it);
  `test_plant_data_stats.PlantDataStatsQueryTest` pins `assertNumQueries(7)` (L13).
- AC4: `test_retry_after` (L5, 3 tests OK); L11/L12 covered by the suites below.
- C3: `test_statistics_includes_lb_unit` asserts an `lb` harvest now appears.
- Suites green: `apps.users` (113 w/ the new modules), `test_audit_aggregates`,
  `test_plant_data_stats`, `test_retry_after`, `users.test_rate_limiting`,
  `forum_integration.test_security`, `forum_integration.test_plant_mention_
  serialization`, `users.test_firebase_auth` → all OK.

**Note on pre-existing issues left untouched (out of scope):** the event detail
view has an `attendees__user` N+1 (prefetch is `attendees`, not `attendees__user`)
— unrelated to L4; not fixed (kept surgical). The L4 test fixes attendee count at
1 to stay deterministic.

### 2026-06-05 - Code review (code-review-orchestrator)

- Routed to django-drf / security / api-design / performance / test-quality
  reviewers. **0 findings at any severity; blocking: false.** Reviewer empirically
  confirmed: all 14 oauth F401 removals safe (no side-effect/re-exported import),
  ratelimit wrapper is a true drop-in, firebase `MultipleObjectsReturned`→409 +
  email redaction correct, and L13's `~Q(primary_image="")` ≡
  `exclude(primary_image="")` even though `primary_image` is `null=True`.
- **Known issue (non-blocking, out of scope):** `garden_calendar/api/views.py:253`
  has a separate `event.attendees.get(user=request.user)` in the RSVP *action*
  (the L4 finding scoped only the serializer `can_rsvp`). Same anti-pattern,
  different code path — candidate for a future cleanup; not touched here to stay
  surgical.

### 2026-06-05 - Completed by completing-todos skill (run 2026-06-05-0228)

- Verification: all 4 acceptance criteria passed with quoted command output
  (PyJWT pin, redaction+docstring, L4/L13 assertNumQueries, L5/L6/L11/L12). Full
  finding set resolved (L1, L4, L5, L9, L10, L11, L12, L13, C3, M5-residual);
  L6 explicitly accepted with rationale.
- Review: 0 findings, 0 blocking — no repair needed; 1 non-blocking out-of-scope
  observation recorded under Known issues.

## Notes

p3 — none are exploitable or user-facing today. L9/L10 (PII discipline) are the
most worth doing despite low severity.
