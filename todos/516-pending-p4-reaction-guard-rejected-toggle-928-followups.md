---
status: pending
priority: p4
issue_id: "516"
tags: [forum, web, mobile, testing]
dependencies: []
---

# Reaction guard rejected toggle: non-blocking findings from PR #928 (todo 503)

## Problem

PR #928 (todo 503) merged after two review rounds in todo-sweep run 2026-10-02-0118. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`todos/archive/503-completed-p4-reaction-double-tap-guard-905-followups.md:64`** (low, round 1). The quoted AC1 evidence shows only the Flutter tail. The new web test's pass line ('releases the reaction guard after a failed toggle ... (todo 503)') appears only in the gitignored .sweep-evidence file, which is the non-durable pointer that finding 3 objected to.
   Suggested: Also quote the vitest lines from 503-ac0.txt: the todo 503 test's ✓ line and 'Tests 4 passed'. Then the archive durably shows that the new web test passed.

2. **`web/src/pages/forum/ThreadDetailPage.test.tsx:1213`** (low, round 2). The new rejected-toggle test leaves logger.error unstubbed, so handleReact's catch prints the 'Error toggling reaction' payload to test stdout (visible in .sweep-evidence/g2/503-ac0.txt line 52). Other failure-path tests in this file stub it with vi.spyOn(logger,'error').mockImplementation(() => {}).
   Suggested: Add `const loggerErrorSpy = vi.spyOn(logger, 'error').mockImplementation(() => {});` at the top of the test. Optionally assert it was called once, so the catch path is also pinned.

3. **`web/src/pages/forum/ThreadDetailPage.test.tsx:1233`** (low, round 1). The comment says the test would catch a release placed anywhere outside `finally`, which overstates it. handleReact's catch swallows the rejection, so a delete placed after the try/catch still runs and this test passes. It only catches a release moved into the `try` (the mutation the Work Log names). This is the same blind spot the mobile comment now admits.
   Suggested: Reword the comment: 'If the release ran only on success (inside `try`), the failed key would stay in flight...'. Or add a note that a release after the try/catch would also pass, because the catch swallows the error.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #928 review rounds 1-2.
