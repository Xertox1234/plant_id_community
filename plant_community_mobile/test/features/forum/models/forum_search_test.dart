import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';

void main() {
  group('ForumSearchPage.fromJson', () {
    test(
      'parses topics, posts, and pagination flags from the real API shape',
      () {
        final page = ForumSearchPage.fromJson({
          'topics': [
            {
              'id': 1,
              'slug': 'monstera-care',
              'title': 'Monstera care',
              'reply_count': 3,
              'view_count': 12,
              'is_pinned': false,
              'is_solved': true,
              'last_post_at': '2026-01-02T00:00:00Z',
              'board_id': 1,
              'board_slug': 'general',
            },
          ],
          'posts': [
            {
              'id': 2,
              'topic_id': 1,
              'topic_title': 'Monstera care',
              'topic_slug': 'monstera-care',
              'board_id': 1,
              'board_slug': 'general',
              'excerpt': 'Water it once a week...',
            },
          ],
          'topics_has_more': true,
          'posts_has_more': false,
          'page': 1,
        });

        expect(page.topics.single.title, 'Monstera care');
        expect(page.topics.single.isSolved, isTrue);
        expect(page.posts.single.excerpt, 'Water it once a week...');
        expect(page.topicsHasMore, isTrue);
        expect(page.postsHasMore, isFalse);
        // No `?semantic=1` in this response — absent, not an empty list.
        expect(page.semantic, isNull);
        expect(page.semanticStatus, isNull);
      },
    );

    test('a missing "semantic" key does not throw — null-shorts to null, not '
        'an empty list', () {
      expect(
        () => ForumSearchPage.fromJson({
          'topics': [],
          'posts': [],
          'topics_has_more': false,
          'posts_has_more': false,
          'page': 1,
        }),
        returnsNormally,
      );
    });

    test('parses each semantic_status wire value', () {
      for (final entry in {
        'ok': ForumSemanticStatus.ok,
        'premium_required': ForumSemanticStatus.premiumRequired,
        'unavailable': ForumSemanticStatus.unavailable,
      }.entries) {
        final page = ForumSearchPage.fromJson({
          'topics': [],
          'posts': [],
          'topics_has_more': false,
          'posts_has_more': false,
          'page': 1,
          'semantic': [],
          'semantic_status': entry.key,
        });
        expect(page.semanticStatus, entry.value);
        expect(page.semantic, isEmpty);
      }
    });

    test(
      'an unrecognized semantic_status value parses to null, not a crash',
      () {
        final page = ForumSearchPage.fromJson({
          'topics': [],
          'posts': [],
          'topics_has_more': false,
          'posts_has_more': false,
          'page': 1,
          'semantic_status': 'some_future_status',
        });
        expect(page.semanticStatus, isNull);
      },
    );
  });
}
