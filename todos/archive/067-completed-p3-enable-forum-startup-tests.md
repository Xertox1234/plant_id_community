---
status: completed
priority: p3
issue_id: "067"
tags: [testing, forum, settings]
dependencies: ["065"]
---

# Add startup-verification tests for ENABLE_FORUM=True/False paths

## Problem

PR #261 made `INSTALLED_APPS`, context processors, and template dirs conditional on
`ENABLE_FORUM`. There are no automated tests verifying that either configuration
starts cleanly. A future change to settings.py could silently break one path and
it would only surface as a runtime crash.

## Findings

- PR #261 (todo 065 implementation) modified `settings.py` to gate `MACHINA_APPS`,
  Machina context processors, and template dirs behind `ENABLE_FORUM`.
- Surfaced during `/review` of PR #261 (2026-05-09).
- `backend/apps/forum_integration/tests/` exists but has no test covering Django
  system checks for either `ENABLE_FORUM` value.

## Recommended Action

1. Add a test module `backend/apps/forum_integration/tests/test_settings.py` (or
   `test_startup.py`) that:

   a. **ENABLE_FORUM=False path** — assert `apps.forum` is in `settings.INSTALLED_APPS`
      and `machina.apps.forum` is NOT:

      ```python
      from django.test import TestCase, override_settings
      from django.apps import apps

      class EnableForumFalseTest(TestCase):
          def test_headless_forum_app_loaded(self):
              self.assertIn('forum', [a.label for a in apps.get_app_configs()])
              self.assertNotIn(
                  'machina.apps.forum',
                  [a.name for a in apps.get_app_configs()],
              )
      ```

   b. **ENABLE_FORUM=True path** — use `@override_settings` to swap INSTALLED_APPS
      and verify `apps.forum_integration` is present and `apps.forum` is absent.
      Note: `override_settings` does not re-run app registry — test should verify
      `INSTALLED_APPS` list contents rather than the live app registry.

      ```python
      @override_settings(ENABLE_FORUM=True)
      def test_enable_forum_flag_gates_machina_apps(self):
          # Check the constructed list, not the live registry
          from django.conf import settings
          self.assertIn('apps.forum_integration', settings.INSTALLED_APPS)
          self.assertNotIn('apps.forum', settings.INSTALLED_APPS)
      ```

   c. Run `python manage.py check --deploy` (or `check`) under each config and
      assert exit code 0.

2. Run with `--keepdb` to avoid full DB rebuild.

## Technical Details

- File to create: `backend/apps/forum_integration/tests/test_settings.py`
- Pattern doc: `backend/docs/patterns/domain/forum.md`
- Note: `override_settings` does not reload the app registry mid-test; for the
  `ENABLE_FORUM=True` branch, assert against the `INSTALLED_APPS` list (constructed
  at import time) rather than the live `apps.get_app_configs()` registry.
- If a full registry-reload test is needed, use a subprocess call to
  `python manage.py check` with `ENABLE_FORUM=True` in the environment.

## Acceptance Criteria

- [x] `python manage.py test apps.forum_integration.tests.test_settings --keepdb`
      passes with zero errors.
- [x] The test asserts `apps.forum` IN INSTALLED_APPS when ENABLE_FORUM=False.
- [x] The test asserts `apps.forum_integration` IN INSTALLED_APPS when ENABLE_FORUM=True
      and `apps.forum` NOT in INSTALLED_APPS.
- [x] No database mocks used (real PostgreSQL test DB per project convention).

## Work Log

### 2026-05-09 - Created from PR #261 review

- Gap identified: PR #261 added conditional INSTALLED_APPS logic with no test coverage.
- Reviewer note: "A simple TestCase with call_command('check') would suffice, or even
  just a note in the todo acceptance criteria that manual verification was done."

### 2026-05-09 - Started by completing-todos skill (run 2026-05-09-1324)

- Picked up by automated workflow.
- Approach: SimpleTestCase with subprocess calls for both ENABLE_FORUM paths — environment-independent, tests both configurations on every run.
- Verification output: `Ran 8 tests in 3.827s OK` — all 4 acceptance criteria passed.
  - `ForumStartupCheckTest` (2 tests): manage.py check exits 0 for both ENABLE_FORUM values.
  - `EnableForumFalseInstalledAppsTest` (3 tests): apps.forum in, forum_integration absent, machina absent.
  - `EnableForumTrueInstalledAppsTest` (3 tests): forum_integration in, apps.forum absent, machina present.

### 2026-05-09 - Completed by completing-todos skill (run 2026-05-09-1324)

- Verification: all 8 acceptance criteria passed (`Ran 8 tests in 3.561s OK` after repair).
- Review: 7 findings total — 0 critical/high, 2 medium, 2 low, 2 info. Medium findings repaired (added subprocess timeout=60, pinned DJANGO_SETTINGS_MODULE in env dict).
- Known issues: low findings noted but not blocking.
  - `manage.py check` has implicit DB dependency (consistent with real-Postgres convention).
  - Mirror-image test classes — acceptable for clarity.
  - Four subprocess spawns add ~3.5s to suite (acceptable at current scale).
