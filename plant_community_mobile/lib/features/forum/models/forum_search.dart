/// A topic hit from the `/forum/search/` full-text search (`topics[]`).
class ForumSearchTopicHit {
  const ForumSearchTopicHit({
    required this.id,
    required this.slug,
    required this.title,
    required this.replyCount,
    required this.viewCount,
    required this.isPinned,
    required this.isSolved,
    required this.boardId,
    required this.boardSlug,
    this.lastPostAt,
  });

  final int id;
  final String slug;
  final String title;
  final int replyCount;
  final int viewCount;
  final bool isPinned;
  final bool isSolved;
  final int boardId;
  final String boardSlug;
  final DateTime? lastPostAt;

  factory ForumSearchTopicHit.fromJson(Map<String, dynamic> json) {
    return ForumSearchTopicHit(
      id: json['id'] as int,
      slug: json['slug'] as String? ?? '',
      title: json['title'] as String? ?? '',
      replyCount: json['reply_count'] as int? ?? 0,
      viewCount: json['view_count'] as int? ?? 0,
      isPinned: json['is_pinned'] as bool? ?? false,
      isSolved: json['is_solved'] as bool? ?? false,
      boardId: json['board_id'] as int? ?? 0,
      boardSlug: json['board_slug'] as String? ?? '',
      lastPostAt: DateTime.tryParse(json['last_post_at'] as String? ?? ''),
    );
  }
}

/// A post hit from the `/forum/search/` full-text search (`posts[]`).
class ForumSearchPostHit {
  const ForumSearchPostHit({
    required this.id,
    required this.topicId,
    required this.topicTitle,
    required this.topicSlug,
    required this.boardId,
    required this.boardSlug,
    required this.excerpt,
  });

  final int id;
  final int topicId;
  final String topicTitle;
  final String topicSlug;
  final int boardId;
  final String boardSlug;
  final String excerpt;

  factory ForumSearchPostHit.fromJson(Map<String, dynamic> json) {
    return ForumSearchPostHit(
      id: json['id'] as int,
      topicId: json['topic_id'] as int? ?? 0,
      topicTitle: json['topic_title'] as String? ?? '',
      topicSlug: json['topic_slug'] as String? ?? '',
      boardId: json['board_id'] as int? ?? 0,
      boardSlug: json['board_slug'] as String? ?? '',
      excerpt: json['excerpt'] as String? ?? '',
    );
  }
}

/// The three states `semantic_status` can report (`SemanticSearchMixin`,
/// backend `semantic_search.py`). `premium_required` is reachable by a
/// non-premium caller regardless of the feature flag — the premium check
/// runs BEFORE the flag check server-side, so it's the more commonly hit
/// state for a typical mobile user, not `unavailable`.
enum ForumSemanticStatus { ok, premiumRequired, unavailable }

ForumSemanticStatus? _parseSemanticStatus(String? raw) {
  switch (raw) {
    case 'ok':
      return ForumSemanticStatus.ok;
    case 'premium_required':
      return ForumSemanticStatus.premiumRequired;
    case 'unavailable':
      return ForumSemanticStatus.unavailable;
    default:
      return null;
  }
}

/// One page of the `/forum/search/` response. `topics`/`posts` are two
/// independently-paginated sections sharing one `page` cursor — offset
/// pagination, NOT the cursor-based [CursorPage] every other forum list
/// uses (no `results`/`next` URL; paging is driven by incrementing `page`).
class ForumSearchPage {
  const ForumSearchPage({
    required this.topics,
    required this.posts,
    required this.topicsHasMore,
    required this.postsHasMore,
    required this.page,
    this.semantic,
    this.semanticStatus,
  });

  final List<ForumSearchTopicHit> topics;
  final List<ForumSearchPostHit> posts;
  final bool topicsHasMore;
  final bool postsHasMore;
  final int page;

  /// Only present when the request opted into `?semantic=1`. `null` here
  /// (as opposed to an empty list) means the section wasn't requested at
  /// all — distinct from [semanticStatus] == ok with zero matches.
  final List<ForumSearchTopicHit>? semantic;
  final ForumSemanticStatus? semanticStatus;

  factory ForumSearchPage.fromJson(Map<String, dynamic> json) {
    final semanticJson = json['semantic'] as List<dynamic>?;
    return ForumSearchPage(
      topics: (json['topics'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ForumSearchTopicHit.fromJson)
          .toList(growable: false),
      posts: (json['posts'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ForumSearchPostHit.fromJson)
          .toList(growable: false),
      topicsHasMore: json['topics_has_more'] as bool? ?? false,
      postsHasMore: json['posts_has_more'] as bool? ?? false,
      page: json['page'] as int? ?? 1,
      semantic: semanticJson
          ?.whereType<Map<String, dynamic>>()
          .map(ForumSearchTopicHit.fromJson)
          .toList(growable: false),
      semanticStatus: _parseSemanticStatus(json['semantic_status'] as String?),
    );
  }
}
