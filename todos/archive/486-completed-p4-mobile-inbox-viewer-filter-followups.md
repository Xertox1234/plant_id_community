---
status: completed
priority: p4
issue_id: "486"
tags: [mobile, flutter, forum, testing]
dependencies: []
source_review: "PR #878"
triage: ready
triaged: 2026-09-30
owner_decision: "AC4: add a 375pt 5-member test with a known viewer filtered out; the null-viewer test at group_test:121 alone does not count (2026-09-30)"
---

# Mobile inbox viewer filter: non-blocking findings from PR #878 (todo 463)

## Problem

PR #878 made `AuthorAvatarCluster` leave out the viewer, and the inbox now watches
`userProfileServiceProvider` to learn who that is. Both review rounds were clean. These are the
non-blocking findings.

## Findings

1. **The inbox tests make a real network call.** The shared `_wrap`/`_routed` helpers in
   `forum_conversations_screen_test.dart` and `forum_conversations_group_test.dart`, and
   `test/routing/app_router_test.dart:267`, do not override `userProfileServiceProvider`. Every
   existing inbox test sends a real `GET /auth/user/`, gets flutter_test's mocked 400
   (`[USER_PROFILE ERROR]` in the log), and passes only because the error falls back to a null
   viewer. Riverpod 3 also schedules retries after it.
2. **A reload shows the viewer again.** `asData?.value` is null while the profile reloads, so
   during a refresh the viewer's own avatar comes back into every cluster and the label flips
   from "N other members" to "N+1 members". `.value?.username` keeps the last known value
   (`forum_conversations_screen.dart:29`).
3. **A viewer-only group has no label.** When the viewer is the only member, `others` is empty and
   the widget falls back to the bare group glyph, which has no Semantics label
   (`forum_avatar_cluster.dart:44`).
4. **No narrow-viewport test.** The "+N" disc widens the leading slot from 74px to 95px. No test
   pumps a 5+ member group row at 375pt or narrower (the todo 317 pattern in
   `docs/LEARNINGS.md` 2026-08-28).
5. **The loading invariant is untested.** The doc comment says the profile load "never holds the
   list back". No test pumps `FakeUserProfileService(gate:)` to prove it.
6. **The whole screen rebuilds on any profile edit.** Narrowing the watch with
   `.select((s) => s.value?.username)` avoids that.

## Acceptance Criteria

- [x] No inbox or router test sends a real profile request. The helpers override the provider,
      and one test pins the null-viewer fallback on purpose.
- [x] A reload keeps the last known viewer, with a test.
- [x] A viewer-only group has a Semantics label, with a test.
- [x] A 375pt pump of a 5+ member group row shows no overflow.
- [x] A gated-profile test shows the list rendering first, then the viewer dropping out.
- [x] The inbox watches only the username.

## Work Log

### 2026-09-28 - Filed from PR #878 rounds 1 and 2 (todo sweep run 2026-09-28-2018)

### 2026-09-30 - Implemented by the todo sweep (run 2026-10-01-0121)

- The inbox now watches `userProfileServiceProvider.select((s) => s.value?.username)`: `.value` keeps the last known viewer through `UserProfileService.refresh()`, which sets an explicit `AsyncLoading` where `asData` is null (an `invalidate` stays `AsyncData` and never showed the bug), and the `select` rebuilds the screen only when the username changes.
- `AuthorAvatarCluster`'s bare group glyph (viewer is the only member, or an empty roster) now carries a Semantics label: "No other members", or "No members" while the viewer is unknown.
- `FakeUserProfileService` takes a nullable `username` (null = no profile, the unknown-viewer fallback without a real request or retry timers) and a `refreshGate`, and overrides `fetchProfile` so `refresh()` never hits the network. The inbox `_wrap`/`_routed` helpers and the router inbox test override the provider; real `GET /auth/user/` calls across the three files went from 24 to 0.
- New tests: refresh keeps the viewer out, viewer-only label, a 375pt 5-member row with viewer "me" filtered out ("+1" disc), and a gated profile showing the list first, then the viewer dropping out. The existing 375pt test now pins the null-viewer fallback explicitly (`viewer: null`). The refresh and label tests fail against the old code.

