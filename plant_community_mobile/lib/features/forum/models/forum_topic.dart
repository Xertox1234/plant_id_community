import 'forum_author.dart';

/// A topic row in a board listing. Mirrors the backend `TopicListSerializer`.
class ForumTopicListItem {
  const ForumTopicListItem({
    required this.id,
    required this.title,
    required this.slug,
    required this.author,
    required this.isPinned,
    required this.isClosed,
    required this.locked,
    required this.replyCount,
    required this.viewCount,
    this.lastPostAt,
    this.lastPostAuthor,
    required this.isUnread,
  });

  final int id;
  final String title;
  final String slug;
  final ForumAuthor author;
  final bool isPinned;
  final bool isClosed;
  final bool locked;
  final int replyCount;
  final int viewCount;
  final DateTime? lastPostAt;

  /// `null` (not the `[deleted]` sentinel) when the last-post author is
  /// unknown — see the backend rationale in `serializers.py`.
  final ForumAuthor? lastPostAuthor;
  final bool isUnread;

  /// Whether posting is blocked (closed OR locked), mirroring the web
  /// mapper's `is_locked = is_closed || locked`.
  bool get isLocked => isClosed || locked;

  factory ForumTopicListItem.fromJson(Map<String, dynamic> json) {
    return ForumTopicListItem(
      id: json['id'] as int,
      title: json['title'] as String? ?? '',
      slug: json['slug'] as String? ?? '',
      author: ForumAuthor.fromJson(
        json['author'] as Map<String, dynamic>? ?? const {},
      ),
      isPinned: json['is_pinned'] as bool? ?? false,
      isClosed: json['is_closed'] as bool? ?? false,
      locked: json['locked'] as bool? ?? false,
      replyCount: json['reply_count'] as int? ?? 0,
      viewCount: json['view_count'] as int? ?? 0,
      lastPostAt: _parseDate(json['last_post_at']),
      lastPostAuthor: json['last_post_author'] == null
          ? null
          : ForumAuthor.fromJson(
              json['last_post_author'] as Map<String, dynamic>,
            ),
      isUnread: json['is_unread'] as bool? ?? false,
    );
  }
}

/// Lightweight board reference embedded in a topic detail.
class ForumTopicBoardRef {
  const ForumTopicBoardRef({
    required this.id,
    required this.slug,
    required this.title,
  });

  final int id;
  final String slug;
  final String title;

  factory ForumTopicBoardRef.fromJson(Map<String, dynamic> json) {
    return ForumTopicBoardRef(
      id: json['id'] as int? ?? 0,
      slug: json['slug'] as String? ?? '',
      title: json['title'] as String? ?? '',
    );
  }
}

/// Full topic detail. Mirrors the backend `TopicDetailSerializer`.
class ForumTopicDetail {
  const ForumTopicDetail({
    required this.id,
    required this.title,
    required this.slug,
    required this.board,
    required this.author,
    required this.isPinned,
    required this.isClosed,
    required this.locked,
    required this.replyCount,
    required this.viewCount,
    this.createdAt,
    this.lastPostAt,
    this.lastPostAuthor,
    this.openingPostId,
    required this.isSubscribed,
  });

  final int id;
  final String title;
  final String slug;
  final ForumTopicBoardRef board;
  final ForumAuthor author;
  final bool isPinned;
  final bool isClosed;
  final bool locked;
  final int replyCount;
  final int viewCount;
  final DateTime? createdAt;
  final DateTime? lastPostAt;
  final ForumAuthor? lastPostAuthor;
  final int? openingPostId;
  final bool isSubscribed;

  bool get isLocked => isClosed || locked;

  factory ForumTopicDetail.fromJson(Map<String, dynamic> json) {
    return ForumTopicDetail(
      id: json['id'] as int,
      title: json['title'] as String? ?? '',
      slug: json['slug'] as String? ?? '',
      board: ForumTopicBoardRef.fromJson(
        json['board'] as Map<String, dynamic>? ?? const {},
      ),
      author: ForumAuthor.fromJson(
        json['author'] as Map<String, dynamic>? ?? const {},
      ),
      isPinned: json['is_pinned'] as bool? ?? false,
      isClosed: json['is_closed'] as bool? ?? false,
      locked: json['locked'] as bool? ?? false,
      replyCount: json['reply_count'] as int? ?? 0,
      viewCount: json['view_count'] as int? ?? 0,
      createdAt: _parseDate(json['created_at']),
      lastPostAt: _parseDate(json['last_post_at']),
      lastPostAuthor: json['last_post_author'] == null
          ? null
          : ForumAuthor.fromJson(
              json['last_post_author'] as Map<String, dynamic>,
            ),
      openingPostId: json['opening_post_id'] as int?,
      isSubscribed: json['is_subscribed'] as bool? ?? false,
    );
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}
