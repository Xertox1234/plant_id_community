/// A forum board (category). Mirrors the backend `BoardSerializer`
/// (`wagtail_forum/api/serializers.py`): `{id, title, slug, description,
/// topic_count, post_count}`. Boards are not paginated.
class ForumBoard {
  const ForumBoard({
    required this.id,
    required this.title,
    required this.slug,
    required this.description,
    required this.topicCount,
    required this.postCount,
  });

  final int id;
  final String title;
  final String slug;
  final String description;
  final int topicCount;
  final int postCount;

  factory ForumBoard.fromJson(Map<String, dynamic> json) {
    return ForumBoard(
      id: json['id'] as int,
      title: json['title'] as String? ?? '',
      slug: json['slug'] as String? ?? '',
      description: json['description'] as String? ?? '',
      topicCount: json['topic_count'] as int? ?? 0,
      postCount: json['post_count'] as int? ?? 0,
    );
  }
}
