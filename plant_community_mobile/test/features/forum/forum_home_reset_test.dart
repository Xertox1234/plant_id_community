import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_latest_replies_view.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_season_card.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import 'support/forum_test_support.dart';

/// The home's data belongs to one viewer: a block, a sign-in, a sign-out or
/// an account switch drops it (spec §4, §6.4); a section that fails shows its
/// error at once, not a skeleton through Riverpod's retries (spec §8.4).

ForumRecentTopic _topic(int id) => ForumRecentTopic(
  id: id,
  slug: 'topic-$id',
  title: 'Topic $id',
  board: const ForumTopicBoardRef(id: 1, slug: 'care', title: 'Care'),
  replyCount: 2,
  lastPostAt: DateTime.now().subtract(const Duration(hours: 1)),
);

FakeForumApi _api() => FakeForumApi()
  ..boards = const [
    ForumBoard(
      id: 1,
      title: 'Care',
      slug: 'care',
      description: 'Light, water, soil.',
      topicCount: 1,
      postCount: 1,
    ),
  ]
  ..recentTopics = [_topic(1), _topic(2)]
  ..experts = [expert(username: 'fern', online: true)]
  ..communityStats = const ForumCommunityStats(
    membersOnline: 1,
    registeredMembers: 2,
  );

class _FakeUser implements User {
  _FakeUser(this.uid);

  @override
  final String uid;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// Pumps the home in a container the test can reach, and returns it.
Future<ProviderContainer> _pump(
  WidgetTester tester,
  FakeForumApi api, {
  required AuthState auth,
  bool settle = true,
}) async {
  tester.view.physicalSize = const Size(375, 2000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final container = ProviderContainer(
    overrides: [
      forumApiProvider.overrideWithValue(api),
      forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
      authServiceProvider.overrideWith(
        () => FakeAuthService(loggedIn: false, initial: auth),
      ),
    ],
  );
  addTearDown(container.dispose);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        theme: AppTheme.build(Brightness.light, AppTheme.defaultDensity),
        home: const ForumScreen(),
      ),
    ),
  );
  if (settle) await tester.pumpAndSettle();
  return container;
}

FakeAuthService _auth(ProviderContainer c) =>
    c.read(authServiceProvider.notifier) as FakeAuthService;

/// Lets Riverpod's retry backoff run out so no timer outlives the test.
Future<void> _drainRetries(WidgetTester tester) async {
  for (var i = 0; i < 12; i++) {
    await tester.pump(const Duration(seconds: 5));
  }
}

Future<void> _openCard(WidgetTester tester, String title) async {
  await tester.tap(find.text(title));
  await tester.pumpAndSettle();
}

/// The home's per-viewer fetch counts, to compare before and after a reset.
({int topics, int stats, int experts, int me}) _counts(FakeForumApi api) => (
  topics: api.recentTopicsLimits.length,
  stats: api.communityStatsCalls,
  experts: api.fetchExpertsCalls,
  me: api.fetchMyStatsCalls,
);

