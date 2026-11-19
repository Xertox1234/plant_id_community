// Poll creation in the new-topic composer: the "Add poll" button, the
// inline poll form, what gates Post, and the exact `poll` payload sent.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_composer_screen.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_topics_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_composer_controller.dart';
import 'package:plant_community_mobile/features/forum/widgets/poll_draft_form.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

const _pollTopic = ForumComposeArgs.topic(boardSlug: 'general', canPoll: true);

Future<void> _pump(
  WidgetTester tester,
  FakeForumApi api, {
  ForumComposeArgs args = _pollTopic,
  Future<DateTime?> Function(BuildContext context)? pickCloseTime,
}) async {
  // Tall enough that the whole form is built: the composer is a lazy list.
  tester.view.physicalSize = const Size(1080, 4800);
  tester.view.devicePixelRatio = 2;
  addTearDown(tester.view.reset);
  final screen = pickCloseTime == null
      ? ForumComposerScreen(args: args)
      : ForumComposerScreen(args: args, pickPollCloseTime: pickCloseTime);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        forumApiProvider.overrideWithValue(api),
        authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: true)),
      ],
      child: MaterialApp(
        home: Navigator(
          onGenerateRoute: (_) => MaterialPageRoute<void>(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () => Navigator.of(
                  context,
                ).push(MaterialPageRoute<Object?>(builder: (_) => screen)),
                child: const Text('open'),
              ),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

Finder _field(String label) => find.widgetWithText(TextField, label);

Future<void> _fillTopic(WidgetTester tester) async {
  await tester.enterText(_field('Title'), 'Which pot for my monstera?');
  await tester.enterText(_field('Body'), 'It has three roots.');
  await tester.pump();
}

Future<void> _openPoll(WidgetTester tester) async {
  await tester.tap(find.widgetWithText(OutlinedButton, 'Add poll'));
  await tester.pump();
}

bool _postEnabled(WidgetTester tester) => tester
    .widget<FilledButton>(find.widgetWithText(FilledButton, 'Post'))
    .enabled;

void main() {
  group('ForumPollDraft', () {
    test('sends the trimmed question and only the filled options', () {
      const draft = ForumPollDraft(
        question: '  Which pot?  ',
        options: ['Terracotta', '   ', ' Plastic  nursery pot '],
      );
      expect(draft.isValid, isTrue);
      expect(draft.toJson(), {
        'question': 'Which pot?',
        'options': ['Terracotta', 'Plastic nursery pot'],
      });
    });

    test('needs a question and two filled options', () {
      expect(const ForumPollDraft().isValid, isFalse);
      expect(
        const ForumPollDraft(question: 'Q', options: ['A', '']).isValid,
        isFalse,
      );
      expect(
        const ForumPollDraft(question: ' ', options: ['A', 'B']).isValid,
        isFalse,
      );
    });

    test('options that differ only by case or spacing are duplicates', () {
      const draft = ForumPollDraft(
        question: 'Q',
        options: ['Terracotta', ' terracotta '],
      );
      expect(draft.hasDuplicateOptions, isTrue);
      expect(draft.isValid, isFalse);
    });

    test('max_choices is clamped to the filled options and sent above 1', () {
      const draft = ForumPollDraft(
        question: 'Q',
        options: ['A', 'B', ''],
        maxChoices: 3,
      );
      expect(draft.toJson()['max_choices'], 2);
    });

    test('closes_at is sent as a UTC instant', () {
      final local = DateTime(2030, 1, 2, 18);
      final draft = ForumPollDraft(
        question: 'Q',
        options: const ['A', 'B'],
        closesAt: local,
      );
      final sent = draft.toJson()['closes_at'] as String;
      expect(sent, endsWith('Z'));
      expect(DateTime.parse(sent), local.toUtc());
    });
  });

  group('ForumComposerController poll', () {
    test('passes the poll to createTopic', () async {
      final api = FakeForumApi();
      await ForumComposerController(api: api).submitTopic(
        boardSlug: 'general',
        title: 'T',
        bodyText: 'b',
        poll: const ForumPollDraft(question: 'Q', options: ['A', 'B']),
      );
      expect(api.createTopicPolls.single, {
        'question': 'Q',
        'options': ['A', 'B'],
      });
    });

    test('no poll sends none', () async {
      final api = FakeForumApi();
      await ForumComposerController(
        api: api,
      ).submitTopic(boardSlug: 'general', title: 'T', bodyText: 'b');
      expect(api.createTopicPolls.single, isNull);
    });

    test('a changed poll rotates the idempotency key', () async {
      final api = FakeForumApi();
      final controller = ForumComposerController(api: api);
      Future<void> submit(String second) => controller.submitTopic(
        boardSlug: 'general',
        title: 'T',
        bodyText: 'b',
        poll: ForumPollDraft(question: 'Q', options: ['A', second]),
      );
      await submit('B');
      await submit('B');
      await submit('C');
      expect(api.createTopicKeys[0], api.createTopicKeys[1]);
      expect(api.createTopicKeys[2], isNot(api.createTopicKeys[1]));
    });
  });

  group('composer poll form', () {
    testWidgets('no Add poll where the forum does not allow polls', (
      tester,
    ) async {
      await _pump(
        tester,
        FakeForumApi(),
        args: const ForumComposeArgs.topic(boardSlug: 'general'),
      );
      expect(find.text('Add poll'), findsNothing);
    });

    testWidgets('no Add poll on a reply', (tester) async {
      await _pump(
        tester,
        FakeForumApi(),
        args: const ForumComposeArgs.reply(topicId: 10),
      );
      expect(find.text('Add poll'), findsNothing);
    });

    testWidgets('Add poll opens the form with two empty options', (
      tester,
    ) async {
      await _pump(tester, FakeForumApi());
      expect(_field('Question'), findsNothing);

      await _openPoll(tester);

      expect(find.text('Add poll'), findsNothing);
      expect(_field('Question'), findsOneWidget);
      expect(_field('Option 1'), findsOneWidget);
      expect(_field('Option 2'), findsOneWidget);
      expect(_field('Option 3'), findsNothing);
      expect(find.text('1 option'), findsOneWidget);
      expect(find.text('Never'), findsOneWidget);
    });

    testWidgets('Post waits for a question and two options', (tester) async {
      await _pump(tester, FakeForumApi());
      await _fillTopic(tester);
      expect(_postEnabled(tester), isTrue);

      await _openPoll(tester);
      expect(_postEnabled(tester), isFalse);
      expect(
        find.text('A poll needs a question and two options.'),
        findsOneWidget,
      );

      await tester.enterText(_field('Question'), 'Which pot?');
      await tester.enterText(_field('Option 1'), 'Terracotta');
      await tester.pump();
      expect(_postEnabled(tester), isFalse);

      await tester.enterText(_field('Option 2'), 'Plastic');
      await tester.pump();
      expect(_postEnabled(tester), isTrue);
      expect(
        find.text('A poll needs a question and two options.'),
        findsNothing,
      );
    });

    testWidgets('two options the same block Post and say why', (tester) async {
      await _pump(tester, FakeForumApi());
      await _fillTopic(tester);
      await _openPoll(tester);
      await tester.enterText(_field('Question'), 'Which pot?');
      await tester.enterText(_field('Option 1'), 'Terracotta');
      await tester.enterText(_field('Option 2'), 'terracotta');
      await tester.pump();

      expect(_postEnabled(tester), isFalse);
      expect(find.text('Each option must be different.'), findsOneWidget);
    });

    testWidgets('posts the topic with its poll', (tester) async {
      final api = FakeForumApi();
      await _pump(tester, api);
      await _fillTopic(tester);
      await _openPoll(tester);
      await tester.enterText(_field('Question'), 'Which pot?');
      await tester.enterText(_field('Option 1'), 'Terracotta');
      await tester.enterText(_field('Option 2'), 'Plastic nursery pot');
      await tester.tap(find.widgetWithText(OutlinedButton, 'Add option'));
      await tester.pump();
      await tester.enterText(_field('Option 3'), 'Self-watering');
      await tester.pump();

      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(api.createTopicPolls.single, {
        'question': 'Which pot?',
        'options': ['Terracotta', 'Plastic nursery pot', 'Self-watering'],
      });
    });

    testWidgets('Add option stops at ten', (tester) async {
      await _pump(tester, FakeForumApi());
      await _openPoll(tester);
      for (var i = 0; i < 8; i++) {
        await tester.tap(find.widgetWithText(OutlinedButton, 'Add option'));
        await tester.pump();
      }
      expect(_field('Option 10'), findsOneWidget);
      expect(find.widgetWithText(OutlinedButton, 'Add option'), findsNothing);
    });

    testWidgets('removing the poll posts the topic without one', (
      tester,
    ) async {
      final api = FakeForumApi();
      await _pump(tester, api);
      await _fillTopic(tester);
      await _openPoll(tester);
      await tester.enterText(_field('Question'), 'Which pot?');
      await tester.pump();

      await tester.tap(find.byTooltip('Remove poll'));
      await tester.pump();

      expect(_field('Question'), findsNothing);
      expect(find.text('Add poll'), findsOneWidget);
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();
      expect(api.createTopicPolls.single, isNull);
    });

    testWidgets('voters can pick up to the filled options', (tester) async {
      final api = FakeForumApi();
      await _pump(tester, api);
      await _fillTopic(tester);
      await _openPoll(tester);
      await tester.enterText(_field('Question'), 'Which pots?');
      await tester.enterText(_field('Option 1'), 'Terracotta');
      await tester.enterText(_field('Option 2'), 'Plastic');
      await tester.pump();

      await tester.tap(find.text('Voters can pick'));
      await tester.pumpAndSettle();
      expect(find.text('Up to 3 options'), findsNothing);
      await tester.tap(find.text('Up to 2 options').last);
      await tester.pumpAndSettle();

      expect(find.text('Up to 2 options'), findsOneWidget);
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();
      expect(api.createTopicPolls.single!['max_choices'], 2);
    });

    testWidgets('a closing time is shown and sent', (tester) async {
      final api = FakeForumApi();
      final closes = DateTime.now().add(const Duration(days: 7));
      await _pump(tester, api, pickCloseTime: (_) async => closes);
      await _fillTopic(tester);
      await _openPoll(tester);
      await tester.enterText(_field('Question'), 'Which pot?');
      await tester.enterText(_field('Option 1'), 'Terracotta');
      await tester.enterText(_field('Option 2'), 'Plastic');
      await tester.pump();

      await tester.tap(find.text('Closes'));
      await tester.pumpAndSettle();
      expect(find.text('Never'), findsNothing);

      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();
      expect(
        DateTime.parse(api.createTopicPolls.single!['closes_at'] as String),
        closes.toUtc(),
      );
    });

    testWidgets('a closing time can be cleared back to Never', (tester) async {
      final closes = DateTime.now().add(const Duration(days: 7));
      await _pump(tester, FakeForumApi(), pickCloseTime: (_) async => closes);
      await _openPoll(tester);
      await tester.tap(find.text('Closes'));
      await tester.pumpAndSettle();
      expect(find.text('Never'), findsNothing);

      await tester.tap(find.byTooltip('Clear closing time'));
      await tester.pump();
      expect(find.text('Never'), findsOneWidget);
    });

    testWidgets('a closing time already past is refused before sending', (
      tester,
    ) async {
      final api = FakeForumApi();
      final past = DateTime.now().subtract(const Duration(minutes: 1));
      await _pump(tester, api, pickCloseTime: (_) async => past);
      await _fillTopic(tester);
      await _openPoll(tester);
      await tester.enterText(_field('Question'), 'Which pot?');
      await tester.enterText(_field('Option 1'), 'Terracotta');
      await tester.enterText(_field('Option 2'), 'Plastic');
      await tester.tap(find.text('Closes'));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(api.createTopicPolls, isEmpty);
      expect(
        find.text('The poll closing time has passed. Pick a later one.'),
        findsOneWidget,
      );
    });

    testWidgets('a rebuilt form comes back as the draft it is given', (
      tester,
    ) async {
      // The form is one row of the composer's lazy list: scrolled far enough
      // away its state is disposed, and the composer hands the draft back.
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: PollDraftForm(
                initial: ForumPollDraft(
                  question: 'Which pot?',
                  options: const ['Terracotta', 'Plastic', 'Self-watering'],
                  maxChoices: 2,
                  closesAt: DateTime(2030, 1, 2, 18),
                ),
                onChanged: (_) {},
                onRemove: () {},
              ),
            ),
          ),
        ),
      );

      expect(find.text('Which pot?'), findsOneWidget);
      expect(find.text('Terracotta'), findsOneWidget);
      expect(find.text('Self-watering'), findsOneWidget);
      expect(_field('Option 4'), findsNothing);
      expect(find.text('Up to 2 options'), findsOneWidget);
      expect(find.text('2 Jan, 6:00 PM'), findsOneWidget);
    });

    testWidgets('a typed poll alone asks before discarding', (tester) async {
      await _pump(tester, FakeForumApi());
      await _openPoll(tester);
      await tester.enterText(_field('Question'), 'Which pot?');
      await tester.pump();

      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(find.text('Discard draft?'), findsOneWidget);
    });
  });

  group('can_poll reaches the composer', () {
    test('ForumBoard reads can_poll, false when absent', () {
      Map<String, dynamic> row({bool? canPoll}) => {
        'id': 1,
        'title': 'General',
        'slug': 'general',
        'can_poll': ?canPoll,
      };
      expect(ForumBoard.fromJson(row(canPoll: true)).canPoll, isTrue);
      expect(ForumBoard.fromJson(row(canPoll: false)).canPoll, isFalse);
      expect(ForumBoard.fromJson(row()).canPoll, isFalse);
    });

    Future<void> openComposerFromForum(
      WidgetTester tester, {
      required bool canPoll,
    }) async {
      tester.view.physicalSize = const Size(1080, 4800);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      final api = FakeForumApi()
        ..categories = [
          categoryOf([
            ForumBoard(
              id: 1,
              title: 'General',
              slug: 'general',
              description: '',
              topicCount: 0,
              postCount: 0,
              canPost: true,
              canPoll: canPoll,
            ),
          ]),
        ];
      final router = GoRouter(
        routes: [
          GoRoute(
            path: '/',
            builder: (_, _) => const ForumTopicsScreen(
              boardSlug: 'general',
              boardTitle: 'General',
            ),
          ),
          GoRoute(
            path: '/compose',
            name: 'forumCompose',
            builder: (_, state) =>
                ForumComposerScreen(args: state.extra! as ForumComposeArgs),
          ),
        ],
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('New topic'));
      await tester.pumpAndSettle();
      expect(find.byType(ForumComposerScreen), findsOneWidget);
    }

    testWidgets('New topic offers Add poll in a forum that allows polls', (
      tester,
    ) async {
      await openComposerFromForum(tester, canPoll: true);
      expect(find.text('Add poll'), findsOneWidget);
    });

    testWidgets('New topic has no Add poll in a forum that does not', (
      tester,
    ) async {
      await openComposerFromForum(tester, canPoll: false);
      expect(find.text('Add poll'), findsNothing);
    });
  });
}
