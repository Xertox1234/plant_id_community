import 'dart:async';
import 'dart:collection';
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/models/user_profile.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/push_registration_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

import '../support/wait_until.dart';

/// Unit harness for [AuthService] (todo 288).
///
/// Modelled on `push_registration_service_test.dart`: hand-rolled fakes, no
/// mocking library, and the `@visibleForTesting firebaseAuth` seam so the
/// notifier is constructed without `Firebase.initializeApp()`.
///
/// What this pins, and why each mattered before it existed:
/// - the three push wiring points (`syncAfterLogin` / `clearOnLogout` /
///   `detach`) — a dropped call is silent in production (a stale FCM token, or
///   re-registration after logout);
/// - the ORDER of `clearOnLogout` vs Firebase sign-out — the clear PATCH needs
///   the still-valid JWT, so swapping them breaks the clear without failing
///   anything;
/// - the `_authGeneration` epoch guard — a stale in-flight exchange must not
///   re-establish state after sign-out;
/// - the session-expiry exemption, which is REQUEST-side
///   (`ApiService.skipSessionExpiryKey`), not a notifier flag. There is no
///   `_signingOut` boolean in `lib/` and there deliberately isn't one: a flag
///   could not cover a 401 arriving after the clear's timeout abandoned the
///   request.
void main() {
  setUp(() {
    // In-memory secure storage: the notifier writes/deletes JWTs on nearly
    // every path, and a real write throws MissingPluginException with no
    // platform behind the test.
    FlutterSecureStorage.setMockInitialValues({});
  });

  group('construction', () {
    test(
      'builds without touching real Firebase and reports the current user',
      () async {
        final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
        addTearDown(harness.dispose);

        final state = harness.container.read(authServiceProvider);

        expect(state.firebaseUser?.uid, 'ada');
        expect(
          state.isAuthenticated,
          isFalse,
        ); // no JWT until the exchange lands

        // build() kicks off the exchange unawaited; drain it before teardown so
        // it lands on a live Ref rather than a disposed one.
        await pumpEventQueue();
      },
    );
  });

  group('push registration wiring', () {
    test('a successful JWT exchange calls syncAfterLogin', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.container.read(authServiceProvider); // build the notifier

      await harness.signIn(_FakeUser(uid: 'ada'));

      expect(harness.push.calls, contains('syncAfterLogin'));
      expect(
        harness.container.read(authServiceProvider).jwtToken,
        'django-jwt',
      );
    });

    test('a FAILED exchange does not call syncAfterLogin', () async {
      // Guards the assertion above from passing on a syncAfterLogin that was
      // moved out of the success branch.
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.api.postError = ApiException('server down', statusCode: 500);
      harness.container.read(authServiceProvider);

      await harness.signIn(_FakeUser(uid: 'ada'));

      expect(harness.push.calls, isNot(contains('syncAfterLogin')));
    });

    test('signOut calls clearOnLogout', () async {
      final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);

      await harness.container.read(authServiceProvider.notifier).signOut();

      expect(harness.push.calls, contains('clearOnLogout'));
    });

    test('a signed-out auth state calls detach', () async {
      // Session expiry and external sign-outs reach this path WITHOUT
      // signOut(), so detach must hang off the auth-state listener, not off
      // the signOut() method.
      final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);
      harness.container.read(authServiceProvider);

      await harness.emitAuthState(null);

      expect(harness.push.calls, contains('detach'));
    });
  });

  group('account conflict (todo 447)', () {
    test('a 409 unverified_account offers the reset link', () async {
      // A Django account holds the email unverified: the one conflict the
      // user can clear by resetting its password, so main.dart shows the
      // link.
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.api.postError = ApiException(
        'Account linking conflict',
        statusCode: 409,
        code: 'unverified_account',
      );
      harness.container.read(authServiceProvider);

      await harness.signIn(_FakeUser(uid: 'ada'));

      final state = harness.container.read(authServiceProvider);
      expect(state.unverifiedAccountConflict, isTrue);
      expect(state.error, accountConflictMessage);
      expect(state.isAuthenticated, isFalse);
    });

    test('any other 409 says so without the reset link', () async {
      // Linked to another Firebase identity, or several accounts: a reset
      // would not help, so no link.
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.api.postError = ApiException(
        'Account linking conflict',
        statusCode: 409,
        code: 'account_conflict',
      );
      harness.container.read(authServiceProvider);

      await harness.signIn(_FakeUser(uid: 'ada'));

      final state = harness.container.read(authServiceProvider);
      expect(state.unverifiedAccountConflict, isFalse);
      expect(state.error, accountLinkFailedMessage);
    });

    test('a non-409 failure is not a conflict', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.api.postError = ApiException(
        'server down',
        statusCode: 500,
        code: 'unverified_account',
      );
      harness.container.read(authServiceProvider);

      await harness.signIn(_FakeUser(uid: 'ada'));

      final state = harness.container.read(authServiceProvider);
      expect(state.unverifiedAccountConflict, isFalse);
      expect(state.error, isNot(accountConflictMessage));
      expect(state.error, isNot(accountLinkFailedMessage));
    });

    test('copyWith clears the flag with the error', () {
      const conflicted = AuthState(
        error: accountConflictMessage,
        unverifiedAccountConflict: true,
      );

      expect(
        conflicted.copyWith(isLoading: true).unverifiedAccountConflict,
        isFalse,
      );
    });
  });

  group('email verification (todo 660)', () {
    test('registering sends the verification mail and reports that the '
        'email must be verified', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      final ada = _FakeUser(uid: 'ada', emailVerified: false);
      harness.firebaseAuth.createdUser = ada;
      harness.container.read(authServiceProvider);

      final needsVerification = await harness.container
          .read(authServiceProvider.notifier)
          .registerWithEmailPassword(
            email: 'ada@example.com',
            password: 'fake-pw-1', // pragma: allowlist secret
            displayName: 'Ada',
          );

      expect(needsVerification, isTrue);
      expect(ada.verificationEmailsSent, 1);
      expect(ada.displayName, 'Ada');
      expect(
        harness.container.read(authServiceProvider).emailVerificationRequired,
        isTrue,
      );
    });

    test('the exchange 403 (the view\'s JSON) says to verify the email, not '
        '"failed to connect"', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.api.postError = ApiException(
        'Email address must be verified before logging in.',
        statusCode: 403,
      );
      harness.container.read(authServiceProvider);

      await harness.signIn(_FakeUser(uid: 'ada', emailVerified: false));

      final state = harness.container.read(authServiceProvider);
      expect(state.error, emailNotVerifiedMessage);
      expect(state.emailVerificationRequired, isTrue);
      expect(state.isAuthenticated, isFalse);
      expect(state.firebaseUser?.uid, 'ada', reason: 'kept, so a retry works');
    });

    test('a proxy\'s HTML 403 is not read as an unverified email', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.api.postError = ApiException(
        'Forbidden',
        statusCode: 403,
        unstructured: true,
      );
      harness.container.read(authServiceProvider);

      await harness.signIn(_FakeUser(uid: 'ada'));

      final state = harness.container.read(authServiceProvider);
      expect(state.emailVerificationRequired, isFalse);
      expect(state.error, isNot(emailNotVerifiedMessage));
    });

    test(
      'an unverified user\'s exchange forces a token refresh, so a '
      'relaunch does not resend the cached email_verified=false token',
      () async {
        final ada = _FakeUser(uid: 'ada', emailVerified: false);
        final harness = _Harness(currentUser: ada);
        addTearDown(harness.dispose);
        harness.container.read(authServiceProvider);
        await pumpEventQueue();

        expect(ada.idTokenForceRefresh, [true]);
      },
    );

    test('a verified user\'s launch exchange keeps the cached token', () async {
      final ada = _FakeUser(uid: 'ada');
      final harness = _Harness(currentUser: ada);
      addTearDown(harness.dispose);
      harness.container.read(authServiceProvider);
      await pumpEventQueue();

      expect(ada.idTokenForceRefresh, [false]);
    });

    test('"I\'ve verified" reloads, forces a token refresh and completes the '
        'exchange without a relaunch', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.api.postError = ApiException(
        'Email address must be verified before logging in.',
        statusCode: 403,
      );
      final ada = _FakeUser(uid: 'ada', emailVerified: false);
      harness.container.read(authServiceProvider);
      await harness.signIn(ada);
      expect(
        harness.container.read(authServiceProvider).isAuthenticated,
        isFalse,
      );

      // The link is opened: the server now says verified.
      harness.api.postError = null;
      ada.onReload = () => ada.emailVerified = true;
      ada.idTokenForceRefresh.clear();

      final signedIn = await harness.container
          .read(authServiceProvider.notifier)
          .confirmEmailVerified();

      expect(signedIn, isTrue);
      expect(ada.reloads, 1);
      expect(ada.idTokenForceRefresh, [true]);
      final state = harness.container.read(authServiceProvider);
      expect(state.jwtToken, 'django-jwt');
      expect(state.emailVerificationRequired, isFalse);
      expect(harness.push.calls, contains('syncAfterLogin'));
    });

    test('"I\'ve verified" before the link is opened says so and sends '
        'nothing to the backend', () async {
      final ada = _FakeUser(uid: 'ada', emailVerified: false);
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.api.postError = ApiException('unverified', statusCode: 403);
      harness.container.read(authServiceProvider);
      await harness.signIn(ada);
      final postsBefore = harness.api.postCalls.length;

      final signedIn = await harness.container
          .read(authServiceProvider.notifier)
          .confirmEmailVerified();

      expect(signedIn, isFalse);
      expect(harness.api.postCalls.length, postsBefore);
      final state = harness.container.read(authServiceProvider);
      expect(state.error, emailStillUnverifiedMessage);
      expect(state.emailVerificationRequired, isTrue);
    });

    test('signing in again as the SAME Firebase user runs the exchange '
        'directly, with no auth-state event', () async {
      // A failed exchange leaves the Firebase user signed in; signing in
      // again with the same account changes no uid, so authStateChanges
      // fires nothing (todo 660).
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.api.postError = ApiException('unverified', statusCode: 403);
      final stale = _FakeUser(uid: 'ada', emailVerified: false);
      harness.container.read(authServiceProvider);
      await harness.signIn(stale);
      expect(
        harness.container.read(authServiceProvider).isAuthenticated,
        isFalse,
      );

      harness.api.postError = null;
      final fresh = _FakeUser(uid: 'ada'); // verified since
      harness.firebaseAuth.signInUser = fresh;

      final needsVerification = await harness.container
          .read(authServiceProvider.notifier)
          .signInWithEmailPassword('ada@example.com', 'secret1');

      expect(needsVerification, isFalse);
      expect(fresh.idTokenForceRefresh, [true]);
      expect(
        harness.container.read(authServiceProvider).jwtToken,
        'django-jwt',
      );
    });

    test('an unverified sign-in reports it and does not exchange', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.container.read(authServiceProvider);
      final ada = _FakeUser(uid: 'ada', emailVerified: false);
      harness.firebaseAuth.signInUser = ada;

      final needsVerification = await harness.container
          .read(authServiceProvider.notifier)
          .signInWithEmailPassword('ada@example.com', 'secret1');

      expect(needsVerification, isTrue);
      expect(ada.idTokenForceRefresh, isEmpty);
      expect(
        harness.container.read(authServiceProvider).emailVerificationRequired,
        isTrue,
      );
    });

    test('Resend sends the verification mail to the current user', () async {
      final ada = _FakeUser(uid: 'ada', emailVerified: false);
      final harness = _Harness(currentUser: ada);
      addTearDown(harness.dispose);
      harness.container.read(authServiceProvider);
      await pumpEventQueue();

      await harness.container
          .read(authServiceProvider.notifier)
          .resendVerificationEmail();

      expect(ada.verificationEmailsSent, 1);
    });
  });

  group('ordering', () {
    test('clearOnLogout runs BEFORE Firebase sign-out', () async {
      // The clear PATCH authenticates with the Django JWT, which sign-out
      // invalidates — reversing these silently breaks the server-side clear
      // while every other assertion in this file still passes.
      final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);

      await harness.container.read(authServiceProvider.notifier).signOut();

      expect(
        harness.events,
        containsAllInOrder(<String>['clearOnLogout', 'firebase.signOut']),
      );
    });
  });

  group('_authGeneration epoch guard', () {
    test('an exchange completing after sign-out does not write state', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.container.read(authServiceProvider);

      // Park the exchange on getIdToken, i.e. before the FIRST of the five
      // generation re-checks.
      final gate = Completer<String?>();
      final user = _FakeUser(uid: 'ada', getIdTokenOverride: () => gate.future);
      // signIn() returns once the stream event is delivered; the exchange it
      // starts runs unawaited inside the listener, so the pumpEventQueue()
      // after gate.complete() — not this call — is what resumes and drains it.
      await harness.signIn(user);

      await harness.container.read(authServiceProvider.notifier).signOut();
      gate.complete('firebase-id-token');
      await pumpEventQueue();

      final state = harness.container.read(authServiceProvider);
      expect(state.jwtToken, isNull, reason: 'stale exchange re-authenticated');
      expect(harness.api.postCalls, isEmpty, reason: 'aborted too late');
    });

    test('an exchange parked AFTER the network call also aborts', () async {
      // The exchange re-checks the generation at five points; parking on
      // getIdToken alone would leave the later four unpinned.
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.container.read(authServiceProvider);

      final gate = Completer<void>();
      harness.api.postGate = gate;
      await harness.signIn(_FakeUser(uid: 'ada'));

      await harness.container.read(authServiceProvider.notifier).signOut();
      gate.complete();
      await pumpEventQueue();

      expect(harness.container.read(authServiceProvider).jwtToken, isNull);
      expect(harness.push.calls, isNot(contains('syncAfterLogin')));
    });

    test('the generation bump alone kills a mid-sign-out exchange', () async {
      // The two tests above are satisfied by _isCurrentExchange's OTHER arm
      // (currentUser?.uid == user.uid), which Firebase sign-out already
      // breaks — so signOut()'s `_authGeneration++` could be deleted and both
      // would stay green (confirmed by mutation).
      //
      // This isolates it: resume the exchange while signOut is parked on
      // clearOnLogout, i.e. BEFORE _firebaseAuth.signOut() has cleared
      // currentUser. Only the generation guard can stop it there — and it
      // must, or the resumed exchange re-registers push after the clear.
      final harness = _Harness();
      addTearDown(harness.dispose);

      final postGate = Completer<void>();
      harness.api.postGate = postGate;
      await harness.signIn(_FakeUser(uid: 'ada'));

      final logoutGate = Completer<void>();
      harness.push.clearOnLogoutGate = logoutGate;
      final signOut = harness.container
          .read(authServiceProvider.notifier)
          .signOut();
      await pumpEventQueue();
      expect(harness.firebaseAuth.currentUser, isNotNull, reason: 'premise');

      postGate.complete();
      await pumpEventQueue();

      expect(
        harness.push.calls,
        isNot(contains('syncAfterLogin')),
        reason: 'exchange re-registered push during sign-out',
      );

      logoutGate.complete();
      await signOut;
      expect(harness.container.read(authServiceProvider).jwtToken, isNull);
    });
  });

  group('session expiry', () {
    test(
      'build() registers _handleSessionExpired, and it signs the user out',
      () async {
        // Without this, the whole exemption group below is unfalsifiable from
        // AuthService's side: deleting build()'s
        // `apiService.setSessionExpiredHandler(_handleSessionExpired)` would
        // leave every other test green while 401s stopped signing anyone out.
        final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
        addTearDown(harness.dispose);
        await pumpEventQueue(); // let build()'s exchange settle

        final handler = harness.api.sessionExpiredHandler;
        expect(handler, isNotNull, reason: 'build() registered no handler');

        await handler!();
        await pumpEventQueue();

        final state = harness.container.read(authServiceProvider);
        expect(state.error, 'Your session expired. Please sign in again.');
        expect(state.jwtToken, isNull);
        expect(harness.events, contains('firebase.signOut'));
      },
    );

    test('the handler is unregistered when the notifier is disposed', () async {
      // The handler closes over a Ref; leaving it installed on the shared
      // ApiService after disposal is how "Cannot use Ref after dispose"
      // reaches production.
      final harness = _Harness();
      await pumpEventQueue();
      expect(harness.api.sessionExpiredHandler, isNotNull);

      harness.dispose();

      expect(harness.api.sessionExpiredHandler, isNull);
    });

    test('clears the account profile a screen still watches, so the previous '
        'user\'s username does not outlive the session in `.value` '
        '(todo 520)', () async {
      // A mounted forum screen reads the profile's `.value`, which keeps the
      // last profile through a reload and a failed refresh (todo 507). Only
      // the profile-screen logout cleared it; a session-expiry sign-out left
      // the old username in place until that screen unmounted.
      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        overrides: [
          userProfileServiceProvider.overrideWith(
            () => _FakeUserProfileService('ada'),
          ),
        ],
      );
      addTearDown(harness.dispose);
      await pumpEventQueue();

      // The screen's watch: the provider is autoDispose, so without a
      // listener there would be nothing alive to clear.
      final watching = harness.container.listen(
        userProfileServiceProvider,
        (_, _) {},
      );
      addTearDown(watching.close);
      await harness.container.read(userProfileServiceProvider.future);
      expect(
        harness.container.read(userProfileServiceProvider).value?.username,
        'ada',
      );

      await harness.api.sessionExpiredHandler!();
      await pumpEventQueue();

      // `clear()` lands AsyncData(null): not a reload, which would keep the
      // old profile in `.value` while it re-fetched, and not an error.
      final profile = harness.container.read(userProfileServiceProvider);
      expect(profile.value, isNull);
      expect(profile.isLoading, isFalse);
      expect(profile.hasError, isFalse);
      expect(harness.events, contains('firebase.signOut'));
    });

    test('does not build an account profile nothing is watching', () async {
      // The provider is autoDispose: an unguarded read would build it just to
      // clear it, and that build fetches `/auth/user/` — anonymous, now that
      // the bearer is gone.
      var builds = 0;
      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        overrides: [
          userProfileServiceProvider.overrideWith(() {
            builds++;
            return _FakeUserProfileService('ada');
          }),
        ],
      );
      addTearDown(harness.dispose);
      await pumpEventQueue();

      await harness.api.sessionExpiredHandler!();
      await pumpEventQueue();

      expect(builds, 0);
      expect(harness.events, contains('firebase.signOut'));
    });
  });

  group('account profile across a re-login (todo 520)', () {
    // The session-expiry sign-out above clears the profile a mounted screen
    // holds, and nothing fetched it again. The provider is autoDispose, but a
    // watcher on an OFFSTAGE tab keeps it alive: go_router wraps an inactive
    // shell branch in `TickerMode(enabled: false)`, flutter_riverpod pauses a
    // widget's subscriptions under it, and Riverpod never disposes a provider
    // that still has (paused) listeners. So after a re-login through the
    // pushed sign-in screen — the shell, and that watcher, still mounted —
    // ProfileScreen read `AsyncData(null)` as "No profile data available": a
    // data state, so no Retry, until the process restarted. A completed
    // sign-in now invalidates the provider.

    test('a re-login after a session expiry fetches the profile a screen '
        'still holds again', () async {
      final builds = _ProfileBuilds();
      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        overrides: [builds.override],
      );
      addTearDown(harness.dispose);
      await pumpEventQueue();
      final watching = harness.container.listen(
        userProfileServiceProvider,
        (_, _) {},
      );
      addTearDown(watching.close);
      await harness.container.read(userProfileServiceProvider.future);
      expect(builds.count, 1);

      await harness.api.sessionExpiredHandler!();
      await harness.emitAuthState(null); // Firebase reports the sign-out
      expect(harness.container.read(userProfileServiceProvider).value, isNull);

      await harness.signIn(_FakeUser(uid: 'ada'));
      final profile = await harness.container.read(
        userProfileServiceProvider.future,
      );

      expect(
        harness.container.read(authServiceProvider).jwtToken,
        'django-jwt',
      );
      expect(builds.count, 2, reason: 'the cleared profile was not re-fetched');
      expect(profile?.username, 'ada');
      final settled = harness.container.read(userProfileServiceProvider);
      expect(settled.isLoading, isFalse);
      expect(settled.hasError, isFalse);
    });

    test('a paused watcher (an offstage tab) keeps the cleared profile alive, '
        'and the first read after the re-login fetches it again', () async {
      final builds = _ProfileBuilds();
      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        overrides: [builds.override],
      );
      addTearDown(harness.dispose);
      await pumpEventQueue();
      final watching = harness.container.listen(
        userProfileServiceProvider,
        (_, _) {},
      );
      addTearDown(watching.close);
      await harness.container.read(userProfileServiceProvider.future);
      // The forum tab goes offstage: what flutter_riverpod's
      // ConsumerStatefulElement does to its subscriptions under a disabled
      // TickerMode (`_applyTickerMode`).
      watching.pause();
      await pumpEventQueue();
      expect(
        harness.container.exists(userProfileServiceProvider),
        isTrue,
        reason: 'a paused listener still keeps an autoDispose provider',
      );

      await harness.api.sessionExpiredHandler!();
      await harness.emitAuthState(null);
      await harness.signIn(_FakeUser(uid: 'ada'));
      await pumpEventQueue();

      // Riverpod rebuilds an invalidated provider only when something
      // actively listens, so with its one watcher paused the re-login left it
      // cleared, marked for a rebuild on its next read.
      expect(
        harness.container.read(authServiceProvider).jwtToken,
        'django-jwt',
      );
      expect(builds.count, 1, reason: 'premise: the rebuild is deferred');

      // ProfileScreen's fresh watch, once the sign-in screen pops.
      final profile = await harness.container.read(
        userProfileServiceProvider.future,
      );
      expect(profile?.username, 'ada');
      expect(builds.count, 2);

      // The tab comes back on-screen: nothing left to rebuild.
      watching.resume();
      await pumpEventQueue();
      expect(builds.count, 2);
      expect(
        harness.container.read(userProfileServiceProvider).value?.username,
        'ada',
      );
    });

    test('a refresh that completes a login the launch exchange failed '
        'fetches it again too', () async {
      // The other way a login completes (todo 498): whatever holds the
      // profile then is fetched again the same way.
      final builds = _ProfileBuilds();
      final harness = _Harness(overrides: [builds.override]);
      addTearDown(harness.dispose);
      harness.api.postError = ApiException('server down', statusCode: 500);
      harness.container.read(authServiceProvider);
      await harness.signIn(_FakeUser(uid: 'ada'));
      expect(harness.container.read(authServiceProvider).jwtToken, isNull);
      final watching = harness.container.listen(
        userProfileServiceProvider,
        (_, _) {},
      );
      addTearDown(watching.close);
      await harness.container.read(userProfileServiceProvider.future);
      expect(builds.count, 1);

      harness.api.postError = null;
      expect(await harness.api.accessTokenRefresher!(), 'django-jwt');
      await harness.container.read(userProfileServiceProvider.future);

      expect(builds.count, 2);
    });

    test('a same-session token refresh does not fetch it again', () async {
      final builds = _ProfileBuilds();
      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        overrides: [builds.override],
      );
      addTearDown(harness.dispose);
      await pumpEventQueue(); // the launch exchange signs the user in
      final watching = harness.container.listen(
        userProfileServiceProvider,
        (_, _) {},
      );
      addTearDown(watching.close);
      await harness.container.read(userProfileServiceProvider.future);
      harness.api.nextAccessToken = 'django-jwt-2';

      expect(await harness.api.accessTokenRefresher!(), 'django-jwt-2');
      await pumpEventQueue();

      expect(builds.count, 1, reason: 'a token refresh is not a login');
      expect(
        harness.container.read(userProfileServiceProvider).value?.username,
        'ada',
      );
    });

    test('a completed sign-in builds no profile nothing holds', () async {
      // `ref.invalidate` on a provider that is not alive is a no-op, so there
      // is no `ref.exists` guard: a screen's first watch builds it, under the
      // new bearer, when it is wanted.
      final builds = _ProfileBuilds();
      final harness = _Harness(overrides: [builds.override]);
      addTearDown(harness.dispose);
      harness.container.read(authServiceProvider);

      await harness.signIn(_FakeUser(uid: 'ada'));
      await pumpEventQueue();

      expect(
        harness.container.read(authServiceProvider).jwtToken,
        'django-jwt',
      );
      expect(builds.count, 0);
      expect(harness.container.exists(userProfileServiceProvider), isFalse);
    });
  });

  group('account profile across sign-outs (todo 558)', () {
    Future<(_Harness, ProviderSubscription<AsyncValue<UserProfile?>>)> watched(
      List<Override> overrides,
    ) async {
      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        overrides: overrides,
      );
      addTearDown(harness.dispose);
      await pumpEventQueue();
      final watching = harness.container.listen(
        userProfileServiceProvider,
        (_, _) {},
      );
      addTearDown(watching.close);
      await harness.container.read(userProfileServiceProvider.future);
      return (harness, watching);
    }

    test('#1: a second expiry under a paused watcher sends no bearerless '
        'profile fetch', () async {
      // The re-login's invalidate is deferred under the paused watcher, so
      // the element is dirty; the expiry's `.notifier` read flushes it. Its
      // build() used to GET /auth/user/ just after setAuthToken(null).
      final fetches = <bool>[];
      final (harness, watching) = await watched([
        userProfileServiceProvider.overrideWith(
          () => _FetchRecordingUserProfileService(fetches),
        ),
      ]);
      expect(fetches, [true]);
      watching.pause();

      await harness.api.sessionExpiredHandler!();
      await harness.emitAuthState(null);
      await harness.signIn(_FakeUser(uid: 'ada'));
      await harness.api.sessionExpiredHandler!();
      await harness.emitAuthState(null);
      await pumpEventQueue();

      expect(
        fetches,
        isNot(contains(false)),
        reason:
            'a fetch went out with '
            'no bearer',
      );
      final profile = harness.container.read(userProfileServiceProvider);
      expect(profile.value, isNull);
      expect(profile.hasError, isFalse);
    });

    test('#1: with no bearer, build() returns no profile and sends no '
        'request', () async {
      final fetches = <bool>[];
      final harness = _Harness(
        overrides: [
          userProfileServiceProvider.overrideWith(
            () => _FetchRecordingUserProfileService(fetches),
          ),
        ],
      );
      addTearDown(harness.dispose);

      final profile = await harness.container.read(
        userProfileServiceProvider.future,
      );

      expect(profile, isNull);
      expect(fetches, isEmpty);
    });

    test('#2: an external Firebase sign-out clears the profile a screen '
        'still watches', () async {
      // A revoked token or a disabled account: Firebase reports the
      // sign-out, and no session-expiry handler runs.
      final (harness, _) = await watched([
        userProfileServiceProvider.overrideWith(
          () => _FakeUserProfileService('ada'),
        ),
      ]);
      expect(
        harness.container.read(userProfileServiceProvider).value?.username,
        'ada',
      );

      await harness.emitAuthState(null);

      final profile = harness.container.read(userProfileServiceProvider);
      expect(profile.value, isNull);
      expect(profile.hasError, isFalse);
      expect(harness.container.read(authServiceProvider).jwtToken, isNull);
    });

    test('#3: the profile is held until the auth state flips', () async {
      final (harness, _) = await watched([
        userProfileServiceProvider.overrideWith(
          () => _FakeUserProfileService('ada'),
        ),
      ]);
      final gate = harness.firebaseAuth.signOutGate = Completer<void>();

      final expiry = harness.api.sessionExpiredHandler!();
      await pumpEventQueue();

      // Mid-sign-out: still authenticated, so the profile must still be
      // there; an identity-less signed-in screen was the bug.
      expect(
        harness.container.read(authServiceProvider).isAuthenticated,
        isTrue,
      );
      expect(
        harness.container.read(userProfileServiceProvider).value?.username,
        'ada',
      );

      gate.complete();
      await expiry;

      expect(
        harness.container.read(authServiceProvider).isAuthenticated,
        isFalse,
      );
      expect(harness.container.read(userProfileServiceProvider).value, isNull);
    });

    test('#4: the post-login fetch is a reload, so the profile screen shows '
        'its spinner, not "No profile data available"', () async {
      final builds = _ProfileBuilds();
      final (harness, _) = await watched([builds.override]);
      await harness.api.sessionExpiredHandler!();
      await harness.emitAuthState(null);
      expect(harness.container.read(userProfileServiceProvider).value, isNull);

      final states = <AsyncValue<UserProfile?>>[];
      final recording = harness.container.listen(
        userProfileServiceProvider,
        (_, next) => states.add(next),
      );
      addTearDown(recording.close);
      await harness.signIn(_FakeUser(uid: 'ada'));
      await harness.container.read(userProfileServiceProvider.future);

      // A refresh over AsyncData(null) would be `isRefreshing`, which
      // `when()` skips by default.
      expect(
        states.any((s) => s.isLoading && !s.isRefreshing),
        isTrue,
        reason: 'states: $states',
      );
      expect(builds.count, 2);
      expect(
        harness.container.read(userProfileServiceProvider).value?.username,
        'ada',
      );
    });
  });

  group('access-token refresh (todo 462)', () {
    test('build() registers a refresher that re-exchanges the Firebase token '
        'without signing out or re-running push registration', () async {
      final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);
      await pumpEventQueue(); // let build()'s launch exchange settle

      final refresher = harness.api.accessTokenRefresher;
      expect(refresher, isNotNull, reason: 'build() registered no refresher');
      final syncsBefore = harness.push.calls
          .where((c) => c == 'syncAfterLogin')
          .length;
      harness.api.nextAccessToken = 'django-jwt-2';

      final token = await refresher!();

      expect(token, 'django-jwt-2');
      final state = harness.container.read(authServiceProvider);
      expect(state.jwtToken, 'django-jwt-2');
      expect(state.error, isNull);
      expect(harness.api.currentToken, 'django-jwt-2');
      expect(harness.events, isNot(contains('firebase.signOut')));
      expect(
        harness.push.calls.where((c) => c == 'syncAfterLogin').length,
        syncsBefore,
        reason: 'a token refresh is not a login',
      );

      // The refresh's own exchange may neither refresh again nor sign out.
      final exchange = harness.api.postCalls.last;
      expect(exchange.path, '/auth/firebase-token-exchange/');
      expect(exchange.data, {'firebase_token': 'firebase-id-token'});
      expect(exchange.options?.extra?[ApiService.skipAuthRefreshKey], isTrue);
      expect(exchange.options?.extra?[ApiService.skipSessionExpiryKey], isTrue);
    });

    test('the launch exchange 401 goes straight to sign-out, not to a '
        'refresh', () async {
      final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);
      await pumpEventQueue();

      final launch = harness.api.postCalls.single;
      expect(launch.options?.extra?[ApiService.skipAuthRefreshKey], isTrue);
      expect(launch.options?.extra?[ApiService.skipSessionExpiryKey], isNull);
    });

    test('a failed re-exchange returns null, and the sign-out that follows '
        'keeps the current message', () async {
      final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);
      await pumpEventQueue();
      harness.api.postError = ApiException(
        'Invalid Firebase token',
        statusCode: 401,
      );

      expect(await harness.api.accessTokenRefresher!(), isNull);
      // The refresher itself does not sign out: ApiService does, once.
      expect(harness.events, isNot(contains('firebase.signOut')));

      await harness.api.sessionExpiredHandler!();
      await pumpEventQueue();
      final state = harness.container.read(authServiceProvider);
      expect(state.error, 'Your session expired. Please sign in again.');
      expect(state.jwtToken, isNull);
      expect(harness.events, contains('firebase.signOut'));
    });

    test('with no Firebase user there is nothing to refresh', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      await pumpEventQueue();

      // Overtaken, not refused (todo 500 F2): nobody is left to sign out.
      await expectLater(
        harness.api.accessTokenRefresher!(),
        throwsA(isA<RefreshSupersededException>()),
      );
      expect(harness.api.postCalls, isEmpty);
    });

    test('a refresh overtaken by sign-out does not re-authenticate', () async {
      final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);
      await pumpEventQueue();

      final gate = Completer<void>();
      harness.api.postGate = gate;
      final refresh = harness.api.accessTokenRefresher!();
      await pumpEventQueue();
      await harness.container.read(authServiceProvider.notifier).signOut();
      gate.complete();

      // Overtaken, not refused (todo 500 F2).
      await expectLater(refresh, throwsA(isA<RefreshSupersededException>()));
      expect(harness.container.read(authServiceProvider).jwtToken, isNull);
      expect(harness.api.currentToken, isNull);
    });

    test(
      'the refresher is unregistered when the notifier is disposed',
      () async {
        final harness = _Harness();
        await pumpEventQueue();
        expect(harness.api.accessTokenRefresher, isNotNull);

        harness.dispose();

        expect(harness.api.accessTokenRefresher, isNull);
      },
    );

    test('over real HTTP, an expired token is refreshed through a bearer-less '
        'exchange and the request succeeds without a sign-out', () async {
      // The backend authenticates any bearer before the exchange view runs,
      // so an exchange that carried the expired token would 401 and sign the
      // user out on every real expiry. The loopback server does the same.
      final savedOverrides = HttpOverrides.current;
      HttpOverrides.global = null;
      addTearDown(() => HttpOverrides.global = savedOverrides);
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      addTearDown(() => server.close(force: true));
      final seen = <(String, String?)>[];
      server.listen((request) async {
        await request.drain<void>();
        final auth = request.headers.value(HttpHeaders.authorizationHeader);
        seen.add((request.uri.path, auth));
        final isExchange = request.uri.path == '/auth/firebase-token-exchange/';
        final ok = isExchange ? auth == null : auth == 'Bearer fresh';
        request.response
          ..statusCode = ok ? HttpStatus.ok : HttpStatus.unauthorized
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode(
              !ok
                  ? {'detail': 'Token is expired'}
                  : isExchange
                  ? {'access_token': 'fresh', 'refresh_token': 'refresh'}
                  : {'ok': true},
            ),
          );
        await request.response.close();
      });

      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        baseUrl: 'http://${server.address.host}:${server.port}',
      );
      addTearDown(harness.dispose);
      await pumpEventQueue(); // the launch exchange (faked) settles
      harness.api.realHttp = true;
      harness.api.setAuthToken('expired');

      final response = await harness.api.get('/forum/topics/');

      expect(response.statusCode, 200);
      expect(seen, [
        ('/forum/topics/', 'Bearer expired'),
        ('/auth/firebase-token-exchange/', null),
        ('/forum/topics/', 'Bearer fresh'),
      ]);
      final state = harness.container.read(authServiceProvider);
      expect(state.jwtToken, 'fresh');
      expect(state.error, isNull);
      expect(harness.events, isNot(contains('firebase.signOut')));
    });
  });

  group('refused vs transient refresh failures (todo 498)', () {
    Future<_Harness> signedIn({User? user}) async {
      final harness = _Harness(currentUser: user ?? _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);
      await pumpEventQueue(); // the launch exchange (faked) settles
      return harness;
    }

    // 409 left this set in todo 500 (F1): see 'an exchange 409 keeps the
    // user signed in…' below.
    for (final status in [401, 403]) {
      test('an exchange $status refuses the session: the refresher returns '
          'null', () async {
        final harness = await signedIn();
        harness.api.postError = ApiException('refused', statusCode: status);

        expect(await harness.api.accessTokenRefresher!(), isNull);
      });
    }

    for (final status in [null, 429, 500, 503]) {
      test('an exchange failing with ${status ?? 'no response'} is transient: '
          'the refresher throws it rather than returning null', () async {
        final harness = await signedIn();
        final failure = ApiException('try again', statusCode: status);
        harness.api.postError = failure;

        await expectLater(
          harness.api.accessTokenRefresher!(),
          throwsA(same(failure)),
        );
        expect(harness.events, isNot(contains('firebase.signOut')));
      });
    }

    test('a Firebase network error is transient, a disabled user is '
        'refused', () async {
      var code = 'network-request-failed';
      final harness = await signedIn(
        user: _FakeUser(
          uid: 'ada',
          getIdTokenOverride: () async {
            throw FirebaseAuthException(code: code);
          },
        ),
      );

      await expectLater(
        harness.api.accessTokenRefresher!(),
        throwsA(isA<FirebaseAuthException>()),
      );

      code = 'user-disabled';
      expect(await harness.api.accessTokenRefresher!(), isNull);
    });

    test('over real HTTP, a 503 from the exchange leaves the user signed in, '
        'fails the request as a session-refresh failure, and the next 401 '
        'refreshes again', () async {
      final backend = await _LoopbackBackend.start();
      addTearDown(backend.close);
      backend.exchangeStatus = HttpStatus.serviceUnavailable;
      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        baseUrl: backend.baseUrl,
      );
      addTearDown(harness.dispose);
      await pumpEventQueue();
      var sessionExpiredCalls = 0;
      final handler = harness.api.sessionExpiredHandler!;
      harness.api.setSessionExpiredHandler(() async {
        sessionExpiredCalls++;
        await handler();
      });
      harness.api.realHttp = true;
      harness.api.setAuthToken('expired');

      // Its own error, not the exchange's 503 (todo 500 F5), which would
      // read as the endpoint's outage.
      await expectLater(
        harness.api.get('/forum/topics/'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', isNull)
              .having((e) => e.code, 'code', sessionRefreshUnavailableCode),
        ),
      );
      final state = harness.container.read(authServiceProvider);
      expect(state.jwtToken, isNotNull, reason: 'a 503 signed the user out');
      expect(state.error, isNull);
      expect(harness.events, isNot(contains('firebase.signOut')));
      expect(sessionExpiredCalls, 0);

      backend.exchangeStatus = HttpStatus.ok;
      final response = await harness.api.get('/forum/topics/');

      expect(response.statusCode, 200);
      expect(backend.seen.map((r) => r.$1), [
        '/forum/topics/',
        '/auth/firebase-token-exchange/',
        '/forum/topics/',
        '/auth/firebase-token-exchange/',
        '/forum/topics/',
      ]);
      expect(harness.container.read(authServiceProvider).jwtToken, 'fresh');
      expect(sessionExpiredCalls, 0);
    });

    test(
      'over real HTTP, a refused exchange signs the user out once',
      () async {
        final backend = await _LoopbackBackend.start();
        addTearDown(backend.close);
        backend.exchangeStatus = HttpStatus.forbidden;
        final harness = _Harness(
          currentUser: _FakeUser(uid: 'ada'),
          baseUrl: backend.baseUrl,
        );
        addTearDown(harness.dispose);
        await pumpEventQueue();
        harness.api.realHttp = true;
        harness.api.setAuthToken('expired');

        await expectLater(
          harness.api.get('/forum/topics/'),
          throwsA(
            isA<ApiException>().having((e) => e.statusCode, 'statusCode', 401),
          ),
        );
        await pumpEventQueue();

        final state = harness.container.read(authServiceProvider);
        expect(state.jwtToken, isNull);
        expect(state.error, 'Your session expired. Please sign in again.');
        expect(
          harness.events.where((e) => e == 'firebase.signOut'),
          hasLength(1),
        );
      },
    );

    test('a refresh that finishes while signOut() is clearing the FCM token '
        'does not report "session expired"', () async {
      // Finding 2: signOut() cleared the API token only at its very end, so a
      // refresh landing during clearOnLogout read as refused.
      final backend = await _LoopbackBackend.start();
      addTearDown(backend.close);
      final exchangeGate = Completer<void>();
      backend.holds['/auth/firebase-token-exchange/'] = exchangeGate.future;
      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        baseUrl: backend.baseUrl,
      );
      addTearDown(harness.dispose);
      await pumpEventQueue();
      harness.api.realHttp = true;
      harness.api.setAuthToken('expired');

      final read = harness.api
          .get('/forum/topics/')
          .then<Object?>((r) => r, onError: (Object e) => e);
      await waitUntil(
        () => backend.seen.length >= 2,
        'the refresh to reach the exchange',
      );

      final logoutGate = Completer<void>();
      harness.push.clearOnLogoutGate = logoutGate;
      final signOut = harness.container
          .read(authServiceProvider.notifier)
          .signOut();
      await pumpEventQueue();
      exchangeGate.complete(); // the refresh finishes mid-clear
      expect(await read, isA<ApiException>());
      await pumpEventQueue();

      expect(
        harness.events,
        isNot(contains('firebase.signOut')),
        reason: 'the refresh signed out while signOut() held the clear',
      );
      expect(
        harness.container.read(authServiceProvider).error,
        isNot('Your session expired. Please sign in again.'),
      );

      logoutGate.complete();
      await signOut;
      final state = harness.container.read(authServiceProvider);
      expect(state.error, isNull);
      expect(state.jwtToken, isNull);
      expect(
        harness.events.where((e) => e == 'firebase.signOut'),
        hasLength(1),
      );
    });

    test('over real HTTP, a request sent while the launch exchange runs is '
        're-sent with the JWT it installs, not failed as expired', () async {
      // The launch exchange clears the token first (a new session). The JWT
      // it then installs completes that session rather than starting
      // another, or an anonymous request from the gap whose 401 lands after
      // it would read as from an ended session.
      final backend = await _LoopbackBackend.start();
      addTearDown(backend.close);
      final exchangeGate = Completer<void>();
      final readGate = Completer<void>();
      backend.holds['/auth/firebase-token-exchange/'] = exchangeGate.future;
      backend.holds['/forum/topics/'] = readGate.future;
      final harness = _Harness(baseUrl: backend.baseUrl);
      addTearDown(harness.dispose);
      harness.container.read(authServiceProvider);
      harness.api.realHttp = true;

      await harness.signIn(_FakeUser(uid: 'ada')); // the exchange is held
      final read = harness.api.get('/forum/topics/'); // goes out anonymous
      await waitUntil(
        () => backend.seen.length >= 2,
        'the read to reach the server',
      );
      exchangeGate.complete();
      await waitUntil(
        () => harness.api.currentToken == 'fresh',
        'the launch exchange to install its JWT',
      );
      readGate.complete(); // its 401 lands after the JWT is installed

      expect((await read).statusCode, 200);
      expect(backend.seen.last, ('/forum/topics/', 'Bearer fresh'));
      expect(harness.events, isNot(contains('firebase.signOut')));
    });

    test('a refresh that completes a login the launch exchange failed '
        'registers push', () async {
      // Finding 6.
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.api.postError = ApiException('server down', statusCode: 500);
      harness.container.read(authServiceProvider);
      await harness.signIn(_FakeUser(uid: 'ada'));
      expect(harness.container.read(authServiceProvider).jwtToken, isNull);
      expect(harness.push.calls, isNot(contains('syncAfterLogin')));

      harness.api.postError = null;
      expect(await harness.api.accessTokenRefresher!(), 'django-jwt');
      await pumpEventQueue();

      expect(harness.push.calls, contains('syncAfterLogin'));
    });
  });

  group('todo 500', () {
    Future<_Harness> signedInOver(
      _LoopbackBackend backend, {
      bool useRealPushService = false,
    }) async {
      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        baseUrl: backend.baseUrl,
        useRealPushService: useRealPushService,
      );
      addTearDown(harness.dispose);
      await pumpEventQueue(); // the launch exchange (faked) settles
      return harness;
    }

    test('F1: an exchange 409 keeps the user signed in and the conflict on '
        'screen, never "session expired"', () async {
      final backend = await _LoopbackBackend.start();
      addTearDown(backend.close);
      backend.exchangeStatus = HttpStatus.conflict;
      backend.exchangeBody = {
        'error': 'Account linking conflict',
        'code': 'unverified_account',
      };
      final harness = await signedInOver(backend);
      var sessionExpiredCalls = 0;
      final handler = harness.api.sessionExpiredHandler!;
      harness.api.setSessionExpiredHandler(() async {
        sessionExpiredCalls++;
        await handler();
      });
      harness.api.realHttp = true;
      harness.api.setAuthToken('expired');

      await expectLater(
        harness.api.get('/forum/topics/'),
        throwsA(isA<ApiException>()),
      );
      await pumpEventQueue();

      expect(sessionExpiredCalls, 0, reason: 'a 409 signed the user out');
      expect(harness.events, isNot(contains('firebase.signOut')));
      final state = harness.container.read(authServiceProvider);
      expect(state.error, accountConflictMessage);
      expect(state.unverifiedAccountConflict, isTrue);
      expect(state.firebaseUser?.uid, 'ada');
    });

    test(
      'F1: any other 409 says the link failed, without the reset offer',
      () async {
        final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
        addTearDown(harness.dispose);
        await pumpEventQueue();
        harness.api.postError = ApiException(
          'Account linking conflict',
          statusCode: 409,
          code: 'account_conflict',
        );

        await expectLater(
          harness.api.accessTokenRefresher!(),
          throwsA(isA<ApiException>()),
        );
        final state = harness.container.read(authServiceProvider);
        expect(state.error, accountLinkFailedMessage);
        expect(state.unverifiedAccountConflict, isFalse);
        expect(harness.events, isNot(contains('firebase.signOut')));
      },
    );

    test('F2: a refresh whose Firebase user changed under it signs nobody '
        'out', () async {
      final backend = await _LoopbackBackend.start();
      addTearDown(backend.close);
      final exchangeGate = Completer<void>();
      backend.holds['/auth/firebase-token-exchange/'] = exchangeGate.future;
      final harness = await signedInOver(backend);
      var sessionExpiredCalls = 0;
      final handler = harness.api.sessionExpiredHandler!;
      harness.api.setSessionExpiredHandler(() async {
        sessionExpiredCalls++;
        await handler();
      });
      harness.api.realHttp = true;
      harness.api.setAuthToken('expired');

      final read = harness.api
          .get('/forum/topics/')
          .then<Object?>((r) => r, onError: (Object e) => e);
      await waitUntil(
        () => backend.seen.length >= 2,
        'the refresh to reach the exchange',
      );
      // B is current before the auth-state listener has heard of it.
      harness.firebaseAuth.currentUser = _FakeUser(uid: 'bea');
      exchangeGate.complete();

      expect(await read, isA<ApiException>());
      await pumpEventQueue();
      expect(sessionExpiredCalls, 0, reason: 'B was signed out for A');
      expect(harness.events, isNot(contains('firebase.signOut')));
    });

    test('F3: a sign-out whose FCM clear 401s with no JWT re-sends the clear '
        'and registers nothing after it', () async {
      final backend = await _LoopbackBackend.start();
      addTearDown(backend.close);
      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        baseUrl: backend.baseUrl,
        useRealPushService: true,
      );
      addTearDown(harness.dispose);
      // The launch exchange fails: signed in to Firebase, no JWT.
      harness.api.postError = ApiException('server down', statusCode: 500);
      harness.container.read(authServiceProvider);
      await pumpEventQueue();
      expect(harness.container.read(authServiceProvider).jwtToken, isNull);
      // A registration from earlier is still live on the server. Since
      // todo 621 it is a POST, which postError would fail, so the error is
      // lifted first; the launch exchange has already failed.
      harness.api.postError = null;
      await harness.realPush!.registerToken('device-token-1');
      harness.api.realHttp = true;

      await harness.container.read(authServiceProvider.notifier).signOut();
      await waitUntil(
        () =>
            backend.bodies
                .where((b) => b.$1 == '/push-devices/unregister/')
                .length >=
            2,
        'the clear and its re-send',
      );
      // Give a stray syncAfterLogin time to register.
      await Future<void>.delayed(const Duration(milliseconds: 50));
      await pumpEventQueue();

      // Todo 621: sign-out unregisters this device by its token.
      final clears = [
        for (final b in backend.bodies)
          if (b.$1 == '/push-devices/unregister/') b.$2,
      ];
      expect(clears, [
        {'token': 'device-token-1'},
        {'token': 'device-token-1'},
      ]);
      expect(
        backend.bodies.where((b) => b.$1 == '/push-devices/'),
        isEmpty,
        reason: 'the refresh re-registered push mid-sign-out',
      );
      expect(
        backend.seen.where((r) => r.$1 == '/push-devices/unregister/').last.$2,
        'Bearer fresh',
      );
      final state = harness.container.read(authServiceProvider);
      expect(state.jwtToken, isNull);
      expect(state.error, isNull);
    });

    test('F3: a 401 while the launch exchange runs completes the login once: '
        'push is registered once', () async {
      final backend = await _LoopbackBackend.start();
      addTearDown(backend.close);
      final launchGate = Completer<void>();
      backend.holds['/auth/firebase-token-exchange/'] = launchGate.future;
      final harness = _Harness(baseUrl: backend.baseUrl);
      addTearDown(harness.dispose);
      harness.container.read(authServiceProvider);
      harness.api.realHttp = true;

      await harness.signIn(_FakeUser(uid: 'ada')); // the launch is held
      final read = await harness.api.get('/forum/topics/'); // 401 → refresh
      expect(read.statusCode, 200);
      launchGate.complete();
      await waitUntil(
        () => backend.seen.where((r) => r.$1.contains('exchange')).length >= 2,
        'both exchanges',
      );
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await pumpEventQueue();

      expect(
        harness.push.calls.where((c) => c == 'syncAfterLogin'),
        hasLength(1),
      );
      expect(harness.container.read(authServiceProvider).jwtToken, 'fresh');
    });

    test('F8: a 401 or 403 that is not the view\'s JSON (a proxy page) is '
        'transient, not a refusal', () async {
      final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);
      await pumpEventQueue();
      for (final status in [401, 403]) {
        harness.api.postError = ApiException(
          '<html>Forbidden</html>',
          statusCode: status,
          unstructured: true,
        );
        await expectLater(
          harness.api.accessTokenRefresher!(),
          throwsA(isA<ApiException>()),
          reason: 'an HTML $status signed the user out',
        );
      }
    });

    test('a user switch A→B clears A\'s bearer before B\'s exchange '
        'returns', () async {
      final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);
      await pumpEventQueue();
      expect(harness.api.currentToken, 'django-jwt');

      final gate = Completer<void>();
      harness.api.postGate = gate;
      harness.api.nextAccessToken = 'bea-jwt';
      final switching = harness.signIn(_FakeUser(uid: 'bea'));
      await pumpEventQueue();
      expect(
        harness.api.currentToken,
        isNull,
        reason: "B's requests would go out under A's token",
      );

      gate.complete();
      await switching;
      await pumpEventQueue();
      expect(harness.api.currentToken, 'bea-jwt');
    });

    test('Firebase handing back no ID token is transient', () async {
      final harness = _Harness(
        currentUser: _FakeUser(
          uid: 'ada',
          getIdTokenOverride: () async => null,
        ),
      );
      addTearDown(harness.dispose);
      await pumpEventQueue();

      await expectLater(
        harness.api.accessTokenRefresher!(),
        throwsA(isA<AuthException>()),
      );
      expect(harness.events, isNot(contains('firebase.signOut')));
    });
  });

  group('todo 567', () {
    test(
      'F2: a Firebase refusal after the user switched signs nobody out',
      () async {
        final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
        addTearDown(harness.dispose);
        await pumpEventQueue();
        harness.firebaseAuth.currentUser = _FakeUser(
          uid: 'ada',
          getIdTokenOverride: () async {
            // B signs in while A's token is being fetched; then Firebase
            // refuses A's.
            harness.firebaseAuth.currentUser = _FakeUser(uid: 'bob');
            throw FirebaseAuthException(code: 'user-disabled');
          },
        );

        await expectLater(
          harness.api.accessTokenRefresher!(),
          throwsA(isA<RefreshSupersededException>()),
        );
      },
    );

    test('F2: the same refusal for the current user still refuses', () async {
      final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);
      await pumpEventQueue();
      harness.firebaseAuth.currentUser = _FakeUser(
        uid: 'ada',
        getIdTokenOverride: () async =>
            throw FirebaseAuthException(code: 'user-disabled'),
      );

      expect(await harness.api.accessTokenRefresher!(), isNull);
    });

    test(
      'F5: a refresh 409 drops the expired JWT like the launch 409',
      () async {
        final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
        addTearDown(harness.dispose);
        await pumpEventQueue();
        expect(harness.container.read(authServiceProvider).jwtToken, isNotNull);
        harness.api.postError = ApiException(
          'Account linking conflict',
          statusCode: 409,
          code: 'account_conflict',
        );

        await expectLater(
          harness.api.accessTokenRefresher!(),
          throwsA(isA<ApiException>()),
        );

        final state = harness.container.read(authServiceProvider);
        expect(state.jwtToken, isNull);
        expect(state.isAuthenticated, isFalse);
        expect(state.error, accountLinkFailedMessage);
        expect(state.firebaseUser?.uid, 'ada');
        const storage = FlutterSecureStorage();
        expect(await storage.read(key: 'django_jwt_token'), isNull);
        expect(await storage.read(key: 'django_refresh_token'), isNull);
      },
    );
  });

  group('todo 587', () {
    test(
      'item 2: a refresh 409 overtaken mid-clear keeps the newer tokens',
      () async {
        // The in-memory store the mock platform deletes from. Once armed, the
        // first delete is where B signs in and its exchange stores B's refresh
        // token, before A's conflict handler issues its second delete.
        late _Harness harness;
        late _OnRemoveMap store;
        var armed = false;
        store = _OnRemoveMap((key) {
          if (!armed || key != 'django_jwt_token') return;
          armed = false;
          harness.firebaseAuth.currentUser = _FakeUser(uid: 'bob');
          store['django_refresh_token'] = 'bob-refresh';
        });
        FlutterSecureStorage.setMockInitialValues(store);
        harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
        addTearDown(harness.dispose);
        await pumpEventQueue();
        harness.api.postError = ApiException(
          'Account linking conflict',
          statusCode: 409,
          code: 'account_conflict',
        );
        armed = true;

        await expectLater(
          harness.api.accessTokenRefresher!(),
          throwsA(isA<ApiException>()),
        );

        const storage = FlutterSecureStorage();
        expect(
          await storage.read(key: 'django_refresh_token'),
          'bob-refresh',
          reason: "A's overtaken conflict handler deleted B's token",
        );
        expect(harness.container.read(authServiceProvider).error, isNull);
      },
    );
  });

  group('todo 607', () {
    // Item 2: the launch exchange's failure paths re-check after each await,
    // so an overtaken exchange leaves the newer one's tokens, bearer and
    // state alone.
    for (final failure in <String, Exception>{
      'an API error': ApiException('Server error', statusCode: 500),
      'any other error': Exception('boom'),
    }.entries) {
      test('item 2: a launch exchange failing with ${failure.key}, overtaken '
          'mid-clear, keeps the newer tokens', () async {
        late _Harness harness;
        late _OnRemoveMap store;
        var armed = false;
        store = _OnRemoveMap((key) {
          if (!armed || key != 'django_jwt_token') return;
          armed = false;
          harness.firebaseAuth.currentUser = _FakeUser(uid: 'bob');
          store['django_refresh_token'] = 'bob-refresh';
          harness.api.setAuthToken('bob-jwt');
        });
        FlutterSecureStorage.setMockInitialValues(store);
        harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
        addTearDown(harness.dispose);
        final gate = Completer<void>();
        harness.api
          ..postError = failure.value
          ..postGate = gate;
        await pumpEventQueue();
        expect(harness.api.postCalls, isEmpty, reason: 'post not held');

        // Armed after the exchange's own opening clear, so the first delete
        // it reaches is the failure path's.
        armed = true;
        gate.complete();
        await pumpEventQueue();

        expect(armed, isFalse, reason: 'the failure path never cleared');
        const storage = FlutterSecureStorage();
        expect(
          await storage.read(key: 'django_refresh_token'),
          'bob-refresh',
          reason: "A's overtaken failure path deleted B's token",
        );
        expect(harness.api.currentToken, 'bob-jwt');
        expect(harness.container.read(authServiceProvider).error, isNull);
      });
    }
  });

  group('session-expiry exemption', () {
    test('signOut\'s FCM unregister carries skipSessionExpiryKey', () async {
      // Asserted through the REQUEST options, not a notifier flag — there is
      // no `_signingOut` boolean in lib/ and by design there must not be one.
      final harness = _Harness(
        currentUser: _FakeUser(uid: 'ada'),
        useRealPushService: true,
      );
      addTearDown(harness.dispose);
      harness.container.read(authServiceProvider);
      // clearOnLogout skips the network entirely when this session never
      // registered, so give it a registration to clear.
      await harness.realPush!.registerToken('device-token-1');

      await harness.container.read(authServiceProvider.notifier).signOut();

      // Selected by path, not position: with the real push service the
      // build-time exchange and a registration are POSTs too, so `.last`
      // would be leaning on production ordering to pick the clear. Since
      // todo 621 the clear is the device unregister.
      final clear = harness.api.postCalls.singleWhere(
        (c) => c.path == '/push-devices/unregister/',
      );
      expect(clear.options?.extra?[ApiService.skipSessionExpiryKey], isTrue);
    });

    test('a real 401 on an exempt request does not trigger the session-expired '
        'handler, while an unexempt one does', () async {
      // Drives the actual Dio interceptor against a local server rather than
      // trusting the flag's presence: the request-side opt-out is only worth
      // anything if ApiService honours it.
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      addTearDown(() => server.close(force: true));
      unawaited(() async {
        await for (final request in server) {
          request.response.statusCode = HttpStatus.unauthorized;
          request.response.headers.contentType = ContentType.json;
          request.response.write(jsonEncode({'detail': 'expired'}));
          await request.response.close();
        }
      }());

      final api = ApiService(
        baseUrl: 'http://${server.address.host}:${server.port}',
      );
      var sessionExpiredCalls = 0;
      api.setSessionExpiredHandler(() async => sessionExpiredCalls++);

      await expectLater(
        api.patch(
          '/forum/me/profile/',
          data: {'fcm_token': ''},
          options: Options(extra: {ApiService.skipSessionExpiryKey: true}),
        ),
        throwsA(isA<ApiException>()),
      );
      expect(
        sessionExpiredCalls,
        0,
        reason: 'exempt 401 converted an intentional sign-out into expiry',
      );

      await expectLater(
        api.patch('/forum/me/profile/', data: {'fcm_token': ''}),
        throwsA(isA<ApiException>()),
      );
      expect(
        sessionExpiredCalls,
        1,
        reason: 'the exemption is unfalsifiable — 401 never triggers expiry',
      );
    });
  });
}

