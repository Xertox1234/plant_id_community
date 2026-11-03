---
status: pending
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

- [ ] In a worktree whose `packages/wagtail_forum` differs from the main checkout, `venv/bin/python -m pytest apps/users -q` passes with no `PYTHONPATH` set.
- [ ] Backend CI (`backend-tests`) passes with the same test count.

## Work Log

### 2026-11-03 - Filed

- Hit on PR #1252. The owner asked for todos for repeated agent friction.
