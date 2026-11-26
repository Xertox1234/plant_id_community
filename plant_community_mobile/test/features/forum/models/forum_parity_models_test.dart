import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';

import '../support/forum_test_support.dart';

void main() {
  group('ForumPost safety flags (todo 341)', () {
    test('parses is_blocked / can_block and defaults them to false', () {
      final blocked = ForumPost.fromJson({
        'id': 1,
        'is_blocked': true,
        'can_block': true,
        'can_report': true,
      });
      expect(blocked.isBlocked, isTrue);
      expect(blocked.canBlock, isTrue);
      expect(blocked.canReport, isTrue);

      final bare = ForumPost.fromJson({'id': 2});
      expect(bare.isBlocked, isFalse);
      expect(bare.canBlock, isFalse);
    });

    test('parses is_muted / can_mute and defaults them to false (F47)', () {
      final muted = ForumPost.fromJson(const {
        'id': 1,
        'is_muted': true,
        'can_mute': true,
      });
      expect(muted.isMuted, isTrue);
      expect(muted.canMute, isTrue);
      expect(muted.withBlocked(true).isMuted, isTrue);
      expect(muted.withMuted(false).isMuted, isFalse);
      expect(muted.withMuted(false).canMute, isTrue);

      final bare = ForumPost.fromJson(const {'id': 1});
      expect(bare.isMuted, isFalse);
      expect(bare.canMute, isFalse);
    });

    test('withBlocked flips only the block flag', () {
      final original = post(id: 1, reactionCounts: const {'like': 2});
      final blocked = original.withBlocked(true);
      expect(blocked.isBlocked, isTrue);
      expect(blocked.reactionCounts, {'like': 2});
      expect(blocked.id, 1);
    });
  });

  group('ForumTopicDetail thread flags (todo 341)', () {
    test('parses bookmark, solution and block fields', () {
      final detail = ForumTopicDetail.fromJson({
        'id': 10,
        'is_bookmarked': true,
        'is_solved': true,
        'solved_post_id': 5,
        'can_mark_solution': true,
        'is_blocked': false,
        'can_block': true,
      });
      expect(detail.isBookmarked, isTrue);
      expect(detail.isSolved, isTrue);
      expect(detail.solvedPostId, 5);
      expect(detail.canMarkSolution, isTrue);
      expect(detail.canBlock, isTrue);

      final unsolved = ForumTopicDetail.fromJson({'id': 11});
      expect(unsolved.isSolved, isFalse);
      expect(unsolved.solvedPostId, isNull);
      expect(unsolved.isBookmarked, isFalse);
    });

    test('copyWith can clear the accepted answer', () {
      final solved = topicDetail(solvedPostId: 5);
      expect(solved.copyWith(clearSolvedPostId: true).solvedPostId, isNull);
      expect(solved.copyWith(solvedPostId: 6).solvedPostId, 6);
      // An unrelated copy keeps it.
      expect(solved.copyWith(isBookmarked: true).solvedPostId, 5);
    });

    test('fromDetail builds a list row for the bookmarks feed splice', () {
      final row = ForumTopicListItem.fromDetail(
        topicDetail(id: 42, title: 'Saved', solvedPostId: 3),
      );
      expect(row.id, 42);
      expect(row.title, 'Saved');
      expect(row.isSolved, isTrue);
      expect(row.isUnread, isFalse);
    });

    test('a topic detail parses tags, and a row built from it keeps them '
        '(F140)', () {
      final detail = ForumTopicDetail.fromJson({
        'id': 7,
        'tags': ['Monstera', 'root rot', ''],
      });
      expect(detail.tags, ['Monstera', 'root rot']);
      expect(detail.copyWith(isBookmarked: true).tags, [
        'Monstera',
        'root rot',
      ]);
      expect(ForumTopicListItem.fromDetail(detail).tags, [
        'Monstera',
        'root rot',
      ]);
      expect(ForumTopicDetail.fromJson({'id': 8}).tags, isEmpty);
    });

    test('a list row parses is_solved', () {
      expect(
        ForumTopicListItem.fromJson({'id': 1, 'is_solved': true}).isSolved,
        isTrue,
      );
    });

    test('a list row parses tags, and has none when the payload has none', () {
      expect(
        ForumTopicListItem.fromJson({
          'id': 1,
          'tags': ['Monstera', 'root rot', ''],
        }).tags,
        ['Monstera', 'root rot'],
      );
      expect(ForumTopicListItem.fromJson({'id': 1}).tags, isEmpty);
    });

    test('a board parses default_sort', () {
      expect(
        ForumBoard.fromJson({
          'id': 1,
          'default_sort': '-created_at',
        }).defaultSort,
        '-created_at',
      );
      expect(ForumBoard.fromJson({'id': 1}).defaultSort, '');
    });
  });

  group('ForumProfile block flags (todo 341)', () {
    test('parses is_muted / can_mute, kept by withBlocked (F47)', () {
      final p = profile(username: 'alice', isMuted: true, canMute: true);
      expect(p.isMuted, isTrue);
      expect(p.canMute, isTrue);
      expect(p.withBlocked(true).isMuted, isTrue);
      expect(p.withBlocked(true).canMute, isTrue);
    });

    test('parses is_blocked / can_block', () {
      final p = profile(username: 'alice', isBlocked: true, canBlock: true);
      expect(p.isBlocked, isTrue);
      expect(p.canBlock, isTrue);
    });

    test(
      'withBlocked(true) clears the activity lists like the server does',
      () {
        final p = profile(
          username: 'alice',
          canBlock: true,
          recentTopics: [profileTopicRefJson(id: 1)],
          recentPosts: [profilePostRefJson(id: 2)],
        );
        final blocked = p.withBlocked(true);
        expect(blocked.isBlocked, isTrue);
        expect(blocked.recentTopics, isEmpty);
        expect(blocked.recentPosts, isEmpty);
        expect(blocked.canBlock, isTrue);
      },
    );
  });

  group('ForumPostRevision (todo 341)', () {
    test('parses a history row and a detail with a rendered body', () {
      final row = ForumPostRevision.fromJson({
        'id': 7,
        'created_at': '2026-01-03T10:00:00Z',
        'user': {'username': 'alice', 'display_name': 'Alice'},
      });
      expect(row.id, 7);
      expect(row.user.name, 'Alice');
      expect(row.createdAt, isNotNull);

      final detail = ForumPostRevisionDetail.fromJson({
        'id': 7,
        'created_at': '2026-01-03T10:00:00Z',
        'user': {'username': 'alice'},
        'body': [
          {'type': 'paragraph', 'value': '<p>Older wording</p>'},
        ],
      });
      expect(detail.id, 7);
      expect(detail.body, isNotEmpty);
    });

    test('a null user parses as the deleted sentinel, never crashes', () {
      final row = ForumPostRevision.fromJson({'id': 1, 'user': null});
      expect(row.user.isDeleted, isTrue);
    });
  });

  group('ForumSolutionResult (todo 341)', () {
    test('parses mark and clear payloads identically', () {
      final marked = ForumSolutionResult.fromJson({
        'is_solved': true,
        'solved_post_id': 5,
      });
      expect(marked.isSolved, isTrue);
      expect(marked.solvedPostId, 5);

      final cleared = ForumSolutionResult.fromJson({
        'is_solved': false,
        'solved_post_id': null,
      });
      expect(cleared.isSolved, isFalse);
      expect(cleared.solvedPostId, isNull);
    });
  });
}
