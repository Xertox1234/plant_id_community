import 'forum_author.dart';

/// A topic authored by the profile's user (`recent_topics[]`).
class ForumProfileTopicRef {
  const ForumProfileTopicRef({
    required this.id,
    required this.slug,
    required this.title,
    required this.boardId,
    required this.boardSlug,
    required this.replyCount,
    this.createdAt,
  });

  final int id;
  final String slug;
  final String title;
  final int boardId;
  final String boardSlug;
  final int replyCount;
  final DateTime? createdAt;

  factory ForumProfileTopicRef.fromJson(Map<String, dynamic> json) {
    return ForumProfileTopicRef(
      id: json['id'] as int,
      slug: json['slug'] as String? ?? '',
      title: json['title'] as String? ?? '',
      boardId: json['board_id'] as int? ?? 0,
      boardSlug: json['board_slug'] as String? ?? '',
      replyCount: json['reply_count'] as int? ?? 0,
      createdAt: _parseDate(json['created_at']),
    );
  }
}

/// A reply authored by the profile's user (`recent_posts[]`).
class ForumProfilePostRef {
  const ForumProfilePostRef({
    required this.id,
    required this.topicId,
    required this.topicSlug,
    required this.topicTitle,
    required this.boardId,
    required this.boardSlug,
    this.createdAt,
  });

  final int id;
  final int topicId;
  final String topicSlug;
  final String topicTitle;
  final int boardId;
  final String boardSlug;
  final DateTime? createdAt;

  factory ForumProfilePostRef.fromJson(Map<String, dynamic> json) {
    return ForumProfilePostRef(
      id: json['id'] as int,
      topicId: json['topic_id'] as int? ?? 0,
      topicSlug: json['topic_slug'] as String? ?? '',
      topicTitle: json['topic_title'] as String? ?? '',
      boardId: json['board_id'] as int? ?? 0,
      boardSlug: json['board_slug'] as String? ?? '',
      createdAt: _parseDate(json['created_at']),
    );
  }
}

/// Public forum profile (`GET /forum/users/{username}/`). Mirrors the
/// backend `PUBLIC_PROFILE_SCHEMA` — a flat merge of `serialize_forum_author`
/// with profile-only fields, so [author] parses off the SAME top-level JSON
/// map this class receives, not a nested `author` key.
class ForumProfile {
  const ForumProfile({
    required this.author,
    required this.bio,
    required this.signature,
    required this.postCount,
    this.joinedAt,
    required this.recentTopics,
    required this.recentPosts,
  });

  final ForumAuthor author;
  final String bio;
  final String signature;
  final int postCount;
  final DateTime? joinedAt;
  final List<ForumProfileTopicRef> recentTopics;
  final List<ForumProfilePostRef> recentPosts;

  factory ForumProfile.fromJson(Map<String, dynamic> json) {
    return ForumProfile(
      author: ForumAuthor.fromJson(json),
      bio: json['bio'] as String? ?? '',
      signature: json['signature'] as String? ?? '',
      postCount: json['post_count'] as int? ?? 0,
      joinedAt: _parseDate(json['joined_at']),
      recentTopics: (json['recent_topics'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ForumProfileTopicRef.fromJson)
          .toList(growable: false),
      recentPosts: (json['recent_posts'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ForumProfilePostRef.fromJson)
          .toList(growable: false),
    );
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}
