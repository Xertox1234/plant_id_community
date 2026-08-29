import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';

void main() {
  group('ForumProfile.fromJson', () {
    test(
      'parses a flat PUBLIC_PROFILE_SCHEMA map — author fields off the same '
      'top-level map, plus profile-only fields and recent activity lists',
      () {
        final profile = ForumProfile.fromJson({
          'username': 'alice',
          'display_name': 'Alice',
          'avatar': null,
          'trust_level': 3,
          'title': 'Plant Whisperer',
          'bio': 'I grow monsteras.',
          'signature': 'Happy growing!',
          'post_count': 42,
          'joined_at': '2025-01-01T00:00:00Z',
          'recent_topics': [
            {
              'id': 1,
              'slug': 'monstera-care',
              'title': 'Monstera care',
              'board_id': 2,
              'board_slug': 'general',
              'reply_count': 5,
              'created_at': '2026-01-01T00:00:00Z',
            },
          ],
          'recent_posts': [
            {
              'id': 9,
              'topic_id': 1,
              'topic_slug': 'monstera-care',
              'topic_title': 'Monstera care',
              'board_id': 2,
              'board_slug': 'general',
              'created_at': '2026-01-02T00:00:00Z',
            },
          ],
        });

        expect(profile.author.username, 'alice');
        expect(profile.author.name, 'Alice');
        expect(profile.author.trustLevel, 3);
        expect(profile.author.title, 'Plant Whisperer');
        expect(profile.bio, 'I grow monsteras.');
        expect(profile.signature, 'Happy growing!');
        expect(profile.postCount, 42);
        expect(
          profile.joinedAt!.isAtSameMomentAs(
            DateTime.parse('2025-01-01T00:00:00Z'),
          ),
          isTrue,
        );

        expect(profile.recentTopics, hasLength(1));
        final topicRef = profile.recentTopics.single;
        expect(topicRef.id, 1);
        expect(topicRef.slug, 'monstera-care');
        expect(topicRef.title, 'Monstera care');
        expect(topicRef.boardId, 2);
        expect(topicRef.boardSlug, 'general');
        expect(topicRef.replyCount, 5);
        expect(
          topicRef.createdAt!.isAtSameMomentAs(
            DateTime.parse('2026-01-01T00:00:00Z'),
          ),
          isTrue,
        );

        expect(profile.recentPosts, hasLength(1));
        final postRef = profile.recentPosts.single;
        expect(postRef.id, 9);
        expect(postRef.topicId, 1);
        expect(postRef.topicSlug, 'monstera-care');
        expect(postRef.topicTitle, 'Monstera care');
        expect(postRef.boardId, 2);
        expect(postRef.boardSlug, 'general');
        expect(
          postRef.createdAt!.isAtSameMomentAs(
            DateTime.parse('2026-01-02T00:00:00Z'),
          ),
          isTrue,
        );
      },
    );

    test('missing profile-only fields default sensibly (profileless user)', () {
      final profile = ForumProfile.fromJson({
        'username': 'bob',
        'display_name': 'Bob',
        'avatar': null,
        'trust_level': null,
        'title': '',
      });

      expect(profile.bio, '');
      expect(profile.signature, '');
      expect(profile.postCount, 0);
      expect(profile.joinedAt, isNull);
      expect(profile.recentTopics, isEmpty);
      expect(profile.recentPosts, isEmpty);
    });

    test('the deleted-author sentinel parses without throwing', () {
      final profile = ForumProfile.fromJson({
        'username': '[deleted]',
        'display_name': '[deleted]',
        'avatar': null,
        'trust_level': null,
        'title': '',
      });

      expect(profile.author.isDeleted, isTrue);
    });
  });
}
