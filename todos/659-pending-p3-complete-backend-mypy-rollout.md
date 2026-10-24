---
status: pending
priority: p3
issue_id: "659"
tags: [backend, ci, typing, code-quality]
dependencies: []
---

# Complete backend mypy enforcement for the four remaining areas

## Problem

The recent lint, type-check and staged-test upgrades catch more mistakes before
commit, but Python type enforcement covers only part of the backend. Type errors
in the forum package, core, garden calendar and plant identification still produce
advisory output at commit time and do not block CI. Finish the rollout so new
source errors in these areas cannot silently land.

## Findings

- Discovery: owner-requested status check on 2026-10-22, followed by an explicit
  request to create a todo for the remaining work.
- `backend/pyproject.toml` `[tool.mypy] files` currently gates `apps/users`,
  `apps/forum_host`, `apps/blog` and `plant_community_backend`.
- `backend/CLAUDE.md` records these remaining source-error counts, measured
  **2026-10-19**, with tests excluded: `wagtail_forum` 65, `apps/core` 79,
  `apps/garden_calendar` 102 and `apps/plant_identification` 150 (396 total).
  These are historical estimates; remeasure before implementation.
- `scripts/mypy_staged.py` reads the same gated-path list as CI and treats
  errors outside it as advisory. `.github/workflows/backend-ci.yml` runs a bare
  `python -m mypy`; expanding that shared list enables both gates.
- The owner deliberately excluded tests from mypy enforcement on 2026-10-19.
  `backend/pyproject.toml` documents adding `wagtail_forum.tests.*` to the test
  override when the package is gated.
- An existing blanket `ignore_errors` override for
  `apps.plant_identification.models` must be reassessed as part of that app's
  rollout, rather than leaving its production models silently unchecked.
- Local verification on 2026-10-22: the existing mypy gate passed on 292 source
  files; the Ruff pre-commit gate and web TypeScript check also passed.
- Related completed work: todo 580 introduced the users gate; todo 599 added its
  planted-error self-test. PRs #1167, #1169 and #1171 widened coverage to the
  backend configuration, forum host and blog respectively.

## Recommended Action

1. Remeasure each remaining area's source errors with the existing pinned mypy
   and django-stubs configuration, preserving the deliberate test exclusions.
2. Work through the four areas in manageable changes, preferably smallest first.
   Fix incorrect types and actual bugs; keep type-only changes behavior-preserving
   and add focused regression tests for any behavior fixes.
3. Add each cleaned area to `[tool.mypy] files`. Use the forum package's actual
   importable source root, `packages/wagtail_forum/wagtail_forum`, and verify its
   module naming with the Django plugin. Add its test-only override.
4. Remove the production-model blanket suppression. Resolve remaining legitimate
   library typing limitations with narrow, explained error-code suppressions,
   rather than broad ignores, disabling rules or replacing useful types with Any.
5. Extend the existing gate self-test to prove enforcement in each newly covered
   area. Verify the staged hook independently with temporary deliberate errors.
6. Update the backend CI documentation and workflow comments to describe the
   completed coverage and intentional exclusions.

## Technical Details

- Configuration: `backend/pyproject.toml`.
- Commit gate: `.pre-commit-config.yaml`, `scripts/mypy_staged.py`.
- CI and self-test: `.github/workflows/backend-ci.yml`,
  `backend/bin/test-mypy-gate.sh`.
- Documentation: `backend/CLAUDE.md`, `docs/PRE_COMMIT_SETUP.md`.
- Implementation references: `backend/docs/patterns/README.md` and the relevant
  service, ViewSet, plant-identification and forum pattern documents.
- Test exclusion is intentional; running tests and type-checking their source
  are separate concerns. Keep the existing runtime test gates.

## Acceptance Criteria

- [ ] All four remaining source roots are in `[tool.mypy] files`, and a bare
      `python -m mypy` from `backend/` passes with the CI configuration.
