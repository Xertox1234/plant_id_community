import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/shared/widgets/brand_mark.dart';

import 'support/forum_test_support.dart';

/// Holds the boards and the activity feed in flight.
class _PendingApi extends FakeForumApi {
  final boardsGate = Completer<List<ForumBoard>>();
  final recentGate = Completer<List<ForumRecentTopic>>();

  @override
  Future<List<ForumBoard>> fetchBoards() => boardsGate.future;

  @override
  Future<List<ForumRecentTopic>> fetchRecentTopics({int limit = 10}) =>
      recentGate.future;
}

Widget _wrap(FakeForumApi api) => ProviderScope(
  overrides: [
    forumApiProvider.overrideWithValue(api),
    forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
    authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: false)),
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

  // Was: centred spinners (_SectionLoader). Now skeletons shaped like the
  // rows they stand in for, each announced once.
  testWidgets('loading boards and activity shows skeletons, not spinners', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    final api = _PendingApi();
    await tester.pumpWidget(_wrap(api));
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(find.bySemanticsLabel('Loading boards'), findsOneWidget);
    expect(find.bySemanticsLabel('Loading recent topics'), findsOneWidget);

    api.boardsGate.complete(const []);
    api.recentGate.complete(const []);
    await tester.pumpAndSettle();
    expect(find.bySemanticsLabel('Loading boards'), findsNothing);
    expect(find.textContaining('No boards yet'), findsOneWidget);
    expect(find.textContaining('Nothing here yet'), findsOneWidget);
    handle.dispose();
  });

  testWidgets('the app bar shows the mark and a left-aligned title', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap(FakeForumApi()));
    await tester.pumpAndSettle();
    final bar = tester.widget<AppBar>(find.byType(AppBar));
    expect(bar.centerTitle, isFalse);
    expect(
      find.descendant(
        of: find.byType(AppBar),
        matching: find.text('Community'),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byType(AppBar),
        matching: find.byType(BrandMark),
      ),
      findsOneWidget,
    );
  });
}
