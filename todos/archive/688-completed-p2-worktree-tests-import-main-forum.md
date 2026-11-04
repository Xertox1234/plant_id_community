---
status: completed
priority: p2
issue_id: "688"
tags: [harness, testing, worktrees, wagtail_forum]
dependencies: []
triage: ready
triaged: 2026-11-03
---

# Backend tests in a worktree import the MAIN checkout's wagtail_forum

## Problem

`wagtail_forum` is installed editable from the main checkout. A pytest run in a worktree therefore imports the main checkout's package, not the worktree's. A worktree on a newer main fails with confusing errors, and every agent has to rediscover the `PYTHONPATH=<worktree>/backend/packages/wagtail_forum` prefix.

## Findings

- **2026-11-03, PR #1252.** From `.claude/worktrees/brave-babbage-ee00a5`, `pytest apps/users/...` gave 37 failures, all `ImportError: cannot import name 'CommunityStatsView' from 'wagtail_forum.api.views' (/Users/.../plant_id_community/backend/packages/wagtail_forum/...)`. That is the main checkout's copy, which predated #1248. The same run with the `PYTHONPATH` prefix: 71 passed.
- Recorded before, in the memory note from 2026-09-04: running the package tests twice gave 71 "import file mismatch" errors. The workaround was the same prefix.
- `backend/pytest.ini` has `pythonpath = .`. pytest prepends `pythonpath` entries to `sys.path` at startup, ahead of the editable finder.

## Proposed Solutions

### Option 1: add the package to `pythonpath` in pytest.ini (recommended)

- **Implementation:** `pythonpath = . packages/wagtail_forum`. For mypy, set `mypy_path` under `[tool.mypy]` in `backend/pyproject.toml` to the same package directory, if mypy shows the same drift.
- **Pros:** one line; works in the main checkout, every worktree and CI (same directory there).
- **Cons:** none known. Confirm the editable install in CI still resolves to the same files.
- **Effort:** 30 min, plus a full-suite run.
- **Risk:** low. Note that "import file mismatch" can appear if both paths are collected. `testpaths = apps packages` already collects from `packages/`, so check that this change removes the double collection rather than causing it.

## Recommended Action

1. Edit `backend/pytest.ini` to `pythonpath = . packages/wagtail_forum`.
2. In a worktree whose `wagtail_forum` differs from main, run `pytest apps/users packages/wagtail_forum -q` **without** a `PYTHONPATH` prefix. Expect no ImportError and no import-file-mismatch errors.
3. Run the full backend suite (`pytest --create-db`) in the main checkout. Expect the same count as before.
4. Remove the `PYTHONPATH=` prefix advice from docs and memory once this works.

## Technical Details

- `backend/pytest.ini` (`pythonpath`, `testpaths`), `backend/pyproject.toml` `[tool.mypy]`.
- Editable install: the main venv's site-packages `__editable__` finder points at `<main>/backend/packages/wagtail_forum`.

## Acceptance Criteria

- [x] In a worktree whose `packages/wagtail_forum` differs from the main checkout, `venv/bin/python -m pytest apps/users -q` passes with no `PYTHONPATH` set.
- [ ] Backend CI (`backend-tests`) passes with the same test count. → todo 695 (re-pointed 2026-11-03)

## Work Log

### 2026-11-03 - Filed

- Hit on PR #1252. The owner asked for todos for repeated agent friction.

### 2026-11-03 - Implemented by the todo sweep (run 2026-11-03-2214)

- `backend/pytest.ini` now reads `pythonpath = . packages/wagtail_forum`. pytest puts these entries on `sys.path`, which `PathFinder` searches before the editable meta-path finder, so a worktree run imports its own `wagtail_forum`. Before the change, collecting a package test from this worktree with no `PYTHONPATH` raised `ImportPathMismatchError` on `wagtail_forum/tests/conftest.py`. With the change it collects cleanly.
- New guard `backend/packages/wagtail_forum/wagtail_forum/tests/test_import_location.py`: it asserts that the imported package is the copy beside the test. With the old `pythonpath = .` it fails from a worktree (mismatch error) and with the fix it passes.
- Full suite in this worktree with no `PYTHONPATH`: 6358 passed, 8 skipped (6366). Main checkout collects 6363. The 3 extra are the new test plus the 2 parametrizations `apps/core/tests/test_requests_exception_drift.py` adds for the new file. No test was double-collected or lost.
- Docs: `docs/rules/testing.md` and spec §7.4 now say pytest needs no prefix. The prefix still applies to `manage.py`, `mypy` and `python -c`, which do not read `pytest.ini`, so `scripts/todos/slot_env.py` keeps setting it. `docs/LEARNINGS.md` gained a 2026-11-03 entry. `mypy_path` is unchanged: no mypy drift was observed.

### 2026-11-03 - Verified by the todo sweep (run 2026-11-03-2214)

- AC 1: `bash -c 'cd backend && diff -rq -x __pycache__ backend/packages/wagtail_forum/wagtail_forum backend/packages/wagtail_forum/wagtail_forum; python3 scripts/todos/slot_env.py --main-root . 4 -- env -u PYTHONPATH backend/venv/bin/python -m pytest apps/users packages/wagtail_forum/wagtail_forum/tests/test_import_location.py packages/wagtail_forum/wagtail_forum/tests/test_posts.py -q --create-db'` — evidence `.sweep-evidence/g4/688-ac0.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ================== 528 passed, 3 warnings in 97.06s (0:01:37) ==================
  ```

### 2026-11-03 - Completed by the todo sweep (run 2026-11-03-2214)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-03 - Review round 1: non-blocking findings (PR #1266)

- FIXED (low, two reports at `test_import_location.py:15-16`): the guard only told the two copies apart in a worktree; in the main checkout and CI both are the same path, so dropping the `pytest.ini` entry would not turn CI red. Added `test_package_root_is_on_pytest_pythonpath`, which reads `pytestconfig.getini("pythonpath")` and asserts `packages/wagtail_forum` is in it. A first draft checked `sys.path` instead; the kimi gate pointed out that pytest's default prepend import mode puts the package root on `sys.path` anyway (`packages/wagtail_forum/` has no `__init__.py`), so it was replaced. Mutation check: with `pythonpath = .` and `PYTHONPATH` set so collection gets through, the new test FAILS (1 failed, 1 passed); restored, 2 passed.
- FIXED (low, `todos/695-…md:29`): the criterion said "same test count" while its steps said "plus 3". Both now say main's pre-merge count plus the tests in `test_import_location.py`, with no hard-coded number.
