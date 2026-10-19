import 'dart:convert';

/// Where a topic's live connection stands.
///
/// `stopped` means it will not retry for this foreground session (4503 flag
/// off, 4429 socket cap, a second 4401, or no token); `gone` means the topic
/// itself is no longer visible (4404 or `topic.removed`).
enum LiveStatus { off, connecting, live, stopped, gone }

enum LiveEventType {
  postCreated,
  postUpdated,
  postRemoved,
  topicUpdated,
  topicRemoved,
}

const _wireTypes = {
  'post.created': LiveEventType.postCreated,
  'post.updated': LiveEventType.postUpdated,
  'post.removed': LiveEventType.postRemoved,
  'topic.updated': LiveEventType.topicUpdated,
  'topic.removed': LiveEventType.topicRemoved,
};

/// One frame from the topic socket that the app understands.
sealed class LiveFrame {
  const LiveFrame();
}

/// The server's answer to a `{"type":"ping"}`.
final class LivePong extends LiveFrame {
  const LivePong();
}

/// `{"v":1,"type":T,"topic_id":int,"post_id":int}`; `topic.*` carry no post.
final class LiveEvent extends LiveFrame {
  const LiveEvent(this.type, {required this.topicId, this.postId});

  final LiveEventType type;
  final int topicId;
  final int? postId;

  bool get isPostEvent =>
      type == LiveEventType.postCreated ||
      type == LiveEventType.postUpdated ||
      type == LiveEventType.postRemoved;
}

/// Parses a socket frame, or returns null for anything the app doesn't
/// recognise: a binary frame, bad JSON, a version other than 1, an unknown
/// type, a non-integer `topic_id`, or a post event without an integer
/// `post_id`. A null frame is dropped and fetches nothing.
LiveFrame? parseLiveFrame(Object? data) {
  if (data is! String) return null;
  final Object? decoded;
  try {
    decoded = jsonDecode(data);
  } on FormatException {
    return null;
  }
  if (decoded is! Map<String, dynamic> || decoded['v'] != 1) return null;
  final wireType = decoded['type'];
  if (wireType == 'pong') return const LivePong();
  final type = _wireTypes[wireType];
  final topicId = decoded['topic_id'];
  if (type == null || topicId is! int) return null;
  final postId = decoded['post_id'];
  final event = LiveEvent(
    type,
    topicId: topicId,
    postId: postId is int ? postId : null,
  );
  if (event.isPostEvent && event.postId == null) return null;
  return event;
}
