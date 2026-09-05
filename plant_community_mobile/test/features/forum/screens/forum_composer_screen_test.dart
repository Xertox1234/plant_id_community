// Composer round-trip tests for the rich-text marker grammar (todo 314):
// compose -> submit -> render, one test per mark, asserting the exact
// captured body block AND the rendered styling (not just controller state
// or text presence) — plus the ForumComposeArgs.edit / parseForumRichHtmlToMarkup
// interaction. Split out of forum_read_path_test.dart (already 600+ lines)
// rather than growing that file further.
import 'package:flutter/cupertino.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/models/forum_rich_text_markup.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_composer_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_image_picker.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_body_renderer.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

/// Concatenates all text in a [TextSpan] tree, in document order — enough to
/// assert "these lines, in this order" without depending on style.
String _flattenText(InlineSpan span) {
  final buffer = StringBuffer();
  void visit(InlineSpan s) {
    if (s is TextSpan) {
      if (s.text != null) buffer.write(s.text);
      s.children?.forEach(visit);
    }
  }

  visit(span);
  return buffer.toString();
}

/// Finds the first [TextSpan] (in document order) whose text exactly equals
/// [text], anywhere in the tree rooted at [span].
TextSpan? _findSpanWithText(InlineSpan span, String text) {
  TextSpan? found;
  void visit(InlineSpan s) {
    if (found != null) return;
    if (s is TextSpan) {
      if (s.text == text) {
        found = s;
        return;
      }
      s.children?.forEach(visit);
    }
  }

  visit(span);
  return found;
}

Future<void> _pumpComposer(
  WidgetTester tester,
  FakeForumApi api, {
  ForumComposeArgs? args,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        forumApiProvider.overrideWithValue(api),
        authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: true)),
      ],
      child: MaterialApp(
        home: ForumComposerScreen(
          args: args ?? const ForumComposeArgs.reply(topicId: 10),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<TextSpan> _pumpRenderedBody(
  WidgetTester tester,
  List<Map<String, dynamic>> capturedBody, {
  void Function(String href)? onOpenLink,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: ForumBodyRenderer(
          parseForumBody(capturedBody),
          onOpenLink: onOpenLink,
        ),
      ),
    ),
  );
  await tester.pump();
  final text = tester.widget<Text>(find.byType(Text));
  return text.textSpan as TextSpan;
}

