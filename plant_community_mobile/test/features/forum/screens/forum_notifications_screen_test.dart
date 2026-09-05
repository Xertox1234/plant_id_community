import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_notifications_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';

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
      find.textContaining('alice quoted your post in "Fiddle leaf fig"'),
      findsOneWidget,
    );
    expect(find.byIcon(Icons.format_quote_outlined), findsOneWidget);

    await tester.tap(find.byType(ListTile));
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
      find.textContaining('mentioned you in "Fiddle leaf fig"'),
      findsOneWidget,
    );
    expect(
      find.textContaining('replied to "Watering schedule"'),
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

    expect(find.text('No notifications yet.'), findsOneWidget);
  });

  testWidgets('load more fetches the next page via the verbatim cursor URL', (
    tester,
  ) async {
    final page1 = CursorPage(
      items: [notification(id: 1)],
      next: 'https://api/forum/notifications/?cursor=p2',
    );
    final page2 = CursorPage(items: [notification(id: 2)]);
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
    expect(find.byType(ListTile), findsNWidgets(2));
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

    expect(find.byIcon(Icons.circle), findsOneWidget);

    await tester.tap(find.widgetWithText(TextButton, 'Mark all read'));
    await tester.pumpAndSettle();

    expect(api.markReadCalls, [null]);
    expect(find.byIcon(Icons.circle), findsNothing);
  });
}
