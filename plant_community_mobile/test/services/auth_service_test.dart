import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/push_registration_service.dart';

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
    test('builds without touching real Firebase and reports the current user', () async {
      final harness = _Harness(currentUser: _FakeUser(uid: 'ada'));
      addTearDown(harness.dispose);

      final state = harness.container.read(authServiceProvider);

      expect(state.firebaseUser?.uid, 'ada');
      expect(state.isAuthenticated, isFalse); // no JWT until the exchange lands

      // build() kicks off the exchange unawaited; drain it before teardown so
      // it lands on a live Ref rather than a disposed one.
      await pumpEventQueue();
    });
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
    test('build() registers _handleSessionExpired, and it signs the user out', () async {
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
    });

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

    test(
      'a real 401 on an exempt request does not trigger the session-expired '
      'handler, while an unexempt one does',
      () async {
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
            options: Options(
              extra: {ApiService.skipSessionExpiryKey: true},
            ),
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
      },
    );
  });
}

// ---------------------------------------------------------------------------
// Harness
// ---------------------------------------------------------------------------

/// Wires a [ProviderContainer] with fakes for every collaborator the notifier
/// reaches: Firebase auth, the API, and push registration.
class _Harness {
  _Harness({User? currentUser, bool useRealPushService = false}) {
    firebaseAuth = _FakeFirebaseAuth(events: events, currentUser: currentUser);
    api = _FakeApiService(events: events);
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
  _FakeApiService({required List<String> events})
    : _events = events,
      super(baseUrl: 'http://fake.local', authToken: null);

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

  @override
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    _events.add('api.post $path');
    final gate = postGate;
    if (gate != null) await gate.future;
    postCalls.add(_RequestCall(path, data as Map<String, dynamic>?, options));
    final error = postError;
    if (error != null) throw error;
    return Response<dynamic>(
      requestOptions: RequestOptions(path: path),
      data: {'access_token': 'django-jwt', 'refresh_token': 'django-refresh'},
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
