import 'models/models.dart';

/// Longest quoted excerpt the "Quote" action pre-fills (todo 341 wave 3):
/// enough for a paragraph or two, never a whole post — the reply is meant
/// to answer a point, not mirror the thread. Longer text is cut here and
/// marked with an ellipsis.
const int forumQuoteMaxChars = 500;

/// The `quote` block text the "Quote" action pre-fills for [post]: a plain
/// `username wrote:` attribution line — deliberately WITHOUT the `@`: the
/// server's mention scanner reads every string block, and `@user` here would
/// turn the quoted author's email REPLY notification into a push-only
/// MENTION (review finding; structured attribution is todo
/// 342's job) followed by the post's reader-visible text, capped at
/// [forumQuoteMaxChars]. Returns `null` when the post has no quotable text
/// (image-only, deleted image, an embed).
String? forumQuoteText(ForumPost post) {
  var text = forumBodyPlainText(post.body);
  if (text.isEmpty) return null;
  if (text.length > forumQuoteMaxChars) {
    text = '${text.substring(0, forumQuoteMaxChars).trimRight()}…';
  }
  return '${post.author.username} wrote:\n$text';
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