### 2026-09-30 - Verified by the todo sweep (run 2026-10-01-0121)

- AC 1: `cd plant_community_mobile && out=$(flutter test --reporter expanded test/features/forum/screens/forum_conversations_screen_test.dart test/features/forum/screens/forum_conversations_group_test.dart test/routing/app_router_test.dart 2>&1); printf '%s\n' "$out"; printf 'real profile requests (lines matching USER_PROFILE] Fetching): %s\n' "$(printf '%s\n' "$out" | grep -c 'USER_PROFILE\] Fetching')"; grep -n -B2 'viewer: null' test/features/forum/screens/forum_conversations_group_test.dart` — evidence `.sweep-evidence/g6/486-ac0.txt`, last lines:

  ```text
  00:02 +45: All tests passed!
  real profile requests (lines matching USER_PROFILE] Fetching): 0
  163-      // No profile: the unknown-viewer fallback, pinned on purpose. The
  164-      // cluster draws every member, "me" included, so it folds into "+2".
  165:      await tester.pumpWidget(_wrap(api, viewer: null));
  ```

- AC 2: `cd plant_community_mobile && flutter test --reporter expanded test/features/forum/screens/forum_conversations_screen_test.dart --plain-name "a profile refresh keeps the last known viewer"` — evidence `.sweep-evidence/g6/486-ac1.txt`, last lines:

  ```text
  138 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  00:00 +0: loading /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_8450e5c2-ec4-3/plant_community_mobile/test/features/forum/screens/forum_conversations_screen_test.dart
  00:00 +0: ForumConversationsScreen (todo 339) a profile refresh keeps the last known viewer: the cluster never puts ME back while the profile reloads (todo 486)
  00:00 +1: All tests passed!
  ```

- AC 3: `cd plant_community_mobile && flutter test --reporter expanded test/features/forum/screens/forum_conversations_screen_test.dart --plain-name "a group where I am the only member left"` — evidence `.sweep-evidence/g6/486-ac2.txt`, last lines:

  ```text
  138 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  00:00 +0: loading /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_8450e5c2-ec4-3/plant_community_mobile/test/features/forum/screens/forum_conversations_screen_test.dart
  00:00 +0: ForumConversationsScreen (todo 339) a group where I am the only member left labels its bare group glyph for a screen reader (todo 486)
  00:00 +1: All tests passed!
  ```

- AC 4: `cd plant_community_mobile && flutter test --reporter expanded test/features/forum/screens/forum_conversations_group_test.dart --plain-name "viewer known and left out"` — evidence `.sweep-evidence/g6/486-ac3.txt`, last lines:

  ```text
  138 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  00:00 +0: loading /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_8450e5c2-ec4-3/plant_community_mobile/test/features/forum/screens/forum_conversations_group_test.dart
  00:00 +0: ForumConversationsScreen group rows (todo 350) a crowded 5-member group row fits a 375-wide phone with the viewer known and left out: three others and a "+1" disc in the widened leading slot (todo 486)
  00:00 +1: All tests passed!
  ```

- AC 5: `cd plant_community_mobile && flutter test --reporter expanded test/features/forum/screens/forum_conversations_screen_test.dart --plain-name "the account profile never holds the list back"` — evidence `.sweep-evidence/g6/486-ac4.txt`, last lines:

  ```text
  138 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  00:00 +0: loading /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_8450e5c2-ec4-3/plant_community_mobile/test/features/forum/screens/forum_conversations_screen_test.dart
  00:00 +0: ForumConversationsScreen (todo 339) the account profile never holds the list back: rows render while it loads, then the viewer drops out of the cluster (todo 486)
  00:00 +1: All tests passed!
  ```

- AC 6: `cd plant_community_mobile && grep -n -B1 -A1 "userProfileServiceProvider" lib/features/forum/screens/forum_conversations_screen.dart` — evidence `.sweep-evidence/g6/486-ac5.txt`, last lines:

  ```text
  35-    final me = ref.watch(
  36:      userProfileServiceProvider.select((s) => s.value?.username),
  37-    );
  ```

### 2026-09-30 - Completed by the todo sweep (run 2026-10-01-0121)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