- [ ] The `apps.plant_identification.models` blanket suppression is removed.
      No new production-module blanket ignores or weaker global rules are added;
      any new inline suppressions name an error code and explain the limitation.
- [ ] Automated gate self-tests plant a source type error in each newly gated
      area and prove that the CI command reports it and exits nonzero. Temporary
      probes are cleaned up, and the clean gate passes afterward.
- [ ] The actual `mypy-staged` pre-commit hook fails for a deliberately introduced
      source type error in each newly gated area. Record the commands and results.
- [ ] Existing app-test exclusions remain effective, and forum tests are excluded
      via their module override. Planted-error checks demonstrate that exclusions
      hide test errors without hiding adjacent production-source errors.
- [ ] Ruff, Black and isort checks and the affected backend runtime tests pass.
      Every behavior fix discovered during cleanup has a focused regression test.
- [ ] Backend CI documentation and workflow comments reflect the final coverage;
      the Work Log records verification results and any intentional limitations.

## Work Log

### 2026-10-22 - Filed

- Created at the owner's request after confirming that the checking infrastructure
  is installed but the four remaining backend areas have no open rollout todo.
- Scoped to completing source type enforcement, preserving the owner's decision
  to exclude tests from mypy. The 396-error estimate is from 2026-10-19 and has
  not been remeasured for this filing.

### 2026-10-24 - Area 1 of 4: wagtail_forum gated (PR #1182, merged)

- Owner chose to continue, smallest area first. Remeasured with the CI env:
  65 source errors (31 more in tests), unchanged since 2026-10-19.
- `packages/wagtail_forum/wagtail_forum` added to `[tool.mypy] files`; its tests
  are excluded by `wagtail_forum.tests.*` in the same override as
  `apps.*.tests.*`. No "unused section" note, so the module naming matches.
- All 65 fixed with annotations, Optional narrowing, a locals refactor of the
  `sanitize` segment parser and `functools.partial` for the late-log callbacks.
  Every runtime-touching edit is behavior-equivalent, so no regression tests
  were needed; no real bugs found in this area.
- Narrow, explained ignores only: drf-spectacular optional-import stand-ins,
  mixin `super()` calls, the taggit `tags` prefetch, Wagtail's runtime
  `snippet_viewset`, and the package's `AbstractBaseUser` hints vs the
  host-resolved user FK. `--warn-unused-ignores` clean.
- Limitation found: gating a package that gated code imports types its call
  sites (follow_imports=silent had treated the editable install as untyped).
  4 errors surfaced and were fixed in `apps/forum_host`. Expect the same, larger,
  for `apps/core`; always run the bare gate, not the path.
- Verification: bare `python -m mypy` Success on 503 files (also with a fresh
  cache); `bin/test-mypy-gate.sh` now plants forum source + tests canaries and
  passes, and fails for both negative controls (override renamed; path dropped
  from `files`); `pre-commit run mypy-staged` Failed on a planted forum source
  error, body exit 0 on a planted forum test error, Passed on clean files;
  ruff/black/isort Passed; `pytest packages/wagtail_forum apps/forum_host`
  2195 passed; CI on #1182 all green.
- Remaining: `apps/core` 79, `apps/garden_calendar` 102,
  `apps/plant_identification` 150 (331, measured 2026-10-19), plus the
  `apps.plant_identification.models` blanket suppression.

### 2026-10-24 - Area 2 of 4: apps/garden_calendar gated (PR #1184, merged)

- Remeasured with the CI env: 102 source errors, unchanged since 2026-10-19.
  `apps/garden_calendar` added to `[tool.mypy] files`; no errors rippled into
  already-gated apps (bare gate Success on 548 files).
- Real bug found: three signal receivers (`notify_community_event_created`,
  `notify_event_rsvp_updated`, `notify_weather_alert_created`) called
  `NotificationService.send_email_notification` / `send_push_notification`,
  which never existed. `except Exception` swallowed the AttributeError, so
  nothing had been sent since 2025-10-22; their templates never existed and no
  web or mobile client uses those endpoints. Owner chose to remove them (not
  repair); the module docstring records why, and the test class that pinned
  the swallowed-failure logging went with them.