// ---------------------------------------------------------------------------
// Harness
// ---------------------------------------------------------------------------

/// A string map that calls [onRemove] after each removal: the in-memory
/// secure-storage mock deletes through `remove`, so a test can act at the
/// exact moment the notifier's delete lands.
class _OnRemoveMap extends MapBase<String, String> {
  _OnRemoveMap(this.onRemove);

  final void Function(String key) onRemove;
  final Map<String, String> _inner = {};

  @override
  String? operator [](Object? key) => _inner[key];

  @override
  void operator []=(String key, String value) => _inner[key] = value;

  @override
  void clear() => _inner.clear();

  @override
  Iterable<String> get keys => _inner.keys;

  @override
  String? remove(Object? key) {
    final removed = _inner.remove(key);
    if (key is String) onRemove(key);
    return removed;
  }
}

/// Wires a [ProviderContainer] with fakes for every collaborator the notifier
/// reaches: Firebase auth, the API, and push registration.
class _Harness {
  _Harness({
    User? currentUser,
    bool useRealPushService = false,
    String baseUrl = 'http://fake.local',
    List<Override> overrides = const [],
  }) {
    firebaseAuth = _FakeFirebaseAuth(events: events, currentUser: currentUser);
    api = _FakeApiService(events: events, baseUrl: baseUrl);
    if (useRealPushService) {
      messaging = _FakeMessaging();
      realPush = _TestablePushRegistrationService(api, messaging!);
    }
    push = _RecordingPushRegistrationService(api, events);

    container = ProviderContainer(
      overrides: [
        apiServiceProvider.overrideWithValue(api),
        pushRegistrationServiceProvider.overrideWithValue(realPush ?? push),
        authServiceProvider.overrideWith(
          () => _TestableAuthService(firebaseAuth),
        ),
        ...overrides,
      ],
    );

    // authServiceProvider is autoDispose: a bare container.read() builds the
    // notifier and immediately tears it down, so the NEXT read rebuilds it —
    // re-running build()'s unawaited token exchange against a disposed Ref.
    // Hold a listener for the harness's lifetime so there is exactly one
    // notifier instance, as there is in the app.
    _subscription = container.listen(
      authServiceProvider,
      (_, _) {},
      fireImmediately: true,
    );
  }

