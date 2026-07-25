import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:html/dom.dart' as dom;
import 'package:html/parser.dart' as html_parser;

/// Renders a forum `paragraph` block's sanitized HTML into styled text.
///
/// The server sanitizes paragraph HTML to the forum nh3 allowlist, mirrored by
/// the web `FORUM` DOMPurify preset — `p, br, strong/b, em/i, a, ul, ol, li,
/// code, span.mention`. This renderer walks that (already-safe) DOM into
/// [TextSpan]s: bold/italic/inline-code get text styles, links become tappable
/// (via [onOpenLink]), `<span class="mention">` is tinted, and block elements
/// (`p`, `br`, `li`) introduce line breaks. Anything outside the allowlist
/// contributes its text only, never raw markup.
class ForumHtmlText extends StatefulWidget {
  const ForumHtmlText(this.html, {super.key, this.onOpenLink});

  final String html;

  /// Called with the `href` when a link is tapped. When null, links render
  /// styled but inert.
  final void Function(String href)? onOpenLink;

  @override
  State<ForumHtmlText> createState() => _ForumHtmlTextState();
}

class _ForumHtmlTextState extends State<ForumHtmlText> {
  final List<TapGestureRecognizer> _recognizers = [];

  @override
  void dispose() {
    for (final r in _recognizers) {
      r.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Recognizers are rebuilt every build; dispose the previous batch first so
    // they don't accumulate across rebuilds (scroll, theme change).
    for (final r in _recognizers) {
      r.dispose();
    }
    _recognizers.clear();

    final theme = Theme.of(context);
    final baseStyle =
        theme.textTheme.bodyMedium ?? const TextStyle(fontSize: 14);
    final fragment = html_parser.parseFragment(widget.html);
    final spans = <InlineSpan>[];
    for (final node in fragment.nodes) {
      _appendNode(node, baseStyle, theme, spans);
    }
    return Text.rich(TextSpan(children: spans, style: baseStyle));
  }

  void _appendNode(
    dom.Node node,
    TextStyle style,
    ThemeData theme,
    List<InlineSpan> out,
  ) {
    if (node is dom.Text) {
      out.add(TextSpan(text: node.text, style: style));
      return;
    }
    if (node is! dom.Element) return;

    final tag = node.localName;
    switch (tag) {
      case 'br':
        out.add(const TextSpan(text: '\n'));
        return;
      case 'p':
        if (out.isNotEmpty) out.add(const TextSpan(text: '\n\n'));
        _appendChildren(node, style, theme, out);
        return;
      case 'strong':
      case 'b':
        _appendChildren(
          node,
          style.copyWith(fontWeight: FontWeight.bold),
          theme,
          out,
        );
        return;
      case 'em':
      case 'i':
        _appendChildren(
          node,
          style.copyWith(fontStyle: FontStyle.italic),
          theme,
          out,
        );
        return;
      case 'code':
        _appendChildren(
          node,
          style.copyWith(
            fontFamily: 'monospace',
            backgroundColor: theme.colorScheme.surfaceContainerHighest,
          ),
          theme,
          out,
        );
        return;
      case 'a':
        final href = node.attributes['href'];
        final linkStyle = style.copyWith(
          color: theme.colorScheme.primary,
          decoration: TextDecoration.underline,
        );
        final onOpen = widget.onOpenLink;
        TapGestureRecognizer? recognizer;
        if (href != null && href.isNotEmpty && onOpen != null) {
          recognizer = TapGestureRecognizer()..onTap = () => onOpen(href);
          _recognizers.add(recognizer);
        }
        // Links may wrap styled children; render their text with the link
        // style and attach the tap recognizer.
        out.add(
          TextSpan(text: node.text, style: linkStyle, recognizer: recognizer),
        );
        return;
      case 'ul':
      case 'ol':
        for (final li in node.children.where((e) => e.localName == 'li')) {
          if (out.isNotEmpty) out.add(const TextSpan(text: '\n'));
          out.add(TextSpan(text: '•  ', style: style));
          _appendChildren(li, style, theme, out);
        }
        return;
      case 'span':
        final isMention = (node.attributes['class'] ?? '').contains('mention');
        _appendChildren(
          node,
          isMention
              ? style.copyWith(
                  color: theme.colorScheme.primary,
                  fontWeight: FontWeight.w600,
                )
              : style,
          theme,
          out,
        );
        return;
      default:
        // Unknown/other tags: contribute their text content only.
        _appendChildren(node, style, theme, out);
        return;
    }
  }

  void _appendChildren(
    dom.Node node,
    TextStyle style,
    ThemeData theme,
    List<InlineSpan> out,
  ) {
    for (final child in node.nodes) {
      _appendNode(child, style, theme, out);
    }
  }
}
