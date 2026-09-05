import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_composer_screen.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_thread_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

void main() {
  testWidgets('forum home lists boards and sync-backed recent topics', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..boards = const [
        ForumBoard(
          id: 1,
          title: 'General',
          slug: 'general',
          description: 'Chat',
          topicCount: 2,
          postCount: 5,
        ),
      ]
      ..syncPages = [
        ForumSyncPage(
          topics: [stub(id: 1, title: 'Recent one')],
          deleted: const [],
          hasMore: false,
          nextSince: DateTime.utc(2026, 1, 1),
          nextSinceId: 1,
        ),
      ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false),
          ),
        ],
        child: const MaterialApp(home: ForumScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('General'), findsOneWidget);
    expect(find.text('Recent one'), findsOneWidget);
  });

  testWidgets('forum home shows the unread notification count on the bell', (
    tester,
  ) async {
    final api = FakeForumApi()..unreadCount = 3;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: true),
          ),
        ],
        child: const MaterialApp(home: ForumScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.notifications_outlined), findsOneWidget);
    expect(find.text('3'), findsOneWidget);
  });

  testWidgets(
    'forum home shows the unread conversation count on the inbox icon '
    '(todo 339)',
    (tester) async {
      final api = FakeForumApi()..unreadConversationCount = 2;

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: const MaterialApp(home: ForumScreen()),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.mail_outline), findsOneWidget);
      expect(find.byTooltip('Messages'), findsOneWidget);
      expect(find.text('2'), findsOneWidget);
    },
  );

  testWidgets(
    'forum home offers the Bookmarks entry to a signed-in member only '
    '(todo 341)',
    (tester) async {
      Widget wrap({required bool loggedIn}) => ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(FakeForumApi()),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: loggedIn),
          ),
        ],
        child: const MaterialApp(home: ForumScreen()),
      );

      await tester.pumpWidget(wrap(loggedIn: true));
      await tester.pumpAndSettle();
      expect(find.byTooltip('Bookmarks'), findsOneWidget);
      expect(find.byIcon(Icons.bookmark_border), findsOneWidget);

      // A fresh ProviderScope — re-pumping the same scope with different
      // overrides keeps the first container (and its signed-in fake).
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(wrap(loggedIn: false));
      await tester.pumpAndSettle();
      expect(find.byTooltip('Bookmarks'), findsNothing);
    },
  );

  testWidgets('forum home hides the inbox icon for an anonymous viewer', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(FakeForumApi()),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false),
          ),
        ],
        child: const MaterialApp(home: ForumScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.mail_outline), findsNothing);
  });

  testWidgets('thread screen renders posts with rendered bodies', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..topicDetail = topicDetail(title: 'Monstera help')
      ..posts = CursorPage(
        items: [
          post(id: 1, body: const [ParagraphBlock('Leaves turning yellow')]),
        ],
      );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false),
          ),
        ],
        child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Monstera help'), findsOneWidget);
    expect(find.textContaining('Leaves turning yellow'), findsOneWidget);
  });

  testWidgets('a pending post surfaces the awaiting-moderation marker', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..topicDetail = topicDetail()
      ..posts = CursorPage(items: [post(id: 2, isPending: true)]);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false),
          ),
        ],
        child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Awaiting moderation'), findsOneWidget);
  });

  testWidgets('subscribe toggle reflects isSubscribed and flips on tap', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..topicDetail = topicDetail(id: 10)
      ..posts = CursorPage(items: [post(id: 1)]);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: true),
          ),
        ],
        child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
      ),
    );
    await tester.pumpAndSettle();

    // Starts unsubscribed (the topicDetail() fixture default).
    expect(find.byIcon(Icons.notifications_none), findsOneWidget);
    expect(find.byIcon(Icons.notifications_active), findsNothing);

    await tester.tap(find.byIcon(Icons.notifications_none));
    await tester.pumpAndSettle();

    expect(api.subscribeCalls, [10]);
    expect(find.byIcon(Icons.notifications_active), findsOneWidget);
    expect(find.byIcon(Icons.notifications_none), findsNothing);
  });

  testWidgets('composer shows the notify-and-return moderation notice', (
    tester,
  ) async {
    final api = FakeForumApi()..replyStatus = ForumModerationStatus.pending;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: true),
          ),
        ],
        child: const MaterialApp(
          home: ForumComposerScreen(args: ForumComposeArgs.reply(topicId: 10)),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'my reply');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Post'));
    await tester.pumpAndSettle();

    expect(find.textContaining('awaiting moderation'), findsOneWidget);
    expect(api.createReplyKeys, hasLength(1));
  });

  testWidgets(
    'picking a photo uploads it and includes it as an image block on submit (todo 294 AC1)',
    (tester) async {
      final api = FakeForumApi()
        // Pending, not published: this screen is the ROOT route
        // (`MaterialApp(home: ...)`), so a published-path `Navigator.pop`
        // has nothing to pop back to. Staying on the pending view (like the
        // "notify-and-return" test above) avoids that, and still lets this
        // test assert the submitted body after the tap.
        ..replyStatus = ForumModerationStatus.pending
        ..uploadImageResult = const ForumImageBlock(
          id: 42,
          url: 'https://example.com/forum/images/42.jpg',
          alt: '',
          width: 800,
          height: 600,
        );
      final picker = FakeForumImagePicker(nextPath: '/tmp/leaf.jpg');

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: MaterialApp(
            home: ForumComposerScreen(
              args: ForumComposeArgs.reply(topicId: 10),
              imagePicker: picker,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(OutlinedButton, 'Add photo'));
      // Bounded pumps, not pumpAndSettle: the attached thumbnail renders via
      // CachedNetworkImage, whose placeholder spinner never resolves in the
      // test harness's blocked-network environment (every HTTP request
      // 400s) and would make pumpAndSettle hang.
      await tester.pump();
      await tester.pump();

      // The upload happened and the thumbnail replaced the "Add photo" button.
      expect(api.uploadImageFilePaths, ['/tmp/leaf.jpg']);
      expect(find.widgetWithText(OutlinedButton, 'Add photo'), findsNothing);

      await tester.enterText(find.byType(TextField), 'a leafy problem');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(api.createReplyBodies.single, [
        {'type': 'paragraph', 'value': 'a leafy problem'},
        {'type': 'image', 'value': 42},
      ]);
    },
  );

  testWidgets(
    'a rejected image upload surfaces an error and leaves the drafted text intact (todo 294 AC2)',
    (tester) async {
      final api = FakeForumApi()
        ..failUploadImageWith = ApiException(
          'Image failed validation.',
          statusCode: 422,
        );
      final picker = FakeForumImagePicker(nextPath: '/tmp/leaf.jpg');

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: MaterialApp(
            home: ForumComposerScreen(
              args: ForumComposeArgs.reply(topicId: 10),
              imagePicker: picker,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'my drafted reply');
      await tester.pump();

      await tester.tap(find.widgetWithText(OutlinedButton, 'Add photo'));
      await tester.pumpAndSettle();

      expect(find.text('Image failed validation.'), findsOneWidget);
      // The drafted text survives the failed upload untouched.
      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, 'my drafted reply');
      // "Add photo" is still offered — no image got attached.
      expect(find.widgetWithText(OutlinedButton, 'Add photo'), findsOneWidget);
    },
  );

  testWidgets(
    'a picker-level failure (e.g. a denied permission) surfaces an error '
    'the same way an upload rejection does (code review, todo 294)',
    (tester) async {
      final api = FakeForumApi();
      final picker = FakeForumImagePicker(
        throwOnPick: Exception('permission denied'),
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: MaterialApp(
            home: ForumComposerScreen(
              args: ForumComposeArgs.reply(topicId: 10),
              imagePicker: picker,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'my drafted reply');
      await tester.pump();

      // Must complete without throwing (a bare "throw" out of the picker
      // call used to escape unhandled — code review).
      await tester.tap(find.widgetWithText(OutlinedButton, 'Add photo'));
      await tester.pumpAndSettle();

      expect(find.text('Could not upload that photo.'), findsOneWidget);
      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, 'my drafted reply');
      expect(api.uploadImageKeys, isEmpty); // never reached the API call
    },
  );

  testWidgets(
    'Post is disabled while an image upload is in flight (code review, '
    'todo 294 — prevents silently dropping the attachment)',
    (tester) async {
      final gate = Completer<ForumImageBlock>();
      final api = FakeForumApi()..uploadImageGate = gate;
      final picker = FakeForumImagePicker(nextPath: '/tmp/leaf.jpg');

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: MaterialApp(
            home: ForumComposerScreen(
              args: ForumComposeArgs.reply(topicId: 10),
              imagePicker: picker,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'a leafy problem');
      await tester.pump();
      await tester.tap(find.widgetWithText(OutlinedButton, 'Add photo'));
      await tester.pump(); // upload starts, still gated — _uploadingImage=true

      var postButton = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Post'),
      );
      expect(postButton.onPressed, isNull);

      gate.complete(
        const ForumImageBlock(id: 9, url: 'https://x/i.jpg', alt: ''),
      );
      await tester.pump();
      await tester.pump();

      postButton = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Post'),
      );
      expect(postButton.onPressed, isNotNull);
    },
  );

  testWidgets(
    'edit composer shows the notify-and-return moderation notice (todo 292 AC2)',
    (tester) async {
      final api = FakeForumApi()..editStatus = ForumModerationStatus.pending;

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: MaterialApp(
            home: ForumComposerScreen(
              args: ForumComposeArgs.edit(
                post: post(id: 7, body: const [ParagraphBlock('original')]),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // The field pre-fills from the existing single-paragraph body.
      expect(find.text('original'), findsOneWidget);

      await tester.enterText(find.byType(TextField), 'edited text');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Save'));
      await tester.pumpAndSettle();

      expect(find.textContaining('awaiting moderation'), findsOneWidget);
      expect(api.editPostKeys, hasLength(1));
    },
  );

  testWidgets(
    'edit composer surfaces a 409 frozen-topic message verbatim, not the generic retry copy (todo 292 AC3)',
    (tester) async {
      final api = FakeForumApi()
        ..failEditPostWith = ApiException(
          'Topic is closed or locked.',
          statusCode: 409,
        );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: MaterialApp(
            home: ForumComposerScreen(
              args: ForumComposeArgs.edit(
                post: post(id: 7, body: const [ParagraphBlock('original')]),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'edited text');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Save'));
      await tester.pumpAndSettle();

      expect(find.text('Topic is closed or locked.'), findsOneWidget);
      expect(find.textContaining('tap Post again to retry'), findsNothing);
    },
  );

  testWidgets(
    'edit composer warns when the body has non-text content it cannot round-trip (todo 292)',
    (tester) async {
      final api = FakeForumApi();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: MaterialApp(
            home: ForumComposerScreen(
              args: ForumComposeArgs.edit(
                post: post(
                  id: 7,
                  body: const [
                    ForumImageBlock(id: 1, url: 'https://x/i.png', alt: ''),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining("can't show here yet"), findsOneWidget);
      // Nothing to pre-fill from an image-only body — the field starts empty.
      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, isEmpty);
    },
  );

  testWidgets('thread screen deletes a post after confirmation (todo 292)', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..topicDetail = topicDetail()
      ..posts = CursorPage(items: [post(id: 1, canDelete: true)]);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          forumApiProvider.overrideWithValue(api),
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: true),
          ),
        ],
        child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byIcon(Icons.more_vert));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Delete'));
    await tester.pumpAndSettle();

    expect(find.text('Delete post?'), findsOneWidget);
    // Two "Delete" texts now: the dialog's confirm button and the (still
    // visible underneath) menu item — target the dialog's action button.
    await tester.tap(
      find.descendant(
        of: find.byType(AlertDialog),
        matching: find.text('Delete'),
      ),
    );
    await tester.pumpAndSettle();

    expect(api.deletePostCalls, [1]);
    expect(find.text('No posts yet.'), findsOneWidget);
  });

  testWidgets(
    'thread screen keeps the post when delete is cancelled (todo 292)',
    (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail()
        ..posts = CursorPage(items: [post(id: 1, canDelete: true)]);

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(api.deletePostCalls, isEmpty);
      expect(find.text('No posts yet.'), findsNothing);
    },
  );

  testWidgets(
    'thread screen surfaces a 409 delete rejection as a clear message (todo 292 AC3)',
    (tester) async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail()
        ..posts = CursorPage(items: [post(id: 1, canDelete: true)])
        ..failDeletePostWith = ApiException(
          'Topic is closed or locked.',
          statusCode: 409,
        );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            forumApiProvider.overrideWithValue(api),
            authServiceProvider.overrideWith(
              () => FakeAuthService(loggedIn: true),
            ),
          ],
          child: const MaterialApp(home: ForumThreadScreen(topicId: 10)),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Delete'),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Topic is closed or locked.'), findsOneWidget);
      // The post is still there — the delete never actually applied.
      expect(find.text('No posts yet.'), findsNothing);
    },
  );
}
