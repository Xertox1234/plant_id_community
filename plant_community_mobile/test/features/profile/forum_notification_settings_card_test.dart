import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/profile/forum_notification_settings_card.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

import '../forum/support/forum_test_support.dart';

Widget _wrap(
  FakeForumApi api, {
  bool emailOn = true,
  bool forumOn = true,
  ThemeData? theme,
}) => ProviderScope(
  overrides: [forumApiProvider.overrideWithValue(api)],
  child: MaterialApp(
    theme: theme,
    home: Scaffold(
      body: SingleChildScrollView(
        child: ForumNotificationSettingsCard(
          // A new key per pump is a fresh State: a "reload".
          key: UniqueKey(),
          emailOn: emailOn,
          forumOn: forumOn,
        ),
      ),
    ),
  ),
);

/// Its load fails with a non-API error whose text carries a URL.
class _DumpingForumApi extends FakeForumApi {
  @override
  Future<ForumNotificationSettings> fetchNotificationSettings() async {
    throw Exception('DioException GET https://api.example/secret');
  }
}

SwitchListTile _switch(WidgetTester tester, String title) =>
    tester.widget<SwitchListTile>(find.widgetWithText(SwitchListTile, title));

const _replyEmail = 'Replies to topics you follow: Email';
const _mentionPush = 'Mentions: Push';
const _digest = 'Weekly forum digest';

