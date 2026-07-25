import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';

import 'support/forum_test_support.dart';

Widget _wrap(FakeForumApi api) => ProviderScope(
  overrides: [
    forumApiProvider.overrideWithValue(api),
    forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
  ],
  child: const MaterialApp(home: ForumScreen()),
);

void main() {
  testWidgets('empty forum shows empty-state placeholders', (tester) async {
    // No boards and an empty sync feed.
    await tester.pumpWidget(_wrap(FakeForumApi()));
    await tester.pumpAndSettle();

    expect(find.text('Boards'), findsOneWidget);
    expect(find.text('Recent activity'), findsOneWidget);
    expect(find.textContaining('No boards yet'), findsOneWidget);
    expect(find.textContaining('Nothing here yet'), findsOneWidget);
  });

  testWidgets('pumps without exceptions', (tester) async {
    await tester.pumpWidget(_wrap(FakeForumApi()));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
