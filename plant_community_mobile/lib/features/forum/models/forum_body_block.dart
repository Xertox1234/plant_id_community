/// Parsed StreamField body blocks for forum topics/posts.
///
/// Mirrors the backend on-read shape (`FORUM_BODY_SCHEMA`,
/// `wagtail_forum/api/serializers.py`): a JSON array of
/// `{type, value, id}`. The permitted block types are
/// `heading`, `paragraph`, `quote`, `code`, `image`, `embed` (`blocks.py`).
///
/// Per-type `value` on read:
/// - `heading`  → plain string
/// - `paragraph`→ sanitized HTML string
/// - `quote`    → plain string (defensively also accepts the web's
///                `{quote_text|quote, attribution}` object)
/// - `post_quote` → `{text, post_id, available, topic_id, author,
///                is_blocked, is_muted}` (todo 342): a quote OF A SPECIFIC
///                POST. `text` is plain text by the same contract as
///                `quote`; the attribution is resolved server-side and
///                `available` is `false` (no author/topic) once the quoted
///                post is gone — the text still renders. `is_blocked` /
///                `is_muted` say the VIEWER blocked / muted the quoted
///                author (both `false` for an anonymous viewer) — the card
///                collapses like a blocked post, never hides.
/// - `code`     → `{language, code}` object
/// - `image`    → `{id, url, alt, width, height}` object, or `null` when the
///                referenced image was deleted after posting
/// - `embed`    → `{url, provider_name, title, thumbnail_url, embed_url}`
///                (todo 344): a video link the server unfurled. Mobile
///                renders a thumbnail card — no WebView, no provider HTML.
///
/// Unknown block types are preserved as [UnknownBlock] and rendered as a
/// graceful fallback, mirroring the web renderer's `default:` case, rather
/// than crashing the whole body.
library;

import 'package:html/parser.dart' as html_parser;

import 'forum_author.dart';
import 'forum_rich_text_markup.dart';

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
      case 'post_quote':
        return PostQuoteBlock.fromJson(
          value is Map<String, dynamic> ? value : const <String, dynamic>{},
        );
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
      case 'embed':
        if (value is Map<String, dynamic>) {
          return EmbedBlock(
            url: value['url'] as String? ?? '',
            providerName: value['provider_name'] as String? ?? '',
            title: value['title'] as String? ?? '',
            thumbnailUrl: value['thumbnail_url'] as String? ?? '',
          );
        }
        // A pre-unfurl client could only have sent the bare URL.
        return EmbedBlock(url: value is String ? value : '');
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

/// `quote` → plain string. The legacy free-form quote; the "Quote" action
/// writes a [PostQuoteBlock] since todo 342, but older bodies still carry
/// these.
class QuoteBlock extends ForumBodyBlock {
  const QuoteBlock(this.text);
  final String text;
}

/// `post_quote` on read (todo 342): the quoted text plus the server-resolved
/// attribution. [text] is PLAIN TEXT — render it as text, never as markup.
/// When [available] is `false` the quoted post is gone (unpublished, hidden,
/// deleted, or its board no longer visible) and [author]/[topicId] are
/// `null`; the text still renders, only the attribution changes.
class PostQuoteBlock extends ForumBodyBlock {
  const PostQuoteBlock({
    required this.text,
    required this.postId,
    required this.available,
    this.topicId,
    this.author,
    this.isBlocked = false,
    this.isMuted = false,
  });

  final String text;

  /// The quoted post's id — `null` only for a malformed envelope.
  final int? postId;
  final bool available;
  final int? topicId;
  final ForumAuthor? author;

  /// `true` when the VIEWER has blocked the quoted author (todo 284/347 on
  /// the post; here the quote card collapses the same way). Always `false`
  /// for an anonymous viewer, and absent from older envelopes.
  final bool isBlocked;

  /// `true` when the VIEWER has muted the quoted author — the softer
  /// relation; collapses with its own wording. Blocked wins when both.
  final bool isMuted;

  factory PostQuoteBlock.fromJson(Map<String, dynamic> json) {
    final author = json['author'];
    return PostQuoteBlock(
      text: json['text'] as String? ?? '',
      postId: json['post_id'] as int?,
      available: json['available'] as bool? ?? false,
      topicId: json['topic_id'] as int?,
      author: author is Map<String, dynamic>
          ? ForumAuthor.fromJson(author)
          : null,
      isBlocked: json['is_blocked'] as bool? ?? false,
      isMuted: json['is_muted'] as bool? ?? false,
    );
  }
}

/// `code` → `{language, code}`.
class CodeBlock extends ForumBodyBlock {
  const CodeBlock({required this.code, required this.language});
  final String code;
  final String language;
}

/// `image` with a live rendition.
///
/// Also doubles as the shape of `POST /forum/images/`'s upload response
/// (`{id, url, alt, width, height}`, un-nested — [fromUploadResponse]) since
/// the fields are identical; the read-body `value` object and the upload
/// response are two different backend endpoints that happen to serialize the
/// same way.
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

  factory ForumImageBlock.fromUploadResponse(Map<String, dynamic> json) {
    return ForumImageBlock(
      id: json['id'] as int? ?? 0,
      url: json['url'] as String? ?? '',
      alt: json['alt'] as String? ?? '',
      width: json['width'] as int?,
      height: json['height'] as int?,
    );
  }
}

