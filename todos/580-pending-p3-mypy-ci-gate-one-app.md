---
status: pending
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

- [ ] `backend/pyproject.toml` enables the django-stubs plugin
      (`plugins = ["mypy_django_plugin.main"]`), and the settings module it
      names loads in CI without a real `.env`.
- [ ] `mypy apps/users` (run from `backend/`) exits 0. Any remaining
      suppression is a narrow, per-module override or a `# type: ignore[code]`
      with a reason, never a blanket `ignore_errors`.
- [ ] A step in `.github/workflows/backend-ci.yml` runs that mypy command and
      fails the job on any error.
- [ ] A deliberately introduced type error in `apps/users` makes the step
      fail (shown once, then reverted).

## Work Log

## Notes

Split out of todo 466 (owner decision 2026-10-11). Widen the gate to other apps
in later todos, one app at a time.
