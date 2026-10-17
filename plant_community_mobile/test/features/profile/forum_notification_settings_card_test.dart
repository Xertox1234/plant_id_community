import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
  Future<String?> Function()? deviceTimeZone,
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
          deviceTimeZone: deviceTimeZone ?? () async => null,
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
    // Dio's own text for a failure with no HTTP status (todo 651 round 2).
    expect(apiErrorMessage(ApiException('Connection reset by peer')), isNull);
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

  group('important-event email and quiet hours (todo 624)', () {
    // What a todo-624 backend sends: email for every event, off by default
    // except replies, and quiet hours off at 22:00-07:00 with no zone yet.
    const full = ForumNotificationSettings(
      digestFrequency: 'off',
      preferences: {
        'reply': {'push': true, 'email': true},
        'mention': {'push': true, 'email': false},
        'quote': {'push': true, 'email': false},
        'solution': {'push': true, 'email': false},
      },
      quietHours: QuietHours(
        enabled: false,
        start: '22:00',
        end: '07:00',
        timeZone: '',
      ),
    );

    test('fromJson reads quiet hours and drops a malformed window', () {
      final quiet = ForumNotificationSettings.fromJson({
        'quiet_hours_enabled': true,
        'quiet_hours_start': '21:30',
        'quiet_hours_end': '06:45',
        'time_zone': 'America/Denver',
      }).quietHours!;
      expect(
        [quiet.enabled, quiet.start, quiet.end, quiet.shownZone],
        [true, '21:30', '06:45', 'America/Denver'],
      );
      expect(
        ForumNotificationSettings.fromJson({
          'quiet_hours_enabled': true,
          'quiet_hours_start': '9pm',
          'quiet_hours_end': '07:00',
        }).quietHours,
        isNull,
      );
      // A backend from before todo 624: nothing to offer.
      expect(ForumNotificationSettings.fromJson({}).quietHours, isNull);
      // Shaped like HH:MM but out of range: dropped, never parsed into an
      // invalid TimeOfDay for the picker (review round 1, PR #1132).
      for (final bad in ['99:99', '24:00', '23:60']) {
        expect(
          ForumNotificationSettings.fromJson({
            'quiet_hours_enabled': true,
            'quiet_hours_start': bad,
            'quiet_hours_end': '07:00',
          }).quietHours,
          isNull,
          reason: bad,
        );
      }
    });

    test('only an IANA name is reportable', () {
      for (final zone in [
        'America/Denver',
        'America/Argentina/Buenos_Aires',
        'Etc/GMT+7',
        'UTC',
      ]) {
        expect(isReportableTimeZone(zone), isTrue, reason: zone);
      }
      for (final zone in ['MDT', 'GMT+02:00', '', 'A/${'b' * 70}']) {
        expect(isReportableTimeZone(zone), isFalse, reason: zone);
      }
    });

    group('the default zone lookup', () {
      const channel = MethodChannel('flutter_timezone');
      TestDefaultBinaryMessenger messenger() =>
          TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
      tearDown(() => messenger().setMockMethodCallHandler(channel, null));

      testWidgets("sends the platform's IANA zone with a quiet-hours save", (
        tester,
      ) async {
        // The platform side of flutter_timezone, as iOS and Android answer.
        messenger().setMockMethodCallHandler(channel, (call) async {
          expect(call.method, 'getLocalTimezone');
          return 'America/Denver';
        });
        final api = FakeForumApi()..notificationSettings = full;
        await tester.pumpWidget(
          ProviderScope(
            overrides: [forumApiProvider.overrideWithValue(api)],
            child: MaterialApp(
              home: Scaffold(
                body: SingleChildScrollView(
                  // No deviceTimeZone: the real reportableTimeZone runs.
                  child: ForumNotificationSettingsCard(
                    emailOn: true,
                    forumOn: true,
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        await tester.scrollUntilVisible(find.text('Until'), 200);

        await tester.tap(find.text('Quiet hours'));
        await tester.pumpAndSettle();

        expect(api.notificationSettingsUpdates.last, {
          'quiet_hours_enabled': true,
          'time_zone': 'America/Denver',
        });
      });

      testWidgets('reports nothing for an abbreviation or a platform error', (
        tester,
      ) async {
        messenger().setMockMethodCallHandler(channel, (call) async => 'MDT');
        expect(await reportableTimeZone(), isNull);
        messenger().setMockMethodCallHandler(
          channel,
          (call) async => throw PlatformException(code: 'boom'),
        );
        expect(await reportableTimeZone(), isNull);
      });
    });

    testWidgets('offers the new email cells, off, and saves one', (
      tester,
    ) async {
      final api = FakeForumApi()..notificationSettings = full;
      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      for (final title in [
        'Mentions: Email',
        'Quotes of your posts: Email',
        'Answer accepted: Email',
      ]) {
        expect(_switch(tester, title).value, isFalse, reason: title);
      }
      expect(find.textContaining('sends one email'), findsOneWidget);

      await tester.tap(find.text('Mentions: Email'));
      await tester.pumpAndSettle();
      expect(api.notificationSettingsUpdates, [
        {
          'notification_preferences': {
            'mention': {'email': true},
          },
        },
      ]);
      expect(_switch(tester, 'Mentions: Email').value, isTrue);
    });

    testWidgets('quiet hours show off, in UTC, with the times disabled', (
      tester,
    ) async {
      final api = FakeForumApi()..notificationSettings = full;
      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('Until'), 200);

      expect(_switch(tester, 'Quiet hours').value, isFalse);
      expect(find.textContaining('Times are in UTC.'), findsOneWidget);
      expect(
        find.textContaining('security email always sends'),
        findsOneWidget,
      );
      final from = tester.widget<ListTile>(
        find.widgetWithText(ListTile, 'From'),
      );
      expect(from.enabled, isFalse);
      expect(find.text('22:00'), findsOneWidget);
      expect(find.text('07:00'), findsOneWidget);
    });

    testWidgets('turning them on reports an IANA zone, never an abbreviation', (
      tester,
    ) async {
      final api = FakeForumApi()..notificationSettings = full;
      await tester.pumpWidget(
        _wrap(api, deviceTimeZone: () async => 'America/Denver'),
      );
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('Until'), 200);

      await tester.tap(find.text('Quiet hours'));
      await tester.pumpAndSettle();

      expect(api.notificationSettingsUpdates.last, {
        'quiet_hours_enabled': true,
        'time_zone': 'America/Denver',
      });
      expect(_switch(tester, 'Quiet hours').value, isTrue);
      expect(
        find.textContaining('Times are in America/Denver.'),
        findsOneWidget,
      );
      expect(
        tester.widget<ListTile>(find.widgetWithText(ListTile, 'From')).enabled,
        isTrue,
      );

      // A device that only knows "MDT" reports no zone at all; the server
      // keeps the one it has.
      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('Until'), 200);
      await tester.tap(find.text('Quiet hours'));
      await tester.pumpAndSettle();
      expect(api.notificationSettingsUpdates.last, {
        'quiet_hours_enabled': false,
      });
    });

    testWidgets('picking a time saves only that end of the window', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..notificationSettings = full.withQuietHours(
          full.quietHours!.copyWith(enabled: true),
        );
      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('Until'), 200);

      await tester.tap(find.text('Until'));
      await tester.pumpAndSettle();
      // The picker opens on 07:00; accept it as 07:00 would be a no-op, so
      // switch it to 08:00 through the input mode.
      await tester.tap(find.byIcon(Icons.keyboard_outlined));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextFormField).first, '08');
      await tester.tap(find.text('OK'));
      await tester.pumpAndSettle();

      expect(api.notificationSettingsUpdates.last, {
        'quiet_hours_end': '08:00',
      });
      expect(find.text('08:00'), findsOneWidget);
    });

    testWidgets('a failed quiet-hours save reverts and says so', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..notificationSettings = full
        ..failNotificationSettingsUpdateWith = ApiException('boom');
      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('Until'), 200);

      await tester.tap(find.text('Quiet hours'));
      await tester.pumpAndSettle();

      expect(_switch(tester, 'Quiet hours').value, isFalse);
      expect(
        find.textContaining('Failed to save notification settings'),
        findsOneWidget,
      );
    });
  });
}
