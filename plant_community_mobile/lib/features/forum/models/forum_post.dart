import 'forum_author.dart';
import 'forum_body_block.dart';

/// A forum post (thread reply, or the opening post). Mirrors the backend
/// `PostSerializer`.
///
/// Note the `status` enum here is `"live" | "pending"` (distinct from the
/// create/edit responses which use `"published" | "pending"`).
class ForumPost {
  const ForumPost({
    required this.id,
    required this.topicId,
    required this.author,
    required this.body,
    this.createdAt,
    this.updatedAt,
    this.editedAt,
    required this.isOpeningPost,
    required this.isPending,
    required this.reactionCounts,
    required this.reacted,
    required this.canEdit,
    required this.canDelete,
    required this.canReport,
  });

  final int id;
  final int topicId;
  final ForumAuthor author;
  final List<ForumBodyBlock> body;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  /// `null` unless the post has been edited.
  final DateTime? editedAt;
  final bool isOpeningPost;

  /// `true` when `status == "pending"` (held for moderation, `live=False`).
  final bool isPending;

  /// Active reaction counts keyed by type; zero-count types are omitted.
  final Map<String, int> reactionCounts;

  /// The reaction types the current user has active on this post (`[]` if
  /// anonymous).
  final List<String> reacted;
  final bool canEdit;
  final bool canDelete;
  final bool canReport;

  bool get isEdited => editedAt != null;

  factory ForumPost.fromJson(Map<String, dynamic> json) {
    return ForumPost(
      id: json['id'] as int,
      topicId: json['topic_id'] as int? ?? 0,
      author: ForumAuthor.fromJson(
        json['author'] as Map<String, dynamic>? ?? const {},
      ),
      body: parseForumBody(json['body']),
      createdAt: _parseDate(json['created_at']),
      updatedAt: _parseDate(json['updated_at']),
      editedAt: _parseDate(json['edited_at']),
      isOpeningPost: json['is_opening_post'] as bool? ?? false,
      isPending: (json['status'] as String? ?? 'live') == 'pending',
      reactionCounts: _parseReactionCounts(json['reaction_counts']),
      reacted: (json['reacted'] as List<dynamic>?)?.cast<String>() ?? const [],
      canEdit: json['can_edit'] as bool? ?? false,
      canDelete: json['can_delete'] as bool? ?? false,
      canReport: json['can_report'] as bool? ?? false,
    );
  }

  /// Returns a copy with reaction state replaced (used after a reaction
  /// toggle, whose response carries the fresh `reaction_counts`).
  ForumPost withReactions({
    required Map<String, int> reactionCounts,
    required List<String> reacted,
  }) {
    return ForumPost(
      id: id,
      topicId: topicId,
      author: author,
      body: body,
      createdAt: createdAt,
      updatedAt: updatedAt,
      editedAt: editedAt,
      isOpeningPost: isOpeningPost,
      isPending: isPending,
      reactionCounts: reactionCounts,
      reacted: reacted,
      canEdit: canEdit,
      canDelete: canDelete,
      canReport: canReport,
    );
  }

  static Map<String, int> _parseReactionCounts(dynamic raw) {
    if (raw is! Map) return const {};
    final result = <String, int>{};
    raw.forEach((key, value) {
      if (key is String && value is int) result[key] = value;
    });
    return result;
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}
