import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_avatar_cluster.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_whos_online.dart';

import '../../support/forum_test_support.dart';

Future<void> _pump(
  WidgetTester tester,
  FakeForumApi api, {
  Brightness brightness = Brightness.dark,
  Size size = const Size(375, 812),
  double textScale = 1.0,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [forumApiProvider.overrideWithValue(api)],
      child: MaterialApp(
        theme: AppTheme.build(brightness, AppTheme.defaultDensity),
        home: MediaQuery(
          data: MediaQueryData(
            size: size,
            textScaler: TextScaler.linear(textScale),
          ),
          child: const Scaffold(
            body: SingleChildScrollView(child: ForumWhosOnline()),
          ),
        ),
      ),
    ),
  );
}

ForumAuthor _a(String name) =>
    author(username: name.toLowerCase(), displayName: name);

void main() {
  group('ForumWhosOnline', () {
    testWidgets('hides while loading', (tester) async {
      final api = _PendingApi();
      await _pump(tester, api);
      expect(find.text("Who's online"), findsNothing);
      api.completer.complete(const ForumCommunityStats());
      await tester.pumpAndSettle();
    });

    testWidgets('hides on error', (tester) async {
      final api = FakeForumApi()..communityStatsError = Exception('boom');
      await _pump(tester, api);
      await tester.pumpAndSettle();
      expect(find.text("Who's online"), findsNothing);
    });

    testWidgets('shows counts, three names and the newest member', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..communityStats = ForumCommunityStats(
          membersOnline: 3,
          onlineSample: [
            _a('Sam Carter'),
            _a('Will Tower'),
            author(username: 'simtest', displayName: 'simtest'),
          ],
          registeredMembers: 120,
          topicCount: 1,
          postCount: 14,
          newestMember: _a('Iris Moon'),
        );
      await _pump(tester, api);
      await tester.pumpAndSettle();
      expect(find.text("Who's online"), findsOneWidget);
      expect(find.textContaining('3 members online'), findsOneWidget);
      expect(find.textContaining('120 registered'), findsOneWidget);
      expect(find.text('Sam, Will and simtest'), findsOneWidget);
      expect(find.text('1 topic · 14 posts'), findsOneWidget);
      expect(find.text('Newest: Iris Moon'), findsOneWidget);
      expect(find.byType(AuthorAvatarCluster), findsOneWidget);
    });

    testWidgets('five online: three names then "and 2 others"', (tester) async {
      final api = FakeForumApi()
        ..communityStats = ForumCommunityStats(
          membersOnline: 5,
          onlineSample: [
            for (final n in ['Sam', 'Will', 'Iris', 'Ola', 'Pia']) _a(n),
          ],
        );
      await _pump(tester, api);
      await tester.pumpAndSettle();
      expect(find.text('Sam, Will, Iris and 2 others'), findsOneWidget);
      expect(find.textContaining('Newest'), findsNothing);
    });

    testWidgets('nobody online says so instead of the cluster', (tester) async {
      final api = FakeForumApi()
        ..communityStats = const ForumCommunityStats(registeredMembers: 9);
      await _pump(tester, api);
      await tester.pumpAndSettle();
      expect(find.text('No members online right now'), findsOneWidget);
      expect(find.byType(AuthorAvatarCluster), findsNothing);
    });

    for (final brightness in Brightness.values) {
      testWidgets('no overflow at 320x640, x2.0, ${brightness.name}', (
        tester,
      ) async {
        final api = FakeForumApi()
          ..communityStats = ForumCommunityStats(
            membersOnline: 5,
            onlineSample: [
              for (final n in [
                'Alexandria',
                'Bartholomew',
                'Cornelius',
                'D',
                'E',
              ])
                _a(n),
            ],
            registeredMembers: 123456,
            topicCount: 4321,
            postCount: 98765,
            newestMember: _a('Maximiliana-Josephine'),
          );
        await _pump(
          tester,
          api,
          brightness: brightness,
          size: const Size(320, 640),
          textScale: 2.0,
        );
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      });
    }
  });
}

class _PendingApi extends FakeForumApi {
  final completer = Completer<ForumCommunityStats>();
  @override
  Future<ForumCommunityStats> fetchCommunityStats() => completer.future;
}
