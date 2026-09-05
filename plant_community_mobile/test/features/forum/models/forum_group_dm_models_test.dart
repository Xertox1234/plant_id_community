import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';

import '../support/forum_test_support.dart';

Map<String, dynamic> _authorJson(String username, {String? displayName}) => {
  'username': username,
  'display_name': displayName ?? username,
  'avatar': null,
  'trust_level': 2,
};

void main() {
  group('ForumConversation group rows (todo 350)', () {
    test('parses every group key from the contract envelope', () {
      final row = ForumConversation.fromJson({
        'id': 12,
        'kind': 'group',
        'title': 'Seed swap committee',
        'other_participant': null,
        'participants': [
          _authorJson('me'),
          _authorJson('ada', displayName: 'Ada Lovelace'),
          _authorJson('bob'),
        ],
        'participant_count': 3,
        'created_by': _authorJson('me'),
        'can_manage': true,
        'created_at': '2026-01-01T00:00:00Z',
        'last_message_at': '2026-01-02T00:00:00Z',
        'unread_count': 3,
        'last_message': {
          'body': 'preview…',
          'is_mine': false,
          'sender': _authorJson('ada', displayName: 'Ada Lovelace'),
          'created_at': '2026-01-02T00:00:00Z',
        },
      });

      expect(row.id, 12);
      expect(row.kind, ForumConversationKind.group);
      expect(row.isGroup, isTrue);
      expect(row.title, 'Seed swap committee');
      expect(row.otherParticipant, isNull);
      expect(row.participants.map((p) => p.username), ['me', 'ada', 'bob']);
      expect(row.participants[1].name, 'Ada Lovelace');
      expect(row.participantCount, 3);
      expect(row.createdBy?.username, 'me');
      expect(row.canManage, isTrue);
      expect(row.unreadCount, 3);
      expect(row.hasUnread, isTrue);
      expect(row.isAtCapacity, isFalse);
      expect(row.lastMessage?.body, 'preview…');
      expect(row.lastMessage?.isMine, isFalse);
      expect(row.lastMessage?.sender?.username, 'ada');
      expect(row.lastMessage?.sender?.name, 'Ada Lovelace');
      expect(row.lastMessageAt, isNotNull);
    });

    test('tolerates every new key being absent (a backend that predates '
        'group DMs) and reads the row as a direct thread', () {
      final row = ForumConversation.fromJson({
        'id': 1,
        'other_participant': _authorJson('bob', displayName: 'Bob Fern'),
        'unread_count': 1,
        'last_message': {'body': 'hi', 'is_mine': true},
      });

      expect(row.kind, ForumConversationKind.direct);
      expect(row.isGroup, isFalse);
      expect(row.title, isNull);
      expect(row.otherParticipant?.username, 'bob');
      expect(row.otherParticipant?.name, 'Bob Fern');
      expect(row.participants, isEmpty);
      expect(row.participantCount, 0);
      expect(row.createdBy, isNull);
      expect(row.canManage, isFalse);
      expect(row.isAtCapacity, isFalse);
      expect(row.lastMessage?.sender, isNull);
      expect(row.lastMessage?.isMine, isTrue);
    });

    test('a direct row carrying the new keys keeps its far side', () {
      final row = ForumConversation.fromJson({
        'id': 2,
        'kind': 'direct',
        'title': null,
        'other_participant': _authorJson('bob'),
        'participants': [_authorJson('me'), _authorJson('bob')],
        'participant_count': 2,
        'created_by': null,
        'can_manage': false,
        'last_message': {
          'body': 'yo',
          'is_mine': false,
          'sender': _authorJson('bob'),
        },
      });

      expect(row.isGroup, isFalse);
      expect(row.otherParticipant?.username, 'bob');
      expect(row.participants.length, 2);
      expect(row.participantCount, 2);
      expect(row.createdBy, isNull);
      expect(row.canManage, isFalse);
      expect(row.lastMessage?.sender?.username, 'bob');
    });

    test('a direct row with no other_participant falls back to the '
        '[deleted] sentinel; a group never fabricates one', () {
      final direct = ForumConversation.fromJson({'id': 3});
      expect(direct.otherParticipant?.isDeleted, isTrue);

      final grp = ForumConversation.fromJson({'id': 4, 'kind': 'group'});
      expect(grp.otherParticipant, isNull);
      expect(grp.isGroup, isTrue);
    });

    test('an unknown kind reads as direct, never throws', () {
      final row = ForumConversation.fromJson({
        'id': 5,
        'kind': 'broadcast',
        'other_participant': _authorJson('bob'),
      });
      expect(row.kind, ForumConversationKind.direct);
    });

    test('participant_count falls back to the roster length and '
        'isAtCapacity trips at the 8-member cap', () {
      final counted = ForumConversation.fromJson({
        'id': 6,
        'kind': 'group',
        'participants': [_authorJson('a'), _authorJson('b')],
      });
      expect(counted.participantCount, 2);

      final full = ForumConversation.fromJson({
        'id': 7,
        'kind': 'group',
        'participants': [
          for (var i = 0; i < forumGroupMaxParticipants; i++)
            _authorJson('u$i'),
        ],
        'participant_count': forumGroupMaxParticipants,
      });
      expect(full.isAtCapacity, isTrue);
      // Only the roster elements that are objects count.
      final mixed = ForumConversation.fromJson({
        'id': 8,
        'kind': 'group',
        'participants': [_authorJson('a'), 'junk', null],
      });
      expect(mixed.participants.map((p) => p.username), ['a']);
    });

    test('copyWith keeps the group identity and recomputes the count when '
        'the roster changes', () {
      final row = groupConversation(
        id: 12,
        title: 'Seed swap committee',
        creatorUsername: 'me',
        memberUsernames: const ['ada', 'bob'],
        canManage: true,
      );
      expect(row.participantCount, 3);

      final read = row.copyWith(unreadCount: 0);
      expect(read.isGroup, isTrue);
      expect(read.title, 'Seed swap committee');
      expect(read.createdBy?.username, 'me');
      expect(read.canManage, isTrue);
      expect(read.participants.length, 3);
      expect(read.participantCount, 3);

      final smaller = row.copyWith(
        participants: [
          for (final p in row.participants)
            if (p.username != 'bob') p,
        ],
      );
      expect(smaller.participants.map((p) => p.username), ['me', 'ada']);
      expect(smaller.participantCount, 2);

      final explicit = row.copyWith(participantCount: 5);
      expect(explicit.participantCount, 5);
      expect(explicit.participants.length, 3);
    });
  });

  group('ForumLastMessage (todo 350)', () {
    test('parses sender and tolerates a non-object sender', () {
      final withSender = ForumLastMessage.fromJson({
        'body': 'x',
        'is_mine': false,
        'sender': _authorJson('ada'),
      });
      expect(withSender.sender?.username, 'ada');

      final junk = ForumLastMessage.fromJson({
        'body': 'x',
        'is_mine': false,
        'sender': 'ada',
      });
      expect(junk.sender, isNull);
    });
  });
}
