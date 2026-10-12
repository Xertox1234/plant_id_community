import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/push_registration_service.dart';

/// Todo 621 moved registration from the legacy `PATCH /forum/me/profile/`
/// `fcm_token` field to per-device `POST /push-devices/` and sign-out to
/// `POST /push-devices/unregister/`, so this file asserts those requests.
/// Every test from before todo 621 keeps its name and intent; the new ones
/// cover the installation id, the deploy-skew fallback, the user-visible
/// status, the bounded retries and the sign-out races.
const _register = {
  'token': 'device-token-1',
  'installation_id': 'install-1',
  'platform': 'ios',
};

Map<String, Object?> _registration(String token) => {
  ..._register,
  'token': token,
};

void main() {
  late _FakeApiService fakeApi;
  late _FakeMessaging fakeMessaging;
  late _TestablePushRegistrationService service;

  setUp(() {
    fakeApi = _FakeApiService();
    fakeMessaging = _FakeMessaging();
    service = _TestablePushRegistrationService(fakeApi, fakeMessaging);
  });

  tearDown(() async {
    service.detach();
    await fakeMessaging.tokenRefreshController.close();
  });

  group('syncAfterLogin', () {
    test('registers the FCM token as one of the account\'s devices', () async {
      fakeMessaging.token = 'device-token-1';

      await service.syncAfterLogin();

      expect(fakeApi.calls, hasLength(1));
      expect(fakeApi.calls.single.method, 'POST');
      expect(fakeApi.calls.single.path, '/push-devices/');
      expect(fakeApi.calls.single.data, _register);
      expect(service.lastSyncedToken, 'device-token-1');
      expect(
        service.status.value,
        const PushStatus(
          permission: PushPermission.granted,
          registration: PushRegistration.registered,
        ),
      );
    });

    test('skips re-registering an unchanged token', () async {
      // Fires on every JWT exchange, including silent app-start login — an
      // unchanged token must not burn the registration throttle.
      fakeMessaging.token = 'device-token-1';

      await service.syncAfterLogin();
      await service.syncAfterLogin();

      expect(fakeApi.calls, hasLength(1));
    });

    test('retries on the next login when the registration failed', () async {
      fakeMessaging.token = 'device-token-1';
      fakeApi.error = ApiException('server down', statusCode: 500);

      await service.syncAfterLogin(); // must not throw
      expect(service.lastSyncedToken, isNull); // marker only set on success
      expect(service.status.value.registration, PushRegistration.failed);

      fakeApi.error = null;
      await service.syncAfterLogin();

      expect(fakeApi.calls, hasLength(2));
      expect(fakeApi.calls.last.data, _register);
    });

    test('never throws into the login flow when messaging fails', () async {
      fakeMessaging.getTokenError = Exception('firebase unavailable');

      await expectLater(service.syncAfterLogin(), completes);
      expect(fakeApi.calls, isEmpty);
      expect(
        service.status.value.registration,
        PushRegistration.tokenUnavailable,
      );
    });

    test('a null token still installs the rotation listener, which heals '
        'registration when the token arrives (iOS APNS warm-up)', () async {
      fakeMessaging.token = null;

      await service.syncAfterLogin();
      expect(fakeApi.calls, isEmpty);
      expect(
        service.status.value.registration,
        PushRegistration.tokenUnavailable,
      );

      fakeMessaging.tokenRefreshController.add('late-token');
      await pumpEventQueue();

      expect(fakeApi.calls, hasLength(1));
      expect(fakeApi.calls.single.data, _registration('late-token'));
      expect(service.status.value.registration, PushRegistration.registered);
    });

    test('a failed initial registration does not cost the session its '
        'rotation listener', () async {
      fakeMessaging.token = 'device-token-1';
      fakeApi.error = ApiException('server down', statusCode: 500);

      await service.syncAfterLogin();
      expect(fakeApi.calls, hasLength(1)); // the failed attempt

      fakeApi.error = null;
      fakeMessaging.tokenRefreshController.add('device-token-2');
      await pumpEventQueue();

      expect(fakeApi.calls, hasLength(2));
      expect(fakeApi.calls.last.data, _registration('device-token-2'));
    });

    test('re-registers when FCM rotates the token', () async {
      fakeMessaging.token = 'device-token-1';
      await service.syncAfterLogin();

      fakeMessaging.tokenRefreshController.add('device-token-2');
      await pumpEventQueue();

      expect(fakeApi.calls, hasLength(2));
      // Same installation id: the backend replaces this device's row.
      expect(fakeApi.calls.last.data, _registration('device-token-2'));
    });

    test(
      'a refresh event for the unchanged token does not re-register',
      () async {
        // FCM fires onTokenRefresh for the token's FIRST generation too —
        // without this guard every fresh install double-registered (observed
        // live in the on-device E2E).
        fakeMessaging.token = 'device-token-1';
        await service.syncAfterLogin();

        fakeMessaging.tokenRefreshController.add('device-token-1');
        await pumpEventQueue();

        expect(fakeApi.calls, hasLength(1));
      },
    );

    test('does not stack refresh listeners across repeated logins', () async {
      fakeMessaging.token = 'device-token-1';
      await service.syncAfterLogin();
      await service.syncAfterLogin();

      fakeMessaging.tokenRefreshController.add('device-token-2');
      await pumpEventQueue();

      // 1 initial registration + exactly 1 rotation registration — a stacked
      // listener would register the rotated token twice.
      expect(fakeApi.calls, hasLength(2));
    });

    test('a sync parked on getToken when detach() runs registers nothing and '
        'attaches nothing (sign-out during login sync)', () async {
      // Empirically confirmed race in review: without the epoch guard the
      // resumed continuation re-registered the token and re-attached the
      // listener after logout had cleared everything.
      final gate = Completer<String?>();
      fakeMessaging.getTokenOverride = () => gate.future;

      final inFlight = service.syncAfterLogin();
      await pumpEventQueue();

      service.detach(); // sign-out path
      gate.complete('device-token-1');
      await inFlight;

      expect(fakeApi.calls, isEmpty);
      expect(service.status.value.registration, PushRegistration.signedOut);

      fakeMessaging.tokenRefreshController.add('device-token-2');
      await pumpEventQueue();
      expect(fakeApi.calls, isEmpty); // no resurrected listener either
    });
  });

  group('permission (todo 621)', () {
    test('asks only a user who was never asked', () async {
      fakeMessaging.authorization = AuthorizationStatus.notDetermined;
      fakeMessaging.authorizationAfterRequest = AuthorizationStatus.authorized;

      await service.syncAfterLogin();

      expect(fakeMessaging.requestPermissionCalls, 1);
      expect(service.status.value.permission, PushPermission.granted);
    });

    test('never asks a user who said no again, but still registers the '
        'device and says notifications are off', () async {
      fakeMessaging.authorization = AuthorizationStatus.denied;

      await service.syncAfterLogin();
      await service.syncAfterLogin();

      expect(fakeMessaging.requestPermissionCalls, 0);
      // Android delivers data to a denied device; the tray stays silent.
      expect(fakeApi.calls, hasLength(1));
      expect(
        service.status.value,
        const PushStatus(
          permission: PushPermission.denied,
          registration: PushRegistration.registered,
        ),
      );
    });

    test('a permission API failure does not stop the registration', () async {
      fakeMessaging.settingsError = Exception('platform channel gone');

      await service.syncAfterLogin();

      expect(fakeApi.calls, hasLength(1));
      expect(service.status.value.permission, PushPermission.unknown);
    });

    test('a resume picks up a permission the user changed in the OS '
        'settings, without asking', () async {
      fakeMessaging.authorization = AuthorizationStatus.denied;
      await service.syncAfterLogin();

      fakeMessaging.authorization = AuthorizationStatus.authorized;
      await service.reconcile(force: true);

      expect(service.status.value.permission, PushPermission.granted);
      expect(fakeMessaging.requestPermissionCalls, 0);
    });

    test('requestPermission (the settings tile) reports the answer', () async {
      fakeMessaging.authorization = AuthorizationStatus.notDetermined;
      fakeMessaging.authorizationAfterRequest = AuthorizationStatus.denied;

      await service.requestPermission();

      expect(service.status.value.permission, PushPermission.denied);
    });
  });

  group('bounded recovery (todo 621)', () {
    late _TestablePushRegistrationService fast;

    setUp(() {
      fast = _TestablePushRegistrationService(
        fakeApi,
        fakeMessaging,
        retryDelays: const [Duration(seconds: 1), Duration(seconds: 2)],
      );
    });

    tearDown(() => fast.detach());

    testWidgets('a failed registration retries on the schedule, then '
        'stops', (tester) async {
      fakeApi.error = ApiException('server down', statusCode: 503);

      await fast.syncAfterLogin();
      expect(fakeApi.calls, hasLength(1));

      await tester.pump(const Duration(seconds: 1));
      await tester.pump();
      expect(fakeApi.calls, hasLength(2));

      await tester.pump(const Duration(seconds: 2));
      await tester.pump();
      expect(fakeApi.calls, hasLength(3));

      await tester.pump(const Duration(minutes: 30));
      expect(fakeApi.calls, hasLength(3), reason: 'retries are bounded');
      expect(fast.status.value.registration, PushRegistration.failed);
    });

    testWidgets('a retry that succeeds says the device is registered', (
      tester,
    ) async {
      fakeApi.error = ApiException('server down', statusCode: 503);
      await fast.syncAfterLogin();

      fakeApi.error = null;
      await tester.pump(const Duration(seconds: 1));
      await tester.pump();

      expect(fakeApi.calls, hasLength(2));
      expect(fast.status.value.registration, PushRegistration.registered);
      expect(fast.lastSyncedToken, 'default-token');
    });

    testWidgets('a missing token is retried too', (tester) async {
      fakeMessaging.token = null;
      await fast.syncAfterLogin();
      expect(fakeApi.calls, isEmpty);

      fakeMessaging.token = 'device-token-1';
      await tester.pump(const Duration(seconds: 1));
      await tester.pump();

      expect(fakeApi.calls, hasLength(1));
      expect(fast.status.value.registration, PushRegistration.registered);
    });

    testWidgets('a 429 or a 400 is not retried', (tester) async {
      for (final code in [429, 400]) {
        fast.detach();
        fakeApi.calls.clear();
        fakeApi.error = ApiException('refused', statusCode: code);

        await fast.syncAfterLogin();
        await tester.pump(const Duration(minutes: 30));

        expect(fakeApi.calls, hasLength(1), reason: '$code was retried');
        expect(fast.status.value.registration, PushRegistration.failed);
      }
    });

    testWidgets('sign-out cancels a scheduled retry', (tester) async {
      fakeApi.error = ApiException('server down', statusCode: 503);
      await fast.syncAfterLogin();

      fast.detach();
      fakeApi.error = null;
      await tester.pump(const Duration(minutes: 30));

      expect(fakeApi.calls, hasLength(1));
      expect(fast.lastSyncedToken, isNull);
    });

    test('a resume after the retries ran out tries again, at most once per '
        'interval unless forced', () async {
      fakeApi.error = ApiException('refused', statusCode: 429);
      await service.syncAfterLogin();
      fakeApi.error = null;

      await service.reconcile();
      await service.reconcile(); // inside the interval: skipped
      expect(fakeApi.calls, hasLength(2));
      expect(service.status.value.registration, PushRegistration.registered);

      fakeMessaging.token = 'device-token-2';
      await service.reconcile(force: true);
      expect(fakeApi.calls, hasLength(3));
    });

    test('a resume while signed out does nothing', () async {
      await service.reconcile(force: true);

      expect(fakeApi.calls, isEmpty);
    });
  });

  group('registerToken', () {
    test('never throws on API failure', () async {
      fakeApi.error = ApiException('offline', statusCode: 503);

      await expectLater(service.registerToken('tok'), completes);
      expect(service.lastSyncedToken, isNull);
    });

    test('a registration in flight across detach() does not resurrect the sync '
        'marker', () async {
      fakeApi.gate = Completer<void>();

      final inFlight = service.registerToken('device-token-1');
      await pumpEventQueue();

      service.detach();
      fakeApi.gate!.complete();
      await inFlight;

      expect(service.lastSyncedToken, isNull);
    });

    test('a backend without the device route (deploy skew) falls back to the '
        'legacy profile field', () async {
      fakeApi.postError = ApiException('not found', statusCode: 404);

      await service.registerToken('device-token-1');

      expect(fakeApi.calls.map((c) => '${c.method} ${c.path}'), [
        'POST /push-devices/',
        'PATCH /forum/me/profile/',
      ]);
      expect(fakeApi.calls.last.data, {'fcm_token': 'device-token-1'});
      expect(service.lastSyncedToken, 'device-token-1');
    });

    test('a 500 is not mistaken for an old backend', () async {
      fakeApi.postError = ApiException('server down', statusCode: 500);

      await service.registerToken('device-token-1');

      expect(fakeApi.calls.map((c) => c.method), ['POST']);
    });

    test(
      'registers without an installation id when storage has none',
      () async {
        final noId = _TestablePushRegistrationService(
          fakeApi,
          fakeMessaging,
          installationId: () async => null,
        );
        addTearDown(noId.detach);

        await noId.registerToken('device-token-1');

        expect(fakeApi.calls.single.data, {
          'token': 'device-token-1',
          'platform': 'ios',
        });
      },
    );
  });

  group('clearOnLogout', () {
    test(
      'unregisters this device only and stops the refresh listener',
      () async {
        fakeMessaging.token = 'device-token-1';
        await service.syncAfterLogin();

        await service.clearOnLogout();

        expect(fakeApi.calls.last.method, 'POST');
        expect(fakeApi.calls.last.path, '/push-devices/unregister/');
        // This device's token: never a blank that would clear another device.
        expect(fakeApi.calls.last.data, {'token': 'device-token-1'});
        expect(
          fakeApi.calls.last.options?.extra?[ApiService.skipSessionExpiryKey],
          isTrue,
        );
        expect(service.lastSyncedToken, isNull);
        expect(service.status.value.registration, PushRegistration.signedOut);

        fakeMessaging.tokenRefreshController.add('device-token-3');
        await pumpEventQueue();
        expect(fakeApi.calls, hasLength(2)); // nothing after detach
      },
    );

    test(
      'skips the network clear entirely when this session never registered',
      () async {
        await service.clearOnLogout();

        expect(fakeApi.calls, isEmpty);
      },
    );

    test('never throws when the unregister fails', () async {
      fakeMessaging.token = 'device-token-1';
      await service.syncAfterLogin();
      fakeApi.error = ApiException('offline', statusCode: 503);

      await expectLater(service.clearOnLogout(), completes);
    });

    test(
      'a registration made the legacy way is cleared the legacy way',
      () async {
        fakeApi.postError = ApiException('not found', statusCode: 404);
        await service.registerToken('device-token-1');

        await service.clearOnLogout();

        expect(fakeApi.calls.last.method, 'PATCH');
        expect(fakeApi.calls.last.data, {'fcm_token': ''});
      },
    );

    test('a registration still in flight at sign-out lands before the '
        'unregister, so it cannot outlive it', () async {
      fakeApi.gate = Completer<void>();
      final registering = service.registerToken('device-token-1');
      await pumpEventQueue();

      final clearing = service.clearOnLogout();
      await pumpEventQueue();
      expect(fakeApi.calls.map((c) => c.path), ['/push-devices/']);

      fakeApi.gate!.complete();
      fakeApi.gate = null;
      await registering;
      await clearing;

      expect(fakeApi.calls.map((c) => c.path), [
        '/push-devices/',
        '/push-devices/unregister/',
      ]);
    });

    test('over real HTTP, a clear whose access token expired while the app '
        'sat idle refreshes it and still clears, without a sign-out '
        '(todo 498)', () async {
      // Finding 3: skipSessionExpiryKey used to skip the refresh too, so the
      // 401 left the FCM token registered and the device kept receiving the
      // signed-out user's pushes.
      final savedOverrides = HttpOverrides.current;
      HttpOverrides.global = null;
      addTearDown(() => HttpOverrides.global = savedOverrides);
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      addTearDown(() => server.close(force: true));
      var accepted = 'first-token';
      final seen = <(String, String, String?, Object?)>[];
      server.listen((request) async {
        final raw = await utf8.decodeStream(request);
        final auth = request.headers.value(HttpHeaders.authorizationHeader);
        Object? body;
        try {
          body = jsonDecode(raw);
        } on FormatException {
          // A bad body is answered, not left to hang the test until the
          // suite timeout (todo 500).
          seen.add((request.method, request.uri.path, auth, raw));
          request.response.statusCode = HttpStatus.badRequest;
          await request.response.close();
          return;
        }
        seen.add((request.method, request.uri.path, auth, body));
        final ok = auth == 'Bearer $accepted';
        request.response
          ..statusCode = ok ? HttpStatus.ok : HttpStatus.unauthorized
          ..headers.contentType = ContentType.json
          ..write(jsonEncode(ok ? {} : {'detail': 'Token is expired'}));
        await request.response.close();
      });

      final api = ApiService(
        baseUrl: 'http://${server.address.host}:${server.port}',
        authToken: 'first-token',
      );
      var refreshCalls = 0;
      var sessionExpiredCalls = 0;
      api.setAccessTokenRefresher(() async {
        refreshCalls++;
        return 'fresh';
      });
      api.setSessionExpiredHandler(() async => sessionExpiredCalls++);
      final realService = _TestablePushRegistrationService(api, fakeMessaging);
      addTearDown(realService.detach);
      await realService.registerToken('device-token-1');
      expect(realService.lastSyncedToken, 'device-token-1');

      accepted = 'fresh'; // the access token expires server-side
      await realService.clearOnLogout();

      expect(refreshCalls, 1);
      expect(sessionExpiredCalls, 0);
      expect(seen.last.$1, 'POST');
      expect(seen.last.$2, '/push-devices/unregister/');
      expect(seen.last.$3, 'Bearer fresh', reason: 'the clear was not re-sent');
      expect(seen.last.$4, {'token': 'device-token-1'});
    });
  });

  group('clearOnLogout bound (todo 500 F6)', () {
    testWidgets('a clear whose 401 refresh outlasts the 3 s bound is '
        'abandoned at 3 s, so sign-out is never held by it', (tester) async {
      await service.registerToken('device-token-1');
      // The clear, its refresh and the re-send are all still running: the
      // documented limit is that past 3 s the clear is given up.
      final hung = Completer<void>();
      fakeApi.gate = hung;

      var done = false;
      final clear = service.clearOnLogout().then((_) => done = true);
      await tester.pump(const Duration(milliseconds: 2900));
      expect(done, isFalse, reason: 'the clear was cut short');
      await tester.pump(const Duration(milliseconds: 200));
      expect(done, isTrue, reason: 'sign-out waited past the bound');

      hung.complete();
      await clear;
    });
  });

  group('detach', () {
    test('clears the sync marker so a different user on this device is never '
        'dedupe-skipped', () async {
      // Session-expiry and external sign-outs run detach() only (no
      // clearOnLogout); the next account's registration of the SAME device
      // token must still be sent (review: cross-file tracer).
      fakeMessaging.token = 'device-token-1';
      await service.syncAfterLogin();
      expect(fakeApi.calls, hasLength(1));

      service.detach();

      await service.syncAfterLogin();
      expect(fakeApi.calls, hasLength(2));
      expect(fakeApi.calls.last.data, _register);
    });

    test('an account switch registers the device for the new account and '
        'never unregisters it for the old one', () async {
      fakeMessaging.token = 'device-token-1';
      await service.syncAfterLogin(); // account A
      service.detach(); // A's session expired; B signs in
      await service.syncAfterLogin(); // account B

      expect(fakeApi.calls.map((c) => c.path), [
        '/push-devices/',
        '/push-devices/',
      ]);
    });
  });
}

