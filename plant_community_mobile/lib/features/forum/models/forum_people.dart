import 'forum_author.dart';

/// One `GET users/search/?q=` row — `{username, display_name}` — for the
/// composer's @mention autocomplete (todo 341 wave 4). Only the literal
/// `@username` ever reaches the wire: the server resolves mentions with its
/// own regex against real usernames (`wagtail_forum/mentions.py`).
class ForumMentionUser {
  const ForumMentionUser({required this.username, required this.displayName});

  final String username;
  final String displayName;

  factory ForumMentionUser.fromJson(Map<String, dynamic> json) {
    final username = json['username'] as String? ?? '';
    return ForumMentionUser(
      username: username,
      displayName: json['display_name'] as String? ?? username,
    );
  }
}

/// One `GET users/experts/` row: the shared author shape plus `online`
/// (`EXPERT_AUTHOR_SCHEMA`, todo 301). `online` is computed by that view
/// only — it is not part of every topic/post author payload.
class ForumExpert {
  const ForumExpert({required this.author, required this.online});

  final ForumAuthor author;
  final bool online;

  factory ForumExpert.fromJson(Map<String, dynamic> json) {
    return ForumExpert(
      author: ForumAuthor.fromJson(json),
      online: json['online'] as bool? ?? false,
    );
  }
}
