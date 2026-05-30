---
name: add-backend-tests-to-ci
status: pending
priority: p1
created: 2026-05-30
tags: [harness, ci, backend, testing]
source_review: "docs/audits/2026-05-30-harness.md"
source_finding: "F2"
---

# Run the backend test suite in CI

## Problem

`backend-ci.yml` runs only `pip check`, `python manage.py check`, and
`python manage.py spectacular` (OpenAPI schema validation). It does **not** run
`python manage.py test`. Pre-commit doesn't run backend tests either (only
black/flake8/isort). So the backend test suite — the very baseline the `/audit`
skill tells you to record — is gated by **no** CI workflow. A PR that breaks
backend tests merges green.

Mobile is the only stack whose tests run in CI (`mobile-ci.yml` runs
`flutter test`). Backend and web are not.

This may be partly deliberate (the suite needs postgres + redis; `backend-ci.yml`
deliberately uses sqlite for the lightweight checks). The fix is to add a proper
test job, not to hand-wave it.

## Acceptance criteria

- [ ] A CI job runs `python manage.py test` (or pytest) for the backend on PRs
      touching `backend/**`, with postgres + redis services wired up (mirror the
      env the suite needs; see backend/CLAUDE.md).
- [ ] The job is blocking (a failing backend test fails the PR).
- [ ] Decide + document whether backend flake8/black should also run in CI (today
      they are pre-commit-only and bypassable with `--no-verify`).
- [ ] Record the suite's pass count in the job log so drift is visible.

## Notes

Workflow files are not under `.claude/` — editable directly. Confirm the test
DB / service container setup against backend/CLAUDE.md before wiring. Watch the
"required status check + path filter" gotcha documented in `backend-ci.yml:12-15`.
