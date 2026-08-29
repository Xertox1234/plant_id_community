import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/forum_rich_text_markup.dart';
import 'package:plant_community_mobile/features/forum/models/forum_body_block.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_html_text.dart';

/// A flattened (text, style, href) tuple from a [ForumHtmlText]'s rendered
/// [TextSpan] tree — enough to assert render-equivalence between two HTML
/// strings without depending on byte-identical markup (the todo-314 brief's
/// explicit, deliberate refinement: the server force-sets `rel` on every
/// `<a>` on save, so byte-identity was never a true property of the
/// generate(parse()) direction).
class _FlatSpan {
  const _FlatSpan(
    this.text, {
    this.bold = false,
    this.italic = false,
    this.code = false,
    this.href,
  });
  final String text;
  final bool bold;
  final bool italic;
  final bool code;
  final String? href;

  @override
  bool operator ==(Object other) =>
      other is _FlatSpan &&
      other.text == text &&
      other.bold == bold &&
      other.italic == italic &&
      other.code == code &&
      other.href == href;

  @override
  int get hashCode => Object.hash(text, bold, italic, code, href);

  @override
  String toString() =>
      '_FlatSpan("$text", bold: $bold, italic: $italic, code: $code, href: $href)';
}

/// Pumps [html] through [ForumHtmlText] and flattens the resulting
/// [TextSpan] tree into a list of (text, style, href) tuples for
/// render-equivalence comparisons.
Future<List<_FlatSpan>> _render(WidgetTester tester, String html) async {
  final tappedHrefs = <String>[];
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: ForumHtmlText(html, onOpenLink: tappedHrefs.add)),
    ),
  );
  await tester.pump();

  final textRich = tester.widget<Text>(find.byType(Text));
  final rootSpan = textRich.textSpan as TextSpan;
  final out = <_FlatSpan>[];

  void visit(InlineSpan span) {
    if (span is TextSpan) {
      final style = span.style;
      final text = span.text;
      if (text != null && text.isNotEmpty) {
        String? href;
        if (span.recognizer is TapGestureRecognizer) {
          // Trigger the tap to recover which href this span is wired to.
          tappedHrefs.clear();
          (span.recognizer as TapGestureRecognizer).onTap?.call();
          if (tappedHrefs.isNotEmpty) href = tappedHrefs.first;
        }
        out.add(
          _FlatSpan(
            text,
            bold: style?.fontWeight == FontWeight.bold,
            italic: style?.fontStyle == FontStyle.italic,
            code: style?.fontFamily == 'monospace',
            href: href,
          ),
        );
      }
      span.children?.forEach(visit);
    }
  }

  visit(rootSpan);
  return out;
}

