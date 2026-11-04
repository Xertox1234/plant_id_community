---
status: pending
priority: p3
issue_id: "695"
tags: [backend, testing, ci, worktree]
dependencies: ["688"]
---

# Confirm Backend CI test count after todo 688's pytest.ini change

## Problem

Todo 688 set `pythonpath = . packages/wagtail_forum` in `backend/pytest.ini`, so a
worktree's pytest run imports the worktree's own `wagtail_forum` instead of the main
checkout's editable install. Locally the full suite gave 6358 passed, 8 skipped with no
`PYTHONPATH` set (main's collected count plus the tests 688 added in `test_import_location.py`, now 2). Whether CI's
`backend-tests` job reports the same count is only visible once 688's PR has run in CI.
Owner decision 2026-11-03 ("Move to new todo") moved that check here.

## Steps

1. Open the `backend-tests` job of todo 688's PR (or the first `main` run after it merges).
2. Compare its pytest summary with main's last run before the merge: the passed count
   should be that number plus the tests in `test_import_location.py`, with the same skips and no new failures or errors.
3. Record the job URL and both summary lines in the Work Log.

## Acceptance Criteria

- [ ] Backend CI (`backend-tests`) passes with main's pre-merge passed count plus the tests todo 688's `test_import_location.py` adds (count them in the job's collection), the same skips, and no new failures or errors.

## Work Log

- 2026-11-03: Created from todo 688 criterion 2 (re-pointed by owner decision "Move to new todo").
