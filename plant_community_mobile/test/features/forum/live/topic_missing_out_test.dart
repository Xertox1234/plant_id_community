// TopicMissingOut: the signed-out reader's 30 s check that offers "New
// replies are coming in. Sign in or sign up to follow along live." (live
// forum replies, slice 4). testWidgets fakes the timer.
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/live/live_updates_settings.dart';
import 'package:plant_community_mobile/features/forum/live/topic_missing_out.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

class _Harness {
  _Harness({this.loggedIn = false});

  final bool loggedIn;
  final api = FakeForumApi()..topicDetail = topicDetail(replyCount: 1);
  late final ProviderContainer container;

  int get seq => container.read(topicMissingOutProvider(10));
  TopicMissingOut get notifier =>
      container.read(topicMissingOutProvider(10).notifier);

  Future<void> start(WidgetTester tester) async {
    container = ProviderContainer(
      overrides: [
        forumApiProvider.overrideWithValue(api),
        authServiceProvider.overrideWith(
          () => FakeAuthService(loggedIn: loggedIn),
        ),
      ],
    );
    container.listen(topicMissingOutProvider(10), (_, _) {});
    await tester.pump();
  }

  Future<void> stop(WidgetTester tester) async {
    container.dispose();
    await tester.pump();
  }
}

void main() {
  late Map<String, String> store;

  setUp(() {
    store = {};
    FlutterSecureStorage.setMockInitialValues(store);
  });

  testWidgets('no polling while signed in', (tester) async {
    final h = _Harness(loggedIn: true);
    await h.start(tester);

    await tester.pump(const Duration(minutes: 2));

    expect(h.api.peekCalls, 0);
    expect(h.seq, 0);
    await h.stop(tester);
  });

  testWidgets('the first read sets the baseline without a toast', (
    tester,
  ) async {
    final h = _Harness();
    h.api.peekDetails = [topicDetail(replyCount: 5)];
    await h.start(tester);

    await tester.pump(missingOutPollInterval);

    expect(h.api.peekCalls, 1);
    expect(h.seq, 0);
    await h.stop(tester);
  });

  testWidgets('a higher count makes the toast due once, then stops polling', (
    tester,
  ) async {
    final h = _Harness();
    h.api.peekDetails = [
      topicDetail(replyCount: 1),
      topicDetail(replyCount: 2),
    ];
    await h.start(tester);

    await tester.pump(missingOutPollInterval);
    await tester.pump(missingOutPollInterval);

    expect(h.seq, 1);
    expect(store[missingOutKey], isNotNull);
    await tester.pump(const Duration(minutes: 2));
    expect(h.api.peekCalls, 2);
    expect(h.seq, 1);
    await h.stop(tester);
  });

  testWidgets('not due when mayShowMissingOut is false', (tester) async {
    store[missingOutKey] = DateTime.now().millisecondsSinceEpoch.toString();
    final h = _Harness();
    h.api.peekDetails = [
      topicDetail(replyCount: 1),
      topicDetail(replyCount: 2),
    ];
    await h.start(tester);

    await tester.pump(const Duration(minutes: 2));

    expect(h.seq, 0);
    expect(h.api.peekCalls, 0);
    await h.stop(tester);
  });

  testWidgets('suspend stops polling, and resume restarts it', (tester) async {
    final h = _Harness();
    await h.start(tester);
    await tester.pump(missingOutPollInterval);
    expect(h.api.peekCalls, 1);

    h.notifier.suspend();
    await tester.pump(const Duration(minutes: 2));
    expect(h.api.peekCalls, 1);

    h.api.peekDetails = [topicDetail(replyCount: 4)];
    h.notifier.resume();
    await tester.pump();
    await tester.pump(missingOutPollInterval);

    expect(h.api.peekCalls, 2);
    expect(h.seq, 1);
    await h.stop(tester);
  });

  testWidgets('a failed read is silent and the next tick retries', (
    tester,
  ) async {
    final h = _Harness();
    h.api.topicDetail = null; // the peek throws
    await h.start(tester);

    await tester.pump(missingOutPollInterval);
    expect(h.api.peekCalls, 1);
    expect(tester.takeException(), isNull);

    h.api.topicDetail = topicDetail(replyCount: 1);
    await tester.pump(missingOutPollInterval);
    h.api.topicDetail = topicDetail(replyCount: 3);
    await tester.pump(missingOutPollInterval);

    expect(h.api.peekCalls, 3);
    expect(h.seq, 1);
    await h.stop(tester);
  });
}
