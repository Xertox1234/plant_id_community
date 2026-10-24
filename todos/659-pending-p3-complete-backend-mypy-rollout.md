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
