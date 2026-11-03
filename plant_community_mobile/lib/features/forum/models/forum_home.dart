/// Models for the redesigned forum home: the recent-topics feed
/// (`GET /forum/topics/recent/`), a topic's latest-replies peek
/// (`GET /forum/topics/<id>/latest-replies/`) and the community stats
/// (`GET /forum/community/stats/`).
library;

import 'package:flutter/foundation.dart';

import 'forum_author.dart';
import 'forum_topic.dart';

DateTime? _date(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}

ForumAuthor? _author(dynamic value) =>
    value is Map<String, dynamic> ? ForumAuthor.fromJson(value) : null;

List<ForumAuthor> _authors(dynamic value) =>
    (value as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(ForumAuthor.fromJson)
        .toList(growable: false);

/// One row of the home activity feed.
@immutable
class ForumRecentTopic {
  const ForumRecentTopic({
    required this.id,
    required this.slug,
    required this.title,
    required this.board,
    required this.replyCount,
    this.lastPostAt,
    this.isPinned = false,
    this.isSolved = false,
    this.isUnread = false,
    this.thumbnailUrl,
    this.imageUrl,
  });

  final int id;
  final String slug;
  final String title;
  final ForumTopicBoardRef board;
  final int replyCount;
  final DateTime? lastPostAt;
  final bool isPinned;
  final bool isSolved;
  final bool isUnread;
  final String? thumbnailUrl;

  /// A wide image for the card, or `null` (older servers never send it).
  final String? imageUrl;

  bool get hasPicture => imageUrl != null;

  factory ForumRecentTopic.fromJson(Map<String, dynamic> json) {
    final board = json['board'];
    return ForumRecentTopic(
      id: json['id'] as int? ?? 0,
      slug: json['slug'] as String? ?? '',
      title: json['title'] as String? ?? '',
      // The feed's board is `{id, name, slug}`; `name` is the ref's title.
      board: board is Map<String, dynamic>
          ? ForumTopicBoardRef(
              id: board['id'] as int? ?? 0,
              slug: board['slug'] as String? ?? '',
              title: board['name'] as String? ?? '',
            )
          : const ForumTopicBoardRef(id: 0, slug: '', title: ''),
      replyCount: json['reply_count'] as int? ?? 0,
      lastPostAt: _date(json['last_post_at']),
      isPinned: json['is_pinned'] as bool? ?? false,
      isSolved: json['is_solved'] as bool? ?? false,
      isUnread: json['is_unread'] as bool? ?? false,
      thumbnailUrl: json['thumbnail_url'] as String?,
      imageUrl: json['image_url'] as String?,
    );
  }
}

/// A single reply in the latest-replies peek.
@immutable
class ForumLatestReply {
  const ForumLatestReply({
    required this.id,
    required this.author,
    required this.excerpt,
    this.createdAt,
  });

  final int id;
  final ForumAuthor author;
  final DateTime? createdAt;
  final String excerpt;

  factory ForumLatestReply.fromJson(Map<String, dynamic> json) {
    return ForumLatestReply(
      id: json['id'] as int? ?? 0,
      author:
          _author(json['author']) ??
          const ForumAuthor(
            username: ForumAuthor.deletedUsername,
            displayName: ForumAuthor.deletedUsername,
          ),
      createdAt: _date(json['created_at']),
      excerpt: json['excerpt'] as String? ?? '',
    );
  }
}

/// The latest-replies peek for one topic.
@immutable
class ForumLatestReplies {
  const ForumLatestReplies({
    this.replies = const [],
    this.solution,
    this.moreCount = 0,
    this.participantCount = 0,
    this.participants = const [],
    this.startedBy,
  });

  final List<ForumLatestReply> replies;
  final ForumLatestReply? solution;
  final int moreCount;
  final int participantCount;
  final List<ForumAuthor> participants;
  final ForumAuthor? startedBy;

  bool get isEmpty => replies.isEmpty && solution == null;

  factory ForumLatestReplies.fromJson(Map<String, dynamic> json) {
    final solution = json['solution'];
    return ForumLatestReplies(
      replies: (json['replies'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ForumLatestReply.fromJson)
          .toList(growable: false),
      solution: solution is Map<String, dynamic>
          ? ForumLatestReply.fromJson(solution)
          : null,
      moreCount: json['more_count'] as int? ?? 0,
      participantCount: json['participant_count'] as int? ?? 0,
      participants: _authors(json['participants']),
      startedBy: _author(json['started_by']),
    );
  }
}

/// Community-wide counters for "Who's online".
@immutable
class ForumCommunityStats {
  const ForumCommunityStats({
    this.membersOnline = 0,
    this.onlineSample = const [],
    this.registeredMembers = 0,
    this.topicCount = 0,
    this.postCount = 0,
    this.newestMember,
  });

  final int membersOnline;
  final List<ForumAuthor> onlineSample;
  final int registeredMembers;
  final int topicCount;
  final int postCount;
  final ForumAuthor? newestMember;

  factory ForumCommunityStats.fromJson(Map<String, dynamic> json) {
    return ForumCommunityStats(
      membersOnline: json['members_online'] as int? ?? 0,
      onlineSample: _authors(json['online_sample']),
      registeredMembers: json['registered_members'] as int? ?? 0,
      topicCount: json['topic_count'] as int? ?? 0,
      postCount: json['post_count'] as int? ?? 0,
      newestMember: _author(json['newest_member']),
    );
  }
}
