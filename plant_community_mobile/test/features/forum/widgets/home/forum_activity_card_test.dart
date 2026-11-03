import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_avatar_cluster.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_activity_card.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_latest_replies_view.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import '../../support/forum_test_support.dart';

const _board = ForumTopicBoardRef(id: 1, slug: 'care', title: 'Care');

ForumRecentTopic _topic(
  int id, {
  String? imageUrl,
  bool isUnread = false,
  bool isSolved = false,
  String? title,
}) => ForumRecentTopic(
  id: id,
  slug: 'topic-$id',
  title: title ?? 'Topic $id',
  board: _board,
  replyCount: 4,
  lastPostAt: DateTime.now().subtract(const Duration(hours: 2)),
  isUnread: isUnread,
  isSolved: isSolved,
  imageUrl: imageUrl,
);

ForumLatestReply _reply(int id, String excerpt, {String name = 'Iris'}) =>
    ForumLatestReply(
      id: id,
      author: author(username: name.toLowerCase(), displayName: name),
      createdAt: DateTime.now().subtract(Duration(hours: id)),
      excerpt: excerpt,
    );

ForumLatestReplies _peek({
  bool solution = true,
  int replies = 4,
  ForumAuthor? startedBy,
  bool withStarter = true,
}) => ForumLatestReplies(
  solution: solution ? _reply(99, 'The accepted answer') : null,
  replies: [for (var i = 1; i <= replies; i++) _reply(i, 'Reply number $i')],
  participantCount: 3,
  participants: [
    author(username: 'iris', displayName: 'Iris Delgado'),
    author(username: 'will', displayName: 'Will Tower'),
    author(username: 'sam', displayName: 'Sam Whitaker'),
  ],
  startedBy: withStarter
      ? (startedBy ?? author(username: 'will', displayName: 'Will Tower'))
      : null,
);

