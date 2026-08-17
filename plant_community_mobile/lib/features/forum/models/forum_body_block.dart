/// Parsed StreamField body blocks for forum topics/posts.
///
/// Mirrors the backend on-read shape (`FORUM_BODY_SCHEMA`,
/// `wagtail_forum/api/serializers.py`): a JSON array of
/// `{type, value, id}`. The permitted block types are
/// `heading`, `paragraph`, `quote`, `code`, `image` (`blocks.py`).
///
/// Per-type `value` on read:
/// - `heading`  → plain string
/// - `paragraph`→ sanitized HTML string
/// - `quote`    → plain string (defensively also accepts the web's
///                `{quote_text|quote, attribution}` object)
/// - `code`     → `{language, code}` object
/// - `image`    → `{id, url, alt, width, height}` object, or `null` when the
///                referenced image was deleted after posting
///
/// Unknown block types are preserved as [UnknownBlock] and rendered as a
/// graceful fallback, mirroring the web renderer's `default:` case, rather
/// than crashing the whole body.
sealed class ForumBodyBlock {
  const ForumBodyBlock();

  factory ForumBodyBlock.fromJson(Map<String, dynamic> json) {
    final type = json['type'] as String? ?? '';
    final value = json['value'];
    switch (type) {
      case 'heading':
        return HeadingBlock(value is String ? value : '');
      case 'paragraph':
        return ParagraphBlock(value is String ? value : '');
      case 'quote':
        return QuoteBlock(_quoteText(value));
      case 'code':
        final map = value is Map<String, dynamic>
            ? value
            : const <String, dynamic>{};
        return CodeBlock(
          code: map['code'] as String? ?? '',
          language: map['language'] as String? ?? '',
        );
      case 'image':
        if (value is Map<String, dynamic>) {
          return ForumImageBlock(
            id: value['id'] as int? ?? 0,
            url: value['url'] as String? ?? '',
            alt: value['alt'] as String? ?? '',
            width: value['width'] as int?,
            height: value['height'] as int?,
          );
        }
        // value == null → the image row was deleted after posting.
        return const DeletedImageBlock();
      default:
        return UnknownBlock(type);
    }
  }

  static String _quoteText(dynamic value) {
    if (value is String) return value;
    if (value is Map<String, dynamic>) {
      return value['quote_text'] as String? ?? value['quote'] as String? ?? '';
    }
    return '';
  }
}

/// `heading` → plain string.
class HeadingBlock extends ForumBodyBlock {
  const HeadingBlock(this.text);
  final String text;
}

/// `paragraph` → sanitized HTML string (rendered via the forum HTML renderer).
class ParagraphBlock extends ForumBodyBlock {
  const ParagraphBlock(this.html);
  final String html;
}

/// `quote` → plain string.
class QuoteBlock extends ForumBodyBlock {
  const QuoteBlock(this.text);
  final String text;
}

/// `code` → `{language, code}`.
class CodeBlock extends ForumBodyBlock {
  const CodeBlock({required this.code, required this.language});
  final String code;
  final String language;
}

/// `image` with a live rendition.
class ForumImageBlock extends ForumBodyBlock {
  const ForumImageBlock({
    required this.id,
    required this.url,
    required this.alt,
    this.width,
    this.height,
  });
  final int id;
  final String url;
  final String alt;
  final int? width;
  final int? height;
}

/// `image` whose referenced image row was deleted (`value == null`).
class DeletedImageBlock extends ForumBodyBlock {
  const DeletedImageBlock();
}

/// A block type the client does not recognise — preserved for a fallback
/// render instead of dropping the whole body.
class UnknownBlock extends ForumBodyBlock {
  const UnknownBlock(this.type);
  final String type;
}

/// Parse a raw body array (`List<dynamic>` of `{type, value, id}` maps) into
/// typed blocks. Non-map entries are skipped defensively.
List<ForumBodyBlock> parseForumBody(dynamic raw) {
  if (raw is! List) return const [];
  return raw
      .whereType<Map<String, dynamic>>()
      .map(ForumBodyBlock.fromJson)
      .toList(growable: false);
}

/// Build the write-shape `body` payload for a plain-text composer input.
///
/// The mobile composer is text-first: the whole input becomes a single
/// `paragraph` block whose value is HTML-escaped text with newlines mapped to
/// `<br>`. The server sanitizes it (nh3 allowlist) on write. Returns an empty
/// list for blank input.
List<Map<String, dynamic>> buildParagraphBody(String text) {
  final trimmed = text.trim();
  if (trimmed.isEmpty) return const [];
  final escaped = _escapeHtml(trimmed).replaceAll('\n', '<br>');
  return [
    {'type': 'paragraph', 'value': escaped},
  ];
}

String _escapeHtml(String input) {
  return input
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
}

/// True when [body] is exactly the shape the mobile composer itself can
/// produce: one `paragraph` block WHOSE HTML CONTAINS NOTHING BUT
/// [buildParagraphBody]'s own escaping (todo 292). The mobile composer is
/// text-first (todo 294 tracks images/rich-text authoring) — a body outside
/// this shape cannot be edited here without losing content, so callers must
/// gate mobile editing on this rather than assuming every editable post
/// round-trips through plain text.
///
/// Block SHAPE alone is not enough (code review — a real, reproduced gap):
/// a web-authored post using only inline marks (bold/italic/links/lists, no
/// image, no top-level blockquote) collapses to exactly ONE `paragraph`
/// block too, but its HTML is real markup (e.g. `<strong>`, `<a href=...>`),
/// not [buildParagraphBody]'s escaped-text-plus-`<br>` shape. Without this
/// tag check, that markup would silently show as literal `&lt;strong&gt;`
/// tag soup in the edit field with NO warning, and saving would burn it in
/// permanently. `buildParagraphBody` only ever emits `<br>` as a literal
/// tag — every other `<`/`>` in its output is escaped — so stripping every
/// `<br>` and checking for a leftover `<` or `>` is an exact test for "this
/// HTML could only have come from the mobile composer or plain re-escaped
/// text", not merely "this is one paragraph block".
bool isSingleEditableParagraph(List<ForumBodyBlock> body) {
  if (body.length != 1) return false;
  final block = body.first;
  if (block is! ParagraphBlock) return false;
  return !block.html.replaceAll('<br>', '').contains(RegExp('[<>]'));
}

/// Reverse of [buildParagraphBody]'s escaping, for pre-filling the edit
/// composer's plain-text field from an existing single paragraph's HTML.
/// Only meaningful when [isSingleEditableParagraph] is true for the body
/// this came from — callers must check that first.
String plainTextFromParagraphHtml(String html) {
  // Mirror image of _escapeHtml's replacement order: <br> back to newlines,
  // then unescape entities in the REVERSE of the order they were escaped in
  // (quote/apostrophe/angle-brackets first, `&amp;` last) so a literal `&`
  // in the original text — which became a lone `&amp;` — isn't corrupted by
  // an earlier unescape step reinterpreting part of it.
  return html
      .replaceAll('<br>', '\n')
      .replaceAll('&#39;', "'")
      .replaceAll('&quot;', '"')
      .replaceAll('&gt;', '>')
      .replaceAll('&lt;', '<')
      .replaceAll('&amp;', '&');
}
