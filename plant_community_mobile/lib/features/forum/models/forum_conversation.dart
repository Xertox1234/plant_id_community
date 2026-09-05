import 'forum_author.dart';

/// Preview of the most recent message in a conversation, as embedded in an
/// inbox row. Mirrors `ConversationSerializer.get_last_message`: [body] is
/// server-truncated (`MESSAGE_PREVIEW_CHARS`, 140), never the full text.
class ForumLastMessage {
  const ForumLastMessage({
    required this.body,
    required this.isMine,
    this.createdAt,
  });

  final String body;

  /// `true` when the requesting user sent it — the inbox prefixes the
  /// preview with "You: " in that case.
  final bool isMine;
  final DateTime? createdAt;

  factory ForumLastMessage.fromJson(Map<String, dynamic> json) {
    return ForumLastMessage(
      body: json['body'] as String? ?? '',
      isMine: json['is_mine'] as bool? ?? false,
      createdAt: _parseDate(json['created_at']),
    );
  }
}

/// One 1:1 direct-message conversation from the requesting user's point of
/// view (todo 339). Mirrors the backend `ConversationSerializer`: the row
/// carries the OTHER participant only, never both sides.
class ForumConversation {
  const ForumConversation({
    required this.id,
    required this.otherParticipant,
    this.createdAt,
    this.lastMessageAt,
    this.unreadCount = 0,
    this.lastMessage,
  });

  final int id;

  /// Never `null` server-side — a deleted participant serializes as the
  /// `[deleted]` sentinel (see `ForumAuthor.isDeleted`).
  final ForumAuthor otherParticipant;
  final DateTime? createdAt;

  /// Most recent activity; the inbox is ordered by this, newest first.
  final DateTime? lastMessageAt;

  /// Messages from the other side newer than my read marker. Own messages
  /// never count (server-side rule).
  final int unreadCount;

  /// `null` only for a conversation that has no messages yet.
  final ForumLastMessage? lastMessage;

  bool get hasUnread => unreadCount > 0;

  /// Local splice helper for the inbox feed (read → unread 0; send → new
  /// preview and activity time) so a loaded, paged inbox is never
  /// collapsed back to page 1 by a whole-provider invalidation.
  ForumConversation copyWith({
    int? unreadCount,
    DateTime? lastMessageAt,
    ForumLastMessage? lastMessage,
  }) {
    return ForumConversation(
      id: id,
      otherParticipant: otherParticipant,
      createdAt: createdAt,
      lastMessageAt: lastMessageAt ?? this.lastMessageAt,
      unreadCount: unreadCount ?? this.unreadCount,
      lastMessage: lastMessage ?? this.lastMessage,
    );
  }

  factory ForumConversation.fromJson(Map<String, dynamic> json) {
    return ForumConversation(
      id: json['id'] as int,
      otherParticipant: ForumAuthor.fromJson(
        json['other_participant'] as Map<String, dynamic>? ?? const {},
      ),
      createdAt: _parseDate(json['created_at']),
      lastMessageAt: _parseDate(json['last_message_at']),
      unreadCount: json['unread_count'] as int? ?? 0,
      lastMessage: json['last_message'] == null
          ? null
          : ForumLastMessage.fromJson(
              json['last_message'] as Map<String, dynamic>,
            ),
    );
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}
