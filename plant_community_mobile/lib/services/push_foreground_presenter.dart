import 'dart:async';
import 'dart:collection';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/forum/providers/forum_providers.dart';
import '../features/garden/providers/garden_provider.dart';
import '../shared/root_scaffold_messenger.dart';
import 'auth_service.dart';
import 'push_message_router_service.dart';

/// A banner the presenter asks the app to show.
@immutable
class ForegroundBanner {
  const ForegroundBanner({
    required this.title,
    required this.body,
    required this.onView,
  });

  final String title;
  final String body;

  /// Opens what the push is about, as a tray tap would.
  final VoidCallback onView;
}

/// Handles pushes that arrive while the app is in the foreground (todo 621).
///
/// Owner decision 2026-10-12: a restrained in-app banner plus a refresh of
/// the data the push is about, never an OS banner too. iOS shows no OS
/// banner for a foreground message unless the app opts in, and this app
/// does not ([configureForegroundPresentation]); Android never draws one
/// for a foreground FCM message. So the banner here is the only alert.
///
/// - Every message refreshes its data (the bell count, the garden), even
///   a silent one.
/// - A routine event ([silentEvents], e.g. a moderation decision on the
///   user's own trust-autopublished post) and a data-only message never show
///   a banner.
/// - A message is handled once: FCM can deliver the same message again
///   (a retry after an accepted-but-timed-out send), so ids are remembered.
/// - Nothing is shown while signed out, and the memory is cleared on every
///   account change: a push for the previous account must not surface.
///
/// Android notification channels are scoped out of this slice (2026-10-12):
/// the Android release is blocked on signing (todo 387), and in the
/// foreground no channel is involved, since this banner is in-app. Background
/// tray pushes on Android keep FCM's default channel until that release.
class PushForegroundPresenter {
  PushForegroundPresenter({
    required Stream<RemoteMessage> messages,
    required this.showBanner,
    required this.refresh,
    required this.isSignedIn,
    required this.open,
  }) {
    _subscription = messages.listen(
      handle,
      onError: (Object e) {
        if (kDebugMode) debugPrint('[PUSH] Foreground stream error: $e');
      },
    );
  }

  /// Events that never show a banner (`_notification_content` in
  /// `backend/apps/forum_host/tasks.py` sends these data-only already; this
  /// is the client's half of the same rule).
  static const Set<String> silentEvents = {'moderation_decided'};

  /// How many message ids are remembered for deduplication.
  static const int rememberedIds = 64;

  final void Function(ForegroundBanner banner) showBanner;
  final void Function(String? event, Map<String, dynamic> data) refresh;
  final bool Function() isSignedIn;
  final void Function(RemoteMessage message) open;

  late final StreamSubscription<RemoteMessage> _subscription;
  final Queue<String> _seenOrder = Queue<String>();
  final Set<String> _seen = <String>{};
  bool _disposed = false;

  /// Handles one foreground message. Public for tests.
  @visibleForTesting
  void handle(RemoteMessage message) {
    if (_disposed || !isSignedIn()) return;
    final id = _idOf(message);
    if (id != null) {
      if (_seen.contains(id)) return;
      _seen.add(id);
      _seenOrder.addLast(id);
      if (_seenOrder.length > rememberedIds) {
        _seen.remove(_seenOrder.removeFirst());
      }
    }
    final event = message.data['event'] as String?;
    try {
      refresh(event, message.data);
    } catch (e) {
      if (kDebugMode) debugPrint('[PUSH] Foreground refresh failed: $e');
    }
    if (silentEvents.contains(event)) return;
    final title = message.notification?.title?.trim() ?? '';
    final body = message.notification?.body?.trim() ?? '';
    if (title.isEmpty && body.isEmpty) return; // data-only: silent
    showBanner(
      ForegroundBanner(title: title, body: body, onView: () => open(message)),
    );
  }

  /// The message id, or (when the platform gave none) a key built from the
  /// payload, so a duplicate without an id is still caught.
  static String? _idOf(RemoteMessage message) {
    final id = message.messageId;
    if (id != null && id.isNotEmpty) return id;
    if (message.data.isEmpty) return null;
    final keys = message.data.keys.toList()..sort();
    return [for (final k in keys) '$k=${message.data[k]}'].join('&');
  }

  /// Forgets every remembered id: a new account starts clean.
  void accountChanged() {
    _seen.clear();
    _seenOrder.clear();
  }

  void dispose() {
    _disposed = true;
    unawaited(_subscription.cancel());
  }
}

/// Turns iOS's foreground OS banner, sound and badge off for FCM messages,
/// explicitly: the in-app banner is the only foreground alert (todo 621).
/// Never throws: there is no Firebase app in widget tests.
Future<void> configureForegroundPresentation(
  FirebaseMessaging Function() messaging,
) async {
  try {
    await messaging().setForegroundNotificationPresentationOptions(
      alert: false,
      badge: false,
      sound: false,
    );
  } catch (e) {
    if (kDebugMode) debugPrint('[PUSH] Foreground presentation not set: $e');
  }
}

/// The restrained banner: a floating SnackBar with the title, the body and
/// a View action, on the app's root messenger.
void showForegroundBannerSnackBar(
  ScaffoldMessengerState? messenger,
  ForegroundBanner banner,
) {
  if (messenger == null) return;
  messenger.showSnackBar(
    SnackBar(
      behavior: SnackBarBehavior.floating,
      duration: const Duration(seconds: 4),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (banner.title.isNotEmpty)
            Text(
              banner.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          if (banner.body.isNotEmpty)
            Text(banner.body, maxLines: 2, overflow: TextOverflow.ellipsis),
        ],
      ),
      action: SnackBarAction(label: 'View', onPressed: banner.onView),
    ),
  );
}

/// The foreground message stream. A provider so tests can feed it.
final foregroundMessagesProvider = Provider<Stream<RemoteMessage>>(
  (ref) => FirebaseMessaging.onMessage,
);

/// Watched from `MyApp.build()`, so the listener lives as long as the app;
/// cancelled on disposal.
final pushForegroundPresenterProvider = Provider<PushForegroundPresenter>((
  ref,
) {
  final presenter = PushForegroundPresenter(
    messages: ref.watch(foregroundMessagesProvider),
    showBanner: (banner) => showForegroundBannerSnackBar(
      rootScaffoldMessengerKey.currentState,
      banner,
    ),
    refresh: (event, data) => refreshForPush(ref, event),
    isSignedIn: () => ref.read(authServiceProvider).isAuthenticated,
    open: (message) =>
        ref.read(pushMessageRouterServiceProvider).routeTap(message),
  );
  ref.listen<String?>(authServiceProvider.select((s) => s.firebaseUser?.uid), (
    previous,
    next,
  ) {
    if (previous != next) presenter.accountChanged();
  });
  unawaited(configureForegroundPresentation(() => FirebaseMessaging.instance));
  ref.onDispose(presenter.dispose);
  return presenter;
});

/// Refreshes what a push is about: the garden for a care reminder, the
/// notification bell and feed for a forum event.
void refreshForPush(Ref ref, String? event) {
  if (event == careTaskDueEvent) {
    ref.invalidate(gardenProvider);
    return;
  }
  ref.invalidate(unreadNotificationCountProvider);
  ref.invalidate(notificationsFeedProvider);
}
