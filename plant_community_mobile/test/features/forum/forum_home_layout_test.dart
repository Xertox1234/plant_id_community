import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/core/routing/main_shell.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/features/blog/models/blog_post.dart';
import 'package:plant_community_mobile/features/blog/services/blog_api.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_experts_strip.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_activity_card.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_home_footer.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_latest_replies_view.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_season_card.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

import '../blog/support/fake_blog_api.dart';
import 'support/forum_test_support.dart';

const _longBoard = ForumTopicBoardRef(
  id: 1,
  slug: 'pests-and-diseases',
  title: 'Pests, diseases and other unwelcome visitors',
);

ForumRecentTopic _topic(
  int id, {
  String? title,
  String? imageUrl,
  bool isUnread = false,
  bool isSolved = false,
}) => ForumRecentTopic(
  id: id,
  slug: 'topic-$id',
  title: title ?? 'Topic $id',
  board: _longBoard,
  replyCount: 12,
  lastPostAt: DateTime.now().subtract(const Duration(hours: 3)),
  isUnread: isUnread,
  isSolved: isSolved,
  imageUrl: imageUrl,
);

/// After the first fetch, experts and community stats wait on a gate: a
/// refresh whose refetch is still in flight.
class _SlowRefreshApi extends FakeForumApi {
  final expertsGate = Completer<void>();
  final statsGate = Completer<void>();

  /// Every call, counted on entry (the base counters tick after the gate).
  int expertsAttempts = 0;
  int statsAttempts = 0;

  @override
  Future<List<ForumExpert>> fetchExperts() async {
    if (expertsAttempts++ > 0) await expertsGate.future;
    return super.fetchExperts();
  }

  @override
  Future<ForumCommunityStats> fetchCommunityStats() async {
    if (statsAttempts++ > 0) await statsGate.future;
    return super.fetchCommunityStats();
  }
}

/// Copies the [_fullApi] fixtures onto [api].
T _withFixtures<T extends FakeForumApi>(T api) {
  final full = _fullApi();
  return api
    ..boards = full.boards
    ..recentTopics = [_topic(1)]
    ..experts = full.experts
    ..communityStats = const ForumCommunityStats(
      membersOnline: 1,
      registeredMembers: 2,
    );
}

/// Everything the home reads, with the long strings that break layouts.
FakeForumApi _fullApi() => FakeForumApi()
  ..boards = const [
    ForumBoard(
      id: 1,
      title: 'Pests, diseases and other unwelcome visitors on houseplants',
      slug: 'pests-and-diseases',
      description:
          'Spider mites, thrips, fungus gnats, mealybugs, scale and every '
          'spot, blotch and wilt you cannot name yet.',
      topicCount: 12345,
      postCount: 678901,
    ),
    ForumBoard(
      id: 2,
      title: 'Care',
      slug: 'care',
      description: 'Light, water, soil.',
      topicCount: 1,
      postCount: 1,
    ),
  ]
  ..recentTopics = [
    _topic(
      1,
      title:
          'My Monstera deliciosa has yellowing lower leaves with brown crispy '
          'edges after I moved it next to the radiator in November',
      isUnread: true,
      isSolved: true,
    ),
    // No picture card here: its CachedNetworkImage reaches for
    // path_provider, which has no plugin under test. The picture card's own
    // 320x640 / 2.0x matrix lives in forum_activity_card_test.dart.
    _topic(2, title: 'Fungus gnats everywhere'),
    for (var i = 3; i <= 11; i++) _topic(i),
  ]
  ..stats = myStats(
    posts: 12345,
    solutionsAccepted: 678,
    identificationsShared: 9012,
    streakDays: 345,
    badgeName: 'Extraordinarily Dedicated Botanist',
    badgeProgress: 4,
    badgeTarget: 20,
    badges: [
      badge(name: 'Botanist'),
      badge(slug: 'h', name: 'Helper'),
    ],
  )
  ..experts = [
    expert(username: 'maximiliana_greenfingers_the_third', online: true),
    expert(username: 'fern'),
  ]
  ..communityStats = ForumCommunityStats(
    membersOnline: 7,
    onlineSample: [
      author(username: 'a', displayName: 'Bartholomew-Alexander Fitzgerald'),
      author(username: 'b', displayName: 'Wilhelmina Featherstonehaugh'),
      author(username: 'c', displayName: 'simtest'),
    ],
    registeredMembers: 123456,
    topicCount: 98765,
    postCount: 4321098,
    newestMember: author(
      username: 'newbie',
      displayName: 'Persephone Marguerite Ravenscroft-Delacroix',
    ),
  );

