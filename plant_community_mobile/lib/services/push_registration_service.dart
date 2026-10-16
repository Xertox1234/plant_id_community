import 'dart:async';

import 'package:dio/dio.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

import 'api_service.dart';

/// What the OS lets this app show (todo 621).
enum PushPermission {
  /// Not read yet, or the platform would not say.
  unknown,

  /// The user has not been asked.
  notDetermined,

  /// Turned off for this app; only the OS settings can turn it back on.
  denied,

  /// Allowed (iOS provisional counts: it delivers quietly).
  granted,
}

/// Where this device's backend registration stands (todo 621).
enum PushRegistration {
  /// No account signed in on this device.
  signedOut,

  /// A registration is in flight or scheduled.
  pending,

  /// The backend has this device's token for the signed-in account.
  registered,

  /// FCM has not issued a token yet (iOS APNs still warming up, Play
  /// services missing). Retried when it arrives and on a bounded schedule.
  tokenUnavailable,

  /// The backend refused or could not be reached, after the bounded retries.
  failed,
}

/// The user-visible push status, read by the settings tile.
@immutable
class PushStatus {
  const PushStatus({
    this.permission = PushPermission.unknown,
    this.registration = PushRegistration.signedOut,
  });

  final PushPermission permission;
  final PushRegistration registration;

  PushStatus copyWith({
    PushPermission? permission,
    PushRegistration? registration,
  }) => PushStatus(
    permission: permission ?? this.permission,
    registration: registration ?? this.registration,
  );

  @override
  bool operator ==(Object other) =>
      other is PushStatus &&
      other.permission == permission &&
      other.registration == registration;

  @override
  int get hashCode => Object.hash(permission, registration);

  @override
  String toString() => 'PushStatus($permission, $registration)';
}

/// Registers this device's FCM token with the backend so forum and care
/// pushes reach it (todos 253 slice 6, 621).
///
/// One registration per device: `POST /push-devices/` with the token, a
/// random installation id kept in secure storage, and the platform. An
/// account may hold several devices, and signing out removes only this one
/// (`POST /push-devices/unregister/` with this device's token). The token is
/// a credential: it is never logged (length only) and the API never echoes
/// it.
///
/// Deploy skew: a backend from before todo 621 has no `/push-devices/`
/// route, so a 404 falls back to the legacy `PATCH /forum/me/profile/`
/// `fcm_token` field, and sign-out then clears it the legacy way.
///
/// Lifecycle (wired in AuthService):
/// - after a successful JWT exchange → [syncAfterLogin]
/// - in signOut(), BEFORE Firebase sign-out (the request needs the
///   still-valid JWT) → [clearOnLogout]
/// - on any signed-out auth state (session expiry, external sign-out) →
///   [detach]
/// - when the app returns to the foreground → [reconcile] (the provider
///   wires an [AppLifecycleListener]).
///
/// Login is never blocked: every call here catches its own failures. A
/// failed registration is retried on [retryDelays], then waits for the
/// next resume, rotation or login, and [status] says so meanwhile.
class PushRegistrationService {
  PushRegistrationService(
    this._apiService, {
    Future<String?> Function()? installationId,
    this.retryDelays = defaultRetryDelays,
    this.reconcileInterval = defaultReconcileInterval,
    String? platform,
  }) : _installationId = installationId ?? _secureInstallationId,
       _platform = platform ?? _currentPlatform();

  final ApiService _apiService;
  final Future<String?> Function() _installationId;
  final String _platform;

  static const String devicesPath = '/push-devices/';
  static const String unregisterPath = '/push-devices/unregister/';
  static const String legacyProfilePath = '/forum/me/profile/';

  /// Bounded recovery after a failed registration or a missing token: these
  /// waits, then nothing until the next resume, rotation or login.
  static const List<Duration> defaultRetryDelays = [
    Duration(seconds: 30),
    Duration(minutes: 2),
    Duration(minutes: 10),
  ];

  /// A resume reconciles at most this often, unless forced.
  static const Duration defaultReconcileInterval = Duration(minutes: 5);

  final List<Duration> retryDelays;
  final Duration reconcileInterval;

