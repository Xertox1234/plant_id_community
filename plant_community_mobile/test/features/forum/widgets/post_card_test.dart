import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/widgets/post_card.dart';

import '../support/forum_test_support.dart';

void main() {
  Future<void> pump(WidgetTester tester, Widget child) {
    return tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
  }

  group('PostCard post menu (todo 292 AC1)', () {
    testWidgets(
      'shows Edit and Delete when the post allows both and callbacks are wired',
      (tester) async {
        var edited = false;
        var deleted = false;
        await pump(
          tester,
          PostCard(
            post: post(canEdit: true, canDelete: true),
            onEdit: () => edited = true,
            onDelete: () => deleted = true,
          ),
        );

        expect(find.byIcon(Icons.more_vert), findsOneWidget);
        await tester.tap(find.byIcon(Icons.more_vert));
        await tester.pumpAndSettle();
        expect(find.text('Edit'), findsOneWidget);
        expect(find.text('Delete'), findsOneWidget);

        await tester.tap(find.text('Edit'));
        await tester.pumpAndSettle();
        expect(edited, isTrue);
        expect(deleted, isFalse);
      },
    );

    testWidgets('shows no menu at all when the post allows neither', (
      tester,
    ) async {
      await pump(
        tester,
        PostCard(
          post: post(canEdit: false, canDelete: false),
          onEdit: () {},
          onDelete: () {},
        ),
      );

      expect(find.byIcon(Icons.more_vert), findsNothing);
    });

    testWidgets(
      'shows only Edit when canDelete is false, even with an onDelete callback wired',
      (tester) async {
        await pump(
          tester,
          PostCard(
            post: post(canEdit: true, canDelete: false),
            onEdit: () {},
            onDelete: () {},
          ),
        );

        await tester.tap(find.byIcon(Icons.more_vert));
        await tester.pumpAndSettle();
        expect(find.text('Edit'), findsOneWidget);
        expect(find.text('Delete'), findsNothing);
      },
    );

    testWidgets(
      'shows no menu when the post allows both but the screen wired no callbacks '
      '(e.g. an anonymous viewer)',
      (tester) async {
        await pump(
          tester,
          PostCard(post: post(canEdit: true, canDelete: true)),
        );

        expect(find.byIcon(Icons.more_vert), findsNothing);
      },
    );
  });
}