  late final ProviderSubscription<AuthState> _subscription;

  late final _FakeFirebaseAuth firebaseAuth;
  late final _FakeApiService api;
  late final _RecordingPushRegistrationService push;
  late final ProviderContainer container;

  /// Both non-null only when constructed with `useRealPushService: true`.
  _TestablePushRegistrationService? realPush;
  _FakeMessaging? messaging;

  /// Shared ordering log — every fake appends to it, so cross-collaborator
  /// sequencing (e.g. clearOnLogout before firebase.signOut) is assertable.
  final List<String> events = [];

  /// Drive the Firebase auth-state stream the way a real sign-in does, and
  /// wait for the listener's async work to settle.
  Future<void> signIn(User user) async {
    firebaseAuth.currentUser = user;
    return emitAuthState(user);
  }

  Future<void> emitAuthState(User? user) async {
    firebaseAuth.currentUser = user;
    firebaseAuth.authStateController.add(user);
    await pumpEventQueue();
  }

  void dispose() {
    _subscription.close();
    container.dispose();
    firebaseAuth.authStateController.close();
    // The real push service subscribes to onTokenRefresh; leaving the
    // controller open outlives the test.
    messaging?.tokenRefreshController.close();
  }
}

/// Injects the fake FirebaseAuth through the production `@visibleForTesting`
/// seam, so no test needs Firebase.initializeApp().
class _TestableAuthService extends AuthService {
  _TestableAuthService(this._firebaseAuth);

