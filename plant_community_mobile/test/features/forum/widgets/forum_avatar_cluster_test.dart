import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_avatar_cluster.dart';

import '../support/forum_test_support.dart';

void main() {
  group('AuthorAvatarCluster (todo 350)', () {
    testWidgets('announces the member COUNT, not the initials underneath', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AuthorAvatarCluster(
              authors: [
                for (final username in ['ada', 'bob', 'carol', 'dave', 'erin'])
                  author(username: username),
              ],
            ),
          ),
        ),
      );

      final node = tester.getSemantics(find.byType(AuthorAvatarCluster));
      // The count is every member, not the three avatars actually drawn.
      expect(node.label, '5 members');
      expect(
        find.descendant(
          of: find.byType(AuthorAvatarCluster),
          matching: find.byType(AuthorAvatar),
        ),
        findsNWidgets(3),
      );

      handle.dispose();
    });

    testWidgets('an empty roster falls back to the group glyph', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: AuthorAvatarCluster(authors: [])),
        ),
      );

      expect(find.byIcon(Icons.group), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });
}
