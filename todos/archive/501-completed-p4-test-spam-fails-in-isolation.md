---
status: completed
priority: p4
issue_id: "501"
tags: [forum, backend, testing]
dependencies: []
triage: ready
triaged: 2026-09-30
---

# `test_spam.py` fails 8 tests when run on its own

## Problem

`pytest packages/wagtail_forum/wagtail_forum/tests/test_spam.py` run as a
lone file fails 8 of its 9 tests with `RuntimeError: Database access not
allowed`. The tests aren't marked `django_db`, but `HeuristicSpamBackend`
calls `get_setting`, which reaches the host's override provider
(`apps/forum_host/forum_settings.provide` → `_values` → `_load_values`, one
SELECT) whenever the process-level `_memo` is cold.

Inside the full suite an earlier DB test warms the memo, so the file passes.
The result depends on run order, and a developer iterating on spam code
gets a wall of false failures.

## Findings

- Found while implementing todo 426 (2026-09-24), on clean `main`.
- Traceback: `spam/heuristic.py:21` → `conf.py:223` →
  `forum_settings.py:105/94/72` → `transaction.atomic()`.

## Recommended Action

Either mark the module `pytestmark = pytest.mark.django_db`, or give
`wagtail_forum` tests an autouse fixture that primes or stubs the override
provider. Prefer the one that also covers other package test files with the
same shape (grep for `get_setting` use in tests without `django_db`).

## Acceptance Criteria

- [x] `test_spam.py` passes when run as a lone file, and in the full suite.

## Work Log

### 2026-09-24 - Filed from todo 426

### 2026-09-30 - Implemented by the todo sweep (run 2026-10-01-0121)

- Reproduced on clean main: `test_spam.py` alone failed 10 of 14 (the file
  has grown since filing), and `test_conf.py` alone failed 4 of 6 for the
  same reason, the host provider's cold-memo SELECT in a test without DB access.
- Added `backend/packages/wagtail_forum/wagtail_forum/tests/conftest.py`, an
  autouse fixture that empties `wagtail_forum.conf._override_providers` for
  every package test and restores it in place afterwards. Package tests now
  resolve settings package-only (Django setting, then default); no package
  test creates host override rows, and the conftest imports nothing from the host.
- Chose this over a `django_db` module mark because it covers every package
  test file of the same shape (test_conf included), needs no edit to an
  existing test, and also stops a memo warmed by a rolled-back host
  `ForumSettings` row leaking into package tests.

### 2026-09-30 - Verified by the todo sweep (run 2026-10-01-0121)

- AC 1: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_8cfcf2b7-580-1/backend && python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_8cfcf2b7-580-1/scripts/todos/slot_env.py 4 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_spam.py --create-db -p no:cacheprovider && python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_8cfcf2b7-580-1/scripts/todos/slot_env.py 4 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g10/501-ac0.txt`, last lines:

  ```text
    File "/Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_8cfcf2b7-580-1/backend/apps/plant_identification/services/combined_identification_service.py", line 121, in _cleanup_executor
      logger.info("[SHUTDOWN] ThreadPoolExecutor cleanup complete")
  Message: '[SHUTDOWN] ThreadPoolExecutor cleanup complete'
  Arguments: ()
  EXIT_STATUS=0
  ```

### 2026-09-30 - Completed by the todo sweep (run 2026-10-01-0121)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
