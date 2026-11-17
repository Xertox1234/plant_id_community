/// A forum (board). Mirrors both the backend `BoardSerializer`
/// (`wagtail_forum/api/serializers.py`): `{id, title, slug, description,
/// topic_count, post_count}`, and the forum rows of `GET /forum/categories/`,
/// which add `icon`, `colour`, `has_unread`, `is_locked`, `is_closed`,
/// `can_post` and `last_post_at`. Boards are not paginated.
class ForumBoard {
  const ForumBoard({
    required this.id,
    required this.title,
    required this.slug,
    required this.description,
    required this.topicCount,
    required this.postCount,
    this.icon = '',
    this.colour = '',
    this.hasUnread = false,
    this.isLocked = false,
    this.isClosed = false,
    this.canPost = false,
    this.lastPostAt,
  });

  final int id;
  final String title;
  final String slug;
  final String description;
  final int topicCount;
  final int postCount;
  final String icon;
  final String colour;
  final bool hasUnread;
  final bool isLocked;
  final bool isClosed;
  final bool canPost;
  final DateTime? lastPostAt;

  factory ForumBoard.fromJson(Map<String, dynamic> json) {
    return ForumBoard(
      id: json['id'] as int,
      title: json['title'] as String? ?? '',
      slug: json['slug'] as String? ?? '',
      description: json['description'] as String? ?? '',
      topicCount: json['topic_count'] as int? ?? 0,
      postCount: json['post_count'] as int? ?? 0,
      icon: json['icon'] as String? ?? '',
      colour: json['colour'] as String? ?? '',
      hasUnread: json['has_unread'] as bool? ?? false,
      isLocked: json['is_locked'] as bool? ?? false,
      isClosed: json['is_closed'] as bool? ?? false,
      canPost: json['can_post'] as bool? ?? false,
      lastPostAt: DateTime.tryParse(json['last_post_at'] as String? ?? ''),
    );
  }
}
