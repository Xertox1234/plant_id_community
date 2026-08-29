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
        TopicCard(topic: topic(authorOverride: author(username: 'alice'))),
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
  });
}