  final FirebaseAuth _firebaseAuth;

  @override
  FirebaseAuth get firebaseAuth => _firebaseAuth;
}

/// A resolved account profile, held the way a mounted forum screen holds it.
/// `build()` never reaches `/auth/user/`; only a rebuild (a completed
/// sign-in's invalidate, todo 520) runs it again.
class _FakeUserProfileService extends UserProfileService {
  _FakeUserProfileService(this._username);

  final String _username;

  @override
  Future<UserProfile?> build() async => UserProfile(
    id: 1,
    username: _username,
    email: '$_username@example.com',
    dateJoined: DateTime(2026, 1, 1),
  );
}

/// Runs the REAL `build()` (its bearer gate included) and fakes only the
/// request, recording whether each fetch would have carried a bearer.
class _FetchRecordingUserProfileService extends UserProfileService {
  _FetchRecordingUserProfileService(this.fetches);

  /// One entry per GET /auth/user/: was a bearer installed when it went out.
  final List<bool> fetches;

  @override
  Future<UserProfile> fetchProfile() async {
    fetches.add(ref.read(apiServiceProvider).hasAuthToken);
    return UserProfile(
      id: 1,
      username: 'ada',
      email: 'ada@example.com',
      dateJoined: DateTime(2026, 1, 1),
    );
  }
}

