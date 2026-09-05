import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_bookmarks_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/topic_card.dart';

import '../support/forum_test_support.dart';

Widget _wrap(FakeForumApi api) => ProviderScope(
  overrides: [forumApiProvider.overrideWithValue(api)],
  child: const MaterialApp(home: ForumBookmarksScreen()),
);

void main() {
  group('ForumBookmarksScreen (todo 341)', () {
    testWidgets('lists bookmarked topics as topic cards', (tester) async {
      final api = FakeForumApi()
        ..bookmarks = [
          topic(id: 1, title: 'Monstera care'),
          topic(id: 2, title: 'Fiddle leaf fig'),
        ];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('Bookmarks'), findsOneWidget);
      expect(find.byType(TopicCard), findsNWidgets(2));
      expect(find.text('Monstera care'), findsOneWidget);
      expect(find.text('Fiddle leaf fig'), findsOneWidget);
      expect(api.fetchBookmarksCalls, [null]);
    });

    testWidgets('empty state renders when nothing is bookmarked', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(FakeForumApi()));
      await tester.pumpAndSettle();

      expect(find.text('No bookmarks yet.'), findsOneWidget);
      expect(find.byType(TopicCard), findsNothing);
    });

    testWidgets('load more fetches the next page via the verbatim cursor URL', (
      tester,
    ) async {
      final page1 = CursorPage(
        items: [topic(id: 1, title: 'first')],
        next: 'https://api/forum/me/bookmarks/?cursor=p2',
      );
      final page2 = CursorPage(items: [topic(id: 2, title: 'second')]);
      final api = FakeForumApi()..bookmarkPages = [page1, page2];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(OutlinedButton, 'Load more'));
      await tester.pumpAndSettle();

      expect(api.fetchBookmarksCalls, [null, page1.next]);
      expect(find.byType(TopicCard), findsNWidgets(2));
      expect(find.widgetWithText(OutlinedButton, 'Load more'), findsNothing);
    });

    testWidgets('a solved bookmarked topic shows the solved marker', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..bookmarks = [
          ForumTopicListItem.fromDetail(
            topicDetail(id: 5, title: 'Answered', solvedPostId: 9),
          ),
        ];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.check_circle), findsOneWidget);
    });
  });
}
