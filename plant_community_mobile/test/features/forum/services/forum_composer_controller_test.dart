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

    // todo 292 AC4: edit key rotation mirrors submitReply's rotation exactly
    // — same unit-test scope (asserting the CONTROLLER's own rotation
    // decision via the keys it sent), not a claim about server-side
    // rejection semantics, which are backend-tested separately.
    test(
      'submitEdit reuses one Idempotency-Key across retries of the same content',
      () async {
        final api = FakeForumApi();
        final controller = ForumComposerController(api: api);

        await controller.submitEdit(postId: 5, bodyText: 'same text');
        await controller.submitEdit(postId: 5, bodyText: 'same text');

        expect(api.editPostKeys, hasLength(2));
        expect(api.editPostKeys[0], api.editPostKeys[1]);
      },
    );

    test(
      'submitEdit rotates the key when the edited content changes',
      () async {
        final api = FakeForumApi();
        final controller = ForumComposerController(api: api);

        await controller.submitEdit(postId: 5, bodyText: 'first draft');
        await controller.submitEdit(postId: 5, bodyText: 'revised draft');

        expect(api.editPostKeys, hasLength(2));
        expect(api.editPostKeys[0], isNot(api.editPostKeys[1]));
      },
    );

    test('submitEdit surfaces the pending moderation status', () async {
      final api = FakeForumApi()..editStatus = ForumModerationStatus.pending;
      final controller = ForumComposerController(api: api);
      final result = await controller.submitEdit(
        postId: 5,
        bodyText: 'edited body',
      );
      expect(result.status.isPending, isTrue);
      expect(api.editPostKeys.single, controller.idempotencyKey);
    });

    // todo 294
    test(
      'uploadImage reuses one Idempotency-Key across retries of the same file',
      () async {
        final api = FakeForumApi();
        final controller = ForumComposerController(api: api);

        await controller.uploadImage(filePath: '/tmp/leaf.jpg');
        await controller.uploadImage(filePath: '/tmp/leaf.jpg');

        expect(api.uploadImageKeys, hasLength(2));
        expect(api.uploadImageKeys[0], api.uploadImageKeys[1]);
      },
    );

    test('uploadImage rotates the key when the file changes', () async {
      final api = FakeForumApi();
      final controller = ForumComposerController(api: api);

      await controller.uploadImage(filePath: '/tmp/leaf.jpg');
      await controller.uploadImage(filePath: '/tmp/stem.jpg');

      expect(api.uploadImageKeys, hasLength(2));
      expect(api.uploadImageKeys[0], isNot(api.uploadImageKeys[1]));
    });

    test('submitTopic appends the image block AFTER the paragraph, referencing '
        'the bare integer id (not the {id,url,...} object)', () async {
      final api = FakeForumApi();
      final controller = ForumComposerController(api: api);

      await controller.submitTopic(
        boardSlug: 'general',
        title: 'My topic',
        bodyText: 'a leaf',
        imageId: 42,
      );

      final body = api.createTopicBodies.single;
      expect(body, [
        {'type': 'paragraph', 'value': 'a leaf'},
        {'type': 'image', 'value': 42},
      ]);
    });

    test(
      'submitReply with empty text and an image sends an image-only body',
      () async {
        final api = FakeForumApi();
        final controller = ForumComposerController(api: api);

        await controller.submitReply(topicId: 10, bodyText: '', imageId: 7);

        expect(api.createReplyBodies.single, [
          {'type': 'image', 'value': 7},
        ]);
      },
    );

    test(
      'a submit failure after a successful upload keeps the same imageId '
      'and reuses the key on retry (code review — the real production '
      'sequence: uploadImage then submit then retry on one controller)',
      () async {
        final api = FakeForumApi()..failCreateReplyTimes = 1;
        final controller = ForumComposerController(api: api);

        final image = await controller.uploadImage(filePath: '/tmp/leaf.jpg');

        // First submit attempt fails (simulated 500) — the attachment must
        // not be lost; the caller retries with the exact same content.
        await expectLater(
          controller.submitReply(
            topicId: 10,
            bodyText: 'hi',
            imageId: image.id,
          ),
          throwsA(isA<ApiException>()),
        );
        final result = await controller.submitReply(
          topicId: 10,
          bodyText: 'hi',
          imageId: image.id,
        );

        expect(result.id, 2);
        expect(api.createReplyKeys, hasLength(2));
        // Identical retry content (same text, same imageId) reuses the key
        // so the backend replays instead of duplicating.
        expect(api.createReplyKeys[0], api.createReplyKeys[1]);
        expect(api.createReplyBodies[0], api.createReplyBodies[1]);
        expect(api.createReplyBodies[1], [
          {'type': 'paragraph', 'value': 'hi'},
          {'type': 'image', 'value': image.id},
        ]);
      },
    );
  });
}
