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
