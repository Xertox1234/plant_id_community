import 'forum_post.dart';

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

/// Result of `PATCH /forum/posts/{id}/` — the full post shape (todo 292)
/// plus `moderation_status`. When [status] is pending, [post]'s body is the
/// SUBMITTED revision the caller just sent (see PostWriteView.patch), not
/// what a fresh GET will return until the edit clears moderation — the
/// same "shows what you sent" contract the web client's edit flow relies on.
class EditPostResult {
  const EditPostResult({required this.post, required this.status});

  final ForumPost post;
  final ForumModerationStatus status;

  factory EditPostResult.fromJson(Map<String, dynamic> json) {
    return EditPostResult(
      post: ForumPost.fromJson(json),
      status: ForumModerationStatus.fromString(
        json['moderation_status'] as String?,
      ),
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

/// Result of `POST`/`DELETE /forum/topics/{id}/solution/` — the topic's
/// CURRENT accepted-answer state, structurally identical for mark and clear
/// so a client never infers `is_solved` from the status code.
class ForumSolutionResult {
  const ForumSolutionResult({required this.isSolved, this.solvedPostId});

  final bool isSolved;
  final int? solvedPostId;

  factory ForumSolutionResult.fromJson(Map<String, dynamic> json) {
    return ForumSolutionResult(
      isSolved: json['is_solved'] as bool? ?? false,
      solvedPostId: json['solved_post_id'] as int?,
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
