import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_composer_screen.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_thread_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/identification_card.dart';
import 'package:plant_community_mobile/features/forum/widgets/poll_card.dart';
import 'package:plant_community_mobile/features/forum/widgets/post_card.dart';
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

/// The thread behind a real router so `context.pushNamed('forumCompose')`
/// (the Quote action) lands on the composer.
Widget _routed(FakeForumApi api) {
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (_, _) => const ForumThreadScreen(topicId: 10),
      ),
      GoRoute(
        path: '/forum/compose',
        name: 'forumCompose',
        builder: (_, state) =>
            ForumComposerScreen(args: state.extra as ForumComposeArgs),
      ),
    ],
  );
  return ProviderScope(
    overrides: [
      forumApiProvider.overrideWithValue(api),
      authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: true)),
    ],
    child: MaterialApp.router(routerConfig: router),
  );
}

ForumPoll _threadPoll() => poll(
  totalVotes: 1,
  options: [
    pollOption(id: 1, text: 'Weekly', voteCount: 0),
    pollOption(id: 2, text: 'Fortnightly', voteCount: 1),
    pollOption(id: 3, text: 'When dry', voteCount: 0),
  ],
);

void main() {
  group('Thread poll (todo 341 wave 3)', () {
    testWidgets('renders under the opening post and a vote goes through the '
        'provider to the server', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, poll: _threadPoll())
        ..posts = CursorPage(items: [post(id: 1), post(id: 2)]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.byType(PollCard), findsOneWidget);
      expect(find.text('How often do you water?'), findsOneWidget);
      // Under the opening post: the card sits below the first PostCard.
      expect(
        tester.getTopLeft(find.byType(PollCard)).dy,
        greaterThan(tester.getBottomLeft(find.byType(PostCard).first).dy),
      );
      expect(find.text('1 vote'), findsOneWidget);

      await tester.tap(find.text('Weekly'));
      await tester.pumpAndSettle();

      expect(api.votePollCalls, [
        [1],
      ]);
      expect(find.text('your vote'), findsOneWidget);
      expect(find.text('2 votes · your vote is final'), findsOneWidget);
      expect(find.text('1 (50%)'), findsNWidgets(2));
    });

    testWidgets('a 409 shows the server\'s own sentence and refetches the '
        'detail to resync the ballot', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, poll: _threadPoll())
        ..posts = CursorPage(items: [post(id: 1)])
        ..failVoteWith = ApiException(
          'You have already voted for option 2 in this poll.',
          statusCode: 409,
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      expect(api.fetchTopicDetailCalls, 1);

      await tester.tap(find.text('Weekly'));
      await tester.pumpAndSettle();

      expect(
        find.text('You have already voted for option 2 in this poll.'),
        findsOneWidget,
      );
      // Never the idempotency-twin wording.
      expect(find.textContaining('already in progress'), findsNothing);
      expect(api.fetchTopicDetailCalls, 2);
      expect(find.byType(OutlinedButton), findsNWidgets(3));
    });

    testWidgets('a rate-limited vote reads as "too fast" and the ballot '
        'comes back', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, poll: _threadPoll())
        ..posts = CursorPage(items: [post(id: 1)])
        ..failVoteWith = ApiException('slow down', statusCode: 429);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Weekly'));
      await tester.pumpAndSettle();

      expect(find.text('Too fast — try again in a minute'), findsOneWidget);
      expect(
        tester
            .widget<OutlinedButton>(
              find.widgetWithText(OutlinedButton, 'Weekly'),
            )
            .onPressed,
        isNotNull,
      );
    });

    testWidgets('an anonymous viewer sees totals but cannot vote', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, poll: _threadPoll())
        ..posts = CursorPage(items: [post(id: 1)]);

      await tester.pumpWidget(_wrap(api, loggedIn: false));
      await tester.pumpAndSettle();

      expect(find.text('1 vote · sign in to vote'), findsOneWidget);
      for (final button in tester.widgetList<OutlinedButton>(
        find.byType(OutlinedButton),
      )) {
        expect(button.onPressed, isNull);
      }
    });
  });

  group('Thread identification snapshot (todo 341 wave 3)', () {
    testWidgets('renders under the opening post and links to the accepted '
        'answer', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(
          id: 10,
          identification: identification(),
          solvedPostId: 2,
        )
        ..posts = CursorPage(items: [post(id: 1), post(id: 2)]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.byType(IdentificationCard), findsOneWidget);
      expect(find.text('Swiss cheese plant'), findsOneWidget);
      expect(find.text('92%'), findsOneWidget);
      expect(
        tester.getTopLeft(find.byType(IdentificationCard)).dy,
        greaterThan(tester.getBottomLeft(find.byType(PostCard).first).dy),
      );

      await tester.tap(find.text('See the accepted answer'));
      await tester.pumpAndSettle();
      expect(find.text('Accepted answer'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('no card for the common snapshot-less, poll-less topic', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(items: [post(id: 1)]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.byType(IdentificationCard), findsNothing);
      expect(find.byType(PollCard), findsNothing);
    });
  });

  group('Thread Quote action (todo 342)', () {
    testWidgets('opens the composer pre-filled with the post\'s excerpt and '
        'author, sent as a post_quote block keyed to the post ahead of the '
        'paragraph', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(
          items: [
            post(id: 1),
            post(
              id: 2,
              authorOverride: author(username: 'bob', displayName: 'Bob B'),
              body: const [ParagraphBlock('Water it <em>less</em>.')],
            ),
          ],
        );

      await tester.pumpWidget(_routed(api));
      await tester.pumpAndSettle();

      expect(find.byTooltip('Quote'), findsNWidgets(2));
      await tester.tap(find.byTooltip('Quote').last);
      await tester.pumpAndSettle();

      expect(find.byType(ForumComposerScreen), findsOneWidget);
      expect(find.text('Water it less.'), findsOneWidget);
      expect(find.text('— Bob B'), findsOneWidget);
      // No "wrote:" line anywhere — the server carries the attribution.
      expect(find.textContaining('wrote'), findsNothing);

      await tester.enterText(find.byType(TextField), 'Noted, thanks.');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(api.createReplyBodies.single, [
        {
          'type': 'post_quote',
          'value': {'post': 2, 'text': 'Water it less.'},
        },
        {'type': 'paragraph', 'value': 'Noted, thanks.'},
      ]);
      expect(find.byType(ForumThreadScreen), findsOneWidget);
    });

    testWidgets('is hidden on a locked topic and for an anonymous viewer', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, locked: true)
        ..posts = CursorPage(items: [post(id: 1)]);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      expect(find.byTooltip('Quote'), findsNothing);

      api.topicDetail = topicDetail(id: 10);
      await tester.pumpWidget(_wrap(api, loggedIn: false));
      await tester.pumpAndSettle();
      expect(find.byTooltip('Quote'), findsNothing);
    });

    testWidgets('an image-only post has nothing to quote', (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(
          items: [
            post(id: 1),
            post(
              id: 2,
              body: const [ForumImageBlock(id: 1, url: '', alt: '')],
            ),
          ],
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      await tester.tap(find.byTooltip('Quote').last);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('Nothing to quote in that post.'), findsOneWidget);
      expect(find.byType(ForumThreadScreen), findsOneWidget);
    });
  });

  group('Thread post_quote rendering (todo 342)', () {
    PostQuoteBlock quoteOf({required int topicId}) => PostQuoteBlock(
      text: 'Water it less.',
      postId: 1,
      available: true,
      topicId: topicId,
      author: author(username: 'bob', displayName: 'Bob B'),
    );

    testWidgets('the thread hands its topic id down: a quote of a post in '
        'THIS topic has no "in topic" link, one from elsewhere keeps it', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..posts = CursorPage(
          items: [
            post(id: 1),
            post(id: 2, body: [quoteOf(topicId: 10)]),
            post(id: 3, body: [quoteOf(topicId: 7)]),
          ],
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('Water it less.'), findsNWidgets(2));
      expect(find.text('Bob B'), findsNWidgets(2));
      expect(find.text('in topic'), findsOneWidget);
    });
  });
}
