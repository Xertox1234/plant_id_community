import 'forum_board.dart';

/// A link row inside a forum category. Mirrors the backend category feed's
/// `links` entries (`GET /forum/categories/`).
class ForumLink {
  const ForumLink({
    required this.id,
    required this.title,
    required this.slug,
    required this.description,
    required this.linkUrl,
    required this.trackClicks,
    this.clickCount,
  });

  final int id;
  final String title;
  final String slug;
  final String description;
  final String linkUrl;
  final bool trackClicks;
  final int? clickCount;

  factory ForumLink.fromJson(Map<String, dynamic> json) {
    return ForumLink(
      id: json['id'] as int,
      title: json['title'] as String? ?? '',
      slug: json['slug'] as String? ?? '',
      description: json['description'] as String? ?? '',
      linkUrl: json['link_url'] as String? ?? '',
      trackClicks: json['track_clicks'] as bool? ?? false,
      clickCount: json['click_count'] as int?,
    );
  }
}

/// A forum category grouping boards and links (`GET /forum/categories/`).
class ForumCategory {
  const ForumCategory({
    required this.id,
    required this.title,
    required this.slug,
    required this.description,
    required this.icon,
    required this.colour,
    required this.hasUnread,
    required this.forums,
    required this.links,
  });

  final int id;
  final String title;
  final String slug;
  final String description;
  final String icon;
  final String colour;
  final bool hasUnread;
  final List<ForumBoard> forums;
  final List<ForumLink> links;

  factory ForumCategory.fromJson(Map<String, dynamic> json) {
    return ForumCategory(
      id: json['id'] as int,
      title: json['title'] as String? ?? '',
      slug: json['slug'] as String? ?? '',
      description: json['description'] as String? ?? '',
      icon: json['icon'] as String? ?? '',
      colour: json['colour'] as String? ?? '',
      hasUnread: json['has_unread'] as bool? ?? false,
      forums: (json['forums'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ForumBoard.fromJson)
          .toList(growable: false),
      links: (json['links'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ForumLink.fromJson)
          .toList(growable: false),
    );
  }
}
