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
    this.isSolved = false,
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

  /// Whether the topic has an accepted answer (`is_solved`).
  final bool isSolved;

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
      isSolved: json['is_solved'] as bool? ?? false,
    );
  }

  /// A list row built from a topic detail — the thread screen bookmarks a
  /// topic it holds only as a [ForumTopicDetail], and the bookmarks feed
  /// (which lists `TopicListSerializer` rows) is spliced locally rather than
  /// refetched (todo 341). `is_unread` is not on the detail payload; a topic
  /// the viewer is currently reading is not unread.
  factory ForumTopicListItem.fromDetail(ForumTopicDetail detail) {
    return ForumTopicListItem(
      id: detail.id,
      title: detail.title,
      slug: detail.slug,
      author: detail.author,
      isPinned: detail.isPinned,
      isClosed: detail.isClosed,
      locked: detail.locked,
      replyCount: detail.replyCount,
      viewCount: detail.viewCount,
      lastPostAt: detail.lastPostAt,
      lastPostAuthor: detail.lastPostAuthor,
      isUnread: false,
      isSolved: detail.isSolved,
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
    this.isBookmarked = false,
    this.solvedPostId,
    this.canMarkSolution = false,
    this.isBlocked = false,
    this.canBlock = false,
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

  /// Save-for-later, distinct from [isSubscribed]'s notify-me intent
  /// (todo 283). `false` for an anonymous viewer.
  final bool isBookmarked;

  /// The accepted answer's post id, or `null` while unsolved. The single
  /// source for "is this post the answer" — mirrors the web's
  /// `isSolvedPost`; `is_solved` is derived here, never read separately.
  final int? solvedPostId;

  /// Whether THIS viewer may accept/clear an answer (topic author or a
  /// moderator) — server authority, never re-derived client-side.
  final bool canMarkSolution;

  /// Whether the viewer has blocked the topic's author (todo 284/M9).
  final bool isBlocked;

  /// Whether the viewer may block the topic's author.
  final bool canBlock;

  bool get isLocked => isClosed || locked;
  bool get isSolved => solvedPostId != null;

  /// Returns a copy with [isSubscribed] replaced (used after a
  /// subscribe/unsubscribe call, whose response carries the fresh state).
  ForumTopicDetail withSubscribed(bool isSubscribed) =>
      copyWith(isSubscribed: isSubscribed);

  ForumTopicDetail copyWith({
    bool? isSubscribed,
    bool? isBookmarked,
    int? solvedPostId,
    bool clearSolvedPostId = false,
  }) {
    return ForumTopicDetail(
      id: id,
      title: title,
      slug: slug,
      board: board,
      author: author,
      isPinned: isPinned,
      isClosed: isClosed,
      locked: locked,
      replyCount: replyCount,
      viewCount: viewCount,
      createdAt: createdAt,
      lastPostAt: lastPostAt,
      lastPostAuthor: lastPostAuthor,
      openingPostId: openingPostId,
      isSubscribed: isSubscribed ?? this.isSubscribed,
      isBookmarked: isBookmarked ?? this.isBookmarked,
      solvedPostId: clearSolvedPostId
          ? null
          : (solvedPostId ?? this.solvedPostId),
      canMarkSolution: canMarkSolution,
      isBlocked: isBlocked,
      canBlock: canBlock,
    );
  }

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
      isBookmarked: json['is_bookmarked'] as bool? ?? false,
      solvedPostId: json['solved_post_id'] as int?,
      canMarkSolution: json['can_mark_solution'] as bool? ?? false,
      isBlocked: json['is_blocked'] as bool? ?? false,
      canBlock: json['can_block'] as bool? ?? false,
    );
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}
