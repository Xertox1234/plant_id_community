---
status: completed
priority: p3
issue_id: "288"
tags: [flutter, testing, firebase, notifications]
dependencies: []
source_review: "todo 272 item 6 (spun out 2026-07-29)"
---

# AuthService has no unit-test harness

## Problem

`plant_community_mobile/lib/services/auth_service.dart` (478 lines) is the
notifier that owns Firebase auth state, the Django JWT exchange, and the
lifecycle wiring for push registration — and it has no test file. Its three
push-registration call sites and its session-expiry suppression are pinned only
indirectly, so a refactor that drops one of them fails no test.

## Findings

- `plant_community_mobile/test/services/` contains
  `firebase_storage_service_test.dart`, `firestore_service_test.dart`,
  `plant_identification_service_test.dart`, `push_registration_service_test.dart`
  and `user_profile_service_test.dart` — there is **no** `auth_service_test.dart`
  (verified 2026-07-29).
- The unpinned wiring, by line in `auth_service.dart` (line numbers as of this
  todo's creation, after the class-head comment was added):
  - `:131` — `pushRegistrationServiceProvider.detach()` on a signed-out auth
    state, followed by `_authGeneration++` at `:132`
  - `:255` — `clearOnLogout()` in `signOut()`, after `_authGeneration++` at `:250`
  - `:354` — `unawaited(syncAfterLogin())` after a successful JWT exchange
- Also unpinned: the `_authGeneration` epoch guard — the mechanism that stops a
  stale in-flight exchange from re-establishing state after sign-out. `:279`
  captures `exchangeGeneration`; the comparison lives in the
  `_isCurrentExchange` helper (`:404`), which the exchange path re-checks at
  **five** points (`:299`, `:322`, `:337`, `:360`, `:383`) — one after each
  await, so a harness should pin the guard at more than one of them.
- Also unpinned: the session-expiry path `_handleSessionExpired` (`:432`).
- **Correction to todo 272's item 6 text**, which named "the `_signingOut`
  session-expiry suppression": there is no `_signingOut` identifier anywhere in
  `lib/` (verified by grep 2026-07-29). The suppression is not a notifier-side
  boolean at all — `signOut()`'s own FCM-clear PATCH is exempted **request-side**
  via `ApiService.skipSessionExpiryKey`, and the docstring at `:429-431`
  records why a flag was rejected: it "couldn't cover a 401 arriving after the
  clear's timeout abandoned the request". This matches the standing Flutter rule
  against suppressing an interceptor side effect with a boolean around an
  awaited call. So what needs pinning is the request-side exemption, not a flag.
- A test seam already exists: `@visibleForTesting FirebaseAuth get firebaseAuth`
  (`:92`) is a lazy getter precisely so a subclass can inject a fake without
  `Firebase.initializeApp()`. `PushRegistrationService` mirrors this pattern and
  **is** tested, so the harness shape is already proven in-repo.
- Pre-existing gap, not introduced by todo 253 slice 6 — that slice added the
  three call sites to an already-untested class.
- Discovery source: todo 253 slice 6 review (2026-07-16), deferred as item 6 of
  todo 272.

## Recommended Action

1. Add `plant_community_mobile/test/services/auth_service_test.dart`, modelled
   on `push_registration_service_test.dart` (same fake-injection approach via
   the `@visibleForTesting` getter, same `ProviderContainer` setup).
2. Override `pushRegistrationServiceProvider` with a recording fake so the three
   wiring points can be asserted directly: sign-out calls `clearOnLogout()`, a
   successful exchange calls `syncAfterLogin()`, a signed-out auth state calls
   `detach()`.
3. Pin the ordering constraint that the production code depends on, not just the
   fact of the call: `clearOnLogout()` must run **before** Firebase sign-out,
   because the PATCH needs the still-valid JWT (documented in
   `push_registration_service.dart`'s class docstring).
4. Pin the session-expiry exemption: a 401 on `signOut()`'s own FCM-clear PATCH
   must not drive `_handleSessionExpired` (it carries
   `ApiService.skipSessionExpiryKey`), so an intentional sign-out never surfaces
   a "Your session expired" message. Assert this through the request options,
   not a notifier flag — there isn't one, by design.
5. Pin the epoch guard: an exchange that completes after `_authGeneration` has
   moved must not write state.

## Technical Details

- `plant_community_mobile/lib/services/auth_service.dart` — carries a comment at
  the class head describing this gap (added during todo 272's closure).
- `plant_community_mobile/test/services/push_registration_service_test.dart` —
  the reference harness shape.
- `plant_community_mobile/docs/patterns/riverpod.md`,
  `.../firebase-auth.md` — read before writing.
- Codegen gate: `auth_service.dart` is a `@riverpod` source, so any edit to it
  requires `flutter pub run build_runner build --delete-conflicting-outputs`
  and a committed `.g.dart`; CI blocks on this and local `flutter analyze` does
  **not** catch it. (A test-only addition does not touch the generated file,
  but the class-head comment already did.)

## Acceptance Criteria

- [x] `test/services/auth_service_test.dart` exists and constructs the notifier
      without touching real Firebase
- [x] All three push wiring points asserted: `syncAfterLogin` post-exchange,
      `clearOnLogout` in `signOut`, `detach` on signed-out state
- [x] `clearOnLogout`-before-Firebase-sign-out ordering pinned
- [x] Session-expiry exemption pinned: a 401 on the FCM-clear PATCH does not
      trigger `_handleSessionExpired` / a "session expired" error state
- [x] `flutter test` passes; `flutter analyze` clean

## Work Log

### 2026-07-31 - Implemented and verified (run 2026-07-31-0411)

13 tests in `test/services/auth_service_test.dart` (11 at first pass,
+2 from review), modelled on
`push_registration_service_test.dart` (hand-rolled fakes, no mocking library).

**Two obstacles the todo did not anticipate, both solved without a production
seam:**

1. `_secureStorage` is a plain `const FlutterSecureStorage()` field with no
   injection point, and every notifier path writes or deletes a JWT — a real
   write throws `MissingPluginException` under `flutter test`. Solved with the
   package's own `FlutterSecureStorage.setMockInitialValues({})` (a
   `@visibleForTesting` static shipped in flutter_secure_storage 10.x that
   swaps in an in-memory platform). No `auth_service.dart` change needed.
2. `authServiceProvider` is **autoDispose**. A bare `container.read()` builds
   the notifier and immediately tears it down, so the *next* read rebuilds it —
   re-running `build()`'s unawaited token exchange against a disposed `Ref`
   ("Cannot use Ref after dispose"). The harness now holds a
   `container.listen(..., fireImmediately: true)` subscription for its
   lifetime, so there is exactly one notifier instance, as in the app.

**Correction confirmed.** The todo's note that todo 272 was wrong about a
`_signingOut` flag is accurate — there is none, and the exemption is
request-side. The test asserts it through `Options.extra`, per the todo.

**Beyond the todo's ask:** the session-expiry AC is pinned *end-to-end* rather
than by flag presence alone. A local `HttpServer` returning 401 backs a real
`ApiService`, and the test asserts the handler fires for an unexempt 401 and
does NOT fire for an exempt one — the flag is worthless if the interceptor
ignores it, and nothing previously covered either side.

Every assertion was **mutation-verified** — regressions introduced one at a
time into `auth_service.dart` / `push_registration_service.dart`:

```
drop syncAfterLogin                  -> RED: ...calls syncAfterLogin
drop clearOnLogout                   -> RED: ...signOut calls clearOnLogout (+3 more)
drop detach                          -> RED: ...signed-out auth state calls detach
clearOnLogout AFTER firebase signOut -> RED: ...ordering ... BEFORE Firebase sign-out
drop signOut epoch bump              -> RED: ...generation bump alone kills a mid-sign-out exchange
drop skipSessionExpiry flag          -> RED: ...FCM-clear PATCH carries skipSessionExpiryKey
```

The fifth mutant initially came back **GREEN (not caught)**: `_isCurrentExchange`
ANDs the generation check with `currentUser?.uid == user.uid`, and the fake's
sign-out clears `currentUser` — so the uid arm alone killed the stale exchange
and `signOut()`'s `_authGeneration++` could have been deleted silently. Added
`the generation bump alone kills a mid-sign-out exchange`, which resumes the
exchange while sign-out is parked on `clearOnLogout` (i.e. *before* Firebase
clears `currentUser`), where only the generation guard can stop it. That mutant
is now caught.

Also updated the class-head comment in `auth_service.dart`, which still said
"NO UNIT-TEST HARNESS". `build_runner build --delete-conflicting-outputs` was
re-run for the CI codegen gate (which local `flutter analyze` does not catch);
it reported the output "same" and `auth_service.g.dart` is byte-identical —
`_$authServiceHash` is `8fbb70b6…` before and after, so riverpod_generator's
source hash is not sensitive to a comment-only edit. Running the regen is still
the right move: that insensitivity is a generator implementation detail, not a
contract to rely on.

Verification:

```
$ flutter analyze
No issues found! (ran in 2.9s)

$ flutter test
00:16 +231 ~3: All tests passed!
```

### 2026-07-31 - Review and repair

`flutter-dart-reviewer`. Two mediums and four lows; all but one repaired.

**Repaired (medium): `_handleSessionExpired` was never exercised.** The
exemption tests proved the flag and the interceptor, but nothing asserted that
`build()` installs the handler at all — deleting
`apiService.setSessionExpiredHandler(_handleSessionExpired)` would have left
every test green while 401s silently stopped signing anyone out. Added a
`session expiry` group: one test fires the registered handler and asserts the
resulting state (`'Your session expired. Please sign in again.'`, JWT cleared,
Firebase sign-out recorded), one asserts the handler is UNinstalled on
disposal (a handler closing over a dead `Ref` is how "Cannot use Ref after
dispose" reaches production). Both mutation-verified — the suite now catches
8 of 8 mutants, up from 6.

**Repaired (low):** `patchCalls.last` replaced with a `singleWhere` on the
payload (with the real push service the build-time exchange also PATCHes that
endpoint, so `.last` leaned on production ordering); `_FakeMessaging` is now
held by the harness and its `tokenRefreshController` closed in `dispose()`
(the real `syncAfterLogin` subscribes to it); `realPush` made nullable instead
of a `late final` that threw `LateInitializationError` in the default harness
mode; the misleading `final inFlight = harness.signIn(...)` captures removed —
`pumpEventQueue()` after the gate completes is the real synchronisation point,
now said so in a comment.

**Not repaired, recorded deliberately (medium): checkpoint 3 of the epoch
guard is not isolated.** `_exchangeFirebaseTokenForJWT` re-checks the
generation at five points; checkpoints 1 and 2 are pinned, but the third —
which runs *after* the JWT is written to secure storage and calls
`_clearJWTIfMatches` to undo it — cannot be reached without a gate between the
storage write and that check. `_secureStorage` is a plain `const` field, so
isolating it needs either a production seam on `AuthService` or promoting
`flutter_secure_storage_platform_interface` (currently transitive) to a
dev_dependency so a gating platform can be installed. Both are wider than a
p3 test-coverage todo, and `_clearJWTIfMatches` is a compensating cleanup
whose failure mode is a stale token in storage, not a wrong auth state. Left
uncovered on purpose rather than papered over.

### 2026-07-29 - Spun out of todo 272 (item 6)

- Promoted rather than re-deferred: todo 272 conditioned items 4/5/6 on the
  forum-mobile-client work being touched again, and that trigger has fired
  (todo 260 merged, PR #498). Per `CLAUDE.md` → Review Doc Tracking,
  promote-all is the only terminal state for a parking todo.
- Given its own todo rather than appended to todo 279 (forum mobile client
  follow-ups), deliberately: 279 is a feature-scope tracking list whose single
  AC is "prioritize the above into concrete slices", so a test-infrastructure
  item added there would be invisible. This is auth-layer test infra, not forum
  client feature scope.
- Verified before promoting that the gap is real (no `auth_service_test.dart`)
  and that a seam already exists (`@visibleForTesting firebaseAuth`), so this is
  a bounded task rather than a testability refactor.

## Notes

p3: pure test-coverage hardening — no user-facing defect, and the wiring is
currently correct. Value is regression protection on a class where a dropped
call is silent (a missing `clearOnLogout` leaves a stale FCM token; a missing
`detach` re-registers after logout). Related: todo 272 (origin), todo 279
(forum mobile client follow-ups), todo 253 slice 6 (added the call sites).
