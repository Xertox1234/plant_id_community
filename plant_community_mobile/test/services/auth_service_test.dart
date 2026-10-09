import 'dart:async';
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

      expect(await harness.api.accessTokenRefresher!(), isNull);
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

      expect(await refresh, isNull);
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

    for (final status in [401, 403, 409]) {
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
        'fails the request with the 503, and the next 401 refreshes '
        'again', () async {
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

      await expectLater(
        harness.api.get('/forum/topics/'),
        throwsA(
          isA<ApiException>().having((e) => e.statusCode, 'statusCode', 503),
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
      for (var poll = 0; backend.seen.length < 2; poll++) {
        if (poll > 400) fail('the refresh never reached the exchange');
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }

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
      for (var poll = 0; backend.seen.length < 2; poll++) {
        if (poll > 400) fail('the read never reached the server');
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
      exchangeGate.complete();
      for (var poll = 0; harness.api.currentToken != 'fresh'; poll++) {
        if (poll > 400) fail('the launch exchange never installed its JWT');
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
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

  group('session-expiry exemption', () {
    test('signOut\'s FCM-clear PATCH carries skipSessionExpiryKey', () async {
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

      // Selected by payload, not position: with the real push service the
      // build-time exchange also PATCHes this endpoint (a registration), so
      // `.last` would be leaning on production ordering to pick the clear.
      final clear = harness.api.patchCalls.singleWhere(
        (c) => c.data?['fcm_token'] == '',
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

  @override
  Future<void> signOut() async {
    _events.add('firebase.signOut');
    _currentUser = null;
  }

  /// Anything the notifier starts using that is not faked here fails loudly
  /// rather than silently no-op'ing.
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeUser implements User {
  _FakeUser({required this.uid, this.getIdTokenOverride});

  @override
  final String uid;

  /// Read by AuthService's kDebugMode logging (via redactEmail), which is
  /// live under `flutter test` — a noSuchMethod fallthrough would throw.
  @override
  String? get email => '$uid@example.com';

  final Future<String?> Function()? getIdTokenOverride;

  @override
  Future<String?> getIdToken([bool forceRefresh = false]) async {
    final override = getIdTokenOverride;
    if (override != null) return override();
    return 'firebase-id-token';
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// A loopback backend for the refresh tests (todo 498): `Bearer fresh` is
/// the only accepted token, and the token exchange answers
/// [exchangeStatus], only when it carries no bearer, like the real view
/// behind DRF's authenticators. [holds] delays the first response on a
/// path.
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
  int exchangeStatus = HttpStatus.ok;
  final Map<String, Future<void>> holds = {};

  String get baseUrl => 'http://${_server.address.host}:${_server.port}';

  Future<void> _handle(HttpRequest request) async {
    await request.drain<void>();
    final auth = request.headers.value(HttpHeaders.authorizationHeader);
    seen.add((request.uri.path, auth));
    final hold = holds.remove(request.uri.path);
    if (hold != null) await hold;
    final isExchange = request.uri.path == '/auth/firebase-token-exchange/';
    int status;
    Object body;
    if (isExchange) {
      status = auth != null ? HttpStatus.unauthorized : exchangeStatus;
      body = status == HttpStatus.ok
          ? {'access_token': 'fresh', 'refresh_token': 'refresh'}
          : {'error': 'exchange failed'};
    } else {
      final ok = auth == 'Bearer fresh';
      status = ok ? HttpStatus.ok : HttpStatus.unauthorized;
      body = ok ? {'ok': true} : {'detail': 'Token is expired'};
    }
    request.response
      ..statusCode = status
      ..headers.contentType = ContentType.json
      ..write(jsonEncode(body));
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
