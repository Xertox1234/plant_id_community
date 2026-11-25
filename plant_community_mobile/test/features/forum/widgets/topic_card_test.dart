import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/forum_format.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
import 'package:plant_community_mobile/features/forum/widgets/topic_card.dart';

import '../support/forum_test_support.dart';

void main() {
  Future<void> pump(WidgetTester tester, Widget child) {
    return tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
  }

  group('TopicRow tags and pin', () {
    testWidgets('shows at most three of a topic\'s tags', (tester) async {
      await pump(
        tester,
        TopicRow(topic: topic(tags: ['hoya', 'aroid', 'tree', 'fern'])),
      );

      expect(find.text('#hoya'), findsOneWidget);
      expect(find.text('#tree'), findsOneWidget);
      expect(find.text('#fern'), findsNothing);
    });

    testWidgets('only a pinned row sits on a wash', (tester) async {
      final wash = find.descendant(
        of: find.byType(TopicRow),
        matching: find.byWidgetPredicate(
          (w) => w is ColoredBox && w.color.a > 0,
        ),
      );
      await pump(tester, TopicRow(topic: topic()));
      expect(wash, findsNothing);

      await pump(tester, TopicRow(topic: topic(isPinned: true)));
      expect(wash, findsOneWidget);
      expect(find.text('Pinned'), findsOneWidget);
    });
  });

  group('TopicCard author (todo 317)', () {
    testWidgets('renders an AuthorIdentity for the topic author', (
      tester,
    ) async {
      await pump(
        tester,
        TopicCard(
          topic: topic(authorOverride: author(username: 'alice')),
        ),
      );

      expect(find.byType(AuthorIdentity), findsOneWidget);
      expect(find.text('alice'), findsOneWidget);
    });

    testWidgets(
      'tapping the author fires onAuthorTap, not the card-level onTap',
      (tester) async {
        var authorTapped = false;
        var cardTapped = false;
        await pump(
          tester,
          TopicCard(
            topic: topic(authorOverride: author(username: 'alice')),
            onTap: () => cardTapped = true,
            onAuthorTap: () => authorTapped = true,
          ),
        );

        await tester.tap(find.text('alice'));
        await tester.pump();

        expect(authorTapped, isTrue);
        expect(cardTapped, isFalse);
      },
    );

    testWidgets(
      'a deleted author renders no author-level InkWell, but the card '
      'itself is still tappable',
      (tester) async {
        var cardTapped = false;
        await pump(
          tester,
          TopicCard(
            topic: topic(
              authorOverride: author(
                username: ForumAuthor.deletedUsername,
                trustLevel: null,
              ),
            ),
            onTap: () => cardTapped = true,
            onAuthorTap: () {},
          ),
        );

        // Exactly one InkWell — the card's own — since the author is deleted.
        expect(find.byType(InkWell), findsOneWidget);

        await tester.tap(find.byType(InkWell));
        await tester.pump();
        expect(cardTapped, isTrue);
      },
    );

    testWidgets(
      'does not overflow at a 375pt-wide viewport with a long author name '
      'and real stats (final review, todo 317)',
      (tester) async {
        // 375x800 @ 1.0 mirrors an iPhone SE/mini logical viewport — Flutter's
        // default test surface (800x600) never exercises this width and
        // would pass even with the pre-fix regression present.
        final originalPhysicalSize = tester.view.physicalSize;
        final originalDevicePixelRatio = tester.view.devicePixelRatio;
        tester.view.physicalSize = const Size(375, 800);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.physicalSize = originalPhysicalSize;
          tester.view.devicePixelRatio = originalDevicePixelRatio;
        });

        await pump(
          tester,
          TopicCard(
            topic: ForumTopicListItem(
              id: 10,
              title: 'A sample topic title',
              slug: 'sample-topic',
              author: author(
                username: 'alexandra',
                displayName: 'Alexandra Greenthumbington',
              ),
              isPinned: false,
              isClosed: false,
              locked: false,
              replyCount: 128,
              viewCount: 45231,
              // Well beyond forumRelativeTime's 7-day cutoff, so it renders
              // as a full "YYYY-MM-DD" date — the widest form of the
              // trailing time label — rather than "just now"/"Nd".
              lastPostAt: DateTime(2020, 1, 2),
              lastPostAuthor: author(),
              isUnread: false,
            ),
          ),
        );

        expect(tester.takeException(), isNull);
      },
    );
  });

  group('topic row layout', () {
    ForumTopicListItem busy(String title) => ForumTopicListItem(
      id: 11,
      title: title,
      slug: 'busy',
      author: author(
        username: 'alexandra',
        displayName: 'Alexandra Greenthumbington',
      ),
      isPinned: true,
      isClosed: true,
      locked: false,
      replyCount: 128,
      viewCount: 45231,
      lastPostAt: DateTime(2020, 1, 2),
      lastPostAuthor: author(),
      isUnread: true,
      isSolved: true,
    );

    testWidgets('status never moves the title: a solved, pinned, locked, '
        'unread topic starts on the same edge as a plain one', (tester) async {
      final semantics = tester.ensureSemantics();
      await pump(
        tester,
        Column(
          children: [
            TopicRow(topic: topic(title: 'Plain topic')),
            TopicRow(topic: busy('Busy topic')),
          ],
        ),
      );

      expect(
        tester.getTopLeft(find.text('Busy topic')).dx,
        tester.getTopLeft(find.text('Plain topic')).dx,
      );
      expect(find.text('Solved'), findsOneWidget);
      expect(find.text('Pinned'), findsOneWidget);
      expect(find.text('Locked'), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp('Unread')), findsWidgets);
      semantics.dispose();
    });

    for (final width in [320.0, 375.0]) {
      for (final scale in [1.0, 2.0]) {
        testWidgets('every status at once fits ${width.toInt()}pt wide at '
            'text scale $scale', (tester) async {
          tester.view.physicalSize = Size(width, 800);
          tester.view.devicePixelRatio = 1.0;
          addTearDown(tester.view.reset);

          await tester.pumpWidget(
            MaterialApp(
              home: MediaQuery(
                data: MediaQueryData(
                  size: Size(width, 800),
                  textScaler: TextScaler.linear(scale),
                ),
                child: Scaffold(
                  body: SingleChildScrollView(
                    child: TopicRow(
                      topic: busy(
                        'Found this trailing thing at an estate sale — hoya '
                        'or dischidia?',
                      ),
                    ),
                  ),
                ),
              ),
            ),
          );

          expect(tester.takeException(), isNull);
        });
      }
    }
  });

  group('forumListTime', () {
    final now = DateTime(2026, 11, 17, 12);

    test('stays relative within a week', () {
      expect(forumListTime(DateTime(2026, 11, 15, 12), now: now), '2d');
    });

    test('is a short date later in the same year', () {
      expect(forumListTime(DateTime(2026, 8, 16), now: now), 'Aug 16');
    });

    test('names the year when it is not this one', () {
      expect(forumListTime(DateTime(2025, 8, 16), now: now), 'Aug 16, 2025');
    });

    test('is empty for no date', () {
      expect(forumListTime(null, now: now), '');
    });
  });
}
