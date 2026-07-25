import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_composer_controller.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import '../support/forum_test_support.dart';

void main() {
  group('slugifyForumTitle', () {
    test('lowercases, hyphenates, trims', () {
      expect(slugifyForumTitle('  Hello, World!  '), 'hello-world');
    });
    test('falls back to "topic" for empty result', () {
      expect(slugifyForumTitle('!!!'), 'topic');
    });
  });

  group('ForumComposerController idempotency', () {
    test(
      'reuses one Idempotency-Key across retries of the same reply',
      () async {
        final api = FakeForumApi()..failCreateReplyTimes = 1;
        final controller = ForumComposerController(api: api);

        // First attempt fails (simulated 500).
        await expectLater(
          controller.submitReply(topicId: 10, bodyText: 'hi'),
          throwsA(isA<ApiException>()),
        );
        // Retry the same compose action succeeds.
        final result = await controller.submitReply(
          topicId: 10,
          bodyText: 'hi',
        );

        expect(result.id, 2);
        expect(api.createReplyKeys, hasLength(2));
        // The retry MUST reuse the original key so the backend replays instead
        // of creating a duplicate reply.
        expect(api.createReplyKeys[0], api.createReplyKeys[1]);
        expect(api.createReplyKeys.first, controller.idempotencyKey);
      },
    );

    test('a new controller uses a new key', () {
      final api = FakeForumApi();
      final a = ForumComposerController(api: api);
      final b = ForumComposerController(api: api);
      expect(a.idempotencyKey, isNotEmpty);
      expect(a.idempotencyKey, isNot(b.idempotencyKey));
    });

    test(
      'rotates the key when the content changes (avoids a wedged 422)',
      () async {
        final api = FakeForumApi();
        final controller = ForumComposerController(api: api);
        await controller.submitReply(topicId: 10, bodyText: 'first draft');
        // The user edits the draft and resubmits — a genuinely different payload
        // must not reuse the old key (which would 422 for 24h).
        await controller.submitReply(topicId: 10, bodyText: 'edited draft');
        expect(api.createReplyKeys, hasLength(2));
        expect(api.createReplyKeys[0], isNot(api.createReplyKeys[1]));
      },
    );

    test('topic create surfaces the pending moderation status', () async {
      final api = FakeForumApi()..topicStatus = ForumModerationStatus.pending;
      final controller = ForumComposerController(api: api);
      final result = await controller.submitTopic(
        boardSlug: 'general',
        title: 'My topic',
        bodyText: 'body',
      );
      expect(result.status.isPending, isTrue);
      expect(api.createTopicKeys.single, controller.idempotencyKey);
    });
  });
}
