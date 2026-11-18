import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_topics_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/topic_card.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_accents.dart';

import '../support/forum_test_support.dart';

const _board = ForumBoard(
  id: 1,
  title: 'Plant identification',
  slug: 'plant-identification',
  description: 'Post a photo, get a name.',
  topicCount: 7,
  postCount: 46,
);

Widget _wrap(FakeForumApi api, {bool loggedIn = true}) => ProviderScope(
  overrides: [
    forumApiProvider.overrideWithValue(api),
    authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: loggedIn)),
  ],
  child: const MaterialApp(
    home: ForumTopicsScreen(
      boardSlug: 'plant-identification',
      boardTitle: 'Plant identification',
    ),
  ),
);

void main() {
  group('ForumTopicsScreen viewer change', () {
    testWidgets('a forum locked for the new viewer drops the previous '
        'viewer\'s topics', (tester) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(items: [topic(id: 1, title: 'Monstera albo')]);
      final container = ProviderContainer(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false, initial: signedInAs('ada')),
          ),
        ],
        retry: (_, _) => null,
      );
      addTearDown(container.dispose);
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: ForumTopicsScreen(
              boardSlug: 'plant-identification',
              boardTitle: 'Plant identification',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Monstera albo'), findsOneWidget);

      api.topicsError = ApiException(
        'locked',
        statusCode: 403,
        code: 'forum_locked',
      );
      (container.read(authServiceProvider.notifier) as FakeAuthService).setAuth(
        signedInAs('bob'),
      );
      await tester.pumpAndSettle();

      expect(find.text('Monstera albo'), findsNothing);
      expect(find.text('Could not load topics.'), findsOneWidget);
    });
  });

  group('ForumTopicsScreen', () {
    testWidgets('shows the board intro above one row per topic', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(
          items: [
            topic(id: 1, title: 'Monstera albo'),
            topic(id: 2, title: 'What tree is this?'),
          ],
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('Plant identification'), findsOneWidget);
      expect(find.text('Post a photo, get a name.'), findsOneWidget);
      expect(find.text('7 topics · 46 posts'), findsOneWidget);
      expect(find.byType(TopicRow), findsNWidgets(2));
      expect(find.text('New topic'), findsOneWidget);
    });

    testWidgets('the header uses the server icon and colour', (tester) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [
            ForumBoard(
              id: 1,
              title: 'Plant identification',
              slug: 'plant-identification', // hardcoded: leaf + sage
              description: '',
              topicCount: 7,
              postCount: 46,
              icon: '🪴',
              colour: 'orchid',
            ),
          ]),
        ]
        ..topics = CursorPage(items: [topic(id: 1, title: 'Monstera albo')]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('🪴'), findsOneWidget);
      final tile = tester.widget<CanopyAccentTile>(
        find.byType(CanopyAccentTile).first,
      );
      final canopy = tester.element(find.byType(CanopyAccentTile).first).canopy;
      expect(tile.tone, canopy.sky);
    });

    testWidgets('the topics still show when the boards list fails', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categoriesError = Exception('offline')
        ..topics = CursorPage(items: [topic(id: 1, title: 'Monstera albo')]);

      await tester.pumpWidget(_wrap(api));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Plant identification'), findsOneWidget);
      expect(find.byType(TopicRow), findsOneWidget);
      expect(find.textContaining('topics ·'), findsNothing);

      // Let Riverpod's retry of the failed boards fetch run out.
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(minutes: 2));
    });

    testWidgets('pull to refresh refetches the header counts too', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(items: [topic(id: 1, title: 'Monstera albo')]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      final before = api.fetchCategoriesCalls;

      await tester.fling(find.byType(ListView), const Offset(0, 400), 1000);
      await tester.pumpAndSettle();

      expect(api.fetchCategoriesCalls, before + 1);
    });

    testWidgets('an empty board says so, and offers no button signed out', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ];

      await tester.pumpWidget(_wrap(api, loggedIn: false));
      await tester.pumpAndSettle();

      expect(find.text('No topics yet'), findsOneWidget);
      expect(find.byType(TopicRow), findsNothing);
      expect(find.text('New topic'), findsNothing);
    });

    testWidgets('a board with more topics offers Load more under the list', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..topics = CursorPage(
          items: [topic(id: 1, title: 'first')],
          next: 'https://api/forum/topics/?cursor=p2',
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(OutlinedButton, 'Load more'), findsOneWidget);
    });
  });

  group('TopicRow author', () {
    testWidgets('the name and the avatar open the author, not the topic', (
      tester,
    ) async {
      var authorTaps = 0;
      var rowTaps = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TopicRow(
              topic: topic(authorOverride: author(username: 'alice')),
              onTap: () => rowTaps++,
              onAuthorTap: () => authorTaps++,
            ),
          ),
        ),
      );

      await tester.tap(find.text('alice'));
      await tester.tap(find.byType(CircleAvatar));
      await tester.pump();
      expect(authorTaps, 2);
      expect(rowTaps, 0);

      await tester.tap(find.text('Sample topic'));
      await tester.pump();
      expect(rowTaps, 1);
    });
  });
}
