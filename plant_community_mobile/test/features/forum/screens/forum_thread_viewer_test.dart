// The thread screen is keyed on who reads it: a password forum's thread is
// per member, so a sign-out or an account switch whose refetch fails must
// show the error, never the previous member's thread.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_thread_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_unlock_store.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

Future<(ProviderContainer, FakeForumApi)> _open(WidgetTester tester) async {
  final api = FakeForumApi()
    ..topicDetail = topicDetail(title: 'Secret thread')
    ..posts = CursorPage(
      items: [
        post(id: 1, body: const [ParagraphBlock('Only for members')]),
      ],
    );
  final container = ProviderContainer(
    retry: (_, _) => null,
    overrides: [
      forumApiProvider.overrideWithValue(api),
      forumUnlockStoreProvider.overrideWithValue(FakeForumUnlockStore()),
      apiServiceProvider.overrideWithValue(
        ApiService(baseUrl: 'http://localhost:8000/api/v1', authToken: 'a'),
      ),
      authServiceProvider.overrideWith(
        () => FakeAuthService(loggedIn: false, initial: signedInAs('ada')),
      ),
      ...liveTestOverrides(FakeLiveConnector()),
    ],
  );
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
    ),
  );
  await tester.pumpAndSettle();
  expect(find.text('Secret thread'), findsNWidgets(2)); // bar + heading
  expect(find.text('Only for members'), findsOneWidget);
  return (container, api);
}

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  for (final (name, next) in [
    ('another member', signedInAs('bob')),
    ('a sign-out', const AuthState()),
  ]) {
    testWidgets('$name whose refetch fails shows the error, not the old '
        'thread', (tester) async {
      final (container, api) = await _open(tester);

      api
        ..topicDetail =
            null // 404
        ..throwOnFetchPostsCallNumber = 2;
      (container.read(authServiceProvider.notifier) as FakeAuthService).setAuth(
        next,
      );
      await tester.pumpAndSettle();

      expect(find.text('Secret thread'), findsNothing);
      expect(find.text('Only for members'), findsNothing);
      expect(find.text('Could not load this thread.'), findsOneWidget);

      // No socket or toast timer outlives the test.
      await tester.pumpWidget(const SizedBox());
      container.dispose();
      await tester.pump();
    });
  }
}
