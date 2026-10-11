---
status: pending
priority: p4
issue_id: "558"
tags: [todo-sweep, follow-ups, mobile]
dependencies: []
---

# Follow-ups from PR #948 (todo 520), run 2026-10-02-0335

## Problem

Promoted out of todo 527 on 2026-10-10 (owner decision: slice it per PR). Todo-sweep run 2026-10-02-0335
merged PR #948; its review rounds reported the non-blocking findings below, which a curation pass
checked against main and a refuter failed to refute. Line numbers are as of 2026-10-02, so re-check each
finding against main before acting on it.

## Findings

### PR #948 (todo 520)

1. **`plant_community_mobile/lib/services/auth_service.dart:724`** (medium, defect). ref.exists guard does not stop the bearerless fetch when the profile element is dirty. After a re-login with only a paused (offstage-tab) watcher, \_refetchAccountProfile's invalidate stays deferred (the scheduler flushes only active elements), so the element is dirty. A second session expiry passes ref.exists and the .notifier read flushes it: build() sends GET /auth/user/ just after setAuthToken(null), with no bearer. Its 401 lands over clear()'s AsyncData(null) as a retrying error and arms Riverpod's retry timer. If it returns before Firebase signOut finishes, it carries the current session and enters \_refreshAccessToken. The guard comment (:720-721) covers only the unwatched case of this same anonymous fetch.
   Suggested: Gate UserProfileService.build() on a bearer (an ApiService getter) or on auth state, and return null with no request; keep clear(). Test: paused watcher, expiry, re-login, second expiry, then assert no bearerless build. A broader option: build() watches authServiceProvider.select((s) => s.isAuthenticated) and returns null when signed out. That would also cover the external-path and pre-await items; check for a provider cycle first.
   Seen on main: auth\_service.dart:711 setAuthToken(null), then :723-724 `if (ref.exists(userProfileServiceProvider)) ref.read(userProfileServiceProvider.notifier).clear();`. riverpod 3.2.1 scheduler.dart:132 `if (element.isActive) element.flush();`; proxy\_provider\_listenable.dart:130 read calls element.flush(). auth\_service\_test.dart:484 pins the deferral ('premise: the rebuild is deferred').

