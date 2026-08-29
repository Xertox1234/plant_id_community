/// Marker-syntax <-> HTML conversion for the mobile forum composer's rich
/// text (todo 314): bold (`**text**`), italic (`_text_`), inline code
/// (`` `text` ``), links (`[text](url)`), and bulleted lists (`- ` per
/// line) — the five marks [ForumHtmlText] already renders on read.
///
/// [generateForumRichHtml] converts composer marker text to the HTML string
/// stored as a `paragraph` block's `value` (mirroring the shape
/// [buildParagraphBody] already produced for plain text — no wrapping `<p>`,
/// since the block TYPE already conveys "paragraph").
///
/// [parseForumRichHtmlToMarkup] is the inverse, used to make an existing
/// post's body editable again: it accepts HTML **only** in the closed
/// grammar the generator itself emits (the five marks, no nesting beyond
/// what's supported, no other tags) plus one transparent top-level `<p>`
/// wrapper (web-authored paragraph values are `<p>`-wrapped —
/// `web/src/components/forum/TipTapEditor.tsx` — and [ForumHtmlText]'s own
/// `<p>` handling only inserts a separator when prior output is non-empty,
/// so a single top-level `<p>` renders identically to a bare fragment).
/// Anything outside that grammar returns `null`, so callers fall back to the
/// existing plain-text/warning-banner path — nothing new is trusted, since
/// the server re-sanitizes on every save regardless of origin.
///
/// Escaping: a mark delimiter appearing literally inside reconstructed plain
/// text (e.g. an underscore inside `<em>snake_case</em>`) would otherwise
/// falsely re-delimit on the next [generateForumRichHtml] pass, silently
/// corrupting content on re-save. [escapeMarkerChars] backslash-escapes the
/// five delimiter characters (plus a line-leading `-`, which would otherwise
/// be misread as a list prefix) everywhere plain text is reconstructed from
/// HTML. [generateForumRichHtml] mirrors this: it substitutes every escaped
/// sequence for a private-use-area sentinel *before* its tokenizer regexes
/// run (so an escaped delimiter can never falsely close/open a real one),
/// and restores the sentinels to literal characters only in the final leaf
/// text, right before HTML-escaping.
library;

import 'package:html/dom.dart' as dom;
import 'package:html/parser.dart' as html_parser;

// Private-use-area sentinels — one per escapable character. Substituted in
// before tokenizing, restored to the literal character only in a leaf's
// final text, so an escaped delimiter can never be mistaken for a real one.
const _sentinelBackslash = '';
const _sentinelStar = '';
const _sentinelUnderscore = '';
const _sentinelBacktick = '';
const _sentinelBracket = '';
const _sentinelHyphen = '';

final _codeRe = RegExp('`([^`]+)`');
final _boldRe = RegExp(r'\*\*(.+?)\*\*');
final _italicRe = RegExp(r'_(.+?)_');
final _linkRe = RegExp(r'\[(.+?)\]\((.+?)\)');

/// Backslash-escapes the marker-grammar's delimiter characters (`\`, `*`,
/// `_`, `` ` ``, `[`) wherever they appear, plus a `-` that is the first
/// character of any line (which [generateForumRichHtml] would otherwise
/// treat as a list prefix). The backslash itself is escaped first so a
/// character escaped by this pass is never re-escaped by a later one.
String escapeMarkerChars(String text) {
  final backslashed = text.replaceAll('\\', '\\\\');
  final markersEscaped = backslashed.replaceAllMapped(
    RegExp(r'[*_`\[]'),
    (m) => '\\${m[0]}',
  );
  return markersEscaped.replaceAllMapped(
    RegExp(r'^-', multiLine: true),
    (m) => '\\-',
  );
}

/// Mirrors web's `isAllowedLinkHref`
/// (`web/src/components/forum/TipTapEditor.tsx`): a trimmed non-empty
/// value; a single leading `/` (not `//`) is allowed; otherwise it must
/// parse as an absolute URI with scheme `http`, `https`, or `mailto`.
bool isAllowedForumLinkHref(String url) {
  final trimmed = url.trim();
  if (trimmed.isEmpty) return false;
  if (trimmed.startsWith('/') && !trimmed.startsWith('//')) return true;
  final uri = Uri.tryParse(trimmed);
  if (uri == null || !uri.isAbsolute) return false;
  return uri.scheme == 'http' ||
      uri.scheme == 'https' ||
      uri.scheme == 'mailto';
}

