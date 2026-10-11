import 'package:intl/intl.dart';

/// The blog's one name on mobile (todo 460): the Home card, the list's app
/// bar and a post's title bar before the post loads all say it.
const String blogDisplayName = 'Plant Journal';

/// "May 9, 2026 · 3 min read", either half omitted when unknown; empty when
/// both are. `publish_date` is a calendar date, so no time zone shift.
String blogMetaLine(DateTime? publishDate, int? readingTime) {
  return [
    if (publishDate != null) DateFormat.yMMMd().format(publishDate),
    if (readingTime != null && readingTime > 0) '$readingTime min read',
  ].join(' · ');
}