void main() {
  group('generateForumRichHtml', () {
    test('bold — emits <strong>, not <b>', () {
      final html = generateForumRichHtml('a **bold** word');
      expect(html, 'a <strong>bold</strong> word');
      expect(html, isNot(contains('<b>')));
    });

    test('italic — emits <em>, not <i>', () {
      final html = generateForumRichHtml('a _italic_ word');
      expect(html, 'a <em>italic</em> word');
      expect(html, isNot(contains('<i>')));
    });

    test('inline code', () {
      final html = generateForumRichHtml('a `code` word');
      expect(html, 'a <code>code</code> word');
    });

    test('link', () {
      final html = generateForumRichHtml('a [text](https://example.com) word');
      expect(html, 'a <a href="https://example.com">text</a> word');
    });

    test('list — bulleted lines become <ul><li>', () {
      final html = generateForumRichHtml('- one\n- two');
      expect(html, '<ul><li>one</li><li>two</li></ul>');
    });

    test('never emits <ol>', () {
      final html = generateForumRichHtml('- one\n- two');
      expect(html, isNot(contains('<ol>')));
    });

    test('plain text with no markers is HTML-escaped, no tags added', () {
      expect(generateForumRichHtml('a < b & c'), 'a &lt; b &amp; c');
    });

    test('newlines become <br> when no list lines are present', () {
      expect(generateForumRichHtml('line1\nline2'), 'line1<br>line2');
    });

    test('mixed text/list/text body — segments joined by <br>', () {
      final html = generateForumRichHtml('intro\n- item1\n- item2\noutro');
      expect(html, 'intro<br><ul><li>item1</li><li>item2</li></ul><br>outro');
    });

    test('a link with a disallowed scheme is left as literal text', () {
      final html = generateForumRichHtml('[click](javascript:alert(1))');
      expect(html, isNot(contains('<a ')));
    });

    test('an unterminated bold marker is left as literal text', () {
      expect(generateForumRichHtml('**not closed'), '**not closed');
    });
  });

  group('parseForumRichHtmlToMarkup — success', () {
    test('bold', () {
      expect(
        parseForumRichHtmlToMarkup('a <strong>bold</strong> word'),
        'a **bold** word',
      );
    });

    test('italic', () {
      expect(
        parseForumRichHtmlToMarkup('a <em>italic</em> word'),
        'a _italic_ word',
      );
    });

    test('inline code', () {
      expect(
        parseForumRichHtmlToMarkup('a <code>code</code> word'),
        'a `code` word',
      );
    });

    test('link', () {
      expect(
        parseForumRichHtmlToMarkup(
          'a <a href="https://example.com">text</a> word',
        ),
        'a [text](https://example.com) word',
      );
    });

    test('list', () {
      expect(
        parseForumRichHtmlToMarkup('<ul><li>one</li><li>two</li></ul>'),
        '- one\n- two',
      );
    });

    test('a single top-level <p> wrapper is treated as transparent', () {
      expect(
        parseForumRichHtmlToMarkup('<p>a <strong>bold</strong> word</p>'),
        'a **bold** word',
      );
    });

    test('mixed text/list/text round-trips through the parser', () {
      expect(
        parseForumRichHtmlToMarkup(
          'intro<br><ul><li>item1</li><li>item2</li></ul><br>outro',
        ),
        'intro\n- item1\n- item2\noutro',
      );
    });
  });

  group('parseForumRichHtmlToMarkup — failure (returns null)', () {
    test('unsupported nesting (marks nested within each other)', () {
      expect(parseForumRichHtmlToMarkup('<strong><em>x</em></strong>'), isNull);
    });

    test('an <a> with non-text children (matching ForumHtmlText\'s own '
        'flattening rule) is rejected', () {
      expect(
        parseForumRichHtmlToMarkup('<a href="/x"><strong>x</strong></a>'),
        isNull,
      );
    });

    test('<ol> is always rejected, even though ForumHtmlText renders it '
        'identically to <ul>', () {
      expect(parseForumRichHtmlToMarkup('<ol><li>a</li></ol>'), isNull);
    });

    test('unknown tags (e.g. a mention span) are rejected', () {
      expect(
        parseForumRichHtmlToMarkup('<span class="mention">@bob</span>'),
        isNull,
      );
    });

    test('a disallowed href is rejected, not silently dropped', () {
      expect(
        parseForumRichHtmlToMarkup('<a href="javascript:alert(1)">x</a>'),
        isNull,
      );
    });

    test('a literal backtick inside a code span is unrepresentable and '
        'rejected', () {
      expect(parseForumRichHtmlToMarkup('<code>a`b</code>'), isNull);
    });
  });

  group('escapeMarkerChars', () {
    test('escapes backslash, star, underscore, backtick, left-bracket', () {
      expect(escapeMarkerChars(r'a*b_c`d[e'), r'a\*b\_c\`d\[e');
    });

    test('escapes a leading hyphen on any line, not mid-line hyphens', () {
      expect(escapeMarkerChars('-lead'), r'\-lead');
      expect(escapeMarkerChars('mid-dash'), 'mid-dash');
      expect(escapeMarkerChars('line1\n-line2'), 'line1\n\\-line2');
    });

    test('a literal backslash is doubled, not left bare', () {
      expect(escapeMarkerChars('back\\slash'), r'back\\slash');
    });

    test('escaping the backslash happens before escaping other markers, so '
        'a marker char is never double-escaped', () {
      // '*' becomes '\*' — a single backslash, not '\\*' (which would mean
      // "a literal backslash followed by a literal star").
      expect(escapeMarkerChars('*'), r'\*');
    });
  });

  group('isAllowedForumLinkHref', () {
    test('allows http/https/mailto absolute URLs', () {
      expect(isAllowedForumLinkHref('https://example.com'), isTrue);
      expect(isAllowedForumLinkHref('http://example.com'), isTrue);
      expect(isAllowedForumLinkHref('mailto:a@example.com'), isTrue);
    });

    test('allows a single leading-slash relative path', () {
      expect(isAllowedForumLinkHref('/forum/topic/1'), isTrue);
    });

    test('rejects a protocol-relative //-prefixed URL', () {
      expect(isAllowedForumLinkHref('//evil.example.com'), isFalse);
    });

    test('rejects disallowed schemes', () {
      expect(isAllowedForumLinkHref('javascript:alert(1)'), isFalse);
      expect(isAllowedForumLinkHref('ftp://example.com'), isFalse);
      expect(isAllowedForumLinkHref('data:text/html,x'), isFalse);
    });

    test('rejects empty / whitespace-only input', () {
      expect(isAllowedForumLinkHref(''), isFalse);
      expect(isAllowedForumLinkHref('   '), isFalse);
    });
  });

  group('required invariant — generate(plainTextFromParagraphHtml(html)) '
      '== html, byte-identical, for every shape isSingleEditableParagraph '
      'already accepts', () {
    void checkRoundTrip(String html) {
      expect(isSingleEditableParagraph([ParagraphBlock(html)]), isTrue);
      final markerText = plainTextFromParagraphHtml(html);
      expect(generateForumRichHtml(markerText), html);
    }

    test('plain escaped text, no <br>', () {
      checkRoundTrip('a &lt; b &amp; c');
    });

    test('escaped text plus a real <br>', () {
      checkRoundTrip('a &lt; b &amp; c<br>line2');
    });

    test('literal "<br>" text, fully escaped (not a real line break)', () {
      checkRoundTrip('a &lt; b &amp; c&lt;br&gt;line2');
    });

    test('text containing marker-lookalike characters ( _ * ` [ )', () {
      checkRoundTrip('my_file * note `q` [x');
    });

    test('a line-leading hyphen — the exact case escapeMarkerChars\' '
        'leading-hyphen rule exists to protect: without it, this would be '
        'misread as a list line on regeneration', () {
      checkRoundTrip('- item<br>- item2');
    });

    test('quotes and ampersand entities round-trip without '
        'double-unescaping', () {
      checkRoundTrip(
        'a &amp;lt; tricky &quot;quote&quot; &#39;apostrophe&#39;',
      );
    });
  });

  group('required invariant — '
      'parseForumRichHtmlToMarkup(generateForumRichHtml(markerText)) == '
      'markerText, byte-identical, for representative marker text', () {
    void checkRoundTrip(String markerText) {
      final html = generateForumRichHtml(markerText);
      expect(parseForumRichHtmlToMarkup(html), markerText);
    }

    test('bold', () => checkRoundTrip('a **bold** word'));
    test('italic', () => checkRoundTrip('a _italic_ word'));
    test('code', () => checkRoundTrip('a `code` word'));
    test('link', () => checkRoundTrip('a [text](https://example.com) word'));
    test('list', () => checkRoundTrip('- one\n- two'));

    test('mixed text/list/text', () {
      checkRoundTrip('intro\n- item1\n- item2\noutro');
    });

    test('a properly-escaped literal backslash (the doubled `\\\\` form)', () {
      checkRoundTrip(r'back\\slash');
    });

    test('an escaped underscore INSIDE an italic span — the brief\'s '
        'flagship snake_case-in-<em> corruption case', () {
      checkRoundTrip(r'_ital\_ic_');
    });

    test('an escaped leading hyphen', () {
      checkRoundTrip(r'\-not a list item');
    });
  });

  group('required invariant — generate(parse(webAuthoredHtml)) is '
      'render-equivalent (not byte-identical — the server force-sets '
      '`rel` on every <a> on save, so byte-identity was never a true '
      'property of this direction)', () {
    testWidgets('a <p>-wrapped, web-authored post with bold/italic/link/'
        'code/list renders identically after being parsed and '
        're-generated', (tester) async {
      const webHtml =
          '<p>Check out <strong>this</strong> and <em>that</em>, plus '
          '<code>some code</code> and a '
          '<a href="https://example.com" rel="noopener noreferrer nofollow" '
          'target="_blank">link</a>.</p>';

      final markup = parseForumRichHtmlToMarkup(webHtml);
      expect(markup, isNotNull);
      final regenerated = generateForumRichHtml(markup!);

      final originalRendered = await _render(tester, webHtml);
      final regeneratedRendered = await _render(tester, regenerated);

      expect(regeneratedRendered, originalRendered);
    });

    testWidgets('the flagship escaping bug: a web post with '
        '<em>snake_case</em> re-renders identically after a parse+'
        'regenerate round trip (unescaped, this would corrupt to '
        'italic ending mid-word)', (tester) async {
      const webHtml = '<p>the <em>snake_case</em> variable</p>';

      final markup = parseForumRichHtmlToMarkup(webHtml);
      expect(markup, isNotNull);
      final regenerated = generateForumRichHtml(markup!);

      final originalRendered = await _render(tester, webHtml);
      final regeneratedRendered = await _render(tester, regenerated);

      expect(regeneratedRendered, originalRendered);
      // Belt and suspenders: the italic span's text is the whole word, not
      // truncated at the first real underscore.
      expect(
        regeneratedRendered.any((s) => s.italic && s.text == 'snake_case'),
        isTrue,
      );
    });
  });
}
