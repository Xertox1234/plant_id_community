/// Forum author identity — the single unified shape used everywhere the
/// backend embeds a user (topic author, last-post author, post author,
/// notification actor, public-profile identity).
///
/// Mirrors the backend `AUTHOR_SCHEMA`
/// (`wagtail_forum/api/serializers.py`): `{username, display_name, avatar,
/// trust_level}`. A deleted user is never `null` — the backend returns a
/// `[deleted]` sentinel object.
class ForumAuthor {
  const ForumAuthor({
    required this.username,
    required this.displayName,
    this.avatar,
    this.trustLevel,
  });

  final String username;
  final String displayName;

  /// Absolute URL to the raw avatar image, or `null`.
  final String? avatar;

  /// Integer trust level (0-4) or `null` when the user has no forum profile.
  /// See [trustLevelLabel] for the human label.
  final int? trustLevel;

  /// Sentinel username the backend uses for a deleted author.
  static const String deletedUsername = '[deleted]';

  bool get isDeleted => username == deletedUsername;

  factory ForumAuthor.fromJson(Map<String, dynamic> json) {
    return ForumAuthor(
      username: json['username'] as String? ?? deletedUsername,
      displayName:
          json['display_name'] as String? ??
          json['username'] as String? ??
          deletedUsername,
      avatar: json['avatar'] as String?,
      trustLevel: json['trust_level'] as int?,
    );
  }

  /// Human-readable name — always non-empty (`display_name` falls back to
  /// `username` server-side, mirrored here defensively).
  String get name => displayName.isNotEmpty ? displayName : username;
}

/// Trust-level integer → label, mirroring backend `ForumProfile.TrustLevel`
/// and the web `TRUST_LEVEL_LABELS`. Level 0 ("New") is intentionally
/// un-badged in the UI (see the badge gate in `TrustBadge`).
const Map<int, String> forumTrustLevelLabels = {
  0: 'New',
  1: 'Basic',
  2: 'Member',
  3: 'Regular',
  4: 'Leader',
};

/// Label for a trust level, with a `Level {n}` fallback for unknown ints.
String? trustLevelLabel(int? level) {
  if (level == null) return null;
  return forumTrustLevelLabels[level] ?? 'Level $level';
}
