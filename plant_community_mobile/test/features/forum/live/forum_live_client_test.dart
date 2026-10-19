// ForumLiveClient: connect, the close-code rules, backoff and heartbeat
// (live forum replies, slice 4). testWidgets runs on fake time, so pump(d)
// drives every timer, and a timer left running fails the test.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/live/forum_live_client.dart';
import 'package:plant_community_mobile/features/forum/live/forum_live_event.dart';

import '../support/forum_test_support.dart';

class _Harness {
  _Harness({String? token = 'tok-1'}) : _token = token;

  final connector = FakeLiveConnector();
  final events = <LiveEvent>[];
  final statuses = <LiveStatus>[];
  int opens = 0;
  int refreshes = 0;
  String? _token;

  /// What the next refreshAuth installs as the token.
  String? refreshedToken;

  late final client = ForumLiveClient(
    connect: connector.fn,
    uri: Uri.parse('ws://localhost:8000/ws/forum/topics/10/'),
    token: () => _token,
    refreshAuth: () async {
      refreshes++;
      if (refreshedToken != null) _token = refreshedToken;
    },
    onEvent: events.add,
    onOpen: () => opens++,
    onStatus: statuses.add,
    random: () => 0.5,
  );

  LiveStatus? get status => statuses.isEmpty ? null : statuses.last;
}