  /// The whole budget of sign-out's unregister. When the access token
  /// expired while the app sat idle, the request, its 401, `getIdToken`, the
  /// token exchange and the re-sent request must all fit in it. Past it the
  /// unregister is abandoned and sign-out goes on: a slow network must not
  /// hold the user on a sign-out spinner (todo 500 finding 6, a documented
  /// limit). What that costs is bounded: the token stays registered to the
  /// signed-out account until any account registers it on this device again,
  /// which moves it (the backend's one-account-per-token rule).
  static const Duration _logoutClearTimeout = Duration(seconds: 3);

  /// Test seam, mirroring AuthService.firebaseAuth: a lazy getter so
  /// constructing the service in a unit test never touches
  /// Firebase.initializeApp(); test subclasses override it with a fake.
  @visibleForTesting
  FirebaseMessaging get messaging => FirebaseMessaging.instance;

  /// The user-visible status, for the settings tile.
  final ValueNotifier<PushStatus> status = ValueNotifier(const PushStatus());

  StreamSubscription<String>? _refreshSubscription;

  /// Bumped by [detach]. Async work captures it at entry and aborts when it
  /// changed across an await — an in-flight sync parked on the permission
  /// dialog or getToken() must not register a token, or re-attach the
  /// rotation listener, after sign-out already cleared everything (mirrors
  /// AuthService._authGeneration; slice-6 review, confirmed empirically).
  int _epoch = 0;

  /// True between [syncAfterLogin] and [detach]: an account is signed in.
  bool _active = false;

  String? _lastSyncedToken;

  /// Whether [_lastSyncedToken] went through the legacy profile field (a
  /// backend from before todo 621), so sign-out clears it the same way.
  bool _syncedViaLegacy = false;

  /// The registration request in flight, if any. Sign-out waits for it
  /// (inside its bound) so the unregister cannot land first and leave the
  /// token registered to the signed-out account.
  Future<void>? _inFlight;

  Timer? _retryTimer;
  int _retryAttempt = 0;
  DateTime? _lastReconcile;

  /// Last token successfully registered this session. Exposed so the
  /// on-device E2E can poll for registration completion instead of
  /// blind-waiting.
  @visibleForTesting
  String? get lastSyncedToken => _lastSyncedToken;

  /// Obtain this device's FCM token and register it with the backend.
  ///
  /// Fire-and-forget from the auth flow: every failure is caught — push
  /// registration must never break login. The permission dialog is shown
  /// only when the user has never been asked; a user who said no is not
  /// asked again (the settings tile sends them to the OS settings). The
  /// token-rotation listener is attached BEFORE the token fetch, so a null
  /// token (iOS APNs still warming up) or a failed first registration still
  /// heals on the next rotation event (slice-6 review).
  Future<void> syncAfterLogin() async {
    final epoch = _epoch;
    _active = true;
    _retryAttempt = 0;
    _setStatus(registration: PushRegistration.pending);
    try {
      await _refreshPermission(askIfUndetermined: true);
      if (epoch != _epoch) return; // signed out while awaiting the dialog

      await _refreshSubscription?.cancel();
      if (epoch != _epoch) return; // cancel() is an await too (review sweep)
      _refreshSubscription = messaging.onTokenRefresh.listen(
        registerToken,
        onError: (Object e) {
          // A platform error event (e.g. Android SERVICE_NOT_AVAILABLE)
          // must not become an unhandled zone error.
          if (kDebugMode) {
            debugPrint('[PUSH] Token-refresh stream error: $e');
          }
        },
      );
      await _syncToken(epoch);
    } catch (e) {
      // Never rethrow into the login flow. The token itself is never logged.
      if (kDebugMode) {
        debugPrint('[PUSH] FCM registration skipped: $e');
      }
      if (epoch == _epoch) {
        _setStatus(registration: PushRegistration.tokenUnavailable);
        _scheduleRetry(epoch);
      }
    }
  }

