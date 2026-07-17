import 'dart:async';

import 'package:dio/dio.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/push_registration_service.dart';

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
    test('registers the FCM token against the forum profile endpoint', () async {
      fakeMessaging.token = 'device-token-1';

      await service.syncAfterLogin();

      expect(fakeApi.patchCalls, hasLength(1));
      expect(fakeApi.patchCalls.single.path, '/forum/me/profile/');
      expect(fakeApi.patchCalls.single.data, {'fcm_token': 'device-token-1'});
      expect(service.lastSyncedToken, 'device-token-1');
    });

    test('skips re-registering an unchanged token', () async {
      // Fires on every JWT exchange, including silent app-start login — an
      // unchanged token must not burn the profile_update 10/h throttle.
      fakeMessaging.token = 'device-token-1';

      await service.syncAfterLogin();
      await service.syncAfterLogin();

      expect(fakeApi.patchCalls, hasLength(1));
    });

    test('retries on the next login when the PATCH failed', () async {
      fakeMessaging.token = 'device-token-1';
      fakeApi.patchError = ApiException('server down', statusCode: 500);

      await service.syncAfterLogin(); // must not throw
      expect(service.lastSyncedToken, isNull); // marker only set on success

      fakeApi.patchError = null;
      await service.syncAfterLogin();

      expect(fakeApi.patchCalls, hasLength(2));
      expect(fakeApi.patchCalls.last.data, {'fcm_token': 'device-token-1'});
    });

    test('never throws into the login flow when messaging fails', () async {
      fakeMessaging.getTokenError = Exception('firebase unavailable');

      await expectLater(service.syncAfterLogin(), completes);
      expect(fakeApi.patchCalls, isEmpty);
    });

    test(
      'a null token still installs the rotation listener, which heals '
      'registration when the token arrives (iOS APNS warm-up)',
      () async {
        fakeMessaging.token = null;

        await service.syncAfterLogin();
        expect(fakeApi.patchCalls, isEmpty);

        fakeMessaging.tokenRefreshController.add('late-token');
        await pumpEventQueue();

        expect(fakeApi.patchCalls, hasLength(1));
        expect(fakeApi.patchCalls.single.data, {'fcm_token': 'late-token'});
      },
    );

    test(
      'a failed initial PATCH does not cost the session its rotation '
      'listener',
      () async {
        fakeMessaging.token = 'device-token-1';
        fakeApi.patchError = ApiException('server down', statusCode: 500);

        await service.syncAfterLogin();
        expect(fakeApi.patchCalls, hasLength(1)); // the failed attempt

        fakeApi.patchError = null;
        fakeMessaging.tokenRefreshController.add('device-token-2');
        await pumpEventQueue();

        expect(fakeApi.patchCalls, hasLength(2));
        expect(fakeApi.patchCalls.last.data, {'fcm_token': 'device-token-2'});
      },
    );

    test('re-registers when FCM rotates the token', () async {
      fakeMessaging.token = 'device-token-1';
      await service.syncAfterLogin();

      fakeMessaging.tokenRefreshController.add('device-token-2');
      await pumpEventQueue();

      expect(fakeApi.patchCalls, hasLength(2));
      expect(fakeApi.patchCalls.last.data, {'fcm_token': 'device-token-2'});
    });

    test('a refresh event for the unchanged token does not re-PATCH', () async {
      // FCM fires onTokenRefresh for the token's FIRST generation too —
      // without this guard every fresh install double-registered (observed
      // live in the on-device E2E).
      fakeMessaging.token = 'device-token-1';
      await service.syncAfterLogin();

      fakeMessaging.tokenRefreshController.add('device-token-1');
      await pumpEventQueue();

      expect(fakeApi.patchCalls, hasLength(1));
    });

    test('does not stack refresh listeners across repeated logins', () async {
      fakeMessaging.token = 'device-token-1';
      await service.syncAfterLogin();
      await service.syncAfterLogin();

      fakeMessaging.tokenRefreshController.add('device-token-2');
      await pumpEventQueue();

      // 1 initial registration + exactly 1 rotation registration — a stacked
      // listener would PATCH the rotated token twice.
      expect(fakeApi.patchCalls, hasLength(2));
    });

    test(
      'a sync parked on getToken when detach() runs registers nothing and '
      'attaches nothing (sign-out during login sync)',
      () async {
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

        expect(fakeApi.patchCalls, isEmpty);

        fakeMessaging.tokenRefreshController.add('device-token-2');
        await pumpEventQueue();
        expect(fakeApi.patchCalls, isEmpty); // no resurrected listener either
      },
    );
  });

  group('registerToken', () {
    test('never throws on API failure', () async {
      fakeApi.patchError = ApiException('offline', statusCode: 503);

      await expectLater(service.registerToken('tok'), completes);
      expect(service.lastSyncedToken, isNull);
    });

    test(
      'a PATCH in flight across detach() does not resurrect the sync marker',
      () async {
        fakeApi.patchGate = Completer<void>();

        final inFlight = service.registerToken('device-token-1');
        await pumpEventQueue();

        service.detach();
        fakeApi.patchGate!.complete();
        await inFlight;

        expect(service.lastSyncedToken, isNull);
      },
    );
  });

  group('clearOnLogout', () {
    test('PATCHes a blank token and stops the refresh listener', () async {
      fakeMessaging.token = 'device-token-1';
      await service.syncAfterLogin();

      await service.clearOnLogout();

      expect(fakeApi.patchCalls.last.data, {'fcm_token': ''});
      expect(service.lastSyncedToken, isNull);

      fakeMessaging.tokenRefreshController.add('device-token-3');
      await pumpEventQueue();
      expect(fakeApi.patchCalls, hasLength(2)); // no PATCH after detach
    });

    test(
      'skips the network clear entirely when this session never registered',
      () async {
        await service.clearOnLogout();

        expect(fakeApi.patchCalls, isEmpty);
      },
    );

    test('never throws when the clear PATCH fails', () async {
      fakeMessaging.token = 'device-token-1';
      await service.syncAfterLogin();
      fakeApi.patchError = ApiException('offline', statusCode: 503);

      await expectLater(service.clearOnLogout(), completes);
    });
  });

  group('detach', () {
    test(
      'clears the sync marker so a different user on this device is never '
      'dedupe-skipped',
      () async {
        // Session-expiry and external sign-outs run detach() only (no
        // clearOnLogout); the next account's registration of the SAME device
        // token must still be sent (review: cross-file tracer).
        fakeMessaging.token = 'device-token-1';
        await service.syncAfterLogin();
        expect(fakeApi.patchCalls, hasLength(1));

        service.detach();

        await service.syncAfterLogin();
        expect(fakeApi.patchCalls, hasLength(2));
        expect(fakeApi.patchCalls.last.data, {'fcm_token': 'device-token-1'});
      },
    );
  });
}

