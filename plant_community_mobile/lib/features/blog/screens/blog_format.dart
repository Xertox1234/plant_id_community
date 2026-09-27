import 'package:intl/intl.dart';

/// "May 9, 2026 · 3 min read", either half omitted when unknown; empty when
/// both are. `publish_date` is a calendar date, so no time zone shift.
String blogMetaLine(DateTime? publishDate, int? readingTime) {
  return [
    if (publishDate != null) DateFormat.yMMMd().format(publishDate),
    if (readingTime != null && readingTime > 0) '$readingTime min read',
  ].join(' · ');
}