Future<void> _pump(
  WidgetTester tester,
  FakeForumApi api,
  List<ForumRecentTopic> topics, {
  List<int>? opened,
  Brightness brightness = Brightness.dark,
  Size size = const Size(375, 812),
  double textScale = 1.0,
  bool disableAnimations = false,
  bool autoRetry = false,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [forumApiProvider.overrideWithValue(api)],
      // Off by default so fetch counts are exact; see the autoRetry test.
      retry: autoRetry ? null : (_, _) => null,
      child: MaterialApp(
        theme: AppTheme.build(brightness, AppTheme.defaultDensity),
        home: MediaQuery(
          data: MediaQueryData(
            size: size,
            textScaler: TextScaler.linear(textScale),
            disableAnimations: disableAnimations,
          ),
          child: Scaffold(
            body: SingleChildScrollView(
              child: Column(
                children: [
                  for (final t in topics)
                    Padding(
                      padding: const EdgeInsets.all(8),
                      child: ForumActivityCard(
                        key: ValueKey('card-${t.id}'),
                        topic: t,
                        onOpen: () => opened?.add(t.id),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

Finder _card(int id) => find.byKey(ValueKey('card-$id'));

Finder _bodyOf(int id) => find.descendant(
  of: _card(id),
  matching: find.byType(ForumLatestRepliesView),
);

Future<void> _tapCard(WidgetTester tester, int id) =>
    tester.tap(find.text('Topic $id'));

void main() {
  group('ForumActivityCard', () {
    testWidgets('picture card opens the topic and never fetches replies', (
      tester,
    ) async {
      final api = FakeForumApi()..latestRepliesByTopic = {1: _peek()};
      final opened = <int>[];
      await _pump(tester, api, [
        _topic(1, imageUrl: 'https://example.test/a.jpg'),
      ], opened: opened);
      // Bounded pumps: a CachedNetworkImage placeholder never settles.
      await tester.pump();
      expect(find.byType(CachedNetworkImage), findsOneWidget);
      expect(
        tester
            .widget<CachedNetworkImage>(find.byType(CachedNetworkImage))
            .memCacheWidth,
        375,
      );
      await _tapCard(tester, 1);
      await tester.pump(const Duration(milliseconds: 300));
      expect(opened, [1]);
      expect(_bodyOf(1), findsNothing);
      expect(api.latestRepliesCalls(1), 0);
    });

    for (final size in const [Size(320, 640), Size(375, 812)]) {
      for (final scale in const [1.0, 2.0]) {
        testWidgets('text-card chevron is at the right content edge, '
            '${size.width.toInt()}pt x$scale', (tester) async {
          final api = FakeForumApi();
          await _pump(
            tester,
            api,
            [_topic(1), _topic(2, imageUrl: 'https://x.test/a.jpg')],
            size: size,
            textScale: scale,
          );
          final textRight = tester
              .getTopRight(
                find.descendant(
                  of: _card(1),
                  matching: find.byIcon(LucideIcons.chevronDown),
                ),
              )
              .dx;
          final pictureRight = tester
              .getTopRight(
                find.descendant(
                  of: _card(2),
                  matching: find.byIcon(LucideIcons.chevronRight),
                ),
              )
              .dx;
          expect((textRight - pictureRight).abs(), lessThanOrEqualTo(1));
        });
      }
    }

    testWidgets('text card expands to the solution plus the 2 newest', (
      tester,
    ) async {
      final api = FakeForumApi()..latestRepliesByTopic = {1: _peek()};
      final opened = <int>[];
      await _pump(tester, api, [_topic(1, isSolved: true)], opened: opened);
      expect(_bodyOf(1), findsNothing);

      await _tapCard(tester, 1);
      await tester.pumpAndSettle();
      expect(api.latestRepliesCalls(1), 1);
      expect(_bodyOf(1), findsOneWidget);
      expect(find.text('The accepted answer'), findsOneWidget);
      expect(find.text('Solution'), findsOneWidget);
      expect(find.text('Reply number 1'), findsOneWidget);
      expect(find.text('Reply number 2'), findsOneWidget);
      expect(find.text('Reply number 3'), findsNothing);
      expect(find.text('Reply number 4'), findsNothing);
      expect(find.text('+2 more replies'), findsOneWidget);
      expect(find.byType(AuthorAvatarCluster), findsOneWidget);
      expect(
        find.text('3 people in this thread · started by Will'),
        findsOneWidget,
      );

      await tester.tap(find.text('Open topic'));
      await tester.pumpAndSettle();
      expect(opened, [1]);
      // "Open topic" is its own control: the card stayed open.
      expect(_bodyOf(1), findsOneWidget);
    });

    testWidgets('three replies and no solution shows all three', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..latestRepliesByTopic = {1: _peek(solution: false, replies: 3)};
      await _pump(tester, api, [_topic(1)]);
      await _tapCard(tester, 1);
      await tester.pumpAndSettle();
      for (var i = 1; i <= 3; i++) {
        expect(find.text('Reply number $i'), findsOneWidget);
      }
      expect(find.text('Solution'), findsNothing);
      expect(find.textContaining('more repl'), findsNothing);
    });

    testWidgets('opening B collapses A; a double tap on B ends collapsed', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..latestRepliesByTopic = {1: _peek(), 2: _peek()};
      await _pump(tester, api, [_topic(1), _topic(2)]);

      await _tapCard(tester, 1);
      await tester.pumpAndSettle();
      expect(_bodyOf(1), findsOneWidget);

      await _tapCard(tester, 2);
      await tester.pumpAndSettle();
      expect(_bodyOf(1), findsNothing);
      expect(_bodyOf(2), findsOneWidget);

      // Collapse B, then tap it twice within 50 ms: taps are never queued
      // or debounced, so it ends where it started — collapsed.
      await _tapCard(tester, 2);
      await tester.pumpAndSettle();
      expect(_bodyOf(2), findsNothing);
      await _tapCard(tester, 2);
      await tester.pump(const Duration(milliseconds: 20));
      await _tapCard(tester, 2);
      await tester.pumpAndSettle();
      expect(_bodyOf(2), findsNothing);
      // Fetched once, on first open; keepAlive serves every reopen.
      expect(api.latestRepliesCalls(2), 1);
    });

    testWidgets('no replies says so and keeps the Open topic button', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..latestRepliesByTopic = {1: const ForumLatestReplies()};
      await _pump(tester, api, [_topic(1)]);
      await _tapCard(tester, 1);
      await tester.pumpAndSettle();
      expect(find.text('No replies yet'), findsOneWidget);
      expect(find.text('Open topic'), findsOneWidget);
    });

    testWidgets('an error offers Retry, which refetches', (tester) async {
      // A 4xx: forumRetry never auto-retries it, so the count stays exact.
      final api = FakeForumApi()
        ..latestRepliesError = ApiException('gone', statusCode: 404)
        ..latestRepliesByTopic = {1: _peek()};
      final opened = <int>[];
      await _pump(tester, api, [_topic(1)], opened: opened);
      await _tapCard(tester, 1);
      await tester.pumpAndSettle();
      expect(find.text("Couldn't load replies"), findsOneWidget);
      expect(api.latestRepliesCalls(1), 1);

      // The button still works while the replies failed.
      await tester.tap(find.text('Open topic'));
      await tester.pump();
      expect(opened, [1]);

      api.latestRepliesError = null;
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(api.latestRepliesCalls(1), 2);
      expect(find.text("Couldn't load replies"), findsNothing);
      expect(find.text('The accepted answer'), findsOneWidget);
    });

    testWidgets('the failure shows while Riverpod retries on its own', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..latestRepliesError = Exception('boom')
        ..latestRepliesByTopic = {1: _peek()};
      await _pump(tester, api, [_topic(1)], autoRetry: true);
      await _tapCard(tester, 1);
      await tester.pump(); // expanded, skeleton
      await tester.pump(); // the first failure lands
      // Past the skeleton's cross-fade (Durations.short4), before the first
      // automatic retry (Riverpod's default starts at 200 ms) succeeds.
      await tester.pump(const Duration(milliseconds: 210));
      // Not a skeleton through ~40 s of automatic retries.
      expect(find.text("Couldn't load replies"), findsOneWidget);
      expect(find.byKey(const ValueKey('loading')), findsNothing);
      // The next automatic retry succeeds and replaces the failure.
      api.latestRepliesError = null;
      await tester.pumpAndSettle(const Duration(seconds: 1));
      expect(find.text('The accepted answer'), findsOneWidget);
    });

    testWidgets('no starter: no "started by"', (tester) async {
      final api = FakeForumApi()
        ..latestRepliesByTopic = {1: _peek(withStarter: false)};
      await _pump(tester, api, [_topic(1)]);
      await _tapCard(tester, 1);
      await tester.pumpAndSettle();
      expect(find.text('3 people in this thread'), findsOneWidget);
      expect(find.textContaining('started by'), findsNothing);
    });

    testWidgets('unread shows "New replies"; solved shows "Solved"', (
      tester,
    ) async {
      final api = FakeForumApi();
      await _pump(tester, api, [
        _topic(1, isUnread: true),
        _topic(2, isSolved: true),
      ]);
      expect(
        find.descendant(of: _card(1), matching: find.text('New replies')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: _card(2), matching: find.text('Solved')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: _card(2), matching: find.text('New replies')),
        findsNothing,
      );
    });

    testWidgets('the text card reports its expanded state', (tester) async {
      final handle = tester.ensureSemantics();
      final api = FakeForumApi()..latestRepliesByTopic = {1: _peek()};
      await _pump(tester, api, [_topic(1, isUnread: true)]);
      // The header's own text is excluded; its node is the card's button.
      final label = find.text('Topic 1');
      expect(
        tester.getSemantics(label),
        matchesSemantics(
          label: 'Care, Topic 1, 4 replies, 2h, New replies',
          isButton: true,
          hasTapAction: true,
          hasEnabledState: true,
          isEnabled: true,
          hasExpandedState: true,
          isExpanded: false,
        ),
      );
      await _tapCard(tester, 1);
      await tester.pumpAndSettle();
      expect(
        tester.getSemantics(label),
        matchesSemantics(
          label: 'Care, Topic 1, 4 replies, 2h, New replies',
          isButton: true,
          hasTapAction: true,
          hasEnabledState: true,
          isEnabled: true,
          hasExpandedState: true,
          isExpanded: true,
        ),
      );
      // "Open topic" is a control of its own, not folded into the card.
      final open = tester.getSemantics(find.text('Open topic'));
      expect(open.label, 'Open topic');
      expect(open.flagsCollection.isButton, isTrue);
      handle.dispose();
    });

    testWidgets('reduced motion: expand and collapse complete in one pump', (
      tester,
    ) async {
      final api = FakeForumApi()..latestRepliesByTopic = {1: _peek()};
      await _pump(tester, api, [_topic(1)], disableAnimations: true);
      final collapsed = tester.getSize(_card(1)).height;
      // First open loads the replies (skeleton, then content); settle it.
      await _tapCard(tester, 1);
      await tester.pump();
      expect(tester.getSize(_card(1)).height, greaterThan(collapsed));
      await tester.pumpAndSettle();
      final open = tester.getSize(_card(1)).height;

      await _tapCard(tester, 1);
      await tester.pump();
      expect(tester.getSize(_card(1)).height, collapsed);

      // Reopen from the cache: full height on the very next frame.
      await _tapCard(tester, 1);
      await tester.pump();
      expect(tester.getSize(_card(1)).height, open);
      await tester.pumpAndSettle();
      expect(tester.getSize(_card(1)).height, open);
    });

    testWidgets('a tap mid-collapse reverses from where it is', (tester) async {
      final api = FakeForumApi()..latestRepliesByTopic = {1: _peek()};
      await _pump(tester, api, [_topic(1)]);
      await _tapCard(tester, 1);
      await tester.pumpAndSettle();
      final open = tester.getSize(_card(1)).height;
      await _tapCard(tester, 1);
      await tester.pump(); // the frame the collapse starts on
      await tester.pump(const Duration(milliseconds: 100));
      final mid = tester.getSize(_card(1)).height;
      expect(mid, lessThan(open));
      await _tapCard(tester, 1);
      await tester.pumpAndSettle();
      expect(tester.getSize(_card(1)).height, open);
    });

    for (final brightness in Brightness.values) {
      for (final size in const [Size(320, 640), Size(375, 812)]) {
        for (final scale in const [1.0, 2.0]) {
          final name =
              '${size.width.toInt()}x${size.height.toInt()}, x$scale, '
              '${brightness.name}';
          testWidgets('no overflow, expanded and picture: $name', (
            tester,
          ) async {
            final long =
                'What is eating my hosta leaves overnight, and should I worry '
                'about the rest of the bed?';
            final api = FakeForumApi()
              ..latestRepliesByTopic = {
                1: _peek(
                  startedBy: author(
                    username: 'max',
                    displayName: 'Maximiliana-Josephine',
                  ),
                ),
              };
            await _pump(
              tester,
              api,
              [
                _topic(1, isSolved: true, isUnread: true, title: long),
                _topic(2, imageUrl: 'https://example.test/b.jpg', title: long),
              ],
              brightness: brightness,
              size: size,
              textScale: scale,
            );
            await tester.tap(find.text(long).first);
            // Bounded pumps: the picture card's placeholder never settles.
            for (var i = 0; i < 10; i++) {
              await tester.pump(const Duration(milliseconds: 50));
            }
            expect(_bodyOf(1), findsOneWidget);
            expect(tester.takeException(), isNull);
          });
        }
      }
    }

    for (final brightness in Brightness.values) {
      testWidgets('accessibility guidelines, ${brightness.name}', (
        tester,
      ) async {
        final handle = tester.ensureSemantics();
        final api = FakeForumApi()..latestRepliesByTopic = {1: _peek()};
        await _pump(tester, api, [
          _topic(1, isSolved: true),
          _topic(3, isUnread: true),
        ], brightness: brightness);
        await _tapCard(tester, 1);
        await tester.pumpAndSettle();
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
        await expectLater(tester, meetsGuideline(iOSTapTargetGuideline));
        await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
        await expectLater(tester, meetsGuideline(textContrastGuideline));
        handle.dispose();
      });
    }
  });
}
