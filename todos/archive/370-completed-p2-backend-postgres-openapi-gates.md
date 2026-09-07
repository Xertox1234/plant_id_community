---
status: completed
priority: p2
issue_id: "370"
tags: [backend, testing, postgres, pgvector, openapi, ci]
dependencies: []
---

# Restore PostgreSQL tests and OpenAPI validation gates

## Problem

The backend verification commands are not aligned with the supported production test environment. A local pytest run unexpectedly used SQLite and caused PostgreSQL/pgvector end-to-end tests to fail, while OpenAPI validation reports an invalid request-body schema and exits non-zero. These gates need to exercise PostgreSQL with pgvector and reject genuinely invalid API documentation without unrelated environment drift.

## Findings

- **SQLite was used by pytest:** `backend/plant_community_backend/settings.py:302-325` selects the SQLite default from `DATABASE_URL` unless the literal string `"test"` appears in `sys.argv`; pytest does not enter that branch. The file's own comment acknowledges that the PostgreSQL branch only fires for `manage.py test`. This was verified by the SQLite traceback during `pytest -q apps/forum_host`.
- **The supported CI environment is PostgreSQL + pgvector:** `.github/workflows/backend-ci.yml:117-126` provisions `pgvector/pgvector:pg16`, and `.github/workflows/backend-ci.yml:148-155` sets the PostgreSQL `DATABASE_URL` explicitly for pytest. Local verification should use the same contract rather than silently falling back to SQLite.
- **Seven forum-host failures were database-vendor failures:** the run collected 526 tests, passed 519, and failed 7 in `apps/forum_host/tests/test_rag_retrieval.py` and `apps/forum_host/tests/test_similar.py`. Those tests document that they build/search the real pgvector store (`test_similar.py:281-295`, `test_rag_retrieval.py:1-7`), and the observed error was `sqlite3.OperationalError: near ">": syntax error` from the pgvector query path.
- **OpenAPI validation fails on the notification mark-read request:** `backend/packages/wagtail_forum/wagtail_forum/api/notifications.py:113-120` passes a raw object schema directly as `extend_schema(request=...)`. Generated output places `type` and `properties` under `requestBody.content` as sibling media-type entries instead of producing one valid JSON schema. `manage.py spectacular --validate` reported `SchemaValidationError` for `{'ids': {'type': 'array', 'items': {'type': 'integer'}}}`.
- **The OpenAPI command currently used by CI does not validate the document:** `.github/workflows/backend-ci.yml:92-100` runs `manage.py spectacular --file /dev/null` without `--validate`. The command completes, but the explicit validation run reported 205 errors / 47 unique errors, so the current gate may not detect malformed generated output.
- **No fixes were made during the link-preview work:** these are separate verification/configuration issues and are being tracked here for deliberate investigation.

## Proposed Solutions

### Option 1: Align test settings and repair the schema contract

- **Implementation:** Make pytest's database selection explicitly PostgreSQL/pgvector in local and CI environments, add a non-secret runtime assertion that the test connection vendor is PostgreSQL, inventory/group all `spectacular --validate` errors, replace malformed raw request dictionaries with a valid serializer/OpenAPI request schema, and make the validation command an intentional gate.
- **Pros:** Local, CI, and production-like tests exercise the same database features; pgvector regressions become actionable; generated API documentation is standards-valid.
- **Cons:** Requires local PostgreSQL/pgvector setup or a documented container workflow, and the schema inventory may expose additional pre-existing contract gaps.
- **Effort:** 2–4 hours for investigation and first repair pass.
- **Risk:** Medium; changing test database selection can expose additional genuine PostgreSQL-only failures that SQLite had hidden.

## Recommended Action

1. Reproduce the test environment with a safe diagnostic that reports only `connection.vendor`, PostgreSQL server version, and whether the `vector` extension is installed; never print credentials or full database URLs.
2. Decide whether the supported local path should use `TEST_DB_*` settings, an explicit `DATABASE_URL`, or a local pgvector container, then make pytest use that path without relying on the fragile `"test" in sys.argv` check.
3. Add a regression test or test-start assertion proving `pytest` uses PostgreSQL and that the `vector` extension is available before pgvector end-to-end tests run.
4. Run the forum-host suite against PostgreSQL/pgvector and classify any remaining failures as real test/code defects rather than SQLite incompatibilities.
5. Run `python manage.py spectacular --file /tmp/schema.yml --validate`, collect every unique validation error by endpoint/component, and fix the `NotificationMarkReadView` request schema first.
6. Add an OpenAPI regression assertion for `POST /forum/notifications/mark-read/` proving `ids` is an array of integers in the JSON request schema.
7. Decide whether CI should add `--validate` to `.github/workflows/backend-ci.yml`; if it does, repair or explicitly document every remaining warning/error so the gate is intentional rather than merely non-crashing.