/// Counts how often the account profile is built. Riverpod 3 keeps one
/// notifier per provider element and re-runs its `build()` on a rebuild
/// (riverpod 3.2.1 caches it in `classListenable.result`), so the count is
/// taken in `build()`: a factory counter would stay at 1 across an invalidate.
class _ProfileBuilds {
  int count = 0;

  Override get override => userProfileServiceProvider.overrideWith(
    () => _CountingUserProfileService('ada', this),
  );
}

/// The fake profile, counting each `build()` into [_ProfileBuilds].
class _CountingUserProfileService extends _FakeUserProfileService {
  _CountingUserProfileService(super.username, this._builds);

  final _ProfileBuilds _builds;

  @override
  Future<UserProfile?> build() {
    _builds.count++;
    return super.build();
  }
}

/// Records the three lifecycle calls AuthService is responsible for making.
/// Extends rather than implements so the real constructor and any unoverridden
/// member stay real — `messaging` is a lazy getter, so nothing touches
/// Firebase.
class _RecordingPushRegistrationService extends PushRegistrationService {
  _RecordingPushRegistrationService(super.apiService, this._events);

  final List<String> _events;

  List<String> get calls => _events.where(_isPushEvent).toList();

  static bool _isPushEvent(String e) =>
      e == 'syncAfterLogin' || e == 'clearOnLogout' || e == 'detach';

