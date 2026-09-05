import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/post_card.dart';

import '../support/forum_test_support.dart';

void main() {
  Future<void> pump(WidgetTester tester, Widget child) {
    return tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
  }

  group('PostCard Quote action (todo 341 wave 3)', () {
    testWidgets('a visible 48dp Quote button when the screen wires it', (
      tester,
    ) async {
      var quoted = 0;
      await pump(tester, PostCard(post: post(), onQuote: () => quoted++));

      final button = find.byTooltip('Quote');
      expect(button, findsOneWidget);
      final size = tester.getSize(find.byType(IconButton));
      expect(size.width, greaterThanOrEqualTo(48));
      expect(size.height, greaterThanOrEqualTo(48));
      // Not a menu entry: a post with no other capability still offers it.
      expect(find.byIcon(Icons.more_vert), findsNothing);

      await tester.tap(button);
      await tester.pump();
      expect(quoted, 1);
    });

    testWidgets('absent when not wired (anonymous / locked topic)', (
      tester,
    ) async {
      await pump(tester, PostCard(post: post()));
      expect(find.byTooltip('Quote'), findsNothing);
    });
  });

  group('PostCard post_quote in the current topic (todo 342)', () {
    final body = [
      PostQuoteBlock(
        text: 'Water it less.',
        postId: 1,
        available: true,
        topicId: 10,
        author: author(username: 'bob', displayName: 'Bob B'),
      ),
    ];

    testWidgets('currentTopicId reaches the body: a same-topic quote has no '
        '"in topic" link, a foreign one keeps it', (tester) async {
      await pump(tester, PostCard(post: post(id: 2, body: body)));
      expect(find.text('in topic'), findsOneWidget);

      await pump(
        tester,
        PostCard(post: post(id: 2, body: body), currentTopicId: 10),
      );
      expect(find.text('Water it less.'), findsOneWidget);
      expect(find.text('Bob B'), findsOneWidget);
      expect(find.text('in topic'), findsNothing);
    });
  });
}