class _Call {
  _Call(this.method, this.path, this.data, this.options);

  final String method;
  final String path;
  final Map<String, dynamic>? data;
  final Options? options;
}

/// Minimal [ApiService] stand-in, mirroring user_profile_service_test.dart's
/// convention: no real network; records every POST and PATCH attempt
/// (including ones configured to fail), throws [error] from either and
/// [postError] from POST only, and can hold a request in flight via [gate].
class _FakeApiService extends ApiService {
  _FakeApiService() : super(baseUrl: 'http://fake.local', authToken: null);

  final List<_Call> calls = [];
  Exception? error;
  Exception? postError;
  Completer<void>? gate;

  Future<Response> _record(
    String method,
    String path,
    dynamic data,
    Options? options,
  ) async {
    calls.add(_Call(method, path, data as Map<String, dynamic>?, options));
    final held = gate;
    if (held != null) await held.future;
    final failure = error ?? (method == 'POST' ? postError : null);
    if (failure != null) throw failure;
    return Response<dynamic>(requestOptions: RequestOptions(path: path));
  }

  @override
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) => _record('POST', path, data, options);

  @override
  Future<Response> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) => _record('PATCH', path, data, options);
}

/// Overrides the [PushRegistrationService.messaging] test seam so no test
/// ever touches Firebase.initializeApp(), and pins the installation id and
/// platform so no test touches secure storage.
class _TestablePushRegistrationService extends PushRegistrationService {
  _TestablePushRegistrationService(
    super.apiService,
    this._messaging, {
    Future<String?> Function()? installationId,
    super.retryDelays,
  }) : super(
         installationId: installationId ?? () async => 'install-1',
         platform: 'ios',
       );

