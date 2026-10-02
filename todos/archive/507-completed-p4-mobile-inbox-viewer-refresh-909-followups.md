---
status: completed
priority: p4
issue_id: "507"
tags: [forum, mobile, testing]
dependencies: []
triage: ready
triaged: 2026-10-01
owner_decision: "Finding 3: keep .value (a stale username is harmless; a null viewer would misattribute own messages); record the reason in the Work Log, no code change (2026-10-01)"
---

# Mobile inbox viewer refresh: non-blocking findings from PR #909 (todo 486)

## Problem

PR #909 (todo 486) merged after two review rounds in todo-sweep run 2026-10-01-0121. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`plant_community_mobile/lib/features/forum/screens/forum_conversation_screen.dart:124`** (low, round 2). Outside the diff: the group thread still uses `asData?.value`. Its comment says asData keeps the old value through a re-fetch, which todo 486 shows is false for refresh(). So a profile refresh sets awaitingMe and holds the thread list back, and a failed refresh shows my messages as theirs.
   Suggested: File a follow-up todo to switch to `meAsync?.value?.username` and fix the comment, with a test that fires refresh() like the new inbox test. forum\_new\_group\_screen.dart:174 and forum\_user\_profile\_screen.dart:38 have the same pattern.

2. **`plant_community_mobile/lib/features/forum/screens/forum_conversations_screen.dart:35`** (low, round 2). AC6 (watch only the username) is checked only by grep. No test shows that a profile change other than the username (e.g. updateProfile changing bio) leaves the screen unrebuilt, so dropping the select would not fail any test.
   Suggested: Optional: set state to AsyncData with the same username and a different bio, then assert conversationsFeed was not re-fetched and the build count is unchanged. Or accept the grep evidence, since this is a performance AC.

3. **`plant_community_mobile/lib/features/forum/screens/forum_conversations_screen.dart:37`** (low, round 1). `s.value` on an AsyncError that carries a previous value keeps returning the stale username. After a failed refresh on account switch the old viewer could be left out of clusters. Unlikely, since sign-out clears the profile.
   Suggested: Accept as is, or guard with `s.hasError ? null : s.value?.username` if a stale viewer matters.

4. **`plant_community_mobile/lib/features/forum/widgets/forum_avatar_cluster.dart:14`** (low, round 1, round 2). The class doc still says every member is shown while the account profile 'is loading or failed'. Since the inbox now reads `.value`, a reload or a failed refresh keeps the last known viewer (Riverpod 3.2.1 element.dart:66 copyWithPrevious). The doc now misstates when the fallback applies.
   Suggested: Reword it: every member is shown only while the viewer is unknown, meaning before the profile first resolves, after a failure with no earlier value, or after sign-out clears it. A reload or failed refresh keeps the last known viewer.
   Also reported: The class doc still says every member is shown while the profile is "loading or failed". With `.value`, a reload, or a failed refresh (Riverpod 3.2.1 AsyncError.copyWithPrevious keeps the previous value), now keeps the last known viewer. Only a first load that has not resolved, or never resolves, shows everyone.

5. **`plant_community_mobile/lib/features/forum/widgets/forum_avatar_cluster.dart:49`** (low, round 1). The new 'No members' label (viewer unknown and empty roster) has no test. Only the 'No other members' branch is covered, by the viewer-only test in forum\_conversations\_screen\_test.dart.
   Suggested: Add a case with \_wrap(api, viewer: null) and a group whose participants list is empty, asserting that \_clusterLabel starts with 'No members'. Or unit-test AuthorAvatarCluster(authors: const []) directly.

6. **`plant_community_mobile/test/features/forum/screens/forum_conversations_group_test.dart:102`** (low, round 1). The first group-row test now runs with viewer 'me' (new \_wrap default), so the cluster shows three of four OTHERS plus a '+1' disc. Its comment still says 'at most three of the five members', which describes the old null-viewer path it no longer exercises.
   Suggested: Reword the comment to 'three of the four other members (the viewer is left out)', and optionally assert the '+1' disc so the test pins the viewer-known path it now runs.

7. **`plant_community_mobile/test/features/forum/screens/forum_conversations_screen_test.dart:195`** (low, round 2). The refresh test covers only the AsyncLoading window. With `.value`, a failed refresh (AsyncError carrying the previous profile) also keeps the viewer, and no test pins that. The new 'No members' label (viewer unknown, empty roster) is also untested; only 'No other members' is.
   Suggested: Add a refresh case where fetchProfile throws: assert the cluster still leaves 'me' out. Add a `viewer: null` empty-roster case asserting the label starts with 'No members'.

