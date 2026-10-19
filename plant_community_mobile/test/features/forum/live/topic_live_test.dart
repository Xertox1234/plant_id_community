// TopicLive: every decision about a live event for the open topic (live
// forum replies, slice 4). testWidgets runs on fake time, so pump(d) drives
// the debounce, and a timer left running fails the test.
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/live/forum_live_client.dart';
import 'package:plant_community_mobile/features/forum/live/forum_live_event.dart';
import 'package:plant_community_mobile/features/forum/live/live_updates_settings.dart';
import 'package:plant_community_mobile/features/forum/live/topic_live.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

/// The setting without FlutterSecureStorage.
class _FakeSetting extends LiveUpdatesSetting {
  _FakeSetting(this._initial);
  final bool _initial;

  @override
  bool build() => _initial;

  @override
  void setEnabled(bool on) => state = on;
}

class _Harness {
  _Harness({this.loggedIn = true, this.liveOn = true});

  final bool loggedIn;
  final bool liveOn;
  final api = FakeForumApi()
    ..topicDetail = topicDetail(replyCount: 1)
    ..posts = CursorPage(items: [post(id: 1), post(id: 2)]);
  final connector = FakeLiveConnector();
  late final ProviderContainer container;

  TopicLiveState get live => container.read(topicLiveProvider(10));
  TopicLive get notifier => container.read(topicLiveProvider(10).notifier);
  List<int> get ids => container
      .read(topicPostsProvider(10))
      .asData!
      .value
      .items
      .map((p) => p.id)
      .toList();
  FakeLiveChannel get channel => connector.last;

  Future<void> start(WidgetTester tester) async {
    container = ProviderContainer(
      overrides: [
        forumApiProvider.overrideWithValue(api),
        apiServiceProvider.overrideWithValue(
          ApiService(
            baseUrl: 'http://localhost:8000/api/v1',
            authToken: loggedIn ? 'test-jwt' : null,
          ),
        ),
        authServiceProvider.overrideWith(
          () => FakeAuthService(loggedIn: loggedIn),
        ),
        liveUpdatesSettingProvider.overrideWith(() => _FakeSetting(liveOn)),
        ...liveTestOverrides(connector),
      ],
    );
    container.listen(topicPostsProvider(10), (_, _) {});
    container.listen(topicDetailProvider(10), (_, _) {});
    await tester.pump();
    container.listen(topicLiveProvider(10), (_, _) {});
    await tester.pump();
  }

