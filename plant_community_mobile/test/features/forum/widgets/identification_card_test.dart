import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/identification_card.dart';

import '../support/forum_test_support.dart';

Future<void> _pump(WidgetTester tester, Widget child) {
  return tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  );
}

void main() {
  group('IdentificationCard (todo 341 wave 3)', () {
    testWidgets('lists every candidate with its confidence, labelled as a '
        'suggestion', (tester) async {
      await _pump(tester, IdentificationCard(identification: identification()));

      expect(find.text('What the app suggested'), findsOneWidget);
      expect(find.text('Swiss cheese plant'), findsOneWidget);
      expect(find.text('Monstera deliciosa'), findsOneWidget);
      expect(find.text('92%'), findsOneWidget);
      expect(find.text('Monkey mask'), findsOneWidget);
      expect(find.text('5%'), findsOneWidget);
      expect(find.textContaining('(plant.id)'), findsOneWidget);
      expect(
        find.textContaining('not a confirmed identification'),
        findsOneWidget,
      );
      expect(find.text('See the accepted answer'), findsNothing);
      expect(find.byType(CachedNetworkImage), findsNothing);
    });

    testWidgets('points at the accepted answer once the topic is solved', (
      tester,
    ) async {
      var jumped = 0;
      await _pump(
        tester,
        IdentificationCard(
          identification: identification(),
          solvedPostId: 4,
          onJumpToAnswer: () async => jumped++,
        ),
      );

      await tester.tap(find.text('See the accepted answer'));
      await tester.pump();
      expect(jumped, 1);
    });

    testWidgets('no candidates is a real state, not an error', (tester) async {
      await _pump(
        tester,
        IdentificationCard(
          identification: identification(candidates: const [], provider: ''),
        ),
      );

      expect(find.text('No suggestions were recorded.'), findsOneWidget);
      expect(find.textContaining('('), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('renders the kept photo with the author\'s alt text', (
      tester,
    ) async {
      // Bounded pumps only: a CachedNetworkImage placeholder never settles
      // in the blocked-network harness.
      await _pump(
        tester,
        IdentificationCard(
          identification: identification(
            image: const ForumImageBlock(
              id: 1,
              url: 'https://example.com/leaf.jpg',
              alt: 'My monstera leaf',
            ),
          ),
        ),
      );
      await tester.pump();

      expect(find.byType(CachedNetworkImage), findsOneWidget);
      // The image's own Semantics wrapper (non-container, so it merges into
      // the card's node — assert on the widget, not the semantics tree).
      final wrapper = tester.widget<Semantics>(
        find
            .ancestor(
              of: find.byType(CachedNetworkImage),
              matching: find.byType(Semantics),
            )
            .first,
      );
      expect(wrapper.properties.label, 'My monstera leaf');
      expect(wrapper.properties.image, isTrue);
    });
  });
}