## Acceptance Criteria

- [x] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #909 review rounds 1-2.

### 2026-10-01 - Implemented by the todo sweep (run 2026-10-02-0118)

- Finding 1: the group thread (`forum_conversation_screen.dart`), the new-group screen and the forum profile screen now read the account profile's `.value?.username`, not `asData?.value`, and their comments say why. A `refresh()` sets an explicit loading state and a failed one an AsyncError. `asData` is null in both, but Riverpod 3.2.1 `copyWithPrevious` keeps the last profile in `.value`. New tests fire `refresh()` (in flight, and failing) on each of the three screens: the thread is not held back and "Mine" stays on the right; "That's you." still refuses `@me`; "Message" neither blinks out on someone else's profile nor appears on your own. Reverting each site to `asData` fails its new tests.
- Finding 2: a new inbox test emits a profile with the same username and a different bio. It checks that the screen's Scaffold is the same instance (no rebuild) and that `conversationsFeed` was not re-fetched. As a positive control, a username change does rebuild. Dropping the `select` makes the test fail.
- Finding 3: left as is, per the owner decision of 2026-10-01: keep `.value`, because a stale username is harmless and a null viewer would misattribute my own messages. Sign-out clears the profile anyway. No code change, but a new inbox test pins the failed-refresh behaviour this choice relies on.
- Findings 4-7: reworded the `AuthorAvatarCluster` class doc (everyone is shown only while the viewer is unknown; a reload or failed refresh keeps the last known viewer). Added the 'No members' / 'No other members' widget test, an inbox test for `viewer: null` with an empty roster ('No members'), and a failed-refresh inbox test (the cluster still leaves 'me' out). Reworded the group-row comment in `forum_conversations_group_test.dart` and added its '+1' assertion.
- Test support: `FakeUserProfileService` gained `failRefresh` (its `fetchProfile` throws) and `emit(profile)`.

### 2026-10-01 - Verified by the todo sweep (run 2026-10-02-0118)

- AC 1: `bash -c 'cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_4cfc8bb3-2ac-3/plant_community_mobile && flutter test --no-pub -r expanded test/features/forum/screens/forum_conversations_screen_test.dart test/features/forum/screens/forum_conversations_group_test.dart test/features/forum/screens/forum_group_conversation_test.dart test/features/forum/screens/forum_new_group_screen_test.dart test/features/forum/screens/forum_user_profile_screen_test.dart test/features/forum/widgets/forum_avatar_cluster_test.dart && grep -n -A8 "Implemented by the todo sweep (run 2026-10-02-0118)" ../todos/507-pending-p4-mobile-inbox-viewer-refresh-909-followups.md'` — evidence `.sweep-evidence/g6/507-ac0.txt`, last lines:

  ```text
  52-- Finding 1: the group thread (`forum_conversation_screen.dart`), the new-group screen and the forum profile screen now read the account profile's `.value?.username`, not `asData?.value`, and their comments say why. A `refresh()` sets an explicit loading state and a failed one an AsyncError. `asData` is null in both, but Riverpod 3.2.1 `copyWithPrevious` keeps the last profile in `.value`. New tests fire `refresh()` (in flight, and failing) on each of the three screens: the thread is not held back and "Mine" stays on the right; "That's you." still refuses `@me`; "Message" neither blinks out on someone else's profile nor appears on your own. Reverting each site to `asData` fails its new tests.
  53-- Finding 2: a new inbox test emits a profile with the same username and a different bio. It checks that the screen's Scaffold is the same instance (no rebuild) and that `conversationsFeed` was not re-fetched. As a positive control, a username change does rebuild. Dropping the `select` makes the test fail.
  54-- Finding 3: left as is, per the owner decision of 2026-10-01: keep `.value`, because a stale username is harmless and a null viewer would misattribute my own messages. Sign-out clears the profile anyway. No code change, but a new inbox test pins the failed-refresh behaviour this choice relies on.
  55-- Findings 4-7: reworded the `AuthorAvatarCluster` class doc (everyone is shown only while the viewer is unknown; a reload or failed refresh keeps the last known viewer). Added the 'No members' / 'No other members' widget test, an inbox test for `viewer: null` with an empty roster ('No members'), and a failed-refresh inbox test (the cluster still leaves 'me' out). Reworded the group-row comment in `forum_conversations_group_test.dart` and added its '+1' assertion.
  56-- Test support: `FakeUserProfileService` gained `failRefresh` (its `fetchProfile` throws) and `emit(profile)`.
  ```

### 2026-10-01 - Completed by the todo sweep (run 2026-10-02-0118)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
