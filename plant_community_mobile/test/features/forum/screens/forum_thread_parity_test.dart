import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_thread_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_edit_history_sheet.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

Widget _wrap(FakeForumApi api, {bool loggedIn = true}) => ProviderScope(
  overrides: [
    forumApiProvider.overrideWithValue(api),
    authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: loggedIn)),
  ],
  child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
);

/// The only post menu on screen — fixtures below give exactly one post a
/// capability, so this is unambiguous.
Finder _menu() => find.byIcon(Icons.more_vert);

void main() {
  group('Thread bookmark toggle (todo 341)', () {
    testWidgets('reflects isBookmarked and flips on tap', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(items: [post(id: 1)]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.byTooltip('Bookmark'), findsOneWidget);
      await tester.tap(find.byIcon(Icons.bookmark_border));
      await tester.pumpAndSettle();

      expect(api.bookmarkCalls, [10]);
      expect(find.byIcon(Icons.bookmark), findsOneWidget);
      expect(find.byTooltip('Remove bookmark'), findsOneWidget);
    });

    testWidgets('is hidden for an anonymous viewer', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(items: [post(id: 1)]);

      await tester.pumpWidget(_wrap(api, loggedIn: false));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.bookmark_border), findsNothing);
    });

    testWidgets('a rate-limited toggle reverts the icon and reads as "too '
        'fast"', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(items: [post(id: 1)])
        ..failBookmarkWith = ApiException('slow down', statusCode: 429);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.bookmark_border));
      await tester.pumpAndSettle();

      expect(find.text('Too fast — try again in a minute'), findsOneWidget);
      expect(find.byIcon(Icons.bookmark_border), findsOneWidget);
      expect(find.byIcon(Icons.bookmark), findsNothing);
    });
  });

  group('Thread report post (todo 341)', () {
    testWidgets('Report opens the sheet and submitting calls the API with a '
        'key', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(
          items: [post(id: 1), post(id: 2, canReport: true)],
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.tap(_menu());
      await tester.pumpAndSettle();
      await tester.tap(find.text('Report'));
      await tester.pumpAndSettle();

      expect(find.text('Report post'), findsOneWidget);
      final submit = find.widgetWithText(FilledButton, 'Report');
      expect(tester.widget<FilledButton>(submit).onPressed, isNull);

      await tester.tap(find.widgetWithText(ChoiceChip, 'Spam'));
      await tester.pumpAndSettle();
      await tester.tap(submit);
      await tester.pumpAndSettle();

      expect(api.reportPostCalls, [
        {'postId': 2, 'reason': 'spam', 'detail': null},
      ]);
      expect(api.reportPostKeys.single, isNotEmpty);
      expect(find.text('Reported'), findsOneWidget);
      expect(find.text('Report post'), findsNothing);
    });

    testWidgets('a 400 (own post / already reported) shows the server '
        'message verbatim', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(items: [post(id: 1), post(id: 2, canReport: true)])
        ..failReportPostWith = ApiException(
          'You cannot report your own post.',
          statusCode: 400,
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.tap(_menu());
      await tester.pumpAndSettle();
      await tester.tap(find.text('Report'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(ChoiceChip, 'Abuse'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Report'));
      await tester.pumpAndSettle();

      expect(find.text('You cannot report your own post.'), findsOneWidget);
      expect(find.text('Reported'), findsNothing);
    });

    testWidgets('Report is not offered to an anonymous viewer', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(
          items: [post(id: 1), post(id: 2, canReport: true)],
        );

      await tester.pumpWidget(_wrap(api, loggedIn: false));
      await tester.pumpAndSettle();

      expect(_menu(), findsNothing);
    });
  });

  group('Thread accepted answer (todo 341)', () {
    testWidgets(
      'the topic author marks a reply as the answer, sees the chip + banner, '
      'then unmarks it',
      (tester) async {
        final api = FakeForumApi()
          ..topicDetail = topicDetail(id: 10, canMarkSolution: true)
          ..posts = CursorPage(items: [post(id: 1), post(id: 2)]);

        await tester.pumpWidget(_wrap(api));
        await tester.pumpAndSettle();

        // Only the reply gets a menu — the opening post is never offered.
        expect(_menu(), findsOneWidget);
        expect(find.text('Jump to answer'), findsNothing);

        await tester.tap(_menu());
        await tester.pumpAndSettle();
        await tester.tap(find.text('Mark as answer'));
        await tester.pumpAndSettle();

        expect(api.markSolutionCalls, [
          {'topicId': 10, 'postId': 2},
        ]);
        expect(api.markSolutionKeys.single, isNotEmpty);
        expect(find.text('Accepted answer'), findsOneWidget);
        expect(find.text('Jump to answer'), findsOneWidget);

        await tester.tap(_menu());
        await tester.pumpAndSettle();
        expect(find.text('Unmark answer'), findsOneWidget);
        await tester.tap(find.text('Unmark answer'));
        await tester.pumpAndSettle();

        expect(api.clearSolutionCalls, [10]);
        expect(find.text('Accepted answer'), findsNothing);
        expect(find.text('Jump to answer'), findsNothing);
      },
    );

    testWidgets('no mark affordance when the server says the viewer may not', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, canMarkSolution: false)
        ..posts = CursorPage(items: [post(id: 1), post(id: 2)]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(_menu(), findsNothing);
    });

    testWidgets('a 403 reads as the who-may-accept notice and the badge stays '
        'where it was', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, canMarkSolution: true)
        ..posts = CursorPage(items: [post(id: 1), post(id: 2)])
        ..failSolutionWith = ApiException(
          'You do not have permission to perform this action.',
          statusCode: 403,
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.tap(_menu());
      await tester.pumpAndSettle();
      await tester.tap(find.text('Mark as answer'));
      await tester.pumpAndSettle();

      expect(
        find.text(
          "Only the topic's author or a moderator can accept an answer.",
        ),
        findsOneWidget,
      );
      expect(find.text('Accepted answer'), findsNothing);
    });

    testWidgets('"Jump to answer" scrolls an off-screen answer into view', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, solvedPostId: 14)
        ..posts = CursorPage(
          items: [
            for (var i = 1; i <= 14; i++)
              post(id: i, body: [ParagraphBlock('Reply number $i')]),
          ],
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      // Lazy list: the answer (last of 14) is not built on first frame.
      expect(find.text('Accepted answer'), findsNothing);

      await tester.tap(find.text('Jump to answer'));
      await tester.pumpAndSettle();

      expect(find.text('Accepted answer'), findsOneWidget);
      expect(find.text('Reply number 14'), findsOneWidget);
    });

    testWidgets('"Jump to answer" pulls the next cursor page when the answer '
        'is not loaded yet', (tester) async {
      final page1 = CursorPage(
        items: [post(id: 1), post(id: 2)],
        next: 'https://api/forum/topics/10/posts/?cursor=p2',
      );
      final page2 = CursorPage(
        items: [
          post(id: 3, body: const [ParagraphBlock('The answer')]),
        ],
      );
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, solvedPostId: 3)
        ..postPages = [page1, page2];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      expect(find.text('The answer'), findsNothing);

      await tester.tap(find.text('Jump to answer'));
      await tester.pumpAndSettle();

      expect(api.fetchPostsCalls, [null, page1.next]);
      expect(find.text('The answer'), findsOneWidget);
      expect(find.text('Accepted answer'), findsOneWidget);
    });
  });

  group('Thread edit history (todo 341)', () {
    testWidgets('tapping "edited" lists revisions and opens one\'s body', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(
          items: [
            post(id: 1),
            post(id: 2, editedAt: DateTime(2026, 1, 2)),
          ],
        )
        ..revisions = [revision(id: 7, username: 'alice')]
        ..revisionDetails = {
          7: revisionDetail(
            id: 7,
            body: const [ParagraphBlock('Older wording')],
          ),
        };

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.tap(find.text('edited'));
      await tester.pumpAndSettle();

      expect(find.text('Edit history'), findsOneWidget);
      expect(api.fetchRevisionsCalls, [2]);
      final row = find.descendant(
        of: find.byType(ForumEditHistorySheet),
        matching: find.text('alice'),
      );
      expect(row, findsOneWidget);

      await tester.tap(row);
      await tester.pumpAndSettle();

      expect(api.fetchRevisionCalls, [7]);
      expect(find.textContaining('Older wording'), findsOneWidget);
      expect(find.textContaining('Revision from'), findsOneWidget);
    });

    testWidgets('a 403 renders the moderator-only refusal, not a failure', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(
          items: [
            post(id: 1),
            post(id: 2, editedAt: DateTime(2026, 1, 2)),
          ],
        )
        ..failRevisionsWith = ApiException(
          'You do not have permission to perform this action.',
          statusCode: 403,
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.tap(find.text('edited'));
      await tester.pumpAndSettle();

      expect(find.textContaining('only visible to moderators'), findsOneWidget);
      expect(find.textContaining("Couldn't load"), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('the stamp stays static for an anonymous viewer', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(
          items: [
            post(id: 1),
            post(id: 2, editedAt: DateTime(2026, 1, 2)),
          ],
        );

      await tester.pumpWidget(_wrap(api, loggedIn: false));
      await tester.pumpAndSettle();

      expect(find.text('edited'), findsOneWidget);
      expect(find.byTooltip('View edit history'), findsNothing);
    });
  });
}
