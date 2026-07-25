/// Moderation outcome of a create/edit write. The create/reply/edit
/// responses use `"published" | "pending"` (distinct from a Post's
/// `"live" | "pending"` status).
enum ForumModerationStatus {
  published,
  pending;

  static ForumModerationStatus fromString(String? value) =>
      value == 'pending' ? pending : published;

  bool get isPending => this == pending;
}

/// Result of `POST /forum/boards/{slug}/topics/` — `{id, slug, status}`.
/// The server auto-suffixes a taken slug, so read the final [slug] here.
class CreateTopicResult {
  const CreateTopicResult({
    required this.id,
    required this.slug,
    required this.status,
  });

  final int id;
  final String slug;
  final ForumModerationStatus status;

  factory CreateTopicResult.fromJson(Map<String, dynamic> json) {
    return CreateTopicResult(
      id: json['id'] as int,
      slug: json['slug'] as String? ?? '',
      status: ForumModerationStatus.fromString(json['status'] as String?),
    );
  }
}

/// Result of `POST /forum/topics/{id}/posts/` — `{id, status}`.
class CreateReplyResult {
  const CreateReplyResult({required this.id, required this.status});

  final int id;
  final ForumModerationStatus status;

  factory CreateReplyResult.fromJson(Map<String, dynamic> json) {
    return CreateReplyResult(
      id: json['id'] as int,
      status: ForumModerationStatus.fromString(json['status'] as String?),
    );
  }
}

/// Result of a reaction toggle — `{reaction_counts, reacted}` where `reacted`
/// is the resulting boolean state of the single toggled type.
class ReactionToggleResult {
  const ReactionToggleResult({
    required this.reactionCounts,
    required this.reacted,
  });

  final Map<String, int> reactionCounts;
  final bool reacted;

  factory ReactionToggleResult.fromJson(Map<String, dynamic> json) {
    final counts = <String, int>{};
    final raw = json['reaction_counts'];
    if (raw is Map) {
      raw.forEach((key, value) {
        if (key is String && value is int) counts[key] = value;
      });
    }
    return ReactionToggleResult(
      reactionCounts: counts,
      reacted: json['reacted'] as bool? ?? false,
    );
  }
}

/// Result of `POST /forum/images/` — `{id, url, alt, width, height}`.
class ForumImageUploadResult {
  const ForumImageUploadResult({
    required this.id,
    required this.url,
    required this.alt,
    required this.width,
    required this.height,
  });

  final int id;
  final String url;
  final String alt;
  final int width;
  final int height;

  factory ForumImageUploadResult.fromJson(Map<String, dynamic> json) {
    return ForumImageUploadResult(
      id: json['id'] as int,
      url: json['url'] as String? ?? '',
      alt: json['alt'] as String? ?? '',
      width: json['width'] as int? ?? 0,
      height: json['height'] as int? ?? 0,
    );
  }
}
