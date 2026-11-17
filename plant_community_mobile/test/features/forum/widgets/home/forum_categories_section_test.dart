import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_link_launcher.dart';
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

ForumLink _link(
  int id,
  String title, {
  String description = '',
  bool track = false,
  int? clicks,
}) => ForumLink(
  id: id,
  title: title,
  slug: 'l$id',
  description: description,
  linkUrl: 'https://example.com/$id',
  trackClicks: track,
  clickCount: clicks,
);

Widget _wrapHome(FakeForumApi api, {ForumLinkLauncher? launcher}) =>
    ProviderScope(
      overrides: [
        if (launcher != null)
          forumExternalLinkLauncherProvider.overrideWithValue(launcher),
        forumApiProvider.overrideWithValue(api),
        forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
        authServiceProvider.overrideWith(
          () => FakeAuthService(loggedIn: false),
        ),
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

  group('link rows', () {
    testWidgets('links draw after the forums of their category', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(
              1,
              'General',
              [_forum(1, 'Plant identification')],
              links: [_link(1, 'Care guide', description: 'Outside reading')],
            ),
            _category(2, 'Community', [_forum(2, 'Show & tell')]),
          ],
          onForumTap: (_) {},
          onLinkTap: (_) {},
        ),
      );
      double y(String t) => tester.getTopLeft(find.text(t)).dy;
      expect(y('Plant identification'), lessThan(y('Care guide')));
      expect(y('Care guide'), lessThan(y('Community')));
      expect(find.text('Outside reading'), findsOneWidget);
      expect(find.text('External link'), findsOneWidget);
      expect(find.byIcon(LucideIcons.externalLink), findsOneWidget);
      // No chevron on a link row; the forum row keeps its own.
      expect(find.byIcon(LucideIcons.chevronRight), findsNWidgets(2));
    });

    testWidgets('forums and links share ONE card per category', (tester) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(
              1,
              'General',
              [_forum(1, 'Alpha'), _forum(2, 'Beta')],
              links: [_link(1, 'Care guide')],
            ),
          ],
          onForumTap: (_) {},
          onLinkTap: (_) {},
        ),
      );
      final card = find.descendant(
        of: find.byKey(const ValueKey('category-1')),
        matching: find.byType(CanopyGroupedCard),
      );
      expect(card, findsOneWidget);
      for (final t in ['Alpha', 'Beta', 'Care guide']) {
        expect(
          find.descendant(of: card, matching: find.text(t)),
          findsOneWidget,
        );
      }
      double y(String t) => tester.getTopLeft(find.text(t)).dy;
      expect(y('Beta'), lessThan(y('Care guide')));
    });

    testWidgets('a links-only category draws one card', (tester) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(
              1,
              'Links',
              const [],
              links: [_link(1, 'One'), _link(2, 'Two')],
            ),
          ],
          onForumTap: (_) {},
          onLinkTap: (_) {},
        ),
      );
      expect(find.byType(CanopyGroupedCard), findsOneWidget);
      expect(find.text('One'), findsOneWidget);
      expect(find.text('Two'), findsOneWidget);
    });

    testWidgets('a category with only links draws heading and rows', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'Only links', const [], links: [_link(1, 'Docs')]),
          ],
          onForumTap: (_) {},
          onLinkTap: (_) {},
        ),
      );
      expect(find.text('Only links'), findsOneWidget);
      expect(find.text('Docs'), findsOneWidget);
    });

    testWidgets('click count shows only when tracked and not null', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(
              1,
              'Links',
              const [],
              links: [
                _link(1, 'Many', track: true, clicks: 12),
                _link(2, 'One', track: true, clicks: 1),
                _link(3, 'Untracked', track: false, clicks: 5),
                _link(4, 'Hidden', track: true),
              ],
            ),
          ],
          onForumTap: (_) {},
          onLinkTap: (_) {},
        ),
      );
      expect(find.text('External link · 12 clicks'), findsOneWidget);
      expect(find.text('External link · 1 click'), findsOneWidget);
      expect(find.text('External link'), findsNWidgets(2));
    });

    testWidgets('a link row is announced once', (tester) async {
      final handle = tester.ensureSemantics();
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(
              1,
              'Links',
              const [],
              links: [
                _link(
                  1,
                  'Care guide',
                  description: 'Outside',
                  track: true,
                  clicks: 3,
                ),
              ],
            ),
          ],
          onForumTap: (_) {},
          onLinkTap: (_) {},
        ),
      );
      final label = tester.getSemantics(find.byType(CanopyPressable)).label;
      expect(label, 'Care guide, Outside, External link, 3 clicks');
      handle.dispose();
    });

    testWidgets('tapping a link reports it', (tester) async {
      ForumLink? tapped;
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'Links', const [], links: [_link(9, 'Docs')]),
          ],
          onForumTap: (_) {},
          onLinkTap: (l) => tapped = l,
        ),
      );
      await tester.tap(find.text('Docs'));
      expect(tapped?.id, 9);
    });
  });

  group('forum home link forums', () {
    testWidgets('a links-only category is not "No forums yet."', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          _category(1, 'Reading', const [], links: [_link(1, 'Care guide')]),
        ];
      await tester.pumpWidget(_wrapHome(api));
      await tester.pumpAndSettle();
      expect(find.text('No forums yet.'), findsNothing);
      expect(find.text('Reading'), findsOneWidget);
      expect(find.text('Care guide'), findsOneWidget);
    });

    testWidgets('tapping a link opens the resolved address externally', (
      tester,
    ) async {
      final opened = <Uri>[];
      final api = FakeForumApi()
        ..categories = [
          _category(1, 'Reading', const [], links: [_link(1, 'Care guide')]),
        ]
        ..resolvedLink = Uri.parse('https://example.com/resolved');
      await tester.pumpWidget(
        _wrapHome(
          api,
          launcher: (uri) async {
            opened.add(uri);
            return true;
          },
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Care guide'));
      await tester.pumpAndSettle();
      expect(opened, [Uri.parse('https://example.com/resolved')]);
      expect(api.resolveLinkCalls, [1]);
      expect(find.text("This link can't be opened."), findsNothing);
    });

    testWidgets('a second tap while a link is resolving is ignored', (
      tester,
    ) async {
      final opened = <Uri>[];
      final gate = Completer<void>();
      final api = FakeForumApi()
        ..categories = [
          _category(1, 'Reading', const [], links: [_link(1, 'Care guide')]),
        ]
        ..resolvedLink = Uri.parse('https://example.com/resolved')
        ..resolveLinkGate = gate;
      await tester.pumpWidget(
        _wrapHome(
          api,
          launcher: (uri) async {
            opened.add(uri);
            return true;
          },
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Care guide'));
      await tester.pump();
      await tester.tap(find.text('Care guide'));
      await tester.pump();
      gate.complete();
      await tester.pumpAndSettle();
      expect(api.resolveLinkCalls, [1]);
      expect(opened, hasLength(1));

      await tester.tap(find.text('Care guide'));
      await tester.pumpAndSettle();
      expect(api.resolveLinkCalls, [1, 1]);
      expect(opened, hasLength(2));
    });

    testWidgets('a launcher that throws shows the message', (tester) async {
      final api = FakeForumApi()
        ..categories = [
          _category(1, 'Reading', const [], links: [_link(1, 'Care guide')]),
        ]
        ..resolvedLink = Uri.parse('https://example.com/resolved');
      await tester.pumpWidget(
        _wrapHome(api, launcher: (uri) async => throw Exception('no browser')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Care guide'));
      await tester.pumpAndSettle();
      expect(find.text("This link can't be opened."), findsOneWidget);
    });

    testWidgets('a null resolve or a refused launch shows the message', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          _category(1, 'Reading', const [], links: [_link(1, 'Care guide')]),
        ];
      var launches = 0;
      await tester.pumpWidget(
        _wrapHome(
          api,
          launcher: (uri) async {
            launches++;
            return false;
          },
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Care guide'));
      await tester.pumpAndSettle();
      expect(launches, 0);
      expect(find.text("This link can't be opened."), findsOneWidget);

      ScaffoldMessenger.of(
        tester.element(find.byType(Scaffold).first),
      ).clearSnackBars();
      await tester.pumpAndSettle();
      api.resolvedLink = Uri.parse('https://example.com/x');
      await tester.tap(find.text('Care guide'));
      await tester.pumpAndSettle();
      expect(launches, 1);
      expect(find.text("This link can't be opened."), findsOneWidget);
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
