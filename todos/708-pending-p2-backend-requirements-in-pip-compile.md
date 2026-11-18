---
status: pending
priority: p2
issue_id: "708"
tags: [backend, dependencies, dependabot, ci]
dependencies: []
triage: ready
triaged: 2026-11-17
owner_decision: "Owner 2026-11-17: pip-tools (pip-compile), no hashes (the -e wagtail_forum line cannot be hashed); dev tools (pytest, mypy, ruff, ...) move to requirements-dev.in/.txt so the production image drops them, CI installs both. The post-merge Dependabot criterion moves to todo 711"
---

# Backend: split requirements.txt into requirements.in + a compiled lock

## Problem

`backend/requirements.txt` is a hand-kept full freeze of about 200 pins with no
record of which ones the app asks for and which are pulled in by a parent.
Dependabot therefore treats every pin as top-level and proposes bumps the
parents forbid, so the weekly backend PR will keep failing at `pip install`.

## Findings

Source: stack audit, 2026-11-15 (this session; Dependabot turned back on in
PR #1303).

- `pip list --outdated` in `backend/venv` on 2026-11-15 listed about 150
  outdated packages; `pip list --outdated --not-required` cut that to 33 that
  are in `requirements.txt`. The rest are transitive.
- Transitive majors a parent caps (hypothesis, not verified one by one):
  `django-treebeard` 5 -> 7 and `django-taggit` 6 -> 7 (Wagtail), `protobuf`
  6 -> 7 and `grpcio` (the google-* libraries), `rpds-py`, `pycparser`,
  `python-dateutil`.
- `backend/requirements-dev.txt` is one line, `-r requirements.txt`: dev tools
  (pytest, mypy, ruff, ipython, django-debug-toolbar) are installed in the
  production image.
- The local venv holds packages that are in neither file (`daphne`, `Twisted`,
  `autobahn`, `flake8`, `isort`, `numpy`), so a freeze of it is not the
  production set either.

## Recommended Action

1. Write `backend/requirements.in`: only the packages the code imports or the
   deploy runs, each with the loosest constraint that is true. Start from
   `pip list --not-required` and check each name against the imports.
2. Compile it with `pip-compile --generate-hashes` (pip-tools) to
   `requirements.txt`. Diff the result against today's file: every version
   change in that diff is a real upgrade and must be listed in the PR.
3. Decide in the same PR whether dev tools move to a `requirements-dev.in`
   compiled against the production lock. If they move, check
   `backend/Dockerfile`, `backend-ci.yml` and `security-scan.yml` still install
   what they need.
4. Keep `-e ./packages/wagtail_forum` working (pip-compile needs it in the
   `.in` file).
5. Add a CI step that fails when `requirements.txt` is not what the `.in`
   compiles to.
6. Confirm Dependabot's pip entry picks up the `.in` file (it supports
   pip-compile) and that the `ruff` ignore in `.github/dependabot.yml` still
   matches.

## Technical Details

- `backend/requirements.txt`, `backend/requirements-dev.txt`
- `backend/Dockerfile` (the install line)
- `.github/workflows/backend-ci.yml`, `.github/workflows/security-scan.yml`
  (pip-audit reads `-r requirements.txt`)
- `.github/dependabot.yml` (pip entry)
- ruff's pin must stay equal to the `ruff-pre-commit` rev in
  `.pre-commit-config.yaml`.

## Acceptance Criteria

- [ ] `backend/requirements.in` exists and `pip-compile` reproduces the
      committed `requirements.txt` byte for byte (CI step proves it).
- [ ] The Work Log lists every package whose version changed against the old
      freeze; Land copies that list into the PR body.
- [ ] The full backend suite passes, run repo-wide (not app-scoped).
- [ ] The Dockerfile's install steps, replayed in a fresh Python 3.13 venv,
      install `requirements.txt` cleanly and `pip-audit -r requirements.txt`
      passes (the real image build is checked at deploy, todo 711).
- [ ] The first Dependabot pip PR after merge installs without a resolver
      conflict (record the PR number and date here). → todo 711 (re-pointed 2026-11-17)

## Work Log

### 2026-11-15 - Filed

- Filed from the stack audit, with Dependabot version updates turned back on
  in PR #1303. Blocks todos 710 and 711.

### 2026-11-15 - First Dependabot group showed the cost (#1322 / #1333)

- The first backend minor/patch group (106 bumps) could not install: it
  raised `django-ai-core`, `llm` and `sqlite-migrate` past what their
  parents and siblings allow, and left `psutil` (new, via `ipython`)
  unpinned. Repaired by hand in #1333 with a dry-run install loop;
  `.github/dependabot.yml` now ignores those versions (#1326).
- Each hold in `dependabot.yml` is a hand-kept copy of a constraint
  `pip-compile` would read from the packages. This todo removes the need.

## Notes

p2 because it decides whether the weekly backend PR is mergeable at all. `uv`
is an alternative to pip-tools; pick one in the PR and say why.

### 2026-11-18 — criteria reworded (owner)

- Sweep 2026-11-18-0148 blocked on two criteria no worker can pass: the PR body
  does not exist until Land, and workers cannot reach a Docker daemon.
- Owner 2026-11-18: the changed-package list lives in the Work Log and Land
  copies it into the PR body; the image criterion becomes the venv replay plus
  pip-audit, and the real image build moves to todo 711 (first Railway deploy
  after this merges).
