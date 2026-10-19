// The topic socket's URL: the API's scheme and host, with no /api/v1.
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/live/forum_live_channel.dart';

void main() {
  test('topicLiveUri keeps the host and swaps http for ws', () {
    expect(
      topicLiveUri('http://localhost:8000/api/v1', 12).toString(),
      'ws://localhost:8000/ws/forum/topics/12/',
    );
  });

  test('topicLiveUri keeps the host and swaps https for wss', () {
    expect(
      topicLiveUri('https://api.houseplant-md.com/api/v1', 12).toString(),
      'wss://api.houseplant-md.com/ws/forum/topics/12/',
    );
  });
}
