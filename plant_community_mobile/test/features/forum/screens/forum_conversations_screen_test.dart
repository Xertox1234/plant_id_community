import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_conversations_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_avatar_cluster.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

import '../support/forum_test_support.dart';

/// The inbox with a faked account profile (todo 486): without the override
/// every test sends a real `GET /auth/user/`. [viewer] is who "I" am — the
/// fixture's group creator by default; null pins the unknown-viewer fallback.
Widget _wrap(
  FakeForumApi api, {
  String? viewer = 'me',
  Future<void>? gate,
  Future<void>? refreshGate,
}) => ProviderScope(
  overrides: [
    forumApiProvider.overrideWithValue(api),
    userProfileServiceProvider.overrideWith(
      () => FakeUserProfileService(
        username: viewer,
        gate: gate,
        refreshGate: refreshGate,
      ),
    ),
  ],
  child: const MaterialApp(home: ForumConversationsScreen()),
);

/// The usernames of the avatars the (single) group row's cluster draws.
List<String> _clusterUsernames(WidgetTester tester) => tester
    .widgetList<AuthorAvatar>(
      find.descendant(
        of: find.byType(AuthorAvatarCluster),
        matching: find.byType(AuthorAvatar),
      ),
    )
    .map((a) => a.author.username)
    .toList();

/// The cluster's semantics label. Inside a ListTile the cluster's node is
/// merged into the row's, so the row's label OPENS with it.
String _clusterLabel(WidgetTester tester) =>
    tester.getSemantics(find.byType(AuthorAvatarCluster)).label;