void main() {
  test(
    'liveBackoff: at random 0.5, attempt 0 is 3000 ms and attempt 3 is '
    '15500 ms (the cap already applies); at random 1.0, attempt 10 is 30000 ms',
    () {
      expect(liveBackoff(0, 0.5), const Duration(milliseconds: 3000));
      expect(liveBackoff(3, 0.5), const Duration(milliseconds: 15500));
      expect(liveBackoff(10, 1.0), const Duration(milliseconds: 30000));
      expect(liveBackoff(0, 0), const Duration(milliseconds: 1000));
      expect(liveBackoff(0, 1.0), const Duration(milliseconds: 5000));
      expect(liveBackoff(1000, 1.0), const Duration(milliseconds: 30000));
    },
  );

  testWidgets('sends the bearer header and reports connecting then live, '
      'calling onOpen', (tester) async {
    final h = _Harness();
    h.client.start();
    await tester.pump();

    expect(h.connector.connects, hasLength(1));
    expect(
      h.connector.connects.single.uri.toString(),
      'ws://localhost:8000/ws/forum/topics/10/',
    );
    expect(h.connector.connects.single.headers, {
      'Authorization': 'Bearer tok-1',
    });
    expect(h.statuses, [LiveStatus.connecting, LiveStatus.live]);
    expect(h.opens, 1);
    await h.client.close();
  });

  testWidgets('no token: no connect, status stopped', (tester) async {
    final h = _Harness(token: null);
    h.client.start();
    await tester.pump(const Duration(minutes: 1));

    expect(h.connector.connects, isEmpty);
    expect(h.status, LiveStatus.stopped);
  });

  testWidgets('delivers events and drops null frames and pongs', (
    tester,
  ) async {
    final h = _Harness();
    h.client.start();
    await tester.pump();

    h.connector.last
      ..serverEvent('post.created', postId: 5)
      ..serverFrame('{bad')
      ..serverFrame(jsonEncode({'v': 1, 'type': 'pong'}))
      ..serverFrame(utf8.encode('binary'))
      ..serverEvent('topic.updated');
    await tester.pump();

    expect(h.events.map((e) => e.type), [
      LiveEventType.postCreated,
      LiveEventType.topicUpdated,
    ]);
    expect(h.events.first.postId, 5);
    await h.client.close();
  });

  testWidgets('does not reconnect after 4503', (tester) async {
    final h = _Harness();
    h.client.start();
    await tester.pump();

    h.connector.last.serverClose(liveCloseDisabled);
    await tester.pump(const Duration(minutes: 2));

    expect(h.connector.connects, hasLength(1));
    expect(h.status, LiveStatus.stopped);

    await h.client.close();
    await tester.pump(const Duration(minutes: 2));
    expect(h.connector.connects, hasLength(1));
  });

  testWidgets('does not reconnect after 4429', (tester) async {
    final h = _Harness();
    h.client.start();
    await tester.pump();

    h.connector.last.serverClose(liveCloseLimited);
    await tester.pump(const Duration(minutes: 2));

    expect(h.connector.connects, hasLength(1));
    expect(h.status, LiveStatus.stopped);
  });

  testWidgets('4404 reports gone and does not reconnect', (tester) async {
    final h = _Harness();
    h.client.start();
    await tester.pump();

    h.connector.last.serverClose(liveCloseNotFound);
    await tester.pump(const Duration(minutes: 2));

    expect(h.connector.connects, hasLength(1));
    expect(h.status, LiveStatus.gone);
  });

  testWidgets('4401 refreshes once and reconnects once; a second 4401 stops', (
    tester,
  ) async {
    final h = _Harness()..refreshedToken = 'tok-2';
    h.client.start();
    await tester.pump();

    h.connector.last.serverClose(liveCloseUnauthenticated);
    await tester.pump();

    expect(h.refreshes, 1);
    expect(h.connector.connects, hasLength(2));
    expect(h.connector.connects.last.headers, {
      'Authorization': 'Bearer tok-2',
    });

    h.connector.last.serverClose(liveCloseUnauthenticated);
    await tester.pump(const Duration(minutes: 2));

    expect(h.refreshes, 1);
    expect(h.connector.connects, hasLength(2));
    expect(h.status, LiveStatus.stopped);
  });

  testWidgets('a 4401 after a connection that worked refreshes again', (
    tester,
  ) async {
    final h = _Harness();
    h.client.start();
    await tester.pump();
    h.connector.last.serverClose(liveCloseUnauthenticated);
    await tester.pump();
    // The reconnect works: a frame arrives. Much later the network drops and
    // the reconnect finds the token expired again.
    h.connector.last.serverEvent('topic.updated');
    await tester.pump();
    h.connector.last.serverClose(null);
    await tester.pump(const Duration(seconds: 3));
    expect(h.connector.connects, hasLength(3));

    h.connector.last.serverClose(liveCloseUnauthenticated);
    await tester.pump();

    expect(h.refreshes, 2);
    expect(h.connector.connects, hasLength(4));
    await h.client.close();
  });

  testWidgets('a thrown connect retries with backoff', (tester) async {
    final h = _Harness();
    h.connector.throwOnConnect = const WebSocketException('refused');
    h.client.start();
    await tester.pump();
    expect(h.connector.connects, hasLength(1));

    await tester.pump(const Duration(milliseconds: 2999));
    expect(h.connector.connects, hasLength(1));
    await tester.pump(const Duration(milliseconds: 1));
    expect(h.connector.connects, hasLength(2));
    await h.client.close();
  });

  testWidgets('the backoff resets after a successful open', (tester) async {
    final h = _Harness();
    h.connector.throwOnConnect = const WebSocketException('refused');
    h.client.start();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 3000)); // attempt 0
    await tester.pump(const Duration(milliseconds: 5000)); // attempt 1: 5 s
    expect(h.connector.connects, hasLength(3));

    h.connector.throwOnConnect = null;
    await tester.pump(const Duration(milliseconds: 9000)); // attempt 2: 9 s
    expect(h.connector.connects, hasLength(4));
    expect(h.status, LiveStatus.live);

    h.connector.last.serverClose(1006);
    await tester.pump(const Duration(milliseconds: 2999));
    expect(h.connector.connects, hasLength(4));
    await tester.pump(const Duration(milliseconds: 1));
    expect(h.connector.connects, hasLength(5));
    await h.client.close();
  });

  testWidgets('pings every 25 s, and reconnects when no frame arrives within '
      '10 s', (tester) async {
    final h = _Harness();
    h.client.start();
    await tester.pump();
    final first = h.connector.last;

    await tester.pump(livePingInterval);
    expect(first.sent, ['{"type":"ping"}']);

    await tester.pump(livePongTimeout);
    expect(first.closedByClient, isTrue);
    expect(h.status, isNot(LiveStatus.live));

    await tester.pump(const Duration(seconds: 3));
    expect(h.connector.connects, hasLength(2));
    expect(h.status, LiveStatus.live);
    await h.client.close();
  });

  testWidgets('any frame clears the pong timer', (tester) async {
    final h = _Harness();
    h.client.start();
    await tester.pump();
    final first = h.connector.last;

    await tester.pump(livePingInterval);
    first.serverFrame(jsonEncode({'v': 1, 'type': 'pong'}));
    await tester.pump(livePongTimeout);

    expect(first.closedByClient, isFalse);
    expect(h.connector.connects, hasLength(1));
    await tester.pump(livePingInterval);
    expect(first.sent, hasLength(2));
    await h.client.close();
  });

  testWidgets('close() stops everything', (tester) async {
    final h = _Harness();
    h.client.start();
    await tester.pump();
    final first = h.connector.last;

    await h.client.close();
    await tester.pump(const Duration(minutes: 2));

    expect(first.closedByClient, isTrue);
    expect(h.connector.connects, hasLength(1));
    expect(h.status, LiveStatus.off);
  });

  testWidgets('close() during an in-flight connect closes that channel when '
      'it arrives', (tester) async {
    final h = _Harness();
    h.connector.gate = Completer<void>();
    h.client.start();
    await tester.pump();

    await h.client.close();
    h.connector.gate!.complete();
    await tester.pump();

    expect(h.connector.channels.single.closedByClient, isTrue);
    expect(h.opens, 0);
    expect(h.status, LiveStatus.off);
  });
}
