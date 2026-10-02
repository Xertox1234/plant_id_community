---
status: completed
priority: p4
issue_id: "503"
tags: [forum, web, mobile, testing]
dependencies: []
triage: ready
triaged: 2026-10-01
owner_decision: "Findings 1-2: rename the mobile test and add a comment that it covers the swallowed-error path; do not restructure the fake (2026-10-01)"
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

- [x] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #905 review rounds 1-2.

### 2026-10-01 - Implemented by the todo sweep (run 2026-10-02-0118)

- Findings 1-2 (mobile), left as is per the owner decision: the test is
  renamed to 'the guard releases after a swallowed (caught) toggle failure
  (todo 465)' and a comment says it pins release only on the swallowed-error
  path, since `_toggleReactionOnce` catches the ApiException and returns
  normally. The fake is not restructured, so a thrown failure stays
  unexercised; no `lib/` change, so `forum_providers.g.dart` is unaffected.
- Finding 4 (web), fixed with a test: 'releases the reaction guard after a
  failed toggle, so the next tap sends (todo 503)' rejects the first
  `toggleReaction`, waits for the notice, taps again and asserts a second
  call. Mutation-checked by hand: moving the `finally` release into the
  `try` fails this test while the existing todo 465 test still passes.
- Finding 3 (archived 465), fixed without rewriting history: the Land-written
  "Verified by" entry is left as recorded, and a `## Notes` section now gives
  repo-relative commands that re-run both criteria from a checkout root. The
  gitignored `.sweep-evidence/` pointer is left as is: the output it names is
  already quoted inline in that entry.

### 2026-10-01 - Verified by the todo sweep (run 2026-10-02-0118)

- AC 1: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_867e27f5-a58-2/web && npx vitest run --reporter=verbose src/pages/forum/ThreadDetailPage.test.tsx -t "reaction" && cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_867e27f5-a58-2/plant_community_mobile && flutter test test/features/forum/providers/forum_providers_test.dart --plain-name "TopicPosts.toggleReaction"` — evidence `.sweep-evidence/g2/503-ac0.txt`, last lines:

  ```text
  00:00 +0: TopicPosts.toggleReaction success writes the fresh reaction counts back to the post
  00:00 +1: TopicPosts.toggleReaction a failed toggle does not throw and leaves state unchanged
  00:00 +2: TopicPosts.toggleReaction a second tap on the same reaction while the first is in flight is dropped (todo 465)
  00:00 +3: TopicPosts.toggleReaction the guard releases after a swallowed (caught) toggle failure (todo 465)
  00:00 +4: All tests passed!
  ```

  The web half of that run was not quoted (todo 516, finding 1). Re-run in
  todo-sweep run 2026-10-02-0335 from a checkout root with `cd web && npx
  vitest run --reporter=verbose src/pages/forum/ThreadDetailPage.test.tsx -t
  reaction`; its result lines:

  ```text
   ✓ src/pages/forum/ThreadDetailPage.test.tsx > ThreadDetailPage > releases the reaction guard after a failed toggle, so the next tap sends (todo 503) 35ms
   Test Files  1 passed (1)
        Tests  4 passed | 80 skipped (84)
  ```

### 2026-10-01 - Completed by the todo sweep (run 2026-10-02-0118)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