- The rest were annotations and narrowing: `@admin.display` for 15 attribute
  assignments, `bool()` around permission and serializer comparisons,
  TYPE_CHECKING `User` imports in the services, `garden_bed is None` checks,
  an `isinstance(field, models.ForeignKey)` cache loop, and `# type: ignore[misc]`
  on the audit-actor mixin `super()` calls. One small behavior change: an
  image upload PIL reads with no format now gets a 400 instead of a 500
  (`(img.format or "").lower()`).
- `bin/test-mypy-gate.sh` gained a `garden=apps/garden_calendar` canary pair;
  its "others" count now loops over every canary, so the next area only adds a
  pair.
- Verification: bare gate Success; self-test passes and fails for both
  negative controls (path dropped from `files`; an extra planted error);
  `mypy-staged` blocks a planted source error, skips a planted test file;
  ruff/black/isort Passed; pytest garden_calendar + core + users 2842 passed,
  1 skipped; CI on #1184 all green.
- kimi-review WARNINGs declined: two "lazy-load" warnings on the
  `garden_bed is None` checks are false (a null FK returns None without a
  query, and the old code already loaded the bed for the message); the
  `interval == 0` path in `_create_next_occurrence` is unreachable because the
  caller returns first for a non-recurring task; the remaining no-op
  `cleanup_orphaned_forum_topics` receiver needs no test.
- Remaining: `apps/core` 79, `apps/plant_identification` 150 (229), plus the
  `apps.plant_identification.models` blanket suppression.

### 2026-10-24 - Area 3 of 4: apps/core gated (PR #1186, merged)

- Remeasured with the CI env: 79 source errors, unchanged since 2026-10-19.
  `apps/core` added to `[tool.mypy] files`; bare gate Success on 640 files,
  also with `--warn-unused-ignores`.
- Zero ripple, correcting the area 1 prediction: core is first-party, so mypy
  already followed and typed it for gated callers. Only an editable install
  treated as untyped (wagtail_forum) ripples. `backend/CLAUDE.md` says so.
- Fixes: the todo 580 TYPE_CHECKING `User` pattern in `security.py`,
  `email_service.py` and `notification_service.py` (runtime still resolves
  `get_user_model()`); `Optional[...]` for None defaults; annotated locals where
  an untyped call returned Any; `callable` -> `Callable[...]`;
  `timezone.datetime` -> `datetime`. No real bugs found in this area.
- Todo 623 alert paths keep the exception unbound so no frame local reaches
  Sentry: `sys.exc_info()[0].__name__` became
  `getattr(sys.exc_info()[0], "__name__", "unknown")` in `delivery.py` and
  `notification_ops.py`. #1184 had bound the exception in
  `garden_calendar/tasks.py` `_log_care_outcomes`; the unbound form was
  restored there.
- Narrow, explained ignores: `mail.mailers` in `checks.py` and
  `django70_compat.py` (django-stubs 6.0.3 predates Django 6.1's MAILERS), the
  mixin `super().send_messages` in `mail_backends.py`, and RunSQL's invariant
  list parameter in migration 0003 (SQL unchanged).
- Verification: self-test gained a `core=apps/core` canary pair, passes, and
  fails for both negative controls (path dropped from `files`; an extra planted
  error in `fcm.py`); `mypy-staged` blocks a planted core source error, skips a
  planted test file; `makemigrations --check` clean; ruff/black/isort Passed;
  full pytest 5689 passed, 8 skipped; CI on #1186 all green.
- kimi-review WARNING declined: "canary files not in diff" — the self-test
  plants them at run time and deletes them on exit.
- Remaining: `apps/plant_identification` 150, plus the
  `apps.plant_identification.models` blanket suppression.
