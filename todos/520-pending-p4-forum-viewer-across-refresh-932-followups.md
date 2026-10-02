---
status: pending
priority: p4
issue_id: "520"
tags: [forum, mobile, testing]
dependencies: []
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

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #932 review rounds 1-2.