void main() {
  test('fromJson keeps only real cells and tolerates junk', () {
    final settings = ForumNotificationSettings.fromJson({
      'digest_frequency': 'weekly',
      'notification_preferences': {
        'reply': {'push': true, 'email': false, 'sms': 'yes'},
        'mention': 'nope',
        'quote': {'push': false},
      },
    });
    expect(settings.digestOn, isTrue);
    expect(settings.cell('reply', 'email'), isFalse);
    expect(settings.cell('reply', 'sms'), isNull);
    expect(settings.cell('mention', 'push'), isNull);
    expect(settings.cell('quote', 'push'), isFalse);
    expect(ForumNotificationSettings.fromJson({}).digestOn, isFalse);
  });

  testWidgets('shows the stored digest and matrix, email only where wired', (
    tester,
  ) async {
    final api = FakeForumApi();
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(_switch(tester, _digest).value, isFalse);
    expect(_switch(tester, _replyEmail).value, isTrue);
    expect(_switch(tester, _mentionPush).value, isTrue);
    // Email exists for replies alone: no mention email switch is offered.
    expect(find.text('Mentions: Email'), findsNothing);
    expect(api.fetchNotificationSettingsCalls, 1);
  });

  testWidgets('a toggle PATCHes only that cell and survives a reload', (
    tester,
  ) async {
    final api = FakeForumApi();
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text(_mentionPush));
    await tester.pumpAndSettle();

    expect(api.notificationSettingsUpdates, [
      {
        'notification_preferences': {
          'mention': {'push': false},
        },
      },
    ]);
    expect(_switch(tester, _mentionPush).value, isFalse);

    await tester.pumpWidget(_wrap(api)); // reload: a fresh fetch
    await tester.pumpAndSettle();
    expect(api.fetchNotificationSettingsCalls, 2);
    expect(_switch(tester, _mentionPush).value, isFalse);
    expect(_switch(tester, _replyEmail).value, isTrue); // untouched
  });

  testWidgets('the digest switch saves weekly and off', (tester) async {
    final api = FakeForumApi();
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text(_digest));
    await tester.pumpAndSettle();
    expect(api.notificationSettingsUpdates.last, {
      'digest_frequency': 'weekly',
    });
    expect(_switch(tester, _digest).value, isTrue);

    await tester.tap(find.text(_digest));
    await tester.pumpAndSettle();
    expect(api.notificationSettingsUpdates.last, {'digest_frequency': 'off'});
    expect(api.notificationSettings.digestOn, isFalse);
  });

  testWidgets('web turned reply email off; mobile shows it and turns it on', (
    tester,
  ) async {
    // The server state web Settings left behind.
    final api = FakeForumApi()
      ..notificationSettings = FakeForumApi().notificationSettings.withCell(
        'reply',
        'email',
        false,
      );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();
    expect(_switch(tester, _replyEmail).value, isFalse);

    await tester.tap(find.text(_replyEmail));
    await tester.pumpAndSettle();

    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();
    expect(_switch(tester, _replyEmail).value, isTrue);
    expect(api.notificationSettings.cell('reply', 'email'), isTrue);
  });

  testWidgets('a failed save reverts the switch and says so', (tester) async {
    final api = FakeForumApi()
      ..failNotificationSettingsUpdateWith = ApiException('boom');
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text(_replyEmail));
    await tester.pumpAndSettle();

    expect(_switch(tester, _replyEmail).value, isTrue); // the saved value
    expect(
      find.textContaining('Failed to save notification settings'),
      findsOneWidget,
    );
    expect(api.notificationSettings.cell('reply', 'email'), isTrue);
  });

  testWidgets('a failed load offers Retry, which loads', (tester) async {
    final api = FakeForumApi()
      ..failNotificationSettingsWith = ApiException('offline');
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.text('Could not load notification settings'), findsOneWidget);
    expect(find.byType(SwitchListTile), findsNothing);

    api.failNotificationSettingsWith = null;
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();

    expect(find.text(_digest), findsOneWidget);
  });

  testWidgets('says when a master switch holds these choices back', (
    tester,
  ) async {
    final api = FakeForumApi();
    await tester.pumpWidget(_wrap(api, emailOn: false));
    await tester.pumpAndSettle();
    expect(find.textContaining('Email notifications are off'), findsOneWidget);

    await tester.pumpWidget(_wrap(api, forumOn: false));
    await tester.pumpAndSettle();
    expect(find.textContaining('Forum notifications are off'), findsOneWidget);
    // The choices stay visible and editable as stored.
    expect(_switch(tester, _replyEmail).value, isTrue);
  });

  test(
    'a missing or unknown digest cadence is unknown, not off (todo 651)',
    () {
      for (final json in <Map<String, dynamic>>[
        {},
        {'digest_frequency': null},
        {'digest_frequency': 7},
        {'digest_frequency': 'daily'},
      ]) {
        final settings = ForumNotificationSettings.fromJson(json);
        expect(settings.hasDigest, isFalse, reason: '$json');
        expect(settings.digestFrequency, isNull, reason: '$json');
      }
      expect(
        ForumNotificationSettings.fromJson({
          'digest_frequency': 'off',
        }).digestFrequency,
        'off',
      );
    },
  );

  testWidgets('an unknown digest is not offered, so no tap writes weekly', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..notificationSettings = ForumNotificationSettings.fromJson({
        'notification_preferences': {
          'reply': {'push': true, 'email': true},
        },
      });
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.text(_digest), findsNothing);
    expect(_switch(tester, _replyEmail).value, isTrue); // the rest still shows

    // A cell save never sends a guessed digest (todo 651 review).
    await tester.tap(find.text(_replyEmail));
    await tester.pumpAndSettle();
    expect(api.notificationSettingsUpdates, hasLength(1));
    expect(
      api.notificationSettingsUpdates.single.containsKey('digest_frequency'),
      isFalse,
    );
  });

  test('only a message our views wrote reaches the user (todo 651 review)', () {
    expect(
      apiErrorMessage(ApiException('Bad value.', statusCode: 400)),
      'Bad value.',
    );
    expect(
      apiErrorMessage(
        ApiException(
          '<html>Gateway</html>',
          statusCode: 403,
          unstructured: true,
        ),
      ),
      isNull,
    );
    expect(
      apiErrorMessage(
        UserProfileException(
          'Failed to update profile: Bad value.',
          statusCode: 400,
          apiMessage: 'Bad value.',
        ),
      ),
      'Bad value.',
    );
    expect(
      apiErrorMessage(UserProfileException('Failed to update profile: boom')),
      isNull,
    );
    expect(
      notificationErrorText(
        UserProfileException('x', statusCode: 400, apiMessage: 'Bad value.'),
        action: 'Failed to update preferences',
      ),
      'Failed to update preferences: Bad value.',
    );
  });

  testWidgets('a 429 save rolls back and says try again later (todo 651)', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..failNotificationSettingsUpdateWith = ApiException(
        'Too many requests. Please wait a moment and try again.',
        statusCode: 429,
      );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text(_replyEmail));
    await tester.pumpAndSettle();

    expect(_switch(tester, _replyEmail).value, isTrue);
    expect(find.text(notificationThrottledText), findsOneWidget);
  });

  testWidgets('errors show the API message, never the exception dump', (
    tester,
  ) async {
    final api = FakeForumApi()
      ..failNotificationSettingsUpdateWith = ApiException(
        'Server unavailable',
        statusCode: 503,
      );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();
    await tester.tap(find.text(_replyEmail));
    await tester.pumpAndSettle();
    expect(
      find.text('Failed to save notification settings: Server unavailable'),
      findsOneWidget,
    );
    expect(find.textContaining('ApiException'), findsNothing);

    // A non-API error (e.g. a DioException that escaped) shows no detail.
    await tester.pumpWidget(_wrap(_DumpingForumApi()));
    await tester.pumpAndSettle();
    expect(find.text('Could not load notification settings'), findsOneWidget);
    expect(find.text('Something went wrong.'), findsOneWidget);
    expect(find.textContaining('example/secret'), findsNothing);
  });

  testWidgets('the master-switch note reads in dark mode (todo 651)', (
    tester,
  ) async {
    final dark = ThemeData(brightness: Brightness.dark);
    await tester.pumpWidget(_wrap(FakeForumApi(), emailOn: false, theme: dark));
    await tester.pumpAndSettle();

    final note = tester.widget<Text>(
      find.textContaining('Email notifications are off'),
    );
    expect(note.style?.color, dark.colorScheme.onSurfaceVariant);
    expect(
      dark.colorScheme.onSurfaceVariant.computeLuminance(),
      greaterThan(0.4), // light ink on the dark surface
    );
  });
}
