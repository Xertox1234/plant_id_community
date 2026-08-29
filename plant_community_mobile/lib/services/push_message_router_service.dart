import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/routing/app_router.dart';

/// Registered via `FirebaseMessaging.onBackgroundMessage` in `main.dart`,
/// immediately after `Firebase.initializeApp()` succeeds and before
/// `runApp()`. The `vm:entry-point` pragma is required for Android AOT
/// builds — without it the release compiler tree-shakes the handler and it
/// is never invoked.
///
/// **This handler runs in a separate isolate**: no widget tree, no
/// `ProviderScope`, no `GoRouter` — it cannot navigate, and must never be
/// mistaken for a navigation hook. All it does is log, gated to debug
/// builds. Actual tap-to-navigate only ever happens inside
/// [PushMessageRouterService], via FCM's `onMessageOpenedApp` (warm resume)
/// or `getInitialMessage()` (cold start) — both of which only run on the
/// app's own isolate, after the user has tapped the notification and the
/// app has (re)launched into the foreground.
@pragma('vm:entry-point')
Future<void> pushBackgroundMessageHandler(RemoteMessage message) async {
  if (kDebugMode) {
    debugPrint('[PUSH] Background message received: ${message.data}');
  }
}

/// Routes a tapped forum push notification to its topic (and highlights the
/// post, when the payload carries one) — todo 311.
///
/// A sibling to `PushRegistrationService`, not an extension of it: token
/// registration is scoped to login/logout, tap-routing is scoped to the
/// app's whole lifetime, and the two lifecycles don't belong in the same
/// file.
///
/// FCM exposes exactly two tap entry points, both wired here:
/// - **Cold start** — the app was launched BY the tap (it wasn't already
///   running). [FirebaseMessaging.getInitialMessage] returns the message
///   that launched it; checked once, right after construction.
/// - **Warm resume** — the app was already running (foreground or
///   background) and the tap brought it forward.
///   [FirebaseMessaging.onMessageOpenedApp] fires the message.
///
/// ### The splash-screen race (cold start only — real bug, fixed here)
/// `SplashScreen` unconditionally calls `context.go(AppRoutes.home)` ~1.8s
/// after mount (a progress timer, then a settle delay). A cold-start push
/// that resolves before that timer fires would otherwise get silently wiped
/// out when splash reroutes to `/home` out from under it. The fix: on cold
/// start ONLY, this service calls `router.go(AppRoutes.home)` immediately
/// before `router.pushNamed('forumTopic', ...)`. That either pre-empts
/// splash's own `go(home)` (splash's `dispose()` runs, and its timer
/// callback's existing `if (!mounted) { timer.cancel(); return; }` guard
/// makes the now-orphaned timer a no-op on its next tick), or is a harmless
/// no-op if splash's timer already fired first. This step is deliberately
/// **not** applied on warm resume — the user could be anywhere in the app,
/// and forcing a detour through home would discard whatever screen they
/// were on.
class PushMessageRouterService {
  PushMessageRouterService(this.routerAccessor) {
    _openedAppSubscription = FirebaseMessaging.onMessageOpenedApp.listen(
      (message) => _route(message, isColdStart: false),
    );
    unawaited(_checkInitialMessage());
  }

  /// Reads the live router on every navigation rather than caching one at
  /// construction — `pushNamed`/`go` work from any `Ref`-holding service, no
  /// `BuildContext`/`navigatorKey` needed. Built by the provider factory as
  /// `() => ref.read(appRouterProvider)`.
  final GoRouter Function() routerAccessor;

  /// Test seam, mirroring `PushRegistrationService.messaging`: a lazy
  /// getter so constructing this service in a unit test never touches
  /// `Firebase.initializeApp()`; test subclasses override it with a fake.
  @visibleForTesting
  FirebaseMessaging get messaging => FirebaseMessaging.instance;

  StreamSubscription<RemoteMessage>? _openedAppSubscription;

  /// Bumped by [detach]. [_checkInitialMessage] captures it at entry and
  /// aborts if it changed across the `getInitialMessage()` await — mirrors
  /// `PushRegistrationService._epoch`.
  int _epoch = 0;

  Future<void> _checkInitialMessage() async {
    final epoch = _epoch;
    try {
      final initial = await messaging.getInitialMessage();
      if (initial == null || epoch != _epoch) return;
      _route(initial, isColdStart: true);
    } catch (e) {
      // Required, not optional: test/widget_test.dart and
      // test/integration/plant_identification_flow_test.dart both pump
      // MyApp without Firebase.initializeApp() and without overriding this
      // service's provider — accessing `messaging` above throws
      // synchronously ("no default Firebase app"), and that throw must not
      // escape into an unhandled zone error.
      if (kDebugMode) {
        debugPrint('[PUSH] getInitialMessage check failed: $e');
      }
    }
  }

  void _route(RemoteMessage message, {required bool isColdStart}) {
    final topicId = _parseId(message.data['topic_id']);
    if (topicId == null) {
      // Malformed/unroutable payload (e.g. a future moderation_decided-
      // shaped message with no usable topic) — silent no-op, never a crash.
      return;
    }
    final postId = _parseId(message.data['post_id']);

    final router = routerAccessor();
    if (isColdStart) {
      router.go(AppRoutes.home);
    }
    router.pushNamed(
      'forumTopic',
      pathParameters: {'id': '$topicId'},
      queryParameters: postId == null ? {} : {'postId': '$postId'},
    );
  }

  /// Stops listening. Called on provider disposal — this service is scoped
  /// to the app's lifetime, not to login/logout like `PushRegistrationService`.
  void detach() {
    _epoch++;
    _openedAppSubscription?.cancel();
    _openedAppSubscription = null;
  }
}

/// Parses an FCM data-payload value as an int. FCM data values are always
/// strings, but a missing key must be treated as absent — not as an empty
/// string that happens to fail the same parse — so this checks for `null`
/// before ever calling `.toString()`.
int? _parseId(dynamic raw) {
  if (raw == null) return null;
  return int.tryParse(raw.toString());
}

/// Singleton service provider, mirroring `pushRegistrationServiceProvider`'s
/// manual style. Constructed once and watched (not read) from
/// `MyApp.build()` so its cold-start/warm-resume listeners live for the
/// app's whole lifetime.
final pushMessageRouterServiceProvider = Provider<PushMessageRouterService>((
  ref,
) {
  final service = PushMessageRouterService(() => ref.read(appRouterProvider));
  ref.onDispose(service.detach);
  return service;
});
