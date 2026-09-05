import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import '../support/forum_test_support.dart';

/// A container with the fake API installed. Every provider under test is
/// autoDispose, so callers hold a `listen` on what they exercise (see
/// forum_parity_providers_test.dart).
ProviderContainer _container(FakeForumApi api) {
  final container = ProviderContainer(
    overrides: [forumApiProvider.overrideWithValue(api)],
  );
  addTearDown(container.dispose);
  return container;
}

ForumPoll _pollOf(ProviderContainer c) =>
    c.read(topicDetailProvider(10)).asData!.value.poll!;

void main() {
  group('TopicDetail.votePoll (todo 341 wave 3)', () {
    test('writes the server\'s recomputed poll, never a local count', () async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, poll: poll(totalVotes: 4))
        // The server is the authority — a result whose numbers differ from
        // anything a local increment would produce must win.
        ..voteResult = poll(
          totalVotes: 99,
          myVoteOptionIds: [2],
          options: [pollOption(id: 2, text: 'Fortnightly', voteCount: 42)],
        );
      final container = _container(api);
      container.listen(topicDetailProvider(10), (_, _) {});
      await container.read(topicDetailProvider(10).future);

      await container.read(topicDetailProvider(10).notifier).votePoll([2]);

      expect(api.votePollCalls, [
        [2],
      ]);
      final updated = _pollOf(container);
      expect(updated.totalVotes, 99);
      expect(updated.myVoteOptionIds, [2]);
      expect(updated.options.single.voteCount, 42);
      expect(updated.isVoting, isFalse);
    });

    test('marks the ballot pending while in flight (optimistic disabling) '
        'and clears it on success', () async {
      final gate = Completer<ForumPoll>();
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, poll: poll(totalVotes: 1))
        ..voteGate = gate;
      final container = _container(api);
      container.listen(topicDetailProvider(10), (_, _) {});
      await container.read(topicDetailProvider(10).future);

      final pending = container.read(topicDetailProvider(10).notifier).votePoll(
        [1, 3],
      );
      final inFlight = _pollOf(container);
      expect(inFlight.pendingOptionIds, [1, 3]);
      expect(inFlight.isVoting, isTrue);
      // Counts and the recorded vote are untouched until the server says.
      expect(inFlight.totalVotes, 1);
      expect(inFlight.hasVoted, isFalse);

      gate.complete(poll(totalVotes: 2, myVoteOptionIds: [1, 3]));
      await pending;
      final settled = _pollOf(container);
      expect(settled.isVoting, isFalse);
      expect(settled.hasVoted, isTrue);
      expect(settled.totalVotes, 2);
    });

    test('a refused vote reverts the pending marker, leaves the poll as it '
        'was, and rethrows', () async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, poll: poll(totalVotes: 4))
        ..failVoteWith = ApiException('This poll has closed.', statusCode: 409);
      final container = _container(api);
      container.listen(topicDetailProvider(10), (_, _) {});
      await container.read(topicDetailProvider(10).future);

      await expectLater(
        container.read(topicDetailProvider(10).notifier).votePoll([1]),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 409)),
      );

      final reverted = _pollOf(container);
      expect(reverted.isVoting, isFalse);
      expect(reverted.hasVoted, isFalse);
      expect(reverted.totalVotes, 4);
    });

    test('a double-tap sends one ballot (re-entrancy guard)', () async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, poll: poll());
      final container = _container(api);
      container.listen(topicDetailProvider(10), (_, _) {});
      await container.read(topicDetailProvider(10).future);
      final notifier = container.read(topicDetailProvider(10).notifier);

      await Future.wait([
        notifier.votePoll([1]),
        notifier.votePoll([2]),
      ]);

      expect(api.votePollCalls, [
        [1],
      ]);
      expect(_pollOf(container).myVoteOptionIds, [1]);
    });

    test('a topic without a poll, or an empty ballot, sends nothing', () async {
      final api = FakeForumApi()..topicDetail = topicDetail(id: 10);
      final container = _container(api);
      container.listen(topicDetailProvider(10), (_, _) {});
      await container.read(topicDetailProvider(10).future);

      await container.read(topicDetailProvider(10).notifier).votePoll([1]);
      expect(api.votePollCalls, isEmpty);

      api.topicDetail = topicDetail(id: 11, poll: poll());
      container.listen(topicDetailProvider(11), (_, _) {});
      await container.read(topicDetailProvider(11).future);
      await container.read(topicDetailProvider(11).notifier).votePoll([]);
      expect(api.votePollCalls, isEmpty);
    });
  });

  group('MentionSearch (todo 341 wave 4)', () {
    // testWidgets, not test: the debounce is a Timer, and only the widget
    // test binding runs the body under a fake clock `tester.pump(Duration)`
    // can advance. The container is disposed explicitly at the end of each
    // body so no timer is pending when the binding checks.
    testWidgets('waits the debounce window and collapses rapid prefixes into '
        'the last one', (tester) async {
      final api = FakeForumApi()
        ..mentionUsers = [mentionUser('alice'), mentionUser('alan')];
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      container.listen(mentionSearchProvider, (_, _) {});
      final notifier = container.read(mentionSearchProvider.notifier);

      notifier.lookup('a');
      expect(container.read(mentionSearchProvider).isLoading, isTrue);
      await tester.pump(const Duration(milliseconds: 100));
      notifier.lookup('al');
      await tester.pump(const Duration(milliseconds: 299));
      expect(api.mentionSearchCalls, isEmpty);

      await tester.pump(const Duration(milliseconds: 1));
      await tester.pump();
      expect(api.mentionSearchCalls, ['al']);
      final state = container.read(mentionSearchProvider);
      expect(state.query, 'al');
      expect(state.isLoading, isFalse);
      expect(state.results.map((u) => u.username), ['alice', 'alan']);

      container.dispose();
    });

    testWidgets('a response for a superseded prefix is discarded even when '
        'it lands last', (tester) async {
      final gates = [
        Completer<List<ForumMentionUser>>(),
        Completer<List<ForumMentionUser>>(),
      ];
      final api = FakeForumApi()..mentionGates = gates;
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      container.listen(mentionSearchProvider, (_, _) {});
      final notifier = container.read(mentionSearchProvider.notifier);

      notifier.lookup('a');
      await tester.pump(forumMentionDebounce);
      notifier.lookup('al');
      await tester.pump(forumMentionDebounce);
      expect(api.mentionSearchCalls, ['a', 'al']);

      gates[1].complete([mentionUser('alice')]);
      await tester.pump();
      expect(
        container.read(mentionSearchProvider).results.map((u) => u.username),
        ['alice'],
      );

      // The older, broader lookup resolves late: it must not overwrite.
      gates[0].complete([mentionUser('adam'), mentionUser('alice')]);
      await tester.pump();
      expect(
        container.read(mentionSearchProvider).results.map((u) => u.username),
        ['alice'],
      );

      container.dispose();
    });

    testWidgets('clear() drops the pending timer and an in-flight response', (
      tester,
    ) async {
      final gate = Completer<List<ForumMentionUser>>();
      final api = FakeForumApi()..mentionGates = [gate];
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      container.listen(mentionSearchProvider, (_, _) {});
      final notifier = container.read(mentionSearchProvider.notifier);

      notifier.lookup('a');
      await tester.pump(forumMentionDebounce);
      expect(api.mentionSearchCalls, ['a']);
      notifier.clear();
      expect(container.read(mentionSearchProvider).isActive, isFalse);

      gate.complete([mentionUser('adam')]);
      await tester.pump();
      expect(container.read(mentionSearchProvider).results, isEmpty);

      // A cancelled timer never fires.
      notifier.lookup('b');
      notifier.clear();
      await tester.pump(forumMentionDebounce);
      expect(api.mentionSearchCalls, ['a']);

      container.dispose();
    });

    testWidgets('a failed lookup shows nothing and never throws', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..failMentionSearchWith = ApiException('slow down', statusCode: 429);
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      container.listen(mentionSearchProvider, (_, _) {});

      container.read(mentionSearchProvider.notifier).lookup('a');
      await tester.pump(forumMentionDebounce);
      await tester.pump();
      final state = container.read(mentionSearchProvider);
      expect(state.results, isEmpty);
      expect(state.isLoading, isFalse);
      expect(tester.takeException(), isNull);

      container.dispose();
    });
  });

  group('myStats / experts', () {
    test('pass the API payloads through', () async {
      final api = FakeForumApi()
        ..stats = myStats(posts: 7, badges: [badge()])
        ..experts = [expert(username: 'sage', online: true)];
      final container = _container(api);
      container.listen(meStatsProvider, (_, _) {});
      container.listen(expertsProvider, (_, _) {});

      final stats = await container.read(meStatsProvider.future);
      final experts = await container.read(expertsProvider.future);
      expect(stats.posts, 7);
      expect(stats.badges.single.name, 'Botanist');
      expect(experts.single.online, isTrue);
      expect(api.fetchMyStatsCalls, 1);
      expect(api.fetchExpertsCalls, 1);
    });
  });
}