/// Bounded pumps: the picture card's CachedNetworkImage never settles.
Future<void> _settle(WidgetTester tester) async {
  await tester.pump();
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 200));
  }
}

/// The PRODUCTION router, so the shell's Identify FAB and its clearance are
/// real (as in test/routing/navigation_shell_test.dart).
Future<void> _pumpInShell(
  WidgetTester tester,
  FakeForumApi api, {
  required Size size,
  required double textScale,
  required Brightness brightness,
  bool loggedIn = true,
}) async {
  tester.view.physicalSize = size * 3;
  tester.view.devicePixelRatio = 3.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final container = ProviderContainer(
    overrides: [
      authServiceProvider.overrideWith(
        () => FakeAuthService(loggedIn: loggedIn),
      ),
      forumApiProvider.overrideWithValue(api),
      blogApiProvider.overrideWithValue(
        FakeBlogApi(
          pages: [
            BlogPostPage(items: [summary(1)], totalCount: 1),
          ],
        ),
      ),
      forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
      userProfileServiceProvider.overrideWith(
        () => FakeUserProfileService(username: 'tester'),
      ),
    ],
  );
  addTearDown(container.dispose);
  container.listen(appRouterProvider, (_, _) {});
  final router = container.read(appRouterProvider);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(
        routerConfig: router,
        theme: AppTheme.build(brightness, AppTheme.defaultDensity),
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!,
        ),
      ),
    ),
  );
  router.go(AppRoutes.forum);
  await _settle(tester);
}

/// The forum home's vertical list (the experts strip scrolls sideways).
ScrollableState _homeScroll(WidgetTester tester) {
  return tester
      .stateList<ScrollableState>(
        find.descendant(
          of: find.byType(ForumScreen),
          matching: find.byType(Scrollable),
        ),
      )
      .firstWhere((s) => s.position.axis == Axis.vertical);
}

Future<void> _scrollToEnd(WidgetTester tester) async {
  // Jump until we sit at the real end with the footer laid out; the extent
  // can still move after the first jump as late layout settles.
  final scroll = _homeScroll(tester);
  for (var i = 0; i < 30; i++) {
    scroll.position.jumpTo(scroll.position.maxScrollExtent);
    await tester.pump();
    final atEnd =
        scroll.position.pixels == scroll.position.maxScrollExtent &&
        find.byType(ForumHomeFooter).evaluate().isNotEmpty;
    if (atEnd) break;
  }
  expect(find.byType(ForumHomeFooter), findsOneWidget);
  await _settle(tester);
}

Future<void> _expectGuidelines(WidgetTester tester) async {
  await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
  await expectLater(tester, meetsGuideline(iOSTapTargetGuideline));
  await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
  await expectLater(tester, meetsGuideline(textContrastGuideline));
}

