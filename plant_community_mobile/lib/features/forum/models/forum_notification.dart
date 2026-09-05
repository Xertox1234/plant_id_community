import 'forum_author.dart';

/// Lightweight topic reference embedded in a notification. Distinct from
/// [ForumTopicBoardRef] (`forum_topic.dart`) — this one is flat
/// (`board_id`/`board_slug`), mirroring the backend's
/// `NotificationSerializer.get_topic`, not the nested `board` object on
/// `TopicDetailSerializer`.
class ForumNotificationTopicRef {
  const ForumNotificationTopicRef({
    required this.id,
    required this.slug,
    required this.title,
    required this.boardId,
    required this.boardSlug,
  });

  final int id;
  final String slug;
  final String title;
  final int boardId;
  final String boardSlug;

  factory ForumNotificationTopicRef.fromJson(Map<String, dynamic> json) {
    return ForumNotificationTopicRef(
      id: json['id'] as int,
      slug: json['slug'] as String? ?? '',
      title: json['title'] as String? ?? '',
      boardId: json['board_id'] as int? ?? 0,
      boardSlug: json['board_slug'] as String? ?? '',
    );
  }
}

/// A single notification row. Mirrors the backend `NotificationSerializer`.
///
/// [topic] is `null` for a future non-topic-scoped verb (see the backend's
/// `_visible_notifications` docstring) — never treat a null topic as "the
/// topic was deleted"; a since-unpublished topic's notifications are excluded
/// server-side entirely, not nulled out.
class ForumNotification {
  const ForumNotification({
    required this.id,
    required this.verb,
    required this.actor,
    this.topic,
    this.postId,
    this.quotedPostId,
    this.createdAt,
    this.readAt,
  });

  final int id;
  final String verb;

  /// Never `null` server-side — a deleted actor serializes as the
  /// `[deleted]` sentinel (see `ForumAuthor.isDeleted`).
  final ForumAuthor actor;
  final ForumNotificationTopicRef? topic;

  /// The post this notification is about, or `null` for a post-less verb.
  /// Deep-link target once push-tap routing lands (todo 311). For a `quote`
  /// this is the QUOTING post — the reply to open — not the quoted one.
  final int? postId;

  /// `quote` only (todo 342): the recipient's own post that was quoted.
  /// `null` for every other verb.
  final int? quotedPostId;
  final DateTime? createdAt;
  final DateTime? readAt;

  bool get isRead => readAt != null;

  factory ForumNotification.fromJson(Map<String, dynamic> json) {
    return ForumNotification(
      id: json['id'] as int,
      verb: json['verb'] as String? ?? '',
      actor: ForumAuthor.fromJson(
        json['actor'] as Map<String, dynamic>? ?? const {},
      ),
      topic: json['topic'] == null
          ? null
          : ForumNotificationTopicRef.fromJson(
              json['topic'] as Map<String, dynamic>,
            ),
      postId: json['post_id'] as int?,
      quotedPostId: json['quoted_post_id'] as int?,
      createdAt: _parseDate(json['created_at']),
      readAt: _parseDate(json['read_at']),
    );
  }

  /// Returns a copy with [readAt] set — used after a mark-read call whose
  /// response doesn't echo the row back (avoids a refetch to reflect the
  /// tap locally).
  ForumNotification asRead(DateTime readAt) {
    return ForumNotification(
      id: id,
      verb: verb,
      actor: actor,
      topic: topic,
      postId: postId,
      quotedPostId: quotedPostId,
      createdAt: createdAt,
      readAt: readAt,
    );
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}
