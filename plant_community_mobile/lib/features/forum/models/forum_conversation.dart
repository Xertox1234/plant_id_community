import 'forum_author.dart';

/// Preview of the most recent message in a conversation, as embedded in an
/// inbox row. Mirrors `ConversationSerializer.get_last_message`: [body] is
/// server-truncated (`MESSAGE_PREVIEW_CHARS`, 140), never the full text.
class ForumLastMessage {
  const ForumLastMessage({
    required this.body,
    required this.isMine,
    this.sender,
    this.createdAt,
  });

  final String body;

  /// `true` when the requesting user sent it — the inbox prefixes the
  /// preview with "You: " in that case.
  final bool isMine;

  /// Who sent it (todo 350) — a group row prefixes the preview with the
  /// sender's name. `null` from a backend that predates group DMs.
  final ForumAuthor? sender;
  final DateTime? createdAt;

  factory ForumLastMessage.fromJson(Map<String, dynamic> json) {
    final sender = json['sender'];
    return ForumLastMessage(
      body: json['body'] as String? ?? '',
      isMine: json['is_mine'] as bool? ?? false,
      sender: sender is Map<String, dynamic>
          ? ForumAuthor.fromJson(sender)
          : null,
      createdAt: _parseDate(json['created_at']),
    );
  }
}

/// `Conversation.kind` (todo 350): a 1:1 thread or a titled group.
enum ForumConversationKind {
  direct,
  group;

  /// Tolerant of an absent/unknown value: a backend that predates group
  /// DMs sends no `kind` at all, and every such row is a direct thread.
  static ForumConversationKind parse(Object? value) =>
      value == 'group' ? group : direct;
}

/// Backend `DM_GROUP_MAX_PARTICIPANTS`: members in a group INCLUDING me.
/// Enforced client-side too (the "Add member" action disables at the cap,
/// the new-group form caps its chips at [forumGroupMaxOthers]).
const int forumGroupMaxParticipants = 8;

/// Others a group can hold besides me: [forumGroupMaxParticipants] − 1.
const int forumGroupMaxOthers = forumGroupMaxParticipants - 1;

/// Fewest others a NEW group needs (a two-member "group" is a direct DM).
const int forumGroupMinOthers = 2;

/// Backend cap on a group title (`title`, ≤ 80 chars).
const int forumGroupTitleMaxChars = 80;

/// One conversation from the requesting user's point of view (todo 339,
/// groups todo 350). Mirrors the backend `ConversationSerializer`: a
/// direct row carries the OTHER participant in [otherParticipant]; a group
/// row carries `null` there and names itself with [title].
class ForumConversation {
  const ForumConversation({
    required this.id,
    required this.otherParticipant,
    this.kind = ForumConversationKind.direct,
    this.title,
    this.participants = const [],
    int? participantCount,
    this.createdBy,
    this.canManage = false,
    this.createdAt,
    this.lastMessageAt,
    this.unreadCount = 0,
    this.lastMessage,
  }) : participantCount = participantCount ?? participants.length;

  final int id;
  final ForumConversationKind kind;

  /// Group name (≤ 80 chars); `null` for a direct thread.
  final String? title;

  /// The far side of a DIRECT thread — never `null` server-side for one (a
  /// deleted participant serializes as the `[deleted]` sentinel, see
  /// `ForumAuthor.isDeleted`); always `null` for a group.
  final ForumAuthor? otherParticipant;

  /// Every member including me, in joined order. Empty from a backend that
  /// predates group DMs.
  final List<ForumAuthor> participants;

  /// Server-side member count (falls back to [participants]' length).
  final int participantCount;

  /// The group's creator; `null` for a direct thread.
  final ForumAuthor? createdBy;

  /// `true` when I created the group (I may add/remove members). Always
  /// `false` for a direct thread.
  final bool canManage;
  final DateTime? createdAt;

  /// Most recent activity; the inbox is ordered by this, newest first.
  final DateTime? lastMessageAt;

  /// Messages from the other side newer than my read marker. Own messages
  /// never count (server-side rule).
  final int unreadCount;

  /// `null` only for a conversation that has no messages yet.
  final ForumLastMessage? lastMessage;

  bool get hasUnread => unreadCount > 0;
  bool get isGroup => kind == ForumConversationKind.group;

  /// The group is full — "Add member" disables (server 400s past the cap).
  bool get isAtCapacity => participantCount >= forumGroupMaxParticipants;

  /// Local splice helper for the inbox feed (read → unread 0; send → new
  /// preview and activity time; member add/remove → new roster) so a
  /// loaded, paged inbox is never collapsed back to page 1 by a
  /// whole-provider invalidation.
  ForumConversation copyWith({
    int? unreadCount,
    DateTime? lastMessageAt,
    ForumLastMessage? lastMessage,
    List<ForumAuthor>? participants,
    int? participantCount,
  }) {
    final roster = participants ?? this.participants;
    return ForumConversation(
      id: id,
      kind: kind,
      title: title,
      otherParticipant: otherParticipant,
      participants: roster,
      participantCount:
          participantCount ??
          (participants != null ? roster.length : this.participantCount),
      createdBy: createdBy,
      canManage: canManage,
      createdAt: createdAt,
      lastMessageAt: lastMessageAt ?? this.lastMessageAt,
      unreadCount: unreadCount ?? this.unreadCount,
      lastMessage: lastMessage ?? this.lastMessage,
    );
  }

  factory ForumConversation.fromJson(Map<String, dynamic> json) {
    final kind = ForumConversationKind.parse(json['kind']);
    final other = json['other_participant'];
    final createdBy = json['created_by'];
    final participants = [
      for (final item in json['participants'] as List<dynamic>? ?? const [])
        if (item is Map<String, dynamic>) ForumAuthor.fromJson(item),
    ];
    return ForumConversation(
      id: json['id'] as int,
      kind: kind,
      title: json['title'] as String?,
      // A direct row from any backend carries the far side; the key is
      // absent (older backend) or null (group) otherwise. Only a DIRECT
      // row with a missing value falls back to the `[deleted]` sentinel —
      // a group has no far side by definition.
      otherParticipant: other is Map<String, dynamic>
          ? ForumAuthor.fromJson(other)
          : (kind == ForumConversationKind.direct
                ? ForumAuthor.fromJson(const {})
                : null),
      participants: participants,
      participantCount: json['participant_count'] as int?,
      createdBy: createdBy is Map<String, dynamic>
          ? ForumAuthor.fromJson(createdBy)
          : null,
      canManage: json['can_manage'] as bool? ?? false,
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