  /// Fetch the token and register it unless this session already did.
  Future<void> _syncToken(int epoch) async {
    // A denied permission still yields a valid token on Android — the tray
    // stays silent but registration works, so proceed regardless; [status]
    // carries the permission separately.
    final token = await messaging.getToken();
    if (epoch != _epoch) return; // signed out while fetching the token
    if (token == null || token.isEmpty) {
      if (kDebugMode) {
        debugPrint(
          '[PUSH] No FCM token yet; the rotation listener or a retry will '
          'register it',
        );
      }
      _setStatus(registration: PushRegistration.tokenUnavailable);
      _scheduleRetry(epoch);
      return;
    }
    if (token != _lastSyncedToken) {
      await registerToken(token);
    } else {
      _setStatus(registration: PushRegistration.registered);
      if (kDebugMode) {
        debugPrint('[PUSH] FCM token unchanged since last sync; skipping');
      }
    }
  }

  /// Register the token for the signed-in account. Never throws: failures
  /// are logged (redacted), [status] says so, and a bounded retry is
  /// scheduled; the sync marker stays unset, so the next login, rotation or
  /// resume retries too.
  Future<void> registerToken(String token) async {
    if (token == _lastSyncedToken) {
      // FCM emits an onTokenRefresh for the token's FIRST generation too —
      // observed live in the on-device E2E as a duplicate request right
      // after registration.
      return;
    }
    final epoch = _epoch;
    final done = Completer<void>();
    _inFlight = done.future;
    _setStatus(registration: PushRegistration.pending);
    try {
      final viaLegacy = await _register(token);
      if (epoch != _epoch) {
        // Signed out while the request was in flight — the marker must not
        // resurrect for the next account on this device.
        return;
      }
      _lastSyncedToken = token;
      _syncedViaLegacy = viaLegacy;
      _retryAttempt = 0;
      _retryTimer?.cancel();
      _setStatus(registration: PushRegistration.registered);
      if (kDebugMode) {
        debugPrint('[PUSH] FCM token registered (${token.length} chars)');
      }
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[PUSH] FCM token registration failed: $e');
      }
      if (epoch == _epoch && _active) {
        _setStatus(registration: PushRegistration.failed);
        if (_isRetryable(e)) _scheduleRetry(epoch);
      }
    } finally {
      done.complete();
      if (identical(_inFlight, done.future)) _inFlight = null;
    }
  }

  /// One registration request; true when it had to use the legacy field.
  Future<bool> _register(String token) async {
    final installationId = await _installationId();
    try {
      await _apiService.post(
        devicesPath,
        data: {
          'token': token,
          'installation_id': ?installationId,
          if (_platform.isNotEmpty) 'platform': _platform,
        },
      );
      return false;
    } on ApiException catch (e) {
      if (e.statusCode != 404) rethrow;
      // A backend from before todo 621 (deploy skew).
      await _apiService.patch(legacyProfilePath, data: {'fcm_token': token});
      return true;
    }
  }

  /// A network error, a 5xx or a lost race (409) may pass on retry. A 400
  /// will not, and a 429 must not be retried (docs/rules/flutter.md): both
  /// wait for the next resume, rotation or login.
  static bool _isRetryable(Object e) {
    if (e is! ApiException) return true;
    final code = e.statusCode;
    return code == null || code >= 500 || code == 409;
  }

  /// Retry after [retryDelays], a bounded number of times.
  void _scheduleRetry(int epoch) {
    _retryTimer?.cancel();
    if (_retryAttempt >= retryDelays.length) return;
    final delay = retryDelays[_retryAttempt++];
    _retryTimer = Timer(delay, () {
      if (epoch != _epoch || !_active) return;
      unawaited(_retry(epoch));
    });
  }

  Future<void> _retry(int epoch) async {
    try {
      await _syncToken(epoch);
    } catch (e) {
      if (kDebugMode) debugPrint('[PUSH] FCM registration retry failed: $e');
      if (epoch == _epoch) {
        _setStatus(registration: PushRegistration.tokenUnavailable);
        _scheduleRetry(epoch);
      }
    }
  }

  /// Re-check the permission and the registration, e.g. when the app comes
  /// back to the foreground (the user may have just changed the OS setting,
  /// or the network may be back). At most once per [reconcileInterval]
  /// unless [force] (the settings tile's retry). Never asks for permission
  /// and never throws. Starts a fresh round of bounded retries.
  Future<void> reconcile({bool force = false}) async {
    if (!_active) return;
    final now = DateTime.now();
    final last = _lastReconcile;
    if (!force && last != null && now.difference(last) < reconcileInterval) {
      return;
    }
    _lastReconcile = now;
    final epoch = _epoch;
    _retryAttempt = 0;
    try {
      await _refreshPermission(askIfUndetermined: false);
      if (epoch != _epoch) return;
      await _syncToken(epoch);
    } catch (e) {
      if (kDebugMode) debugPrint('[PUSH] Push reconcile failed: $e');
    }
  }

  /// Ask for notification permission now — the settings tile's "Allow"
  /// button, a contextual ask. When the user already said no, the OS will
  /// not ask again; the tile offers the OS settings instead.
  Future<void> requestPermission() async {
    try {
      final settings = await messaging.requestPermission();
      _setStatus(permission: _permissionOf(settings.authorizationStatus));
    } catch (e) {
      if (kDebugMode) debugPrint('[PUSH] Permission request failed: $e');
    }
  }

  Future<void> _refreshPermission({required bool askIfUndetermined}) async {
    // Its own guard: reading the permission must never stop the token from
    // being registered (a denied Android device still receives data).
    try {
      var settings = await messaging.getNotificationSettings();
      if (askIfUndetermined &&
          settings.authorizationStatus == AuthorizationStatus.notDetermined) {
        settings = await messaging.requestPermission();
      }
      if (kDebugMode) {
        debugPrint(
          '[PUSH] Notification permission: ${settings.authorizationStatus}',
        );
      }
      _setStatus(permission: _permissionOf(settings.authorizationStatus));
    } catch (e) {
      if (kDebugMode) debugPrint('[PUSH] Permission check failed: $e');
      _setStatus(permission: PushPermission.unknown);
    }
  }

  static PushPermission _permissionOf(AuthorizationStatus s) => switch (s) {
    AuthorizationStatus.authorized => PushPermission.granted,
    AuthorizationStatus.provisional => PushPermission.granted,
    AuthorizationStatus.denied => PushPermission.denied,
    AuthorizationStatus.notDetermined => PushPermission.notDetermined,
  };

  /// Best-effort server-side unregister for sign-out: removes this device
  /// only, never the account's other devices. Never throws; bounded by a
  /// short timeout so a slow network can't stall sign-out. Skipped entirely
  /// when this session never registered a token — it would only cost
  /// sign-out latency. A registration still in flight is awaited first
  /// (inside the bound), so it cannot land after the unregister.
  Future<void> clearOnLogout() async {
    final pending = _inFlight;
    final deadline = DateTime.now().add(_logoutClearTimeout);
    if (pending != null) {
      try {
        await pending.timeout(_logoutClearTimeout);
      } catch (_) {
        // Abandoned at the bound; sign-out goes on.
      }
    }
    final token = _lastSyncedToken;
    final viaLegacy = _syncedViaLegacy;
    detach();
    if (token == null) {
      return;
    }
    final remaining = deadline.difference(DateTime.now());
    if (remaining <= Duration.zero) return;
    // skipSessionExpiryKey rides the REQUEST: if the JWT already expired,
    // this request's 401 must not convert an intentional sign-out into the
    // session-expired flow — even when the response lands after our
    // timeout abandoned it (Future.timeout abandons, Dio keeps going).
    // It still refreshes the token and re-sends once, so a JWT that
    // expired while the app sat idle (15 min in prod) does not leave this
    // device receiving the signed-out user's pushes (todo 498).
    final options = Options(extra: {ApiService.skipSessionExpiryKey: true});
    try {
      if (viaLegacy) {
        await _apiService
            .patch(legacyProfilePath, data: {'fcm_token': ''}, options: options)
            .timeout(remaining);
      } else {
        await _apiService
            .post(unregisterPath, data: {'token': token}, options: options)
            .timeout(remaining);
      }
      if (kDebugMode) {
        debugPrint('[PUSH] FCM device unregistered on logout');
      }
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[PUSH] FCM unregister on logout failed (ignored): $e');
      }
    }
  }

  /// Full local reset, no network: stop listening for rotations, cancel the
  /// retry schedule, invalidate in-flight work (epoch bump), and forget the
  /// sync marker — a different user may sign in next on this device, and
  /// their registration must not be deduped against ours (slice-6 review).
  /// Runs on every signed-out auth state and on provider disposal.
  void detach() {
    _epoch++;
    _active = false;
    _refreshSubscription?.cancel();
    _refreshSubscription = null;
    _retryTimer?.cancel();
    _retryTimer = null;
    _retryAttempt = 0;
    _lastReconcile = null;
    _lastSyncedToken = null;
    _syncedViaLegacy = false;
    _setStatus(registration: PushRegistration.signedOut);
  }

  void _setStatus({
    PushPermission? permission,
    PushRegistration? registration,
  }) {
    status.value = status.value.copyWith(
      permission: permission,
      registration: registration,
    );
  }
}

