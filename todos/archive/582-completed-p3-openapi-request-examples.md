---
status: completed
priority: p3
issue_id: "582"
tags: [backend, api-docs]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Add `OpenApiExample` request examples for plant_identification, users and blog

## Problem

Todo 031 asked for request examples in the API docs UI. `OpenApiExample`
appears only in `backend/apps/garden_calendar/api/views.py` and
`backend/packages/wagtail_forum/wagtail_forum/api/views.py` (checked
2026-10-11). The plant_identification, users and blog APIs have none, so
`/api/docs` shows no sample request body for them.

The owner decided (todo 466, 2026-10-11) to add them for those three apps.

## Acceptance Criteria

- [x] Each write endpoint (POST, PUT, PATCH) in `apps/plant_identification`,
      `apps/users` and `apps/blog` that takes a request body has at least one
      `OpenApiExample` with `request_only=True`, following the garden_calendar
      pattern.
- [x] Example values are obviously fake: no real email addresses, tokens, API
      keys or user data.
- [x] The generated schema contains the examples: a test or script counts the
      request examples per app in the `spectacular` output and the count is
      non-zero for each of the three apps.
- [x] `python manage.py spectacular --file /dev/null --validate` still passes.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1929)

- Added `OpenApiExample(..., request_only=True)` to every POST/PUT/PATCH with a body in users (15 operations), plant_identification (7) and blog (4). The multipart endpoints (identify, disease requests) set `media_type="multipart/form-data"` so the example lands on the content type they accept.
- Example values are placeholders: `@example.com` addresses and tokens, keys and passwords spelled `example-...-not-real`.
- `apps/core/tests/test_schema_request_examples.py` generates the schema and checks three things: every body-taking write in the three apps has an example, the request-example count per app is non-zero, and the values are fake. Writes without a body must match a four-item allowlist.
- Done together with todo 581, which touched the same views; `spectacular --validate` still passes.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1929)

- AC 1: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest apps/core/tests/test_schema_request_examples.py --create-db -v -p no:cacheprovider; rc=$?; echo "--- OpenApiExample(..., request_only=True) per file:"; grep -rc "request_only=True" apps/users/view_schemas.py apps/users/firebase_auth_views.py apps/users/email_preferences_views.py apps/plant_identification/views.py apps/plant_identification/api/simple_views.py apps/blog/views.py apps/blog/newsletter_views.py; exit $rc'` — evidence `.sweep-evidence/g1/582-ac0.txt` (not committed), last lines:

  ```text
  apps/users/email_preferences_views.py:1
  apps/plant_identification/views.py:4
  apps/plant_identification/api/simple_views.py:1
  apps/blog/views.py:2
  apps/blog/newsletter_views.py:2
  ```

- AC 2: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python manage.py spectacular --format openapi-json --file /tmp/claude-501/ac582-schema.json > /dev/null 2>&1 && python3 -c "import json; d=json.load(open(\"/tmp/claude-501/ac582-schema.json\")); [print(m.upper(), p, json.dumps(e[\"value\"])) for p,ops in d[\"paths\"].items() if p.startswith((\"/auth/\",\"/api/auth/\",\"/plant-identification/\",\"/blog/\",\"/blog-api/\")) for m,op in ops.items() if m in (\"post\",\"put\",\"patch\") for c in (op.get(\"requestBody\") or {}).get(\"content\",{}).values() for e in c.get(\"examples\",{}).values()]" && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest "apps/core/tests/test_schema_request_examples.py::test_request_example_values_are_obviously_fake" --create-db -v -p no:cacheprovider'` — evidence `.sweep-evidence/g1/582-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 3 warnings in 0.52s =========================
  ```

- AC 3: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest "apps/core/tests/test_schema_request_examples.py::test_each_app_has_request_examples" --create-db -v -s -p no:cacheprovider'` — evidence `.sweep-evidence/g1/582-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 3 warnings in 0.48s =========================
  ```

- AC 4: `bash -c 'cd backend && env -i HOME=$HOME PATH=/usr/bin:/bin:/opt/homebrew/bin PYTHONPATH=packages/wagtail_forum DEBUG=True ENABLE_FILE_LOGGING=False DATABASE_URL=sqlite:///db.sqlite3 SECRET_KEY=ci-django-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890 JWT_SECRET_KEY=ci-jwt-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890-different MYPY_CACHE_DIR=/tmp/claude-501/ac-mypy-cache backend/venv/bin/python manage.py spectacular --file /dev/null --validate; rc=$?; echo "spectacular --validate exit=$rc"; exit $rc'` — evidence `.sweep-evidence/g1/582-ac3.txt` (not committed), last lines:

  ```text
  ⚠️  Redis not configured - caching will use in-memory fallback (not recommended)
  ⚠️  SQLite database detected; DATABASE_URL must point to PostgreSQL when DEBUG=False.
  ============================================================

  spectacular --validate exit=0
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1929)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

Split out of todo 466 (owner decision 2026-10-11).
