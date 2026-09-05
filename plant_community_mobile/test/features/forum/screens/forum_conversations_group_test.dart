import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_conversations_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_avatar_cluster.dart';

import '../support/forum_test_support.dart';

Widget _wrap(FakeForumApi api) => ProviderScope(
  overrides: [forumApiProvider.overrideWithValue(api)],
  child: const MaterialApp(home: ForumConversationsScreen()),
);

/// The inbox behind a router that records where each tap navigates.
Widget _routed(FakeForumApi api, List<Uri> opened) {
  Widget stub(BuildContext _, GoRouterState state) {
    opened.add(state.uri);
    // An AppBar so `tester.pageBack()` has a back button to press.
    return Scaffold(appBar: AppBar(), body: const Text('stub'));
  }

  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, _) => const ForumConversationsScreen()),
      GoRoute(
        path: '/forum/messages/:username',
        name: 'forumConversation',
        builder: stub,
      ),
      GoRoute(path: '/forum/groups/new', name: 'forumNewGroup', builder: stub),
      GoRoute(
        path: '/forum/groups/:id',
        name: 'forumGroupConversation',
        builder: stub,
      ),
    ],
  );
  return ProviderScope(
    overrides: [forumApiProvider.overrideWithValue(api)],
    child: MaterialApp.router(routerConfig: router),
  );
}

void main() {
  group('ForumConversationsScreen group rows (todo 350)', () {
    testWidgets(
      'a group row shows its title, an avatar cluster, the sender-prefixed '
      'preview and the unread chip; a direct row is unchanged',
      (tester) async {
        final api = FakeForumApi()
          ..conversations = [
            groupConversation(
              id: 12,
              title: 'Seed swap committee',
              memberUsernames: const ['ada', 'bob', 'carol', 'dave'],
              unreadCount: 3,
              lastMessageBody: 'Bring pots',
              lastMessageSender: 'ada',
            ),
            groupConversation(
              id: 13,
              title: 'Cuttings',
              lastMessageBody: 'Sent!',
              lastMessageIsMine: true,
            ),
            conversation(
              id: 1,
              otherUsername: 'bob',
              otherDisplayName: 'Bob Fern',
              lastMessageBody: 'Is it root rot?',
            ),
          ];

        await tester.pumpWidget(_wrap(api));
        await tester.pumpAndSettle();

        expect(find.text('Seed swap committee'), findsOneWidget);
        expect(find.text('ada: Bring pots'), findsOneWidget);
        expect(find.widgetWithText(Badge, '3'), findsOneWidget);
        // Own last message in a group reads "You:", never the sender's name.
        expect(find.text('Cuttings'), findsOneWidget);
        expect(find.text('You: Sent!'), findsOneWidget);
        // The cluster shows at most three of the five members.
        final clusters = find.byType(AuthorAvatarCluster);
        expect(clusters, findsNWidgets(2));
        expect(
          find.descendant(
            of: clusters.first,
            matching: find.byType(AuthorAvatar),
          ),
          findsNWidgets(3),
        );
        // The direct row keeps its single avatar and un-prefixed preview.
        expect(find.text('Bob Fern'), findsOneWidget);
        expect(find.text('Is it root rot?'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets('a group row with no sender on the preview shows the body '
        'un-prefixed rather than crashing', (tester) async {
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(id: 12, title: 'Cuttings').copyWith(
            lastMessage: const ForumLastMessage(body: 'legacy', isMine: false),
          ),
        ];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('legacy'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('a crowded group row fits a 375-wide phone: long title, long '
        'sender-prefixed preview, a 5-member cluster and an unread badge', (
      tester,
    ) async {
      // The narrowest phone the app targets, at 1 dp = 1 px so the widths
      // below are the real ones (the default 800x600 test view hides
      // overflow this row would show on a device).
      tester.view.physicalSize = const Size(375, 667);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      const title = 'Seed swap committee — autumn cuttings and tuber exchange';
      const body =
          'Bring pots, labels and anything you want to trade on Saturday '
          'morning before the rain starts.';
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(
            id: 12,
            title: title,
            memberUsernames: const ['ada', 'bob', 'carol', 'dave'],
            unreadCount: 12,
            lastMessageBody: body,
            lastMessageSender: 'ada-with-a-long-name',
          ),
        ];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      // No RenderFlex overflow, and the row still says what it is.
      expect(tester.takeException(), isNull);
      expect(find.text(title), findsOneWidget);
      expect(find.text('ada-with-a-long-name: $body'), findsOneWidget);
      expect(find.widgetWithText(Badge, '12'), findsOneWidget);
      expect(find.byType(AuthorAvatarCluster), findsOneWidget);
      // Every part of the row stays inside the viewport.
      for (final finder in [find.text(title), find.byType(Badge)]) {
        final rect = tester.getRect(finder);
        expect(rect.left, greaterThanOrEqualTo(0));
        expect(rect.right, lessThanOrEqualTo(375));
      }
    });

    testWidgets('tapping a group row opens the group thread by id; a direct '
        'row still opens by username; "New group" opens the compose '
        'screen from a 48 dp target', (tester) async {
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(id: 12, title: 'Seed swap committee'),
          conversation(id: 1, otherUsername: 'bob'),
        ];
      final opened = <Uri>[];

      await tester.pumpWidget(_routed(api, opened));
      await tester.pumpAndSettle();

      final newGroup = find.byTooltip('New group');
      expect(newGroup, findsOneWidget);
      // The button's padded tap target, not the 40 dp visual the Tooltip
      // wraps (same measurement as PostCard's Quote button test).
      final size = tester.getSize(
        find.widgetWithIcon(IconButton, Icons.group_add_outlined),
      );
      expect(size.width, greaterThanOrEqualTo(48));
      expect(size.height, greaterThanOrEqualTo(48));

      await tester.tap(find.text('Seed swap committee'));
      await tester.pumpAndSettle();
      expect(opened.last.path, '/forum/groups/12');

      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.tap(find.text('bob'));
      await tester.pumpAndSettle();
      expect(opened.last.path, '/forum/messages/bob');

      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.tap(newGroup);
      await tester.pumpAndSettle();
      expect(opened.last.path, '/forum/groups/new');
    });
  });
}
