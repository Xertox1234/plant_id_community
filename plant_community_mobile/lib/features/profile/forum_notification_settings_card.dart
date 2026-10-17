import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_timezone/flutter_timezone.dart';

import '../../services/api_service.dart';
import '../../services/user_profile_service.dart';
import '../forum/models/models.dart';
import '../forum/services/forum_api.dart';

/// Shown when a notification save hits a 429. Master-switch toggles share
/// the 30/h `profile_updates` throttle with the profile form (owner
/// decision 2026-10-12, todo 651); web Settings shows the same words.
const notificationThrottledText =
    'Too many changes. Try again in a few minutes.';

/// An API error's own message, which our views write for users, or null.
/// Never the exception's `toString()`, which can carry a request URL or a
/// Dio dump (todo 651), never an unstructured body such as a proxy's HTML
/// page, and never Dio's own text for a failure with no HTTP status. A master-switch save fails as a UserProfileException, which
/// carries the same message (todo 651 review).
String? apiErrorMessage(Object error) => switch (error) {
  ApiException(:final message, statusCode: _?, unstructured: false)
      when message.isNotEmpty =>
    message,
  UserProfileException(:final apiMessage?) when apiMessage.isNotEmpty =>
    apiMessage,
  _ => null,
};

/// A failed notification save as a line fit to show a user (todo 651): the
/// throttle text on a 429, else `$action: <API message>`, or `$action.` when
/// there is no API message to show.
String notificationErrorText(Object error, {required String action}) {
  final status = switch (error) {
    ApiException(:final statusCode) => statusCode,
    UserProfileException(:final statusCode) => statusCode,
    _ => null,
  };
  if (status == 429) return notificationThrottledText;
  final message = apiErrorMessage(error);
  return message == null ? '$action.' : '$action: $message';
}

/// The forum digest and per-event push/email choices (todo 620), the same
/// fields web Settings edits through the same endpoint, so the two clients
/// always show one set of choices (docs/notifications-policy.md).
///
/// The account-wide switches above it ([emailOn], [forumOn]) are master
/// switches: off holds these choices back without rewriting them, and this
/// card says so instead of showing switches that would not deliver.
class ForumNotificationSettingsCard extends ConsumerStatefulWidget {
  const ForumNotificationSettingsCard({
    super.key,
    required this.emailOn,
    required this.forumOn,
    this.deviceTimeZone = reportableTimeZone,
  });

  final bool emailOn;
  final bool forumOn;

  /// This device's IANA zone to report with a quiet-hours save, or null.
  /// Injectable for tests; the default asks the platform.
  final Future<String?> Function() deviceTimeZone;

  @override
  ConsumerState<ForumNotificationSettingsCard> createState() =>
      _ForumNotificationSettingsCardState();
}

/// This device's IANA time zone ("America/Denver"), from the platform
/// (owner decision 2026-10-13: `flutter_timezone`), or null when it cannot
/// say. Dart's own `DateTime.timeZoneName` is an abbreviation ("MDT") the
/// server cannot resolve. Quiet hours are wall-clock times in the zone a
/// client reports (owner decision 2026-10-12, todo 624); with none reported
/// the server keeps the zone web Settings sent, or UTC, and this card says
/// which.
Future<String?> reportableTimeZone() async {
  try {
    final zone = (await FlutterTimezone.getLocalTimezone()).identifier;
    return isReportableTimeZone(zone) ? zone : null;
  } catch (_) {
    // No plugin (a test, an unsupported platform) or a platform error.
    return null;
  }
}

/// An IANA "Area/City" name (or UTC) that fits the server's 64-character
/// field; never an abbreviation or a "GMT+02:00" offset.
bool isReportableTimeZone(String zone) =>
    zone.length <= 64 &&
    (zone == 'UTC' ||
        RegExp(r'^[A-Za-z_]+(/[A-Za-z0-9_+\-]+)+$').hasMatch(zone));

/// Row labels, in display order; they match web Settings.
const forumNotificationVerbLabels = <String, String>{
  'reply': 'Replies to topics you follow',
  'mention': 'Mentions',
  'quote': 'Quotes of your posts',
  'solution': 'Answer accepted',
};

const forumNotificationChannelLabels = <String, String>{
  'push': 'Push',
  'email': 'Email',
};

