import 'models/models.dart';

/// Longest quoted excerpt the "Quote" action pre-fills (todo 341 wave 3):
/// enough for a paragraph or two, never a whole post — the reply is meant
/// to answer a point, not mirror the thread. Longer text is cut here and
/// marked with an ellipsis.
const int forumQuoteMaxChars = 500;

/// What the "Quote" action carries into the reply composer (todo 342): the
/// quoted post's id and excerpt — sent as a structured `post_quote` block
/// (`buildPostQuoteBlockBody`) — plus the author's display name for the
/// composer's draft card. The name is NOT part of the sent text: the server
/// resolves the attribution from [postId] on read, and a plain
/// `username wrote:` line would only feed its mention scanner.
class ForumQuoteDraft {
  const ForumQuoteDraft({
    required this.postId,
    required this.text,
    required this.authorName,
  });

  final int postId;
  final String text;
  final String authorName;
}

/// The quote draft the "Quote" action pre-fills for [post]: its
/// reader-visible text capped at [forumQuoteMaxChars], keyed to the post's
/// id. Returns `null` when the post has no quotable text (image-only,
/// deleted image, an embed).
ForumQuoteDraft? forumQuoteDraft(ForumPost post) {
  var text = forumBodyPlainText(post.body);
  if (text.isEmpty) return null;
  if (text.length > forumQuoteMaxChars) {
    text = '${text.substring(0, forumQuoteMaxChars).trimRight()}…';
  }
  return ForumQuoteDraft(
    postId: post.id,
    text: text,
    authorName: post.author.name,
  );
}

/// Compact relative-time label for forum timestamps ("just now", "5m", "3h",
/// "2d", or an absolute date beyond a week). Returns an empty string for null.
String forumRelativeTime(DateTime? dt, {DateTime? now}) {
  if (dt == null) return '';
  final reference = now ?? DateTime.now();
  final diff = reference.difference(dt);
  if (diff.isNegative || diff.inSeconds < 45) return 'just now';
  if (diff.inMinutes < 60) return '${diff.inMinutes}m';
  if (diff.inHours < 24) return '${diff.inHours}h';
  if (diff.inDays < 7) return '${diff.inDays}d';
  final local = dt.toLocal();
  final month = local.month.toString().padLeft(2, '0');
  final day = local.day.toString().padLeft(2, '0');
  return '${local.year}-$month-$day';
}
