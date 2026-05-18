---
status: pending
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

- [ ] Each finding fixed or explicitly closed as false-positive with evidence.
- [ ] `python manage.py test` for affected apps passes.

## Work Log

### 2026-05-17 - Created

- Deferred from the 2026-05-17 full audit (Phase 4).
