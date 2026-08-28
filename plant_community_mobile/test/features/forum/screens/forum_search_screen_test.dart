import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_search_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import '../support/forum_test_support.dart';

void main() {
  testWidgets('idle state before any search is submitted', (tester) async {
    final api = FakeForumApi();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: ForumSearchScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Search topics and posts.'), findsOneWidget);
  });

  testWidgets('submitting a query renders topic and post hits', (tester) async {
    final api = FakeForumApi()
      ..searchResult = const ForumSearchPage(
        topics: [
          ForumSearchTopicHit(
            id: 1,
            slug: 'monstera-care',
            title: 'Monstera care tips',
            replyCount: 4,
            viewCount: 20,
            isPinned: false,
            isSolved: false,
            boardId: 1,
            boardSlug: 'general',
          ),
        ],
        posts: [
          ForumSearchPostHit(
            id: 2,
            topicId: 1,
            topicTitle: 'Monstera care tips',
            topicSlug: 'monstera-care',
            boardId: 1,
            boardSlug: 'general',
            excerpt: 'Water it once a week...',
          ),
        ],
        topicsHasMore: false,
        postsHasMore: false,
        page: 1,
      );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: ForumSearchScreen()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'monstera');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    // Rendered twice: once as the topic hit's title, once as the post
    // hit's topic-title subtitle — both correctly say "Monstera care tips".
    expect(find.text('Monstera care tips'), findsNWidgets(2));
    expect(find.text('Water it once a week...'), findsOneWidget);
    expect(api.searchCalls.single['q'], 'monstera');
  });

  testWidgets('no results renders an explicit empty state', (tester) async {
    final api = FakeForumApi();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: ForumSearchScreen()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'nothing-matches');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(find.text('No results.'), findsOneWidget);
  });

  testWidgets('a genuine zero-hit search still shows "No results." even when '
      'semantic_status is "ok" (code review: this used to render nothing)', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..searchResult = const ForumSearchPage(
        topics: [],
        posts: [],
        topicsHasMore: false,
        postsHasMore: false,
        page: 1,
        semantic: [],
        semanticStatus: ForumSemanticStatus.ok,
      );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: ForumSearchScreen()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'nothing-matches');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(find.text('No results.'), findsOneWidget);
  });

  testWidgets(
    'semantic_status "unavailable" renders as a state, not an error (todo 295 AC)',
    (tester) async {
      final api = FakeForumApi()
        ..searchResult = const ForumSearchPage(
          topics: [],
          posts: [],
          topicsHasMore: false,
          postsHasMore: false,
          page: 1,
          semanticStatus: ForumSemanticStatus.unavailable,
        );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [forumApiProvider.overrideWithValue(api)],
          child: const MaterialApp(home: ForumSearchScreen()),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'q');
      await tester.testTextInput.receiveAction(TextInputAction.search);
      await tester.pumpAndSettle();

      expect(
        find.text('Related topics are unavailable right now.'),
        findsOneWidget,
      );
      // Not surfaced as an error/retry.
      expect(find.text('Could not search right now.'), findsNothing);
    },
  );

  testWidgets('a search failure surfaces a retry, not a crash', (tester) async {
    final api = FakeForumApi()
      ..failSearchWith = ApiException('temporary failure', statusCode: 500);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: ForumSearchScreen()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'q');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(find.text('Could not search right now.'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, 'Retry'), findsOneWidget);
  });

  testWidgets('load more appends the next page', (tester) async {
    final api = FakeForumApi()
      ..searchPages = {
        1: const ForumSearchPage(
          topics: [
            ForumSearchTopicHit(
              id: 1,
              slug: 't1',
              title: 'Topic 1',
              replyCount: 0,
              viewCount: 0,
              isPinned: false,
              isSolved: false,
              boardId: 1,
              boardSlug: 'general',
            ),
          ],
          posts: [],
          topicsHasMore: true,
          postsHasMore: false,
          page: 1,
        ),
        2: const ForumSearchPage(
          topics: [
            ForumSearchTopicHit(
              id: 2,
              slug: 't2',
              title: 'Topic 2',
              replyCount: 0,
              viewCount: 0,
              isPinned: false,
              isSolved: false,
              boardId: 1,
              boardSlug: 'general',
            ),
          ],
          posts: [],
          topicsHasMore: false,
          postsHasMore: false,
          page: 2,
        ),
      };

    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: ForumSearchScreen()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'topic');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(OutlinedButton, 'Load more'));
    await tester.pumpAndSettle();

    expect(find.text('Topic 1'), findsOneWidget);
    expect(find.text('Topic 2'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, 'Load more'), findsNothing);
  });
}
