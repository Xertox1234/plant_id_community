/// The caller's forum notification choices from `GET/PATCH forum/me/profile/`
/// (todo 620): the digest cadence (todo 340) and the per-event push/email
/// matrix (todo 343). Web Settings edits the same two fields, so both clients
/// show one set of choices (docs/notifications-policy.md).
///
/// Only the cells the server sends exist: email is wired for replies alone.
/// A cell that is missing has no delivery path and is not offered.
class ForumNotificationSettings {
  const ForumNotificationSettings({
    required this.digestFrequency,
    required this.preferences,
  });

  /// `off` or `weekly`.
  final String digestFrequency;

  /// `{verb: {channel: bool}}`, e.g. `{'reply': {'push': true, 'email': false}}`.
  final Map<String, Map<String, bool>> preferences;

  static const digestOff = 'off';
  static const digestWeekly = 'weekly';

  bool get digestOn => digestFrequency == digestWeekly;

  /// The stored value of one cell, or null when the server sent no such cell.
  bool? cell(String verb, String channel) => preferences[verb]?[channel];

  /// A copy with one cell set; the maps are replaced, never mutated.
  ForumNotificationSettings withCell(String verb, String channel, bool value) {
    return ForumNotificationSettings(
      digestFrequency: digestFrequency,
      preferences: {
        for (final entry in preferences.entries)
          entry.key: entry.key == verb
              ? {...entry.value, channel: value}
              : entry.value,
      },
    );
  }

  ForumNotificationSettings withDigest(String frequency) {
    return ForumNotificationSettings(
      digestFrequency: frequency,
      preferences: preferences,
    );
  }

  /// Tolerant of a skewed backend: junk cells (non-bool values, non-map rows)
  /// are dropped, never thrown on.
  factory ForumNotificationSettings.fromJson(Map<String, dynamic> json) {
    final raw = json['notification_preferences'];
    final matrix = <String, Map<String, bool>>{};
    if (raw is Map) {
      raw.forEach((verb, row) {
        if (verb is! String || row is! Map) return;
        final cells = <String, bool>{};
        row.forEach((channel, value) {
          if (channel is String && value is bool) cells[channel] = value;
        });
        if (cells.isNotEmpty) matrix[verb] = cells;
      });
    }
    final digest = json['digest_frequency'];
    return ForumNotificationSettings(
      digestFrequency: digest is String ? digest : digestOff,
      preferences: matrix,
    );
  }
}
