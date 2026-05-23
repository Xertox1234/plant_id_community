---
status: completed
priority: p2
issue_id: "081"
tags: [backend, api, wagtail, celery, audit-2026-05-17]
dependencies: []
source_review: "docs/audits/2026-05-17-full.md"
source_finding: "H12,H13,H16,H17,H18,H19,H28,H29"
---

# Backend High-severity audit findings (api / drf / wagtail / celery)

## Problem

Eight High-severity backend findings from the 2026-05-17 full audit, deferred at
triage (fix scope was Critical + security + N+1). Full detail per finding is in
`docs/audits/2026-05-17-full.md`.

## Findings

- **H12** — Rate-limited function-based views raise `Ratelimited` → HTTP 403 (no
  DRF handler) instead of 429 + `Retry-After`. `apps/users/views.py`,
  `apps/plant_identification/views.py`.
- **H13** — Three incompatible error-response shapes across active code
  (`apps/core/exceptions.py`, `apps/users/views.py`, inline returns).
- **H16** — TOCTOU race in `PlantViewSet.upload_image` image-count check, no lock.
  `apps/garden_calendar/api/views.py:917`.
- **H17** — Wagtail AI cache hit bypasses rate limiting — cached prompt replayable
  past quota. `apps/blog/wagtail_ai_v3_integration.py:184`.
- **H18** — `AIRateLimiter.check_and_increment()` does not exist — latent
  `AttributeError`. `apps/blog/wagtail_ai_v3_integration.py:211`.
- **H19** — `@receiver(post_delete)` registered with no `sender` — fires on every
  model delete project-wide. `apps/blog/signals.py:105`.
- **H28** — Celery task enqueued without `transaction.on_commit` — worker can race
  the creating transaction. `apps/plant_identification/views.py:162`.
- **H29** — Celery `autoretry_for` and explicit `self.retry()` both fire for
  `RateLimitExceeded`. `apps/plant_identification/tasks.py:80`. NOTE: audit C2
  scoped `autoretry_for` to specific exceptions excluding `RateLimitExceeded`, so
  this may already be resolved — verify before working it.

## Recommended Action

Triage each against `docs/audits/2026-05-17-full.md` and the pattern docs
(`backend/docs/patterns/architecture/rate-limiting.md`, `domain/celery.md`,
`domain/blog.md`, `domain/wagtail.md`). H16 mirrors the fix already applied in
`apps/forum/viewsets/post_viewset.py` (`select_for_update()`).

## Acceptance Criteria

- [x] Each finding fixed or explicitly closed as false-positive with evidence.
- [x] `python manage.py test` for affected apps passes.

## Work Log

### 2026-05-17 - Created

- Deferred from the 2026-05-17 full audit (Phase 4).

### 2026-05-21 - Started by completing-todos skill (run 2026-05-21-0238)

- Picked up by automated workflow.

### 2026-05-21 - Triage + fixes

Per-finding resolution (verified each against current code first):

- **H12 — false-positive (already resolved).** `REST_FRAMEWORK["EXCEPTION_HANDLER"]`
  = `apps.core.exceptions.custom_exception_handler` (settings.py:496), which converts
  `Ratelimited` → 429 + `Retry-After`. The cited function views use `@api_view`
  (outermost) over `@ratelimit`, so DRF's dispatch catches `Ratelimited` via the
  handler. Evidence: `apps/users/tests/test_rate_limiting.py` passes (users 96 OK).
- **H13 — fixed.** `create_error_response` (the divergent nested shape used only in
  `apps/users/views.py`) converged to the canonical flat shape emitted by
  `custom_exception_handler` (`{error, message, code, status_code, errors?}`). This
  also fixes a latent web bug: `authService.login` read flat `error.message` and so
  never displayed backend messages from the old nested shape. Updated 3 assertions in
  `test_account_lockout.py` (105/376/444) to the flat shape. Remaining inline
  `{"error": "string"}` returns are tracked separately as M12/M20 (backlog 085).
- **H16 — fixed.** `PlantViewSet.upload_image` now re-checks the image-count limit
  under `transaction.atomic()` + `Plant.objects.select_for_update()` (the top-of-method
  check stays as a fast pre-filter). `apps/forum/post_viewset.py` (the audit's cited
  reference) was deleted with the forum app, so the pattern was applied directly.
- **H17 — fixed.** `CachedLLMService.completion()` now enforces the per-user rate
  limit BEFORE the cache lookup, so a cached prompt can no longer be replayed past
  quota.
- **H18 — fixed.** Replaced the non-existent `AIRateLimiter.check_and_increment(...)`
  with the real `AIRateLimiter.check_user_limit(user_id, is_staff)`. (Full
  per-feature/tier limiter reconciliation remains M24, backlog.)
- **H19 — fixed.** `@receiver(post_delete)` scoped to `sender=BlogPostPage` (with a
  module-level import) so it no longer fires on every project-wide delete. Safe:
  `test_blog_signals.py` already dispatches `post_delete` with `sender=BlogPostPage`.
- **H28 — fixed.** Celery enqueue wrapped in `transaction.on_commit(...)` so the
  worker cannot fetch the request before its row commits.
- **H29 — false-positive (obsolete).** `autoretry_for` (tasks.py:22-26) excludes
  `RateLimitExceeded`, and the explicit `except RateLimitExceeded` block catches it
  before propagation — no double-retry. Resolved by audit C2.

Verification (`python manage.py test --keepdb`):

- `apps.users` — Ran 96 tests, **OK** (covers H12 rate-limit→429, H13 lockout shape).
- `apps.blog` — Ran 177 tests, **OK** (skipped=7) (covers H17/H18/H19).
- `apps.garden_calendar` — Ran 150 tests, **OK** (skipped=1) (covers H16).
- `apps.plant_identification` — Ran 108 tests, **OK** (covers H28).
- Fresh-DB re-run of `test_blog_signals + test_ai_rate_limiter + test_ai_integration`
  — Ran 47, **OK** (the `--keepdb` isolation failure of the signal tests was a shared
  test-DB artifact, not a regression).
- `python manage.py check` — 0 issues.

### 2026-05-21 - Code review + completion

- Code review (code-review-orchestrator workflow: django-drf, celery-async,
  wagtail, api-design, test-quality, performance, security checklists): **no
  critical/high findings**. One LOW (redundant function-local `BlogPostPage`
  import in `signals.py`, superseded by the new module-level import) — repaired
  (also fixed the now-stale "sender unreliable" docstring note); `test_blog_signals`
  re-run 13 OK.
- Known issues (non-blocking, INFO): H28's `on_commit` is currently preventive —
  `ATOMIC_REQUESTS` is unset and `perform_create` is not wrapped in `atomic()`, so
  the callback fires immediately today; it becomes load-bearing if either is added.
  H17 now counts cache hits against the per-user quota (intended).
- Manifest `docs/audits/2026-05-17-full.md` High table updated: H13/H16/H17/H18/
  H19/H28 → verified; H12/H29 → false-positive.

### 2026-05-21 - Completed by completing-todos skill (run 2026-05-21-0238)

- Verification: both acceptance criteria passed (6 findings fixed, 2 closed as
  false-positive; affected app suites green: users 96 / blog 177 / garden_calendar
  150 / plant_identification 108).
- Review: code-review-orchestrator workflow — 0 blocking findings; 1 LOW repaired,
  2 INFO recorded as known issues.