void main() {
  group('ForumConversationsScreen (todo 339)', () {
    testWidgets(
      'lists conversations with the other member, preview, and unread chip',
      (tester) async {
        final api = FakeForumApi()
          ..conversations = [
            conversation(
              id: 1,
              otherUsername: 'bob',
              otherDisplayName: 'Bob Fern',
              unreadCount: 2,
              lastMessageBody: 'Is it root rot?',
            ),
            conversation(
              id: 2,
              otherUsername: 'carol',
              lastMessageBody: 'Thanks for the cutting!',
              lastMessageIsMine: true,
            ),
          ];

        await tester.pumpWidget(_wrap(api));
        await tester.pumpAndSettle();

        expect(find.text('Bob Fern'), findsOneWidget);
        expect(find.text('Is it root rot?'), findsOneWidget);
        // Unread count chip on the unread row only.
        expect(find.widgetWithText(Badge, '2'), findsOneWidget);
        expect(find.byType(Badge), findsOneWidget);
        // Own last message is prefixed so the reader knows who spoke last.
        expect(find.text('You: Thanks for the cutting!'), findsOneWidget);
        expect(find.text('carol'), findsOneWidget);
      },
    );

    testWidgets('unread rows read bold; read rows do not', (tester) async {
      final api = FakeForumApi()
        ..conversations = [
          conversation(
            id: 1,
            otherUsername: 'bob',
            unreadCount: 1,
            lastMessageBody: 'unread preview',
          ),
          conversation(
            id: 2,
            otherUsername: 'carol',
            lastMessageBody: 'read preview',
          ),
        ];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      final unread = tester.widget<Text>(find.text('bob'));
      final read = tester.widget<Text>(find.text('carol'));
      expect(unread.style?.fontWeight, FontWeight.w700);
      expect(read.style?.fontWeight, isNot(FontWeight.w700));
    });

    testWidgets('empty state renders when there are no conversations', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(FakeForumApi()));
      await tester.pumpAndSettle();

      expect(find.text('No messages yet.'), findsOneWidget);
    });

    testWidgets('load more fetches the next page via the verbatim cursor URL', (
      tester,
    ) async {
      final page1 = CursorPage(
        items: [conversation(id: 1, otherUsername: 'bob')],
        next: 'https://api/forum/conversations/?cursor=p2',
      );
      final page2 = CursorPage(
        items: [conversation(id: 2, otherUsername: 'carol')],
      );
      final api = FakeForumApi()..conversationPages = [page1, page2];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(OutlinedButton, 'Load more'));
      await tester.pumpAndSettle();

      expect(api.fetchConversationsCalls, [null, page1.next]);
      expect(find.byType(ListTile), findsNWidgets(2));
      expect(find.widgetWithText(OutlinedButton, 'Load more'), findsNothing);
    });

    testWidgets('a group row\'s avatar cluster leaves ME out and shows "+N" '
        'past three others (todo 463, web ParticipantStack parity)', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      // The fixture puts the creator ("me") first, so a cluster that does
      // not filter the viewer draws my own avatar in the first slot.
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(
            id: 12,
            title: 'Seed swap committee',
            memberUsernames: const ['ada', 'bob', 'carol', 'dave'],
          ),
        ];

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            userProfileServiceProvider.overrideWith(
              () => FakeUserProfileService(username: 'me'),
            ),
          ],
          child: const MaterialApp(home: ForumConversationsScreen()),
        ),
      );
      await tester.pumpAndSettle();

      final cluster = find.byType(AuthorAvatarCluster);
      final shown = tester
          .widgetList<AuthorAvatar>(
            find.descendant(of: cluster, matching: find.byType(AuthorAvatar)),
          )
          .map((a) => a.author.username)
          .toList();
      expect(shown, ['ada', 'bob', 'carol']);
      expect(
        find.descendant(of: cluster, matching: find.text('+1')),
        findsOneWidget,
      );
      // Inside a ListTile the cluster's node is merged into the row's, so
      // the row's label OPENS with the count rather than equalling it.
      expect(tester.getSemantics(cluster).label, startsWith('4 other members'));
      expect(tester.takeException(), isNull);

      handle.dispose();
    });

    testWidgets('a profile refresh keeps the last known viewer: the cluster '
        'never puts ME back while the profile reloads (todo 486)', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      final refreshGate = Completer<void>();
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(
            id: 12,
            memberUsernames: const ['ada', 'bob', 'carol', 'dave'],
          ),
        ];

      await tester.pumpWidget(_wrap(api, refreshGate: refreshGate.future));
      await tester.pumpAndSettle();
      expect(_clusterUsernames(tester), ['ada', 'bob', 'carol']);

      // `refresh()` (the profile screen's pull-to-refresh) sets an explicit
      // loading state. Unlike an invalidate, that state is NOT AsyncData, so
      // `asData` is null mid-reload and only `.value` still names me.
      final container = ProviderScope.containerOf(
        tester.element(find.byType(ForumConversationsScreen)),
        listen: false,
      );
      unawaited(container.read(userProfileServiceProvider.notifier).refresh());
      await tester.pump();

      final reloading = container.read(userProfileServiceProvider);
      expect(reloading.isLoading, isTrue);
      expect(reloading.asData, isNull);
      expect(_clusterUsernames(tester), ['ada', 'bob', 'carol']);
      expect(
        find.descendant(
          of: find.byType(AuthorAvatarCluster),
          matching: find.text('+1'),
        ),
        findsOneWidget,
      );
      expect(_clusterLabel(tester), startsWith('4 other members'));

      refreshGate.complete();
      await tester.pumpAndSettle();
      expect(_clusterUsernames(tester), ['ada', 'bob', 'carol']);
      expect(tester.takeException(), isNull);

      handle.dispose();
    });

    testWidgets('a group where I am the only member left labels its bare '
        'group glyph for a screen reader (todo 486)', (tester) async {
      final handle = tester.ensureSemantics();
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(id: 12, memberUsernames: const []),
        ];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      final cluster = find.byType(AuthorAvatarCluster);
      expect(_clusterUsernames(tester), isEmpty);
      expect(
        find.descendant(of: cluster, matching: find.byType(Icon)),
        findsOneWidget,
      );
      expect(_clusterLabel(tester), startsWith('No other members'));
      expect(tester.takeException(), isNull);

      handle.dispose();
    });

    testWidgets('the account profile never holds the list back: rows render '
        'while it loads, then the viewer drops out of the cluster '
        '(todo 486)', (tester) async {
      final handle = tester.ensureSemantics();
      final gate = Completer<void>();
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(
            id: 12,
            title: 'Seed swap committee',
            memberUsernames: const ['ada', 'bob', 'carol', 'dave'],
          ),
        ];

      await tester.pumpWidget(_wrap(api, gate: gate.future));
      // Not pumpAndSettle: the profile is still gated, and the point is what
      // shows before it resolves.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      final container = ProviderScope.containerOf(
        tester.element(find.byType(ForumConversationsScreen)),
        listen: false,
      );
      expect(container.read(userProfileServiceProvider).isLoading, isTrue);
      // The list is up, and with the viewer unknown every member is drawn —
      // me (the creator) first, the other two past three folded into "+2".
      expect(find.text('Seed swap committee'), findsOneWidget);
      expect(_clusterUsernames(tester), ['me', 'ada', 'bob']);
      expect(
        find.descendant(
          of: find.byType(AuthorAvatarCluster),
          matching: find.text('+2'),
        ),
        findsOneWidget,
      );
      expect(_clusterLabel(tester), startsWith('5 members'));

      gate.complete();
      await tester.pumpAndSettle();

      expect(_clusterUsernames(tester), ['ada', 'bob', 'carol']);
      expect(_clusterLabel(tester), startsWith('4 other members'));
      expect(tester.takeException(), isNull);

      handle.dispose();
    });

    testWidgets('a conversation with no messages yet shows a placeholder '
        'preview and never crashes on the null last_message', (tester) async {
      final api = FakeForumApi()
        ..conversations = [conversation(id: 1, otherUsername: 'bob')];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('No messages yet.'), findsOneWidget);
    });
  });
}