void main() {
  group('the home resets for a new viewer', () {
    testWidgets('a block refetches the home and collapses the open card', (
      tester,
    ) async {
      final api = _api();
      final container = await _pump(
        tester,
        api,
        auth: const AuthState(jwtToken: 'jwt'),
      );
      await _openCard(tester, 'Topic 1');
      expect(find.byType(ForumLatestRepliesView), findsOneWidget);
      final before = _counts(api);

      container
          .read(authorBlockChangesProvider.notifier)
          .emit(username: 'fern', blocked: true);
      await tester.pumpAndSettle();

      final after = _counts(api);
      expect(after.topics, before.topics + 1);
      expect(after.stats, before.stats + 1);
      expect(after.experts, before.experts + 1);
      expect(after.me, before.me + 1);
      expect(container.read(expandedActivityTopicProvider), isNull);
      expect(find.byType(ForumLatestRepliesView), findsNothing);
      // The open card's peek was dropped: reopening fetches it afresh.
      await _openCard(tester, 'Topic 1');
      expect(api.latestRepliesCalls(1), 2);
    });

    testWidgets('a sign-in refetches the home and shows the season', (
      tester,
    ) async {
      final api = _api();
      final container = await _pump(tester, api, auth: const AuthState());
      expect(find.byType(ForumSeasonCard), findsNothing);
      await _openCard(tester, 'Topic 2');
      final before = _counts(api);

      _auth(container).setAuth(const AuthState(jwtToken: 'jwt'));
      await tester.pumpAndSettle();

      final after = _counts(api);
      expect(after.topics, before.topics + 1);
      expect(after.stats, before.stats + 1);
      expect(after.experts, before.experts + 1);
      expect(container.read(expandedActivityTopicProvider), isNull);
      expect(find.byType(ForumSeasonCard), findsOneWidget);
    });

    testWidgets('a sign-out refetches the home and never asks for stats', (
      tester,
    ) async {
      final api = _api();
      final container = await _pump(
        tester,
        api,
        auth: const AuthState(jwtToken: 'jwt'),
      );
      await _openCard(tester, 'Topic 1');
      final before = _counts(api);

      _auth(container).setAuth(const AuthState());
      await tester.pumpAndSettle();

      final after = _counts(api);
      expect(after.topics, before.topics + 1);
      expect(after.stats, before.stats + 1);
      expect(after.experts, before.experts + 1);
      expect(after.me, before.me);
      expect(container.read(expandedActivityTopicProvider), isNull);
      expect(find.byType(ForumSeasonCard), findsNothing);
    });

    testWidgets('an account switch resets; a token refresh does not', (
      tester,
    ) async {
      final api = _api();
      final container = await _pump(
        tester,
        api,
        auth: AuthState(jwtToken: 'a1', firebaseUser: _FakeUser('ada')),
      );
      final start = _counts(api);

      // Same member, new token: nothing changes for the viewer.
      _auth(
        container,
      ).setAuth(AuthState(jwtToken: 'a2', firebaseUser: _FakeUser('ada')));
      await tester.pumpAndSettle();
      expect(_counts(api), start);

      _auth(
        container,
      ).setAuth(AuthState(jwtToken: 'b1', firebaseUser: _FakeUser('bob')));
      await tester.pumpAndSettle();
      final after = _counts(api);
      expect(after.topics, start.topics + 1);
      expect(after.stats, start.stats + 1);
      expect(after.me, start.me + 1);
    });
  });

  group('latest replies live as long as the home', () {
    testWidgets('reopening a card does not refetch while the home is up', (
      tester,
    ) async {
      final api = _api();
      final container = await _pump(tester, api, auth: const AuthState());
      await _openCard(tester, 'Topic 1');
      await _openCard(tester, 'Topic 1'); // collapse
      expect(find.byType(ForumLatestRepliesView), findsNothing);
      await tester.pump(const Duration(seconds: 1));
      await _openCard(tester, 'Topic 1');
      expect(api.latestRepliesCalls(1), 1);
      expect(container.exists(latestRepliesProvider(1)), isTrue);

      // The home goes away: its peeks go with it.
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: SizedBox()),
        ),
      );
      await tester.pumpAndSettle();
      expect(container.exists(latestRepliesProvider(1)), isFalse);
    });
  });

  group('a failing section shows its error while Riverpod retries', () {
    for (final (label, error) in [
      ('network (no status)', ApiException('offline')),
      ('503', ApiException('down', statusCode: 503)),
    ]) {
      testWidgets('boards, recent activity and season: $label', (tester) async {
        final api = _api()
          ..boardsError = error
          ..recentTopicsError = error
          ..failMyStatsWith = error;
        await _pump(
          tester,
          api,
          auth: const AuthState(jwtToken: 'jwt'),
          settle: false,
        );
        // Past the first failure, well inside the ~40 s of retries.
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 50));
        await tester.pump(const Duration(milliseconds: 500));

        expect(find.text('Could not load boards.'), findsOneWidget);
        expect(find.text('Could not load recent topics.'), findsOneWidget);
        expect(find.text('Could not load your stats.'), findsOneWidget);
        expect(find.bySemanticsLabel('Loading boards'), findsNothing);
        expect(find.bySemanticsLabel('Loading recent topics'), findsNothing);
        expect(find.bySemanticsLabel('Loading your stats'), findsNothing);

        // Riverpod is still retrying behind the error.
        await tester.pump(const Duration(seconds: 3));
        expect(api.fetchBoardsCalls, greaterThan(1));
        expect(api.recentTopicsLimits.length, greaterThan(1));
        expect(find.text('Could not load boards.'), findsOneWidget);

        // Retry works once the network is back.
        api
          ..boardsError = null
          ..recentTopicsError = null
          ..failMyStatsWith = null;
        final retries = find.text('Retry').evaluate().length;
        expect(retries, 3);
        for (var i = retries - 1; i >= 0; i--) {
          await tester.tap(find.text('Retry').at(i));
        }
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));
        expect(find.text('Could not load boards.'), findsNothing);
        expect(find.text('Could not load recent topics.'), findsNothing);
        expect(find.text('Could not load your stats.'), findsNothing);
        expect(find.text('Care'), findsWidgets);
        expect(find.text('Topic 1'), findsOneWidget);
        expect(find.byType(ForumSeasonCard), findsOneWidget);
        await _drainRetries(tester);
      });
    }
  });
}
