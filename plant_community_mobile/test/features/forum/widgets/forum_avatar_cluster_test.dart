import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_avatar_cluster.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

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

    testWidgets('leaves the viewer out, folds the overflow into "+N" and '
        'counts only the OTHER members (todo 463, web ParticipantStack)', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AuthorAvatarCluster(
              viewerUsername: 'me',
              authors: [
                for (final username in ['me', 'ada', 'bob', 'carol', 'dave'])
                  author(username: username),
              ],
            ),
          ),
        ),
      );

      final avatars = tester
          .widgetList<AuthorAvatar>(
            find.descendant(
              of: find.byType(AuthorAvatarCluster),
              matching: find.byType(AuthorAvatar),
            ),
          )
          .map((a) => a.author.username)
          .toList();
      // The first three OTHERS, in joined order — never the viewer.
      expect(avatars, ['ada', 'bob', 'carol']);
      // dave is past the cap of three: one "+1" disc stands in for him.
      expect(find.text('+1'), findsOneWidget);
      final node = tester.getSemantics(find.byType(AuthorAvatarCluster));
      expect(node.label, '4 other members');
      expect(tester.takeException(), isNull);

      handle.dispose();
    });

    testWidgets('no "+N" disc when the others fit, and a one-other group '
        'reads in the singular', (tester) async {
      final handle = tester.ensureSemantics();
      Future<void> pump(List<String> usernames) => tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AuthorAvatarCluster(
              viewerUsername: 'me',
              authors: [for (final u in usernames) author(username: u)],
            ),
          ),
        ),
      );

      await pump(['me', 'ada', 'bob', 'carol']);
      expect(find.byType(AuthorAvatar), findsNWidgets(3));
      expect(find.textContaining('+'), findsNothing);
      expect(
        tester.getSemantics(find.byType(AuthorAvatarCluster)).label,
        '3 other members',
      );

      await pump(['ada', 'me']);
      expect(find.byType(AuthorAvatar), findsOneWidget);
      expect(
        tester.getSemantics(find.byType(AuthorAvatarCluster)).label,
        '1 other member',
      );

      handle.dispose();
    });

    testWidgets('an unknown viewer shows everyone, "+N" included', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AuthorAvatarCluster(
              authors: [
                for (final username in ['me', 'ada', 'bob', 'carol', 'dave'])
                  author(username: username),
              ],
            ),
          ),
        ),
      );

      expect(find.byType(AuthorAvatar), findsNWidgets(3));
      expect(find.text('+2'), findsOneWidget);
    });

    testWidgets('an empty roster falls back to the group glyph', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: AuthorAvatarCluster(authors: [])),
        ),
      );

      expect(find.byIcon(LucideIcons.users), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('the bare group glyph reads "No members" when the viewer is '
        'unknown and "No other members" when only the viewer is left '
        '(todo 507)', (tester) async {
      final handle = tester.ensureSemantics();
      Future<void> pump(AuthorAvatarCluster cluster) =>
          tester.pumpWidget(MaterialApp(home: Scaffold(body: cluster)));

      // Released even when an expect fails, so the handle cannot leak into
      // later tests. Not addTearDown: flutter_test checks that every handle
      // is disposed at the END of the body, before tearDowns run (todo 520).
      try {
        await pump(const AuthorAvatarCluster(authors: []));
        expect(find.byIcon(LucideIcons.users), findsOneWidget);
        expect(
          tester.getSemantics(find.byType(AuthorAvatarCluster)).label,
          'No members',
        );

        await pump(
          AuthorAvatarCluster(
            viewerUsername: 'me',
            authors: [author(username: 'me')],
          ),
        );
        expect(find.byIcon(LucideIcons.users), findsOneWidget);
        expect(
          tester.getSemantics(find.byType(AuthorAvatarCluster)).label,
          'No other members',
        );
        expect(tester.takeException(), isNull);
      } finally {
        handle.dispose();
      }
    });
  });
}
