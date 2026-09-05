import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/poll_card.dart';

import '../support/forum_test_support.dart';

Future<void> _pump(WidgetTester tester, Widget child) {
  return tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  );
}

/// A poll with visible counts for the results view.
ForumPoll _counted({
  int maxChoices = 1,
  List<int> myVoteOptionIds = const [],
  bool isClosed = false,
}) {
  return poll(
    maxChoices: maxChoices,
    totalVotes: 4,
    myVoteOptionIds: myVoteOptionIds,
    isClosed: isClosed,
    options: [
      pollOption(id: 1, text: 'Weekly', voteCount: 3),
      pollOption(id: 2, text: 'Fortnightly', voteCount: 1),
      pollOption(id: 3, text: 'When dry', voteCount: 0),
    ],
  );
}

void main() {
  group('PollCard single-choice ballot (todo 341 wave 3)', () {
    testWidgets('one tap per option casts that option', (tester) async {
      final votes = <List<int>>[];
      await _pump(
        tester,
        PollCard(
          poll: poll(),
          canVote: true,
          onVote: (ids) async => votes.add(ids),
        ),
      );

      expect(find.text('How often do you water?'), findsOneWidget);
      expect(find.byType(OutlinedButton), findsNWidgets(3));
      expect(find.byType(CheckboxListTile), findsNothing);
      // Results are hidden until the viewer votes.
      expect(find.byType(LinearProgressIndicator), findsNothing);
      expect(find.text('0 votes'), findsOneWidget);

      await tester.tap(find.text('Fortnightly'));
      await tester.pump();
      expect(votes, [
        [2],
      ]);
    });

    testWidgets('a pending ballot disables the controls and spins', (
      tester,
    ) async {
      await _pump(
        tester,
        PollCard(
          poll: poll().copyWith(pendingOptionIds: [1]),
          canVote: true,
          onVote: (_) async {},
        ),
      );

      for (final button in tester.widgetList<OutlinedButton>(
        find.byType(OutlinedButton),
      )) {
        expect(button.onPressed, isNull);
      }
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('a signed-out viewer gets totals but no ballot', (
      tester,
    ) async {
      await _pump(
        tester,
        PollCard(poll: _counted(), canVote: false, onVote: (_) async {}),
      );

      for (final button in tester.widgetList<OutlinedButton>(
        find.byType(OutlinedButton),
      )) {
        expect(button.onPressed, isNull);
      }
      expect(find.text('4 votes · sign in to vote'), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsNothing);
    });
  });

  group('PollCard multi-choice ballot', () {
    testWidgets('caps the ballot at max_choices and sends it whole', (
      tester,
    ) async {
      final votes = <List<int>>[];
      await _pump(
        tester,
        PollCard(
          poll: poll(maxChoices: 2),
          canVote: true,
          onVote: (ids) async => votes.add(ids),
        ),
      );

      expect(find.text('Pick up to 2.'), findsOneWidget);
      expect(find.byType(CheckboxListTile), findsNWidgets(3));
      final vote = find.widgetWithText(FilledButton, 'Vote');
      expect(tester.widget<FilledButton>(vote).onPressed, isNull);

      await tester.tap(find.text('Weekly'));
      await tester.pump();
      await tester.tap(find.text('Fortnightly'));
      await tester.pump();

      // The third box goes inert once the ballot is full — the Vote button
      // can never send a ballot the server would refuse whole.
      final third = tester.widget<CheckboxListTile>(
        find.widgetWithText(CheckboxListTile, 'When dry'),
      );
      expect(third.onChanged, isNull);
      expect(third.value, isFalse);
      await tester.tap(find.text('When dry'));
      await tester.pump();
      expect(
        tester
            .widget<CheckboxListTile>(
              find.widgetWithText(CheckboxListTile, 'When dry'),
            )
            .value,
        isFalse,
      );

      // Unticking one frees a slot again.
      await tester.tap(find.text('Weekly'));
      await tester.pump();
      expect(
        tester
            .widget<CheckboxListTile>(
              find.widgetWithText(CheckboxListTile, 'When dry'),
            )
            .onChanged,
        isNotNull,
      );
      await tester.tap(find.text('When dry'));
      await tester.pump();

      await tester.tap(vote);
      await tester.pump();
      expect(votes, [
        [2, 3],
      ]);
    });
  });

  group('PollCard results', () {
    testWidgets('after voting: bars, counts, percentages and "your vote"', (
      tester,
    ) async {
      await _pump(
        tester,
        PollCard(
          poll: _counted(myVoteOptionIds: [1]),
          canVote: true,
          onVote: (_) async {},
        ),
      );

      expect(find.byType(OutlinedButton), findsNothing);
      expect(find.byType(LinearProgressIndicator), findsNWidgets(3));
      expect(find.text('3 (75%)'), findsOneWidget);
      expect(find.text('1 (25%)'), findsOneWidget);
      expect(find.text('0 (0%)'), findsOneWidget);
      expect(find.text('your vote'), findsOneWidget);
      expect(find.text('4 votes · your vote is final'), findsOneWidget);
      expect(find.text('Closed'), findsNothing);
    });

    testWidgets('a closed poll shows results and the Closed chip, no ballot', (
      tester,
    ) async {
      await _pump(
        tester,
        PollCard(
          poll: _counted(isClosed: true),
          canVote: true,
          onVote: (_) async {},
        ),
      );

      expect(find.text('Closed'), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsNWidgets(3));
      expect(find.byType(OutlinedButton), findsNothing);
      expect(find.byType(CheckboxListTile), findsNothing);
      expect(find.text('your vote'), findsNothing);
      expect(find.text('4 votes'), findsOneWidget);
    });

    testWidgets('a multi-choice poll counts voters, not votes', (tester) async {
      await _pump(
        tester,
        PollCard(
          poll: _counted(maxChoices: 2, myVoteOptionIds: [1, 2]),
          canVote: true,
          onVote: (_) async {},
        ),
      );

      expect(find.text('your vote'), findsNWidgets(2));
      expect(find.text('4 voters · your vote is final'), findsOneWidget);
      expect(find.text('Pick up to 2.'), findsNothing);
    });
  });
}