  /// Ends the test with no socket timer left running.
  Future<void> stop(WidgetTester tester) async {
    container.dispose();
    await tester.pump();
  }
}

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  testWidgets('connects when signed in with the setting on', (tester) async {
    final h = _Harness();
    await h.start(tester);

    expect(h.connector.connects, hasLength(1));
    expect(
      h.connector.connects.single.uri.toString(),
      'ws://localhost:8000/ws/forum/topics/10/',
    );
    expect(
      h.connector.connects.single.headers['Authorization'],
      'Bearer test-jwt',
    );
    expect(h.live.status, LiveStatus.live);
    await h.stop(tester);
  });

  testWidgets('no socket when signed out', (tester) async {
    final h = _Harness(loggedIn: false);
    await h.start(tester);

    expect(h.connector.connects, isEmpty);
    expect(h.live.status, LiveStatus.off);
    await h.stop(tester);
  });

  testWidgets('no socket when the setting is off', (tester) async {
    final h = _Harness(liveOn: false);
    await h.start(tester);

    expect(h.connector.connects, isEmpty);
    expect(h.live.status, LiveStatus.off);
    await h.stop(tester);
  });

  testWidgets('turning the setting off closes the socket', (tester) async {
    final h = _Harness();
    await h.start(tester);

    h.container.read(liveUpdatesSettingProvider.notifier).setEnabled(false);
    await tester.pump();

    expect(h.channel.closedByClient, isTrue);
    expect(h.live.status, LiveStatus.off);
    expect(h.connector.connects, hasLength(1));
    await h.stop(tester);
  });

  testWidgets('catch-up on open sets the pill from the peek count when every '
      'page is loaded', (tester) async {
    final h = _Harness();
    h.api.peekDetails = [topicDetail(replyCount: 3)];
    await h.start(tester);

    expect(h.api.peekCalls, 1);
    expect(h.live.pendingCount, 2);
    expect(
      h.container.read(topicDetailProvider(10)).asData!.value.replyCount,
      3,
    );
    await h.stop(tester);
  });

  testWidgets('catch-up leaves the pill alone with pages unloaded', (
    tester,
  ) async {
    final h = _Harness();
    h.api
      ..posts = CursorPage(items: [post(id: 1), post(id: 2)], next: 'p2')
      ..peekDetails = [topicDetail(replyCount: 9)];
    await h.start(tester);

    expect(h.api.peekCalls, 1);
    expect(h.live.pendingCount, 0);
    await h.stop(tester);
  });

  testWidgets('post.created at the bottom inserts and flashes', (tester) async {
    final h = _Harness();
    h.api.postsById[3] = post(id: 3);
    await h.start(tester);

    h.channel.serverEvent('post.created', postId: 3);
    await tester.pump();

    expect(h.ids, [1, 2, 3]);
    expect(h.live.flashIds, {3});
    expect(h.live.slideIds, {3});
    expect(h.live.pendingCount, 0);
    await h.stop(tester);
  });

  testWidgets('post.created when scrolled up counts in the pill', (
    tester,
  ) async {
    final h = _Harness();
    h.api.postsById[3] = post(id: 3);
    await h.start(tester);
    h.notifier.setReaderAtBottom(false);

    h.channel.serverEvent('post.created', postId: 3);
    await tester.pump();

    expect(h.ids, [1, 2]);
    expect(h.live.pendingCount, 1);
    expect(h.live.flashIds, isEmpty);
    await h.stop(tester);
  });

  testWidgets('post.created with pages unloaded counts in the pill', (
    tester,
  ) async {
    final h = _Harness();
    h.api
      ..posts = CursorPage(items: [post(id: 1), post(id: 2)], next: 'p2')
      ..postsById[3] = post(id: 3);
    await h.start(tester);

    h.channel.serverEvent('post.created', postId: 3);
    await tester.pump();

    expect(h.ids, [1, 2]);
    expect(h.live.pendingCount, 1);
    await h.stop(tester);
  });

  testWidgets('post.created while the pill is showing counts, never inserts', (
    tester,
  ) async {
    final h = _Harness();
    h.api.postsById
      ..[3] = post(id: 3)
      ..[4] = post(id: 4);
    await h.start(tester);
    h.notifier.setReaderAtBottom(false);
    h.channel.serverEvent('post.created', postId: 3);
    await tester.pump();

    h.notifier.setReaderAtBottom(true);
    h.channel.serverEvent('post.created', postId: 4);
    await tester.pump();

    expect(h.ids, [1, 2]);
    expect(h.live.pendingCount, 2);
    await h.stop(tester);
  });

  testWidgets('a post.created that 404s does nothing', (tester) async {
    final h = _Harness();
    await h.start(tester);

    h.channel.serverEvent('post.created', postId: 3);
    await tester.pump();

    expect(h.api.fetchPostCalls, [3]);
    expect(h.ids, [1, 2]);
    expect(h.live.pendingCount, 0);
    expect(h.live.introSeq, 0);
    await h.stop(tester);
  });

  testWidgets('a post.created already in the list does nothing', (
    tester,
  ) async {
    final h = _Harness();
    await h.start(tester);

    h.channel.serverEvent('post.created', postId: 2);
    await tester.pump();

    expect(h.api.fetchPostCalls, isEmpty);
    expect(h.live.pendingCount, 0);
    await h.stop(tester);
  });

  testWidgets('held post.created events already in the list are dropped', (
    tester,
  ) async {
    final h = _Harness();
    h.api.postsById[3] = post(id: 3);
    await h.start(tester);

    h.notifier.beginOwnReply();
    h.channel.serverEvent('post.created', postId: 3);
    await tester.pump();
    // The reply is published and the thread re-walks its pages.
    h.api.posts = CursorPage(items: [post(id: 1), post(id: 2), post(id: 3)]);
    await h.container.read(topicPostsProvider(10).notifier).refreshAfterReply();
    h.notifier.endOwnReply();
    await tester.pump();

    expect(h.ids, [1, 2, 3]);
    expect(h.api.fetchPostCalls, isEmpty);
    expect(h.live.pendingCount, 0);
    expect(h.live.introSeq, 0);
    expect(h.live.flashIds, isEmpty);
    await h.stop(tester);
  });

  testWidgets("a held event for someone else's reply that isn't in the list "
      'is applied on release', (tester) async {
    final h = _Harness();
    h.api.postsById[7] = post(id: 7);
    await h.start(tester);

    h.notifier.beginOwnReply();
    h.channel.serverEvent('post.created', postId: 7);
    await tester.pump();
    expect(h.ids, [1, 2]);

    h.notifier.endOwnReply();
    await tester.pump();

    expect(h.ids, [1, 2, 7]);
    expect(h.live.flashIds, {7});
    await h.stop(tester);
  });

  testWidgets('post.updated splices the fetched post', (tester) async {
    final h = _Harness();
    h.api.postsById[2] = post(id: 2, body: const [ParagraphBlock('edited')]);
    await h.start(tester);

    h.channel.serverEvent('post.updated', postId: 2);
    await tester.pump();

    final items = h.container.read(topicPostsProvider(10)).asData!.value.items;
    expect(items[1].body, [const ParagraphBlock('edited')]);
    expect(h.live.pendingCount, 0);
    await h.stop(tester);
  });

  testWidgets('post.removed removes it, and removing the accepted answer '
      'refetches the topic', (tester) async {
    final h = _Harness();
    h.api.topicDetail = topicDetail(replyCount: 1, solvedPostId: 2);
    await h.start(tester);
    final peeksBefore = h.api.peekCalls;

    h.channel.serverEvent('post.removed', postId: 2);
    await tester.pump();
    expect(h.ids, [1]);

    await tester.pump(const Duration(milliseconds: 500));
    expect(h.api.peekCalls, peeksBefore + 1);
    await h.stop(tester);
  });

  testWidgets('topic.updated: three events in 500 ms make one peek read', (
    tester,
  ) async {
    final h = _Harness();
    await h.start(tester);
    final peeksBefore = h.api.peekCalls;
    h.api.peekDetails = [topicDetail(replyCount: 1, locked: true)];

    for (var i = 0; i < 3; i++) {
      h.channel.serverEvent('topic.updated');
      await tester.pump(const Duration(milliseconds: 100));
    }
    await tester.pump(const Duration(milliseconds: 500));

    expect(h.api.peekCalls, peeksBefore + 1);
    expect(
      h.container.read(topicDetailProvider(10)).asData!.value.locked,
      isTrue,
    );
    await h.stop(tester);
  });

  testWidgets('topic.removed sets gone', (tester) async {
    final h = _Harness();
    await h.start(tester);

    h.channel.serverEvent('topic.removed');
    await tester.pump(const Duration(minutes: 1));

    expect(h.live.status, LiveStatus.gone);
    expect(h.channel.closedByClient, isTrue);
    expect(h.connector.connects, hasLength(1));
    await h.stop(tester);
  });

  testWidgets('a 4404 close sets gone', (tester) async {
    final h = _Harness();
    await h.start(tester);

    h.channel.serverClose(liveCloseNotFound);
    await tester.pump(const Duration(minutes: 1));

    expect(h.live.status, LiveStatus.gone);
    await h.stop(tester);
  });

  testWidgets('ignores an event for another topic', (tester) async {
    final h = _Harness();
    h.api.postsById[3] = post(id: 3);
    await h.start(tester);

    h.channel
      ..serverEvent('post.created', topicId: 99, postId: 3)
      ..serverEvent('post.updated', topicId: 99, postId: 2)
      ..serverEvent('topic.removed', topicId: 99);
    await tester.pump(const Duration(seconds: 1));

    expect(h.api.fetchPostCalls, isEmpty);
    expect(h.live.status, LiveStatus.live);
    expect(h.ids, [1, 2]);
    await h.stop(tester);
  });

  testWidgets('the intro is due once, on the first insert', (tester) async {
    final h = _Harness();
    h.api.postsById
      ..[3] = post(id: 3)
      ..[4] = post(id: 4);
    await h.start(tester);

    h.channel.serverEvent('post.created', postId: 3);
    await tester.pump();
    expect(h.live.introSeq, 1);

    h.channel.serverEvent('post.created', postId: 4);
    await tester.pump();
    expect(h.live.introSeq, 1);
    expect(h.ids, [1, 2, 3, 4]);
    await h.stop(tester);
  });

  testWidgets('a catch-up pill does not trigger the intro', (tester) async {
    final h = _Harness();
    h.api.peekDetails = [topicDetail(replyCount: 3)];
    await h.start(tester);

    expect(h.live.pendingCount, 2);
    expect(h.live.introSeq, 0);
    await h.stop(tester);
  });

  testWidgets('a catch-up that returns after 4503 sets no pill', (
    tester,
  ) async {
    final h = _Harness();
    h.api
      ..peekGate = Completer<void>()
      ..peekDetails = [topicDetail(replyCount: 2)];
    await h.start(tester);

    h.channel.serverClose(liveCloseDisabled);
    await tester.pump();
    h.api.peekGate!.complete();
    await tester.pump();

    expect(h.live.status, LiveStatus.stopped);
    expect(h.live.pendingCount, 0);
    expect(h.live.introSeq, 0);
    expect(
      h.container.read(topicDetailProvider(10)).asData!.value.replyCount,
      1,
    );
    await tester.pump(const Duration(minutes: 2));
    expect(h.connector.connects, hasLength(1));
    await h.stop(tester);
  });

  testWidgets('4401: two peek reads (refresh, then the reconnect\'s catch-up) '
      'and one reconnect', (tester) async {
    final h = _Harness();
    await h.start(tester);
    final peeksBefore = h.api.peekCalls;

    h.channel.serverClose(liveCloseUnauthenticated);
    await tester.pump();

    expect(h.api.peekCalls, peeksBefore + 2);
    expect(h.connector.connects, hasLength(2));
    expect(h.live.status, LiveStatus.live);
    await h.stop(tester);
  });

  testWidgets('suspend closes, resume reconnects and catches up', (
    tester,
  ) async {
    final h = _Harness();
    await h.start(tester);

    h.notifier.suspend();
    await tester.pump();
    expect(h.channel.closedByClient, isTrue);
    expect(h.live.status, LiveStatus.off);

    h.api.peekDetails = [topicDetail(replyCount: 3)];
    await tester.pump(const Duration(minutes: 5));
    expect(h.connector.connects, hasLength(1));

    h.notifier.resume();
    await tester.pump();
    expect(h.connector.connects, hasLength(2));
    expect(h.live.status, LiveStatus.live);
    expect(h.live.pendingCount, 2);
    await h.stop(tester);
  });

  testWidgets('resume after 4503 makes one new attempt', (tester) async {
    final h = _Harness();
    await h.start(tester);
    h.channel.serverClose(liveCloseDisabled);
    await tester.pump();

    h.notifier.suspend();
    h.notifier.resume();
    await tester.pump();

    expect(h.connector.connects, hasLength(2));
    await h.stop(tester);
  });

  testWidgets('takePending walks every page and returns the first new id', (
    tester,
  ) async {
    final h = _Harness();
    h.api.postPages = [
      CursorPage(items: [post(id: 1), post(id: 2)], next: 'p2'),
      CursorPage(items: [post(id: 3)]),
    ];
    h.api.postsById
      ..[4] = post(id: 4)
      ..[5] = post(id: 5);
    await h.start(tester);
    h.channel
      ..serverEvent('post.created', postId: 4)
      ..serverEvent('post.created', postId: 5);
    await tester.pump();
    expect(h.live.pendingCount, 2);

    h.api.postPages = [
      CursorPage(items: [post(id: 1), post(id: 2)], next: 'p2'),
      CursorPage(items: [post(id: 3), post(id: 4), post(id: 5)]),
    ];
    final first = await h.notifier.takePending();

    expect(first, 4);
    expect(h.ids, [1, 2, 3, 4, 5]);
    expect(h.live.flashIds, {4, 5});
    expect(h.live.slideIds, isEmpty);
    expect(h.live.pendingCount, 0);

    h.notifier.clearFlash(4);
    expect(h.live.flashIds, {5});
    await h.stop(tester);
  });
}
