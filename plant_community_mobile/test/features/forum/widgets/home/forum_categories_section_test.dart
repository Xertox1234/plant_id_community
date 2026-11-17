import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_categories_section.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_accents.dart';

import '../../support/forum_test_support.dart';

ForumBoard _forum(
  int id,
  String title, {
  bool hasUnread = false,
  bool isLocked = false,
  DateTime? lastPostAt,
  String? slug,
  String icon = '',
  String colour = '',
}) => ForumBoard(
  id: id,
  title: title,
  slug: slug ?? 'f$id',
  icon: icon,
  colour: colour,
  description: '',
  topicCount: 12,
  postCount: 80,
  hasUnread: hasUnread,
  isLocked: isLocked,
  lastPostAt: lastPostAt,
);

ForumCategory _category(
  int id,
  String title,
  List<ForumBoard> forums, {
  String icon = '',
  List<ForumLink> links = const [],
}) => ForumCategory(
  id: id,
  title: title,
  slug: 'c$id',
  description: '',
  icon: icon,
  colour: '',
  hasUnread: false,
  forums: forums,
  links: links,
);

Future<void> _pump(WidgetTester tester, Widget child) async {
  tester.view.physicalSize = const Size(375, 2000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.build(Brightness.dark, AppTheme.defaultDensity),
      home: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  );
}

Widget _wrapHome(FakeForumApi api) => ProviderScope(
  overrides: [
    forumApiProvider.overrideWithValue(api),
    forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
    authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: false)),
  ],
  child: const MaterialApp(home: ForumScreen()),
);

void main() {
  group('ForumCategoriesSection', () {
    testWidgets('two categories render in feed order with their forums', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'General', [_forum(1, 'Plant identification')]),
            _category(2, 'Community', [_forum(2, 'Show & tell')]),
          ],
          onForumTap: (_) {},
        ),
      );
      double y(String t) => tester.getTopLeft(find.text(t)).dy;
      expect(y('General'), lessThan(y('Plant identification')));
      expect(y('Plant identification'), lessThan(y('Community')));
      expect(y('Community'), lessThan(y('Show & tell')));
    });

    testWidgets('a category icon shows before its name; blank is ignored', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'General', [_forum(1, 'A')], icon: '🌿'),
            _category(2, 'Community', [_forum(2, 'B')], icon: '  '),
          ],
          onForumTap: (_) {},
        ),
      );
      expect(find.text('🌿 General'), findsOneWidget);
      expect(find.text('Community'), findsOneWidget);
    });

    testWidgets('a forum shows the server icon and colour, not the slug\'s', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'General', [
              // care-problems is hardcoded droplet + pollen; the server wins.
              _forum(
                1,
                'Care',
                slug: 'care-problems',
                icon: '🪴',
                colour: 'orchid',
              ),
            ]),
          ],
          onForumTap: (_) {},
        ),
      );
      expect(find.text('🪴'), findsOneWidget);
      final tile = tester.widget<CanopyAccentTile>(
        find.byType(CanopyAccentTile),
      );
      final canopy = tester.element(find.byType(CanopyAccentTile)).canopy;
      expect(tile.tone, canopy.sky);
      expect(tile.emoji, '🪴');
    });

    testWidgets('the unread dot shows on an unread row only', (tester) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'General', [
              _forum(1, 'Unread one', hasUnread: true),
              _forum(2, 'Read one'),
            ]),
          ],
          onForumTap: (_) {},
        ),
      );
      expect(find.byKey(const ValueKey('unread-dot')), findsOneWidget);
      expect(
        find.descendant(
          of: find.ancestor(
            of: find.text('Unread one'),
            matching: find.byType(CanopyPressable),
          ),
          matching: find.byKey(const ValueKey('unread-dot')),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: find.ancestor(
            of: find.text('Read one'),
            matching: find.byType(CanopyPressable),
          ),
          matching: find.byKey(const ValueKey('unread-dot')),
        ),
        findsNothing,
      );
    });

    testWidgets('a category header is announced by title only', (tester) async {
      final handle = tester.ensureSemantics();
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'General', [_forum(1, 'A')], icon: '🌿'),
          ],
          onForumTap: (_) {},
        ),
      );
      final node = tester.getSemantics(find.text('🌿 General'));
      expect(node.label, 'General');
      expect(node.flagsCollection.isHeader, isTrue);
      handle.dispose();
    });

    testWidgets('unread dot and last activity show', (tester) async {
      final handle = tester.ensureSemantics();
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'General', [
              _forum(
                1,
                'Plant identification',
                hasUnread: true,
                lastPostAt: DateTime.now().subtract(
                  const Duration(hours: 2, minutes: 5),
                ),
              ),
            ]),
          ],
          onForumTap: (_) {},
        ),
      );
      expect(find.bySemanticsLabel(RegExp('unread')), findsOneWidget);
      expect(find.text('12 topics · 80 posts · 2h'), findsOneWidget);
      handle.dispose();
    });

    for (final unread in [true, false]) {
      testWidgets('a ${unread ? 'unread' : 'read'} row is announced once', (
        tester,
      ) async {
        final handle = tester.ensureSemantics();
        await _pump(
          tester,
          ForumCategoriesSection(
            categories: [
              _category(1, 'General', [
                _forum(1, 'Plant identification', hasUnread: unread),
              ]),
            ],
            onForumTap: (_) {},
          ),
        );
        final label = tester.getSemantics(find.byType(CanopyPressable)).label;
        expect('Plant identification'.allMatches(label), hasLength(1));
        expect(label.contains('unread'), unread);
        handle.dispose();
      });
    }

    testWidgets('a category with only links or locked forums is skipped', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'Only locked', [_forum(1, 'Secret', isLocked: true)]),
            _category(
              2,
              'Only links',
              const [],
              links: const [
                ForumLink(
                  id: 1,
                  title: 'Docs',
                  slug: 'docs',
                  description: '',
                  linkUrl: 'https://example.com',
                  trackClicks: false,
                ),
              ],
            ),
            _category(3, 'Open', [_forum(3, 'Visible')]),
          ],
          onForumTap: (_) {},
        ),
      );
      expect(find.text('Only locked'), findsNothing);
      expect(find.text('Only links'), findsNothing);
      expect(find.text('Secret'), findsNothing);
      expect(find.text('Open'), findsOneWidget);
      expect(find.text('Visible'), findsOneWidget);
    });

    testWidgets('tapping a forum reports it', (tester) async {
      ForumBoard? tapped;
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'General', [_forum(1, 'Plant identification')]),
          ],
          onForumTap: (f) => tapped = f,
        ),
      );
      await tester.tap(find.text('Plant identification'));
      expect(tapped?.id, 1);
    });
  });

  group('forum home Forums section', () {
    testWidgets('empty feed shows "No forums yet."', (tester) async {
      await tester.pumpWidget(_wrapHome(FakeForumApi()));
      await tester.pumpAndSettle();
      expect(find.text('No forums yet.'), findsOneWidget);
    });

    testWidgets('feed error shows Retry and the other sections still build', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categoriesError = ApiException('x', connectivity: true);
      await tester.pumpWidget(_wrapHome(api));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      expect(find.text('Could not load forums.'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
      // Recent activity built too: its empty-state line is not the feed's.
      expect(find.text('Nothing here yet.'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(minutes: 2));
    });
  });
}
