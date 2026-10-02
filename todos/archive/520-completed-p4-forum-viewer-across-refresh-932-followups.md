---
status: completed
priority: p4
issue_id: "520"
tags: [forum, mobile, testing]
dependencies: []
triage: ready
triaged: 2026-10-02
owner_decision: "Findings 1-2: also reset userProfileServiceProvider on session-expiry sign-out in _handleSessionExpired so the stale username is cleared, and keep the comments truthful (2026-10-02)"
---

# Forum viewer across refresh: non-blocking findings from PR #932 (todo 507)

## Problem

PR #932 (todo 507) merged after two review rounds in todo-sweep run 2026-10-02-0118. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`plant_community_mobile/lib/features/forum/screens/forum_conversation_screen.dart:121`** (low, round 2). New comments here, in forum\_avatar\_cluster.dart and in the 507 work log say sign-out clears the profile. Only the profile-screen logout calls clear(); AuthService.\_handleSessionExpired (auth\_service.dart:694) does not. With .value, a refresh that fails after expiry now keeps the old username. The router redirect and autoDispose prevent real exposure.
   Suggested: Narrow the comment to 'an explicit logout clears the profile'. Or have \_handleSessionExpired/signOut invalidate userProfileServiceProvider, so a session-expiry sign-out never leaves the previous account's username in .value.

2. **`plant_community_mobile/lib/features/forum/screens/forum_conversation_screen.dart:126`** (low, round 1). New comments say sign-out clears the profile, but only ProfileScreen logout calls clear(); \_handleSessionExpired (auth\_service.dart:690) does not, and nothing invalidates the provider on auth change. With `.value`, a failed refresh after an account switch now keeps the previous user's username.
   Suggested: Narrow the comments to 'profile-screen logout clears it', or have the provider ref.watch the auth state (or clear() in \_handleSessionExpired) so a sign-out on any path resets the identity. The stale identity was already possible before this change, so this can be a follow-up todo.

3. **`plant_community_mobile/test/features/forum/screens/forum_group_conversation_test.dart:540`** (low, round 1). The updated comment says 'the explicit refresh() below does not', but the code right below it calls invalidate(), not refresh(). The refresh() case is in a separate test further down, and that also means this existing test cannot tell asData and .value apart.
   Suggested: Change the comment to say this invalidate() path keeps asData too, so it does not tell the two apart, and that the refresh() tests that follow cover the .value change.

4. **`plant_community_mobile/test/features/forum/screens/forum_user_profile_screen_test.dart:196`** (low, round 2). The 'stays hidden on your OWN profile while the account profile refreshes' test passes under both the old asData code and the new .value code, because an unknown viewer also hides Message. It does not tell the two apart and has no failed-refresh variant. It is a guard for the safe direction, not evidence for the fix.
   Suggested: Optional: say in the test's comment that it guards the safe direction and does not tell asData from .value, or loop it over failRefresh [false, true] as the sibling test does. The sibling 'stays put' tests already cover the change itself.

5. **`plant_community_mobile/test/features/forum/screens/forum_user_profile_screen_test.dart:561`** (low, round 1). The 'stays hidden on your OWN profile while the account profile refreshes' test passes with both asData and .value: under asData, myUsername is null during the refresh, which also hides Message. So the test does not exercise the change, though the Work Log says reverting any site to asData makes its new tests fail.
   Suggested: Keep the test as a guard against a 'show while loading' regression, but say so in a comment, and narrow the Work Log claim to the other-user test, which does tell the two apart.

6. **`plant_community_mobile/test/features/forum/widgets/forum_avatar_cluster_test.dart:172`** (low, round 1). handle.dispose() runs at the end of the test body, not in a finally/addTearDown. If an expect fails first, the semantics handle leaks into later tests and can add noise.
   Suggested: Use addTearDown(handle.dispose) right after ensureSemantics().

7. **`todos/archive/507-completed-p4-mobile-inbox-viewer-refresh-909-followups.md:70`** (low, round 1). Work Log headers are dated 2026-10-01 but cite run 2026-10-02-0118, so the run id and date disagree. This is cosmetic only.
   Suggested: Align the dates, or leave as is if the run id is authoritative.

