/// A lightweight topic stub returned by the `/forum/sync/` delta endpoint —
/// `{id, slug, title, updated_at}`. Sync returns stubs only; full detail and
/// bodies are fetched separately.
class ForumTopicStub {
  const ForumTopicStub({
    required this.id,
    required this.slug,
    required this.title,
    required this.updatedAt,
  });

  final int id;
  final String slug;
  final String title;
  final DateTime updatedAt;

  factory ForumTopicStub.fromJson(Map<String, dynamic> json) {
    return ForumTopicStub(
      id: json['id'] as int,
      slug: json['slug'] as String? ?? '',
      title: json['title'] as String? ?? '',
      updatedAt:
          DateTime.tryParse(json['updated_at'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'slug': slug,
    'title': title,
    'updated_at': updatedAt.toIso8601String(),
  };

  @override
  bool operator ==(Object other) =>
      other is ForumTopicStub &&
      other.id == id &&
      other.slug == slug &&
      other.title == title &&
      other.updatedAt.isAtSameMomentAs(updatedAt);

  @override
  int get hashCode => Object.hash(id, slug, title, updatedAt);
}

/// A tombstone from the sync `deleted` array — `{topic_id, board_id}`. Only
/// populated when `since` is provided.
class ForumTombstone {
  const ForumTombstone({required this.topicId, required this.boardId});

  final int topicId;
  final int boardId;

  factory ForumTombstone.fromJson(Map<String, dynamic> json) {
    return ForumTombstone(
      topicId: json['topic_id'] as int,
      boardId: json['board_id'] as int? ?? 0,
    );
  }
}

/// One page of the `/forum/sync/` response.
class ForumSyncPage {
  const ForumSyncPage({
    required this.topics,
    required this.deleted,
    required this.hasMore,
    this.nextSince,
    this.nextSinceId,
  });

  final List<ForumTopicStub> topics;
  final List<ForumTombstone> deleted;
  final bool hasMore;

  /// Pass back as `since` on the next request. `null` echoes back the
  /// incoming cursor for an empty batch.
  final DateTime? nextSince;

  /// Pass back as `since_id` on the next request.
  final int? nextSinceId;

  factory ForumSyncPage.fromJson(Map<String, dynamic> json) {
    return ForumSyncPage(
      topics: (json['topics'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ForumTopicStub.fromJson)
          .toList(growable: false),
      deleted: (json['deleted'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ForumTombstone.fromJson)
          .toList(growable: false),
      hasMore: json['has_more'] as bool? ?? false,
      nextSince: DateTime.tryParse(json['next_since'] as String? ?? ''),
      nextSinceId: json['next_since_id'] as int?,
    );
  }
}

/// The keyset cursor persisted between sync runs: `(since, since_id)`. A
/// `null` [since] means "never synced" → the next sync is a full pull.
class ForumSyncCursor {
  const ForumSyncCursor({this.since, this.sinceId});

  final DateTime? since;
  final int? sinceId;

  bool get isInitial => since == null;

  Map<String, dynamic> toJson() => {
    'since': since?.toIso8601String(),
    'since_id': sinceId,
  };

  factory ForumSyncCursor.fromJson(Map<String, dynamic> json) {
    return ForumSyncCursor(
      since: DateTime.tryParse(json['since'] as String? ?? ''),
      sinceId: json['since_id'] as int?,
    );
  }
}
