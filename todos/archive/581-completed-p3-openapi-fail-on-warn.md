---
status: completed
priority: p3
issue_id: "581"
tags: [backend, ci, api-docs]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Fix all (large): keep the AC as written; fix every spectacular warning and error in all apps so --validate --fail-on-warn exits 0; runs in sequence with 582, which touches the same views (2026-10-11)"
---

# Fix the auth schema warnings and run `spectacular` with `--fail-on-warn`

## Problem

The CI step "Validate OpenAPI schema generation"
(`.github/workflows/backend-ci.yml`) runs
`python manage.py spectacular --file /dev/null --validate` without
`--fail-on-warn`. Its comment explains why: the auth APIViews emit standing
"unable to guess serializer" warnings, and those are tolerated. So a new
warning anywhere in the API goes unnoticed, and the auth endpoints have no
documented request or response shape in `/api/docs`.

The owner decided (todo 466, 2026-10-11) to fix the warnings and make CI fail
on any new one.

## Acceptance Criteria

- [x] `python manage.py spectacular --file /dev/null --validate --fail-on-warn`
      (run from `backend/`) exits 0. Each auth APIView that warned now declares
      its request and response shapes (`@extend_schema` with a serializer or
      `inline_serializer`), rather than having the warning silenced.
- [x] The CI step passes `--fail-on-warn`, and its comment no longer describes
      tolerated warnings.
- [x] A view added without a serializer makes the step fail (shown once, then
      reverted).

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1929)

- Every auth function view now declares its request and response shapes: `backend/apps/users/view_schemas.py` holds one `extend_schema` per view (inline serializers for the bodies, the shared error envelope), applied above `@api_view` in `views.py` and `oauth_views.py`.
- Cleared the rest of the 93 warnings and 145 errors in all apps: return hints on serializer method fields and model properties, `swagger_fake_view` guards on three `get_queryset`s, `@extend_schema` on the blog, plant-ID, CSP and forum views (`request=None` where a view reads no body), distinct operationIds for the list views, a `BlogAuthorUser` component name, and `ENUM_NAME_OVERRIDES` for the colliding `status`/`priority`/`task_type`/health enums.
- `PlantDiseaseRequest.status` choices moved to `plant_identification/constants.py` so the override can name them; `makemigrations --check` reports no change.
- CI runs `spectacular --file /dev/null --validate --fail-on-warn`, and `apps/core/tests/test_openapi_schema_warnings.py` runs the same gate in pytest. A probe urlconf with a serializer-less `@api_view` made the command exit 1.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1929)

- AC 1: `bash -c 'cd backend && if [ -e .env ]; then mv .env .env.ac-aside; trap "mv .env.ac-aside .env" EXIT; fi; echo "backend/.env present during run: $([ -e .env ] && echo yes || echo no)"; env -i HOME=$HOME PATH=/usr/bin:/bin:/opt/homebrew/bin PYTHONPATH=packages/wagtail_forum DEBUG=True ENABLE_FILE_LOGGING=False DATABASE_URL=sqlite:///db.sqlite3 SECRET_KEY=ci-django-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890 JWT_SECRET_KEY=ci-jwt-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890-different MYPY_CACHE_DIR=/tmp/claude-501/ac-mypy-cache backend/venv/bin/python manage.py spectacular --file /dev/null --validate --fail-on-warn; rc=$?; echo "spectacular exit=$rc"; echo "--- schemas declared on the auth function views (apps/users):"; grep -n -A1 "^@vs\." apps/users/views.py apps/users/oauth_views.py; echo "--- silencing escape hatches used (expect none):"; grep -rnE "extend_schema\(exclude|exclude=True|DISABLE_ERRORS_AND_WARNINGS|GENERATOR_STATS.silence" apps packages/wagtail_forum/wagtail_forum plant_community_backend --include=*.py | grep -v /tests/; exit $rc'` — evidence `.sweep-evidence/g1/581-ac0.txt` (not committed), last lines:

  ```text
  apps/users/oauth_views.py-63-@api_view(["GET"])
  --
  apps/users/oauth_views.py:150:@vs.OAUTH_CALLBACK_SCHEMA
  apps/users/oauth_views.py-151-@api_view(["GET"])
  --- silencing escape hatches used (expect none):
  ```

- AC 2: `grep -n -B8 -A1 "spectacular --file /dev/null" .github/workflows/backend-ci.yml` — evidence `.sweep-evidence/g1/581-ac1.txt` (not committed), last lines:

  ```text
  90-        # warning or error too (todo 581): a view whose request or response
  91-        # shape drf-spectacular cannot see needs an @extend_schema, so /api/docs
  92-        # never silently drops an endpoint's shapes.
  93:        run: python manage.py spectacular --file /dev/null --validate --fail-on-warn
  94-
  ```

- AC 3: `bash -c 'cd backend && printf "from django.urls import path\nfrom plant_community_backend.urls import urlpatterns as real_urlpatterns\nfrom rest_framework.decorators import api_view\nfrom rest_framework.response import Response\n\n\n@api_view([\"POST\"])\ndef ac_probe_view(request):\n    return Response({\"ok\": True})\n\n\nurlpatterns = [path(\"api/v1/ac-probe/\", ac_probe_view)] + real_urlpatterns\n" > _ac_probe_urls.py && cat _ac_probe_urls.py && env -i HOME=$HOME PATH=/usr/bin:/bin:/opt/homebrew/bin PYTHONPATH=packages/wagtail_forum DEBUG=True ENABLE_FILE_LOGGING=False DATABASE_URL=sqlite:///db.sqlite3 SECRET_KEY=ci-django-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890 JWT_SECRET_KEY=ci-jwt-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890-different MYPY_CACHE_DIR=/tmp/claude-501/ac-mypy-cache backend/venv/bin/python manage.py spectacular --file /dev/null --validate --fail-on-warn --urlconf _ac_probe_urls; rc=$?; rm -f _ac_probe_urls.py; echo "spectacular exit=$rc (non-zero fails the CI step)"; echo "probe file removed: $([ -e _ac_probe_urls.py ] && echo no || echo yes)"; test $rc -ne 0'` — evidence `.sweep-evidence/g1/581-ac2.txt` (not committed), last lines:

  ```text
  ⚠️  SQLite database detected; DATABASE_URL must point to PostgreSQL when DEBUG=False.
  ============================================================

  spectacular exit=1 (non-zero fails the CI step)
  probe file removed: yes
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1929)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

Split out of todo 466 (owner decision 2026-10-11).
