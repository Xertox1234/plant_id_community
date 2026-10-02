---
status: completed
priority: p4
issue_id: "511"
tags: [forum, backend, testing]
dependencies: []
triage: ready
triaged: 2026-10-01
---

# Forum package test isolation: non-blocking findings from PR #913 (todo 501)

## Problem

PR #913 (todo 501) merged after two review rounds in todo-sweep run 2026-10-01-0121. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`backend/packages/wagtail_forum/wagtail_forum/tests/conftest.py:25`** (low, round 1, round 2). The autouse fixture has no regression test. If it were deleted, the full suite would still pass, because an earlier DB test warms the host memo. Only the lone-file run would fail, and nothing in CI runs that.
   Suggested: Add a small test asserting conf.\_override\_providers is empty inside a package test. Optionally add a CI step that runs test\_spam.py as a lone file.
   Also reported: The autouse fixture has no regression test. If it is deleted, the full suite stays green because a warmed memo hides the cold-memo failure; only a lone-file run of test\_spam.py goes red.

2. **`todos/archive/501-completed-p4-test-spam-fails-in-isolation.md:58`** (low, round 1). The Work Log embeds absolute paths to a throwaway worktree and the machine's user home (/Users/williamtower/...). The evidence excerpt is only log-noise lines plus EXIT\_STATUS=0, not a pytest pass summary.
   Suggested: Use repo-relative commands, and quote the pytest 'N passed' line from the evidence file.

## Acceptance Criteria

- [x] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #913 review rounds 1-2.

### 2026-10-01 - Implemented by the todo sweep (run 2026-10-02-0118)

- Finding 1: added `backend/packages/wagtail_forum/wagtail_forum/tests/test_conftest_isolation.py`.
  A module-scoped fixture captures the provider list before the autouse
  fixture runs; the test asserts it held the host's provider and that the
  live list is empty, and the teardown asserts the list was restored. The host
  registers its provider at `ready()`, so the test fails in the full suite
  too, not only in a lone-file run. Mutation check: with the conftest fixture
  set to `autouse=False`, it failed with `Left contains one more item:
  <function provide ...>`. A second test keeps the conftest free of host
  imports, which `test_reusability` does not cover because it skips `tests/`.
- Finding 1, CI lone-file step (marked optional): not added. The new test
  catches a deleted fixture in any run order, so a separate CI job that runs
  `test_spam.py` alone would add CI time without catching anything more.
- Finding 2: the Verified entry in `todos/archive/501-completed-p4-test-spam-fails-in-isolation.md`
  now uses repo-relative commands, with no worktree or home paths. The original
  evidence file was swept with its worktree, so its pytest summary is lost.
  The entry now cites the #913 squash commit's counts and quotes a fresh
  lone-file run (`14 passed`).

### 2026-10-01 - Verified by the todo sweep (run 2026-10-02-0118)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py 3 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_conftest_isolation.py packages/wagtail_forum/wagtail_forum/tests/test_spam.py --create-db -p no:cacheprovider && cd .. && ! grep -n '/Users/' todos/archive/501-completed-p4-test-spam-fails-in-isolation.md && echo 'no absolute paths in the 501 Work Log'` (the venv is the main checkout's) — evidence `.sweep-evidence/g9/511-ac0.txt`, last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 16 passed, 2 warnings in 16.73s ========================
  no absolute paths in the 501 Work Log
  EXIT_STATUS=0
  ```

### 2026-10-01 - Completed by the todo sweep (run 2026-10-02-0118)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