## Acceptance Criteria

- [x] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #932 review rounds 1-2.

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Findings 1-2 (owner decision 2026-10-02): `AuthService._handleSessionExpired` now resets the account profile — `ref.read(userProfileServiceProvider.notifier).clear()` right after the bearer is dropped, guarded by `ref.exists` so an unwatched autoDispose provider is not built (and `/auth/user/` not fetched) just to be cleared. `clear()` rather than `invalidate()`: a rebuild keeps the old profile in `.value` while it re-fetches, anonymously, into Riverpod's retry loop. Two new `auth_service_test.dart` tests: a watched profile lands as `AsyncData(null)` (not loading, not an error) after the handler runs, and an unwatched one is never built; `_Harness` takes extra `overrides`. Mutation-checked: removing the `clear()` fails the first test, swapping in `invalidate()` fails it too, and dropping the `ref.exists` guard fails the second — plus the existing real-HTTP "a refused exchange signs the user out once" test, because the unguarded read built the real profile service and it fetched `/auth/user/`. The comments in `forum_conversation_screen.dart` and `forum_avatar_cluster.dart` now name the two paths that clear the profile (the profile-screen logout and a session-expiry sign-out). `auth_service.g.dart` regenerated for the hash. Outside the decision's scope: the auth-state listener's null branch (an external Firebase sign-out) still does not clear the profile; the login redirect and autoDispose bound that.
- Finding 3: the group-thread comment now says this `invalidate()` keeps `asData` too, so it cannot tell `asData` from `.value`, and that the `refresh()` tests that follow can.
- Findings 4-5: the own-profile test now runs for `failRefresh` false and true, asserts the settled `hasError`, and its comment says it guards the safe direction only and passes under both readings. Narrowing 507's "reverting each site to `asData` fails its new tests": that holds for the group thread, the new-group screen and the OTHER-user profile tests ('stays put'); the own-profile test is a regression guard, not evidence for the fix. Recorded here rather than rewriting 507's archived entry.
- Finding 6: the test body now runs inside `try { … } finally { handle.dispose(); }`, so a failing expect no longer leaks the semantics handle into later tests. Not the suggested `addTearDown(handle.dispose)`: flutter_test verifies at the end of the test BODY that every `SemanticsHandle` is disposed (`WidgetTester._verifySemanticsHandlesWereDisposed`), and tearDowns run after that check, so the suggestion fails every run with "A SemanticsHandle was active at the end of the test" (tried, reverted).
- Finding 7: left as is. Run ids are minted in UTC (`.claude/skills/completing-todos/SKILL.md`: `RUN_ID = date -u +%Y-%m-%d-%H%M`) while Work Log dates are local: run 2026-10-02-0118's triage commit landed at 01:35:59Z, 17 minutes after a 01:18 UTC mint, which was the evening of 2026-10-01 in MDT. The dates and the run id disagree by time zone, not by fact.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/services/auth_service_test.dart test/features/forum/screens/forum_group_conversation_test.dart test/features/forum/screens/forum_user_profile_screen_test.dart test/features/forum/widgets/forum_avatar_cluster_test.dart && grep -n -A9 "Implemented by the todo sweep (run 2026-10-02-0335)" ../todos/archive/520-completed-p4-forum-viewer-across-refresh-932-followups.md'` — evidence `.sweep-evidence/g9/520-ac0.txt` (not committed), last lines:

  ```text
  51-- Findings 1-2 (owner decision 2026-10-02): `AuthService._handleSessionExpired` now resets the account profile — `ref.read(userProfileServiceProvider.notifier).clear()` right after the bearer is dropped, guarded by `ref.exists` so an unwatched autoDispose provider is not built (and `/auth/user/` not fetched) just to be cleared. `clear()` rather than `invalidate()`: a rebuild keeps the old profile in `.value` while it re-fetches, anonymously, into Riverpod's retry loop. Two new `auth_service_test.dart` tests: a watched profile lands as `AsyncData(null)` (not loading, not an error) after the handler runs, and an unwatched one is never built; `_Harness` takes extra `overrides`. Mutation-checked: removing the `clear()` fails the first test, swapping in `invalidate()` fails it too, and dropping the `ref.exists` guard fails the second — plus the existing real-HTTP "a refused exchange signs the user out once" test, because the unguarded read built the real profile service and it fetched `/auth/user/`. The comments in `forum_conversation_screen.dart` and `forum_avatar_cluster.dart` now name the two paths that clear the profile (the profile-screen logout and a session-expiry sign-out). `auth_service.g.dart` regenerated for the hash. Outside the decision's scope: the auth-state listener's null branch (an external Firebase sign-out) still does not clear the profile; the login redirect and autoDispose bound that.
  52-- Finding 3: the group-thread comment now says this `invalidate()` keeps `asData` too, so it cannot tell `asData` from `.value`, and that the `refresh()` tests that follow can.
  53-- Findings 4-5: the own-profile test now runs for `failRefresh` false and true, asserts the settled `hasError`, and its comment says it guards the safe direction only and passes under both readings. Narrowing 507's "reverting each site to `asData` fails its new tests": that holds for the group thread, the new-group screen and the OTHER-user profile tests ('stays put'); the own-profile test is a regression guard, not evidence for the fix. Recorded here rather than rewriting 507's archived entry.
  54-- Finding 6: the test body now runs inside `try { … } finally { handle.dispose(); }`, so a failing expect no longer leaks the semantics handle into later tests. Not the suggested `addTearDown(handle.dispose)`: flutter_test verifies at the end of the test BODY that every `SemanticsHandle` is disposed (`WidgetTester._verifySemanticsHandlesWereDisposed`), and tearDowns run after that check, so the suggestion fails every run with "A SemanticsHandle was active at the end of the test" (tried, reverted).
  55-- Finding 7: left as is. Run ids are minted in UTC (`.claude/skills/completing-todos/SKILL.md`: `RUN_ID = date -u +%Y-%m-%d-%H%M`) while Work Log dates are local: run 2026-10-02-0118's triage commit landed at 01:35:59Z, 17 minutes after a 01:18 UTC mint, which was the evening of 2026-10-01 in MDT. The dates and the run id disagree by time zone, not by fact.
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-02 - Round-1 repair by the todo sweep (run 2026-10-02-0335)