  /// Holds `clearOnLogout` open so a test can resume an in-flight exchange
  /// mid-sign-out, while Firebase still reports the user as current.
  Completer<void>? clearOnLogoutGate;

  @override
  Future<void> syncAfterLogin() async => _events.add('syncAfterLogin');

  @override
  Future<void> clearOnLogout() async {
    _events.add('clearOnLogout');
    final gate = clearOnLogoutGate;
    if (gate != null) await gate.future;
  }

  @override
  void detach() => _events.add('detach');
}

/// The real service with only its Firebase seam faked — used by the
/// exemption test, which must exercise the production `clearOnLogout`.
class _TestablePushRegistrationService extends PushRegistrationService {
  _TestablePushRegistrationService(super.apiService, this._messaging);

  final FirebaseMessaging _messaging;

  @override
  FirebaseMessaging get messaging => _messaging;
}

class _RequestCall {
  _RequestCall(this.path, this.data, this.options);

  final String path;
  final Map<String, dynamic>? data;
  final Options? options;
}

class _FakeApiService extends ApiService {
  _FakeApiService({required List<String> events, required super.baseUrl})
    : _events = events,
      super(authToken: null);

  /// Send `post` over real HTTP to [baseUrl] instead of faking the response.
  bool realHttp = false;

  final List<String> _events;
  final List<_RequestCall> postCalls = [];
  final List<_RequestCall> patchCalls = [];
  Exception? postError;
  Completer<void>? postGate;

