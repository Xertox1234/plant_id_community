import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_thread_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_link_launcher.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

const _video = 'https://youtu.be/dQw4w9WgXcQ?si=abc123';

/// Records every URL handed to the launcher; [result] is what it reports.
class _FakeLauncher {
  _FakeLauncher({this.result = true, this.error});

  final bool result;
  final Object? error;
  final opened = <String>[];

  Future<bool> call(Uri uri) async {
    opened.add(uri.toString());
    if (error != null) throw error!;
    return result;
  }
}

Widget _wrap(FakeForumApi api, _FakeLauncher launcher) => ProviderScope(
  overrides: [
    forumApiProvider.overrideWithValue(api),
    authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: true)),
    forumLinkLauncherProvider.overrideWithValue(launcher.call),
  ],
  child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
);

FakeForumApi _thread(List<ForumBodyBlock> body) => FakeForumApi()
  ..topicDetail = topicDetail(id: 10)
  ..posts = CursorPage(items: [post(id: 1, body: body)]);

void main() {
  group('Forum links open in the in-app browser (todo 424)', () {
    testWidgets('tapping a link in post text hands the exact URL to the '
        'launcher', (tester) async {
      final launcher = _FakeLauncher();
      await tester.pumpWidget(
        _wrap(
          _thread(const [
            ParagraphBlock(
              '<p>See the <a href="https://example.com/care?x=1">care '
              'guide</a>.</p>',
            ),
          ]),
          launcher,
        ),
      );
      await tester.pumpAndSettle();

      await tester.tapOnText(find.textRange.ofSubstring('care guide'));
      await tester.pumpAndSettle();

      expect(launcher.opened, ['https://example.com/care?x=1']);
      expect(find.text('https://example.com/care?x=1'), findsNothing);
    });

    testWidgets('a screen reader tap on a video card hands the exact URL to '
        'the launcher', (tester) async {
      final handle = tester.ensureSemantics();
      final launcher = _FakeLauncher();
      await tester.pumpWidget(
        _wrap(
          _thread(const [EmbedBlock(url: _video, title: 'Repotting')]),
          launcher,
        ),
      );
      await tester.pumpAndSettle();

      final node = tester.getSemantics(
        find.bySemanticsLabel(RegExp(r': Repotting$')),
      );
      node.owner!.performAction(node.id, SemanticsAction.tap);
      await tester.pumpAndSettle();

      expect(launcher.opened, [_video]);
      // The old handler put the raw URL in a SnackBar, which VoiceOver then
      // spelled out character by character.
      expect(find.byType(SnackBar), findsNothing);
      handle.dispose();
    });

    for (final href in const [
      'javascript:alert(1)',
      'file:///etc/passwd',
      'intent://scan/#Intent;scheme=zxing;end',
      'mailto:someone@example.com',
      '/forum/topics/3/',
    ]) {
      testWidgets('"$href" never reaches the launcher', (tester) async {
        final launcher = _FakeLauncher();
        await tester.pumpWidget(
          _wrap(
            _thread([ParagraphBlock('<p><a href="$href">bad link</a></p>')]),
            launcher,
          ),
        );
        await tester.pumpAndSettle();

        await tester.tapOnText(find.textRange.ofSubstring('bad link'));
        await tester.pumpAndSettle();

        expect(launcher.opened, isEmpty);
        expect(find.text("Couldn't open this link."), findsOneWidget);
        expect(find.text(href), findsNothing);
      });
    }

    testWidgets('a launch that fails shows a readable error, not the URL', (
      tester,
    ) async {
      final launcher = _FakeLauncher(result: false);
      await tester.pumpWidget(
        _wrap(_thread(const [EmbedBlock(url: _video, title: 'T')]), launcher),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('T'));
      await tester.pumpAndSettle();

      expect(launcher.opened, [_video]);
      expect(find.text("Couldn't open this link."), findsOneWidget);
      // The card shows its own URL as a line; the SnackBar must not repeat it.
      expect(
        find.descendant(of: find.byType(SnackBar), matching: find.text(_video)),
        findsNothing,
      );
    });

    testWidgets('a launch that throws shows the same readable error', (
      tester,
    ) async {
      final launcher = _FakeLauncher(error: Exception('no handler'));
      await tester.pumpWidget(
        _wrap(_thread(const [EmbedBlock(url: _video, title: 'T')]), launcher),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('T'));
      await tester.pumpAndSettle();

      expect(find.text("Couldn't open this link."), findsOneWidget);
    });
  });

  group('openableForumLink', () {
    test('passes absolute http and https links unchanged', () {
      for (final href in const [
        'https://example.com/a?b=1#c',
        'http://example.com',
        'HTTPS://Example.com/x',
        _video,
      ]) {
        expect(openableForumLink(href), Uri.parse(href), reason: href);
      }
    });

    test('refuses every other scheme, relative paths and hostless URLs', () {
      for (final href in const [
        'javascript:alert(1)',
        'JavaScript:alert(1)',
        'file:///etc/passwd',
        'intent://scan/#Intent;end',
        'tel:+15551234567',
        'mailto:a@b.co',
        'data:text/html,hi',
        '/forum/topics/3/',
        '//example.com/protocol-relative',
        'https://',
        'https:///path-only',
        '',
      ]) {
        expect(openableForumLink(href), isNull, reason: href);
      }
    });
  });
}
