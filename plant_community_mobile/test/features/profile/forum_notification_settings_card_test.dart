import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/profile/forum_notification_settings_card.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import '../forum/support/forum_test_support.dart';

Widget _wrap(FakeForumApi api, {bool emailOn = true, bool forumOn = true}) =>
    ProviderScope(
      overrides: [forumApiProvider.overrideWithValue(api)],
      child: MaterialApp(
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
}
