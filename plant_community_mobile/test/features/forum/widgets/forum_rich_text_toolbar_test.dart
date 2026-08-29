import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_rich_text_toolbar.dart';

void main() {
  group('wrapInlineMarker', () {
    test('wraps a non-collapsed selection in the marker pair', () {
      final value = const TextEditingValue(
        text: 'hello world',
        selection: TextSelection(baseOffset: 6, extentOffset: 11), // "world"
      );
      final result = wrapInlineMarker(value, '**');
      expect(result.text, 'hello **world**');
      // The wrapped text stays selected so a re-tap or typing replaces it.
      expect(result.selection.textInside(result.text), 'world');
    });

    test('collapsed selection inserts an empty marker pair with the cursor '
        'placed between them', () {
      final value = const TextEditingValue(
        text: 'hello ',
        selection: TextSelection.collapsed(offset: 6),
      );
      final result = wrapInlineMarker(value, '_');
      expect(result.text, 'hello __');
      expect(result.selection.isCollapsed, isTrue);
      expect(result.selection.baseOffset, 7); // between the two underscores
    });

    test('collapsed selection with a placeholder selects the placeholder '
        'text so typing overwrites it', () {
      final value = const TextEditingValue(
        text: '',
        selection: TextSelection.collapsed(offset: 0),
      );
      final result = wrapInlineMarker(value, '`', placeholder: 'code');
      expect(result.text, '`code`');
      expect(result.selection.textInside(result.text), 'code');
    });

    test('an invalid (out of range) selection is a no-op', () {
      const value = TextEditingValue(
        text: 'x',
        selection: TextSelection(baseOffset: -1, extentOffset: -1),
      );
      expect(wrapInlineMarker(value, '**'), same(value));
    });
  });

  group('insertLink', () {
    test('uses the current non-empty selection as the link text', () {
      final value = const TextEditingValue(
        text: 'see my plant',
        selection: TextSelection(baseOffset: 4, extentOffset: 12), // "my plant"
      );
      final result = insertLink(value, url: 'https://example.com');
      expect(result.text, 'see [my plant](https://example.com)');
      expect(result.selection.isCollapsed, isTrue);
      expect(result.selection.baseOffset, result.text.length);
    });

    test('a collapsed selection with linkTextOverride uses the override '
        'as the link text', () {
      final value = const TextEditingValue(
        text: 'check this: ',
        selection: TextSelection.collapsed(offset: 12),
      );
      final result = insertLink(
        value,
        url: 'https://example.com',
        linkTextOverride: 'my plant',
      );
      expect(result.text, 'check this: [my plant](https://example.com)');
    });

    test('a collapsed selection with no override falls back to the URL '
        'itself as the link text', () {
      final value = const TextEditingValue(
        text: '',
        selection: TextSelection.collapsed(offset: 0),
      );
      final result = insertLink(value, url: 'https://example.com');
      expect(result.text, '[https://example.com](https://example.com)');
    });

    test('a disallowed URL is rejected — no-op, does not insert a broken '
        'link', () {
      final value = const TextEditingValue(
        text: '',
        selection: TextSelection.collapsed(offset: 0),
      );
      final result = insertLink(value, url: 'javascript:alert(1)');
      expect(result, same(value));
    });
  });

  group('toggleListPrefix', () {
    test('toggles ON for a single line the cursor is on', () {
      final value = const TextEditingValue(
        text: 'buy soil',
        selection: TextSelection.collapsed(offset: 3),
      );
      final result = toggleListPrefix(value);
      expect(result.text, '- buy soil');
    });

    test('toggles ON for every line a multi-line selection touches', () {
      final value = const TextEditingValue(
        text: 'line1\nline2\nline3',
        // Selection spans from line1 into line2 only.
        selection: TextSelection(baseOffset: 2, extentOffset: 8),
      );
      final result = toggleListPrefix(value);
      expect(result.text, '- line1\n- line2\nline3');
    });

    test('only the lines the selection touches are affected — lines '
        'before/after the touched range are untouched', () {
      final value = const TextEditingValue(
        text: 'before\nmiddle\nafter',
        selection: TextSelection.collapsed(offset: 10), // inside "middle"
      );
      final result = toggleListPrefix(value);
      expect(result.text, 'before\n- middle\nafter');
    });

    test('toggles OFF only when EVERY touched line already has the prefix', () {
      final value = const TextEditingValue(
        text: '- one\n- two',
        selection: TextSelection(baseOffset: 0, extentOffset: 11),
      );
      final result = toggleListPrefix(value);
      expect(result.text, 'one\ntwo');
    });

    test('a mix of prefixed and unprefixed touched lines toggles ON — only '
        'the lines lacking the prefix gain it, the already-prefixed line is '
        'untouched', () {
      final value = const TextEditingValue(
        text: '- one\ntwo',
        selection: TextSelection(baseOffset: 0, extentOffset: 9),
      );
      final result = toggleListPrefix(value);
      expect(result.text, '- one\n- two');
    });

    test('an invalid (out of range) selection is a no-op', () {
      const value = TextEditingValue(
        text: 'x',
        selection: TextSelection(baseOffset: -1, extentOffset: -1),
      );
      expect(toggleListPrefix(value), same(value));
    });
  });

  group('ForumRichTextToolbar widget', () {
    testWidgets('renders its buttons without nesting a TextField — keeps '
        'find.byType(TextField) unambiguous for composer-screen tests '
        '(the toolbar owns a link dialog with its own text input, deliberately '
        'not a Material TextField)', (tester) async {
      final controller = TextEditingController();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                ForumRichTextToolbar(controller: controller),
                TextField(controller: controller),
              ],
            ),
          ),
        ),
      );

      // Exactly one TextField in the tree: the composer's own body field.
      expect(find.byType(TextField), findsOneWidget);
      expect(find.byIcon(Icons.format_bold), findsOneWidget);
      expect(find.byIcon(Icons.format_italic), findsOneWidget);
      expect(find.byIcon(Icons.code), findsOneWidget);
      expect(find.byIcon(Icons.link), findsOneWidget);
      expect(find.byIcon(Icons.format_list_bulleted), findsOneWidget);
    });

    testWidgets('tapping bold wraps the current selection in the body field', (
      tester,
    ) async {
      final controller = TextEditingController(text: 'hello world');
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                ForumRichTextToolbar(controller: controller),
                TextField(controller: controller),
              ],
            ),
          ),
        ),
      );

      controller.selection = const TextSelection(
        baseOffset: 6,
        extentOffset: 11,
      );
      await tester.tap(find.byIcon(Icons.format_bold));
      await tester.pump();

      expect(controller.text, 'hello **world**');
    });
  });
}
