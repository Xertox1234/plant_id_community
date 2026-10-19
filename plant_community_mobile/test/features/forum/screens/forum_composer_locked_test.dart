// D20 (forum live replies, slice 4): a topic locked while the reader types a
// reply keeps their text, disables Post and shows the locked notice.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_composer_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

const _locked = 'This thread is locked — new replies are disabled.';

Future<ProviderContainer> _pump(WidgetTester tester, FakeForumApi api) async {
  final container = ProviderContainer(
    overrides: [
      forumApiProvider.overrideWithValue(api),
      authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: true)),
    ],
  );
  addTearDown(container.dispose);
  // The thread beneath the composer keeps the topic alive.
  container.listen(topicDetailProvider(10), (_, _) {});
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        home: ForumComposerScreen(args: ForumComposeArgs.reply(topicId: 10)),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return container;
}

FilledButton _postButton(WidgetTester tester) =>
    tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Post'));

void main() {
  testWidgets('a topic locked while typing keeps the text, disables Post and '
      'shows the locked notice', (tester) async {
    final api = FakeForumApi()..topicDetail = topicDetail();
    final container = await _pump(tester, api);
    await tester.enterText(find.byType(TextField).last, 'Half a thought');
    await tester.pump();
    expect(_postButton(tester).onPressed, isNotNull);
    expect(find.text(_locked), findsNothing);

    container
        .read(topicDetailProvider(10).notifier)
        .applyPeek(topicDetail(locked: true));
    await tester.pump();

    expect(find.text(_locked), findsOneWidget);
    expect(_postButton(tester).onPressed, isNull);
    expect(find.text('Half a thought'), findsOneWidget);
  });

  testWidgets('a reply 409 on a locked topic shows the locked notice', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..topicDetail = topicDetail()
      ..failCreateReplyWith = ApiException(
        'Topic is closed or locked.',
        statusCode: 409,
      )
      ..peekDetails = [topicDetail(isClosed: true)];
    await _pump(tester, api);
    await tester.enterText(find.byType(TextField).last, 'Too late');
    await tester.pump();

    await tester.tap(find.widgetWithText(FilledButton, 'Post'));
    await tester.pumpAndSettle();

    expect(find.text(_locked), findsOneWidget);
    expect(find.textContaining('Still processing'), findsNothing);
    expect(find.text('Too late'), findsOneWidget);
    expect(_postButton(tester).onPressed, isNull);
  });

  testWidgets('a reply 409 on an open topic still reads as an in-flight '
      'retry', (tester) async {
    final api = FakeForumApi()
      ..topicDetail = topicDetail()
      ..failCreateReplyWith = ApiException('Conflict', statusCode: 409);
    await _pump(tester, api);
    await tester.enterText(find.byType(TextField).last, 'Again');
    await tester.pump();

    await tester.tap(find.widgetWithText(FilledButton, 'Post'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Still processing'), findsOneWidget);
    expect(find.text(_locked), findsNothing);
  });
}
