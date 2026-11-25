import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/collapsed_categories.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_link_launcher.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/features/forum/services/forum_unlock_store.dart';
import 'package:plant_community_mobile/features/forum/utils/board_identity.dart';
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
  bool hasUnread = false,
}) => ForumCategory(
  id: id,
  title: title,
  slug: 'c$id',
  description: '',
  icon: icon,
  colour: '',
  hasUnread: hasUnread,
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

Widget _wrapHome(
  FakeForumApi api, {
  ForumLinkLauncher? launcher,
  AuthState? auth,
  CollapsedCategoriesStore? collapsedStore,
}) => ProviderScope(
  overrides: [
    collapsedCategoriesStoreProvider.overrideWithValue(
      collapsedStore ?? FakeCollapsedCategoriesStore(),
    ),
    // Secure storage answers on real time, which a widget test never
    // advances: a signed-in feed would wait on it for ever.
    forumUnlockStoreProvider.overrideWithValue(FakeForumUnlockStore()),
    if (launcher != null)
      forumExternalLinkLauncherProvider.overrideWithValue(launcher),
    forumApiProvider.overrideWithValue(api),
    forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
    authServiceProvider.overrideWith(
      () => FakeAuthService(loggedIn: false, initial: auth),
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

    testWidgets('a link that resolves after another screen was pushed '
        'does not open', (tester) async {
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
      unawaited(
        Navigator.of(tester.element(find.byType(ForumScreen))).push(
          MaterialPageRoute<void>(
            builder: (_) => const Scaffold(body: Text('Elsewhere')),
          ),
        ),
      );
      await tester.pumpAndSettle();
      gate.complete();
      await tester.pumpAndSettle();
      expect(opened, isEmpty);
      expect(find.text("This link can't be opened."), findsNothing);

      // Back on the forum, the next tap opens: the guard was released.
      Navigator.of(tester.element(find.text('Elsewhere'))).pop();
      await tester.pumpAndSettle();
      api.resolveLinkGate = null;
      await tester.tap(find.text('Care guide'));
      await tester.pumpAndSettle();
      expect(opened, hasLength(1));
    });

    testWidgets('a link that resolves after the tab went inactive '
        'does not open', (tester) async {
      final opened = <Uri>[];
      final gate = Completer<void>();
      final tabActive = ValueNotifier<bool>(true);
      addTearDown(tabActive.dispose);
      final api = FakeForumApi()
        ..categories = [
          _category(1, 'Reading', const [], links: [_link(1, 'Care guide')]),
        ]
        ..resolvedLink = Uri.parse('https://example.com/resolved')
        ..resolveLinkGate = gate;
      // go_router wraps an inactive shell branch in TickerMode(enabled: false).
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumExternalLinkLauncherProvider.overrideWithValue((uri) async {
              opened.add(uri);
              return true;
            }),
            forumApiProvider.overrideWithValue(api),
            forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: false),
            ),
          ],
          child: MaterialApp(
            home: ValueListenableBuilder<bool>(
              valueListenable: tabActive,
              builder: (_, active, child) =>
                  TickerMode(enabled: active, child: child!),
              child: const ForumScreen(),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Care guide'));
      await tester.pump();
      tabActive.value = false;
      await tester.pump();
      gate.complete();
      await tester.pump();
      await tester.pump();
      expect(opened, isEmpty);
      expect(find.text("This link can't be opened."), findsNothing);
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
      expect(find.text("This link can't be opened."), findsNothing);
      api.resolvedLink = Uri.parse('https://example.com/x');
      await tester.tap(find.text('Care guide'));
      await tester.pumpAndSettle();
      expect(launches, 1);
      expect(find.text("This link can't be opened."), findsOneWidget);
    });
  });

  group('locked rows', () {
    ForumBoard locked(int id, String title) => ForumBoard(
      id: id,
      title: title,
      slug: 'care-problems', // hardcoded identity: droplet + pollen
      description: 'Members only',
      icon: '🪴',
      colour: 'orchid',
      topicCount: 12,
      postCount: 80,
      hasUnread: true,
      isLocked: true,
      lastPostAt: DateTime.now().subtract(const Duration(hours: 2)),
    );

    testWidgets('a locked row shows no counts, time or unread dot', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'General', [locked(1, 'Secret garden')]),
          ],
          onForumTap: (_) {},
          onLockedTap: (_) {},
        ),
      );
      expect(find.text('Secret garden'), findsOneWidget);
      expect(find.text('Members only'), findsOneWidget);
      expect(find.textContaining('topic'), findsNothing);
      expect(find.textContaining('post'), findsNothing);
      expect(find.textContaining('2h'), findsNothing);
      expect(find.byKey(const ValueKey('unread-dot')), findsNothing);
      expect(find.byIcon(LucideIcons.chevronRight), findsNothing);
    });

    for (final brightness in Brightness.values) {
      testWidgets('a locked row: lock in the tile, default tone '
          '(${brightness.name})', (tester) async {
        tester.view.physicalSize = const Size(375, 2000);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.build(brightness, AppTheme.defaultDensity),
            home: Scaffold(
              body: ForumCategoriesSection(
                categories: [
                  _category(1, 'General', [locked(1, 'Secret garden')]),
                ],
                onForumTap: (_) {},
                onLockedTap: (_) {},
              ),
            ),
          ),
        );
        final tile = tester.widget<CanopyAccentTile>(
          find.byType(CanopyAccentTile),
        );
        final canopy = tester.element(find.byType(CanopyAccentTile)).canopy;
        expect(tile.icon, LucideIcons.lock);
        expect(tile.emoji, isNull, reason: 'the lock, not the server emoji');
        // The slug's tone, never the server colour (orchid = sky).
        expect(tile.tone, CanopyTone.pollen.colorOf(canopy));
        expect(find.byIcon(LucideIcons.lock), findsOneWidget);
        // The row is one tap target of at least 48pt.
        final row = find.byType(CanopyPressable);
        expect(tester.getSize(row).height, greaterThanOrEqualTo(48));
      });
    }

    for (final brightness in Brightness.values) {
      for (final (size, scale) in [
        (const Size(320, 640), 2.0),
        (const Size(375, 812), 1.0),
      ]) {
        testWidgets('a locked row fits and meets the guidelines: '
            '${size.width.toInt()}pt x$scale, ${brightness.name}', (
          tester,
        ) async {
          final handle = tester.ensureSemantics();
          tester.view.physicalSize = size;
          tester.view.devicePixelRatio = 1.0;
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          await tester.pumpWidget(
            MaterialApp(
              theme: AppTheme.build(brightness, AppTheme.defaultDensity),
              home: MediaQuery(
                data: MediaQueryData(
                  size: size,
                  textScaler: TextScaler.linear(scale),
                ),
                child: Scaffold(
                  body: SingleChildScrollView(
                    child: ForumCategoriesSection(
                      categories: [
                        _category(1, 'General', [
                          locked(1, 'A rather long password forum title'),
                        ]),
                      ],
                      onForumTap: (_) {},
                      onLockedTap: (_) {},
                    ),
                  ),
                ),
              ),
            ),
          );
          expect(tester.takeException(), isNull);
          await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
          await expectLater(tester, meetsGuideline(iOSTapTargetGuideline));
          await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
          await expectLater(tester, meetsGuideline(textContrastGuideline));
          handle.dispose();
        });
      }
    }

    testWidgets('a locked row is announced once, by title and description', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'General', [locked(1, 'Secret garden')]),
          ],
          onForumTap: (_) {},
          onLockedTap: (_) {},
        ),
      );
      final label = tester.getSemantics(find.byType(CanopyPressable)).label;
      expect(label, 'Secret garden, Members only, password protected');
      handle.dispose();
    });

    testWidgets('tapping a locked row reports it to onLockedTap only', (
      tester,
    ) async {
      ForumBoard? lockedTap;
      ForumBoard? forumTap;
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'General', [locked(1, 'Secret garden')]),
          ],
          onForumTap: (f) => forumTap = f,
          onLockedTap: (f) => lockedTap = f,
        ),
      );
      await tester.tap(find.text('Secret garden'));
      expect(lockedTap?.id, 1);
      expect(forumTap, isNull);
    });

    testWidgets('a category whose forums are all locked draws its heading '
        'and rows', (tester) async {
      final api = FakeForumApi()
        ..categories = [
          _category(1, 'Private', [
            locked(1, 'Secret garden'),
            locked(2, 'Seed swap'),
          ]),
        ];
      await tester.pumpWidget(_wrapHome(api));
      await tester.pumpAndSettle();
      expect(find.text('Private'), findsOneWidget);
      expect(find.text('Secret garden'), findsOneWidget);
      expect(find.text('Seed swap'), findsOneWidget);
      expect(find.text('No forums yet.'), findsNothing);
    });

    testWidgets('"No forums yet." only when no category has a forum or link', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          _category(1, 'Empty one', const []),
          _category(2, 'Empty two', const []),
        ];
      await tester.pumpWidget(_wrapHome(api));
      await tester.pumpAndSettle();
      expect(find.text('No forums yet.'), findsOneWidget);
      expect(find.text('Empty one'), findsNothing);
    });

    testWidgets('guest tap on a locked row shows the sign-in message', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = [
          _category(1, 'Private', [locked(1, 'Secret garden')]),
        ];
      await tester.pumpWidget(_wrapHome(api));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Secret garden'));
      await tester.pump();
      expect(find.text('Sign in to open this forum.'), findsOneWidget);
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

  group('collapsing', () {
    List<ForumCategory> two({bool unread = true}) => [
      _category(1, 'General', [_forum(1, 'Ferns')], hasUnread: unread),
      _category(2, 'Community', [_forum(2, 'Swaps')]),
    ];

    testWidgets('a collapsed category hides its rows and shows its unread '
        'dot', (tester) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: two(),
          onForumTap: (_) {},
          collapsed: const {1},
          onToggleCollapse: (_) {},
        ),
      );
      expect(find.text('General'), findsOneWidget);
      expect(find.text('Ferns'), findsNothing);
      expect(find.text('Swaps'), findsOneWidget);
      expect(find.byKey(const ValueKey('category-unread-dot')), findsOneWidget);
    });

    testWidgets('an expanded or read category shows no header dot', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            ...two(),
            _category(3, 'Read', [_forum(3, 'Old')]),
          ],
          onForumTap: (_) {},
          collapsed: const {3},
          onToggleCollapse: (_) {},
        ),
      );
      expect(find.byKey(const ValueKey('category-unread-dot')), findsNothing);
    });

    testWidgets('all categories collapsed shows only headers, no error', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: two(),
          onForumTap: (_) {},
          collapsed: const {1, 2},
          onToggleCollapse: (_) {},
        ),
      );
      expect(tester.takeException(), isNull);
      expect(find.text('General'), findsOneWidget);
      expect(find.text('Community'), findsOneWidget);
      expect(find.byType(CanopyGroupedCard), findsNothing);
    });

    testWidgets('an unknown id in the set changes nothing', (tester) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: two(),
          onForumTap: (_) {},
          collapsed: const {99},
          onToggleCollapse: (_) {},
        ),
      );
      expect(find.text('Ferns'), findsOneWidget);
      expect(find.text('Swaps'), findsOneWidget);
      expect(find.byType(CanopyGroupedCard), findsNWidgets(2));
    });

    testWidgets('a category with nothing to draw is still skipped', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [_category(1, 'Empty', const []), ...two()],
          onForumTap: (_) {},
          collapsed: const {1},
          onToggleCollapse: (_) {},
        ),
      );
      expect(find.text('Empty'), findsNothing);
    });

    testWidgets('without onToggleCollapse: no chevron, no toggle, the set is '
        'ignored', (tester) async {
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: two(),
          onForumTap: (_) {},
          collapsed: const {1},
        ),
      );
      expect(find.byIcon(LucideIcons.chevronDown), findsNothing);
      expect(find.text('Ferns'), findsOneWidget);
      expect(
        find.ancestor(
          of: find.text('General'),
          matching: find.byType(CanopyPressable),
        ),
        findsNothing,
      );
    });

    testWidgets('the header is one 48pt header button that says what it '
        'does', (tester) async {
      final handle = tester.ensureSemantics();
      ForumCategory? tapped;
      await _pump(
        tester,
        ForumCategoriesSection(
          categories: [
            _category(1, 'General', [_forum(1, 'A')], icon: '🌿'),
            _category(2, 'Community', [_forum(2, 'B')]),
          ],
          onForumTap: (_) {},
          collapsed: const {2},
          onToggleCollapse: (c) => tapped = c,
        ),
      );
      final open = tester.getSemantics(find.text('🌿 General'));
      expect(open.label, 'Collapse General');
      expect(open.flagsCollection.isHeader, isTrue);
      expect(open.flagsCollection.isButton, isTrue);
      final shut = tester.getSemantics(find.text('Community'));
      expect(shut.label, 'Expand Community');
      final header = find.ancestor(
        of: find.text('🌿 General'),
        matching: find.byType(CanopyPressable),
      );
      expect(tester.getSize(header).height, greaterThanOrEqualTo(48));
      expect(find.byIcon(LucideIcons.chevronDown), findsNWidgets(2));

      await tester.tap(find.text('🌿 General'));
      expect(tapped?.id, 1);
      handle.dispose();
    });

    for (final reduce in [false, true]) {
      testWidgets(
        'collapsing ${reduce ? 'does not move under' : 'animates '
                  'without'} reduced motion',
        (tester) async {
          Widget section(Set<int> collapsed) => MediaQuery(
            data: MediaQueryData(disableAnimations: reduce),
            child: ForumCategoriesSection(
              categories: two(),
              onForumTap: (_) {},
              collapsed: collapsed,
              onToggleCollapse: (_) {},
            ),
          );
          await _pump(tester, section(const {}));
          await _pump(tester, section(const {1}));
          // The card is never built once collapsed. Reduced motion: nothing
          // animates the space it leaves, and the chevron turns at once.
          expect(find.text('Ferns'), findsNothing);
          if (!reduce) {
            await tester.pump();
            expect(tester.hasRunningAnimations, isTrue);
          }
          expect(
            find.byType(AnimatedSize),
            reduce ? findsNothing : findsWidgets,
          );
          final turn = tester.widget<AnimatedRotation>(
            find.byType(AnimatedRotation).first,
          );
          expect(turn.duration, reduce ? Duration.zero : isNot(Duration.zero));
          await tester.pumpAndSettle();
        },
      );
    }
  });

  group('forum home collapsing', () {
    List<ForumCategory> feed() => [
      _category(1, 'General', [_forum(1, 'Ferns')]),
    ];

    testWidgets('a guest tap collapses and expands the category', (
      tester,
    ) async {
      final api = FakeForumApi()..categories = feed();
      final store = FakeCollapsedCategoriesStore();
      await tester.pumpWidget(_wrapHome(api, collapsedStore: store));
      await tester.pumpAndSettle();
      await tester.tap(find.text('General'));
      await tester.pumpAndSettle();
      expect(find.text('Ferns'), findsNothing);
      expect(store.guest, {1});
      await tester.tap(find.text('General'));
      await tester.pumpAndSettle();
      expect(find.text('Ferns'), findsOneWidget);
      expect(api.collapsedSaves, isEmpty);
    });

    testWidgets('a failed save puts it back and says so', (tester) async {
      final api = FakeForumApi()
        ..categories = feed()
        ..collapsedSaveError = ApiException('x', statusCode: 500);
      await tester.pumpWidget(_wrapHome(api, auth: signedInAs('u1')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('General'));
      await tester.pumpAndSettle();
      expect(api.collapsedSaves, [
        [1],
      ]);
      expect(find.text("Couldn't save. Try again."), findsOneWidget);
      expect(find.text('Ferns'), findsOneWidget);
    });

    testWidgets('a member\'s saved list collapses the category', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categories = feed()
        ..collapsedCategories = [1];
      await tester.pumpWidget(_wrapHome(api, auth: signedInAs('u1')));
      await tester.pumpAndSettle();
      expect(find.text('General'), findsOneWidget);
      expect(find.text('Ferns'), findsNothing);
    });

    testWidgets('pull to refresh re-reads the member\'s list', (tester) async {
      final api = FakeForumApi()..categories = feed();
      await tester.pumpWidget(_wrapHome(api, auth: signedInAs('u1')));
      await tester.pumpAndSettle();
      expect(api.fetchCollapsedCalls, 1);
      expect(find.text('Ferns'), findsOneWidget);

      api.collapsedCategories = [1]; // collapsed on the web meanwhile
      await tester.fling(find.text('General'), const Offset(0, 400), 1000);
      await tester.pumpAndSettle();
      expect(api.fetchCollapsedCalls, 2);
      expect(find.text('Ferns'), findsNothing);
    });

    testWidgets('Retry on the forums re-reads the member\'s list', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..categoriesError = ApiException('x', statusCode: 404);
      await tester.pumpWidget(_wrapHome(api, auth: signedInAs('u1')));
      await tester.pumpAndSettle();
      expect(find.text('Could not load forums.'), findsOneWidget);
      expect(api.fetchCollapsedCalls, 1);

      api
        ..categoriesError = null
        ..categories = feed()
        ..collapsedCategories = [1];
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(api.fetchCollapsedCalls, 2);
      expect(find.text('General'), findsOneWidget);
      expect(find.text('Ferns'), findsNothing);
    });
  });
}
