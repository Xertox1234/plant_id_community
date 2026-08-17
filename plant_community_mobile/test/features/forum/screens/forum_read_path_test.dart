import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_composer_screen.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_thread_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

void main() {
  testWidgets('forum home lists boards and sync-backed recent topics', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..boards = const [
        ForumBoard(
          id: 1,
          title: 'General',
          slug: 'general',
          description: 'Chat',
          topicCount: 2,
          postCount: 5,
        ),
      ]
      ..syncPages = [
        ForumSyncPage(
          topics: [stub(id: 1, title: 'Recent one')],
          deleted: const [],
          hasMore: false,
          nextSince: DateTime.utc(2026, 1, 1),
          nextSinceId: 1,
        ),
      ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false),
          ),
        ],
        child: const MaterialApp(home: ForumScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('General'), findsOneWidget);
    expect(find.text('Recent one'), findsOneWidget);
  });

  testWidgets('forum home shows the unread notification count on the bell', (
    tester,
  ) async {
    final api = FakeForumApi()..unreadCount = 3;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: true),
          ),
        ],
        child: const MaterialApp(home: ForumScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.notifications_outlined), findsOneWidget);
    expect(find.text('3'), findsOneWidget);
  });

  testWidgets('thread screen renders posts with rendered bodies', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..topicDetail = topicDetail(title: 'Monstera help')
      ..posts = CursorPage(
        items: [
          post(id: 1, body: const [ParagraphBlock('Leaves turning yellow')]),
        ],
      );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false),
          ),
        ],
        child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Monstera help'), findsOneWidget);
    expect(find.textContaining('Leaves turning yellow'), findsOneWidget);
  });

  testWidgets('a pending post surfaces the awaiting-moderation marker', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..topicDetail = topicDetail()
      ..posts = CursorPage(items: [post(id: 2, isPending: true)]);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false),
          ),
        ],
        child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Awaiting moderation'), findsOneWidget);
  });

  testWidgets('subscribe toggle reflects isSubscribed and flips on tap', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..topicDetail = topicDetail(id: 10)
      ..posts = CursorPage(items: [post(id: 1)]);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: true),
          ),
        ],
        child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
      ),
    );
    await tester.pumpAndSettle();

    // Starts unsubscribed (the topicDetail() fixture default).
    expect(find.byIcon(Icons.notifications_none), findsOneWidget);
    expect(find.byIcon(Icons.notifications_active), findsNothing);

    await tester.tap(find.byIcon(Icons.notifications_none));
    await tester.pumpAndSettle();

    expect(api.subscribeCalls, [10]);
    expect(find.byIcon(Icons.notifications_active), findsOneWidget);
    expect(find.byIcon(Icons.notifications_none), findsNothing);
  });

  testWidgets('composer shows the notify-and-return moderation notice', (
    tester,
  ) async {
    final api = FakeForumApi()..replyStatus = ForumModerationStatus.pending;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: true),
          ),
        ],
        child: const MaterialApp(
          home: ForumComposerScreen(args: ForumComposeArgs.reply(topicId: 10)),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'my reply');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Post'));
    await tester.pumpAndSettle();

    expect(find.textContaining('awaiting moderation'), findsOneWidget);
    expect(api.createReplyKeys, hasLength(1));
  });
}
