import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/forum_format.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_mention_suggestions.dart';

import '../support/forum_test_support.dart';

void main() {
  group('ForumPoll.fromJson (todo 341 wave 3)', () {
    test('parses the Poll.serialize shape', () {
      final poll = ForumPoll.fromJson({
        'id': 7,
        'question': 'How often do you water?',
        'closes_at': '2026-02-01T00:00:00Z',
        'is_closed': false,
        'max_choices': 2,
        'options': [
          {'id': 1, 'text': 'Weekly', 'order': 0, 'vote_count': 3},
          {'id': 2, 'text': 'When dry', 'order': 1, 'vote_count': 1},
        ],
        'total_votes': 4,
        'my_vote_option_ids': [2],
      });

      expect(poll.id, 7);
      expect(poll.question, 'How often do you water?');
      expect(poll.closesAt, isNotNull);
      expect(poll.isClosed, isFalse);
      expect(poll.maxChoices, 2);
      expect(poll.isMultiChoice, isTrue);
      expect(poll.options.map((o) => o.text), ['Weekly', 'When dry']);
      expect(poll.options.first.voteCount, 3);
      expect(poll.totalVotes, 4);
      expect(poll.myVoteOptionIds, [2]);
      expect(poll.hasVoted, isTrue);
      expect(poll.pendingOptionIds, isEmpty);
      expect(poll.isVoting, isFalse);
      expect(poll.percentFor(poll.options.first), 75);
    });

    test('a missing max_choices reads as single-choice, never unlimited', () {
      final poll = ForumPoll.fromJson({'id': 1, 'question': 'q'});
      expect(poll.maxChoices, 1);
      expect(poll.isMultiChoice, isFalse);
      expect(poll.hasVoted, isFalse);
      expect(poll.percentFor(pollOption(id: 1)), 0);
    });

    test('copyWith only touches the client-side pending marker', () {
      final base = poll(totalVotes: 3);
      final pending = base.copyWith(pendingOptionIds: [2]);
      expect(pending.isVoting, isTrue);
      expect(pending.totalVotes, 3);
      expect(pending.myVoteOptionIds, isEmpty);
      expect(pending.copyWith(pendingOptionIds: const []).isVoting, isFalse);
    });
  });

  group('ForumIdentification.fromJson', () {
    test('parses candidates, provider and the rendition image', () {
      final id = ForumIdentification.fromJson({
        'image': {
          'id': 4,
          'url': 'https://img/4.jpg',
          'alt': 'My plant',
          'width': 800,
          'height': 600,
        },
        'provider': 'plant.id',
        'candidates': [
          {
            'name': 'Swiss cheese plant',
            'scientific_name': 'Monstera deliciosa',
            'confidence': 0.917,
          },
          {'name': 'Unknown', 'confidence': 1.4},
        ],
        'created_at': '2026-01-01T00:00:00Z',
      });

      expect(id.image?.url, 'https://img/4.jpg');
      expect(id.image?.alt, 'My plant');
      expect(id.provider, 'plant.id');
      expect(id.candidates.first.scientificName, 'Monstera deliciosa');
      expect(id.candidates.first.confidencePercent, 92);
      // Clamped: a provider can't claim more than 100%.
      expect(id.candidates.last.confidence, 1.0);
      expect(id.candidates.last.scientificName, '');
      expect(id.createdAt, isNotNull);
    });

    test('a deleted photo is null, not an error', () {
      final id = ForumIdentification.fromJson({
        'image': null,
        'provider': '',
        'candidates': [],
      });
      expect(id.image, isNull);
      expect(id.candidates, isEmpty);
    });
  });

  group('ForumTopicDetail carries the header cards', () {
    test('parses poll and identification when present', () {
      final detail = ForumTopicDetail.fromJson({
        'id': 10,
        'title': 't',
        'board': {'id': 1, 'slug': 'g', 'title': 'G'},
        'author': {'username': 'alice'},
        'poll': {
          'id': 1,
          'question': 'q',
          'options': [],
          'total_votes': 0,
          'my_vote_option_ids': [],
        },
        'identification': {
          'image': null,
          'provider': 'plantnet',
          'candidates': [
            {'name': 'Fern', 'confidence': 0.5},
          ],
        },
      });
      expect(detail.poll?.question, 'q');
      expect(detail.identification?.provider, 'plantnet');
      expect(detail.identification?.candidates.single.name, 'Fern');

      // copyWith keeps both unless a poll replacement is given.
      final bookmarked = detail.copyWith(isBookmarked: true);
      expect(bookmarked.poll?.id, 1);
      expect(bookmarked.identification?.provider, 'plantnet');
      final voted = detail.copyWith(poll: poll(id: 99));
      expect(voted.poll?.id, 99);
    });

    test('both are null for the common poll-less, snapshot-less topic', () {
      final detail = ForumTopicDetail.fromJson({
        'id': 10,
        'poll': null,
        'identification': null,
      });
      expect(detail.poll, isNull);
      expect(detail.identification, isNull);
    });
  });

  group('ForumMyStats / ForumBadge / ForumProfile.badges (wave 4)', () {
    test('ForumMyStats.fromJson parses the ME_STATS_SCHEMA shape', () {
      final stats = ForumMyStats.fromJson({
        'posts': 12,
        'solutions_accepted': 3,
        'identifications_shared': 4,
        'streak_days': 2,
        'badge_name': 'Botanist',
        'badge_progress': 4,
        'badge_target': 10,
        'badges': [
          {
            'slug': 'early-bird',
            'name': 'Early Bird',
            'description': 'Joined in the first season',
            'awarded_at': '2026-01-05T00:00:00Z',
          },
        ],
      });
      expect(stats.posts, 12);
      expect(stats.solutionsAccepted, 3);
      expect(stats.identificationsShared, 4);
      expect(stats.streakDays, 2);
      expect(stats.badgeName, 'Botanist');
      expect(stats.badgeProgress, 4);
      expect(stats.badgeTarget, 10);
      expect(stats.badgeComplete, isFalse);
      expect(stats.badges.single.slug, 'early-bird');
      expect(stats.badges.single.awardedAt, isNotNull);
    });

    test('badgeComplete only when a target exists and is met', () {
      expect(myStats(badgeProgress: 10, badgeTarget: 10).badgeComplete, isTrue);
      expect(myStats(badgeProgress: 0, badgeTarget: 0).badgeComplete, isFalse);
    });

    test('ForumProfile parses badges and keeps them through a block', () {
      final p = profile(
        username: 'alice',
        badges: [badgeJson(name: 'Botanist')],
      );
      expect(p.badges.single.name, 'Botanist');
      expect(p.withBlocked(true).badges.single.name, 'Botanist');
    });
  });

  group('ForumMentionUser / ForumExpert', () {
    test('mention row falls back to the username as display name', () {
      final u = ForumMentionUser.fromJson({'username': 'alice'});
      expect(u.displayName, 'alice');
      final v = ForumMentionUser.fromJson({
        'username': 'bob',
        'display_name': 'Bob B',
      });
      expect(v.displayName, 'Bob B');
    });

    test('expert row is the author shape plus online', () {
      final e = ForumExpert.fromJson({
        'username': 'sage',
        'display_name': 'Sage',
        'trust_level': 4,
        'online': true,
      });
      expect(e.author.username, 'sage');
      expect(e.author.trustLevel, 4);
      expect(e.online, isTrue);
      expect(ForumExpert.fromJson({'username': 'x'}).online, isFalse);
    });
  });

  group('forumBodyPlainText', () {
    test('flattens headings, paragraph HTML and code; drops the rest', () {
      final text = forumBodyPlainText([
        const HeadingBlock('Title'),
        const ParagraphBlock(
          'a <strong>bold</strong> line<br>second &amp; third',
        ),
        const QuoteBlock('nested quote'),
        const PostQuoteBlock(
          text: 'nested post quote',
          postId: 5,
          available: true,
        ),
        const ForumImageBlock(id: 1, url: 'u', alt: 'a'),
        const DeletedImageBlock(),
        const EmbedBlock(url: 'https://youtu.be/x'),
        const UnknownBlock('mystery'),
        const CodeBlock(code: 'print(1)', language: 'dart'),
      ]);
      expect(text, 'Title\n\na bold line\nsecond & third\n\nprint(1)');
      expect(text, isNot(contains('nested quote')));
      expect(text, isNot(contains('nested post quote')));
    });

    test('list items become lines', () {
      expect(
        forumBodyPlainText(const [
          ParagraphBlock('<ul><li>one</li><li>two</li></ul>'),
        ]),
        'one\ntwo',
      );
    });
  });

  group('forumQuoteDraft (todo 342)', () {
    test('keys the excerpt to the post id and carries the author name '
        'separately — never as a "wrote:" line in the text', () {
      final draft = forumQuoteDraft(
        post(
          id: 2,
          authorOverride: author(username: 'bob', displayName: 'Bob B'),
          body: const [ParagraphBlock('Water it less.')],
        ),
      )!;
      expect(draft.postId, 2);
      expect(draft.text, 'Water it less.');
      expect(draft.authorName, 'Bob B');
      // The server resolves the attribution from the id; a name in the text
      // would only feed its mention scanner (todo 341 waves 3+4 review).
      expect(draft.text, isNot(contains('wrote')));
      expect(draft.text, isNot(contains('@')));
    });

    test('caps the excerpt and marks the cut', () {
      final long = 'x' * (forumQuoteMaxChars + 50);
      final draft = forumQuoteDraft(post(body: [ParagraphBlock(long)]))!;
      expect(draft.text.endsWith('…'), isTrue);
      expect(draft.text.length, forumQuoteMaxChars + 1);
    });

    test('is null for a post with nothing quotable', () {
      expect(
        forumQuoteDraft(
          post(
            body: const [ForumImageBlock(id: 1, url: 'u', alt: '')],
          ),
        ),
        isNull,
      );
    });
  });

  group('mentionFragmentAt / insertMention (wave 4)', () {
    TextEditingValue at(String text, int caret) => TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: caret),
    );

    test('finds the @word under the caret', () {
      final f = mentionFragmentAt(at('hi @al', 6));
      expect(f, isNotNull);
      expect(f!.prefix, 'al');
      expect(f.start, 3);
      expect(f.end, 6);
    });

    test('the span runs to the end of the word when the caret is inside', () {
      final f = mentionFragmentAt(at('@alice rocks', 3))!;
      expect(f.prefix, 'al');
      expect(f.start, 0);
      expect(f.end, 6);
    });

    test('an email is not a mention, and a bare @ has no prefix yet', () {
      expect(mentionFragmentAt(at('me@gmail', 8)), isNull);
      expect(mentionFragmentAt(at('hi @', 4)), isNull);
      expect(mentionFragmentAt(at('done @al ', 9)), isNull);
      expect(
        mentionFragmentAt(
          const TextEditingValue(
            text: '@al',
            selection: TextSelection(baseOffset: 0, extentOffset: 3),
          ),
        ),
        isNull,
      );
    });

    test('insertMention replaces the fragment and parks the caret after '
        'the trailing space', () {
      final value = insertMention(
        at('hi @al there', 6),
        start: 3,
        end: 6,
        username: 'alice',
      );
      expect(value.text, 'hi @alice  there');
      expect(value.selection.baseOffset, 'hi @alice '.length);
      expect(value.selection.isCollapsed, isTrue);
      expect(value.composing, TextRange.empty);
    });
  });
}
