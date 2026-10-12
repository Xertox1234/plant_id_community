import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:permission_handler/permission_handler.dart' as permissions;

import '../../services/push_registration_service.dart';

/// The words and the one action the tile shows for a [PushStatus] (todo
/// 621). A pure function so every state is testable without a device.
@immutable
class NotificationStatusCopy {
  const NotificationStatusCopy(this.title, this.subtitle, [this.action]);

  final String title;
  final String subtitle;
  final NotificationStatusAction? action;
}

enum NotificationStatusAction {
  /// Ask for permission now (never asked before).
  allow,

  /// Open the OS settings for this app (the user turned it off).
  openSettings,

  /// Try the registration again now.
  retry,
}

/// What the user is told. Permission first: a registration is no use if the
/// OS will not show anything. Android still registers a denied device (data
/// arrives, the tray stays silent), so "off" never claims the device is
/// unregistered, only that nothing will be shown.
NotificationStatusCopy notificationStatusCopy(PushStatus status) {
  const signedOut = NotificationStatusCopy(
    'Notifications',
    'Sign in to get replies and care reminders on this device.',
  );
  if (status.registration == PushRegistration.signedOut) return signedOut;
  switch (status.permission) {
    case PushPermission.denied:
      return const NotificationStatusCopy(
        'Notifications are off',
        'Turn them on in Settings to see replies and care reminders.',
        NotificationStatusAction.openSettings,
      );
    case PushPermission.notDetermined:
      return const NotificationStatusCopy(
        'Notifications are not set up',
        'Allow notifications to see replies and care reminders.',
        NotificationStatusAction.allow,
      );
    case PushPermission.granted:
    case PushPermission.unknown:
      break;
  }
  switch (status.registration) {
    case PushRegistration.registered:
      return const NotificationStatusCopy(
        'Notifications are on',
        'This device gets replies and care reminders.',
      );
    case PushRegistration.pending:
      return const NotificationStatusCopy(
        'Connecting this device…',
        'Notifications start once this device is registered.',
      );
    case PushRegistration.tokenUnavailable:
      return const NotificationStatusCopy(
        'Waiting for this device',
        'The device has not given the app a notification address yet.',
        NotificationStatusAction.retry,
      );
    case PushRegistration.failed:
      return const NotificationStatusCopy(
        'Could not connect this device',
        'Notifications will not arrive until it connects.',
        NotificationStatusAction.retry,
      );
    case PushRegistration.signedOut:
      return signedOut;
  }
}

/// Opens this app's page in the OS settings. A provider so a widget test
/// can replace it.
final openAppSettingsProvider = Provider<Future<void> Function()>(
  (ref) => () async {
    await permissions.openAppSettings();
  },
);

/// The settings screen's push status row (todo 621): what the OS allows,
/// whether this device is registered, and the one thing to do about it.
class NotificationStatusTile extends ConsumerWidget {
  const NotificationStatusTile({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final service = ref.watch(pushRegistrationServiceProvider);
    return ValueListenableBuilder<PushStatus>(
      valueListenable: service.status,
      builder: (context, status, _) {
        final copy = notificationStatusCopy(status);
        return ListTile(
          leading: Icon(
            status.permission == PushPermission.denied
                ? LucideIcons.bellOff
                : LucideIcons.bell,
          ),
          title: Text(copy.title),
          subtitle: Text(copy.subtitle),
          trailing: switch (copy.action) {
            null => null,
            NotificationStatusAction.allow => TextButton(
              onPressed: () async {
                await service.requestPermission();
                await service.reconcile(force: true);
              },
              child: const Text('Allow'),
            ),
            NotificationStatusAction.openSettings => TextButton(
              onPressed: () => ref.read(openAppSettingsProvider)(),
              child: const Text('Settings'),
            ),
            NotificationStatusAction.retry => TextButton(
              onPressed: () => service.reconcile(force: true),
              child: const Text('Retry'),
            ),
          },
        );
      },
    );
  }
}
