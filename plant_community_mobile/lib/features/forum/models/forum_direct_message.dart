import 'forum_author.dart';

/// A single private message (todo 339). Mirrors the backend
/// `MessageSerializer`: [body] is plain text (no body blocks — DMs are not
/// rich-text), so it renders straight into a `Text`.
class ForumDirectMessage {
  const ForumDirectMessage({
    required this.id,
    required this.conversationId,
    required this.sender,
    required this.body,
    this.createdAt,
  });

  final int id;
  final int conversationId;

  /// Never `null` server-side — a deleted sender serializes as the
  /// `[deleted]` sentinel (see `ForumAuthor.isDeleted`).
  final ForumAuthor sender;
  final String body;
  final DateTime? createdAt;

  factory ForumDirectMessage.fromJson(Map<String, dynamic> json) {
    return ForumDirectMessage(
      id: json['id'] as int,
      conversationId: json['conversation_id'] as int? ?? 0,
      sender: ForumAuthor.fromJson(
        json['sender'] as Map<String, dynamic>? ?? const {},
      ),
      body: json['body'] as String? ?? '',
      createdAt: _parseDate(json['created_at']),
    );
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}