void main() {
  _backGuardTests();
  group('rich text composer round-trip (todo 314) — compose -> submit -> '
      'render, one test per mark', () {
    testWidgets('bold', (tester) async {
      final api = FakeForumApi()..replyStatus = ForumModerationStatus.published;
      await _pumpComposer(tester, api);

      await tester.enterText(find.byType(TextField), 'a **bold** word');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(api.createReplyBodies.single, [
        {'type': 'paragraph', 'value': 'a <strong>bold</strong> word'},
      ]);

      final root = await _pumpRenderedBody(
        tester,
        api.createReplyBodies.single,
      );
      final span = _findSpanWithText(root, 'bold');
      expect(span, isNotNull);
      expect(span!.style?.fontWeight, FontWeight.bold);
    });

    testWidgets('italic', (tester) async {
      final api = FakeForumApi()..replyStatus = ForumModerationStatus.published;
      await _pumpComposer(tester, api);

      await tester.enterText(find.byType(TextField), 'a _italic_ word');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(api.createReplyBodies.single, [
        {'type': 'paragraph', 'value': 'a <em>italic</em> word'},
      ]);

      final root = await _pumpRenderedBody(
        tester,
        api.createReplyBodies.single,
      );
      final span = _findSpanWithText(root, 'italic');
      expect(span, isNotNull);
      expect(span!.style?.fontStyle, FontStyle.italic);
    });

    testWidgets('inline code', (tester) async {
      final api = FakeForumApi()..replyStatus = ForumModerationStatus.published;
      await _pumpComposer(tester, api);

      await tester.enterText(find.byType(TextField), 'a `code` word');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(api.createReplyBodies.single, [
        {'type': 'paragraph', 'value': 'a <code>code</code> word'},
      ]);

      final root = await _pumpRenderedBody(
        tester,
        api.createReplyBodies.single,
      );
      final span = _findSpanWithText(root, 'code');
      expect(span, isNotNull);
      expect(span!.style?.fontFamily, 'monospace');
    });

    testWidgets('link', (tester) async {
      final api = FakeForumApi()..replyStatus = ForumModerationStatus.published;
      await _pumpComposer(tester, api);

      await tester.enterText(
        find.byType(TextField),
        'a [my plant](https://example.com) word',
      );
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(api.createReplyBodies.single, [
        {
          'type': 'paragraph',
          'value': 'a <a href="https://example.com">my plant</a> word',
        },
      ]);

      final tappedHrefs = <String>[];
      final root = await _pumpRenderedBody(
        tester,
        api.createReplyBodies.single,
        onOpenLink: tappedHrefs.add,
      );
      final span = _findSpanWithText(root, 'my plant');
      expect(span, isNotNull);
      expect(span!.recognizer, isA<TapGestureRecognizer>());
      (span.recognizer as TapGestureRecognizer).onTap!();
      expect(tappedHrefs, ['https://example.com']);
    });

    testWidgets('list', (tester) async {
      final api = FakeForumApi()..replyStatus = ForumModerationStatus.published;
      await _pumpComposer(tester, api);

      await tester.enterText(find.byType(TextField), '- one\n- two');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(api.createReplyBodies.single, [
        {'type': 'paragraph', 'value': '<ul><li>one</li><li>two</li></ul>'},
      ]);

      final root = await _pumpRenderedBody(
        tester,
        api.createReplyBodies.single,
      );
      // Bullet-prefixed lines, in order — not just that "one" and "two" are
      // present somewhere in the tree.
      expect(_flattenText(root), '•  one\n•  two');
    });
  });

  group('ForumComposeArgs.edit / parseForumRichHtmlToMarkup interaction '
      '(todo 314)', () {
    testWidgets(
      'a post whose body is exactly what the generator produces for marker '
      'text containing a mark opens rich-editable with the original marker '
      'text intact',
      (tester) async {
        final html = generateForumRichHtml('a **bold** word');
        final editedPost = post(
          id: 7,
          body: [ParagraphBlock(html)],
          canEdit: true,
        );

        await _pumpComposer(
          tester,
          FakeForumApi(),
          args: ForumComposeArgs.edit(post: editedPost),
        );

        // The raw marker text is intact in the field — not the HTML, not
        // stripped/escaped tag soup.
        expect(find.text('a **bold** word'), findsOneWidget);
        // No "can't show this yet" warning banner — this post IS fully
        // editable.
        expect(find.textContaining("can't show here yet"), findsNothing);
      },
    );

    testWidgets(
      'a post with markup outside the parser\'s grammar (e.g. a mention '
      'span) still falls back to the existing plain-text/warning-banner '
      'path, unchanged from today\'s behavior',
      (tester) async {
        final editedPost = post(
          id: 7,
          body: const [
            ParagraphBlock('Ping <span class="mention">@bob</span> please'),
          ],
          canEdit: true,
        );

        await _pumpComposer(
          tester,
          FakeForumApi(),
          args: ForumComposeArgs.edit(post: editedPost),
        );

        // Falls back exactly like todo 292's original behavior: the field is
        // left empty and the warning banner is shown, not a corrupted or
        // partially-parsed reconstruction.
        expect(find.textContaining("can't show here yet"), findsOneWidget);
        final field = tester.widget<TextField>(find.byType(TextField));
        expect(field.controller!.text, isEmpty);
      },
    );
  });

  group('rich-text toolbar <-> composer reactivity (todo 314)', () {
    testWidgets('tapping a toolbar button (without typing through the IME) '
        're-evaluates the Post button\'s enabled state — controller.value '
        'assignment does not fire TextField.onChanged', (tester) async {
      await _pumpComposer(tester, FakeForumApi());

      // Empty body: Post starts disabled.
      var postButton = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Post'),
      );
      expect(postButton.onPressed, isNull);

      // Focus the (empty) field first so it has a real, valid selection —
      // then tap the bulleted-list button, which mutates the controller
      // programmatically, exactly as every toolbar button does.
      await tester.tap(find.byType(TextField));
      await tester.pump();
      await tester.tap(find.byIcon(Icons.format_list_bulleted));
      await tester.pump();

      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, isNotEmpty);

      postButton = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Post'),
      );
      expect(postButton.onPressed, isNotNull);
    });

    testWidgets(
      'the link dialog rejects a disallowed URL with an error message, '
      'and inserts valid markup on retry',
      (tester) async {
        await _pumpComposer(tester, FakeForumApi());

        // Focus the body field first so it has a real, valid selection —
        // `insertLink` is a defensive no-op against an invalid one (e.g.
        // the untouched default TextEditingValue's collapsed(-1)).
        await tester.tap(find.byType(TextField));
        await tester.pump();

        await tester.tap(find.byIcon(Icons.link));
        await tester.pumpAndSettle();

        await tester.enterText(
          find.byType(CupertinoTextField),
          'javascript:alert(1)',
        );
        await tester.tap(find.widgetWithText(TextButton, 'Insert'));
        await tester.pump();

        expect(find.textContaining('Enter a valid http(s)'), findsOneWidget);
        // The dialog is still open — no markup was inserted.
        expect(find.byType(CupertinoTextField), findsOneWidget);

        await tester.enterText(
          find.byType(CupertinoTextField),
          'https://example.com',
        );
        await tester.tap(find.widgetWithText(TextButton, 'Insert'));
        await tester.pumpAndSettle();

        final field = tester.widget<TextField>(find.byType(TextField));
        expect(
          field.controller!.text,
          '[https://example.com](https://example.com)',
        );
      },
    );
  });
}

