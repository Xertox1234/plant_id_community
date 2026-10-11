---
status: completed
priority: p3
issue_id: "580"
tags: [backend, ci, typing]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Everything incl. tests: the gate type-checks apps/users app code AND apps/users/tests; only the generated apps/users/migrations is excluded, via a narrow per-module override (2026-10-11)"
---

# Gate one backend app on mypy in CI, with the django-stubs plugin

## Problem

mypy runs in no CI job and no pre-commit hook, so the type hints added under
todo 002 are never checked. The owner decided (todo 466, 2026-10-11) to start
with a gate on one app, using the django-stubs plugin. The suggested app is
`users`.

Current state (checked 2026-10-11):

- `backend/pyproject.toml` has a `[tool.mypy]` section and a
  `[tool.django-stubs]` section, but no `plugins = ["mypy_django_plugin.main"]`
  line, so the plugin never loads.
- `mypy` and `django-stubs` are pinned in `backend/requirements.txt`.
- An approximate run on `backend/apps/users/views.py` (2026-09-27) reported 87
  errors: about 60 untyped decorators, 10 untyped calls, and about 10
  `get_*_display` attribute errors that the plugin should resolve.

## Acceptance Criteria

- [x] `backend/pyproject.toml` enables the django-stubs plugin
      (`plugins = ["mypy_django_plugin.main"]`), and the settings module it
      names loads in CI without a real `.env`.
- [x] `mypy apps/users` (run from `backend/`) exits 0. Any remaining
      suppression is a narrow, per-module override or a `# type: ignore[code]`
      with a reason, never a blanket `ignore_errors`.
- [x] A step in `.github/workflows/backend-ci.yml` runs that mypy command and
      fails the job on any error.
- [x] A deliberately introduced type error in `apps/users` makes the step
      fail (shown once, then reverted).

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1929)

- `backend/pyproject.toml` loads `mypy_django_plugin.main` and sets `follow_imports = "silent"`: modules reached only by import are still analysed, but only the files named on the command line report, so the gate is `apps/users` alone. `apps.users.migrations.*` gets the one narrow `ignore_errors` override (owner decision).
- Fixed all 308 `apps/users` errors (app code and tests): `User` annotations import the concrete model under `TYPE_CHECKING`, admin columns use `@admin.display`, cookie `samesite`/`max_age` and the `SIMPLE_JWT` lifetimes are typed. The 12 remaining `# type: ignore[code]` each carry a reason (mostly simplejwt hinting `Token`/`bytes` where it accepts a `str`).
- Test edits are type-only: `client: APIClient` on classes that swap in DRF's client, `assert x is not None` narrowing, and `.pk` for `.id` on simplejwt's `AbstractBaseUser`. No assertion was weakened.
- `.github/workflows/backend-ci.yml` gains a `python -m mypy apps/users` step in `backend-checks`; a deliberate `count: int = "three"` probe made it exit 1, then was removed.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1929)

- AC 1: `bash -c 'cd backend && grep -n -B1 -A6 "plugins = " pyproject.toml && grep -n -A1 "tool.django-stubs" pyproject.toml && if [ -e .env ]; then mv .env .env.ac-aside; trap "mv .env.ac-aside .env" EXIT; fi; echo "backend/.env present during run: $([ -e .env ] && echo yes || echo no)"; env -i HOME=$HOME PATH=/usr/bin:/bin:/opt/homebrew/bin PYTHONPATH=packages/wagtail_forum DEBUG=True ENABLE_FILE_LOGGING=False DATABASE_URL=sqlite:///db.sqlite3 SECRET_KEY=ci-django-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890 JWT_SECRET_KEY=ci-jwt-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890-different MYPY_CACHE_DIR=/tmp/claude-501/ac-mypy-cache backend/venv/bin/python -m mypy apps/users; rc=$?; echo "mypy exit=$rc"; exit $rc'` — evidence `.sweep-evidence/g1/580-ac0.txt` (not committed), last lines:

  ```text
  ============================================================

  pyproject.toml: note: unused section(s): module = ['apps.plant_identification.services.*']
  Success: no issues found in 77 source files
  mypy exit=0
  ```