/// `image` whose referenced image row was deleted (`value == null`).
class DeletedImageBlock extends ForumBodyBlock {
  const DeletedImageBlock();
}

/// A video link the server unfurled (todo 344). `embedUrl` is deliberately
/// not carried: mobile shows a thumbnail card with the provider and title,
/// never an inline player — see the renderer.
class EmbedBlock extends ForumBodyBlock {
  const EmbedBlock({
    required this.url,
    this.providerName = '',
    this.title = '',
    this.thumbnailUrl = '',
  });
  final String url;
  final String providerName;
  final String title;
  final String thumbnailUrl;
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

/// Build the write-shape `body` payload for a composer input that may
/// contain the five marker-syntax marks (bold/italic/link/inline-code/list —
/// todo 314). The whole input becomes a single `paragraph` block whose value
/// is [generateForumRichHtml]'s HTML (plain text with no markers produces
/// the same HTML-escaped-text-plus-`<br>` shape this function always
/// produced). The server sanitizes it (nh3 allowlist) on write. Returns an
/// empty list for blank input.
List<Map<String, dynamic>> buildParagraphBody(String text) {
  final trimmed = text.trim();
  if (trimmed.isEmpty) return const [];
  return [
    {'type': 'paragraph', 'value': generateForumRichHtml(trimmed)},
  ];
}

/// Write-shape `post_quote` block (todo 342): `{post, text}` — the quoted
/// post's id and plain text. Per `blocks.py` (`PostQuoteBlock`) and
/// `api/sanitize.py`, [text] is plain text the server leaves untouched by
/// contract — consumers escape it at render time — so it goes in verbatim,
/// never HTML-escaped here. The server validates the rest on write: the
/// quoted post must be visible to the writer and not block-paired, at most
/// three distinct posts per body, non-empty text of at most 1000 chars —
/// each a 400 with its own sentence, never a silent strip. Callers pass a
/// non-blank [text] (see `forumQuoteDraft`).
Map<String, dynamic> buildPostQuoteBlockBody(int postId, String text) {
  return {
    'type': 'post_quote',
    'value': {'post': postId, 'text': text.trim()},
  };
}

/// Reader-visible plain text of a body, for quoting it (todo 341 wave 3).
///
/// Headings, paragraphs (HTML → text: `<br>`/`</p>`/`</li>` become line
/// breaks, every tag is dropped, entities are decoded by the parser) and
/// code blocks contribute their text, joined by blank lines. Everything else
/// is dropped: an existing `quote`/`post_quote` block (quoting a reply must
/// not nest its own quotation — the same convention Discourse applies),
/// images, embeds, deleted images and unknown blocks (nothing a reader
/// could re-read).
String forumBodyPlainText(List<ForumBodyBlock> blocks) {
  final parts = <String>[];
  for (final block in blocks) {
    final text = switch (block) {
      HeadingBlock(:final text) => text,
      ParagraphBlock(:final html) => _paragraphHtmlToText(html),
      CodeBlock(:final code) => code,
      QuoteBlock() ||
      PostQuoteBlock() ||
      ForumImageBlock() ||
      DeletedImageBlock() ||
      EmbedBlock() ||
      UnknownBlock() => '',
    }.trim();
    if (text.isNotEmpty) parts.add(text);
  }
  return parts.join('\n\n');
}

String _paragraphHtmlToText(String html) {
  final withBreaks = html
      .replaceAll(RegExp(r'<br\s*/?>', caseSensitive: false), '\n')
      .replaceAll(RegExp(r'</(p|li)>', caseSensitive: false), '\n');
  final text = html_parser.parseFragment(withBreaks).text ?? '';
  // Collapse the runs of blank lines the separators above can produce.
  return text.replaceAll(RegExp(r'\n{3,}'), '\n\n').trim();
}

/// Write-shape `image` block, referencing an already-uploaded image's id.
///
/// Per `api/sanitize.py::validate_forum_body`, the write VALUE is the bare
/// integer PK — NOT the `{id, url, alt, width, height}` object the
/// read/upload-response shape uses. Getting this wrong fails only server-side
/// (a client-side fake would happily accept either shape).
Map<String, dynamic> buildImageBlockBody(int imageId) {
  return {'type': 'image', 'value': imageId};
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
///
/// The final [escapeMarkerChars] step (todo 314) backslash-escapes any of
/// the marker grammar's delimiter characters that happen to already be
/// present in the plain text, so re-running [generateForumRichHtml] on the
/// reconstructed text can never misread them as real markers.
String plainTextFromParagraphHtml(String html) {
  // Mirror image of the old escaping's replacement order: <br> back to
  // newlines, then unescape entities in the REVERSE of the order they were
  // escaped in (quote/apostrophe/angle-brackets first, `&amp;` last) so a
  // literal `&` in the original text — which became a lone `&amp;` — isn't
  // corrupted by an earlier unescape step reinterpreting part of it.
  final unescaped = html
      .replaceAll('<br>', '\n')
      .replaceAll('&#39;', "'")
      .replaceAll('&quot;', '"')
      .replaceAll('&gt;', '>')
      .replaceAll('&lt;', '<')
      .replaceAll('&amp;', '&');
  return escapeMarkerChars(unescaped);
}
