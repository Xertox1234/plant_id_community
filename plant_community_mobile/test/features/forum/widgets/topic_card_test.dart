import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
import 'package:plant_community_mobile/features/forum/widgets/topic_card.dart';

import '../support/forum_test_support.dart';

void main() {
  Future<void> pump(WidgetTester tester, Widget child) {
    return tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
  }

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
}
