/// An earned badge — `{slug, name, description, awarded_at}` (`BADGE_SCHEMA`,
/// todo 348). Carried by both `GET me/stats/` and the public profile: earned
/// badges are public identity.
class ForumBadge {
  const ForumBadge({
    required this.slug,
    required this.name,
    required this.description,
    this.awardedAt,
  });

  final String slug;
  final String name;
  final String description;
  final DateTime? awardedAt;

  factory ForumBadge.fromJson(Map<String, dynamic> json) {
    return ForumBadge(
      slug: json['slug'] as String? ?? '',
      name: json['name'] as String? ?? '',
      description: json['description'] as String? ?? '',
      awardedAt: _parseDate(json['awarded_at']),
    );
  }
}

/// Parse a `badges` array (shared by the stats and profile payloads).
List<ForumBadge> parseForumBadges(dynamic raw) {
  if (raw is! List) return const [];
  return raw
      .whereType<Map<String, dynamic>>()
      .map(ForumBadge.fromJson)
      .toList(growable: false);
}

/// The requesting member's all-time forum stats (`GET me/stats/`,
/// `ME_STATS_SCHEMA` — todo 300/348; todo 341 wave 4). All-time by design:
/// no season windowing, so no sublabel here may claim one.
class ForumMyStats {
  const ForumMyStats({
    required this.posts,
    required this.solutionsAccepted,
    required this.identificationsShared,
    required this.streakDays,
    required this.badgeName,
    required this.badgeProgress,
    required this.badgeTarget,
    required this.badges,
  });

  final int posts;
  final int solutionsAccepted;
  final int identificationsShared;
  final int streakDays;

  /// The single tracked-progress badge (Botanist): its metric is
  /// [identificationsShared], capped at [badgeTarget] server-side so a
  /// member past the threshold reads as complete, not overflowing.
  final String badgeName;
  final int badgeProgress;
  final int badgeTarget;

  /// Earned badges in display order.
  final List<ForumBadge> badges;

  bool get badgeComplete => badgeTarget > 0 && badgeProgress >= badgeTarget;

  factory ForumMyStats.fromJson(Map<String, dynamic> json) {
    return ForumMyStats(
      posts: json['posts'] as int? ?? 0,
      solutionsAccepted: json['solutions_accepted'] as int? ?? 0,
      identificationsShared: json['identifications_shared'] as int? ?? 0,
      streakDays: json['streak_days'] as int? ?? 0,
      badgeName: json['badge_name'] as String? ?? '',
      badgeProgress: json['badge_progress'] as int? ?? 0,
      badgeTarget: json['badge_target'] as int? ?? 0,
      badges: parseForumBadges(json['badges']),
    );
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}
