import 'dart:async';

import 'package:dio/dio.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_service.dart';

/// Registers this device's FCM token with the Django forum profile so the
/// backend push pipeline (`send_forum_push`) can reach it (todo 253 slice 6).
///
/// The token is written to the existing write-only `fcm_token` field via
/// `PATCH /forum/me/profile/` — no dedicated endpoint. The token is a
/// credential: it is never logged (length only) and the API never echoes it.
///
/// Lifecycle (wired in AuthService):
/// - after a successful JWT exchange → [syncAfterLogin]
/// - in signOut(), BEFORE Firebase sign-out (the PATCH needs the still-valid
///   JWT) → [clearOnLogout]
/// - on any signed-out auth state (session expiry, external sign-out) →
///   [detach]
///
/// Known residual race (accepted, ms-scale): a rotation PATCH already in
/// flight when sign-out starts cannot be recalled, so it can land after the
/// logout clear. The server bounds the damage — registering the token from
/// any other account releases it from this profile (MeProfileSerializer's
/// device-uniqueness rule) — and the next login/logout cycle self-corrects.
class PushRegistrationService {
  PushRegistrationService(this._apiService);

  final ApiService _apiService;

  static const String _profilePath = '/forum/me/profile/';
  static const Duration _logoutClearTimeout = Duration(seconds: 3);

  /// Test seam, mirroring AuthService.firebaseAuth: a lazy getter so
  /// constructing the service in a unit test never touches
  /// Firebase.initializeApp(); test subclasses override it with a fake.
  @visibleForTesting
  FirebaseMessaging get messaging => FirebaseMessaging.instance;

  StreamSubscription<String>? _refreshSubscription;

  /// Bumped by [detach]. Async work captures it at entry and aborts when it
  /// changed across an await — an in-flight sync parked on the permission
  /// dialog or getToken() must not register a token, or re-attach the
  /// rotation listener, after sign-out already cleared everything (mirrors
  /// AuthService._authGeneration; slice-6 review, confirmed empirically).
  int _epoch = 0;

  String? _lastSyncedToken;

  /// Last token successfully PATCHed this session. Exposed so the on-device
  /// E2E can poll for registration completion instead of blind-waiting.
  @visibleForTesting
  String? get lastSyncedToken => _lastSyncedToken;

  /// Obtain this device's FCM token and register it with the backend.
  ///
  /// Fire-and-forget from the auth flow: every failure is caught and logged —
  /// push registration must never break login. The token-rotation listener
  /// is attached BEFORE the token fetch/registration, so a null token (iOS
  /// APNS still warming up) or a failed first PATCH still heals on the next
  /// rotation event instead of silencing the whole session (slice-6 review).
  Future<void> syncAfterLogin() async {
    final epoch = _epoch;
    try {
      final settings = await messaging.requestPermission();
      if (kDebugMode) {
        debugPrint(
          '[PUSH] Notification permission: ${settings.authorizationStatus}',
        );
      }
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

      // A denied permission still yields a valid token on Android — the tray
      // stays silent but registration works, so proceed regardless.
      final token = await messaging.getToken();
      if (epoch != _epoch) return; // signed out while fetching the token
      if (token == null || token.isEmpty) {
        if (kDebugMode) {
          debugPrint(
            '[PUSH] No FCM token yet; the rotation listener will '
            'register it when it arrives',
          );
        }
        return;
      }

      if (token != _lastSyncedToken) {
        await registerToken(token);
      } else if (kDebugMode) {
        debugPrint('[PUSH] FCM token unchanged since last sync; skipping');
      }
    } catch (e) {
      // Never rethrow into the login flow. The token itself is never logged.
      if (kDebugMode) {
        debugPrint('[PUSH] FCM registration skipped: $e');
      }
    }
  }

  /// PATCH the token onto the caller's forum profile. Never throws: failures
  /// are logged (redacted) and the sync marker stays unset, so the next
  /// login or token rotation retries naturally.
  Future<void> registerToken(String token) async {
    if (token == _lastSyncedToken) {
      // FCM emits an onTokenRefresh for the token's FIRST generation too —
      // observed live in the on-device E2E as a duplicate PATCH right after
      // registration.
      return;
    }
    final epoch = _epoch;
    try {
      await _apiService.patch(_profilePath, data: {'fcm_token': token});
      if (epoch != _epoch) {
        // Signed out while the PATCH was in flight — the marker must not
        // resurrect for the next account on this device.
        return;
      }
      _lastSyncedToken = token;
      if (kDebugMode) {
        debugPrint('[PUSH] FCM token registered (${token.length} chars)');
      }
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[PUSH] FCM token registration failed: $e');
      }
    }
  }

  /// Best-effort server-side token clear for sign-out. Never throws; bounded
  /// by a short timeout so a slow network can't stall sign-out. Skipped
  /// entirely when this session never registered a token — a blank PATCH
  /// would only cost sign-out latency and could wipe a registration another
  /// account on this device legitimately owns.
  Future<void> clearOnLogout() async {
    final hadRegistration = _lastSyncedToken != null;
    detach();
    if (!hadRegistration) {
      return;
    }
    try {
      // skipSessionExpiryKey rides the REQUEST: if the JWT already expired,
      // this PATCH's 401 must not convert an intentional sign-out into the
      // session-expired flow — even when the response lands after our
      // timeout abandoned it (Future.timeout abandons, Dio keeps going).
      await _apiService
          .patch(
            _profilePath,
            data: {'fcm_token': ''},
            options: Options(extra: {ApiService.skipSessionExpiryKey: true}),
          )
          .timeout(_logoutClearTimeout);
      if (kDebugMode) {
        debugPrint('[PUSH] FCM token cleared on logout');
      }
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[PUSH] FCM token clear on logout failed (ignored): $e');
      }
    }
  }

  /// Full local reset, no network: stop listening for rotations, invalidate
  /// in-flight work (epoch bump), and forget the sync marker — a different
  /// user may sign in next on this device, and their registration must not
  /// be deduped against ours (slice-6 review). Runs on every signed-out auth
  /// state and on provider disposal.
  void detach() {
    _epoch++;
    _refreshSubscription?.cancel();
    _refreshSubscription = null;
    _lastSyncedToken = null;
  }
}

/// Singleton service provider, mirroring [apiServiceProvider]'s manual style —
/// a stateless-between-sessions service object, no codegen needed (the
/// docs/patterns/riverpod.md "plain Provider" DI pattern).
final pushRegistrationServiceProvider = Provider<PushRegistrationService>((
  ref,
) {
  final service = PushRegistrationService(ref.watch(apiServiceProvider));
  ref.onDispose(service.detach);
  return service;
});
