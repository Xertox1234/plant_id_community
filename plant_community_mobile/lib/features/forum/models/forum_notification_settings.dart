/// The caller's forum notification choices from `GET/PATCH forum/me/profile/`
/// (todo 620): the digest cadence (todo 340) and the per-event push/email
/// matrix (todo 343). Web Settings edits the same two fields, so both clients
/// show one set of choices (docs/notifications-policy.md).
///
/// Only the cells the server sends exist: since todo 624 email is wired for
/// every event (off by default except replies). A cell that is missing has
/// no delivery path and is not offered.
class ForumNotificationSettings {
  const ForumNotificationSettings({
    required this.digestFrequency,
    required this.preferences,
    this.quietHours,
  });

  /// `off` or `weekly`; null when the server sent neither (deploy skew).
  /// Such a digest is not offered, never guessed: showing it as off would
  /// make the next tap write `weekly` over a choice nobody saw (todo 651).
  final String? digestFrequency;

  /// `{verb: {channel: bool}}`, e.g. `{'reply': {'push': true, 'email': false}}`.
  final Map<String, Map<String, bool>> preferences;

  /// Quiet hours (todo 624), or null when the server sent none (a backend
  /// from before them): then they are not offered.
  final QuietHours? quietHours;

  static const digestOff = 'off';
  static const digestWeekly = 'weekly';

  bool get digestOn => digestFrequency == digestWeekly;

  /// Whether the server sent a digest cadence this client understands.
  bool get hasDigest => digestFrequency != null;

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
      quietHours: quietHours,
    );
  }

  ForumNotificationSettings withDigest(String frequency) {
    return ForumNotificationSettings(
      digestFrequency: frequency,
      preferences: preferences,
      quietHours: quietHours,
    );
  }

  ForumNotificationSettings withQuietHours(QuietHours value) {
    return ForumNotificationSettings(
      digestFrequency: digestFrequency,
      preferences: preferences,
      quietHours: value,
    );
  }

  /// Tolerant of a skewed backend: junk cells (non-bool values, non-map rows)
  /// are dropped, never thrown on, and a missing or unknown digest cadence
  /// is null, not `off`.
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
      digestFrequency: digest == digestOff || digest == digestWeekly
          ? digest as String
          : null,
      preferences: matrix,
      quietHours: QuietHours.fromJson(json),
    );
  }
}

/// Quiet hours (todo 624): opt-in; pushes and emails that arrive between
/// [start] and [end] ("HH:MM", wall-clock in [timeZone]) wait until the
/// window ends. Security email always sends; the in-app inbox is unaffected.
class QuietHours {
  const QuietHours({
    required this.enabled,
    required this.start,
    required this.end,
    required this.timeZone,
  });

  final bool enabled;
  final String start;
  final String end;

  /// The IANA zone a client reported; empty means the server uses UTC.
  final String timeZone;

  static final _hhmm = RegExp(r'^\d{2}:\d{2}$');

  /// The zone the window is read in, as a member should see it.
  String get shownZone => timeZone.isEmpty ? 'UTC' : timeZone;

  QuietHours copyWith({
    bool? enabled,
    String? start,
    String? end,
    String? timeZone,
  }) => QuietHours(
    enabled: enabled ?? this.enabled,
    start: start ?? this.start,
    end: end ?? this.end,
    timeZone: timeZone ?? this.timeZone,
  );

  /// Null unless the server sent the switch and two valid times.
  static QuietHours? fromJson(Map<String, dynamic> json) {
    final enabled = json['quiet_hours_enabled'];
    final start = json['quiet_hours_start'];
    final end = json['quiet_hours_end'];
    if (enabled is! bool || start is! String || end is! String) return null;
    if (!_hhmm.hasMatch(start) || !_hhmm.hasMatch(end)) return null;
    final zone = json['time_zone'];
    return QuietHours(
      enabled: enabled,
      start: start,
      end: end,
      timeZone: zone is String ? zone : '',
    );
  }
}
