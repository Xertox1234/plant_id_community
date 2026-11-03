import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_notifications_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_surfaces.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../support/forum_test_support.dart';

void main() {
  testWidgets('a quote reads "quoted your post" and opens the quoting reply '
      'exactly like a reply does (todo 342)', (tester) async {
    final api = FakeForumApi()
      ..notifications = [
        notification(
          id: 1,
          verb: 'quote',
          topicTitle: 'Fiddle leaf fig',
          postId: 55,
          quotedPostId: 12,
        ),
      ];
    final opened = <Uri>[];
    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, _) => const ForumNotificationsScreen()),
        GoRoute(
          path: '/forum/topics/:id',
          name: 'forumTopic',
          builder: (_, state) {
            opened.add(state.uri);
            return const Scaffold(body: Text('topic'));
          },
        ),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.textContaining('alice quoted your post in Fiddle leaf fig'),
      findsOneWidget,
    );
    expect(find.byIcon(LucideIcons.quote), findsOneWidget);

    await tester.tap(find.byType(CanopyCard));
    await tester.pumpAndSettle();

    expect(api.markReadCalls.single, [1]);
    // Deep-links to the QUOTING post (`post_id`), not the quoted one.
    expect(opened.single.path, '/forum/topics/10');
    expect(opened.single.queryParameters, {'postId': '55'});
  });

  testWidgets('lists notifications, newest first, with read/unread state', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..notifications = [
        notification(id: 1, verb: 'mention', topicTitle: 'Fiddle leaf fig'),
        notification(
          id: 2,
          verb: 'reply',
          topicTitle: 'Watering schedule',
          readAt: DateTime(2026, 1, 2),
        ),
      ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: ForumNotificationsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.textContaining('mentioned you in Fiddle leaf fig'),
      findsOneWidget,
    );
    expect(find.textContaining('replied to Watering schedule'), findsOneWidget);
    // Unread goes under "New", read under "Earlier".
    expect(find.text('NEW'), findsOneWidget);
    expect(find.text('EARLIER'), findsOneWidget);
    expect(
      tester.getTopLeft(find.text('EARLIER')).dy,
      greaterThan(tester.getTopLeft(find.textContaining('Fiddle leaf fig')).dy),
    );
    expect(
      find.byKey(const ValueKey('notification-unread-dot')),
      findsOneWidget,
    );
  });

  testWidgets('empty state renders when there are no notifications', (
    tester,
  ) async {
    final api = FakeForumApi();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: ForumNotificationsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text("You're all caught up"), findsOneWidget);
  });

  testWidgets('load more fetches the next page via the verbatim cursor URL', (
    tester,
  ) async {
    final page1 = CursorPage(
      items: [notification(id: 1)],
      next: 'https://api/forum/notifications/?cursor=p2',
    );
    // A different topic, so the two rows don't fold into one card.
    final page2 = CursorPage(items: [notification(id: 2, topicId: 11)]);
    final api = FakeForumApi()..notificationPages = [page1, page2];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: ForumNotificationsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(OutlinedButton, 'Load more'));
    await tester.pumpAndSettle();

    expect(api.fetchNotificationsCalls, [null, page1.next]);
    expect(find.byType(CanopyCard), findsNWidgets(2));
  });

  testWidgets('mark all read clears the unread markers', (tester) async {
    final api = FakeForumApi()
      ..notifications = [notification(id: 1, readAt: null)]
      ..unreadCount = 1;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: ForumNotificationsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey('notification-unread-dot')),
      findsOneWidget,
    );

    await tester.tap(find.widgetWithText(TextButton, 'Mark all read'));
    await tester.pumpAndSettle();

    expect(api.markReadCalls, [null]);
    expect(find.byKey(const ValueKey('notification-unread-dot')), findsNothing);
  });

  testWidgets('consecutive same-actor replies to one topic fold into one '
      'card; tapping it marks them all read and opens the newest', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..notifications = [
        notification(id: 3, postId: 30),
        notification(id: 2, postId: 20),
        notification(id: 1, postId: 10),
      ];
    final opened = <Uri>[];
    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, _) => const ForumNotificationsScreen()),
        GoRoute(
          path: '/forum/topics/:id',
          name: 'forumTopic',
          builder: (_, state) {
            opened.add(state.uri);
            return const Scaffold(body: Text('topic'));
          },
        ),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(CanopyCard), findsOneWidget);
    expect(find.textContaining('3 replies'), findsOneWidget);

    await tester.tap(find.byType(CanopyCard));
    await tester.pumpAndSettle();

    expect(api.markReadCalls.single, [3, 2, 1]);
    expect(opened.single.queryParameters, {'postId': '30'});
  });

  test('groupNotifications folds only neighbours with the same verb, actor '
      'and topic', () {
    final groups = groupNotifications([
      notification(id: 5),
      notification(id: 4),
      notification(id: 3, verb: 'mention'),
      notification(id: 2),
      notification(id: 1, topicId: null),
      notification(id: 0, topicId: null),
    ]);
    expect(
      [for (final g in groups) g.items.map((n) => n.id).toList()],
      [
        [5, 4],
        [3],
        [2],
        [1],
        [0],
      ],
    );
  });
}