String _escapeHtml(String input) {
  return input
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
}

String _sentinelSubstitute(String text) {
  var result = text.replaceAll('\\\\', _sentinelBackslash);
  result = result.replaceAll('\\*', _sentinelStar);
  result = result.replaceAll('\\_', _sentinelUnderscore);
  result = result.replaceAll('\\`', _sentinelBacktick);
  result = result.replaceAll('\\[', _sentinelBracket);
  result = result.replaceAllMapped(
    RegExp(r'^\\-', multiLine: true),
    (m) => _sentinelHyphen,
  );
  return result;
}

String _restoreSentinels(String text) {
  return text
      .replaceAll(_sentinelBackslash, '\\')
      .replaceAll(_sentinelStar, '*')
      .replaceAll(_sentinelUnderscore, '_')
      .replaceAll(_sentinelBacktick, '`')
      .replaceAll(_sentinelBracket, '[')
      .replaceAll(_sentinelHyphen, '-');
}

/// Restore sentinels to their literal characters, then HTML-escape — the
/// final step for any leaf plain text the generator emits.
String _restoreAndEscape(String text) => _escapeHtml(_restoreSentinels(text));

/// Render one line's inline marks (bold/italic/code/link) to HTML. Marks do
/// not nest — content captured inside a mark is always plain text, restored
/// and HTML-escaped, never re-tokenized.
String _renderInline(String line) {
  final buffer = StringBuffer();
  var pos = 0;
  while (pos < line.length) {
    Match? earliest;
    String? kind;
    for (final pair in [
      (_codeRe, 'code'),
      (_boldRe, 'bold'),
      (_italicRe, 'italic'),
      (_linkRe, 'link'),
    ]) {
      final matches = pair.$1.allMatches(line, pos);
      if (matches.isEmpty) continue;
      final m = matches.first;
      if (earliest == null || m.start < earliest.start) {
        earliest = m;
        kind = pair.$2;
      }
    }
    if (earliest == null) {
      buffer.write(_restoreAndEscape(line.substring(pos)));
      break;
    }
    if (earliest.start > pos) {
      buffer.write(_restoreAndEscape(line.substring(pos, earliest.start)));
    }
    switch (kind) {
      case 'code':
        buffer.write('<code>${_restoreAndEscape(earliest.group(1)!)}</code>');
      case 'bold':
        buffer.write(
          '<strong>${_restoreAndEscape(earliest.group(1)!)}</strong>',
        );
      case 'italic':
        buffer.write('<em>${_restoreAndEscape(earliest.group(1)!)}</em>');
      case 'link':
        final url = _restoreSentinels(earliest.group(2)!);
        if (isAllowedForumLinkHref(url)) {
          final text = _restoreAndEscape(earliest.group(1)!);
          buffer.write('<a href="${_escapeHtml(url)}">$text</a>');
        } else {
          buffer.write(
            _restoreAndEscape(line.substring(earliest.start, earliest.end)),
          );
        }
    }
    pos = earliest.end;
  }
  return buffer.toString();
}

class _Segment {
  _Segment({required this.isList, required this.lines});
  final bool isList;
  final List<String> lines;
}

/// Convert composer marker text to the HTML stored as a `paragraph` block's
/// `value`. Never wraps in `<p>` (the block type already conveys
/// "paragraph") and never emits `<ol>` — [ForumHtmlText] renders `<ul>`/
/// `<ol>` identically, so there is no distinct "ordered list" output.
String generateForumRichHtml(String markerText) {
  final substituted = _sentinelSubstitute(markerText);
  final lines = substituted.split('\n');

  final segments = <_Segment>[];
  for (final line in lines) {
    final isList = line.startsWith('- ');
    final content = isList ? line.substring(2) : line;
    if (segments.isNotEmpty && segments.last.isList == isList) {
      segments.last.lines.add(content);
    } else {
      segments.add(_Segment(isList: isList, lines: [content]));
    }
  }

  final htmlParts = <String>[];
  for (final segment in segments) {
    if (segment.isList) {
      final items = segment.lines.map((l) => '<li>${_renderInline(l)}</li>');
      htmlParts.add('<ul>${items.join()}</ul>');
    } else {
      htmlParts.add(segment.lines.map(_renderInline).join('<br>'));
    }
  }
  return htmlParts.join('<br>');
}

