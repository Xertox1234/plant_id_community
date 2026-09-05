import 'forum_author.dart';
import 'forum_body_block.dart';

/// One entry of a post's edit history (`GET /forum/posts/{id}/revisions/`,
/// newest first). Mirrors the backend `REVISION_SCHEMA`: `{id, created_at,
/// user}` — there is no summary/diff field; the body lives on
/// [ForumPostRevisionDetail].
class ForumPostRevision {
  const ForumPostRevision({
    required this.id,
    this.createdAt,
    required this.user,
  });

  final int id;
  final DateTime? createdAt;

  /// Who saved this revision — the `[deleted]` sentinel for an unattributed
  /// one (see `ForumAuthor.isDeleted`).
  final ForumAuthor user;

  factory ForumPostRevision.fromJson(Map<String, dynamic> json) {
    return ForumPostRevision(
      id: json['id'] as int,
      createdAt: _parseDate(json['created_at']),
      user: ForumAuthor.fromJson(
        json['user'] as Map<String, dynamic>? ?? const {},
      ),
    );
  }
}

/// One revision's body (`GET /forum/posts/{id}/revisions/{revision_id}/`),
/// in the same block shape as the live post so it renders through the same
/// `ForumBodyRenderer`.
class ForumPostRevisionDetail extends ForumPostRevision {
  const ForumPostRevisionDetail({
    required super.id,
    super.createdAt,
    required super.user,
    required this.body,
  });

  final List<ForumBodyBlock> body;

  factory ForumPostRevisionDetail.fromJson(Map<String, dynamic> json) {
    final summary = ForumPostRevision.fromJson(json);
    return ForumPostRevisionDetail(
      id: summary.id,
      createdAt: summary.createdAt,
      user: summary.user,
      body: parseForumBody(json['body']),
    );
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}