class _ForumNotificationSettingsCardState
    extends ConsumerState<ForumNotificationSettingsCard> {
  ForumNotificationSettings? _settings;
  Object? _loadError;
  bool _saving = false;

  /// The device zone, looked up once per card.
  late final Future<String?> _deviceZone = widget.deviceTimeZone();

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _retry() {
    setState(() {
      _loadError = null;
      _settings = null;
    });
    _load();
  }

  Future<void> _load() async {
    try {
      final settings = await ref
          .read(forumApiProvider)
          .fetchNotificationSettings();
      if (mounted) setState(() => _settings = settings);
    } catch (e) {
      if (mounted) setState(() => _loadError = e);
    }
  }

  /// Optimistic: show [optimistic] while the PATCH is in flight, then the
  /// server's answer; on failure, the last SAVED settings and a snackbar.
  Future<void> _save(
    ForumNotificationSettings optimistic,
    Future<ForumNotificationSettings> Function(ForumApi api) send,
  ) async {
    final previous = _settings;
    if (_saving || previous == null) return;
    setState(() {
      _saving = true;
      _settings = optimistic;
    });
    try {
      final saved = await send(ref.read(forumApiProvider));
      if (mounted) setState(() => _settings = saved);
    } catch (e) {
      if (!mounted) return;
      setState(() => _settings = previous);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            notificationErrorText(
              e,
              action: 'Failed to save notification settings',
            ),
          ),
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _setDigest(bool on) {
    final settings = _settings;
    if (settings == null || !settings.hasDigest) return;
    final frequency = on
        ? ForumNotificationSettings.digestWeekly
        : ForumNotificationSettings.digestOff;
    _save(
      settings.withDigest(frequency),
      (api) => api.updateNotificationSettings(digestFrequency: frequency),
    );
  }

  void _setCell(String verb, String channel, bool value) {
    final settings = _settings;
    if (settings == null) return;
    _save(
      settings.withCell(verb, channel, value),
      (api) => api.updateNotificationSettings(
        preferences: {
          verb: {channel: value},
        },
      ),
    );
  }

  Future<void> _setQuietHours(QuietHours next) async {
    final zone = await _deviceZone;
    if (!mounted) return;
    final settings = _settings;
    final current = settings?.quietHours;
    if (settings == null || current == null) return;
    _save(
      settings.withQuietHours(next.copyWith(timeZone: zone)),
      (api) => api.updateNotificationSettings(
        quietHoursEnabled: next.enabled != current.enabled
            ? next.enabled
            : null,
        quietHoursStart: next.start != current.start ? next.start : null,
        quietHoursEnd: next.end != current.end ? next.end : null,
        timeZone: zone,
      ),
    );
  }

  Future<void> _pickTime(QuietHours quiet, {required bool start}) async {
    final parts = (start ? quiet.start : quiet.end).split(':');
    // The model only keeps in-range "HH:MM"; this is the belt to that
    // brace, so a bad value opens the picker on the default, never throws.
    final hour = int.tryParse(parts.first);
    final minute = parts.length == 2 ? int.tryParse(parts[1]) : null;
    final valid = hour != null && minute != null && hour < 24 && minute < 60;
    final picked = await showTimePicker(
      context: context,
      initialTime: valid
          ? TimeOfDay(hour: hour, minute: minute)
          : TimeOfDay(hour: start ? 22 : 7, minute: 0),
    );
    if (picked == null || !mounted) return;
    final value =
        '${picked.hour.toString().padLeft(2, '0')}:'
        '${picked.minute.toString().padLeft(2, '0')}';
    _setQuietHours(
      start ? quiet.copyWith(start: value) : quiet.copyWith(end: value),
    );
  }

  List<Widget> _quietHoursTiles(QuietHours quiet) => [
    SwitchListTile(
      title: const Text('Quiet hours'),
      subtitle: Text(
        'Pushes and emails that arrive in this window wait until it ends. '
        'The inbox still shows everything, and security email always '
        'sends. Times are in ${quiet.shownZone}.',
      ),
      value: quiet.enabled,
      onChanged: _saving
          ? null
          : (on) => _setQuietHours(quiet.copyWith(enabled: on)),
    ),
    ListTile(
      title: const Text('From'),
      trailing: Text(quiet.start),
      enabled: quiet.enabled && !_saving,
      onTap: () => _pickTime(quiet, start: true),
    ),
    ListTile(
      title: const Text('Until'),
      trailing: Text(quiet.end),
      enabled: quiet.enabled && !_saving,
      onTap: () => _pickTime(quiet, start: false),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final settings = _settings;
    final children = <Widget>[
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Text(
          'Forum notifications by event',
          style: theme.textTheme.titleSmall,
        ),
      ),
      if (!widget.forumOn)
        _Note(
          'Forum notifications are off, so none of these are sent. '
          'They are kept as you set them.',
        )
      else if (!widget.emailOn)
        _Note(
          'Email notifications are off, so the digest and email choices '
          'are not sent. They are kept as you set them.',
        ),
    ];

    if (settings == null) {
      final error = _loadError;
      children.add(
        error == null
            ? const Padding(
                padding: EdgeInsets.all(16),
                child: Text('Loading notification settings…'),
              )
            : ListTile(
                title: const Text('Could not load notification settings'),
                subtitle: Text(
                  apiErrorMessage(error) ?? 'Something went wrong.',
                ),
                trailing: TextButton(
                  onPressed: _retry,
                  child: const Text('Retry'),
                ),
              ),
      );
    } else {
      // No known cadence from the server: not offered, never guessed.
      if (settings.hasDigest) {
        children.add(
          SwitchListTile(
            title: const Text('Weekly forum digest'),
            subtitle: const Text(
              'An email of new replies on topics you follow and active topics',
            ),
            value: settings.digestOn,
            onChanged: _saving ? null : _setDigest,
          ),
        );
      }
      for (final verb in forumNotificationVerbLabels.entries) {
        for (final channel in forumNotificationChannelLabels.entries) {
          final value = settings.cell(verb.key, channel.key);
          // No such cell: the channel has no delivery path for this event.
          if (value == null) continue;
          children.add(
            SwitchListTile(
              title: Text('${verb.value}: ${channel.value}'),
              value: value,
              onChanged: _saving
                  ? null
                  : (on) => _setCell(verb.key, channel.key, on),
            ),
          );
        }
      }
      if (settings.cell('mention', 'email') != null) {
        children.add(
          _Note(
            'Email for mentions, quotes and accepted answers is off until you '
            'turn it on. A mention in a topic you follow sends one email: the '
            'mention email if it is on, otherwise the reply email.',
          ),
        );
      }
      final quiet = settings.quietHours;
      if (quiet != null) children.addAll(_quietHoursTiles(quiet));
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: children,
    );
  }
}

class _Note extends StatelessWidget {
  const _Note(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Text(
        text,
        style: theme.textTheme.bodySmall?.copyWith(
          color: theme.colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}
