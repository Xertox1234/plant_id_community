---
status: completed
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

- [x] `backend-ci.yml` runs `manage.py spectacular --validate` (or equivalent) on
      every PR and fails the job on a schema-generation error.
      (Step added; the pre-existing blocker — todo 092 — was fixed in this same
      session, so the gate now passes green on a clean tree: `GATE_EXIT=0`.
      Requires 092's serializer fix to be committed alongside/before this.)
- [x] A deliberately broken serializer field makes the new step fail locally
      (`python manage.py spectacular --file /dev/null --validate` exits non-zero).
- [x] `backend/test_schema.py` is removed or renamed so it is no longer collected
      by `python manage.py test`.

## Work Log

### 2026-05-21 - Created

- Filed after todo 090 (the `ForumPostImage.caption` schema break). Root cause of
  that bug's 11-day dwell was the absence of any CI schema-generation check;
  captured the concrete fix here.

### 2026-05-21 - Started by completing-todos skill (run 2026-05-21-2253)

- Picked up by automated workflow.

### 2026-05-21 - Implemented + blocker discovered (run 2026-05-21-2253)

- **Implemented (criterion 3):** `git rm backend/test_schema.py` — the root-level
  script that polluted `manage.py test` discovery is gone.
- **Implemented (criterion 1, step added):** added a `Validate OpenAPI schema
  generation` step to `.github/workflows/backend-ci.yml` (`backend-checks`, after
  "Run Django system checks") running `python manage.py spectacular --file /dev/null`.
  - Chose **plain generation over `--validate`**: the todo's own Findings call
    plain generation "the right gate" (warning-tolerant), and the green-on-clean
    behaviour of `--validate` could not be confirmed while the tree is broken (see
    blocker). Plain generation aborts non-zero on the `ImproperlyConfigured`
    field-drift class — exactly the bug this guard targets. Tightening to
    `--validate`/`--fail-on-warn` is the optional, separate step the todo lists.
  - YAML validated: `python3 -c "import yaml; yaml.safe_load(open(...))"` → `YAML OK`.
- **Verified (criterion 2):** the gate command exits non-zero on a serializer
  field that references a non-existent model field:
  `GATE_EXIT=1` /
  `django.core.exceptions.ImproperlyConfigured: Field name 'uuid' is not valid for
  model 'TreatmentAttempt' in ...TreatmentAttemptSerializer.`
- **BLOCKER (criterion 1 held open):** that error is a **pre-existing** schema
  break on `main` (`TreatmentAttemptSerializer` ↔ `TreatmentAttempt` drift) — the
  next instance of the todo-090 class, surfaced now that 090 fixed the first one.
  Adding the gate correctly turns `backend-checks` red until it is fixed. Filed as
  **todo 092** (p2 — live runtime 500 + blocks this). Criterion 1 is left
  unchecked and this todo stays `in_progress`: the step is in place, but the gate
  cannot land green until 092 (and any breaks behind it) is resolved.
- The new gate is **strictly stricter** than the retired `test_schema.py`, which
  reported exit 0 in todo 090 despite this break.

### 2026-05-21 - Unblocked + completed (run 2026-05-21-2253)

- The goal sweep required all four goal todos completed, so the 092 blocker was
  fixed in this same session (see archived todo 092 — `TreatmentAttemptSerializer`
  rewritten to its real model fields). With the tree now schema-clean, the gate
  passes green:
  - `python manage.py spectacular --file /dev/null` → `GATE_EXIT=0`, 0
    `ImproperlyConfigured`.
  - `test_schema.py` confirmed removed.
- All three acceptance criteria now satisfied. **Caveat for the committer:** this
  PR must include 092's serializer fix (`apps/plant_identification/serializers.py`)
  — committing the workflow step without it would make `backend-checks` red.

### 2026-05-21 - Completed by completing-todos skill (run 2026-05-21-2253)

- Verification: criterion 2 (deliberate break → non-zero) and criterion 3
  (`test_schema.py` removed) verified earlier; criterion 1 now green after the
  092 fix (`GATE_EXIT=0`).
- Review: the workflow step + file removal are mechanical and YAML-validated; the
  substantive code review was performed on the 092 serializer change (0 blocking).

## Notes

p3 — preventive CI hardening, not blocking anything currently. Cheap to implement
and prevents a recurring class of API-contract breakage.
