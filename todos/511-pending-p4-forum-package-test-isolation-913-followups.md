---
status: pending
priority: p4
issue_id: "511"
tags: [forum, backend, testing]
dependencies: []
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

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #913 review rounds 1-2.
