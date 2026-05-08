---
status: pending
priority: p3
issue_id: "065"
tags: [testing, forum, machina]
dependencies: []
---

# Fix Machina test environment so forum_integration tests can run

## Problem

All tests under `backend/apps/forum_integration/tests/` fail at import with:

```text
machina.core.loading.AppNotFoundError: No app found matching 'forum_conversation.managers'
```

This means the forum_integration test suite is entirely unexecutable in CI and locally.
The only test covering `PostSerializer` (`test_plant_mention_serialization.py`) cannot
run, leaving the serializer unprotected by automated tests.

## Findings

- Reproduced locally: `python manage.py test apps.forum_integration --keepdb` raises
  `AppNotFoundError` before any test runs.
- Root cause: Machina uses a dynamic class-loading system (`machina.core.loading`) that
  requires its full set of forum apps to be present in `INSTALLED_APPS`. The test runner
  discovers `apps.forum_integration` in isolation without the full Machina app tree.
- `test_plant_mention_serialization.py` imports
  `from machina.apps.forum_conversation.models import Topic, Post` directly, which
  triggers Machina's app registry before Django's app registry is fully configured for
  Machina's overridden apps.
- Surfaced during todo 064 (PostSerializer rich_content fix) — the sole related test
  could not be executed to verify the fix.

## Recommended Action

1. Check `INSTALLED_APPS` in `plant_community_backend/settings.py` — confirm all
   required Machina apps are present (see Machina docs for the full list).
2. Check if a test-specific settings file (`settings_test.py`) or pytest fixture is
   needed to pre-configure Machina's app registry before test discovery.
3. Try running with the full test label path:
   `python manage.py test apps.forum_integration.tests.test_plant_mention_serialization`
   and capture the exact traceback to identify the missing app.
4. If the issue is a missing Machina app in `INSTALLED_APPS`, add it. If it's a test
   isolation issue, add a `conftest.py` or `setUp` that ensures Machina's app registry
   is initialised before imports.
5. Once fixed, run the full forum_integration test suite to confirm all tests pass.

## Technical Details

- Test file: `backend/apps/forum_integration/tests/test_plant_mention_serialization.py`
- Settings: `backend/plant_community_backend/settings.py`
- Machina loading: `machina/core/loading.py` — `get_class` / `get_classes`
- Pattern: `backend/docs/patterns/domain/forum.md`

## Acceptance Criteria

- [ ] `python manage.py test apps.forum_integration --keepdb` runs without
      `AppNotFoundError` at import time.
- [ ] `test_plant_mention_serialization.py` executes and all tests pass.
- [ ] No other test suite is broken by the fix.

## Work Log

### 2026-05-08 - Created as follow-up from PR #259 code review

- Surfaced by todo 064: PostSerializer fix could not be verified because the only
  related test fails at import due to Machina's app loading requirements.
