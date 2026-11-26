// Forum audit F111: thread post cards are keyed by post id, so removing a
// post never hands its State (the blocked-author "revealed" flag) to the
// post that slides into its place, and a moved post keeps its own.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_thread_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_unlock_store.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  testWidgets('removing a post keeps each blocked post\'s own reveal', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..topicDetail = topicDetail(title: 'Keyed thread')
      ..posts = CursorPage(
        items: [
          post(id: 1, body: const [ParagraphBlock('Opening')]),
          post(id: 2, body: const [ParagraphBlock('Plain reply')]),
          post(
            id: 3,
            isBlocked: true,
            body: const [ParagraphBlock('Third body')],
          ),
          post(
            id: 4,
            isBlocked: true,
            body: const [ParagraphBlock('Fourth body')],
          ),
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
    expect(find.text('Show anyway'), findsNWidgets(2));

    // Reveal post 3 only.
    await tester.tap(find.text('Show anyway').first);
    await tester.pumpAndSettle();
    expect(find.text('Third body'), findsOneWidget);
    expect(find.text('Fourth body'), findsNothing);

    // Post 2 goes (removed live); 3 and 4 each move up one place.
    container
        .read(
          topicPostsProvider(10, container.read(forumViewerProvider)).notifier,
        )
        .removeLocal(2);
    await tester.pumpAndSettle();

    expect(find.text('Plain reply'), findsNothing);
    expect(
      find.text('Fourth body'),
      findsNothing,
      reason: 'post 4 must not inherit post 3\'s reveal',
    );
    expect(
      find.text('Third body'),
      findsOneWidget,
      reason: 'post 3 keeps its own reveal',
    );
    expect(find.text('Show anyway'), findsOneWidget);

    await tester.pumpWidget(const SizedBox());
    container.dispose();
    await tester.pump();
  });
}
