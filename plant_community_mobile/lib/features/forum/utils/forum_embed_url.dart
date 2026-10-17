/// Which lines of a composer draft the server will show as link cards
/// (todos 654, 655), so the composer can preview what readers will get.
library;

import 'package:html/dom.dart' as dom;
import 'package:html/parser.dart' as html_parser;

import '../models/forum_body_block.dart';
import '../models/forum_rich_text_markup.dart';

/// The most link cards one post can carry: the server's
/// `MAX_LINK_PREVIEWS_PER_BODY` (5), which todo 655 made the heuristic spam
/// limit's default too (`SPAM_MAX_LINKS`, owner decision 2026-10-17), so a
/// post with all five cards is not held. The lower of the two is the real
/// ceiling; both are 5.
const int kForumMaxLinkCardsPerPost = 5;

// `[^\s<>"'`]+` rather than `\S+`: a "link" carrying HTML meta-characters is
// never a provider URL. Copied from the web's `PROVIDER_VIDEO_URL`
// (web/src/utils/forumBody.ts).
final RegExp _providerVideoUrl = RegExp(
  r"""^https?:\/\/(?:(?:[-\w]+\.)?youtube\.com\/(?:watch\?[^\s<>"'`]+|shorts\/[^\s<>"'`]+|live\/[^\s<>"'`]+|v\/[^\s<>"'`]+)|youtu\.be\/[^\s<>"'`]+|(?:www\.)?vimeo\.com\/[^\s<>"'`]+)$""",
);

/// [text], trimmed, when it is exactly one YouTube or Vimeo video URL, else
/// `null`: a link the server embeds as a video, never shows as a card. The
/// web twin is `providerVideoUrl` (web/src/utils/forumBody.ts); both are
/// tested against the one case table in
/// `test/features/forum/support/video_url_cases.json`.
String? forumVideoUrlOf(String text) {
  final trimmed = text.trim();
  return _providerVideoUrl.hasMatch(trimmed) ? trimmed : null;
}

// Characters that end a sentence rather than a link, as the server trims
// them (`_trim_url`, wagtail_forum/api/sanitize.py).
const String _trailingPunctuation = '.,;:!?';
const Map<String, String> _closingBrackets = {')': '(', ']': '[', '}': '{'};

String _trimUrl(String url) {
  var trimmed = url;
  while (trimmed.isNotEmpty) {
    final last = trimmed[trimmed.length - 1];
    final opening = _closingBrackets[last];
    if (_trailingPunctuation.contains(last) ||
        (opening != null &&
            last.allMatches(trimmed).length >
                opening.allMatches(trimmed).length)) {
      trimmed = trimmed.substring(0, trimmed.length - 1);
    } else {
      break;
    }
  }
  return trimmed;
}

/// The text of one generated line, every tag read as a space (as the server
/// reads it), or `null` when the line holds code or a list: a URL there is a
/// code sample or a list item, never a card.
String? _lineText(String line) {
  final fragment = html_parser.parseFragment(generateForumRichHtml(line));
  final buffer = StringBuffer();
  bool visit(dom.Node node) {
    if (node is dom.Text) {
      buffer.write(node.text);
      return true;
    }
    if (node is dom.Element) {
      if (const {'code', 'ul', 'ol', 'li'}.contains(node.localName)) {
        return false;
      }
      buffer.write(' ');
      for (final child in node.nodes) {
        if (!visit(child)) return false;
      }
      buffer.write(' ');
    }
    return true;
  }

  for (final node in fragment.nodes) {
    if (!visit(node)) return null;
  }
  return buffer.toString().trim();
}

/// The links in composer [text] the server will turn into cards, in order,
/// each once, at most [kForumMaxLinkCardsPerPost]. The server's rule (todo
/// 655): a line whose whole text is one `http(s)` URL becomes a card — not a
/// URL inside a sentence, a list item (`- `) or inline code, and not a video,
/// which embeds instead. This assumes the host has embeds on: with
/// `FORUM_EMBEDS_ENABLED=False` the server cards video lines too, so this
/// count is low there (the client cannot read that flag).
List<String> forumComposerCardLinks(String text) {
  final links = <String>[];
  for (final line in text.split('\n')) {
    final lineText = _lineText(line);
    if (lineText == null ||
        lineText.isEmpty ||
        lineText.contains(RegExp(r'\s'))) {
      continue;
    }
    if (forumVideoUrlOf(lineText) != null) continue;
    final url = _trimUrl(lineText);
    if (linkPreviewShortAddress(url) == null || links.contains(url)) continue;
    links.add(url);
    if (links.length == kForumMaxLinkCardsPerPost) break;
  }
  return links;
}