2. **`plant_community_mobile/lib/services/auth_service.dart:717`** (low, defect). External Firebase sign-out keeps the old profile; comment says expiry is the only other sign-out path. The authStateChanges null branch (revoked token, disabled account) ends the session without clearing the profile, yet :716-717 calls session expiry 'the app's only other sign-out path'. The owner asked for truthful comments, and the Work Log admits the gap. While an offstage watcher keeps the provider alive, a later sign-in as another account leaves the old username in .value during the refetch, and after a failed one. Forum screens then treat the old account as 'me'. \_refetchAccountProfile's doc (:748-749, 'replaces the last one's profile') overstates in the same way.
   Suggested: Run the same guarded clear() in the null branch before `state = AuthState(error: signedOutMessage)`. Do it after the bearer-gate fix, so that read cannot start a fetch. Or narrow both comments to the two paths that clear, and name the external sign-out as uncovered.
   Seen on main: auth\_service.dart:153-166 null branch: detach(), setAuthToken(null), \_clearJWT(), `state = AuthState(error: signedOutMessage)`, no profile clear. :716-717 'The profile-screen logout clears it itself; this is the app's only other sign-out path (todo 520).' :748-749 'for a different account it replaces the last one's profile'.

3. **`plant_community_mobile/lib/services/auth_service.dart:723`** (low, defect). Profile cleared two awaits before the auth flip, so signed-in screens flash an identity-less state. clear() runs before `await _clearJWT()` and `await _firebaseAuth.signOut()`, while isAuthenticated is still true. For those frames, a visible ProfileScreen shows 'No profile data available' (no Retry, no logout). A mounted group thread renders every message as theirs: awaitingMe needs isLoading, and AsyncData(null) is not loading. Only setAuthToken(null) has to come before the awaits. One reviewer reproduced the flash and found all 44 auth tests pass with clear() moved later.
   Suggested: Move the guarded clear() to just before `state = const AuthState(error: message)`, so the identity reset and the auth flip notify in the same frame. Add a test that holds FirebaseAuth.signOut open and asserts the profile is still held while isAuthenticated is true.
   Seen on main: auth\_service.dart:723-729: clear(), then `await _clearJWT(); await _firebaseAuth.signOut(); state = const AuthState(error: message);`. :39 `isAuthenticated => jwtToken != null`. profile\_screen.dart:68-69 null branch returns 'No profile data available'. forum\_conversation\_screen.dart:134 `awaitingMe = isGroup && me == null && (meAsync?.isLoading ?? false)`.

4. **`plant_community_mobile/lib/services/auth_service.dart:756`** (low, defect). Post-login refetch is a refresh, so ProfileScreen shows 'No profile data available' instead of a spinner. ref.invalidate without asReload rebuilds over the cleared AsyncData(null) as a refresh, not a reload. The state stays a data value that is refreshing, and ProfileScreen's when() skips loading on refresh by default, so it shows 'No profile data available' for the whole post-login GET. It also leaves Riverpod's retry counter unchanged (buildState resets it only on a reload), so a retry budget used up earlier gets no auto-retry. The re-login tests check only the settled state.
   Suggested: Use `ref.invalidate(userProfileServiceProvider, asReload: true)`. In the re-login test, assert that the state right after the rebuild isLoading, so ProfileScreen shows its spinner.
   Seen on main: auth\_service.dart:756 `ref.invalidate(userProfileServiceProvider);`. riverpod 3.2.1 element.dart:50 `onLoading(AsyncLoading(), seamless: !ref.isReload)`, :668 `if (_didChangeDependency) _retryCount = 0;`; async\_value.dart:244/253 when() skipLoadingOnRefresh = true. profile\_screen.dart:66-69.

5. **`plant_community_mobile/lib/services/user_profile_service.dart:189`** (low, defect). clear() does not fence a profile fetch already in flight. refresh() writes state after its await with no check. Riverpod drops a pending build() result only on rebuild or dispose, not on a manual state write. So a GET /auth/user/ accepted under the old session that returns 200 after the expiry's clear() puts the previous profile back in .value. In the common case the fetch's own 401 caused the expiry, and it lands an AsyncError with a null value, which is harmless; so this is narrow. The test's 'lands AsyncData(null)' claim holds only when no fetch is in flight.
   Suggested: Add a generation counter that clear() bumps. Capture it before the await in refresh(), updateProfile() and build(), and skip the write (or return null) when it has changed. Or document clear() as best-effort against an in-flight fetch.
   Seen on main: user\_profile\_service.dart:187-190 `state = const AsyncValue<UserProfile?>.loading(); state = await AsyncValue.guard(fetchProfile);`; :193-195 clear() only sets AsyncData(null). riverpod 3.2.1 element.dart:216 `running = false` only via cancel(), called from runOnDispose (:306).

6. **`plant_community_mobile/test/features/forum/widgets/forum_avatar_cluster_test.dart:14`** (low, polish). Three ensureSemantics tests still dispose the handle outside try/finally. PR 948 put only the fourth semantics test in try/finally, with a comment explaining why. The tests that create handles at lines 14, 46 and 83 still dispose them at the end of the body (39, 78, 110). A failing expect there leaks the handle into later tests, which is the problem the PR fixed in the fourth test.
   Suggested: Wrap the three bodies in the same `try { ... } finally { handle.dispose(); }`. Not addTearDown, per the PR's note. Or add a small helper that runs a body under an ensured semantics handle.
   Seen on main: forum\_avatar\_cluster\_test.dart:14/46/83 `final handle = tester.ensureSemantics();`, disposed with no try/finally at :39/:78/:110; :153-178 has the try/finally and its comment.

## Acceptance Criteria

- [ ] Each of its 6 findings is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).
