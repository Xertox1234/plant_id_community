---
status: pending
priority: p3
issue_id: "091"
tags: [ci, drf, openapi, api, testing]
dependencies: []
---

# Add a CI guard for drf-spectacular schema generation (serializer↔model drift)

## Problem

Nothing in CI runs drf-spectacular schema generation, so a serializer that
references a non-existent model field silently breaks `/api/schema/`, `/api/docs/`,
and `/api/redoc/` — and crashes runtime serialization of the affected endpoint —
without failing any check. This is exactly how todo 090 (`ForumPostImage.caption`)
sat undetected for 11 days. A one-line CI step would have caught it on the
introducing PR (#262).

## Findings

- `.github/workflows/backend-ci.yml` job `backend-checks` ("Install dependencies
  and run Django checks") already boots Django and runs `python manage.py check`
  (line ~60), with `SECRET_KEY`/`JWT_SECRET_KEY` set in `env:` (lines ~31–32). It
  does **not** generate the OpenAPI schema.
- `drf_spectacular` is installed (`settings.py:151`, `DEFAULT_SCHEMA_CLASS` at
  `settings.py:503`), so `python manage.py spectacular` is available.
- The current ad-hoc check `backend/test_schema.py` is a root-level script that
  calls `sys.exit(1)`; it only runs by hand and gets swept into `manage.py test`
  discovery (it caused the spurious `test_schema` `_FailedTest` seen in todo 089).
- `manage.py spectacular` currently emits **warnings** (e.g. "unable to guess
  serializer" / "could not resolve authenticator" for `csp_report_view`,
  `get_csrf_token`, auth APIViews) but **0 errors** — so `--fail-on-warn` would be
  too strict today; plain generation (errors fail the build) is the right gate.

## Proposed Solutions

### Option 1: Add a `spectacular --validate` step to `backend-ci.yml` (Recommended)

- **Implementation:** after "Run Django system checks", add a step:
  `python manage.py spectacular --file /dev/null --validate`. Generation aborts
  (non-zero exit) on an `ImproperlyConfigured` field mismatch; `--validate` also
  checks the output against the OpenAPI spec. Do **not** add `--fail-on-warn` yet
  (existing warnings would fail the build).
- **Pros:** one line; reuses the job that already boots Django; catches the whole
  class of serializer↔model drift on every PR.
- **Cons:** doesn't fail on the pre-existing warnings (acceptable — separate
  cleanup).
- **Effort:** ~15 min. **Risk:** low.

### Option 2: Convert the guard into a Django test

- **Implementation:** add a real `TestCase` (e.g. `apps/core/tests/test_schema.py`)
  that calls `SchemaGenerator().get_schema()` and asserts it succeeds; retire the
  root-level `backend/test_schema.py`.
- **Pros:** runs in the existing test suite; no workflow edit.
- **Cons:** slower feedback than a dedicated CI step; still want the root-level
  script removed either way.

## Recommended Action

1. Add the `spectacular --validate` step to `backend-ci.yml` `backend-checks`
   (Option 1).
2. Delete `backend/test_schema.py` (superseded; it pollutes test discovery — see
   todo 090 fallout) **or** keep it only as a local convenience but rename so it
   is not collected by `manage.py test` (e.g. `scripts/check_schema.py`).
3. (Optional, separate) clean up the spectacular warnings, then tighten to
   `--fail-on-warn`.

## Technical Details

- Workflow: `.github/workflows/backend-ci.yml`, job `backend-checks`, after the
  "Run Django system checks" step.
- Command: `python manage.py spectacular --file /dev/null --validate`.
- The `env:` block already provides the keys Django needs to boot in CI.

## Acceptance Criteria

- [ ] `backend-ci.yml` runs `manage.py spectacular --validate` (or equivalent) on
      every PR and fails the job on a schema-generation error.
- [ ] A deliberately broken serializer field makes the new step fail locally
      (`python manage.py spectacular --file /dev/null --validate` exits non-zero).
- [ ] `backend/test_schema.py` is removed or renamed so it is no longer collected
      by `python manage.py test`.

## Work Log

### 2026-05-21 - Created

- Filed after todo 090 (the `ForumPostImage.caption` schema break). Root cause of
  that bug's 11-day dwell was the absence of any CI schema-generation check;
  captured the concrete fix here.

## Notes

p3 — preventive CI hardening, not blocking anything currently. Cheap to implement
and prevents a recurring class of API-contract breakage.