  /// Whatever AuthService.build() installed, so the test can fire the
  /// session-expired path the way the real 401 interceptor would.
  Future<void> Function()? sessionExpiredHandler;

  @override
  void setSessionExpiredHandler(Future<void> Function()? onSessionExpired) {
    sessionExpiredHandler = onSessionExpired;
    super.setSessionExpiredHandler(onSessionExpired);
  }

  /// Whatever AuthService.build() installed as the 401 token refresher.
  Future<String?> Function()? accessTokenRefresher;

  /// The access token the next exchange returns.
  String nextAccessToken = 'django-jwt';

  /// The bearer token AuthService last installed.
  String? currentToken;

  @override
  void setAccessTokenRefresher(Future<String?> Function()? refresher) {
    accessTokenRefresher = refresher;
    super.setAccessTokenRefresher(refresher);
  }

  @override
  void setAuthToken(String? token) {
    currentToken = token;
    super.setAuthToken(token);
  }

  @override
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    _events.add('api.post $path');
    if (realHttp) {
      return super.post(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
    }
    final gate = postGate;
    if (gate != null) await gate.future;
    postCalls.add(_RequestCall(path, data as Map<String, dynamic>?, options));
    final error = postError;
    if (error != null) throw error;
    return Response<dynamic>(
      requestOptions: RequestOptions(path: path),
      data: {
        'access_token': nextAccessToken,
        'refresh_token': 'django-refresh',
      },
    );
  }

