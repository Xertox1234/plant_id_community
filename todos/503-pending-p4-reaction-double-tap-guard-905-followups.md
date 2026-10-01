---
status: pending
priority: p4
issue_id: "503"
tags: [forum, web, mobile, testing]
dependencies: []
---

# Reaction double-tap guard: non-blocking findings from PR #905 (todo 465)

## Problem

PR #905 (todo 465) merged after two review rounds in todo-sweep run 2026-10-01-0121. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`plant_community_mobile/test/features/forum/providers/forum_providers_test.dart:106`** (low, round 1). 'The guard releases after a failed toggle' cannot tell `finally` apart from removal after the await. `_toggleReactionOnce` swallows the ApiException, so even a release placed after the await, outside `finally`, passes. The test only shows that the guard is not left set when the call returns normally.
   Suggested: Accept as is, since the swallowing contract makes both forms equivalent today. Or add a comment saying the test pins release on the swallowed-error path, not on a thrown one.

2. **`plant_community_mobile/test/features/forum/providers/forum_providers_test.dart:107`** (low, round 2). The 'guard releases after a failed toggle' test can't fail while the main test passes. \_toggleReactionOnce catches every API error and returns normally, so the test also passes if the `finally` becomes a plain remove after the await. It doesn't pin the throw path.
   Suggested: Make the fake throw from somewhere the inner try does not catch (or drop the test as redundant), so that removing `finally` fails it. Otherwise rename it to say it covers a swallowed failure, not a thrown one.

3. **`todos/archive/465-completed-p3-reaction-double-tap-guard.md:57`** (low, round 2). Verification commands in the Work Log embed absolute paths into a deleted sweep worktree (.claude/worktrees/wf\_010041ec-ccf-2), so they cannot be re-run from a normal checkout.
   Suggested: Use repo-relative commands (cd web && npx vitest run ...; cd plant\_community\_mobile && flutter test ...).
   Also reported: The archived Work Log records verification commands with absolute worktree paths (/Users/.../.claude/worktrees/wf\_010041ec-ccf-2) and refers to a gitignored .sweep-evidence file. The paths will not resolve later, so the evidence cannot be re-run from the archive.

4. **`web/src/pages/forum/ThreadDetailPage.test.tsx:1163`** (low, round 1). The web test only covers release after a successful toggle. Nothing drives a rejected toggleReaction and then a second tap, so if the `finally` release were moved into the try block, the button would lock after an error and no test would catch it. Mobile has this test; web does not.
   Suggested: Add a web test where toggleReaction rejects once, then mocks a resolve. Click like, wait for the notice, click like again, and assert toggleSpy was called twice.
   Also reported: The web test never covers the guard's release after a failed toggle (the `finally` branch). The Dart side has that test, the web side doesn't. Deleting the `finally` would still pass, but a failed reaction would then stay blocked for the page's life.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #905 review rounds 1-2.
