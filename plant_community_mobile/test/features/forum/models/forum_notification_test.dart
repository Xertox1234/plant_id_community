import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';

Map<String, dynamic> _row({Object? quotedPostId = 12, bool omit = false}) {
  return {
    'id': 5,
    'verb': 'quote',
    'actor': {
      'username': 'bob',
      'display_name': 'Bob B',
      'avatar': null,
      'trust_level': 2,
    },
    'topic': {
      'id': 10,
      'slug': 'sample-topic',
      'title': 'Sample topic',
      'board_id': 1,
      'board_slug': 'general',
    },
    'post_id': 30,
    if (!omit) 'quoted_post_id': quotedPostId,
    'created_at': '2026-01-01T00:00:00Z',
    'read_at': null,
  };
}

void main() {
  group('ForumNotification.quotedPostId (todo 342)', () {
    test('parses quoted_post_id alongside post_id — the quoting post to '
        'open, and the recipient\'s own post that was quoted', () {
      final n = ForumNotification.fromJson(_row());

      expect(n.verb, 'quote');
      expect(n.postId, 30);
      expect(n.quotedPostId, 12);
      expect(n.topic?.id, 10);
      expect(n.actor.name, 'Bob B');
      expect(n.isRead, isFalse);
    });

    test('absent or null quoted_post_id (every other verb) is null', () {
      expect(ForumNotification.fromJson(_row(omit: true)).quotedPostId, isNull);
      expect(
        ForumNotification.fromJson(_row(quotedPostId: null)).quotedPostId,
        isNull,
      );
    });

    test('asRead() preserves quotedPostId with the rest of the row', () {
      final read = ForumNotification.fromJson(_row()).asRead(DateTime(2026, 2));

      expect(read.isRead, isTrue);
      expect(read.readAt, DateTime(2026, 2));
      expect(read.id, 5);
      expect(read.verb, 'quote');
      expect(read.postId, 30);
      expect(read.quotedPostId, 12);
      expect(read.topic?.id, 10);
    });
  });
}