  @override
  Future<Response> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    patchCalls.add(_RequestCall(path, data as Map<String, dynamic>?, options));
    if (realHttp) {
      return super.patch(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
    }
    return Response<dynamic>(requestOptions: RequestOptions(path: path));
  }
}

class _FakeFirebaseAuth implements FirebaseAuth {
  _FakeFirebaseAuth({required List<String> events, User? currentUser})
    : _events = events,
      _currentUser = currentUser;

  final List<String> _events;
  User? _currentUser;
  final StreamController<User?> authStateController =
      StreamController<User?>.broadcast();

  @override
  User? get currentUser => _currentUser;

  set currentUser(User? user) => _currentUser = user;

  @override
  Stream<User?> authStateChanges() => authStateController.stream;

  /// Holds `signOut()` open, so a test can look at the app between the
  /// session expiry's start and its auth flip.
  Completer<void>? signOutGate;

  @override
  Future<void> signOut() async {
    _events.add('firebase.signOut');
    final gate = signOutGate;
    if (gate != null) await gate.future;
    _currentUser = null;
  }

  /// The user `signInWithEmailAndPassword` signs in (todo 660).
  User? signInUser;

  /// The user `createUserWithEmailAndPassword` creates (todo 660).
  User? createdUser;

  @override
  Future<UserCredential> signInWithEmailAndPassword({
    required String email,
    required String password,
  }) async {
    _events.add('firebase.signInWithEmailAndPassword');
    _currentUser = signInUser;
    return _FakeUserCredential(signInUser);
  }

  @override
  Future<UserCredential> createUserWithEmailAndPassword({
    required String email,
    required String password,
  }) async {
    _events.add('firebase.createUserWithEmailAndPassword');
    _currentUser = createdUser;
    return _FakeUserCredential(createdUser);
  }

  /// Anything the notifier starts using that is not faked here fails loudly
  /// rather than silently no-op'ing.
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeUserCredential implements UserCredential {
  _FakeUserCredential(this.user);

  @override
  final User? user;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeUser implements User {
  _FakeUser({
    required this.uid,
    this.getIdTokenOverride,
    this.emailVerified = true,
  });

  @override
  final String uid;

  /// Defaults to true, the state of every user the older tests sign in: the
  /// exchange forces a token refresh for an unverified one (todo 660).
  @override
  bool emailVerified;

  /// Each `getIdToken` call's `forceRefresh` argument, in order.
  final List<bool> idTokenForceRefresh = [];

  /// Run by `reload()`, e.g. to flip [emailVerified] the way opening the
  /// mailed link does server-side.
  void Function()? onReload;
  int reloads = 0;
  int verificationEmailsSent = 0;
  @override
  String? displayName;

  @override
  Future<void> reload() async {
    reloads++;
    onReload?.call();
  }

  @override
  Future<void> sendEmailVerification([
    ActionCodeSettings? actionCodeSettings,
  ]) async {
    verificationEmailsSent++;
  }

  @override
  Future<void> updateDisplayName(String? displayName) async {
    this.displayName = displayName;
  }

  /// Read by AuthService's kDebugMode logging (via redactEmail), which is
  /// live under `flutter test` — a noSuchMethod fallthrough would throw.
  @override
  String? get email => '$uid@example.com';

  final Future<String?> Function()? getIdTokenOverride;

  @override
  Future<String?> getIdToken([bool forceRefresh = false]) async {
    idTokenForceRefresh.add(forceRefresh);
    final override = getIdTokenOverride;
    if (override != null) return override();
    return 'firebase-id-token';
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// A loopback backend for the refresh tests (todo 498): `Bearer fresh` is
/// the only accepted token, and the token exchange answers [exchangeStatus]
/// with [exchangeBody], whatever bearer it carries: the real view runs no
/// authenticator (todo 500). [holds] delays the first response on a path,
/// and [bodies] records each request's decoded JSON body.
class _LoopbackBackend {
  _LoopbackBackend._(this._server, this._savedOverrides) {
    _server.listen(_handle);
  }

  static Future<_LoopbackBackend> start() async {
    // Real loopback HTTP, not whatever HttpClient a test binding installed.
    final saved = HttpOverrides.current;
    HttpOverrides.global = null;
    return _LoopbackBackend._(
      await HttpServer.bind(InternetAddress.loopbackIPv4, 0),
      saved,
    );
  }

  final HttpServer _server;
  final HttpOverrides? _savedOverrides;
  final List<(String, String?)> seen = [];
  final List<(String, Object?)> bodies = [];
  int exchangeStatus = HttpStatus.ok;
  Map<String, Object?>? exchangeBody;
  final Map<String, Future<void>> holds = {};

  String get baseUrl => 'http://${_server.address.host}:${_server.port}';

  Future<void> _handle(HttpRequest request) async {
    final raw = await utf8.decodeStream(request);
    Object? body;
    try {
      body = raw.isEmpty ? null : jsonDecode(raw);
    } on FormatException {
      body = raw;
    }
    final auth = request.headers.value(HttpHeaders.authorizationHeader);
    seen.add((request.uri.path, auth));
    bodies.add((request.uri.path, body));
    final hold = holds.remove(request.uri.path);
    if (hold != null) await hold;
    final isExchange = request.uri.path == '/auth/firebase-token-exchange/';
    int status;
    Object reply;
    if (isExchange) {
      status = exchangeStatus;
      reply = status == HttpStatus.ok
          ? {'access_token': 'fresh', 'refresh_token': 'refresh'}
          : exchangeBody ?? {'error': 'exchange failed'};
    } else {
      final ok = auth == 'Bearer fresh';
      status = ok ? HttpStatus.ok : HttpStatus.unauthorized;
      reply = ok ? {'ok': true} : {'detail': 'Token is expired'};
    }
    request.response
      ..statusCode = status
      ..headers.contentType = ContentType.json
      ..write(jsonEncode(reply));
    await request.response.close();
  }

  Future<void> close() async {
    await _server.close(force: true);
    HttpOverrides.global = _savedOverrides;
  }
}

/// Only the members the real [PushRegistrationService] touches; anything else
/// is a loud NoSuchMethodError.
class _FakeMessaging implements FirebaseMessaging {
  final StreamController<String> tokenRefreshController =
      StreamController<String>.broadcast();

  @override
  Future<NotificationSettings> requestPermission({
    bool alert = true,
    bool announcement = false,
    bool badge = true,
    bool carPlay = false,
    bool criticalAlert = false,
    bool provisional = false,
    bool sound = true,
    bool providesAppNotificationSettings = false,
  }) async => _FakeSettings();

  @override
  Future<String?> getToken({
    String? serviceWorkerScriptPath,
    String? vapidKey,
  }) async => 'device-token-1';

  @override
  Stream<String> get onTokenRefresh => tokenRefreshController.stream;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeSettings implements NotificationSettings {
  @override
  AuthorizationStatus get authorizationStatus => AuthorizationStatus.authorized;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