/// The composer behind a real route, so `pageBack()` hits an AppBar back
/// button that goes through `Navigator.maybePop` (which is what PopScope
/// governs) — as `home:` the composer would be the root route.
Future<void> _pumpComposerBehindHome(
  WidgetTester tester,
  FakeForumApi api, {
  ForumComposeArgs args = const ForumComposeArgs.reply(topicId: 10),
  ForumImagePicker imagePicker = const DeviceForumImagePicker(),
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        forumApiProvider.overrideWithValue(api),
        authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: true)),
      ],
      child: MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) =>
                      ForumComposerScreen(args: args, imagePicker: imagePicker),
                ),
              ),
              child: const Text('open composer'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open composer'));
  await tester.pumpAndSettle();
}

void _backGuardTests() {
  group('unsent-draft back guard (audit 2026-09-04 L8)', () {
    testWidgets('back with unsent text asks first; Keep editing stays', (
      tester,
    ) async {
      await _pumpComposerBehindHome(tester, FakeForumApi());
      await tester.enterText(find.byType(TextField), 'half written');
      await tester.pump();

      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Discard draft?'), findsOneWidget);

      await tester.tap(find.text('Keep editing'));
      await tester.pumpAndSettle();
      expect(find.byType(ForumComposerScreen), findsOneWidget);
      expect(find.text('half written'), findsOneWidget);
    });

    testWidgets('a title alone (topic mode) is unsent input too', (
      tester,
    ) async {
      // Each arm of _hasUnsentInput needs its own case (Phase 6 review):
      // title-only is reachable only in topic mode.
      await _pumpComposerBehindHome(
        tester,
        FakeForumApi(),
        args: const ForumComposeArgs.topic(boardSlug: 'general'),
      );
      await tester.enterText(find.byType(TextField).first, 'Only a title');
      await tester.pump();

      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(find.text('Discard draft?'), findsOneWidget);
    });

    testWidgets('an attached image with no text is unsent input too', (
      tester,
    ) async {
      await _pumpComposerBehindHome(
        tester,
        FakeForumApi(),
        imagePicker: FakeForumImagePicker(nextPath: '/tmp/leaf.jpg'),
      );
      await tester.tap(find.widgetWithText(OutlinedButton, 'Add photo'));
      // Bounded pumps, not pumpAndSettle: the thumbnail's CachedNetworkImage
      // spinner never resolves in the blocked-network harness (see the
      // attach test in forum_read_path_test.dart).
      await tester.pump();
      await tester.pump();
      expect(find.widgetWithText(OutlinedButton, 'Add photo'), findsNothing);

      await tester.pageBack();
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('Discard draft?'), findsOneWidget);
    });

    testWidgets('Discard leaves the composer', (tester) async {
      await _pumpComposerBehindHome(tester, FakeForumApi());
      await tester.enterText(find.byType(TextField), 'half written');
      await tester.pump();

      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.tap(find.text('Discard'));
      await tester.pumpAndSettle();

      expect(find.byType(ForumComposerScreen), findsNothing);
    });

    testWidgets('back with nothing typed leaves without a prompt', (
      tester,
    ) async {
      await _pumpComposerBehindHome(tester, FakeForumApi());

      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(find.text('Discard draft?'), findsNothing);
      expect(find.byType(ForumComposerScreen), findsNothing);
    });

    testWidgets('a moderation-queued submit pops without a prompt', (
      tester,
    ) async {
      // The text is still in the controllers behind the pending view, but it
      // has been sent — back must not ask to discard it (Phase 6 review).
      final api = FakeForumApi()..replyStatus = ForumModerationStatus.pending;
      await _pumpComposerBehindHome(tester, api);
      await tester.enterText(find.byType(TextField), 'queued');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();
      expect(find.byType(ForumComposerScreen), findsOneWidget);

      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(find.text('Discard draft?'), findsNothing);
      expect(find.byType(ForumComposerScreen), findsNothing);
    });

    testWidgets('a successful submit still pops without a prompt', (
      tester,
    ) async {
      final api = FakeForumApi()..replyStatus = ForumModerationStatus.published;
      await _pumpComposerBehindHome(tester, api);
      await tester.enterText(find.byType(TextField), 'sent');
      await tester.pump();

      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(find.text('Discard draft?'), findsNothing);
      expect(find.byType(ForumComposerScreen), findsNothing);
    });
  });
}