/// Where the installation id lives (todo 650 #7). Under a new key: the one
/// before it was stored with the default iOS accessibility (WhenUnlocked),
/// which an encrypted backup carries to a restored phone, so two phones
/// shared one id and each registration deleted the other's row. A new key,
/// not new options on the old one: the iOS plugin matches the accessibility
/// on read, so the old item would read as missing and block the write.
@visibleForTesting
const pushInstallationIdKey = 'push_installation_id_device';
const _legacyInstallationIdKey = 'push_installation_id';

/// `ThisDeviceOnly`: never restored onto another device, so a restored
/// phone mints its own id. After first unlock, so a token refresh in the
/// background can still read it. Android keeps its default.
@visibleForTesting
const pushInstallationIdStorage = FlutterSecureStorage(
  iOptions: IOSOptions(
    accessibility: KeychainAccessibility.first_unlock_this_device,
  ),
);
String? _cachedInstallationId;

/// Forgets the id read this process, so a test can read storage again.
@visibleForTesting
void resetInstallationIdCache() => _cachedInstallationId = null;

/// [_secureInstallationId], for tests.
@visibleForTesting
Future<String?> secureInstallationIdForTesting() => _secureInstallationId();

/// A random id for this install, kept in secure storage so a rotated token
/// replaces this device's registration instead of adding one. Null when
/// storage is unavailable; the registration then goes without it.
///
/// An install that kept its id under the old key mints a new one once; the
/// backend then updates that device's row in place (same token).
Future<String?> _secureInstallationId() async {
  final cached = _cachedInstallationId;
  if (cached != null) return cached;
  try {
    const storage = pushInstallationIdStorage;
    var id = await storage.read(key: pushInstallationIdKey);
    if (id == null || id.isEmpty) {
      id = const Uuid().v4();
      await storage.write(key: pushInstallationIdKey, value: id);
      // The old id may be another phone's (a restore): never reused. Deleted
      // with the default options it was written with (the iOS plugin matches
      // accessibility), and on its own: a failure here never loses the new id.
      try {
        await const FlutterSecureStorage().delete(
          key: _legacyInstallationIdKey,
        );
      } catch (_) {
        // A leftover item is only clutter: nothing reads the old key.
      }
    }
    return _cachedInstallationId = id;
  } catch (e) {
    if (kDebugMode) debugPrint('[PUSH] Installation id unavailable: $e');
    return null;
  }
}

String _currentPlatform() => switch (defaultTargetPlatform) {
  TargetPlatform.iOS => 'ios',
  TargetPlatform.android => 'android',
  _ => '',
};

/// Singleton service provider, mirroring [apiServiceProvider]'s manual style —
/// a stateless-between-sessions service object, no codegen needed (the
/// docs/patterns/riverpod.md "plain Provider" DI pattern). Reconciles on
/// every return to the foreground.
final pushRegistrationServiceProvider = Provider<PushRegistrationService>((
  ref,
) {
  final service = PushRegistrationService(ref.watch(apiServiceProvider));
  AppLifecycleListener? lifecycle;
  try {
    lifecycle = AppLifecycleListener(
      onResume: () => unawaited(service.reconcile()),
    );
  } catch (_) {
    // No widgets binding (a plain unit test): nothing to reconcile on.
  }
  ref.onDispose(() {
    lifecycle?.dispose();
    service.detach();
    service.status.dispose();
  });
  return service;
});
