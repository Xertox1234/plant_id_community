import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';

Map<String, dynamic> _author(String u) => {
  'username': u,
  'display_name': u.toUpperCase(),
  'avatar': null,
  'trust_level': 2,
};

Map<String, dynamic> _reply(int id) => {
  'id': id,
  'author': _author('ann'),
  'created_at': '2026-11-01T10:00:00Z',
  'excerpt': 'Try more light',
};

void main() {
  group('ForumRecentTopic.fromJson', () {
    test('parses a full payload', () {
      final t = ForumRecentTopic.fromJson({
        'id': 7,
        'slug': 'fiddle-leaf',
        'title': 'Fiddle leaf help',
        'board': {'id': 3, 'name': 'Care', 'slug': 'care'},
        'reply_count': 4,
        'last_post_at': '2026-11-01T10:00:00Z',
        'is_pinned': true,
        'thumbnail_url': 'https://x/t.jpg',
        'is_solved': true,
        'is_unread': true,
        'image_url': 'https://x/i.jpg',
      });
      expect(t.id, 7);
      expect(t.slug, 'fiddle-leaf');
      expect(t.title, 'Fiddle leaf help');
      expect(t.board.id, 3);
      expect(t.board.title, 'Care');
      expect(t.board.slug, 'care');
      expect(t.replyCount, 4);
      expect(t.lastPostAt, isNotNull);
      expect(t.isPinned, isTrue);
      expect(t.isSolved, isTrue);
      expect(t.isUnread, isTrue);
      expect(t.thumbnailUrl, 'https://x/t.jpg');
      expect(t.imageUrl, 'https://x/i.jpg');
      expect(t.hasPicture, isTrue);
    });

    test('an older server defaults the new keys', () {
      final t = ForumRecentTopic.fromJson({
        'id': 1,
        'slug': 's',
        'title': 'T',
        'board': {'id': 1, 'name': 'B', 'slug': 'b'},
        'reply_count': 0,
        'last_post_at': null,
        'is_pinned': false,
        'thumbnail_url': null,
      });
      expect(t.imageUrl, isNull);
      expect(t.isUnread, isFalse);
      expect(t.isSolved, isFalse);
      expect(t.hasPicture, isFalse);
      expect(t.lastPostAt, isNull);
    });
  });

  group('ForumLatestReplies.fromJson', () {
    test('parses a full payload', () {
      final r = ForumLatestReplies.fromJson({
        'replies': [_reply(1), _reply(2)],
        'solution': _reply(9),
        'more_count': 3,
        'participant_count': 5,
        'participants': [_author('ann'), _author('bob')],
        'started_by': _author('cy'),
      });
      expect(r.replies.map((e) => e.id), [1, 2]);
      expect(r.replies.first.author.username, 'ann');
      expect(r.replies.first.excerpt, 'Try more light');
      expect(r.replies.first.createdAt, isNotNull);
      expect(r.solution!.id, 9);
      expect(r.moreCount, 3);
      expect(r.participantCount, 5);
      expect(r.participants.map((a) => a.username), ['ann', 'bob']);
      expect(r.startedBy!.username, 'cy');
      expect(r.isEmpty, isFalse);
    });

    test('solution null and empty lists', () {
      final r = ForumLatestReplies.fromJson({
        'replies': [],
        'solution': null,
        'more_count': 0,
        'participant_count': 0,
        'participants': [],
        'started_by': null,
      });
      expect(r.solution, isNull);
      expect(r.startedBy, isNull);
      expect(r.isEmpty, isTrue);
    });

    test('isEmpty is true only when replies and solution are both empty', () {
      final onlySolution = ForumLatestReplies.fromJson({
        'replies': [],
        'solution': _reply(9),
      });
      expect(onlySolution.isEmpty, isFalse);
      final onlyReplies = ForumLatestReplies.fromJson({
        'replies': [_reply(1)],
      });
      expect(onlyReplies.isEmpty, isFalse);
    });
  });

  group('ForumCommunityStats.fromJson', () {
    test('parses a full payload', () {
      final s = ForumCommunityStats.fromJson({
        'members_online': 3,
        'online_sample': [_author('ann')],
        'registered_members': 120,
        'topic_count': 40,
        'post_count': 900,
        'newest_member': _author('zed'),
      });
      expect(s.membersOnline, 3);
      expect(s.onlineSample.single.username, 'ann');
      expect(s.registeredMembers, 120);
      expect(s.topicCount, 40);
      expect(s.postCount, 900);
      expect(s.newestMember!.username, 'zed');
    });

    test('tolerates missing keys', () {
      final s = ForumCommunityStats.fromJson({});
      expect(s.membersOnline, 0);
      expect(s.onlineSample, isEmpty);
      expect(s.newestMember, isNull);
    });
  });
}
