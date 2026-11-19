import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_topics_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/topic_card.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_tips_carousel.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_home_footer.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/forum/services/forum_unlock_store.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_accents.dart';

import '../support/forum_test_support.dart';

const _board = ForumBoard(
  id: 1,
  title: 'Plant identification',
  slug: 'plant-identification',
  description: 'Post a photo, get a name.',
  topicCount: 7,
  postCount: 46,
);

Widget _wrap(FakeForumApi api, {bool loggedIn = true}) => ProviderScope(
  overrides: [
    forumApiProvider.overrideWithValue(api),
    authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: loggedIn)),
  ],
  child: const MaterialApp(
    home: ForumTopicsScreen(
      boardSlug: 'plant-identification',
      boardTitle: 'Plant identification',
    ),
  ),
);

void main() {
  group('ForumTopicsScreen viewer change', () {
    testWidgets('a forum locked for the new viewer drops the previous '
        'viewer\'s topics', (tester) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(items: [topic(id: 1, title: 'Monstera albo')]);
      final container = ProviderContainer(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false, initial: signedInAs('ada')),
          ),
          // Real secure storage never answers on fake time, and a signed-in
          // topic list waits for the stored unlocks.
          forumUnlockStoreProvider.overrideWithValue(FakeForumUnlockStore()),
        ],
        retry: (_, _) => null,
      );
      addTearDown(container.dispose);
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: ForumTopicsScreen(
              boardSlug: 'plant-identification',
              boardTitle: 'Plant identification',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Monstera albo'), findsOneWidget);

      api.topicsError = ApiException(
        'locked',
        statusCode: 403,
        code: 'forum_locked',
      );
      (container.read(authServiceProvider.notifier) as FakeAuthService).setAuth(
        signedInAs('bob'),
      );
      await tester.pumpAndSettle();

      expect(find.text('Monstera albo'), findsNothing);
      expect(find.text('This forum needs a password.'), findsOneWidget);
    });
  });

  group('ForumTopicsScreen locked forum', () {
    final lockedError = ApiException(
      'This forum needs a password.',
      statusCode: 403,
      code: 'forum_locked',
    );

    Widget routed(FakeForumApi api, {Brightness? brightness, double? scale}) {
      final router = GoRouter(
        initialLocation: '/forum/boards/rare-aroids',
        routes: [
          GoRoute(
            path: '/forum/boards/:slug/unlock',
            name: 'forumUnlock',
            builder: (_, state) => Scaffold(
              body: Text(
                'UNLOCK ${state.pathParameters['slug']} ${state.extra}',
              ),
            ),
          ),
          GoRoute(
            path: '/forum/boards/:slug',
            name: 'forumBoard',
            builder: (_, state) => ForumTopicsScreen(
              boardSlug: state.pathParameters['slug']!,
              boardTitle: 'Rare aroids',
            ),
          ),
        ],
      );
      return ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: true),
          ),
        ],
        retry: (_, _) => null,
        child: MaterialApp.router(
          theme: brightness == null
              ? null
              : AppTheme.build(brightness, AppDensity.cozy),
          routerConfig: router,
          builder: (context, child) => scale == null
              ? child!
              : MediaQuery(
                  data: MediaQuery.of(
                    context,
                  ).copyWith(textScaler: TextScaler.linear(scale)),
                  child: child!,
                ),
        ),
      );
    }

    testWidgets('topic list 403 forum_locked shows the Unlock state, not '
        'Retry', (tester) async {
      final api = FakeForumApi()..topicsError = lockedError;
      await tester.pumpWidget(routed(api));
      await tester.pumpAndSettle();

      expect(find.text('This forum needs a password.'), findsOneWidget);
      expect(find.byIcon(LucideIcons.lock), findsOneWidget);
      expect(find.widgetWithText(ClayButton, 'Unlock'), findsOneWidget);
      expect(find.text('Retry'), findsNothing);
      expect(find.text('Could not load topics.'), findsNothing);
      expect(find.text('New topic'), findsNothing);
      expect(api.fetchTopicsCalls, 1);

      await tester.tap(find.widgetWithText(ClayButton, 'Unlock'));
      await tester.pumpAndSettle();
      expect(find.text('UNLOCK rare-aroids Rare aroids'), findsOneWidget);
      expect(find.byType(ForumTopicsScreen), findsNothing, reason: 'replaced');
    });

    testWidgets('another 403 still offers Retry and New topic', (tester) async {
      final api = FakeForumApi()
        ..topicsError = ApiException('Forbidden', statusCode: 403);
      await tester.pumpWidget(routed(api));
      await tester.pumpAndSettle();

      expect(find.text('Could not load topics.'), findsOneWidget);
      expect(find.text('This forum needs a password.'), findsNothing);
      expect(find.text('New topic'), findsOneWidget);
    });

    for (final brightness in Brightness.values) {
      for (final (w, h, scale) in [(320.0, 640.0, 2.0), (375.0, 812.0, 1.0)]) {
        testWidgets('the locked state fits and passes the a11y guidelines at '
            '${w}x$h @$scale (${brightness.name})', (tester) async {
          tester.view.physicalSize = Size(w, h);
          tester.view.devicePixelRatio = 1.0;
          addTearDown(tester.view.reset);
          final handle = tester.ensureSemantics();
          final api = FakeForumApi()..topicsError = lockedError;
          await tester.pumpWidget(
            routed(api, brightness: brightness, scale: scale),
          );
          await tester.pumpAndSettle();

          expect(tester.takeException(), isNull);
          expect(find.text('This forum needs a password.'), findsOneWidget);
          await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
          await expectLater(tester, meetsGuideline(iOSTapTargetGuideline));
          await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
          await expectLater(tester, meetsGuideline(textContrastGuideline));
          handle.dispose();
        });
      }
    }
  });

  group('ForumTopicsScreen', () {
    testWidgets('shows the board intro above one row per topic', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(
          items: [
            topic(id: 1, title: 'Monstera albo'),
            topic(id: 2, title: 'What tree is this?'),
          ],
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('Plant identification'), findsOneWidget);
      expect(find.text('Post a photo, get a name.'), findsOneWidget);
      expect(find.text('7 topics · 46 posts'), findsOneWidget);
      expect(find.byType(TopicRow), findsNWidgets(2));
      expect(find.text('New topic'), findsOneWidget);
    });

    testWidgets('the header uses the server icon and colour', (tester) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [
            ForumBoard(
              id: 1,
              title: 'Plant identification',
              slug: 'plant-identification', // hardcoded: leaf + sage
              description: '',
              topicCount: 7,
              postCount: 46,
              icon: '🪴',
              colour: 'orchid',
            ),
          ]),
        ]
        ..topics = CursorPage(items: [topic(id: 1, title: 'Monstera albo')]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('🪴'), findsOneWidget);
      final tile = tester.widget<CanopyAccentTile>(
        find.byType(CanopyAccentTile).first,
      );
      final canopy = tester.element(find.byType(CanopyAccentTile).first).canopy;
      expect(tile.tone, canopy.sky);
    });

    for (final brightness in Brightness.values) {
      for (final (w, h, scale) in [(320.0, 640.0, 2.0), (375.0, 812.0, 1.0)]) {
        testWidgets('a full list (switcher, tags, a pinned row) fits and '
            'passes the a11y guidelines at ${w}x$h @$scale '
            '(${brightness.name})', (tester) async {
          tester.view.physicalSize = Size(w, h);
          tester.view.devicePixelRatio = 1.0;
          addTearDown(tester.view.reset);
          final handle = tester.ensureSemantics();
          final api = FakeForumApi()
            ..categories = [
              categoryOf(const [
                _board,
                ForumBoard(
                  id: 2,
                  title: 'Care & problems',
                  slug: 'care-problems',
                  description: '',
                  topicCount: 6,
                  postCount: 33,
                ),
              ]),
            ]
            ..topics = CursorPage(
              items: [
                topic(id: 1, title: 'Read first', isPinned: true),
                topic(id: 2, title: 'Monstera albo', tags: ['monstera']),
              ],
            );
          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                forumApiProvider.overrideWithValue(api),
                authServiceProvider.overrideWith(
                  () => FakeAuthService(loggedIn: true),
                ),
              ],
              child: MaterialApp(
                theme: AppTheme.build(brightness, AppDensity.cozy),
                builder: (context, child) => MediaQuery(
                  data: MediaQuery.of(
                    context,
                  ).copyWith(textScaler: TextScaler.linear(scale)),
                  child: child!,
                ),
                home: const ForumTopicsScreen(
                  boardSlug: 'plant-identification',
                  boardTitle: 'Plant identification',
                ),
              ),
            ),
          );
          await tester.pumpAndSettle();

          expect(tester.takeException(), isNull);
          // A screen reader can act on the title and the chips, not just
          // read them.
          for (final label in [
            'Plant identification. Switch forum',
            'Sort: Active',
            'Tag monstera',
          ]) {
            final control = find.bySemanticsLabel(label);
            // At the small size the hero fills the first screen.
            await tester.scrollUntilVisible(
              control,
              100,
              scrollable: find.byType(Scrollable).first,
            );
            expect(
              tester.getSemantics(control),
              isSemantics(isButton: true, hasTapAction: true),
              reason: label,
            );
            expect(
              tester.getSize(control).height,
              greaterThanOrEqualTo(48),
              reason: label,
            );
          }
          expect(
            tester.getSize(find.byType(FloatingActionButton)).height,
            greaterThanOrEqualTo(48),
          );
          // At the small size the hero fills the first screen: bring the
          // pinned row up before judging its contrast.
          await tester.scrollUntilVisible(
            find.text('Pinned'),
            200,
            scrollable: find.byType(Scrollable).first,
          );
          await tester.pump();
          expect(tester.takeException(), isNull);
          // Not the whole-screen tap-target guidelines: the row's author
          // name and avatar are older targets (small, the avatar unlabelled)
          // that this list inherits.
          await expectLater(tester, meetsGuideline(textContrastGuideline));
          handle.dispose();
        });
      }
    }

    testWidgets('the forum footer closes the page, under the topics', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(items: [topic(id: 1, title: 'Monstera albo')]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.byType(ForumHomeFooter),
        200,
        scrollable: find.byType(Scrollable).first,
      );

      expect(
        tester.getTopLeft(find.byType(ForumHomeFooter)).dy,
        greaterThanOrEqualTo(tester.getBottomLeft(find.byType(TopicRow)).dy),
      );
    });

    testWidgets('top contributors list this forum\'s posters with their '
        'counts', (tester) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(items: [topic(id: 1)])
        ..contributors = [
          ForumContributor(
            author: author(username: 'maya', displayName: 'Maya Okafor'),
            postCount: 12,
          ),
          ForumContributor(author: author(username: 'lena'), postCount: 1),
        ];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Top contributors'),
        200,
        scrollable: find.byType(Scrollable).first,
      );

      expect(find.text('Maya Okafor'), findsOneWidget);
      expect(find.text('12 posts'), findsOneWidget);
      expect(find.text('1 post'), findsOneWidget);
    });

    testWidgets('no contributors, or a server without the endpoint, shows no '
        'section', (tester) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(items: [topic(id: 1)])
        ..contributorsError = ApiException('Not found', statusCode: 404);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.byType(ForumHomeFooter),
        200,
        scrollable: find.byType(Scrollable).first,
      );

      expect(find.text('Top contributors'), findsNothing);
      expect(find.text('Active discussions'), findsNothing);
    });

    testWidgets('active discussions are the other forums\' topics only', (
      tester,
    ) async {
      ForumRecentTopic recent(int id, String title, String slug, String name) =>
          ForumRecentTopic(
            id: id,
            slug: 'topic-$id',
            title: title,
            board: ForumTopicBoardRef(id: id, slug: slug, title: name),
            replyCount: 4,
            lastPostAt: DateTime(2026, 1, 2),
          );
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(items: [topic(id: 1)])
        ..recentTopics = [
          recent(7, 'Here already', 'plant-identification', 'Plant ID'),
          recent(8, 'Yellow leaves again', 'care-problems', 'Care & problems'),
        ];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Active discussions'),
        200,
        scrollable: find.byType(Scrollable).first,
      );

      expect(find.text('Yellow leaves again'), findsOneWidget);
      expect(
        find.textContaining('Care & problems · 4 replies'),
        findsOneWidget,
      );
      expect(find.text('Here already'), findsNothing);
    });

    testWidgets('a tag chip filters the list, and again clears it', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(
          items: [
            topic(id: 1, title: 'Monstera albo', tags: ['monstera', 'aroid']),
            topic(id: 2, title: 'Another monstera', tags: ['monstera']),
          ],
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      expect(api.fetchTopicsFilters.last, (null, null));

      // Most used first; the row's own labels are not buttons.
      final chips = find.bySemanticsLabel(RegExp(r'^Tag '));
      expect(chips, findsNWidgets(2));
      expect(
        tester.getTopLeft(find.bySemanticsLabel('Tag monstera')).dx,
        lessThan(tester.getTopLeft(find.bySemanticsLabel('Tag aroid')).dx),
      );

      await tester.tap(find.bySemanticsLabel('Tag aroid'));
      await tester.pumpAndSettle();
      expect(api.fetchTopicsFilters.last, (null, 'aroid'));

      await tester.tap(find.bySemanticsLabel('Tag aroid'));
      await tester.pumpAndSettle();
      expect(api.fetchTopicsFilters.last, (null, null));
    });

    testWidgets('a tag with no topics says so instead of "No topics yet"', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(
          items: [
            topic(id: 1, tags: ['hoya']),
          ],
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      api.topics = const CursorPage(items: []);
      await tester.tap(find.bySemanticsLabel('Tag hoya'));
      await tester.pumpAndSettle();

      expect(find.text('No topics tagged #hoya'), findsOneWidget);
      expect(find.text('No topics yet'), findsNothing);
      // The chip outlives the empty page, so the filter can be cleared.
      expect(find.bySemanticsLabel('Tag hoya'), findsOneWidget);
    });

    testWidgets('the sort sheet sends the chosen order; the forum default is '
        'sent as none', (tester) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(items: [topic(id: 1)]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.tap(find.bySemanticsLabel('Sort: Active'));
      await tester.pumpAndSettle();
      // The test surface is short: the sheet scrolls rather than overflows.
      await tester.ensureVisible(find.text('Most replies'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Most replies'));
      await tester.pumpAndSettle();
      expect(api.fetchTopicsFilters.last, ('-post_count', null));
      expect(find.bySemanticsLabel('Sort: Most replies'), findsOneWidget);

      await tester.tap(find.bySemanticsLabel('Sort: Most replies'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Active'));
      await tester.pumpAndSettle();
      expect(api.fetchTopicsFilters.last, (null, null));
    });

    testWidgets('the title switches forum when there is another to go to', (
      tester,
    ) async {
      const other = ForumBoard(
        id: 2,
        title: 'Care & problems',
        slug: 'care-problems',
        description: '',
        topicCount: 6,
        postCount: 33,
      );
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board, other]),
        ]
        ..topics = CursorPage(items: [topic(id: 1)]);
      final router = GoRouter(
        initialLocation: '/forum/boards/plant-identification',
        routes: [
          GoRoute(
            path: '/forum/boards/:slug',
            name: 'forumBoard',
            builder: (_, state) => ForumTopicsScreen(
              boardSlug: state.pathParameters['slug']!,
              boardTitle: state.extra as String?,
            ),
          ),
        ],
      );
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(
        find.bySemanticsLabel('Plant identification. Switch forum'),
      );
      await tester.pumpAndSettle();
      expect(find.text('Switch forum'), findsOneWidget);
      expect(find.text('6 topics'), findsOneWidget);

      await tester.tap(find.text('Care & problems'));
      await tester.pumpAndSettle();
      expect(
        find.bySemanticsLabel('Care & problems. Switch forum'),
        findsOneWidget,
      );
      // Replaced, not stacked: Back leaves the forum.
      expect(router.canPop(), isFalse);
    });

    testWidgets('with one forum the title is plain text, not a button', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(items: [topic(id: 1)]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.bySemanticsLabel(RegExp('Switch forum')), findsNothing);
      expect(find.text('Plant identification'), findsOneWidget);
    });

    testWidgets('the topics still show when the boards list fails', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categoriesError = Exception('offline')
        ..topics = CursorPage(items: [topic(id: 1, title: 'Monstera albo')]);

      await tester.pumpWidget(_wrap(api));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Plant identification'), findsOneWidget);
      expect(find.byType(TopicRow), findsOneWidget);
      // No board intro in the hero; the Who's online panel further down
      // has site counts of its own.
      expect(
        find.descendant(
          of: find.byType(ForumTipsCarousel),
          matching: find.textContaining('topics ·'),
        ),
        findsNothing,
      );

      // Let Riverpod's retry of the failed boards fetch run out.
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(minutes: 2));
    });

    testWidgets('pull to refresh refetches the header counts too', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ]
        ..topics = CursorPage(items: [topic(id: 1, title: 'Monstera albo')]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      final before = api.fetchCategoriesCalls;

      await tester.fling(find.byType(ListView), const Offset(0, 400), 1000);
      await tester.pumpAndSettle();

      expect(api.fetchCategoriesCalls, before + 1);
    });

    testWidgets('an empty board says so, and offers no button signed out', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf(const [_board]),
        ];

      await tester.pumpWidget(_wrap(api, loggedIn: false));
      await tester.pumpAndSettle();

      expect(find.text('No topics yet'), findsOneWidget);
      expect(find.byType(TopicRow), findsNothing);
      expect(find.text('New topic'), findsNothing);
    });

    testWidgets('a board with more topics offers Load more under the list', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..topics = CursorPage(
          items: [topic(id: 1, title: 'first')],
          next: 'https://api/forum/topics/?cursor=p2',
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(OutlinedButton, 'Load more'), findsOneWidget);
    });
  });

  group('TopicRow author', () {
    testWidgets('the name and the avatar open the author, not the topic', (
      tester,
    ) async {
      var authorTaps = 0;
      var rowTaps = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TopicRow(
              topic: topic(authorOverride: author(username: 'alice')),
              onTap: () => rowTaps++,
              onAuthorTap: () => authorTaps++,
            ),
          ),
        ),
      );

      await tester.tap(find.text('alice'));
      await tester.tap(find.byType(AuthorAvatar));
      await tester.pump();
      expect(authorTaps, 2);
      expect(rowTaps, 0);

      await tester.tap(find.text('Sample topic'));
      await tester.pump();
      expect(rowTaps, 1);
    });
  });
}