  final FirebaseMessaging _messaging;

  @override
  FirebaseMessaging get messaging => _messaging;
}

/// Upgrade-proof settings stub: the service only reads authorizationStatus;
/// any new field it starts reading fails loudly via noSuchMethod instead of
/// forcing this file to track NotificationSettings' 12-field constructor
/// across firebase_messaging upgrades.
class _FakeSettings implements NotificationSettings {
  _FakeSettings(this.authorizationStatus);

  @override
  final AuthorizationStatus authorizationStatus;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// Hand-rolled fake (no mocking library in this suite): only the members
/// the service uses are implemented; anything else is a loud
/// [NoSuchMethodError] via [noSuchMethod].
class _FakeMessaging implements FirebaseMessaging {
  String? token = 'default-token';
  Object? getTokenError;
  Object? settingsError;
  Future<String?> Function()? getTokenOverride;
  AuthorizationStatus authorization = AuthorizationStatus.authorized;
  AuthorizationStatus? authorizationAfterRequest;
  int requestPermissionCalls = 0;
  final StreamController<String> tokenRefreshController =
      StreamController<String>.broadcast();

  @override
  Future<NotificationSettings> getNotificationSettings() async {
    final error = settingsError;
    if (error != null) throw error;
    return _FakeSettings(authorization);
  }

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
  }) async {
    requestPermissionCalls++;
    authorization = authorizationAfterRequest ?? authorization;
    return _FakeSettings(authorization);
  }

  @override
  Future<String?> getToken({
    String? serviceWorkerScriptPath,
    String? vapidKey,
  }) async {
    final override = getTokenOverride;
    if (override != null) return override();
    final error = getTokenError;
    if (error != null) throw error;
    return token;
  }

  @override
  Stream<String> get onTokenRefresh => tokenRefreshController.stream;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