## Technical Details

- Database selection: `backend/plant_community_backend/settings.py:302-325`.
- CI database services and pytest environment: `.github/workflows/backend-ci.yml:117-155`, `.github/workflows/backend-ci.yml:193-200`.
- PostgreSQL/pgvector end-to-end tests: `backend/apps/forum_host/tests/test_similar.py:281-309` and `backend/apps/forum_host/tests/test_rag_retrieval.py`.
- Malformed request schema: `backend/packages/wagtail_forum/wagtail_forum/api/notifications.py:110-142`.
- Schema tests and API documentation patterns: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_schema.py`, `backend/docs/patterns/architecture/rate-limiting.md`, and `docs/rules/testing.md`.
- Verification commands:
  - `PYTHONPATH=backend/packages/wagtail_forum:backend python -m pytest -q apps/forum_host`
  - `python manage.py spectacular --file /tmp/schema.yml --validate`
  - `python manage.py check`

## Acceptance Criteria

- [x] A normal local pytest invocation uses PostgreSQL, not SQLite, and the selected database has the `vector` extension.
- [x] `pytest -q apps/forum_host` passes against the supported PostgreSQL/pgvector environment, or every remaining failure is separately tracked with a verified root cause.
- [x] `POST /forum/notifications/mark-read/` generates a valid OpenAPI JSON request schema with `ids` typed as an integer array.
- [x] `python manage.py spectacular --file /tmp/schema.yml --validate` exits 0, or all remaining validation findings are individually classified, documented, and intentionally excluded from the gate.
- [x] CI's database and OpenAPI commands reflect the supported environment and are covered by regression checks.

## Work Log

### 2026-09-05 - Filed during link-preview verification

- A broad `pytest -q apps/forum_host` run in the forum-editor worktree collected 526 tests: 519 passed and 7 failed in pgvector end-to-end tests with `sqlite3.OperationalError: near ">": syntax error`.
- `manage.py check` passed, but `manage.py spectacular --validate` failed on the malformed `ids` request schema and reported additional pre-existing schema findings.
- The link-preview feature was not changed to work around either failure; this todo records the separate investigation.

### 2026-09-06 - Started by completing-todos skill

- Picked up by the automated workflow after confirming the existing forum-editor worktree and preserving its unrelated uncommitted changes.

### 2026-09-06 - Root-cause and OpenAPI inventory

- The baseline `PYTHONPATH=backend/packages/wagtail_forum:backend python -m pytest -q apps/forum_host` run collected 535 tests: 528 passed and 7 failed. Every failure was one of the pgvector end-to-end tests and the traceback was SQLite's `near ">": syntax error`. The live local PostgreSQL service accepts connections, and the freshly created PostgreSQL test database has the `vector` extension.
- The first `spectacular --validate` run reported 205 errors / 47 unique errors and failed on `NotificationMarkReadView`'s raw object request schema. Replacing it with `NotificationMarkReadRequestSerializer` removed that structural failure and exposed the next raw object request in `BlogPostPageViewSet.add_comment`; that endpoint now uses `BlogCommentCreateSerializer`.
- The remaining 47 unique generation diagnostics are individually classified as non-structural drf-spectacular fallback diagnostics, not schema-validation failures: `csp_report_view`; users `get_csrf_token`, `register`, `login`, `logout`, `firebase_token_exchange`, `oauth_login`, `oauth_callback`, `current_user`, `update_profile`, `user_collections`, `user_collection_detail`, `previous_searches`, `search_detail`, `dashboard_stats`, `token_refresh`, `subscribe_push_notifications`, `unsubscribe_push_notifications`, `push_subscriptions`, `care_reminders`, `care_reminder_detail`, `care_reminder_action`, `care_reminder_stats`, `export_care_reminders_calendar`, `care_reminder_calendar_preview`, `onboarding_progress`, `create_demo_data`, `track_onboarding_event`, and `delete_demo_data`; plant-identification `identify_plant`, `simple_views.health_check`, `urls.health_check`, `service_status`, `get_care_instructions`, `regenerate_care_instructions`, `search_local_plants`, `search_local_diseases`, `enrich_plant_data`, `search_plant_species`, `get_plant_characteristics`, and `get_plant_growth_info`; blog `blog_stats` and `blog_search`; and forum `TopicSubscriptionView`, `TopicBookmarkView`, `UserBlockView`, and `UserMuteView`. They are intentionally excluded from `--fail-on-warn` because these APIViews have no serializer contract and drf-spectacular explicitly skips them with its graceful fallback message.
- The final command reports 183 warnings / 107 unique warnings, limited to pre-existing serializer type-hint, anonymous-queryset/path-parameter, enum-name, and operation-id diagnostics. CI now runs `spectacular --validate` (without `--fail-on-warn`) so malformed documents fail while these documented non-structural diagnostics remain non-blocking.

### 2026-09-06 - Verification

- PostgreSQL contract regression: `python -m pytest -q apps/forum_host/tests/test_database_contract.py --create-db` → `1 passed`; the test asserts `connection.vendor == "postgresql"` and `vector` is installed. The intentionally negative SQLite probe failed at settings import with `ImproperlyConfigured: Django test runs require PostgreSQL with the vector extension`, proving no silent fallback.
- Forum suite: `python -m pytest -q apps/forum_host` → `536 passed, 1 warning in 106.62s` against the local PostgreSQL/pgvector test database.
- Schema regression suite: `python -m pytest -q packages/wagtail_forum/wagtail_forum/tests/api/test_schema.py --create-db` → `11 passed, 1 warning`; this includes the notification `ids` integer-array assertion and the blog comment request assertion.
- OpenAPI gate: `python manage.py spectacular --file /tmp/schema.yml --validate` exited 0 with `Schema generation summary: Warnings: 183 (107 unique), Errors: 205 (47 unique)` and no `SchemaValidationError`; the 47 diagnostics are classified above and intentionally remain outside `--fail-on-warn`.
- Django check: `python manage.py check` → `System check identified no issues (0 silenced)`.
- Focused changed-file gates: isort → exit 0; Ruff format → `6 files already formatted`; Ruff check → `All checks passed!`; flake8 → exit 0. The full settings file retains pre-existing formatter/linter findings outside this change.
- Review round 1 found no blocking findings; round 2 verified the pytest/Django-runner precedence fix and blog schema test with no critical, high, or medium findings. `git diff --check` passed.

### 2026-09-06 - Codified by codify skill

- Added the PostgreSQL/pgvector contract to `docs/rules/testing.md`, the serializer-first OpenAPI request-body rule to `docs/rules/api.md`, and the root-cause incident to the append-only `docs/LEARNINGS.md`. Route verification for representative backend paths returned `api,security,database,forum,wagtail,testing`, so the testing/API rules are reachable by write-time injection.

### 2026-09-06 - Completed by completing-todos skill

- Verification: all five acceptance criteria passed with the quoted test, schema, check, and lint evidence above.
- Review: 0 critical/high/medium findings after the two-round focused review; the one compatibility finding was repaired and verified.

## Notes

P2 because these failures make local verification diverge from the supported PostgreSQL/pgvector environment and leave the OpenAPI validation gate unable to distinguish valid from invalid generated documents. SQLite may remain useful for narrowly scoped checks, but it is not the database target for the forum pgvector test suite.

### 2026-09-07 - Renumbered 358 -> 370 while landing from a peer worktree

- This todo was written uncommitted in the `forum-editor` worktree with
  `issue_id: "358"`, which was already taken on `main` by
  `todos/358-pending-p3-widen-requests-exception-drift-guard.md` (added by
  PR #674, and carrying its own `source_review` tracking). Two different todos
  shared the number; this one is renumbered to the next free id, 370.
- The work itself is unchanged. It was authored in a worktree based on
  `8f9145f` (PR #668, 2026-09-05) and never committed; it was preserved as
  snapshot `6ec8a78` on `feat/forum-editor-responsive` and the postgres/OpenAPI
  half was replayed onto current `main` here. The link-preview feature that
  shared that tree is deliberately NOT included.
- Conflicts on replay were confined to three append-only docs
  (`docs/LEARNINGS.md`, `docs/rules/api.md`, `docs/rules/testing.md`); both
  sides were kept, and the 2026-09-06 LEARNINGS entry was slotted before the
  2026-09-07 run rather than appended, to keep the log chronological. The eight
  code files applied cleanly.
