// parseLiveFrame: the only door from the topic socket into the app. Anything
// it does not recognise is dropped, so a stray frame fetches nothing.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/live/forum_live_event.dart';

void main() {
  String frame(Map<String, Object?> m) => jsonEncode(m);

  test('parses each of the five types', () {
    const cases = {
      'post.created': LiveEventType.postCreated,
      'post.updated': LiveEventType.postUpdated,
      'post.removed': LiveEventType.postRemoved,
    };
    cases.forEach((wire, type) {
      final parsed = parseLiveFrame(
        frame({'v': 1, 'type': wire, 'topic_id': 12, 'post_id': 34}),
      );
      expect(parsed, isA<LiveEvent>(), reason: wire);
      final event = parsed! as LiveEvent;
      expect(event.type, type);
      expect(event.topicId, 12);
      expect(event.postId, 34);
    });

    for (final (wire, type) in [
      ('topic.updated', LiveEventType.topicUpdated),
      ('topic.removed', LiveEventType.topicRemoved),
    ]) {
      final event =
          parseLiveFrame(frame({'v': 1, 'type': wire, 'topic_id': 12}))!
              as LiveEvent;
      expect(event.type, type);
      expect(event.topicId, 12);
      expect(event.postId, isNull);
    }
  });

  test('maps a pong', () {
    expect(parseLiveFrame(frame({'v': 1, 'type': 'pong'})), isA<LivePong>());
  });

  test('null for v != 1', () {
    expect(
      parseLiveFrame(
        frame({'v': 2, 'type': 'post.created', 'topic_id': 1, 'post_id': 2}),
      ),
      isNull,
    );
    expect(
      parseLiveFrame(
        frame({'type': 'post.created', 'topic_id': 1, 'post_id': 2}),
      ),
      isNull,
    );
  });

  test('null for an unknown type', () {
    expect(
      parseLiveFrame(
        frame({'v': 1, 'type': 'post.reacted', 'topic_id': 1, 'post_id': 2}),
      ),
      isNull,
    );
  });

  test('null for bad JSON', () {
    expect(parseLiveFrame('{not json'), isNull);
    expect(parseLiveFrame('[1,2]'), isNull);
    expect(parseLiveFrame('"text"'), isNull);
    expect(parseLiveFrame(null), isNull);
  });

  test('null for a List<int> (binary) frame', () {
    expect(
      parseLiveFrame(
        utf8.encode(
          frame({'v': 1, 'type': 'post.created', 'topic_id': 1, 'post_id': 2}),
        ),
      ),
      isNull,
    );
  });

  test('null for a post event with no integer post_id', () {
    expect(
      parseLiveFrame(frame({'v': 1, 'type': 'post.created', 'topic_id': 1})),
      isNull,
    );
    expect(
      parseLiveFrame(
        frame({'v': 1, 'type': 'post.updated', 'topic_id': 1, 'post_id': '2'}),
      ),
      isNull,
    );
  });

  test('null for a non-integer topic_id', () {
    expect(
      parseLiveFrame(
        frame({'v': 1, 'type': 'post.created', 'topic_id': '1', 'post_id': 2}),
      ),
      isNull,
    );
    expect(parseLiveFrame(frame({'v': 1, 'type': 'topic.updated'})), isNull);
  });

  test('ignores extra fields', () {
    final event =
        parseLiveFrame(
              frame({
                'v': 1,
                'type': 'post.created',
                'topic_id': 1,
                'post_id': 2,
                'extra': {'a': 1},
              }),
            )!
            as LiveEvent;
    expect(event.postId, 2);
  });
}
