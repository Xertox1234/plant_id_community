import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
import 'package:plant_community_mobile/features/forum/widgets/trust_badge.dart';

import '../support/forum_test_support.dart';

void main() {
  Future<void> pump(WidgetTester tester, Widget child) {
    return tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
  }

  group('AuthorIdentity', () {
    testWidgets('renders the name and trust badge', (tester) async {
      await pump(
        tester,
        AuthorIdentity(author: author(username: 'alice', trustLevel: 3)),
      );

      expect(find.text('alice'), findsOneWidget);
      expect(find.byType(TrustBadge), findsOneWidget);
    });

    testWidgets(
      'wraps in a tappable InkWell and fires onTap for a real author',
      (tester) async {
        var tapped = false;
        await pump(
          tester,
          AuthorIdentity(
            author: author(username: 'alice'),
            onTap: () => tapped = true,
          ),
        );

        expect(find.byType(InkWell), findsOneWidget);
        await tester.tap(find.byType(InkWell));
        await tester.pump();
        expect(tapped, isTrue);
      },
    );

    testWidgets('renders with no InkWell at all when onTap is null', (
      tester,
    ) async {
      await pump(tester, AuthorIdentity(author: author(username: 'alice')));

      expect(find.byType(InkWell), findsNothing);
    });

    testWidgets(
      'renders with no InkWell at all for a deleted author, even with onTap set',
      (tester) async {
        var tapped = false;
        await pump(
          tester,
          AuthorIdentity(
            author: author(
              username: ForumAuthor.deletedUsername,
              trustLevel: null,
            ),
            onTap: () => tapped = true,
          ),
        );

        expect(find.byType(InkWell), findsNothing);
        expect(tapped, isFalse);
      },
    );
  });
}
