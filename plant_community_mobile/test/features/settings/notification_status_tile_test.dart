// The settings screen's push status (todo 621): accurate words for each
// permission/registration state, and the one action that fixes it.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/settings/notification_status_tile.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/push_registration_service.dart';

class _Service extends PushRegistrationService {
  _Service()
    : super(
        ApiService(baseUrl: 'http://fake.local'),
        installationId: () async => 'install-1',
        platform: 'ios',
      );

  int permissionRequests = 0;
  final List<bool> reconciles = [];

  @override
  Future<void> requestPermission() async => permissionRequests++;

  @override
  Future<void> reconcile({bool force = false}) async => reconciles.add(force);
}

Future<(_Service, List<String>)> _pump(
  WidgetTester tester,
  PushStatus status,
) async {
  final service = _Service()..status.value = status;
  final settingsOpened = <String>[];
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        pushRegistrationServiceProvider.overrideWithValue(service),
        openAppSettingsProvider.overrideWithValue(
          () async => settingsOpened.add('opened'),
        ),
      ],
      child: const MaterialApp(home: Scaffold(body: NotificationStatusTile())),
    ),
  );
  return (service, settingsOpened);
}

void main() {
  group('notificationStatusCopy', () {
    test('every state has words, and only fixable states an action', () {
      for (final permission in PushPermission.values) {
        for (final registration in PushRegistration.values) {
          final copy = notificationStatusCopy(
            PushStatus(permission: permission, registration: registration),
          );
          expect(copy.title, isNotEmpty);
          expect(copy.subtitle, isNotEmpty);
        }
      }
      expect(
        notificationStatusCopy(
          const PushStatus(
            permission: PushPermission.granted,
            registration: PushRegistration.registered,
          ),
        ).action,
        isNull,
      );
    });

    test('a denied permission wins over a working registration: nothing '
        'will be shown, so it never says "on"', () {
      final copy = notificationStatusCopy(
        const PushStatus(
          permission: PushPermission.denied,
          registration: PushRegistration.registered,
        ),
      );
      expect(copy.title, 'Notifications are off');
      expect(copy.action, NotificationStatusAction.openSettings);
    });

    test('signed out says so, whatever the permission', () {
      final copy = notificationStatusCopy(
        const PushStatus(permission: PushPermission.denied),
      );
      expect(copy.subtitle, contains('Sign in'));
      expect(copy.action, isNull);
    });
  });

  testWidgets('registered and allowed: on, no action', (tester) async {
    await _pump(
      tester,
      const PushStatus(
        permission: PushPermission.granted,
        registration: PushRegistration.registered,
      ),
    );

    expect(find.text('Notifications are on'), findsOneWidget);
    expect(find.byType(TextButton), findsNothing);
  });

  testWidgets('denied: off, and Settings opens the OS settings', (
    tester,
  ) async {
    final (_, opened) = await _pump(
      tester,
      const PushStatus(
        permission: PushPermission.denied,
        registration: PushRegistration.registered,
      ),
    );

    expect(find.text('Notifications are off'), findsOneWidget);
    await tester.tap(find.text('Settings'));
    await tester.pump();

    expect(opened, ['opened']);
  });

  testWidgets('never asked: Allow asks, then re-checks', (tester) async {
    final (service, _) = await _pump(
      tester,
      const PushStatus(
        permission: PushPermission.notDetermined,
        registration: PushRegistration.registered,
      ),
    );

    await tester.tap(find.text('Allow'));
    await tester.pump();

    expect(service.permissionRequests, 1);
    expect(service.reconciles, [true]);
  });

  testWidgets('registration failed: says so, and Retry forces a reconcile', (
    tester,
  ) async {
    final (service, _) = await _pump(
      tester,
      const PushStatus(
        permission: PushPermission.granted,
        registration: PushRegistration.failed,
      ),
    );

    expect(find.text('Could not connect this device'), findsOneWidget);
    await tester.tap(find.text('Retry'));
    await tester.pump();

    expect(service.reconciles, [true]);
  });

  testWidgets('token unavailable: waiting, with Retry', (tester) async {
    await _pump(
      tester,
      const PushStatus(
        permission: PushPermission.granted,
        registration: PushRegistration.tokenUnavailable,
      ),
    );

    expect(find.text('Waiting for this device'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
  });

  testWidgets('follows the service as its status changes', (tester) async {
    final (service, _) = await _pump(
      tester,
      const PushStatus(
        permission: PushPermission.granted,
        registration: PushRegistration.pending,
      ),
    );
    expect(find.text('Connecting this device…'), findsOneWidget);

    service.status.value = const PushStatus(
      permission: PushPermission.granted,
      registration: PushRegistration.registered,
    );
    await tester.pump();

    expect(find.text('Notifications are on'), findsOneWidget);
  });
}
