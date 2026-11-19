---
status: completed
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

- [x] `backend/requirements.in` exists and `pip-compile` reproduces the
      committed `requirements.txt` byte for byte (CI step proves it).
- [x] The Work Log lists every package whose version changed against the old
      freeze; Land copies that list into the PR body.
- [x] The full backend suite passes, run repo-wide (not app-scoped).
- [x] The Dockerfile's install steps, replayed in a fresh Python 3.13 venv,
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

### 2026-11-18 - Implemented by the todo sweep (run 2026-11-18-0148)

- pip-tools (owner decision 2026-11-17), not uv: `backend/requirements.in` lists what the code imports or the deploy runs; `backend/requirements-dev.in` adds the test, type and lint tools and reads the production lock with `-r requirements.txt` (pip refuses `-c` on a file with an editable line). `bash bin/compile-requirements.sh` writes both locks without hashes and puts `-e ./packages/wagtail_forum` back as a relative path. The `backend-checks` job recompiles and fails on any diff.
- The image installs `requirements.txt` only; CI, `security-scan.yml` (pip-audit and the new-vuln gate) and local venvs use `requirements-dev.txt`, which holds every production pin. `settings.py` adds `debug_toolbar` and `django_extensions` only when installed, because the image build runs `compilemessages` and `collectstatic` with DEBUG on. `env_integrity.py` compares against the dev lock.
- Changed against the old freeze (compiled with the old file as the seed, so no version moved):
  - Version changes: none.
  - Removed (nothing imports them, nothing requires them): cachetools 8.0.1, cbor2 6.2.1, decorator 5.3.1, django-js-asset 5.0.0, google-api-python-client 2.201.0, google-auth-httplib2 0.4.4, httplib2 0.32.1, markdown 3.11.3, markdown2 2.5.5, pyparsing 3.3.3, rsa 4.9.1, ujson 6.1.0.
  - Added: django-otp 1.7.5 (todo 705), pip 26.3 (pinned because `llm` depends on it); dev lock only: ast-serialize 0.13.1 (a mypy dependency the old freeze lacked), build 1.6.1, pip-tools 7.7.0, pyproject-hooks 1.3.3, wheel 0.48.0.
  - Moved to the dev lock only: asttokens, coverage, django-debug-toolbar, django-extensions, django-stubs, executing, factory-boy, faker, freezegun, iniconfig, ipython, ipython-pygments-lexers, jedi, librt, matplotlib-inline, mypy, mypy-extensions, parso, pathspec, pexpect, psutil, ptyprocess, pure-eval, pytest, pytest-cov, pytest-django, ruff, stack-data, traitlets, types-pyyaml, types-requests (same versions).
- Compiled on macOS; the locks carry no platform markers, so a Linux compile should match. Not verified on Linux, and the suite ran in the shared venv (which still holds the removed packages): CI's first run is the proof. Risk for todo 711: Dependabot may read pip-compile flags from the lock header, which names `bin/compile-requirements.sh`, and will not run its relative-path fix, so its PRs could fail the lock check. The Dependabot holds in `.github/dependabot.yml` stay (they are todo 711 decisions now, not resolver workarounds); the `ruff` ignore still matches, and the ruff pin moved to `requirements-dev.in`.

### 2026-11-18 - Verified by the todo sweep (run 2026-11-18-0148)

- AC 1: `cd backend && PYTHON=venv/bin/python bash bin/compile-requirements.sh --cache-dir /private/tmp/claude-501/g7-ptcache && /usr/bin/git -C .. diff --exit-code -- backend/requirements.txt backend/requirements-dev.txt && echo LOCKS-MATCH` — evidence `.sweep-evidence/g7/708-ac0.txt` (not committed), last lines:

  ```text

  !!
    self.finalize_options()
      WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection broken by 'ReadTimeoutError("HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out. (read timeout=15)")': /packages/27/8d/2bc5f5546ff2ccb3f7de06742853483ab75bf74f36a92254702f8baecc79/factory_boy-3.3.3-py2.py3-none-any.whl.metadata
  LOCKS-MATCH
  ```

- AC 2: `bash .sweep-evidence/g7/pindiff-708.sh` — evidence `.sweep-evidence/g7/708-ac1.txt` (not committed), last lines:

  ```text
     listed: types-pyyaml
     listed: types-requests
     listed: ujson
     listed: wheel
  == ALL LISTED
  ```

- AC 4: `bash .sweep-evidence/g7/replay-708.sh` — evidence `.sweep-evidence/g7/708-ac3.txt` (not committed), last lines:

  ```text
  No known vulnerabilities found
  Name          Skip Reason
  ------------- ----------------------------------------------------------------------------
  wagtail-forum Dependency not found on PyPI and could not be audited: wagtail-forum (0.1.0)
  == REPLAY OK
  ```

### 2026-11-18 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-18-0148)

- AC 3: confirmed by the owner on 2026-11-18: "Owner confirmed 2026-11-18: full backend suite repo-wide on the g6 staged tree gave 7003 passed, 8 skipped (12m06s, main-session run; worker run identical); the required CI backend-suite check still gates the merge" (`state.py confirm`; no command or evidence)

### 2026-11-18 - Completed by the todo sweep (run 2026-11-18-0148)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

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