/// Returns the plain-text content of [node] if every child is a text node
/// (no nested elements) — the "plain text only" rule shared by every mark's
/// content and by `<a>` (matching [ForumHtmlText]'s own flattening of `<a>`
/// content via `node.text`). Returns `null` if any child is an element.
String? _plainTextOnly(dom.Element node) {
  final buffer = StringBuffer();
  for (final child in node.nodes) {
    if (child is dom.Text) {
      buffer.write(child.text);
    } else {
      return null;
    }
  }
  return buffer.toString();
}

/// Render a single mark element (`strong`/`em`/`code`/`a`) to marker text,
/// or a plain [dom.Text] node via [escapeMarkerChars]. Returns `null` for
/// anything outside that grammar (nested elements, disallowed hrefs, `<ol>`,
/// unknown tags, or a `<code>` whose text contains a literal backtick — not
/// representable in the single-backtick-delimited grammar).
String? _renderLineMarkup(List<dom.Node> nodes) {
  final buffer = StringBuffer();
  for (final node in nodes) {
    if (node is dom.Text) {
      buffer.write(escapeMarkerChars(node.text));
      continue;
    }
    if (node is! dom.Element) return null;
    switch (node.localName) {
      case 'strong':
        final text = _plainTextOnly(node);
        if (text == null || text.isEmpty) return null;
        buffer.write('**${escapeMarkerChars(text)}**');
      case 'em':
        final text = _plainTextOnly(node);
        if (text == null || text.isEmpty) return null;
        buffer.write('_${escapeMarkerChars(text)}_');
      case 'code':
        final text = _plainTextOnly(node);
        if (text == null || text.isEmpty || text.contains('`')) return null;
        buffer.write('`${escapeMarkerChars(text)}`');
      case 'a':
        final text = _plainTextOnly(node);
        if (text == null || text.isEmpty) return null;
        final href = node.attributes['href'];
        if (href == null || !isAllowedForumLinkHref(href)) return null;
        buffer.write('[${escapeMarkerChars(text)}]($href)');
      default:
        return null;
    }
  }
  return buffer.toString();
}

/// Parse [html] back to composer marker text, accepting only the exact
/// shape [generateForumRichHtml] emits (plus a transparent single top-level
/// `<p>` wrapper — see the library doc comment). Returns `null` on anything
/// outside that grammar.
String? parseForumRichHtmlToMarkup(String html) {
  final fragment = html_parser.parseFragment(html);
  var nodes = fragment.nodes;
  if (nodes.length == 1 &&
      nodes.first is dom.Element &&
      (nodes.first as dom.Element).localName == 'p') {
    nodes = (nodes.first as dom.Element).nodes;
  }

  final lines = <String>[];
  final buffer = StringBuffer();
  var justClosedList = false;

  for (final node in nodes) {
    if (node is dom.Text) {
      buffer.write(escapeMarkerChars(node.text));
      justClosedList = false;
      continue;
    }
    if (node is! dom.Element) return null;
    switch (node.localName) {
      case 'br':
        if (buffer.isEmpty && justClosedList) {
          justClosedList = false;
        } else {
          lines.add(buffer.toString());
          buffer.clear();
          justClosedList = false;
        }
      case 'strong':
      case 'em':
      case 'code':
      case 'a':
        final rendered = _renderLineMarkup([node]);
        if (rendered == null) return null;
        buffer.write(rendered);
        justClosedList = false;
      case 'ul':
        if (buffer.isNotEmpty) {
          lines.add(buffer.toString());
          buffer.clear();
        }
        for (final li in node.children) {
          if (li.localName != 'li') return null;
          final content = _renderLineMarkup(li.nodes);
          if (content == null) return null;
          lines.add('- $content');
        }
        justClosedList = true;
      default:
        return null;
    }
  }
  if (!(buffer.isEmpty && justClosedList)) {
    lines.add(buffer.toString());
  }
  return lines.join('\n');
}