/// Standalone screen, for the state tests that need no shell.
Future<void> _pumpScreen(
  WidgetTester tester,
  FakeForumApi api, {
  bool loggedIn = false,
  Size size = const Size(375, 812),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        forumApiProvider.overrideWithValue(api),
        forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
        authServiceProvider.overrideWith(
          () => FakeAuthService(loggedIn: loggedIn),
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.build(Brightness.dark, AppTheme.defaultDensity),
        home: const ForumScreen(),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  group('forum home layout matrix', () {
    for (final size in const [Size(320, 640), Size(375, 812)]) {
      for (final scale in const [1.0, 2.0]) {
        for (final brightness in Brightness.values) {
          final label =
              '${size.width.toInt()}x${size.height.toInt()} '
              'x$scale ${brightness.name}';
          testWidgets('fits, clears the FAB and meets a11y: $label', (
            tester,
          ) async {
            // Not addTearDown: flutter_test checks for live handles BEFORE
            // tear-downs run, so the handle is disposed in a finally.
            final handle = tester.ensureSemantics();
            try {
              await _pumpInShell(
                tester,
                _fullApi(),
                size: size,
                textScale: scale,
                brightness: brightness,
              );
              expect(tester.takeException(), isNull);
              expect(find.byType(ForumSeasonCard), findsOneWidget);
              await _expectGuidelines(tester);

              await _scrollToEnd(tester);
              expect(tester.takeException(), isNull);
              final footer = tester.getRect(find.byType(ForumHomeFooter));
              final fab = tester.getRect(find.byKey(MainShell.identifyFabKey));
              expect(
                footer.bottom,
                lessThanOrEqualTo(fab.top),
                reason:
                    'the footer ends at ${footer.bottom}, under the FAB '
                    'at ${fab.top}',
              );
              await _expectGuidelines(tester);
            } finally {
              handle.dispose();
            }
          });
        }
      }
    }
  });

  group('forum home sections', () {
    testWidgets('order: season, experts, boards, activity, online, footer', (
      tester,
    ) async {
      final api = _fullApi()
        ..recentTopics = [for (var i = 1; i <= 11; i++) _topic(i)];
      // Tall enough that every section is built at once.
      await _pumpScreen(
        tester,
        api,
        loggedIn: true,
        size: const Size(375, 4000),
      );
      double top(Finder f) => tester.getTopLeft(f.first).dy;
      final season = top(find.byType(ForumSeasonCard));
      final experts = top(find.textContaining('Experts'));
      final boards = top(find.text('Boards'));
      final activity = top(find.text('Recent activity'));
      expect(season, lessThan(experts));
      expect(experts, lessThan(boards));
      expect(boards, lessThan(activity));
      expect(
        top(find.text("Who's online")),
        lessThan(top(find.byType(ForumHomeFooter))),
      );
      // Ten cards, though the feed returned eleven.
      expect(
        find.byType(ForumActivityCard, skipOffstage: false),
        findsNWidgets(10),
      );
    });

    testWidgets('signed out: no season; activity and Who\'s online show', (
      tester,
    ) async {
      final api = _fullApi()..recentTopics = [_topic(1)];
      await _pumpScreen(tester, api);
      expect(find.text('YOUR SEASON'), findsNothing);
      expect(find.byType(ForumSeasonCard), findsNothing);
      expect(api.fetchMyStatsCalls, 0);
      expect(find.byType(ForumActivityCard), findsOneWidget);
      await tester.dragUntilVisible(
        find.text("Who's online"),
        find.byType(ForumScreen),
        const Offset(0, -300),
      );
      expect(find.text("Who's online"), findsOneWidget);
    });

    testWidgets('a failed feed shows its error; Who\'s online still shows', (
      tester,
    ) async {
      final api = _fullApi()
        ..recentTopicsError = ApiException('no', statusCode: 403);
      await _pumpScreen(tester, api);
      expect(find.text('Could not load recent topics.'), findsOneWidget);
      expect(find.byType(ForumActivityCard), findsNothing);
      await tester.dragUntilVisible(
        find.byType(ForumHomeFooter),
        find.byType(ForumScreen),
        const Offset(0, -300),
      );
      expect(find.text("Who's online"), findsOneWidget);
    });

    testWidgets('failed stats hide Who\'s online only', (tester) async {
      final api = _fullApi()
        ..recentTopics = [_topic(1)]
        ..communityStatsError = ApiException('gone', statusCode: 404);
      await _pumpScreen(tester, api);
      expect(find.text('Boards'), findsOneWidget);
      expect(find.byType(ForumActivityCard), findsOneWidget);
      await tester.dragUntilVisible(
        find.byType(ForumHomeFooter),
        find.byType(ForumScreen),
        const Offset(0, -300),
      );
      expect(find.byType(ForumHomeFooter), findsOneWidget);
      expect(find.text("Who's online"), findsNothing);
    });

    testWidgets('pull-to-refresh collapses the open card and refetches', (
      tester,
    ) async {
      final api = _fullApi()..recentTopics = [_topic(1), _topic(2)];
      await _pumpScreen(tester, api);
      await tester.ensureVisible(find.text('Topic 1'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Topic 1'));
      await tester.pumpAndSettle();
      expect(find.byType(ForumLatestRepliesView), findsOneWidget);
      expect(api.latestRepliesCalls(1), 1);
      expect(api.recentTopicsLimits, hasLength(1));
      final statsBefore = api.communityStatsCalls;

      final scroll = _homeScroll(tester);
      scroll.position.jumpTo(0);
      await tester.pump();
      await tester.fling(find.byType(ForumScreen), const Offset(0, 400), 1000);
      await tester.pumpAndSettle();

      expect(find.byType(ForumLatestRepliesView), findsNothing);
      final container = ProviderScope.containerOf(
        tester.element(find.byType(ForumScreen)),
      );
      expect(container.read(expandedActivityTopicProvider), isNull);
      expect(api.recentTopicsLimits, hasLength(2));
      expect(api.communityStatsCalls, greaterThan(statsBefore));

      // The peek was dropped too: reopening fetches it afresh.
      await tester.tap(find.text('Topic 1'));
      await tester.pumpAndSettle();
      expect(api.latestRepliesCalls(1), 2);
    });

    for (final reduced in [false, true]) {
      testWidgets(
        'first build: staggered fade${reduced ? ' only (reduced motion)' : ' and rise'}; '
        'a refresh does not replay it',
        (tester) async {
          tester.view.physicalSize = const Size(375, 812);
          tester.view.devicePixelRatio = 1.0;
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          final api = _fullApi()..recentTopics = [_topic(1)];
          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                forumApiProvider.overrideWithValue(api),
                forumSyncStoreProvider.overrideWithValue(
                  InMemoryForumSyncStore(),
                ),
                authServiceProvider.overrideWith(
                  () => FakeAuthService(loggedIn: false),
                ),
              ],
              child: MaterialApp(
                home: Builder(
                  builder: (context) => MediaQuery(
                    data: MediaQuery.of(
                      context,
                    ).copyWith(disableAnimations: reduced),
                    child: const ForumScreen(),
                  ),
                ),
              ),
            ),
          );
          Iterable<Transform> risen() => tester
              .widgetList<Transform>(
                find.descendant(
                  of: find.byType(ForumScreen),
                  matching: find.byType(Transform),
                ),
              )
              .where((t) => t.transform.getTranslation().y > 0);
          Iterable<double> fading() => tester
              .widgetList<Opacity>(
                find.descendant(
                  of: find.byType(ForumScreen),
                  matching: find.byType(Opacity),
                ),
              )
              .map((o) => o.opacity)
              .where((o) => o < 1);

          // Mid-entrance: later sections are still on their way in.
          await tester.pump(const Duration(milliseconds: 100));
          expect(fading(), isNotEmpty);
          expect(risen(), reduced ? isEmpty : isNotEmpty);

          await tester.pumpAndSettle();
          expect(fading(), isEmpty);
          expect(risen(), isEmpty);

          // Pull to refresh: the sections reload, the entrance stays done.
          await tester.fling(
            find.byType(ForumScreen),
            const Offset(0, 400),
            1000,
          );
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 50));
          expect(fading(), isEmpty);
          expect(risen(), isEmpty);
          await tester.pumpAndSettle();
          expect(api.recentTopicsLimits, hasLength(2));
        },
      );
    }
  });

  testWidgets('a section keeps its State when the entrance finishes', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(375, 812);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(_withFixtures(FakeForumApi())),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false),
          ),
        ],
        child: const MaterialApp(home: ForumScreen()),
      ),
    );
    // Mid-entrance: the experts strip is built and still fading in.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 60));
    final strip = find.descendant(
      of: find.byType(ForumExpertsStrip),
      matching: find.byType(Scrollable),
    );
    final before = tester.state<ScrollableState>(strip);

    await tester.pumpAndSettle();
    expect(tester.state<ScrollableState>(strip), same(before));
  });

  testWidgets('a refresh keeps Experts and Who\'s online on screen', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(375, 812);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = _withFixtures(_SlowRefreshApi());
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false),
          ),
        ],
        child: const MaterialApp(home: ForumScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Experts'), findsOneWidget);
    expect(find.text("Who's online"), findsOneWidget);

    await tester.fling(find.text('Boards'), const Offset(0, 400), 1000);
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    // Both refetches are in flight.
    expect(api.expertsAttempts, 2);
    expect(api.statsAttempts, 2);
    expect(find.textContaining('Experts'), findsOneWidget);
    expect(find.byType(ForumExpertsStrip), findsOneWidget);
    expect(find.text("Who's online"), findsOneWidget);

    api.expertsGate.complete();
    api.statsGate.complete();
    await tester.pumpAndSettle();
    expect(find.text("Who's online"), findsOneWidget);
  });

  // Riverpod 3 keeps a refetch-in-flight as AsyncData(isLoading), but a
  // FAILED refetch is an AsyncError carrying the old value: `asData` is null
  // there, `.value` is not. The panels keep their last data.
  testWidgets('a failed refresh keeps the last Experts and Who\'s online', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(375, 812);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = _withFixtures(FakeForumApi());
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false),
          ),
        ],
        child: const MaterialApp(home: ForumScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text("Who's online"), findsOneWidget);

    api
      ..failExpertsWith = ApiException('gone', statusCode: 404)
      ..communityStatsError = ApiException('gone', statusCode: 404);
    await tester.fling(find.text('Boards'), const Offset(0, 400), 1000);
    await tester.pumpAndSettle();

    expect(api.communityStatsCalls, 2);
    expect(find.byType(ForumExpertsStrip), findsOneWidget);
    expect(find.text("Who's online"), findsOneWidget);
  });
}