- Round-1 review (high, `auth_service.dart`): the session-expiry `clear()`
  left the profile at `AsyncData(null)` and nothing fetched it again. A
  watcher on an offstage shell tab keeps the autoDispose provider alive
  (go_router disables `TickerMode` on an inactive branch, flutter_riverpod
  pauses those subscriptions, Riverpod never disposes a provider with paused
  listeners), so after a re-login ProfileScreen showed "No profile data
  available", a data state with no Retry, until a restart.
- `_refetchAccountProfile()` invalidates `userProfileServiceProvider` when a
  sign-in completes: after the exchange succeeds, and when a refresh completes
  a login the launch exchange failed (todo 498). A same-session token refresh
  does not. No `ref.exists` guard: invalidating a provider nothing holds is a
  no-op, and a screen's first watch builds it under the new bearer.
- The repair agent hit the usage limit before verifying; the main session
  finished it. Its tests counted `overrideWith` factory calls, which stay at 1
  across an invalidate (riverpod 3.2.1 keeps one notifier per element and
  re-runs `build()`), so the counter now counts `build()` calls.
- Tests: five new cases (re-login with an active watcher, with a paused
  offstage watcher, a refresh that completes the login, a same-session refresh
  that must not refetch, no build when nothing holds the provider). 44 passed
  in `auth_service_test.dart`; full mobile suite 952 passed / 9 skipped;
  `flutter analyze` clean; `build_runner` wrote 0 outputs. Mutation-checked:
  emptying `_refetchAccountProfile` fails exactly the three re-login tests;
  file restored byte-identical from a copy.