class _PatchCall {
  _PatchCall(this.path, this.data);

  final String path;
  final Map<String, dynamic>? data;
}

/// Minimal [ApiService] stand-in, mirroring user_profile_service_test.dart's
/// convention: no real network; records every PATCH attempt (including ones
/// configured to fail), throws when [patchError] is set, and can hold a
/// request in flight via [patchGate].
class _FakeApiService extends ApiService {
  _FakeApiService() : super(baseUrl: 'http://fake.local', authToken: null);

  final List<_PatchCall> patchCalls = [];
  Exception? patchError;
  Completer<void>? patchGate;

  @override
  Future<Response> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    patchCalls.add(_PatchCall(path, data as Map<String, dynamic>?));
    final gate = patchGate;
    if (gate != null) await gate.future;
    final error = patchError;
    if (error != null) throw error;
    return Response<dynamic>(requestOptions: RequestOptions(path: path));
  }
}

/// Overrides the [PushRegistrationService.messaging] test seam so no test
/// ever touches Firebase.initializeApp().
class _TestablePushRegistrationService extends PushRegistrationService {
  _TestablePushRegistrationService(super.apiService, this._messaging);

  final FirebaseMessaging _messaging;

  @override
  FirebaseMessaging get messaging => _messaging;
}

/// Upgrade-proof settings stub: the service only reads authorizationStatus;
/// any new field it starts reading fails loudly via noSuchMethod instead of
/// forcing this file to track NotificationSettings' 12-field constructor
/// across firebase_messaging upgrades.
class _FakeSettings implements NotificationSettings {
  @override
  AuthorizationStatus get authorizationStatus =>
      AuthorizationStatus.authorized;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// Hand-rolled fake (no mocking library in this suite): only the three
/// members the service uses are implemented; anything else is a loud
/// [NoSuchMethodError] via [noSuchMethod].
class _FakeMessaging implements FirebaseMessaging {
  String? token = 'default-token';
  Object? getTokenError;
  Future<String?> Function()? getTokenOverride;
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
  }) async {
    return _FakeSettings();
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
