// Audit F89: the member's own forum feeds (notifications, the DM inbox, a DM
// thread, bookmarks) are keyed on who reads them, like the thread screen
// (forum_thread_viewer_test.dart). A screen kept offstage by the forum
// branch survives a passive session expiry into another account, so a new
// viewer whose refetch fails must see the error, never the last member's
// rows.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_bookmarks_screen.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_conversation_screen.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_conversations_screen.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_notifications_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_unlock_store.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

import '../support/forum_test_support.dart';

final _failure = ApiException('nope', statusCode: 500);

/// One member feed screen: how to seed ada's rows, the text that shows them,
/// how to make the next viewer's fetch fail, and the screen's error copy.
class _Feed {
  const _Feed(
    this.name,
    this.screen,
    this.seed,
    this.fail,
    this.secret,
    this.error,
  );

  final String name;
  final Widget screen;
  final void Function(FakeForumApi api) seed;
  final void Function(FakeForumApi api) fail;
  final String secret;
  final String error;
}

final _feeds = <_Feed>[
  _Feed(
    'notifications',
    const ForumNotificationsScreen(),
    (api) => api.notifications = [
      notification(id: 1, topicTitle: "Ada's private topic"),
    ],
    (api) => api.failNotificationsWith = _failure,
    "Ada's private topic",
    'Could not load notifications.',
  ),
  _Feed(
    'the DM inbox',
    const ForumConversationsScreen(),
    (api) => api.conversations = [
      conversation(id: 1, otherUsername: 'zed', lastMessageBody: 'Ada secret'),
    ],
    (api) => api.failConversationsWith = _failure,
    'Ada secret',
    'Could not load your messages.',
  ),
  _Feed(
    'a DM thread',
    const ForumConversationScreen(username: 'zed'),
    (api) => api
      ..conversationWith = conversation(id: 1, otherUsername: 'zed')
      ..messages = [
        directMessage(id: 1, senderUsername: 'zed', body: 'Ada secret'),
      ],
    (api) => api.failConversationsWith = _failure,
    'Ada secret',
    'Could not load this conversation.',
  ),
  _Feed(
    'a group DM thread',
    const ForumConversationScreen(conversationId: 12),
    (api) => api
      ..conversationDetail = groupConversation(id: 12, title: 'Ada group')
      ..messages = [
        directMessage(
          id: 1,
          conversationId: 12,
          senderUsername: 'zed',
          body: 'Ada secret',
        ),
      ],
    (api) => api.failConversationsWith = _failure,
    'Ada secret',
    'Could not load this conversation.',
  ),
  _Feed(
    'bookmarks',
    const ForumBookmarksScreen(),
    (api) => api.bookmarks = [topic(id: 1, title: "Ada's bookmark")],
    (api) => api.failBookmarksWith = _failure,
    "Ada's bookmark",
    'Could not load your bookmarks.',
  ),
];

/// Every member-feed request the fake has seen.
int _requests(FakeForumApi api) =>
    api.fetchNotificationsCalls.length +
    api.fetchConversationsCalls.length +
    api.fetchConversationWithCalls.length +
    api.fetchConversationCalls.length +
    api.fetchMessagesCalls.length +
    api.fetchBookmarksCalls.length;

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  for (final feed in _feeds) {
    for (final (name, next) in [
      ('another member', signedInAs('bob')),
      ('a sign-out', const AuthState()),
    ]) {
      testWidgets('${feed.name}: $name whose refetch fails shows the error, '
          "not the last member's rows", (tester) async {
        final api = FakeForumApi();
        feed.seed(api);
        final container = ProviderContainer(
          retry: (_, _) => null,
          overrides: [
            forumApiProvider.overrideWithValue(api),
            forumUnlockStoreProvider.overrideWithValue(FakeForumUnlockStore()),
            apiServiceProvider.overrideWithValue(
              ApiService(
                baseUrl: 'http://localhost:8000/api/v1',
                authToken: 'a',
              ),
            ),
            authServiceProvider.overrideWith(
              () =>
                  FakeAuthService(loggedIn: false, initial: signedInAs('ada')),
            ),
            userProfileServiceProvider.overrideWith(
              () => FakeUserProfileService(username: 'ada'),
            ),
          ],
        );
        addTearDown(container.dispose);
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(home: feed.screen),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.textContaining(feed.secret), findsWidgets);

        feed.fail(api);
        final requestsBefore = _requests(api);
        (container.read(authServiceProvider.notifier) as FakeAuthService)
            .setAuth(next);
        await tester.pumpAndSettle();

        expect(find.textContaining(feed.secret), findsNothing);
        expect(find.text(feed.error), findsOneWidget);
        if (next.firebaseUser == null) {
          // Signed out, the feed fails without a request: an anonymous one
          // would only 401 into a refresh and a second sign-out.
          expect(_requests(api), requestsBefore);
        }

        await tester.pumpWidget(const SizedBox());
        await tester.pump();
      });
    }
  }
}
