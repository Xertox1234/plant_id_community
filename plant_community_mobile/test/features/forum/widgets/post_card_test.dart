import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
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

  group('PostCard author (todo 317)', () {
    testWidgets('uses AuthorIdentity and wires onAuthorTap', (tester) async {
      var tapped = false;
      await pump(
        tester,
        PostCard(
          post: post(authorOverride: author(username: 'alice')),
          onAuthorTap: () => tapped = true,
        ),
      );

      expect(find.byType(AuthorIdentity), findsOneWidget);
      expect(find.byType(InkWell), findsWidgets);

      await tester.tap(find.byType(InkWell).first);
      await tester.pump();
      expect(tapped, isTrue);
    });

    testWidgets(
      'a deleted author renders no InkWell affordance even with onAuthorTap wired',
      (tester) async {
        var tapped = false;
        await pump(
          tester,
          PostCard(
            post: post(
              authorOverride: author(
                username: ForumAuthor.deletedUsername,
                trustLevel: null,
              ),
            ),
            onAuthorTap: () => tapped = true,
          ),
        );

        expect(find.byType(InkWell), findsNothing);
        expect(tapped, isFalse);
      },
    );
  });

  group('PostCard safety (todo 341 wave 1)', () {
    testWidgets('Report shows only when canReport AND a handler is wired', (
      tester,
    ) async {
      var reported = false;
      await pump(
        tester,
        PostCard(
          post: post(id: 2, canReport: true),
          onReport: () => reported = true,
        ),
      );

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      expect(find.text('Report'), findsOneWidget);
      expect(find.text('Edit'), findsNothing);

      await tester.tap(find.text('Report'));
      await tester.pumpAndSettle();
      expect(reported, isTrue);
    });

    testWidgets(
      'no menu for a post the server says cannot be reported (own post), '
      'even with a handler wired',
      (tester) async {
        await pump(
          tester,
          PostCard(post: post(id: 2, canReport: false), onReport: () {}),
        );

        expect(find.byIcon(Icons.more_vert), findsNothing);
      },
    );

    testWidgets(
      'a blocked author\'s post collapses to a placeholder until "Show anyway"',
      (tester) async {
        await pump(
          tester,
          PostCard(
            post: post(
              id: 2,
              authorOverride: author(username: 'alice'),
              isBlocked: true,
              body: const [ParagraphBlock('hidden words')],
            ),
          ),
        );

        expect(find.text("You've blocked alice."), findsOneWidget);
        expect(find.textContaining('hidden words'), findsNothing);

        await tester.tap(find.text('Show anyway'));
        await tester.pumpAndSettle();

        expect(find.textContaining('hidden words'), findsOneWidget);
        expect(find.text("You've blocked alice."), findsNothing);
      },
    );
  });

  group('PostCard accepted answer + edit history (todo 341 wave 2)', () {
    testWidgets(
      'the accepted answer renders the chip and offers "Unmark answer"',
      (tester) async {
        var toggled = false;
        await pump(
          tester,
          PostCard(
            post: post(id: 2),
            isSolution: true,
            onToggleSolution: () => toggled = true,
          ),
        );

        expect(find.text('Accepted answer'), findsOneWidget);
        await tester.tap(find.byIcon(Icons.more_vert));
        await tester.pumpAndSettle();
        expect(find.text('Unmark answer'), findsOneWidget);
        expect(find.text('Mark as answer'), findsNothing);

        await tester.tap(find.text('Unmark answer'));
        await tester.pumpAndSettle();
        expect(toggled, isTrue);
      },
    );

    testWidgets('a non-answer offers "Mark as answer" and no chip', (
      tester,
    ) async {
      await pump(tester, PostCard(post: post(id: 2), onToggleSolution: () {}));

      expect(find.text('Accepted answer'), findsNothing);
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      expect(find.text('Mark as answer'), findsOneWidget);
    });

    testWidgets('without a solution handler there is no answer menu item', (
      tester,
    ) async {
      await pump(
        tester,
        PostCard(post: post(id: 2, canEdit: true), onEdit: () {}),
      );

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      expect(find.text('Mark as answer'), findsNothing);
    });

    testWidgets('the "edited" stamp opens history when wired', (tester) async {
      var opened = false;
      await pump(
        tester,
        PostCard(
          post: post(id: 2, editedAt: DateTime(2026, 1, 2)),
          onShowHistory: () => opened = true,
        ),
      );

      expect(find.byTooltip('View edit history'), findsOneWidget);
      await tester.tap(find.text('edited'));
      await tester.pump();
      expect(opened, isTrue);
    });

    testWidgets('the "edited" stamp is a static label when not wired', (
      tester,
    ) async {
      await pump(
        tester,
        PostCard(post: post(id: 2, editedAt: DateTime(2026, 1, 2))),
      );

      expect(find.text('edited'), findsOneWidget);
      expect(find.byTooltip('View edit history'), findsNothing);
      expect(find.byType(TextButton), findsNothing);
    });

    testWidgets('an unedited post shows no stamp at all', (tester) async {
      await pump(tester, PostCard(post: post(id: 2), onShowHistory: () {}));

      expect(find.text('edited'), findsNothing);
    });
  });
}
