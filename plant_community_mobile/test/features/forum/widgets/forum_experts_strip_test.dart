import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_experts_strip.dart';

import '../support/forum_test_support.dart';

Future<void> _pump(WidgetTester tester, Widget child) {
  return tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
}

void main() {
  group('ForumExpertsStrip (todo 341 wave 4)', () {
    testWidgets('shows an online dot only on members who are online', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumExpertsStrip(
          experts: [
            expert(username: 'sage', online: true),
            expert(username: 'fern', online: false),
          ],
        ),
      );

      expect(find.text('sage'), findsOneWidget);
      expect(find.text('fern'), findsOneWidget);
      expect(find.byKey(const Key('forum-online-dot')), findsOneWidget);
      expect(find.bySemanticsLabel('sage, online'), findsOneWidget);
      expect(find.bySemanticsLabel('fern'), findsOneWidget);
    });

    testWidgets('tapping a member hands the row to the caller', (tester) async {
      ForumExpert? tapped;
      await _pump(
        tester,
        ForumExpertsStrip(
          experts: [expert(username: 'sage', online: true)],
          onTap: (e) => tapped = e,
        ),
      );

      await tester.tap(find.text('sage'));
      await tester.pump();
      expect(tapped?.author.username, 'sage');
    });

    testWidgets('renders nothing for an empty list', (tester) async {
      await _pump(tester, const ForumExpertsStrip(experts: []));
      expect(find.byType(ListView), findsNothing);
    });
  });
}