- AC 2: `bash -c 'cd backend && env -i HOME=$HOME PATH=/usr/bin:/bin:/opt/homebrew/bin PYTHONPATH=packages/wagtail_forum DEBUG=True ENABLE_FILE_LOGGING=False DATABASE_URL=sqlite:///db.sqlite3 SECRET_KEY=ci-django-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890 JWT_SECRET_KEY=ci-jwt-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890-different MYPY_CACHE_DIR=/tmp/claude-501/ac-mypy-cache backend/venv/bin/python -m mypy apps/users; rc=$?; echo "mypy exit=$rc"; echo "--- mypy overrides in pyproject.toml:"; grep -n -A3 "tool.mypy.overrides" pyproject.toml; echo "--- every type: ignore in apps/users, with the line above it (the reason):"; grep -rn -B2 "type: ignore" --include=*.py apps/users; echo "--- type: ignore WITHOUT an [error-code] (expect none):"; grep -rnE "type: ignore($|[^\[])" --include=*.py apps/users; echo "--- blanket ignore_errors outside the migrations override (expect only the pre-existing plant_identification.models one):"; grep -n -B2 "ignore_errors" pyproject.toml; exit $rc'` — evidence `.sweep-evidence/g1/580-ac1.txt` (not committed), last lines:

  ```text
  26:ignore_errors = true
  --
  30-[[tool.mypy.overrides]]
  31-module = "apps.users.migrations.*"
  32:ignore_errors = true
  ```

- AC 3: `grep -n -B1 -A6 "Type-check apps/users" .github/workflows/backend-ci.yml` — evidence `.sweep-evidence/g1/580-ac2.txt` (not committed), last lines:

  ```text
  97-        # plugin with this job's settings env and sets follow_imports=silent, so
  98-        # only the files named here report errors. Widen the gate by naming
  99-        # another app.
  100-        run: python -m mypy apps/users
  101-
  ```

- AC 4: `bash -c 'cd backend && printf "\"\"\"AC probe for todo 580: a deliberate type error.\"\"\"\n\ncount: int = \"three\"\n" > apps/users/_ac_probe_type_error.py && cat apps/users/_ac_probe_type_error.py && env -i HOME=$HOME PATH=/usr/bin:/bin:/opt/homebrew/bin PYTHONPATH=packages/wagtail_forum DEBUG=True ENABLE_FILE_LOGGING=False DATABASE_URL=sqlite:///db.sqlite3 SECRET_KEY=ci-django-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890 JWT_SECRET_KEY=ci-jwt-key-for-backend-checks-abcdefghijklmnopqrstuvwxyz1234567890-different MYPY_CACHE_DIR=/tmp/claude-501/ac-mypy-cache backend/venv/bin/python -m mypy apps/users; rc=$?; rm -f apps/users/_ac_probe_type_error.py; echo "mypy exit=$rc (non-zero fails the CI step)"; echo "probe file removed: $([ -e apps/users/_ac_probe_type_error.py ] && echo no || echo yes)"; test $rc -ne 0'` — evidence `.sweep-evidence/g1/580-ac3.txt` (not committed), last lines:

  ```text
  apps/users/_ac_probe_type_error.py:3: error: Incompatible types in assignment (expression has type "str", variable has type "int")  [assignment]
  pyproject.toml: note: unused section(s): module = ['apps.plant_identification.services.*']
  Found 1 error in 1 file (checked 78 source files)
  mypy exit=1 (non-zero fails the CI step)
  probe file removed: yes
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1929)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

Split out of todo 466 (owner decision 2026-10-11). Widen the gate to other apps
in later todos, one app at a time.
